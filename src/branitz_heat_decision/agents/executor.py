"""
Dynamic Execution Engine — Head Chef that delegates to Station Agents.

Refactored to use domain agents (domain_agents.py) instead of calling
ADK tools directly.  Backward-compatible: the orchestrator and UI still
receive the same response dictionaries they always did.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy imports for heavy optional deps (needed only for what-if)
def _get_pp():
    try:
        import pandapipes as pp
        return pp
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Domain-agent imports (deferred so module loads even if agents aren't used)
# ---------------------------------------------------------------------------
def _import_agents():
    from branitz_heat_decision.agents.domain_agents import (
        AgentResult,
        DataPrepAgent,
        CHAAgent,
        DHAAgent,
        EconomicsAgent,
        DecisionAgent,
        ValidationAgent,
        UHDCAgent,
    )
    return {
        "AgentResult": AgentResult,
        "DataPrepAgent": DataPrepAgent,
        "CHAAgent": CHAAgent,
        "DHAAgent": DHAAgent,
        "EconomicsAgent": EconomicsAgent,
        "DecisionAgent": DecisionAgent,
        "ValidationAgent": ValidationAgent,
        "UHDCAgent": UHDCAgent,
    }


class DynamicExecutor:
    """
    Head Chef: Coordinates domain agents to fulfill user requests.

    Instead of directly calling ADK tools, the executor now:
    1. Determines which agents are needed  (_create_agent_plan)
    2. Delegates to appropriate agents      (execute → _run_agent_plan)
    3. Integrates their results             (_integrate_results)
    4. Returns the **same dict format** the orchestrator / UI expects

    Speaker B's requirements are preserved:
    • Lazy execution — only runs what's needed
    • Cache-first   — agents check result files before running tools
    • Timed logs    — every step shows "✓ Used cached CHA (0.002s)"
    • What-if       — still handled inline (pandapipes network manipulation)
    """

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.scenario_counter = 0

        # Initialise domain agents lazily on first use
        self._agents: Optional[Dict[str, Any]] = None
        self._agent_classes: Optional[Dict[str, Any]] = None

    # -- lazy init so import cost is zero until first execute() call ---------
    def _ensure_agents(self):
        if self._agents is not None:
            return
        cls = _import_agents()
        self._agent_classes = cls
        cache = str(self.cache_dir)
        self._agents = {
            "data_prep":  cls["DataPrepAgent"](cache),
            "cha":        cls["CHAAgent"](cache),
            "dha":        cls["DHAAgent"](cache),
            "economics":  cls["EconomicsAgent"](cache),
            "decision":   cls["DecisionAgent"](cache),
            "validation": cls["ValidationAgent"](cache),
            "uhdc":       cls["UHDCAgent"](cache),
        }

    # -----------------------------------------------------------------------
    # Public API — same signature as before
    # -----------------------------------------------------------------------
    def execute(
        self,
        intent: str,
        street_id: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point — like a head chef receiving an order ticket.

        Returns a dict with at least:
            execution_log:  List[str]   — timed log of what ran
            error:          str | None  — set only on failure
            ...plus intent-specific data keys the UI expects
        """
        context = context or {}
        self._ensure_agents()

        start = time.perf_counter()
        logger.info("[DynamicExecutor] Received order: %s for %s", intent, street_id)

        # What-if is special: it manipulates pandapipes networks directly,
        # so we keep it as an inline method rather than an agent.
        if intent == "WHAT_IF_SCENARIO":
            return self._execute_what_if(street_id, context)

        # For everything else, build and run an agent plan
        plan = self._create_agent_plan(intent, context)
        logger.info("[DynamicExecutor] Agent plan: %s", plan)

        agent_results, execution_log = self._run_agent_plan(
            plan, intent, street_id, context,
        )

        # Integrate agent outputs into the flat dict the UI needs
        integrated = self._integrate_results(agent_results, intent, street_id)
        integrated["execution_log"] = execution_log

        total = time.perf_counter() - start
        integrated.setdefault("agent_results", {
            name: {
                "success": r.success,
                "execution_time": r.execution_time,
                "cache_hit": r.cache_hit,
                "metadata": r.metadata,
            }
            for name, r in agent_results.items()
        })
        integrated["total_execution_time"] = total

        logger.info("[DynamicExecutor] Order completed in %.2fs", total)
        return integrated

    # -----------------------------------------------------------------------
    # Agent plan
    # -----------------------------------------------------------------------
    def _create_agent_plan(self, intent: str, context: Dict) -> List[str]:
        """Dependency-ordered list of agents required for *intent*."""
        plans = {
            "CO2_COMPARISON":    ["cha", "dha", "economics"],
            "LCOH_COMPARISON":   ["cha", "dha", "economics"],
            "VIOLATION_ANALYSIS": ["cha", "dha"],
            "NETWORK_DESIGN":    ["cha"],
            "DECISION":          ["cha", "dha", "economics", "decision"],
            "EXPLAIN_DECISION":  ["cha", "dha", "economics", "decision"],
            "FULL_REPORT":       ["cha", "dha", "economics", "decision", "uhdc"],
            "DATA_PREPARATION":  ["data_prep"],
        }
        base = plans.get(intent, ["cha", "dha", "economics"])

        if context.get("needs_data_prep"):
            base = ["data_prep"] + base

        return base

    # -----------------------------------------------------------------------
    # Run agents
    # -----------------------------------------------------------------------
    def _run_agent_plan(
        self,
        plan: List[str],
        intent: str,
        street_id: str,
        context: Dict,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Execute every agent in *plan* in order, collecting results + log."""
        AgentResult = self._agent_classes["AgentResult"]
        results: Dict[str, Any] = {}
        execution_log: List[str] = []

        for agent_name in plan:
            agent = self._agents.get(agent_name)
            if agent is None:
                continue

            agent_start = time.perf_counter()
            try:
                result = agent.execute(street_id, context)
            except Exception as exc:
                logger.exception("[%s] Exception: %s", agent_name, exc)
                result = AgentResult(
                    success=False,
                    data={},
                    execution_time=time.perf_counter() - agent_start,
                    cache_hit=False,
                    agent_name=agent_name,
                    metadata={},
                    errors=[str(exc)],
                )

            results[agent_name] = result
            duration = result.execution_time

            # Build a timed log line consistent with the UI's "What was calculated" panel
            status = "✓" if result.success else "✗"
            cache_tag = "Used cached" if result.cache_hit else "Calculated"
            label = agent_name.upper().replace("_", " ")
            execution_log.append(
                f"{status} {cache_tag} {label} ({duration:.3f}s)"
                if result.cache_hit
                else f"{status} {cache_tag} {label} ({duration:.1f}s)"
            )

            if not result.success:
                logger.error("[%s] Failed: %s", agent_name, result.errors)
                # If a critical agent fails, stop early for this plan
                if agent_name in ("cha", "dha", "economics"):
                    execution_log.append(
                        f"Pipeline stopped: {agent_name} is a prerequisite"
                    )
                    break

        return results, execution_log

    # -----------------------------------------------------------------------
    # Integrate agent results → flat dict the orchestrator / UI expect
    # -----------------------------------------------------------------------
    def _integrate_results(
        self,
        results: Dict[str, Any],
        intent: str,
        street_id: str,
    ) -> Dict[str, Any]:
        """Merge agent outputs into the response shape the UI renderers need."""

        # Check for critical failures first
        for critical in ("cha", "dha", "economics"):
            if critical in results and not results[critical].success:
                errors = results[critical].errors or ["Unknown error"]
                return {"error": f"{critical.upper()} failed: {'; '.join(errors)}"}

        # Dispatch to intent-specific formatter
        if intent == "CO2_COMPARISON":
            return self._format_co2(results, street_id)
        if intent == "LCOH_COMPARISON":
            return self._format_lcoh(results, street_id)
        if intent == "VIOLATION_ANALYSIS":
            return self._format_violations(results, street_id)
        if intent == "NETWORK_DESIGN":
            return self._format_network_design(results, street_id)
        if intent in ("DECISION", "EXPLAIN_DECISION"):
            return self._format_decision(results, street_id)

        # Generic fallback — return raw agent data
        return {
            name: r.data for name, r in results.items() if r.success
        }

    # -- CO2 ----------------------------------------------------------------
    def _format_co2(self, results: Dict, street_id: str) -> Dict[str, Any]:
        econ = self._extract_economics(results)
        co2_dh = econ.get("co2_dh_t_per_a") or econ.get("co2", {}).get("dh") or 0.0
        co2_hp = econ.get("co2_hp_t_per_a") or econ.get("co2", {}).get("hp") or 0.0
        return {
            "dh_tons_co2": float(co2_dh),
            "hp_tons_co2": float(co2_hp),
            "difference": float(co2_dh - co2_hp),
            "winner": "DH" if co2_dh < co2_hp else "HP",
        }

    # -- LCOH ---------------------------------------------------------------
    def _format_lcoh(self, results: Dict, street_id: str) -> Dict[str, Any]:
        econ = self._extract_economics(results)
        dh = econ.get("lcoh_dh_eur_per_mwh") or econ.get("lcoh", {}).get("dh") or 0.0
        hp = econ.get("lcoh_hp_eur_per_mwh") or econ.get("lcoh", {}).get("hp") or 0.0
        return {
            "lcoh_dh_eur_per_mwh": float(dh),
            "lcoh_hp_eur_per_mwh": float(hp),
            "difference": float(hp - dh),
            "winner": "DH" if dh < hp else "HP",
        }

    # -- Violations ---------------------------------------------------------
    def _format_violations(self, results: Dict, street_id: str) -> Dict[str, Any]:
        cha_kpis = self._extract_cha_kpis(results)
        dha_kpis = self._extract_dha_kpis(results)

        agg = cha_kpis.get("aggregate", {})
        hyd = cha_kpis.get("hydraulics", {})

        return {
            "cha": {
                "converged": cha_kpis.get("convergence", {}).get("converged"),
                "pressure_bar_max": cha_kpis.get("pressure_bar_max"),
                "velocity_ms_max": agg.get("v_max_ms") or hyd.get("max_velocity_ms"),
            },
            "dha": {
                "voltage_violations": dha_kpis.get("voltage_violations_total", 0),
                "line_violations": dha_kpis.get("line_violations_total", 0),
            },
            "v_share_within_limits": (
                agg.get("v_share_within_limits")
                or hyd.get("velocity_share_within_limits")
            ),
            "dp_max_bar_per_100m": (
                agg.get("dp_max_bar_per_100m") or hyd.get("dp_per_100m_max")
            ),
        }

    # -- Network design -----------------------------------------------------
    def _format_network_design(self, results: Dict, street_id: str) -> Dict[str, Any]:
        cha_kpis = self._extract_cha_kpis(results)
        detailed = cha_kpis.get("detailed", {})
        topology = cha_kpis.get("topology", {})
        pipes = detailed.get("pipes", cha_kpis.get("pipes", []))
        heat_consumers = detailed.get("heat_consumers", cha_kpis.get("heat_consumers", []))

        from branitz_heat_decision.config import resolve_cluster_path

        cha_dir = resolve_cluster_path(street_id, "cha")
        map_paths: Dict[str, str] = {}
        for map_type, filename in [
            ("velocity", "interactive_map.html"),
            ("temperature", "interactive_map_temperature.html"),
            ("pressure", "interactive_map_pressure.html"),
        ]:
            p = cha_dir / filename
            if p.exists():
                map_paths[map_type] = str(p)

        return {
            "topology": topology,
            "pipes": pipes,
            "heat_consumers": heat_consumers,
            "map_paths": map_paths,
        }

    # -- Decision -----------------------------------------------------------
    def _format_decision(self, results: Dict, street_id: str) -> Dict[str, Any]:
        if "decision" in results and results["decision"].success:
            dec_data = results["decision"].data.get("decision", {})
            return {
                "choice": dec_data.get("recommendation") or dec_data.get("choice"),
                "recommendation": dec_data.get("recommendation") or dec_data.get("choice"),
                "robust": dec_data.get("robust", False),
                "reason": dec_data.get("reason", ""),
                "reason_codes": dec_data.get("reason_codes", []),
                "metrics_used": dec_data.get("metrics_used", {}),
            }
        return {}

    # -- helpers to pull structured data out of AgentResult -------------------
    @staticmethod
    def _extract_economics(results: Dict) -> Dict[str, Any]:
        if "economics" in results and results["economics"].success:
            data = results["economics"].data
            # Agent stores economics under "economics" key; fall back to raw data
            return data.get("economics", data)
        return {}

    @staticmethod
    def _extract_cha_kpis(results: Dict) -> Dict[str, Any]:
        if "cha" in results and results["cha"].success:
            data = results["cha"].data
            return data.get("kpis", data) if isinstance(data, dict) else {}
        return {}

    @staticmethod
    def _extract_dha_kpis(results: Dict) -> Dict[str, Any]:
        if "dha" in results and results["dha"].success:
            data = results["dha"].data
            kpis = data.get("kpis", data) if isinstance(data, dict) else {}
            return kpis.get("kpis", kpis) if isinstance(kpis, dict) else kpis
        return {}

    # -----------------------------------------------------------------------
    # What-if scenario  (kept inline — needs pandapipes network manipulation)
    # -----------------------------------------------------------------------
    def _execute_what_if(self, street_id: str, context: Dict) -> Dict[str, Any]:
        """
        Speaker B's example: "What if we leave out 2 houses?"

        This is the one intent that cannot be fully delegated to agents
        because it clones + mutates the pandapipes network object.
        """
        pp = _get_pp()
        if pp is None:
            return {"error": "pandapipes not installed", "execution_log": []}

        modification = context.get("modification", "")
        execution_log: List[str] = []

        # 1. Ensure baseline CHA exists (via the CHA agent)
        self._ensure_agents()
        cha_agent = self._agents["cha"]
        cha_start = time.perf_counter()
        cha_result = cha_agent.execute(street_id, context)
        cha_dur = cha_result.execution_time
        cache_tag = "Used cached" if cha_result.cache_hit else "Calculated"
        execution_log.append(
            f"✓ {cache_tag} CHA ({cha_dur:.3f}s)"
            if cha_result.cache_hit
            else f"✓ {cache_tag} CHA ({cha_dur:.1f}s)"
        )

        if not cha_result.success:
            execution_log[-1] = execution_log[-1].replace("✓", "✗")
            return {"error": "CHA baseline failed", "execution_log": execution_log}

        # 2. Load baseline network
        from branitz_heat_decision.config import resolve_cluster_path

        network_path = resolve_cluster_path(street_id, "cha") / "network.pickle"
        if not network_path.exists():
            return {"error": "network.pickle not found", "execution_log": execution_log}

        with open(network_path, "rb") as f:
            baseline_net = pickle.load(f)
        execution_log.append("Using baseline CHA network")

        # 3. Clone + modify
        scenario_id = f"scenario_{self.scenario_counter}"
        self.scenario_counter += 1
        scenario_net = pickle.loads(pickle.dumps(baseline_net))

        n_houses = 0
        mod_lower = modification.lower().replace(" ", "_")
        if "remove" in mod_lower and ("house" in mod_lower or "building" in mod_lower):
            for p in modification.replace(" ", "_").split("_"):
                if p.isdigit():
                    n_houses = int(p)
                    break

        if n_houses > 0:
            try:
                scenario_net = self._exclude_houses(scenario_net, n_houses)
                execution_log.append(f"Modified network: excluded {n_houses} houses")
            except ValueError as e:
                return {"error": str(e), "execution_log": execution_log}

        # 4. Re-run pipeflow
        try:
            pp.pipeflow(scenario_net, mode="all", iter=100, tol_p=1e-4, tol_v=1e-4)
        except Exception as e:
            return {"error": f"Scenario pipeflow failed: {e}", "execution_log": execution_log}

        execution_log.append(f"Ran scenario pipeflow: {scenario_id}")

        # 5. Compare
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

    # -----------------------------------------------------------------------
    # Network helpers (for what-if)
    # -----------------------------------------------------------------------
    @staticmethod
    def _exclude_houses(net: Any, n_houses: int) -> Any:
        """Disable the last *n_houses* heat consumers in the network."""
        if not hasattr(net, "heat_consumer") or net.heat_consumer is None or net.heat_consumer.empty:
            raise ValueError("Network has no heat_consumer table")

        consumers = (
            net.heat_consumer[net.heat_consumer["in_service"] == True]
            if "in_service" in net.heat_consumer.columns
            else net.heat_consumer
        )
        if len(consumers) <= n_houses:
            raise ValueError(f"Cannot remove {n_houses} houses, only {len(consumers)} available")

        for idx in consumers.index[-n_houses:].tolist():
            if "in_service" in net.heat_consumer.columns:
                net.heat_consumer.loc[idx, "in_service"] = False
            if "qext_w" in net.heat_consumer.columns:
                net.heat_consumer.loc[idx, "qext_w"] = 0.0
        return net

    @staticmethod
    def _calculate_dh_co2(net: Any) -> float:
        """Approximate annual CO₂ from DH network (design hour → annual)."""
        try:
            if hasattr(net, "res_heat_consumer") and net.res_heat_consumer is not None and not net.res_heat_consumer.empty:
                col = "qext_w" if "qext_w" in net.res_heat_consumer.columns else None
                total_w = net.res_heat_consumer[col].sum() if col else 0.0
            elif hasattr(net, "heat_consumer") and net.heat_consumer is not None and not net.heat_consumer.empty:
                total_w = net.heat_consumer["qext_w"].sum() if "qext_w" in net.heat_consumer.columns else 0.0
            else:
                return 0.0
            load_factor = 0.15
            annual_mwh = total_w * 1e-6 * 8760 * load_factor
            return float(annual_mwh * 0.2)
        except Exception:
            return 0.0

    @staticmethod
    def _calculate_dh_lcoh(net: Any) -> float:  # noqa: ARG004
        """LCOH from network alone is complex; return 0 (use economics for baseline)."""
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

    def _compare_scenarios(self, baseline: Any, scenario: Any) -> Dict[str, Any]:
        base_p = self._get_max_pressure(baseline)
        scen_p = self._get_max_pressure(scenario)

        def _heat_mw(net: Any) -> float:
            if hasattr(net, "res_heat_consumer") and net.res_heat_consumer is not None:
                col = "qext_w" if "qext_w" in net.res_heat_consumer.columns else None
                return net.res_heat_consumer[col].sum() * 1e-6 if col else 0.0
            return 0.0

        return {
            "pressure_change_bar": scen_p - base_p,
            "heat_delivered_change_mw": _heat_mw(scenario) - _heat_mw(baseline),
            "violation_reduction": self._count_violations(baseline) - self._count_violations(scenario),
        }

    @staticmethod
    def _count_violations(net: Any) -> int:
        try:
            if hasattr(net, "res_junction") and net.res_junction is not None:
                if "p_bar" in net.res_junction.columns:
                    return int((net.res_junction["p_bar"] > 6).sum())
        except Exception:
            pass
        return 0
