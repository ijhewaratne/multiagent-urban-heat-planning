"""
Dynamic Execution Engine for Branitz Heat Decision AI
Replaces static pipeline with lazy, context-aware simulation execution
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Lazy imports for heavy optional deps
def _get_pp():
    try:
        import pandapipes as pp
        return pp
    except ImportError:
        return None


class SimulationType(Enum):
    """Simulation types in Branitz: DH=CHA, CHA_electrical=DHA (Heat Pumps)."""
    DH_HYDRAULIC = "dh_hydraulic"           # Pandapipes pipeflow (CHA)
    DH_THERMAL = "dh_thermal"              # Heat transfer (bundled in DH_HYDRAULIC)
    CHA_ELECTRICAL = "cha_electrical"        # DHA: pandapower power flow / HP hosting
    CHA_THERMAL = "cha_thermal"             # HP performance (handled by economics)


@dataclass
class SimulationCache:
    """Cache entry for simulation results."""
    network: Any              # pandapipes net or DHA result dict
    results_hash: str         # Hash of inputs to detect stale cache
    timestamp: float          # For cache invalidation
    derived_metrics: Dict     # CO2, LCOH calculated from this simulation


class DynamicExecutor:
    """
    Speaker B's requirement: "Try to achieve it with tools"

    This class:
    1. Maintains simulation cache (avoid re-running)
    2. Executes only required simulations based on intent
    3. Handles "what-if" scenarios (network modifications)
    4. Provides comparison capabilities (baseline vs scenario)
    """

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.active_cache: Dict[str, SimulationCache] = {}
        self.scenario_counter = 0
        self._last_cha_error: Optional[str] = None
        self._last_dha_error: Optional[str] = None
        self._last_economics_error: Optional[str] = None

        # Load persistent cache if exists
        self._load_cache()

    def _get_cache_key(self, street_id: str, sim_type: SimulationType,
                       scenario: str = "baseline") -> str:
        """Generate unique cache key for simulation state."""
        key_string = f"{street_id}_{sim_type.value}_{scenario}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def execute(self, intent: str, street_id: str,
                context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point – executes only simulations needed for intent.

        Args:
            intent: From Phase 1 IntentClassifier (CO2_COMPARISON, etc.)
            street_id: Street cluster identifier
            context: Additional parameters (modifications, etc.)
        """
        context = context or {}

        # Route to specific execution strategy
        if intent == "CO2_COMPARISON":
            return self._execute_co2_comparison(street_id, context)
        elif intent == "LCOH_COMPARISON":
            return self._execute_lcoh_comparison(street_id, context)
        elif intent == "VIOLATION_ANALYSIS":
            return self._execute_violation_check(street_id, context)
        elif intent == "WHAT_IF_SCENARIO":
            return self._execute_what_if(street_id, context)
        elif intent == "NETWORK_DESIGN":
            return self._execute_network_design(street_id, context)
        else:
            raise ValueError(
                f"Unknown or non-simulation intent: {intent}. "
                "Use orchestrator for EXPLAIN_DECISION, CAPABILITY_QUERY."
            )

    def _ensure_cha_results(self, street_id: str) -> bool:
        """Run CHA if needed; return True if success."""
        from branitz_heat_decision.adk.tools import run_cha_tool
        from branitz_heat_decision.config import resolve_cluster_path

        cha_dir = resolve_cluster_path(street_id, "cha")
        if (cha_dir / "cha_kpis.json").exists() and (cha_dir / "network.pickle").exists():
            return True
        result = run_cha_tool(street_id)
        if result.get("status") == "success":
            return True
        self._last_cha_error = result.get("stderr") or result.get("error") or "Unknown error"
        return False

    def _ensure_dha_results(self, street_id: str) -> bool:
        """Run DHA if needed; return True if success."""
        from branitz_heat_decision.adk.tools import run_dha_tool
        from branitz_heat_decision.config import resolve_cluster_path

        dha_dir = resolve_cluster_path(street_id, "dha")
        if (dha_dir / "dha_kpis.json").exists():
            return True
        result = run_dha_tool(street_id)
        return result.get("status") == "success"

    def _ensure_economics_results(self, street_id: str) -> bool:
        """Run Economics if needed; return True if success."""
        from branitz_heat_decision.adk.tools import run_economics_tool
        from branitz_heat_decision.config import resolve_cluster_path

        econ_dir = resolve_cluster_path(street_id, "economics")
        if (econ_dir / "economics_deterministic.json").exists():
            return True
        result = run_economics_tool(street_id)
        return result.get("status") == "success"

    def _load_economics(self, street_id: str) -> Dict[str, Any]:
        """Load economics_deterministic.json."""
        from branitz_heat_decision.config import resolve_cluster_path

        path = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _execute_co2_comparison(self, street_id: str, context: Dict) -> Dict:
        """
        Example: User asks "What's the CO2 impact?"

        Execution Plan:
        1. Run CHA, DHA, Economics if not cached
        2. Load economics_deterministic.json for canonical CO2 values
        """
        execution_log = []

        if not self._ensure_cha_results(street_id):
            execution_log.append("CHA run failed")
            err_detail = (
                self._last_cha_error[:500] if self._last_cha_error else ""
            )
            hint = (
                " Run 00_prepare_data.py first if you haven't prepared the data."
                if err_detail and ("not found" in err_detail.lower() or "filenotfounderror" in err_detail.lower())
                else ""
            )
            return {
                "error": f"CHA simulation failed.{hint}"
                + (f" Details: {err_detail[:200]}..." if err_detail else ""),
                "execution_log": execution_log,
            }
        execution_log.append("CHA results available")

        if not self._ensure_dha_results(street_id):
            execution_log.append("DHA run failed")
            return {"error": "DHA simulation failed", "execution_log": execution_log}
        execution_log.append("DHA results available")

        if not self._ensure_economics_results(street_id):
            execution_log.append("Economics run failed")
            return {"error": "Economics simulation failed", "execution_log": execution_log}
        execution_log.append("Economics results available")

        econ = self._load_economics(street_id)
        co2_dh = econ.get("co2_dh_t_per_a") or econ.get("co2", {}).get("dh") or 0.0
        co2_cha = econ.get("co2_hp_t_per_a") or econ.get("co2", {}).get("hp") or 0.0

        result = {
            "dh_tons_co2": float(co2_dh),
            "hp_tons_co2": float(co2_cha),
            "difference": float(co2_dh - co2_cha),
            "winner": "DH" if co2_dh < co2_cha else "HP",
            "execution_log": execution_log,
        }
        return result

    def _execute_lcoh_comparison(self, street_id: str, context: Dict) -> Dict:
        """LCOH comparison: run CHA, DHA, Economics; use economics_deterministic.json."""
        execution_log = []

        if not self._ensure_cha_results(street_id):
            execution_log.append("CHA run failed")
            return {"error": "CHA simulation failed", "execution_log": execution_log}
        execution_log.append("CHA results available")

        if not self._ensure_dha_results(street_id):
            execution_log.append("DHA run failed")
            return {"error": "DHA simulation failed", "execution_log": execution_log}
        execution_log.append("DHA results available")

        if not self._ensure_economics_results(street_id):
            execution_log.append("Economics run failed")
            return {"error": "Economics simulation failed", "execution_log": execution_log}
        execution_log.append("Economics results available")

        econ = self._load_economics(street_id)
        lcoh_dh = econ.get("lcoh_dh_eur_per_mwh") or econ.get("lcoh", {}).get("dh") or 0.0
        lcoh_hp = econ.get("lcoh_hp_eur_per_mwh") or econ.get("lcoh", {}).get("hp") or 0.0

        return {
            "lcoh_dh_eur_per_mwh": float(lcoh_dh),
            "lcoh_hp_eur_per_mwh": float(lcoh_hp),
            "difference": float(lcoh_hp - lcoh_dh),
            "winner": "DH" if lcoh_dh < lcoh_hp else "CHA",
            "execution_log": execution_log,
        }

    def _execute_violation_check(self, street_id: str, context: Dict) -> Dict:
        """Violation analysis: CHA (pressure/velocity) + DHA (voltage/line)."""
        execution_log = []

        if not self._ensure_cha_results(street_id):
            execution_log.append("CHA run failed")
            return {"error": "CHA simulation failed", "execution_log": execution_log}

        if not self._ensure_dha_results(street_id):
            execution_log.append("DHA run failed")
            return {"error": "DHA simulation failed", "execution_log": execution_log}

        from branitz_heat_decision.config import resolve_cluster_path

        cha_path = resolve_cluster_path(street_id, "cha") / "cha_kpis.json"
        dha_path = resolve_cluster_path(street_id, "dha") / "dha_kpis.json"

        cha_kpis = {}
        if cha_path.exists():
            with open(cha_path, "r") as f:
                cha_kpis = json.load(f)

        dha_kpis = {}
        if dha_path.exists():
            with open(dha_path, "r") as f:
                dha_data = json.load(f)
                dha_kpis = dha_data.get("kpis", dha_data)

        agg = cha_kpis.get("aggregate", {})
        hyd = cha_kpis.get("hydraulics", {})

        return {
            "cha": {
                "converged": cha_kpis.get("convergence", {}).get("converged", None),
                "pressure_bar_max": cha_kpis.get("pressure_bar_max"),
                "velocity_ms_max": agg.get("v_max_ms") or hyd.get("max_velocity_ms"),
            },
            "dha": {
                "voltage_violations": dha_kpis.get("voltage_violations_total", 0),
                "line_violations": dha_kpis.get("line_violations_total", 0),
            },
            "v_share_within_limits": agg.get("v_share_within_limits") or hyd.get("velocity_share_within_limits"),
            "dp_max_bar_per_100m": agg.get("dp_max_bar_per_100m") or hyd.get("dp_per_100m_max"),
            "execution_log": execution_log,
        }

    def _execute_network_design(self, street_id: str, context: Dict) -> Dict:
        """Network design: CHA topology, pipe sizes, interactive maps."""
        execution_log = []

        if not self._ensure_cha_results(street_id):
            execution_log.append("CHA run failed")
            return {"error": "CHA simulation failed", "execution_log": execution_log}

        execution_log.append("CHA results available")

        from branitz_heat_decision.config import resolve_cluster_path

        cha_dir = resolve_cluster_path(street_id, "cha")
        cha_path = cha_dir / "cha_kpis.json"
        cha_kpis = {}
        if cha_path.exists():
            with open(cha_path, "r") as f:
                cha_kpis = json.load(f)

        # Extract detailed pipe/consumer data (lives under "detailed" in cha_kpis)
        detailed = cha_kpis.get("detailed", {})
        topology = cha_kpis.get("topology", {})
        pipes = detailed.get("pipes", cha_kpis.get("pipes", []))
        heat_consumers = detailed.get("heat_consumers", cha_kpis.get("heat_consumers", []))

        # Collect available interactive map HTML paths
        map_paths = {}
        for map_type, filename in [
            ("velocity", "interactive_map.html"),
            ("temperature", "interactive_map_temperature.html"),
            ("pressure", "interactive_map_pressure.html"),
        ]:
            p = cha_dir / filename
            if p.exists():
                map_paths[map_type] = str(p)
                execution_log.append(f"Map available: {map_type}")

        return {
            "topology": topology,
            "pipes": pipes,
            "heat_consumers": heat_consumers,
            "map_paths": map_paths,
            "execution_log": execution_log,
        }

    def _execute_what_if(self, street_id: str, context: Dict) -> Dict:
        """
        Speaker B's example: "What if we leave out 2 houses?"

        Execution Plan:
        1. Load baseline network from cache or disk
        2. Clone and modify network (remove houses)
        3. Re-run pipeflow for scenario
        4. Compare with baseline
        """
        pp = _get_pp()
        if pp is None:
            return {"error": "pandapipes not installed", "execution_log": []}

        modification = context.get("modification", "")
        execution_log = []

        # 1. Load baseline network (run CHA if needed)
        if not self._ensure_cha_results(street_id):
            return {"error": "CHA baseline failed", "execution_log": execution_log}

        from branitz_heat_decision.config import resolve_cluster_path

        network_path = resolve_cluster_path(street_id, "cha") / "network.pickle"
        if not network_path.exists():
            return {"error": "network.pickle not found", "execution_log": execution_log}

        with open(network_path, "rb") as f:
            baseline_net = pickle.load(f)

        execution_log.append("Using baseline CHA network")

        # 2. Create scenario network (clone + modify)
        scenario_id = f"scenario_{self.scenario_counter}"
        self.scenario_counter += 1

        scenario_net = pickle.loads(pickle.dumps(baseline_net))

        # Parse modification (e.g. "remove 2 houses", "remove_2_houses")
        n_houses = 0
        mod_lower = modification.lower().replace(" ", "_")
        if "remove" in mod_lower and ("house" in mod_lower or "building" in mod_lower):
            parts = modification.replace(" ", "_").split("_")
            for p in parts:
                if p.isdigit():
                    n_houses = int(p)
                    break

        if n_houses > 0:
            try:
                scenario_net = self._exclude_houses(scenario_net, n_houses)
                execution_log.append(f"Modified network: excluded {n_houses} houses")
            except ValueError as e:
                return {"error": str(e), "execution_log": execution_log}

        # 3. Re-run pipeflow for scenario
        try:
            pp.pipeflow(
                scenario_net,
                mode="all",
                iter=100,
                tol_p=1e-4,
                tol_v=1e-4,
            )
        except Exception as e:
            return {"error": f"Scenario pipeflow failed: {e}", "execution_log": execution_log}

        execution_log.append(f"Ran scenario pipeflow: {scenario_id}")

        # 4. Compare baseline vs scenario
        comparison = self._compare_scenarios(baseline_net, scenario_net)

        return {
            "baseline": {
                "co2_tons": self._calculate_dh_co2(baseline_net),
                "lcoh_eur_mwh": self._calculate_dh_lcoh(baseline_net),
                "max_pressure_bar": self._get_max_pressure(baseline_net),
            },
            "scenario": {
                "co2_tons": self._calculate_dh_co2(scenario_net),
                "lcoh_eur_mwh": self._calculate_dh_lcoh(scenario_net),
                "max_pressure_bar": self._get_max_pressure(scenario_net),
            },
            "comparison": comparison,
            "execution_log": execution_log,
            "modification_applied": modification,
        }

    def _run_dh_simulation(self, street_id: str) -> Any:
        """
        Load CHA network from results (CHA already run by _ensure_cha_results).
        Returns pandapipes net.
        """
        from branitz_heat_decision.config import resolve_cluster_path

        network_path = resolve_cluster_path(street_id, "cha") / "network.pickle"
        if not network_path.exists():
            from branitz_heat_decision.adk.tools import run_cha_tool

            result = run_cha_tool(street_id)
            if result.get("status") != "success":
                raise RuntimeError(f"CHA run failed: {result.get('error', 'unknown')}")

        with open(network_path, "rb") as f:
            return pickle.load(f)

    def _run_cha_simulation(self, street_id: str) -> Dict[str, Any]:
        """
        Run DHA (Heat Pump grid analysis); returns DHA result dict.
        CO2/LCOH for HP come from economics, not from this directly.
        """
        from branitz_heat_decision.adk.tools import run_dha_tool

        result = run_dha_tool(street_id)
        if result.get("status") != "success":
            raise RuntimeError(f"DHA run failed: {result.get('error', 'unknown')}")
        return result

    def _exclude_houses(self, net: Any, n_houses: int) -> Any:
        """
        Modify network for "what-if" scenarios.
        Disables heat consumers by setting in_service=False or qext_w=0.
        """
        if not hasattr(net, "heat_consumer") or net.heat_consumer is None or net.heat_consumer.empty:
            raise ValueError("Network has no heat_consumer table")

        if "in_service" in net.heat_consumer.columns:
            consumers = net.heat_consumer[net.heat_consumer["in_service"] == True]
        else:
            consumers = net.heat_consumer

        if len(consumers) <= n_houses:
            raise ValueError(
                f"Cannot remove {n_houses} houses, only {len(consumers)} available"
            )

        # Disable last N consumers
        indices_to_remove = consumers.index[-n_houses:].tolist()

        for idx in indices_to_remove:
            if "in_service" in net.heat_consumer.columns:
                net.heat_consumer.loc[idx, "in_service"] = False
            if "qext_w" in net.heat_consumer.columns:
                net.heat_consumer.loc[idx, "qext_w"] = 0.0

        return net

    def _calculate_dh_co2(self, net: Any) -> float:
        """Approximate CO2 from DH simulation results (annual heat * emission factor)."""
        try:
            if hasattr(net, "res_heat_consumer") and net.res_heat_consumer is not None and not net.res_heat_consumer.empty:
                col = "qext_w" if "qext_w" in net.res_heat_consumer.columns else None
                if col:
                    total_w = net.res_heat_consumer[col].sum()
                else:
                    total_w = 0.0
            elif hasattr(net, "heat_consumer") and net.heat_consumer is not None and not net.heat_consumer.empty:
                total_w = net.heat_consumer["qext_w"].sum() if "qext_w" in net.heat_consumer.columns else 0.0
            else:
                return 0.0

            # Design hour power -> annual MWh (simplified: * 8760 * load factor)
            load_factor = 0.15
            annual_mwh = total_w * 1e-6 * 8760 * load_factor
            emission_factor = 0.2
            return float(annual_mwh * emission_factor)
        except Exception:
            return 0.0

    def _calculate_dh_lcoh(self, net: Any) -> float:
        """LCOH from network is complex; return 0 for what-if (use economics for baseline)."""
        # Full LCOH requires economics; for what-if we approximate or return N/A
        return 0.0

    def _get_max_pressure(self, net: Any) -> float:
        """Max pressure from res_junction."""
        try:
            if hasattr(net, "res_junction") and net.res_junction is not None and not net.res_junction.empty:
                if "p_bar" in net.res_junction.columns:
                    return float(net.res_junction["p_bar"].max())
        except Exception:
            pass
        return 0.0

    def _compare_scenarios(
        self, baseline: Any, scenario: Any
    ) -> Dict[str, Any]:
        """Compare two network states for what-if analysis."""
        base_p = self._get_max_pressure(baseline)
        scen_p = self._get_max_pressure(scenario)

        base_heat = 0.0
        scen_heat = 0.0
        if hasattr(baseline, "res_heat_consumer") and baseline.res_heat_consumer is not None:
            col = "qext_w" if "qext_w" in baseline.res_heat_consumer.columns else None
            if col:
                base_heat = baseline.res_heat_consumer[col].sum() * 1e-6
        if hasattr(scenario, "res_heat_consumer") and scenario.res_heat_consumer is not None:
            col = "qext_w" if "qext_w" in scenario.res_heat_consumer.columns else None
            if col:
                scen_heat = scenario.res_heat_consumer[col].sum() * 1e-6

        return {
            "pressure_change_bar": scen_p - base_p,
            "heat_delivered_change_mw": scen_heat - base_heat,
            "violation_reduction": self._count_violations(baseline) - self._count_violations(scenario),
        }

    def _count_violations(self, net: Any) -> int:
        """Count pressure/temperature violations."""
        violations = 0
        try:
            if hasattr(net, "res_junction") and net.res_junction is not None:
                if "p_bar" in net.res_junction.columns:
                    violations += int((net.res_junction["p_bar"] > 6).sum())
        except Exception:
            pass
        return violations

    def _hash_network_state(self, net: Any) -> str:
        """Create hash of network state for cache validation."""
        try:
            n_j = len(net.junction) if hasattr(net, "junction") else 0
            n_p = len(net.pipe) if hasattr(net, "pipe") else 0
            hc_sum = 0.0
            if hasattr(net, "heat_consumer") and net.heat_consumer is not None and not net.heat_consumer.empty:
                if "qext_w" in net.heat_consumer.columns:
                    hc_sum = net.heat_consumer["qext_w"].sum()
            state_str = f"{n_j}_{n_p}_{hc_sum}"
            return hashlib.md5(state_str.encode()).hexdigest()
        except Exception:
            return ""

    def _load_cache(self) -> None:
        """Load persistent cache from disk."""
        cache_file = self.cache_dir / "simulation_cache.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    self.active_cache = pickle.load(f)
                logger.info("Loaded simulation cache from %s", cache_file)
            except Exception as e:
                logger.warning("Could not load cache: %s", e)

    def save_cache(self) -> None:
        """Save cache to disk for persistence."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / "simulation_cache.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(self.active_cache, f)
            logger.info("Saved simulation cache to %s", cache_file)
        except Exception as e:
            logger.warning("Could not save cache: %s", e)
