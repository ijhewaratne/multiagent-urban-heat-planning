"""
Domain-Specific Assistant Agents (Layer 2.5)

Each agent is a specialist that handles one domain end-to-end.
Delegates to ADK agents (adk/agent.py) for tool execution instead of
calling ADK tool functions directly.  This gives us:
  - Policy enforcement (guardrails before every tool call)
  - Trajectory tracking (full audit trail per agent)
  - Structured AgentAction results with timestamps
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import time
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import of ADK agent classes (avoids circular / heavy imports at load)
# ---------------------------------------------------------------------------
def _get_adk_agents():
    """Import ADK agent classes with aliases to avoid name collision."""
    from branitz_heat_decision.adk.agent import (
        DataPrepAgent as ADKDataPrepAgent,
        CHAAgent as ADKCHAAgent,
        DHAAgent as ADKDHAAgent,
        EconomicsAgent as ADKEconomicsAgent,
        DecisionAgent as ADKDecisionAgent,
        UHDCAgent as ADKUHDCAgent,
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

    def _compute_cache_key(self, context: Dict) -> str:
        """Compute SHA-256 hash of the input context to guarantee canonical determinism."""
        import hashlib
        import json
        try:
            canonical = json.dumps(context or {}, sort_keys=True)
            return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        except TypeError as e:
            logger.warning("Context unhashable, falling back to string representation: %s", e)
            return hashlib.sha256(str(context).encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Concrete domain agents — each delegates to its ADK agent counterpart
# ---------------------------------------------------------------------------


class DataPrepAgent(BaseDomainAgent):
    """
    Prep Chef: Prepares raw data, creates clusters, generates profiles.
    Handles: Data loading, OSM extraction, building clustering.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        return intent in ["DATA_PREPARATION", "PREPARE_DATA", "LOAD_DATA"]

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check if data already prepared
        if self._is_data_prepared(street_id):
            logger.info(f"[{self.agent_name}] Data already prepared for {street_id}")
            return AgentResult(
                success=True,
                data={"status": "already_prepared", "street_id": street_id},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"preparation_status": "cached"},
            )

        # Delegate to ADK DataPrepAgent
        adk = _get_adk_agents()
        adk_agent = adk["DataPrep"](verbose=True)
        action = adk_agent.run(
            buildings_path=context.get("buildings_path"),
            streets_path=context.get("streets_path"),
        )

        result = action.result or {}
        execution_time = time.time() - start

        return AgentResult(
            success=action.status == "success",
            data=result,
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "outputs_created": result.get("outputs", {}),
                "preparation_status": "completed",
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _is_data_prepared(self, street_id: str) -> bool:
        from branitz_heat_decision.config import (
            BUILDINGS_PATH,
            BUILDING_CLUSTER_MAP_PATH,
            HOURLY_PROFILES_PATH,
        )
        return all([
            BUILDINGS_PATH.exists(),
            BUILDING_CLUSTER_MAP_PATH.exists(),
            HOURLY_PROFILES_PATH.exists(),
        ])


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
            return AgentResult(
                success=True,
                data={"kpis": cached_data},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"cache_source": "file_system", "street_id": street_id},
            )

        # Delegate to ADK CHAAgent
        adk = _get_adk_agents()
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
                
                # Write SHA-256 cache manifest
                manifest_path = resolve_cluster_path(street_id, "cha") / "_cache_manifest.json"
                with open(manifest_path, "w") as f:
                    json.dump({"input_hash": self._compute_cache_key(context)}, f)

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
            with open(output_dir / "_cache_manifest.json") as f:
                manifest = json.load(f)
            
            expected_hash = self._compute_cache_key(context or {})
            if manifest.get("input_hash") == expected_hash:
                with open(required[0]) as f:
                    return True, json.load(f)
            else:
                logger.info(f"[{self.agent_name}] Cache hash mismatch. Recomputing.")
        return False, None


