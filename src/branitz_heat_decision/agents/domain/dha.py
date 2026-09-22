"""DHA (LV grid / heat pump) domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

logger = logging.getLogger(__name__)


class DHAAgent(BaseDomainAgent):
    """
    Sauté Chef: Heat Pump Grid Specialist.
    Handles: LV grid analysis, voltage violations, hosting capacity.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        dha_intents = [
            "DHA_SIMULATION", "HEAT_PUMP", "LV_GRID", "HOSTING_CAPACITY",
            "VOLTAGE_ANALYSIS", "CO2_COMPARISON", "LCOH_COMPARISON",
            "GRID_REINFORCEMENT",
        ]
        return intent in dha_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        from branitz_heat_decision.config import resolve_cluster_path

        reinforcement_path = (
            resolve_cluster_path(street_id, "dha") / "dha_reinforcement.json"
        )
        reinforcement_required = bool(
            context.get("plan_reinforcement") and not reinforcement_path.exists()
        )

        # Check cache
        cache_hit, cached_data = self._check_dha_cache(street_id, context)
        if cache_hit and not context.get("force_recalc") and not reinforcement_required:
            logger.info(f"[{self.agent_name}] Using cached DHA for {street_id}")
            manifest = self._read_cache_manifest(
                resolve_cluster_path(street_id, "dha") / "_cache_manifest.json"
            )
            return AgentResult(
                success=True,
                data={"kpis": cached_data},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={
                    "cache_source": "file_system",
                    "street_id": street_id,
                    **self._cache_timing_metadata(manifest),
                },
            )

        # Delegate to ADK DHAAgent
        adk = base._get_adk_agents()
        adk_agent = adk["DHA"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            cop=context.get("cop", 2.8),
            hp_three_phase=context.get("hp_three_phase", True),
            grid_source=context.get("grid_source", "legacy_json"),
            plan_reinforcement=bool(context.get("plan_reinforcement")),
        )

        result = action.result or {}
        execution_time = time.time() - start

        # Parse KPIs
        kpis = {}
        if result.get("outputs", {}).get("kpis"):
            from branitz_heat_decision.config import resolve_cluster_path
            import json
            kpi_path = resolve_cluster_path(street_id, "dha") / "dha_kpis.json"
            if kpi_path.exists():
                with open(kpi_path) as f:
                    kpis = json.load(f)
                
                manifest_path = resolve_cluster_path(street_id, "dha") / "_cache_manifest.json"
                self._write_cache_manifest(
                    manifest_path,
                    input_hash=self._compute_cache_key(context),
                    calculation_duration_seconds=execution_time,
                )

        return AgentResult(
            success=action.status == "success",
            data={
                "tool_result": result,
                "kpis": kpis,
                "violations": result.get("violations", {}),
                "outputs": result.get("outputs", {}),
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "street_id": street_id,
                "voltage_violations": result.get("violations", {}).get("voltage", 0),
                "line_violations": result.get("violations", {}).get("line", 0),
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _check_dha_cache(self, street_id: str, context: Dict = None) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        output_dir = resolve_cluster_path(street_id, "dha")

        required = [
            output_dir / "dha_kpis.json",
            output_dir / "_cache_manifest.json",
        ]

        if all(f.exists() for f in required):
            import json
            manifest_path = output_dir / "_cache_manifest.json"
            manifest = self._read_cache_manifest(manifest_path)
            expected_hash = self._compute_cache_key(context or {})
            if self._manifest_matches(manifest, expected_hash, manifest_path):
                with open(required[0]) as f:
                    return True, json.load(f)
            else:
                logger.info(f"[{self.agent_name}] Cache hash mismatch. Recomputing.")
        return False, None
