"""Economics domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

logger = logging.getLogger(__name__)


class EconomicsAgent(BaseDomainAgent):
    """
    Pastry Chef: Economic Analysis Specialist.
    Handles: LCOH calculation, CO2 emissions, Monte Carlo simulation.
    """

    _CACHE_MODEL_VERSION = 2

    def can_handle(self, intent: str, context: Dict) -> bool:
        econ_intents = [
            "ECONOMICS", "LCOH_COMPARISON", "CO2_COMPARISON",
            "COST_ANALYSIS", "MONTE_CARLO", "GRID_REINFORCEMENT",
        ]
        return intent in econ_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check if we have both CHA and DHA results first
        cha_ready = self._check_cha_exists(street_id)
        dha_ready = self._check_dha_exists(street_id)

        if not (cha_ready and dha_ready):
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={"prerequisites_missing": {"cha": cha_ready, "dha": dha_ready}},
                errors=["CHA and DHA results required before economics"],
            )

        # Check cache
        cache_hit, cached_data = self._check_economics_cache(street_id, context)
        if cache_hit and not context.get("force_recalc"):
            logger.info(f"[{self.agent_name}] Using cached economics for {street_id}")
            from branitz_heat_decision.config import resolve_cluster_path
            manifest = self._read_cache_manifest(
                resolve_cluster_path(street_id, "economics") / "_cache_manifest.json"
            )
            return AgentResult(
                success=True,
                data={"economics": cached_data},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={
                    "cache_source": "file_system",
                    **self._cache_timing_metadata(manifest),
                },
            )

        # Delegate to ADK EconomicsAgent
        adk = base._get_adk_agents()
        adk_agent = adk["Economics"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            n_samples=context.get("n_samples", 500),
            seed=context.get("seed", 42),
        )

        result = action.result or {}
        execution_time = time.time() - start

        # Load deterministic results
        econ_data = {}
        if result.get("outputs", {}).get("deterministic"):
            from branitz_heat_decision.config import resolve_cluster_path
            import json
            econ_path = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
            if econ_path.exists():
                with open(econ_path) as f:
                    econ_data = json.load(f)
                
                manifest_path = resolve_cluster_path(street_id, "economics") / "_cache_manifest.json"
                self._write_cache_manifest(
                    manifest_path,
                    input_hash=self._economics_cache_key(street_id, context),
                    calculation_duration_seconds=execution_time,
                )

        return AgentResult(
            success=action.status == "success",
            data={
                "tool_result": result,
                "economics": econ_data,
                "win_fractions": result.get("win_fractions"),
                "outputs": result.get("outputs", {}),
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "lcoh_dh": econ_data.get("lcoh_dh_eur_per_mwh"),
                "lcoh_hp": econ_data.get("lcoh_hp_eur_per_mwh"),
                "co2_dh": econ_data.get("co2_dh_t_per_a"),
                "co2_hp": econ_data.get("co2_hp_t_per_a"),
                "winner": (
                    "DH"
                    if econ_data.get("lcoh_dh_eur_per_mwh", 0) < econ_data.get("lcoh_hp_eur_per_mwh", 0)
                    else "HP"
                ),
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _check_cha_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "cha") / "cha_kpis.json").exists()

    def _check_dha_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "dha") / "dha_kpis.json").exists()

    def _check_economics_cache(self, street_id: str, context: Dict = None) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        econ_file = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
        manifest_file = resolve_cluster_path(street_id, "economics") / "_cache_manifest.json"

        if econ_file.exists() and manifest_file.exists():
            import json
            reinforcement_dir = econ_file.parent / "reinforcement"
            plan_path = resolve_cluster_path(street_id, "dha") / "dha_reinforcement.json"
            if plan_path.exists():
                try:
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    plan = {}
                if plan.get("is_sufficient") and not all(
                    (reinforcement_dir / name).exists()
                    for name in (
                        "economics_deterministic.json",
                        "economics_monte_carlo.json",
                    )
                ):
                    return False, None
            manifest = self._read_cache_manifest(manifest_file)
            dependencies = self._economics_dependencies(street_id)
            expected_hash = self._economics_cache_key(street_id, context or {})
            if self._manifest_matches(
                manifest,
                expected_hash,
                manifest_file,
                dependencies,
            ):
                with open(econ_file) as f:
                    return True, json.load(f)
            else:
                logger.info(f"[{self.agent_name}] Cache hash mismatch. Recomputing.")
        return False, None

    def _economics_cache_key(self, street_id: str, context: Dict) -> str:
        cache_context = {
            **(context or {}),
            "economics_case_schema": self._CACHE_MODEL_VERSION,
        }
        return self._compute_cache_key(
            cache_context,
            self._economics_dependencies(street_id),
        )

    def _economics_dependencies(self, street_id: str):
        from branitz_heat_decision.config import resolve_cluster_path

        return [
            resolve_cluster_path(street_id, "cha") / "cha_kpis.json",
            resolve_cluster_path(street_id, "dha") / "dha_kpis.json",
            resolve_cluster_path(street_id, "dha") / "dha_reinforcement.json",
        ]