class DHAAgent(BaseDomainAgent):
    """
    Sauté Chef: Heat Pump Grid Specialist.
    Handles: LV grid analysis, voltage violations, hosting capacity.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        dha_intents = [
            "DHA_SIMULATION", "HEAT_PUMP", "LV_GRID", "HOSTING_CAPACITY",
            "VOLTAGE_ANALYSIS", "CO2_COMPARISON", "LCOH_COMPARISON",
        ]
        return intent in dha_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check cache
        cache_hit, cached_data = self._check_dha_cache(street_id, context)
        if cache_hit and not context.get("force_recalc"):
            logger.info(f"[{self.agent_name}] Using cached DHA for {street_id}")
            return AgentResult(
                success=True,
                data={"kpis": cached_data},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"cache_source": "file_system", "street_id": street_id},
            )

        # Delegate to ADK DHAAgent
        adk = _get_adk_agents()
        adk_agent = adk["DHA"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            cop=context.get("cop", 2.8),
            hp_three_phase=context.get("hp_three_phase", True),
            grid_source=context.get("grid_source", "legacy_json"),
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
                
                # Write SHA-256 cache manifest
                manifest_path = resolve_cluster_path(street_id, "dha") / "_cache_manifest.json"
                with open(manifest_path, "w") as f:
                    json.dump({"input_hash": self._compute_cache_key(context)}, f)

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
            with open(output_dir / "_cache_manifest.json") as f:
                manifest = json.load(f)
            
            expected_hash = self._compute_cache_key(context or {})
            if manifest.get("input_hash") == expected_hash:
                with open(required[0]) as f:
                    return True, json.load(f)
            else:
                logger.info(f"[{self.agent_name}] Cache hash mismatch. Recomputing.")
        return False, None


class EconomicsAgent(BaseDomainAgent):
    """
    Pastry Chef: Economic Analysis Specialist.
    Handles: LCOH calculation, CO2 emissions, Monte Carlo simulation.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        econ_intents = [
            "ECONOMICS", "LCOH_COMPARISON", "CO2_COMPARISON",
            "COST_ANALYSIS", "MONTE_CARLO",
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
            return AgentResult(
                success=True,
                data={"economics": cached_data},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"cache_source": "file_system"},
            )

        # Delegate to ADK EconomicsAgent
        adk = _get_adk_agents()
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
                
                # Write SHA-256 cache manifest
                manifest_path = resolve_cluster_path(street_id, "economics") / "_cache_manifest.json"
                with open(manifest_path, "w") as f:
                    json.dump({"input_hash": self._compute_cache_key(context)}, f)

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
            with open(manifest_file) as f:
                manifest = json.load(f)
            
            expected_hash = self._compute_cache_key(context or {})
            if manifest.get("input_hash") == expected_hash:
                with open(econ_file) as f:
                    return True, json.load(f)
            else:
                logger.info(f"[{self.agent_name}] Cache hash mismatch. Recomputing.")
        return False, None


