"""
Dynamic Execution Engine — Head Chef that delegates to Station Agents.

Refactored to use domain agents (domain_agents.py) instead of calling
ADK tools directly.  Backward-compatible: the orchestrator and UI still
receive the same response dictionaries they always did.

ALL intents — including WHAT_IF_SCENARIO — are now delegated to domain
agents.  No inline tool calls or pandapipes manipulation remain here.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


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
        WhatIfAgent,
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
        "WhatIfAgent": WhatIfAgent,
    }


class DynamicExecutor:
    """
    Head Chef: Coordinates domain agents to fulfill user requests.

    Instead of directly calling ADK tools, the executor:
    1. Determines which agents are needed  (_create_agent_plan)
    2. Delegates to appropriate agents      (execute → _run_agent_plan)
    3. Integrates their results             (_integrate_results)
    4. Returns the **same dict format** the orchestrator / UI expects

    Speaker B's requirements are preserved:
    • Lazy execution — only runs what's needed
    • Cache-first   — agents check result files before running tools
    • Timed logs    — every step shows "✓ Used cached CHA (0.002s)"
    • What-if       — delegated to WhatIfAgent (pandapipes manipulation)
    """

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)

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
            "what_if":    cls["WhatIfAgent"](cache),
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

        # Build and run an agent plan (what-if is now an agent too)
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
            "CO2_COMPARISON":     ["cha", "dha", "economics"],
            "LCOH_COMPARISON":    ["cha", "dha", "economics"],
            "VIOLATION_ANALYSIS": ["cha", "dha"],
            "NETWORK_DESIGN":     ["cha"],
            "WHAT_IF_SCENARIO":   ["what_if"],
            "DECISION":           ["cha", "dha", "economics", "decision"],
            "EXPLAIN_DECISION":   ["cha", "dha", "economics", "decision"],
            "FULL_REPORT":        ["cha", "dha", "economics", "decision", "uhdc"],
            "DATA_PREPARATION":   ["data_prep"],
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

            # Append agent-specific sub-log entries (e.g. WhatIfAgent modification log)
            for entry in result.metadata.get("modification_log", []):
                execution_log.append(f"  → {entry}")

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

        # WhatIfAgent failure
        if "what_if" in results and not results["what_if"].success:
            errors = results["what_if"].errors or ["Unknown error"]
            return {"error": f"What-if failed: {'; '.join(errors)}"}
        
        # Decision is mandatory for decision-oriented intents
        if intent in ("DECISION", "EXPLAIN_DECISION", "FULL_REPORT"):
            decision_result = results.get("decision")
            if decision_result is None:
                return {"error": "DECISION failed: decision agent did not run"}
            if not decision_result.success:
                errors = decision_result.errors or ["Unknown error"]
                return {"error": f"DECISION failed: {'; '.join(errors)}"}

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
        if intent == "WHAT_IF_SCENARIO":
            return self._format_what_if(results, street_id)

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
        dha_dir = resolve_cluster_path(street_id, "dha")
        map_paths: Dict[str, str] = {}
        for map_type, filename in [
            ("velocity", "interactive_map.html"),
            ("temperature", "interactive_map_temperature.html"),
            ("pressure", "interactive_map_pressure.html"),
        ]:
            p = cha_dir / filename
            if p.exists():
                map_paths[map_type] = str(p)

        # Add LV Grid map if it exists
        p_dha = dha_dir / "hp_lv_map.html"
        if p_dha.exists():
            map_paths["lv grid"] = str(p_dha)

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

    # -- What-if ------------------------------------------------------------
    @staticmethod
    def _format_what_if(results: Dict, street_id: str) -> Dict[str, Any]:
        """Flatten WhatIfAgent result into the dict the orchestrator expects."""
        if "what_if" in results and results["what_if"].success:
            data = results["what_if"].data
            return {
                "baseline": data.get("baseline", {}),
                "scenario": data.get("scenario", {}),
                "comparison": data.get("comparison", {}),
                "modification_applied": data.get("modification_applied", ""),
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
