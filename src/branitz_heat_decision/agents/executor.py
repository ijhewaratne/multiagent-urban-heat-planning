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
        incoming_context = context or {}
        is_explanation_request = intent == "EXPLAIN_DECISION"
        context = {
            **incoming_context,
            "requested_intent": intent,
            "require_validated_explanation": incoming_context.get(
                "require_validated_explanation", is_explanation_request
            ),
            # Cache-first by default. A live Gemini call is made only when the
            # validated explanation sidecars are missing/stale, or when a caller
            # explicitly requests a refresh with this flag.
            "require_live_llm_explanation": bool(
                incoming_context.get("require_live_llm_explanation", False)
            ),
            "llm_explanation": incoming_context.get(
                "llm_explanation", is_explanation_request
            ),
            "no_fallback": incoming_context.get(
                "no_fallback", is_explanation_request
            ),
        }
        start = time.perf_counter()
        logger.info("[DynamicExecutor] Received order: %s for %s", intent, street_id)

        # Network maps are already generated CHA/DHA artifacts. Displaying them
        # must not trigger a simulation merely because chat-history fields make
        # the simulation cache hash differ from the original run. If maps exist,
        # load them directly; fall through to CHA only when they are missing.
        if intent == "NETWORK_DESIGN" and not context.get("force_recalc"):
            cached_network = self._format_network_design({}, street_id)
            if cached_network.get("map_paths"):
                duration = time.perf_counter() - start
                original = self._load_original_timing(street_id, ["cha", "dha"])
                timing_text = self._format_cache_timing(duration, original)
                cached_network.update({
                    "execution_log": [f"✓ Loaded cached network maps ({timing_text})"],
                    "agent_results": {
                        "network_artifacts": {
                            "success": True,
                            "execution_time": duration,
                            "cache_hit": True,
                            "metadata": {"street_id": street_id, **original},
                        }
                    },
                    "total_execution_time": duration,
                })
                return cached_network

        # Reinforcement questions are evidence/reporting requests.  When the
        # persisted DHA, economics, and decision artifacts exist, load them
        # directly so a chat question cannot accidentally rerun or overwrite a
        # street simulation.  Missing inputs fall through to the normal agent
        # plan below.
        if intent == "GRID_REINFORCEMENT" and not context.get("force_recalc"):
            cached_reinforcement = self._format_grid_reinforcement({}, street_id)
            reinforcement = cached_reinforcement.get("reinforcement", {})
            complete_cached_analysis = bool(
                cached_reinforcement.get("data_available")
                and (
                    not reinforcement.get("needed")
                    or (
                        reinforcement.get("optimized_plan_available")
                        and cached_reinforcement.get("scenario_artifacts_complete")
                    )
                )
            )
            if complete_cached_analysis:
                duration = time.perf_counter() - start
                original = self._load_original_timing(
                    street_id,
                    ["dha", "economics", "decision"],
                )
                timing_text = self._format_cache_timing(duration, original)
                cached_reinforcement.update({
                    "execution_log": [
                        "✓ Loaded cached LV-grid, economics, and decision evidence "
                        f"({timing_text})"
                    ],
                    "agent_results": {
                        "reinforcement_evidence": {
                            "success": True,
                            "execution_time": duration,
                            "cache_hit": True,
                            "metadata": {"street_id": street_id, **original},
                        }
                    },
                    "total_execution_time": duration,
                })
                return cached_reinforcement

        self._ensure_agents()

        if intent == "GRID_REINFORCEMENT":
            context["plan_reinforcement"] = True

        # Build and run an agent plan (what-if is now an agent too)
        plan = self._create_agent_plan(intent, context)
        if intent == "EXPLAIN_DECISION":
            # Decision explanations consume persisted CHA/DHA/Economics inputs.
            # Do not rerun the physics merely to request a fresh Gemini narrative.
            from branitz_heat_decision.config import resolve_cluster_path

            decision_inputs = [
                resolve_cluster_path(street_id, "cha") / "cha_kpis.json",
                resolve_cluster_path(street_id, "dha") / "dha_kpis.json",
                resolve_cluster_path(street_id, "economics") / "economics_monte_carlo.json",
            ]
            if all(path.exists() for path in decision_inputs):
                plan = ["decision"]
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
            "GRID_REINFORCEMENT": ["dha", "economics", "decision"],
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
            if result.cache_hit:
                original_duration = result.metadata.get(
                    "original_calculation_duration_seconds"
                )
                original_at = result.metadata.get("original_calculated_at_utc")
                if isinstance(original_duration, (int, float)):
                    original_text = f"original calculation {original_duration:.1f}s"
                    if original_at:
                        original_text += f" at {original_at}"
                else:
                    original_text = "original duration unavailable for adopted legacy cache"
                    if original_at:
                        original_text += f"; result artifacts dated {original_at}"
                execution_log.append(
                    f"{status} {cache_tag} {label} "
                    f"(loaded {duration:.3f}s; {original_text})"
                )
            else:
                execution_log.append(
                    f"{status} {cache_tag} {label} ({duration:.1f}s)"
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

    @staticmethod
    def _load_original_timing(
        street_id: str,
        phases: List[str],
    ) -> Dict[str, Any]:
        import json

        from branitz_heat_decision.config import resolve_cluster_path

        durations: List[float] = []
        calculated_at: List[str] = []
        for phase in phases:
            manifest_path = resolve_cluster_path(street_id, phase) / "_cache_manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            value = manifest.get("calculation_duration_seconds")
            if isinstance(value, (int, float)):
                durations.append(float(value))
            timestamp = manifest.get("calculated_at_utc")
            if timestamp:
                calculated_at.append(str(timestamp))
        return {
            "original_calculation_duration_seconds": (
                sum(durations) if durations else None
            ),
            "original_calculated_at_utc": (
                max(calculated_at) if calculated_at else None
            ),
        }

    @staticmethod
    def _format_cache_timing(load_duration: float, timing: Dict[str, Any]) -> str:
        original_duration = timing.get("original_calculation_duration_seconds")
        original_at = timing.get("original_calculated_at_utc")
        if isinstance(original_duration, (int, float)):
            text = f"loaded {load_duration:.3f}s; original calculation {original_duration:.1f}s"
            if original_at:
                text += f" at {original_at}"
            return text
        return (
            f"loaded {load_duration:.3f}s; "
            "original duration unavailable for adopted legacy cache"
            + (f"; result artifacts dated {original_at}" if original_at else "")
        )

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
        if intent == "GRID_REINFORCEMENT":
            return self._format_grid_reinforcement(results, street_id)
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

    # -- LV-grid reinforcement ---------------------------------------------
    def _format_grid_reinforcement(
        self,
        results: Dict,
        street_id: str,
    ) -> Dict[str, Any]:
        """Build an auditable reinforcement and decision-impact report.

        The current-grid DHA result remains the technical baseline.  If an
        optimized ``dha_reinforcement.json`` exists, its measures and cost are
        preferred.  Otherwise the response clearly labels the existing HP
        economics LV-upgrade allowance as an estimate and treats
        ``feasible_with_mitigation`` as a counterfactual assumption.
        """
        import json

        from branitz_heat_decision.config import resolve_cluster_path

        def load_json(path: Path) -> Dict[str, Any]:
            if not path.exists():
                return {}
            try:
                with open(path, encoding="utf-8") as handle:
                    value = json.load(handle)
                return value if isinstance(value, dict) else {}
            except (OSError, ValueError) as exc:
                logger.warning("Could not load reinforcement evidence %s: %s", path, exc)
                return {}

        dha_dir = resolve_cluster_path(street_id, "dha")
        econ_dir = resolve_cluster_path(street_id, "economics")
        decision_dir = resolve_cluster_path(street_id, "decision")

        dha_kpis = self._extract_dha_kpis(results)
        if not dha_kpis:
            dha_kpis = load_json(dha_dir / "dha_kpis.json")
            dha_kpis = dha_kpis.get("kpis", dha_kpis)

        reinforcement_plan = load_json(dha_dir / "dha_reinforcement.json")
        economics = load_json(econ_dir / "economics_deterministic.json")
        monte_carlo = load_json(econ_dir / "economics_monte_carlo.json")
        reinforced_econ_dir = econ_dir / "reinforcement"
        reinforced_economics = load_json(
            reinforced_econ_dir / "economics_deterministic.json"
        )
        reinforced_monte_carlo = load_json(
            reinforced_econ_dir / "economics_monte_carlo.json"
        )
        decision = load_json(decision_dir / f"decision_{street_id}.json")
        reinforced_decision = load_json(
            decision_dir / f"decision_reinforced_{street_id}.json"
        )
        comparison = load_json(decision_dir / "reinforcement_before_after.json")

        mitigations = dha_kpis.get("mitigations", {}) if dha_kpis else {}
        recommendations = mitigations.get("recommendations", []) or []
        current_feasible = bool(dha_kpis.get("feasible", False)) if dha_kpis else None
        mitigation_class = mitigations.get("mitigation_class", "unknown")
        reinforcement_needed = bool(
            current_feasible is False
            or mitigation_class in ("reinforcement", "expansion")
        )

        measures = reinforcement_plan.get("measures", []) or []
        plan_cost = reinforcement_plan.get("total_cost_eur")
        hp_breakdown = economics.get("lcoh_hp_breakdown", {})
        estimated_cost = hp_breakdown.get("capex_lv_upgrade")
        reinforced_hp_breakdown = reinforced_economics.get("lcoh_hp_breakdown", {})

        if plan_cost is not None:
            reinforcement_cost = float(plan_cost)
            cost_source = "verified heuristic DHA reinforcement plan"
            cost_is_estimate = False
        elif estimated_cost is not None:
            reinforcement_cost = float(estimated_cost)
            cost_source = "HP economics LV-upgrade allowance"
            cost_is_estimate = True
        elif not reinforcement_needed:
            reinforcement_cost = 0.0
            cost_source = "no reinforcement required"
            cost_is_estimate = False
        else:
            reinforcement_cost = None
            cost_source = "not calculated"
            cost_is_estimate = True

        if reinforcement_plan:
            post_feasible = bool(reinforcement_plan.get("is_sufficient", False))
            feasibility_basis = "verified reinforcement load-flow plan"
            post_feasible_is_assumption = False
        elif not reinforcement_needed:
            post_feasible = current_feasible
            feasibility_basis = "current grid already feasible"
            post_feasible_is_assumption = False
        else:
            post_feasible = bool(mitigations.get("feasible_with_mitigation", False))
            feasibility_basis = "DHA mitigation assessment; optimized plan not yet run"
            post_feasible_is_assumption = True

        baseline_decision = (
            comparison.get("before_reinforcement", {}).get("decision") or decision
        )
        counterfactual = (
            comparison.get("after_reinforcement", {}).get("decision")
            or reinforced_decision
        )
        current_choice = baseline_decision.get("choice") or baseline_decision.get(
            "recommendation"
        )

        after_choice = counterfactual.get("choice") or counterfactual.get("recommendation")
        if not reinforcement_needed:
            after_choice = current_choice

        metrics = counterfactual.get("metrics_used", {})
        map_path = dha_dir / "hp_lv_map.html"
        limitations: List[str] = []
        if reinforcement_needed and not reinforcement_plan:
            limitations.append(
                "No optimized dha_reinforcement.json is available; measures come from the "
                "DHA mitigation assessment and cost is the economics model's LV-upgrade estimate."
            )
        if post_feasible_is_assumption:
            limitations.append(
                "Post-reinforcement feasibility is a counterfactual assumption, not a rerun "
                "of the reinforced network load flow."
            )

        return {
            "street_id": street_id,
            "data_available": bool(dha_kpis),
            "scenario_artifacts_complete": bool(
                reinforced_economics
                and reinforced_monte_carlo
                and reinforced_decision
                and comparison
            ),
            "current_grid": {
                "feasible": current_feasible,
                "max_feeder_loading_pct": dha_kpis.get("max_feeder_loading_pct"),
                "loading_limit_pct": 100.0,
                "voltage_violations_total": dha_kpis.get("voltage_violations_total", 0),
                "line_violations_total": dha_kpis.get("line_violations_total", 0),
                "trafo_violations_total": dha_kpis.get("trafo_violations_total", 0),
                "line_overload_hours": dha_kpis.get("line_overload_hours", 0),
                "hours_total": dha_kpis.get("hours_total", 0),
                "worst_line_id": dha_kpis.get("max_loading_line"),
            },
            "post_reinforcement_grid": reinforcement_plan.get("after_kpis", {}),
            "reinforcement": {
                "needed": reinforcement_needed,
                "mitigation_class": mitigation_class,
                "summary": mitigations.get("summary", ""),
                "recommendations": recommendations,
                "optimized_measures": measures,
                "cost_eur": reinforcement_cost,
                "cost_source": cost_source,
                "cost_is_estimate": cost_is_estimate,
                "cost_assumptions": reinforcement_plan.get("cost_assumptions", {}),
                "optimized_plan_available": bool(reinforcement_plan),
                "plan_is_sufficient": reinforcement_plan.get("is_sufficient"),
            },
            "economics": {
                "lcoh_dh_eur_per_mwh": (
                    metrics.get("lcoh_dh_median")
                    or reinforced_economics.get("lcoh_dh_eur_per_mwh")
                    or economics.get("lcoh_dh_eur_per_mwh")
                ),
                "lcoh_hp_eur_per_mwh": (
                    metrics.get("lcoh_hp_median")
                    or reinforced_economics.get("lcoh_hp_eur_per_mwh")
                    or economics.get("lcoh_hp_eur_per_mwh")
                ),
                "hp_lv_upgrade_capex_eur": (
                    reinforced_hp_breakdown.get("capex_lv_upgrade")
                    or plan_cost
                    or estimated_cost
                ),
                "dh_wins_fraction": metrics.get("dh_wins_fraction"),
                "hp_wins_fraction": metrics.get("hp_wins_fraction"),
                "monte_carlo_available": bool(reinforced_monte_carlo or monte_carlo),
            },
            "decision_impact": {
                "current_choice": current_choice,
                "post_reinforcement_hp_feasible": post_feasible,
                "post_reinforcement_feasibility_basis": feasibility_basis,
                "post_reinforcement_feasibility_is_assumption": post_feasible_is_assumption,
                "counterfactual_choice": after_choice,
                "current_reason_codes": baseline_decision.get("reason_codes", []),
                "counterfactual_reason_codes": counterfactual.get("reason_codes", []),
                "decision_changes": (
                    current_choice != after_choice
                    if current_choice and after_choice
                    else None
                ),
            },
            "limitations": limitations,
            "map_paths": {"lv grid": str(map_path)} if map_path.exists() else {},
        }

    # -- Network design -----------------------------------------------------
    def _format_network_design(self, results: Dict, street_id: str) -> Dict[str, Any]:
        cha_kpis = self._extract_cha_kpis(results)

        from branitz_heat_decision.config import resolve_cluster_path

        cha_dir = resolve_cluster_path(street_id, "cha")
        dha_dir = resolve_cluster_path(street_id, "dha")

        # Artifact-only requests do not run CHA, so load its persisted KPIs for
        # the topology summary shown below the map.
        if not cha_kpis:
            kpi_path = cha_dir / "cha_kpis.json"
            if kpi_path.exists():
                try:
                    import json
                    with open(kpi_path, encoding="utf-8") as f:
                        cha_kpis = json.load(f)
                except (OSError, ValueError) as exc:
                    logger.warning("Could not load network KPIs for %s: %s", street_id, exc)

        detailed = cha_kpis.get("detailed", {})
        topology = cha_kpis.get("topology", {})
        pipes = detailed.get("pipes", cha_kpis.get("pipes", []))
        heat_consumers = detailed.get("heat_consumers", cha_kpis.get("heat_consumers", []))

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
            decision_result = results["decision"]
            dec_data = decision_result.data.get("decision", {})
            validation = decision_result.data.get("validation")
            llm_explanation = decision_result.data.get("llm_explanation")
            explanation_source = decision_result.data.get("explanation_source")
            validation_passed = bool(
                validation
                and str(validation.get("validation_status", "")).lower() == "pass"
                and int(validation.get("contradiction_count", 0) or 0) == 0
            )
            from branitz_heat_decision.validation.rejection_audit import (
                build_rejection_audit,
            )

            return {
                "choice": dec_data.get("recommendation") or dec_data.get("choice"),
                "recommendation": dec_data.get("recommendation") or dec_data.get("choice"),
                "robust": dec_data.get("robust", False),
                "reason": dec_data.get("reason", ""),
                "reason_codes": dec_data.get("reason_codes", []),
                "metrics_used": dec_data.get("metrics_used", {}),
                "llm_explanation": llm_explanation if validation_passed else None,
                "explanation_source": explanation_source if validation_passed else None,
                "explanation_model": (
                    decision_result.data.get("explanation_model")
                    if validation_passed
                    else None
                ),
                "validation": validation,
                "rejection_audit": build_rejection_audit(validation),
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