class DecisionAgent(BaseDomainAgent):
    """
    Expediter: Final Decision Specialist.
    Handles: KPI contracts, rule-based decision, explanation generation.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        decision_intents = [
            "DECISION", "RECOMMENDATION", "EXPLAIN_DECISION",
            "FINAL_CHOICE", "WHAT_SHOULD_WE_DO",
        ]
        return intent in decision_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check prerequisites
        econ_ready = self._check_economics_exists(street_id)
        if not econ_ready:
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={"prerequisites_missing": {"economics": False}},
                errors=["Economics results required before decision"],
            )

        # Check cache — decision file on disk
        cache_hit, cached_data = self._check_decision_cache(street_id, context)
        if cache_hit and not context.get("force_recalc"):
            sidecars = self._load_decision_sidecars(street_id)
            if context.get("require_validated_explanation") and (
                not sidecars["llm_explanation"] or not sidecars["validation"]
            ):
                logger.info(
                    "[%s] Cached decision for %s missing validated explanation; regenerating.",
                    self.agent_name,
                    street_id,
                )
            else:
                logger.info(f"[{self.agent_name}] Using cached decision for {street_id}")
                return AgentResult(
                    success=True,
                    data={
                        "decision": cached_data,
                        "outputs": {},
                        "llm_explanation": sidecars["llm_explanation"],
                        "validation": sidecars["validation"],
                    },
                    execution_time=time.time() - start,
                    cache_hit=True,
                    agent_name=self.agent_name,
                    metadata={
                        "cache_source": "file_system",
                        "choice": cached_data.get("choice") or cached_data.get("recommendation"),
                        "robust": cached_data.get("robust"),
                        "validation_status": (
                            sidecars["validation"] or {}
                        ).get("validation_status"),
                    },
                )

        # Delegate to ADK DecisionAgent
        adk = _get_adk_agents()
        adk_agent = adk["Decision"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            llm_explanation=context.get("llm_explanation", True),
            explanation_style=context.get("style", "executive"),
            no_fallback=context.get("no_fallback", False),
        )

        result = action.result or {}
        execution_time = time.time() - start

        # Load decision result
        decision_data = result.get("decision", {})
        llm_explanation = result.get("explanation")
        validation = result.get("validation")
        if llm_explanation and not validation:
            logger.warning(
                "[%s] Explanation generated for %s without validation artifact; "
                "suppressing long-form explanation.",
                self.agent_name,
                street_id,
            )
            llm_explanation = None

        # Write SHA-256 cache manifest
        import json
        from branitz_heat_decision.config import resolve_cluster_path
        manifest_path = resolve_cluster_path(street_id, "decision") / "_cache_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({"input_hash": self._compute_cache_key(context)}, f)

        return AgentResult(
            success=action.status == "success",
            data={
                "tool_result": result,
                "decision": decision_data,
                "recommendation": decision_data.get("recommendation"),
                "robust": decision_data.get("robust", False),
                "outputs": result.get("outputs", {}),
                "llm_explanation": llm_explanation,
                "validation": validation,
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "choice": decision_data.get("recommendation"),
                "robust": decision_data.get("robust"),
                "winner": decision_data.get("winner"),
                "reason_code": decision_data.get("reason_code"),
                "validation_status": (validation or {}).get("validation_status"),
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _check_economics_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "economics") / "economics_deterministic.json").exists()

    def _check_decision_cache(self, street_id: str, context: Dict = None) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        dec_file = resolve_cluster_path(street_id, "decision") / f"decision_{street_id}.json"
        manifest_file = resolve_cluster_path(street_id, "decision") / "_cache_manifest.json"
        
        if dec_file.exists() and manifest_file.exists():
            import json
            with open(manifest_file) as f:
                manifest = json.load(f)
            
            expected_hash = self._compute_cache_key(context or {})
            if manifest.get("input_hash") == expected_hash:
                with open(dec_file) as f:
                    return True, json.load(f)
            else:
                logger.info(f"[{self.agent_name}] Cache hash mismatch. Recomputing.")
        return False, None

    def _load_decision_sidecars(self, street_id: str) -> Dict[str, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        import json

        output_dir = resolve_cluster_path(street_id, "decision")
        explanation_text = None
        validation = None

        explanation_path = output_dir / f"explanation_{street_id}.md"
        if explanation_path.exists():
            try:
                explanation_text = explanation_path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to load explanation for %s: %s",
                    self.agent_name,
                    street_id,
                    exc,
                )

        validation_path = output_dir / f"validation_{street_id}.json"
        if validation_path.exists():
            try:
                with open(validation_path, "r", encoding="utf-8") as f:
                    validation = json.load(f)
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to load validation for %s: %s",
                    self.agent_name,
                    street_id,
                    exc,
                )

        if explanation_text and not validation:
            explanation_text = None

        return {
            "llm_explanation": explanation_text,
            "validation": validation,
        }


class ValidationAgent(BaseDomainAgent):
    """
    QA Chef: Logic Auditor & Validation Specialist.

    Two-stage validation pipeline:
      1. **ClaimExtractor** — regex-based extraction of quantitative claims
         from explanation text (LCOH, CO2, etc.) + cross-check vs KPIs.
      2. **TNLIModel** (LightweightValidator) — Tabular Natural Language
         Inference: rule-based + optional LLM verification of qualitative
         statements (comparisons, feasibility, robustness claims).

    No ADK agent equivalent — uses validation module directly.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        validation_intents = [
            "VALIDATE", "AUDIT", "CHECK_CLAIMS", "VERIFY_EXPLANATION",
        ]
        return intent in validation_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        explanation_text = context.get("explanation_text")
        if not explanation_text:
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={},
                errors=["No explanation text provided for validation"],
            )

        # ------------------------------------------------------------------
        # Load KPIs (economics + decision) for both stages
        # ------------------------------------------------------------------
        from branitz_heat_decision.config import resolve_cluster_path
        import json

        kpis: Dict[str, Any] = {}
        econ_path = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
        if econ_path.exists():
            with open(econ_path) as f:
                kpis = json.load(f)

        # Merge decision data so TNLI can validate choice / robustness claims
        dec_path = resolve_cluster_path(street_id, "decision") / f"decision_{street_id}.json"
        if dec_path.exists():
            with open(dec_path) as f:
                dec = json.load(f)
            for key in ("choice", "recommendation", "robust", "reason_codes",
                        "dh_wins_fraction", "hp_wins_fraction",
                        "dh_feasible", "hp_feasible"):
                if key in dec and key not in kpis:
                    kpis[key] = dec[key]

        # ------------------------------------------------------------------
        # Stage 1: ClaimExtractor — quantitative claim extraction + check
        # ------------------------------------------------------------------
        from branitz_heat_decision.validation.logic_auditor import ClaimExtractor

        extractor = ClaimExtractor()
        claims = extractor.extract_all(explanation_text)

        mismatches = []
        for claim_type, values in claims.items():
            if claim_type == "lcoh_dh_median":
                expected = kpis.get("lcoh_dh_eur_per_mwh")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"LCOH DH: claim {values[0]} vs actual {expected}")
            elif claim_type == "lcoh_hp_median":
                expected = kpis.get("lcoh_hp_eur_per_mwh")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"LCOH HP: claim {values[0]} vs actual {expected}")
            elif claim_type == "co2_dh_median":
                expected = kpis.get("co2_dh_t_per_a")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"CO2 DH: claim {values[0]} vs actual {expected}")
            elif claim_type == "co2_hp_median":
                expected = kpis.get("co2_hp_t_per_a")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"CO2 HP: claim {values[0]} vs actual {expected}")

        # ------------------------------------------------------------------
        # Stage 2: TNLI — semantic / qualitative statement validation
        # ------------------------------------------------------------------
        tnli_results = []
        tnli_contradictions = 0
        tnli_verified = 0
        try:
            from branitz_heat_decision.validation.tnli_model import TNLIModel

            tnli = TNLIModel()
            # Split explanation into individual sentences for validation
            sentences = [
                s.strip() for s in explanation_text.replace("\n", ". ").split(".")
                if len(s.strip()) > 10
            ]
            for sentence in sentences:
                result = tnli.validate_statement(kpis, sentence)
                tnli_results.append({
                    "statement": result.statement,
                    "label": result.label.value,
                    "confidence": result.confidence,
                    "reason": result.reason,
                })
                if result.is_contradiction:
                    tnli_contradictions += 1
                    mismatches.append(f"TNLI contradiction: '{sentence[:80]}…' — {result.reason}")
                elif result.is_valid:
                    tnli_verified += 1
        except Exception as exc:
            logger.warning(f"[{self.agent_name}] TNLI stage skipped: {exc}")

        execution_time = time.time() - start
        all_passed = len(mismatches) == 0

        return AgentResult(
            success=all_passed,
            data={
                "claims_extracted": claims,
                "mismatches": mismatches,
                "tnli_results": tnli_results,
                "explanation_text": explanation_text[:200] + "...",
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "claims_found": len(claims),
                "mismatches": len(mismatches),
                "tnli_verified": tnli_verified,
                "tnli_contradictions": tnli_contradictions,
                "tnli_total": len(tnli_results),
                "validation_passed": all_passed,
            },
            errors=mismatches if mismatches else [],
        )


