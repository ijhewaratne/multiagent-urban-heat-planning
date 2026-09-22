"""
Shared base for domain-specific assistant agents (Layer 2.5).

Each agent is a specialist that handles one domain end-to-end.
Delegates to ADK agents (adk/agent.py) for tool execution instead of
calling ADK tool functions directly.  This gives us:
  - Policy enforcement (guardrails before every tool call)
  - Trajectory tracking (full audit trail per agent)
  - Structured AgentAction results with timestamps
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Iterable, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import of ADK agent classes (avoids circular / heavy imports at load)
# ---------------------------------------------------------------------------
def _get_adk_agents():
    """Import ADK agent classes (tool-level, ADK-prefixed)."""
    from branitz_heat_decision.adk.agent import (
        ADKDataPrepAgent,
        ADKCHAAgent,
        ADKDHAAgent,
        ADKEconomicsAgent,
        ADKDecisionAgent,
        ADKUHDCAgent,
        AgentAction,
    )
    return {
        "DataPrep": ADKDataPrepAgent,
        "CHA": ADKCHAAgent,
        "DHA": ADKDHAAgent,
        "Economics": ADKEconomicsAgent,
        "Decision": ADKDecisionAgent,
        "UHDC": ADKUHDCAgent,
        "AgentAction": AgentAction,
    }


@dataclass
class AgentResult:
    """Standard result format from all domain agents."""
    success: bool
    data: Dict[str, Any]
    execution_time: float
    cache_hit: bool
    agent_name: str
    metadata: Dict[str, Any]
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BaseDomainAgent(ABC):
    """
    Base class for all domain agents.
    Like a station chef with their own tools and expertise.
    """

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        self.agent_name = self.__class__.__name__

    @abstractmethod
    def can_handle(self, intent: str, context: Dict) -> bool:
        """Check if this agent can handle the request."""
        pass

    @abstractmethod
    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        """
        Execute the agent's specialty.
        Returns structured result for integration.
        """
        pass

    def _check_cache(self, street_id: str, context: Dict = None) -> tuple[bool, Any]:
        """Check if valid cached result exists."""
        pass

    def _update_cache(self, street_id: str, result: Any):
        """Update cache with new result."""
        pass

    _TRANSIENT_CACHE_KEYS = {
        "requested_intent",
        "history",
        "run_missing",
        "force_recalc",
        "plan_reinforcement",
        "require_validated_explanation",
        "require_live_llm_explanation",
        "llm_explanation",
        "no_fallback",
        "modification",
    }

    def _compute_cache_key(
        self,
        context: Dict,
        dependency_paths: Optional[Iterable[Path]] = None,
    ) -> str:
        """Hash calculation inputs while ignoring conversation-only context."""
        import hashlib
        import json

        stable_context = {
            key: value
            for key, value in (context or {}).items()
            if key not in self._TRANSIENT_CACHE_KEYS
        }
        dependencies = []
        for raw_path in dependency_paths or []:
            path = Path(raw_path)
            if not path.exists():
                dependencies.append({"name": path.name, "sha256": None})
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            dependencies.append({"name": path.name, "sha256": digest})

        try:
            canonical = json.dumps(
                {"context": stable_context, "dependencies": dependencies},
                sort_keys=True,
                default=str,
            )
            return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        except TypeError as e:
            logger.warning("Context unhashable, falling back to string representation: %s", e)
            return hashlib.sha256(str(stable_context).encode('utf-8')).hexdigest()

    def _write_cache_manifest(
        self,
        manifest_path: Path,
        *,
        input_hash: str,
        calculation_duration_seconds: float,
        calculated_at_utc: Optional[str] = None,
    ) -> Dict[str, Any]:
        import json

        manifest = {
            "cache_schema_version": 2,
            "input_hash": input_hash,
            "calculation_duration_seconds": float(calculation_duration_seconds),
            "calculated_at_utc": calculated_at_utc
            or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "agent": self.agent_name,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    @staticmethod
    def _read_cache_manifest(manifest_path: Path) -> Dict[str, Any]:
        import json

        if not manifest_path.exists():
            return {}
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _cache_timing_metadata(manifest: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "original_calculation_duration_seconds": manifest.get(
                "calculation_duration_seconds"
            ),
            "original_calculated_at_utc": manifest.get("calculated_at_utc"),
        }

    @staticmethod
    def _manifest_matches(
        manifest: Dict[str, Any],
        expected_hash: str,
        manifest_path: Path,
        dependency_paths: Optional[Iterable[Path]] = None,
    ) -> bool:
        if int(manifest.get("cache_schema_version", 1)) >= 2:
            return manifest.get("input_hash") == expected_hash

        # The completed thesis batch contains legacy manifests with a result
        # hash but no schema/timing fields. The artifacts themselves are the
        # canonical completed calculations, so adopt them into the current
        # cache instead of rerunning every street merely to modernize metadata.
        if not manifest.get("input_hash"):
            return False

        import json

        artifact_mtimes = [
            path.stat().st_mtime
            for path in manifest_path.parent.iterdir()
            if path.is_file() and path != manifest_path
        ]
        artifact_timestamp = None
        if artifact_mtimes:
            artifact_timestamp = datetime.fromtimestamp(
                max(artifact_mtimes), timezone.utc
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        adopted = {
            "cache_schema_version": 2,
            "input_hash": expected_hash,
            "calculation_duration_seconds": manifest.get(
                "calculation_duration_seconds"
            ),
            "calculated_at_utc": manifest.get("calculated_at_utc")
            or artifact_timestamp,
            "agent": manifest.get("agent"),
            "legacy_cache_adopted": True,
            "timing_source": "legacy_manifest_or_result_mtime",
        }
        try:
            manifest_path.write_text(json.dumps(adopted, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not upgrade legacy cache manifest %s: %s", manifest_path, exc)
        return True
