"""
Answer / response formatting for the Branitz orchestrator.

Transforms DynamicExecutor results into the orchestrator response format
(human-readable answers, visualization hints, decision enrichment).
Extracted from ``orchestrator.py``.
"""

from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from branitz_heat_decision.config import resolve_cluster_path

logger = logging.getLogger(__name__)


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file or return empty dict."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return {}


def explanation_matches_current_contract(cluster_id: str) -> bool:
    """Return true only when explanation provenance matches the baseline contract."""
    decision_dir = resolve_cluster_path(cluster_id, "decision")
    contract = load_json(decision_dir / f"kpi_contract_{cluster_id}.json")
    provenance = load_json(
        decision_dir / f"explanation_{cluster_id}_metadata.json"
    )
    if not contract or not provenance.get("contract_sha256"):
        return False
    canonical_contract = json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return provenance.get("contract_sha256") == hashlib.sha256(
        canonical_contract
    ).hexdigest()


def format_executor_response(
    intent: str,
    intent_data: Dict[str, Any],
    results: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Transform DynamicExecutor results to orchestrator response format.

    The executor now returns richer results including:
      - agent_results: per-agent success/cache/timing
      - total_execution_time: end-to-end duration
    These are passed through to the UI for transparency.
    """
    if "error" in results:
        return {
            "type": intent.lower(),
            "intent_data": intent_data,
            "execution_plan": results.get("execution_log", []),
            "data": results,
            "answer": results["error"],
            "sources": [],
            "can_proceed": False,
            "execution_log": results.get("execution_log", []),
            "visualization": None,
        }

    # Map executor data keys to orchestrator data format for UI compatibility
    data = dict(results)
    if intent == "CO2_COMPARISON":
        data["co2_dh_t_per_a"] = results.get("dh_tons_co2", 0)
        data["co2_hp_t_per_a"] = results.get("hp_tons_co2", 0)
    elif intent == "LCOH_COMPARISON":
        data["lcoh_dh_eur_per_mwh"] = results.get("lcoh_dh_eur_per_mwh", 0)
        data["lcoh_hp_eur_per_mwh"] = results.get("lcoh_hp_eur_per_mwh", 0)
    elif intent == "EXPLAIN_DECISION":
        # Enrich with full decision JSON from disk for UI rendering
        enrich_decision_data(data, intent_data)

    # Build answer/viz from enriched data (important for EXPLAIN_DECISION).
    answer = format_answer(data, intent)
    viz = create_viz(data, intent)

    return {
        "type": intent.lower(),
        "intent_data": intent_data,
        "execution_plan": results.get("execution_log", []),
        "data": data,
        "answer": answer,
        "sources": ["DynamicExecutor"] + (results.get("execution_log", []) or []),
        "can_proceed": True,
        "execution_log": results.get("execution_log", []),
        "visualization": viz,
        # New: agent-level performance metadata
        "agent_results": results.get("agent_results", {}),
        "total_execution_time": results.get("total_execution_time"),
    }


def format_answer(results: Dict[str, Any], intent: str) -> str:
    """Convert executor results to human-readable answer."""
    if intent == "CO2_COMPARISON":
        dh = results.get("dh_tons_co2", 0)
        hp = results.get("hp_tons_co2", 0)
        winner = results.get("winner", "")
        return (
            f"District Heating: {dh:.1f} tCO₂/year vs Heat Pumps: {hp:.1f} tCO₂/year. "
            f"{winner} has lower emissions."
        )
    if intent == "LCOH_COMPARISON":
        dh = results.get("lcoh_dh_eur_per_mwh", 0)
        hp = results.get("lcoh_hp_eur_per_mwh", 0)
        winner = results.get("winner", "")
        return (
            f"LCOH DH: {dh:.1f} €/MWh vs HP: {hp:.1f} €/MWh. "
            f"{winner} has lower cost."
        )
    if intent == "VIOLATION_ANALYSIS":
        cha = results.get("cha", {})
        dha = results.get("dha", {})
        v_max = cha.get("velocity_ms_max", "N/A")
        p_max = cha.get("pressure_bar_max", "N/A")
        v_viol = dha.get("voltage_violations", 0)
        l_viol = dha.get("line_violations", 0)
        return (
            f"CHA: max velocity={v_max} m/s, max pressure={p_max} bar. "
            f"DHA: {v_viol} voltage violations, {l_viol} line violations."
        )
    if intent == "NETWORK_DESIGN":
        topo = results.get("topology", {})
        pipes = results.get("pipes", [])
        map_paths = results.get("map_paths", {})
        n_pipes = len(pipes) if isinstance(pipes, list) else 0
        n_buildings = (
            topo.get("spurs")
            or topo.get("buildings_connected")
            or len(results.get("heat_consumers", []))
            or "N/A"
        )
        n_trunk = topo.get("trunk_edges", "N/A")
        n_nodes = topo.get("trunk_nodes", "N/A")
        maps_available = ", ".join(map_paths.keys()) if map_paths else "none"
        return (
            f"The district heating network has {n_buildings} buildings connected, "
            f"{n_pipes} pipes, {n_trunk} trunk edges, and {n_nodes} trunk nodes. "
            f"Interactive maps available: {maps_available}."
        )
    if intent == "GRID_REINFORCEMENT":
        return format_grid_reinforcement_answer(results)
    if intent == "WHAT_IF_SCENARIO":
        mod = results.get("modification_applied", "N/A")
        comp = results.get("comparison", {})
        dp = comp.get("pressure_change_bar", 0)
        dq = comp.get("heat_delivered_change_mw", 0)
        return (
            f"What-if ({mod}): pressure change {dp:.4f} bar, "
            f"heat delivered change {dq:.4f} MW."
        )
    if intent == "EXPLAIN_DECISION":
        return format_decision_answer(results)
    return str(results)


def format_grid_reinforcement_answer(results: Dict[str, Any]) -> str:
    """Render the LV-grid evidence and reinforced-grid decision comparison."""
    street_id = results.get("street_id", "the selected street")
    grid = results.get("current_grid", {})
    post_grid = results.get("post_reinforcement_grid", {})
    reinforcement = results.get("reinforcement", {})
    economics = results.get("economics", {})
    impact = results.get("decision_impact", {})

    feasible = grid.get("feasible")
    if feasible is True:
        status = "feasible"
    elif feasible is False:
        status = "not feasible"
    else:
        status = "not determined"
    loading = grid.get("max_feeder_loading_pct")
    limit = grid.get("loading_limit_pct", 100.0)
    loading_text = f"{loading:.1f}%" if isinstance(loading, (int, float)) else "not available"

    lines = [f"**LV-grid reinforcement — {street_id}**", ""]
    lines.append(
        f"**Current grid:** {status}. Maximum feeder loading is **{loading_text}** "
        f"(limit {limit:.0f}%). There are **{grid.get('line_violations_total', 0)} line**, "
        f"**{grid.get('voltage_violations_total', 0)} voltage**, and "
        f"**{grid.get('trafo_violations_total', 0)} transformer** violations."
    )
    overload_hours = grid.get("line_overload_hours", 0)
    hours_total = grid.get("hours_total", 0)
    worst_line = grid.get("worst_line_id")
    if overload_hours or worst_line:
        detail = f"Line overloads occur in {overload_hours} of {hours_total} evaluated critical hours"
        if worst_line is not None:
            detail += f"; the worst line is `{worst_line}`"
        lines.append(detail + ".")

    if post_grid:
        def display_value(value: Any, suffix: str = "") -> str:
            if isinstance(value, bool):
                return "Yes" if value else "No"
            if isinstance(value, (int, float)):
                return f"{value:.1f}{suffix}" if suffix else f"{value:g}"
            return "N/A"

        lines.extend([
            "",
            "**Verified before/after load-flow results:**",
            "",
            "| KPI | Before reinforcement | After reinforcement |",
            "|---|---:|---:|",
            f"| Grid feasible | {display_value(grid.get('feasible'))} | "
            f"{display_value(post_grid.get('feasible'))} |",
            f"| Maximum feeder loading | {display_value(grid.get('max_feeder_loading_pct'), '%')} | "
            f"{display_value(post_grid.get('max_feeder_loading_pct'), '%')} |",
            f"| Line violations | {display_value(grid.get('line_violations_total'))} | "
            f"{display_value(post_grid.get('line_violations_total'))} |",
            f"| Voltage violations | {display_value(grid.get('voltage_violations_total'))} | "
            f"{display_value(post_grid.get('voltage_violations_total'))} |",
            f"| Transformer violations | {display_value(grid.get('trafo_violations_total'))} | "
            f"{display_value(post_grid.get('trafo_violations_total'))} |",
        ])

    lines.extend(["", "**Reinforcement measures:**"])
    recommendations = reinforcement.get("recommendations", []) or []
    optimized = reinforcement.get("optimized_measures", []) or []
    if optimized:
        for measure in optimized:
            description = measure.get("description") or measure.get("measure_type", "Grid upgrade")
            measure_cost = measure.get("cost_eur")
            if isinstance(measure_cost, (int, float)):
                description += f" — €{measure_cost:,.0f}"
            lines.append(f"- {description}")
    elif recommendations:
        for recommendation in recommendations:
            title = recommendation.get("title", "Grid reinforcement")
            lines.append(f"- {title}")
            for action in recommendation.get("actions", []) or []:
                lines.append(f"  - {action}")
    else:
        lines.append("- No reinforcement is required for the current grid.")

    cost = reinforcement.get("cost_eur")
    cost_source = reinforcement.get("cost_source", "not calculated")
    if isinstance(cost, (int, float)):
        qualifier = "estimated " if reinforcement.get("cost_is_estimate") else ""
        lines.extend([
            "",
            f"**Reinforcement cost:** {qualifier}**€{cost:,.0f}** ({cost_source}).",
        ])
    else:
        lines.extend(["", f"**Reinforcement cost:** not available ({cost_source})."])

    cost_assumptions = reinforcement.get("cost_assumptions", {})
    if cost_assumptions:
        lines.append(
            "**Cost basis:** "
            f"{cost_assumptions.get('basis', 'planning unit-cost catalog')}; excludes "
            f"{cost_assumptions.get('excluded', 'site-specific civil works and utility quotations')}."
        )

    current_choice = impact.get("current_choice") or "not available"
    after_choice = impact.get("counterfactual_choice") or "not available"
    post_feasible = impact.get("post_reinforcement_hp_feasible")
    basis = impact.get("post_reinforcement_feasibility_basis", "")
    if post_feasible is True:
        feasibility_text = "feasible"
    elif post_feasible is False:
        feasibility_text = "not feasible"
    else:
        feasibility_text = "not determined"

    lines.extend([
        "",
        "**Decision impact:**",
        f"- Current recommendation: **{current_choice}**",
        f"- HP after reinforcement: **{feasibility_text}** ({basis})",
        f"- Counterfactual recommendation: **{after_choice}**",
    ])
    decision_changes = impact.get("decision_changes")
    if decision_changes is True:
        lines.append(f"- **Yes, the decision changes from {current_choice} to {after_choice}.**")
    elif decision_changes is False:
        lines.append(f"- **No, the decision remains {current_choice}.**")

    lcoh_dh = economics.get("lcoh_dh_eur_per_mwh")
    lcoh_hp = economics.get("lcoh_hp_eur_per_mwh")
    if isinstance(lcoh_dh, (int, float)) and isinstance(lcoh_hp, (int, float)):
        lines.append(
            f"- Median LCOH used by the decision: DH **{lcoh_dh:.1f} €/MWh**, "
            f"HP **{lcoh_hp:.1f} €/MWh**."
        )

    limitations = results.get("limitations", []) or []
    if limitations:
        lines.extend(["", "**Important limitation:**"])
        lines.extend(f"- {item}" for item in limitations)

    return "\n".join(lines)


def format_decision_answer(results: Dict[str, Any]) -> str:
    """Build rich human-readable answer for EXPLAIN_DECISION."""
    rec = results.get("choice") or results.get("recommendation", "UNKNOWN")
    reason_codes = results.get("reason_codes", [])
    robust = results.get("robust", False)
    metrics = results.get("metrics_used", {})
    contract = results.get("kpi_contract")

    rec_label = {
        "DH": "District Heating (DH)",
        "HP": "Heat Pumps (HP)",
    }.get(rec, rec)
    robust_label = "robust" if robust else "sensitive to input uncertainty"

    # --- Headline ---
    lines = [f"**Recommendation: {rec_label}** ({robust_label})"]
    lines.append("")

    # --- Causal narrative from KPI contract (preferred) ---
    if contract:
        try:
            from branitz_heat_decision.uhdc.explainer import _build_decision_narrative
            decision_dict = {
                "choice": rec,
                "robust": robust,
                "reason_codes": reason_codes,
            }
            narrative = _build_decision_narrative(contract, decision_dict)
            lines.append(narrative)
            lines.append("")
        except Exception:
            contract = None  # fall through to KPI table

    # --- KPI table (fallback or supplement when contract unavailable) ---
    if not contract:
        lcoh_dh = metrics.get("lcoh_dh_median")
        lcoh_hp = metrics.get("lcoh_hp_median")
        co2_dh = metrics.get("co2_dh_median")
        co2_hp = metrics.get("co2_hp_median")
        dh_wins = metrics.get("dh_wins_fraction")
        hp_wins = metrics.get("hp_wins_fraction")

        if lcoh_dh and lcoh_hp:
            lines.append(f"**LCOH:** DH = {lcoh_dh:.1f} €/MWh | HP = {lcoh_hp:.1f} €/MWh")
        if co2_dh and co2_hp:
            lines.append(f"**CO₂:** DH = {co2_dh:.0f} kg/MWh | HP = {co2_hp:.0f} kg/MWh")
        if dh_wins is not None and hp_wins is not None:
            lines.append(
                f"**Monte Carlo:** DH wins {dh_wins:.0%} | HP wins {hp_wins:.0%} of scenarios"
            )
        lines.append("")

    # --- Validation footer ---
    val = results.get("validation", {}) or {}
    val_status = str(val.get("validation_status", "")).upper()
    if val_status:
        verified = val.get("verified_count", "?")
        total = val.get("statements_validated", "?")
        contradictions = val.get("contradiction_count", 0)
        lines.append(
            f"*Verification: {val_status} — {verified}/{total} claims verified, "
            f"{contradictions} contradictions.*"
        )

    audit = results.get("rejection_audit", {}) or {}
    adversarial = audit.get("global_adversarial_benchmark", {})
    infrastructure = audit.get("unsupported_infrastructure_changes", {})
    current = audit.get("current_explanation", {})
    if adversarial or infrastructure:
        lines.extend(["", "**Selected-street explanation audit**"])
        lines.append(
            f"- Actual generated prose: {current.get('statements_checked', 0)} "
            f"sentences checked — {current.get('verified', 0)} verified, "
            f"{current.get('unverified', 0)} unverified, "
            f"{current.get('rejected', 0)} rejected."
        )
        for statement in current.get("statements", []):
            lines.append(
                f"  - **{statement.get('id')} · {statement.get('status', '').upper()}:** "
                f"{statement.get('statement')} — {statement.get('reason')}"
            )
        if adversarial:
            lines.extend(["", "**Global fixed safety benchmark**"])
            lines.append(
                f"- {adversarial.get('blocked', 0)}/"
                f"{adversarial.get('total', 0)} false explanations blocked. "
                "The same 20 test statements run for the whole application; "
                "this score is intentionally identical for every street and does "
                "not guarantee every possible LLM sentence."
            )
            for case in adversarial.get("cases", []):
                lines.append(
                    f"  - **{case.get('id')} — {case.get('detector')}:** "
                    f"{case.get('reason')} Rejected statement: “{case.get('statement')}”"
                )
        if infrastructure:
            lines.append("- Unsupported infrastructure changes are refused because:")
            for case in infrastructure.get("cases", []):
                lines.append(
                    f"  - **{case.get('id')}:** {case.get('request')} — "
                    f"{case.get('reason')} Required step: {case.get('required_step')}"
                )

    return "\n".join(lines)


def enrich_decision_data(
    data: Dict[str, Any], intent_data: Dict[str, Any]
) -> None:
    """
    Enrich executor result with full decision JSON from disk.

    The executor returns a compact dict from the DecisionAgent.  The UI
    needs the complete decision JSON (choice, reason_codes, metrics_used,
    robustness, etc.) so we load it here and merge into *data* in-place.
    """
    cluster_id = (
        (intent_data.get("entities") or {}).get("street_name")
        or data.get("street_id")
    )
    if not cluster_id:
        return

    dec_path = (
        resolve_cluster_path(cluster_id, "decision")
        / f"decision_{cluster_id}.json"
    )
    dec = load_json(dec_path)
    if not dec:
        return

    # Normalise keys so UI can always read "recommendation" and "reason"
    rec = dec.get("choice") or dec.get("recommendation", "UNKNOWN")
    reason_codes = dec.get("reason_codes", [])
    dec["recommendation"] = rec
    dec["reason"] = dec.get("reason", "") or (
        ", ".join(reason_codes) if reason_codes else ""
    )

    sidecars_match = explanation_matches_current_contract(cluster_id)

    # Attach validation artifact (latest verification report) before deciding
    # whether its corresponding explanation is safe to display.
    val_path = (
        resolve_cluster_path(cluster_id, "decision")
        / f"validation_{cluster_id}.json"
    )
    validation = load_json(val_path) if sidecars_match else {}
    validation_passed = bool(
        validation
        and str(validation.get("validation_status", "")).lower() == "pass"
        and int(validation.get("contradiction_count", 0) or 0) == 0
    )
    if not sidecars_match or not validation_passed:
        data.pop("llm_explanation", None)
        data.pop("explanation_source", None)
        data.pop("explanation_model", None)

    # Attach long-form explanation text only when it was generated from the
    # exact current baseline contract.
    expl_path = (
        resolve_cluster_path(cluster_id, "decision")
        / f"explanation_{cluster_id}.md"
    )
    if validation_passed and expl_path.exists():
        try:
            data.setdefault("llm_explanation", expl_path.read_text(encoding="utf-8").strip())
        except Exception:
            pass

    if validation:
        data["validation"] = validation
    else:
        data.pop("validation", None)

    from branitz_heat_decision.validation.rejection_audit import (
        build_rejection_audit,
    )

    data["rejection_audit"] = build_rejection_audit(validation)

    # Attach KPI contract (needed by _format_decision_answer for the narrative)
    contract_path = (
        resolve_cluster_path(cluster_id, "decision")
        / f"kpi_contract_{cluster_id}.json"
    )
    contract = load_json(contract_path)
    if contract:
        data.setdefault("kpi_contract", contract)

    # Merge full decision fields into data (executor fields win on conflict)
    for key, val in dec.items():
        data.setdefault(key, val)


def create_viz(results: Dict[str, Any], intent: str) -> Optional[Dict[str, Any]]:
    """Create visualization hint for UI (chart type, series, etc.)."""
    if intent == "CO2_COMPARISON":
        return {
            "chart_type": "bar",
            "series": [
                {"name": "District Heating", "value": results.get("dh_tons_co2", 0)},
                {"name": "Heat Pump", "value": results.get("hp_tons_co2", 0)},
            ],
            "x_label": "Option",
            "y_label": "tCO₂/year",
        }
    if intent == "LCOH_COMPARISON":
        return {
            "chart_type": "bar",
            "series": [
                {"name": "District Heating", "value": results.get("lcoh_dh_eur_per_mwh", 0)},
                {"name": "Heat Pump", "value": results.get("lcoh_hp_eur_per_mwh", 0)},
            ],
            "x_label": "Option",
            "y_label": "€/MWh",
        }
    if intent == "WHAT_IF_SCENARIO":
        return {
            "chart_type": "comparison",
            "baseline": results.get("baseline", {}),
            "scenario": results.get("scenario", {}),
        }
    if intent == "EXPLAIN_DECISION":
        metrics = results.get("metrics_used", {})
        rec = results.get("choice") or results.get("recommendation", "UNKNOWN")
        return {
            "chart_type": "decision",
            "recommendation": rec,
            "robust": results.get("robust", False),
            "reason_codes": results.get("reason_codes", []),
            "metrics": {
                "lcoh_dh": metrics.get("lcoh_dh_median"),
                "lcoh_hp": metrics.get("lcoh_hp_median"),
                "co2_dh": metrics.get("co2_dh_median"),
                "co2_hp": metrics.get("co2_hp_median"),
            },
        }
    if intent == "GRID_REINFORCEMENT":
        grid = results.get("current_grid", {})
        reinforcement = results.get("reinforcement", {})
        impact = results.get("decision_impact", {})
        return {
            "chart_type": "grid_reinforcement",
            "max_feeder_loading_pct": grid.get("max_feeder_loading_pct"),
            "loading_limit_pct": grid.get("loading_limit_pct"),
            "reinforcement_cost_eur": reinforcement.get("cost_eur"),
            "current_choice": impact.get("current_choice"),
            "counterfactual_choice": impact.get("counterfactual_choice"),
            "map_paths": results.get("map_paths", {}),
        }
    return None
