"""
Automated Grid Reinforcement Planning.

Implements a heuristic greedy algorithm (simplified from Fraunhofer's Iterated Local Search)
to identifying cost-effective grid upgrades (Line replacements, Transformer upgrades)
that resolve DHA violations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import copy
import logging
import math
import time
import pandas as pd
import numpy as np

try:
    import pandapower as pp
except ImportError:
    pass

from .config import DHAConfig
from .loadflow import run_loadflow
from .kpi_extractor import extract_dha_kpis

logger = logging.getLogger(__name__)

@dataclass
class ReinforcementMeasure:
    """Single reinforcement action"""
    measure_type: str  # "replace_line", "upgrade_trafo"
    element_id: int    # index in pandapower table
    old_type: str
    new_type: str
    cost_eur: float
    description: str
    old_parallel: Optional[int] = None
    new_parallel: Optional[int] = None
    design_loading_pct: Optional[float] = None

@dataclass
class ReinforcementPlan:
    measures: List[ReinforcementMeasure]
    total_cost_eur: float
    is_sufficient: bool
    remaining_violations: int
    before_kpis: Dict[str, Any] = field(default_factory=dict)
    after_kpis: Dict[str, Any] = field(default_factory=dict)
    calculation_duration_seconds: float = 0.0
    calculated_at_utc: str = ""
    methodology: str = "verified_iterative_load_flow"
    target_loading_pct: float = 79.0
    cost_assumptions: Dict[str, Any] = field(default_factory=lambda: {
        "currency": "EUR",
        "basis": "simplified planning unit-cost catalog",
        "included": "additional cable circuit or transformer equipment by modeled length/count",
        "excluded": "site-specific excavation, permits, land, traffic management, and utility quotations",
    })

# Simplified cost catalog (EUR)
# In production, this should be loaded from a CSV/DB
COST_CATALOG = {
    "line_per_km": {
        "NAYY 4x50 SE": 15000,
        "NAYY 4x150 SE": 35000,
        "NAYY 4x240 SE": 55000
    },
    "trafo_total": {
        "0.25 MVA 20/0.4 kV": 15000,
        "0.4 MVA 20/0.4 kV": 22000,
        "0.63 MVA 20/0.4 kV": 28000,
        "1.0 MVA 20/0.4 kV": 40000
    }
}

def plan_grid_reinforcement(
    net: pp.pandapowerNet,
    loads_by_hour: Dict[int, pd.DataFrame],
    cfg: DHAConfig,
    max_iterations: int = 10,
    target_loading_pct: float = 79.0,
    return_details: bool = False,
) -> Any:
    """
    Generate and verify a reinforcement plan that resolves LV-grid violations.

    Imported Branitz lines use explicit electrical parameters and often have no
    ``std_type``.  Therefore merely changing the label does not alter the power
    flow.  This planner installs real parallel cable/transformer circuits by
    updating pandapower's ``parallel`` parameter, reruns every design hour, and
    persists auditable before/after KPIs.
    """
    
    started = time.perf_counter()
    calculated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    current_net = copy.deepcopy(net)
    measures: List[ReinforcementMeasure] = []
    before_kpis: Dict[str, Any] = {}
    last_kpis: Dict[str, Any] = {}
    last_results: Dict[int, Dict[str, object]] = {}
    last_violations = pd.DataFrame()

    target_loading_pct = min(
        float(target_loading_pct),
        float(cfg.planning_warning_pct) - 0.1,
    )

    for iteration in range(max_iterations):
        results = run_loadflow(current_net, loads_by_hour)
        kpis, violations_df = extract_dha_kpis(results, cfg, net=current_net)
        last_kpis = copy.deepcopy(kpis)
        last_results = results
        last_violations = violations_df.copy()
        if not before_kpis:
            before_kpis = copy.deepcopy(kpis)

        if kpis.get("feasible", False) and not kpis.get("planning_warnings_total", 0):
            logger.info("Grid is feasible with planning headroom. Reinforcement planning complete.")
            plan = ReinforcementPlan(
                measures=measures,
                total_cost_eur=sum(m.cost_eur for m in measures),
                is_sufficient=True,
                remaining_violations=0,
                before_kpis=before_kpis,
                after_kpis=last_kpis,
                calculation_duration_seconds=time.perf_counter() - started,
                calculated_at_utc=calculated_at,
                target_loading_pct=target_loading_pct,
            )
            if return_details:
                return plan, current_net, last_results, last_violations
            return plan

        iteration_measures: List[ReinforcementMeasure] = []

        # Upgrade every overloaded line in the current iteration.  Applying the
        # complete batch avoids a slow one-line-per-load-flow loop for streets
        # such as ST010 with many overloaded segments.
        line_loading = _max_element_loading(results, "line_results")
        for line_idx, loading_pct in sorted(line_loading.items()):
            if loading_pct <= float(cfg.planning_warning_pct):
                continue
            current_parallel = max(1, int(current_net.line.at[line_idx, "parallel"]))
            required_parallel = max(
                current_parallel + 1,
                int(math.ceil(current_parallel * loading_pct / target_loading_pct)),
            )
            measure = _add_parallel_line(
                current_net,
                line_idx,
                required_parallel,
                loading_pct,
            )
            if measure:
                iteration_measures.append(measure)

        trafo_loading = _max_element_loading(results, "trafo_results")
        for trafo_idx, loading_pct in sorted(trafo_loading.items()):
            if loading_pct <= float(cfg.trafo_loading_limit_pct):
                continue
            current_parallel = max(1, int(current_net.trafo.at[trafo_idx, "parallel"]))
            required_parallel = max(
                current_parallel + 1,
                int(math.ceil(current_parallel * loading_pct / target_loading_pct)),
            )
            measure = _add_parallel_trafo(
                current_net,
                trafo_idx,
                required_parallel,
                loading_pct,
            )
            if measure:
                iteration_measures.append(measure)

        # A pure voltage violation may remain without a thermal overload.  Add
        # one parallel circuit to the most heavily loaded line and verify again.
        if not iteration_measures and kpis.get("voltage_violations_total", 0):
            if line_loading:
                worst_line, loading_pct = max(line_loading.items(), key=lambda item: item[1])
                current_parallel = max(1, int(current_net.line.at[worst_line, "parallel"]))
                measure = _add_parallel_line(
                    current_net,
                    worst_line,
                    current_parallel + 1,
                    loading_pct,
                )
                if measure:
                    iteration_measures.append(measure)

        if not iteration_measures:
            logger.warning("Could not find suitable upgrade measure despite violations.")
            break

        for measure in iteration_measures:
            logger.info("Iteration %d: %s", iteration, measure.description)
        measures.extend(iteration_measures)

    remaining = _critical_violation_count(last_violations)
    plan = ReinforcementPlan(
        measures=measures,
        total_cost_eur=sum(m.cost_eur for m in measures),
        is_sufficient=False,
        remaining_violations=remaining,
        before_kpis=before_kpis,
        after_kpis=last_kpis,
        calculation_duration_seconds=time.perf_counter() - started,
        calculated_at_utc=calculated_at,
        target_loading_pct=target_loading_pct,
    )
    if return_details:
        return plan, current_net, last_results, last_violations
    return plan


def _critical_violation_count(violations: pd.DataFrame) -> int:
    if violations is None or violations.empty or "type" not in violations:
        return 0
    return int(
        violations["type"].isin(
            ["voltage", "line_overload", "trafo_overload", "non_convergence"]
        ).sum()
    )


def _max_element_loading(
    results: Dict[int, Dict[str, object]],
    result_key: str,
) -> Dict[int, float]:
    maxima: Dict[int, float] = {}
    for result in results.values():
        frame = result.get(result_key)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        if "loading_percent" not in frame.columns:
            continue
        for element_idx, raw_value in frame["loading_percent"].items():
            value = float(pd.to_numeric(raw_value, errors="coerce"))
            if np.isfinite(value):
                idx = int(element_idx)
                maxima[idx] = max(maxima.get(idx, 0.0), value)
    return maxima


def _infer_line_type_and_cost(net, line_idx: int) -> tuple[str, float]:
    row = net.line.loc[line_idx]
    std_type = row.get("std_type")
    if isinstance(std_type, str) and std_type in COST_CATALOG["line_per_km"]:
        return std_type, float(COST_CATALOG["line_per_km"][std_type])

    max_i_ka = float(row.get("max_i_ka", 0.0) or 0.0)
    if max_i_ka <= 0.16:
        inferred = "NAYY 4x50 SE"
    elif max_i_ka <= 0.28:
        inferred = "NAYY 4x150 SE"
    else:
        inferred = "NAYY 4x240 SE"
    return inferred, float(COST_CATALOG["line_per_km"][inferred])


def _add_parallel_line(
    net,
    line_idx: int,
    new_parallel: int,
    loading_pct: float,
) -> Optional[ReinforcementMeasure]:
    old_parallel = max(1, int(net.line.at[line_idx, "parallel"]))
    if new_parallel <= old_parallel:
        return None
    length_km = float(net.line.at[line_idx, "length_km"])
    cable_type, cost_per_km = _infer_line_type_and_cost(net, line_idx)
    added_circuits = int(new_parallel - old_parallel)
    cost = added_circuits * length_km * cost_per_km
    net.line.at[line_idx, "parallel"] = int(new_parallel)
    return ReinforcementMeasure(
        measure_type="add_parallel_cable",
        element_id=int(line_idx),
        old_type=f"{old_parallel} × {cable_type}",
        new_type=f"{new_parallel} × {cable_type}",
        cost_eur=float(cost),
        description=(
            f"Line {line_idx}: install {added_circuits} parallel {cable_type} cable "
            f"circuit(s) over {length_km:.3f} km"
        ),
        old_parallel=old_parallel,
        new_parallel=int(new_parallel),
        design_loading_pct=float(loading_pct),
    )


def _add_parallel_trafo(
    net,
    trafo_idx: int,
    new_parallel: int,
    loading_pct: float,
) -> Optional[ReinforcementMeasure]:
    old_parallel = max(1, int(net.trafo.at[trafo_idx, "parallel"]))
    if new_parallel <= old_parallel:
        return None
    sn_mva = float(net.trafo.at[trafo_idx, "sn_mva"])
    type_name = min(
        COST_CATALOG["trafo_total"],
        key=lambda name: abs(float(name.split()[0]) - sn_mva),
    )
    added_units = int(new_parallel - old_parallel)
    cost = added_units * float(COST_CATALOG["trafo_total"][type_name])
    net.trafo.at[trafo_idx, "parallel"] = int(new_parallel)
    return ReinforcementMeasure(
        measure_type="add_parallel_transformer",
        element_id=int(trafo_idx),
        old_type=f"{old_parallel} × {type_name}",
        new_type=f"{new_parallel} × {type_name}",
        cost_eur=float(cost),
        description=(
            f"Transformer {trafo_idx}: install {added_units} parallel {type_name} unit(s)"
        ),
        old_parallel=old_parallel,
        new_parallel=int(new_parallel),
        design_loading_pct=float(loading_pct),
    )
