"""CHA (district heating) domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

logger = logging.getLogger(__name__)


class CHAAgent(BaseDomainAgent):
    """
    Grill Chef: District Heating Network Specialist.
    Handles: Hydraulic simulation, pipe sizing, pressure analysis.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        cha_intents = [
            "CHA_SIMULATION", "DISTRICT_HEATING", "VIOLATION_ANALYSIS",
            "NETWORK_DESIGN", "CO2_COMPARISON", "LCOH_COMPARISON",
            "WHAT_IF_SCENARIO",
        ]
        return intent in cha_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check cache first
        cache_hit, cached_data = self._check_cha_cache(street_id, context)
        if cache_hit and not context.get("force_recalc"):
            logger.info(f"[{self.agent_name}] Using cached CHA for {street_id}")
            from branitz_heat_decision.config import resolve_cluster_path
            manifest = self._read_cache_manifest(
                resolve_cluster_path(street_id, "cha") / "_cache_manifest.json"
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

        # Delegate to ADK CHAAgent
        adk = base._get_adk_agents()
        adk_agent = adk["CHA"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            use_trunk_spur=context.get("use_trunk_spur", True),
            plant_wgs84_lat=context.get("plant_lat"),
            plant_wgs84_lon=context.get("plant_lon"),
            optimize_convergence=True,
        )

        result = action.result or {}
        execution_time = time.time() - start

        # Parse KPIs for structured data
        kpis = {}
        if result.get("outputs", {}).get("kpis"):
            from branitz_heat_decision.config import resolve_cluster_path
            import json
            kpi_path = resolve_cluster_path(street_id, "cha") / "cha_kpis.json"
            if kpi_path.exists():
                with open(kpi_path) as f:
                    kpis = json.load(f)
                
                manifest_path = resolve_cluster_path(street_id, "cha") / "_cache_manifest.json"
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
                "convergence": result.get("convergence", {}),
                "outputs": result.get("outputs", {}),
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "street_id": street_id,
                "convergence_status": result.get("convergence", {}).get("status"),
                "outputs_created": list(result.get("outputs", {}).keys()),
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _check_cha_cache(self, street_id: str, context: Dict = None) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        output_dir = resolve_cluster_path(street_id, "cha")

        required = [
            output_dir / "cha_kpis.json",
            output_dir / "network.pickle",
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
