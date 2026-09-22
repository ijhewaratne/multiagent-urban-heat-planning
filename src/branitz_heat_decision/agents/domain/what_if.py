"""What-if scenario domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

from .cha import CHAAgent

logger = logging.getLogger(__name__)


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