class UHDCAgent(BaseDomainAgent):
    """
    Plating Chef: Report Generation Specialist.
    Handles: Final report assembly, HTML/Markdown/JSON output.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        uhdc_intents = ["UHDC", "REPORT", "GENERATE_REPORT", "FINAL_OUTPUT"]
        return intent in uhdc_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check prerequisites
        decision_ready = self._check_decision_exists(street_id)
        if not decision_ready:
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={},
                errors=["Decision results required before UHDC report"],
            )

        # Delegate to ADK UHDCAgent
        adk = _get_adk_agents()
        adk_agent = adk["UHDC"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            llm=context.get("llm", True),
            style=context.get("style", "executive"),
            format=context.get("format", "all"),
        )

        result = action.result or {}
        execution_time = time.time() - start

        return AgentResult(
            success=action.status == "success",
            data={
                "tool_result": result,
                "outputs": result.get("outputs", {}),
                "report_paths": {
                    "html": result.get("outputs", {}).get("html"),
                    "markdown": result.get("outputs", {}).get("markdown"),
                    "json": result.get("outputs", {}).get("json"),
                },
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "formats_generated": list(result.get("outputs", {}).keys()),
                "all_outputs_exist": all(result.get("outputs", {}).values()),
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _check_decision_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "decision") / f"decision_{street_id}.json").exists()


class WhatIfAgent(BaseDomainAgent):
    """
    Sous Chef: What-If Scenario Specialist.

    Handles "What if we remove 2 houses?" by:
      1. Ensuring baseline CHA network exists (via CHAAgent)
      2. Cloning the pandapipes network
      3. Applying modifications (disable heat consumers)
      4. Re-running pipeflow on the modified network
      5. Comparing baseline vs scenario (pressure, heat, violations)
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        return intent in ["WHAT_IF_SCENARIO", "WHAT_IF", "SCENARIO_ANALYSIS"]

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        import pickle

        start = time.time()
        context = context or {}
        modification = context.get("modification", "")

        # --- pandapipes required ---
        try:
            import pandapipes as pp
        except ImportError:
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={},
                errors=["pandapipes not installed — required for what-if scenarios"],
            )

        # 1. Ensure baseline CHA (delegate to CHAAgent)
        cha = CHAAgent(cache_dir=self.cache_dir)
        cha_result = cha.execute(street_id, context)
        if not cha_result.success:
            return AgentResult(
                success=False,
                data={},
                execution_time=time.time() - start,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={"cha_result": "failed"},
                errors=["CHA baseline failed: " + "; ".join(cha_result.errors)],
            )

        # 2. Load baseline network
        from branitz_heat_decision.config import resolve_cluster_path

        network_path = resolve_cluster_path(street_id, "cha") / "network.pickle"
        if not network_path.exists():
            return AgentResult(
                success=False,
                data={},
                execution_time=time.time() - start,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={},
                errors=["network.pickle not found"],
            )

        with open(network_path, "rb") as f:
            baseline_net = pickle.load(f)

        # 3. Clone + modify
        scenario_net = pickle.loads(pickle.dumps(baseline_net))

        n_houses = self._parse_house_count(modification)
        mod_log = []
        if n_houses > 0:
            try:
                scenario_net = self._exclude_houses(scenario_net, n_houses)
                mod_log.append(f"Modified network: excluded {n_houses} houses")
            except ValueError as e:
                return AgentResult(
                    success=False,
                    data={},
                    execution_time=time.time() - start,
                    cache_hit=False,
                    agent_name=self.agent_name,
                    metadata={},
                    errors=[str(e)],
                )

        # 4. Re-run pipeflow
        try:
            pp.pipeflow(scenario_net, mode="all", iter=100, tol_p=1e-4, tol_v=1e-4)
            mod_log.append("Ran scenario pipeflow")
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                execution_time=time.time() - start,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={},
                errors=[f"Scenario pipeflow failed: {e}"],
            )

        # 5. Compare baseline vs scenario
        comparison = self._compare_scenarios(baseline_net, scenario_net)

        execution_time = time.time() - start
        return AgentResult(
            success=True,
            data={
                "baseline": {
                    "co2_tons": self._calculate_dh_co2(baseline_net),
                    "max_pressure_bar": self._get_max_pressure(baseline_net),
                },
                "scenario": {
                    "co2_tons": self._calculate_dh_co2(scenario_net),
                    "max_pressure_bar": self._get_max_pressure(scenario_net),
                },
                "comparison": comparison,
                "modification_applied": modification,
            },
            execution_time=execution_time,
            cache_hit=cha_result.cache_hit,  # reflects whether CHA was cached
            agent_name=self.agent_name,
            metadata={
                "houses_removed": n_houses,
                "modification_log": mod_log,
                "cha_cache_hit": cha_result.cache_hit,
            },
        )

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def _parse_house_count(modification: str) -> int:
        """Parse 'remove 2 houses' → 2."""
        mod_lower = modification.lower().replace(" ", "_")
        if "remove" in mod_lower and ("house" in mod_lower or "building" in mod_lower):
            for part in modification.replace(" ", "_").split("_"):
                if part.isdigit():
                    return int(part)
        return 0

    @staticmethod
    def _exclude_houses(net: Any, n_houses: int) -> Any:
        """Disable the last *n_houses* terminal demand elements."""
        table_name, table = WhatIfAgent._get_terminal_table(net)
        if table_name is None or table is None or table.empty:
            raise ValueError("Network has no heat_consumer or heat_exchanger table")

        consumers = (
            table[table["in_service"] == True]
            if "in_service" in table.columns
            else table
        )
        if len(consumers) <= n_houses:
            raise ValueError(f"Cannot remove {n_houses} houses, only {len(consumers)} available")

        for idx in consumers.index[-n_houses:].tolist():
            if "in_service" in table.columns:
                table.loc[idx, "in_service"] = False
            for demand_col in ("qext_w", "controlled_mdot_kg_per_s"):
                if demand_col in table.columns:
                    table.loc[idx, demand_col] = 0.0

        setattr(net, table_name, table)
        return net

    @staticmethod
    def _calculate_dh_co2(net: Any) -> float:
        """Approximate annual CO₂ from DH network."""
        try:
            total_w = WhatIfAgent._get_total_heat_w(net)
            if total_w <= 0:
                return 0.0
            return float(total_w * 1e-6 * 8760 * 0.15 * 0.2)
        except Exception:
            return 0.0

    @staticmethod
    def _get_max_pressure(net: Any) -> float:
        try:
            if hasattr(net, "res_junction") and net.res_junction is not None and not net.res_junction.empty:
                if "p_bar" in net.res_junction.columns:
                    return float(net.res_junction["p_bar"].max())
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _count_violations(net: Any) -> int:
        try:
            if hasattr(net, "res_junction") and net.res_junction is not None:
                if "p_bar" in net.res_junction.columns:
                    return int((net.res_junction["p_bar"] > 6).sum())
        except Exception:
            pass
        return 0

    def _compare_scenarios(self, baseline: Any, scenario: Any) -> Dict[str, Any]:
        base_p = self._get_max_pressure(baseline)
        scen_p = self._get_max_pressure(scenario)

        return {
            "pressure_change_bar": scen_p - base_p,
            "heat_delivered_change_mw": (
                self._get_total_heat_w(scenario) - self._get_total_heat_w(baseline)
            ) * 1e-6,
            "violation_reduction": self._count_violations(baseline) - self._count_violations(scenario),
        }

    @staticmethod
    def _get_terminal_table(net: Any) -> tuple[Optional[str], Any]:
        """Return the active terminal demand table used by this network."""
        for table_name in ("heat_consumer", "heat_exchanger"):
            table = getattr(net, table_name, None)
            if table is not None and hasattr(table, "empty") and not table.empty:
                return table_name, table
        return None, None

    @staticmethod
    def _get_total_heat_w(net: Any) -> float:
        """Best-effort heat extraction across supported pandapipes terminal tables."""
        result_tables = (
            ("res_heat_consumer", "qext_w"),
            ("res_heat_exchanger", "qext_w"),
        )
        for table_name, value_col in result_tables:
            table = getattr(net, table_name, None)
            if table is not None and hasattr(table, "empty") and not table.empty:
                if value_col in table.columns:
                    return float(table[value_col].sum())

        element_tables = (
            ("heat_consumer", "qext_w"),
            ("heat_exchanger", "qext_w"),
        )
        for table_name, value_col in element_tables:
            table = getattr(net, table_name, None)
            if table is not None and hasattr(table, "empty") and not table.empty:
                if value_col in table.columns:
                    return float(table[value_col].sum())

        return 0.0


# Agent Registry for easy access
AGENT_REGISTRY = {
    "data_prep": DataPrepAgent,
    "cha": CHAAgent,
    "dha": DHAAgent,
    "economics": EconomicsAgent,
    "decision": DecisionAgent,
    "validation": ValidationAgent,
    "uhdc": UHDCAgent,
    "what_if": WhatIfAgent,
}


def get_agent(agent_name: str, **kwargs) -> BaseDomainAgent:
    """Factory function to get agent instance."""
    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(AGENT_REGISTRY.keys())}")
    return AGENT_REGISTRY[agent_name](**kwargs)
