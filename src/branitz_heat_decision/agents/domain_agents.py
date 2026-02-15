"""
Domain-Specific Assistant Agents (Layer 2.5)
Each agent is a specialist that handles one domain end-to-end.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import time
import logging

logger = logging.getLogger(__name__)

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
    
    def _check_cache(self, street_id: str) -> tuple[bool, Any]:
        """Check if valid cached result exists."""
        # Implementation using file-based or in-memory cache
        pass
    
    def _update_cache(self, street_id: str, result: Any):
        """Update cache with new result."""
        pass


class DataPrepAgent(BaseDomainAgent):
    """
    Prep Chef: Prepares raw data, creates clusters, generates profiles.
    Handles: Data loading, OSM extraction, building clustering.
    """
    
    def can_handle(self, intent: str, context: Dict) -> bool:
        return intent in ["DATA_PREPARATION", "PREPARE_DATA", "LOAD_DATA"]
    
    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        
        # Check if data already prepared
        if self._is_data_prepared(street_id):
            logger.info(f"[{self.agent_name}] Data already prepared for {street_id}")
            return AgentResult(
                success=True,
                data={"status": "already_prepared", "street_id": street_id},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"preparation_status": "cached"}
            )
        
        # Execute data preparation
        from branitz_heat_decision.adk.tools import prepare_data_tool
        
        result = prepare_data_tool(
            buildings_path=context.get("buildings_path"),
            streets_path=context.get("streets_path"),
            verbose=True
        )
        
        execution_time = time.time() - start
        
        return AgentResult(
            success=result["status"] == "success",
            data=result,
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "outputs_created": result.get("outputs", {}),
                "preparation_status": "completed"
            },
            errors=[result.get("error")] if result.get("error") else []
        )
    
    def _is_data_prepared(self, street_id: str) -> bool:
        from branitz_heat_decision.config import (
            BUILDINGS_PATH,
            BUILDING_CLUSTER_MAP_PATH,
            HOURLY_PROFILES_PATH
        )
        return all([
            BUILDINGS_PATH.exists(),
            BUILDING_CLUSTER_MAP_PATH.exists(),
            HOURLY_PROFILES_PATH.exists()
        ])


class CHAAgent(BaseDomainAgent):
    """
    Grill Chef: District Heating Network Specialist.
    Handles: Hydraulic simulation, pipe sizing, pressure analysis.
    """
    
    def can_handle(self, intent: str, context: Dict) -> bool:
        cha_intents = ["CHA_SIMULATION", "DISTRICT_HEATING", "VIOLATION_ANALYSIS", 
                       "NETWORK_DESIGN", "CO2_COMPARISON", "LCOH_COMPARISON", "WHAT_IF_SCENARIO"]
        return intent in cha_intents
    
    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}
        
        # Check cache
        cache_hit, cached_data = self._check_cha_cache(street_id)
        if cache_hit and not context.get("force_recalc"):
            logger.info(f"[{self.agent_name}] Using cached CHA for {street_id}")
            return AgentResult(
                success=True,
                data=cached_data,
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"cache_source": "file_system"}
            )
        
        # Run CHA simulation
        from branitz_heat_decision.adk.tools import run_cha_tool
        
        result = run_cha_tool(
            cluster_id=street_id,
            use_trunk_spur=context.get("use_trunk_spur", True),
            plant_wgs84_lat=context.get("plant_lat"),
            plant_wgs84_lon=context.get("plant_lon"),
            optimize_convergence=True,
            verbose=True
        )
        
        execution_time = time.time() - start
        
        # Parse KPIs for structured data
        kpis = {}
        if result.get("outputs", {}).get("kpis"):
            from branitz_heat_decision.config import resolve_cluster_path
            import json
            kpi_path = resolve_cluster_path(street_id, "cha") / "cha_kpis.json"
            with open(kpi_path) as f:
                kpis = json.load(f)
        
        return AgentResult(
            success=result["status"] == "success",
            data={
                "tool_result": result,
                "kpis": kpis,
                "convergence": result.get("convergence", {}),
                "outputs": result.get("outputs", {})
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "convergence_status": result.get("convergence", {}).get("status"),
                "outputs_created": list(result.get("outputs", {}).keys())
            },
            errors=[result.get("error")] if result.get("status") == "error" else []
        )
    
    def _check_cha_cache(self, street_id: str) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        output_dir = resolve_cluster_path(street_id, "cha")
        
        required = [
            output_dir / "cha_kpis.json",
            output_dir / "network.pickle"
        ]
        
        if all(f.exists() for f in required):
            import json
            with open(required[0]) as f:
                return True, json.load(f)
        return False, None


class DHAAgent(BaseDomainAgent):
    """
    Sauté Chef: Heat Pump Grid Specialist.
    Handles: LV grid analysis, voltage violations, hosting capacity.
    """
    
    def can_handle(self, intent: str, context: Dict) -> bool:
        dha_intents = ["DHA_SIMULATION", "HEAT_PUMP", "LV_GRID", "HOSTING_CAPACITY",
                       "VOLTAGE_ANALYSIS", "CO2_COMPARISON", "LCOH_COMPARISON"]
        return intent in dha_intents
    
    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}
        
        # Check cache
        cache_hit, cached_data = self._check_dha_cache(street_id)
        if cache_hit and not context.get("force_recalc"):
            logger.info(f"[{self.agent_name}] Using cached DHA for {street_id}")
            return AgentResult(
                success=True,
                data=cached_data,
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"cache_source": "file_system"}
            )
        
        # Run DHA simulation
        from branitz_heat_decision.adk.tools import run_dha_tool
        
        result = run_dha_tool(
            cluster_id=street_id,
            cop=context.get("cop", 2.8),
            hp_three_phase=context.get("hp_three_phase", True),
            grid_source=context.get("grid_source", "legacy_json"),
            verbose=True
        )
        
        execution_time = time.time() - start
        
        # Parse KPIs
        kpis = {}
        if result.get("outputs", {}).get("kpis"):
            from branitz_heat_decision.config import resolve_cluster_path
            import json
            kpi_path = resolve_cluster_path(street_id, "dha") / "dha_kpis.json"
            with open(kpi_path) as f:
                kpis = json.load(f)
        
        return AgentResult(
            success=result["status"] == "success",
            data={
                "tool_result": result,
                "kpis": kpis,
                "violations": result.get("violations", {}),
                "outputs": result.get("outputs", {})
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "voltage_violations": result.get("violations", {}).get("voltage", 0),
                "line_violations": result.get("violations", {}).get("line", 0)
            },
            errors=[result.get("error")] if result.get("status") == "error" else []
        )
    
    def _check_dha_cache(self, street_id: str) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        output_dir = resolve_cluster_path(street_id, "dha")
        
        if (output_dir / "dha_kpis.json").exists():
            import json
            with open(output_dir / "dha_kpis.json") as f:
                return True, json.load(f)
        return False, None


class EconomicsAgent(BaseDomainAgent):
    """
    Pastry Chef: Economic Analysis Specialist.
    Handles: LCOH calculation, CO2 emissions, Monte Carlo simulation.
    """
    
    def can_handle(self, intent: str, context: Dict) -> bool:
        econ_intents = ["ECONOMICS", "LCOH_COMPARISON", "CO2_COMPARISON", 
                       "COST_ANALYSIS", "MONTE_CARLO"]
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
                errors=["CHA and DHA results required before economics"]
            )
        
        # Check cache
        cache_hit, cached_data = self._check_economics_cache(street_id)
        if cache_hit and not context.get("force_recalc"):
            logger.info(f"[{self.agent_name}] Using cached economics for {street_id}")
            return AgentResult(
                success=True,
                data=cached_data,
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"cache_source": "file_system"}
            )
        
        # Run economics
        from branitz_heat_decision.adk.tools import run_economics_tool
        
        result = run_economics_tool(
            cluster_id=street_id,
            n_samples=context.get("n_samples", 500),
            seed=context.get("seed", 42),
            verbose=True
        )
        
        execution_time = time.time() - start
        
        # Load deterministic results
        econ_data = {}
        if result.get("outputs", {}).get("deterministic"):
            from branitz_heat_decision.config import resolve_cluster_path
            import json
            econ_path = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
            with open(econ_path) as f:
                econ_data = json.load(f)
        
        return AgentResult(
            success=result["status"] == "success",
            data={
                "tool_result": result,
                "economics": econ_data,
                "win_fractions": result.get("win_fractions"),
                "outputs": result.get("outputs", {})
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "lcoh_dh": econ_data.get("lcoh_dh_eur_per_mwh"),
                "lcoh_hp": econ_data.get("lcoh_hp_eur_per_mwh"),
                "co2_dh": econ_data.get("co2_dh_t_per_a"),
                "co2_hp": econ_data.get("co2_hp_t_per_a"),
                "winner": "DH" if econ_data.get("lcoh_dh_eur_per_mwh", 0) < econ_data.get("lcoh_hp_eur_per_mwh", 0) else "HP"
            },
            errors=[result.get("error")] if result.get("status") == "error" else []
        )
    
    def _check_cha_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "cha") / "cha_kpis.json").exists()
    
    def _check_dha_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "dha") / "dha_kpis.json").exists()
    
    def _check_economics_cache(self, street_id: str) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        econ_file = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
        
        if econ_file.exists():
            import json
            with open(econ_file) as f:
                return True, json.load(f)
        return False, None


class DecisionAgent(BaseDomainAgent):
    """
    Expediter: Final Decision Specialist.
    Handles: KPI contracts, rule-based decision, explanation generation.
    """
    
    def can_handle(self, intent: str, context: Dict) -> bool:
        decision_intents = ["DECISION", "RECOMMENDATION", "EXPLAIN_DECISION", 
                           "FINAL_CHOICE", "WHAT_SHOULD_WE_DO"]
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
                errors=["Economics results required before decision"]
            )
        
        # Run decision
        from branitz_heat_decision.adk.tools import run_decision_tool
        
        result = run_decision_tool(
            cluster_id=street_id,
            llm_explanation=context.get("llm_explanation", True),
            explanation_style=context.get("style", "executive"),
            no_fallback=context.get("no_fallback", False),
            verbose=True
        )
        
        execution_time = time.time() - start
        
        # Load decision result
        decision_data = result.get("decision", {})
        
        return AgentResult(
            success=result["status"] == "success",
            data={
                "tool_result": result,
                "decision": decision_data,
                "recommendation": decision_data.get("recommendation"),
                "robust": decision_data.get("robust", False),
                "outputs": result.get("outputs", {})
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "choice": decision_data.get("recommendation"),
                "robust": decision_data.get("robust"),
                "winner": decision_data.get("winner"),
                "reason_code": decision_data.get("reason_code")
            },
            errors=[result.get("error")] if result.get("status") == "error" else []
        )
    
    def _check_economics_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "economics") / "economics_deterministic.json").exists()


class ValidationAgent(BaseDomainAgent):
    """
    QA Chef: Logic Auditor & Validation Specialist.
    Handles: Claim extraction, TNLI validation, consistency checking.
    """
    
    def can_handle(self, intent: str, context: Dict) -> bool:
        validation_intents = ["VALIDATE", "AUDIT", "CHECK_CLAIMS", "VERIFY_EXPLANATION"]
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
                errors=["No explanation text provided for validation"]
            )
        
        # Load KPIs for validation
        from branitz_heat_decision.config import resolve_cluster_path
        import json
        
        kpis = {}
        econ_path = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
        if econ_path.exists():
            with open(econ_path) as f:
                kpis = json.load(f)
        
        # Run validation
        from branitz_heat_decision.validation.logic_auditor import ClaimExtractor
        
        extractor = ClaimExtractor()
        claims = extractor.extract_all(explanation_text)
        
        # Cross-validate
        mismatches = []
        for claim_type, values in claims.items():
            # Simple validation against KPIs
            if claim_type == "lcoh_dh_median":
                expected = kpis.get("lcoh_dh_eur_per_mwh")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"LCOH DH: claim {values[0]} vs actual {expected}")
            elif claim_type == "co2_dh_median":
                expected = kpis.get("co2_dh_t_per_a")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"CO2 DH: claim {values[0]} vs actual {expected}")
        
        execution_time = time.time() - start
        
        return AgentResult(
            success=len(mismatches) == 0,
            data={
                "claims_extracted": claims,
                "mismatches": mismatches,
                "explanation_text": explanation_text[:200] + "..."
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "claims_found": len(claims),
                "mismatches": len(mismatches),
                "validation_passed": len(mismatches) == 0
            },
            errors=mismatches if mismatches else []
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
                errors=["Decision results required before UHDC report"]
            )
        
        # Run UHDC
        from branitz_heat_decision.adk.tools import run_uhdc_tool
        
        result = run_uhdc_tool(
            cluster_id=street_id,
            llm=context.get("llm", True),
            style=context.get("style", "executive"),
            format=context.get("format", "all"),
            verbose=True
        )
        
        execution_time = time.time() - start
        
        return AgentResult(
            success=result["status"] == "success",
            data={
                "tool_result": result,
                "outputs": result.get("outputs", {}),
                "report_paths": {
                    "html": result.get("outputs", {}).get("html"),
                    "markdown": result.get("outputs", {}).get("markdown"),
                    "json": result.get("outputs", {}).get("json")
                }
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "formats_generated": list(result.get("outputs", {}).keys()),
                "all_outputs_exist": all(result.get("outputs", {}).values())
            },
            errors=[result.get("error")] if result.get("status") == "error" else []
        )
    
    def _check_decision_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "decision") / f"decision_{street_id}.json").exists()


# Agent Registry for easy access
AGENT_REGISTRY = {
    "data_prep": DataPrepAgent,
    "cha": CHAAgent,
    "dha": DHAAgent,
    "economics": EconomicsAgent,
    "decision": DecisionAgent,
    "validation": ValidationAgent,
    "uhdc": UHDCAgent,
}

def get_agent(agent_name: str, **kwargs) -> BaseDomainAgent:
    """Factory function to get agent instance."""
    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(AGENT_REGISTRY.keys())}")
    return AGENT_REGISTRY[agent_name](**kwargs)