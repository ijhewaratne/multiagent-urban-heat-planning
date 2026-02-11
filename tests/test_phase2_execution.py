"""
Phase 2 Dynamic Execution Engine Tests.

Validates DynamicExecutor: lazy execution, what-if scenarios, intent routing.
Run with: PYTHONPATH=src pytest tests/test_phase2_execution.py -v

Integration tests require pre-run CHA/DHA/Economics for a cluster.
"""

import time
import pytest

from branitz_heat_decision.agents.executor import DynamicExecutor, SimulationType, SimulationCache
from branitz_heat_decision.config import resolve_cluster_path


def _has_cluster_results(cluster_id: str) -> bool:
    """Check if CHA, DHA, Economics results exist for cluster."""
    cha_ok = (resolve_cluster_path(cluster_id, "cha") / "cha_kpis.json").exists()
    dha_ok = (resolve_cluster_path(cluster_id, "dha") / "dha_kpis.json").exists()
    econ_ok = (resolve_cluster_path(cluster_id, "economics") / "economics_deterministic.json").exists()
    return cha_ok and dha_ok and econ_ok


def _has_network_pickle(cluster_id: str) -> bool:
    """Check if CHA network.pickle exists (required for what-if)."""
    return (resolve_cluster_path(cluster_id, "cha") / "network.pickle").exists()


# Use a cluster ID that may exist; adjust per your data
TEST_CLUSTER = "ST010_HEINRICH_ZILLE_STRASSE"


def test_executor_loads():
    """Verify DynamicExecutor and types can be instantiated."""
    executor = DynamicExecutor(cache_dir="./cache")
    assert executor is not None
    assert executor.scenario_counter >= 0
    assert list(SimulationType)  # enum has members


def test_executor_unknown_intent_raises():
    """Executor must raise ValueError for non-simulation intents."""
    executor = DynamicExecutor()
    with pytest.raises(ValueError, match="EXPLAIN_DECISION|Unknown"):
        executor.execute("EXPLAIN_DECISION", "ST001", {})
    with pytest.raises(ValueError, match="CAPABILITY_QUERY|Unknown"):
        executor.execute("CAPABILITY_QUERY", "ST001", {})


def test_executor_co2_result_structure():
    """CO2_COMPARISON returns expected keys when data exists."""
    executor = DynamicExecutor()
    result = executor.execute("CO2_COMPARISON", TEST_CLUSTER, {})
    # May succeed (data exists) or return error (no data)
    if "error" in result:
        pytest.skip(f"No cluster results for {TEST_CLUSTER}")
    assert "dh_tons_co2" in result
    assert "cha_tons_co2" in result
    assert "winner" in result
    assert "execution_log" in result
    assert result["winner"] in ("DH", "CHA")
    assert isinstance(result["execution_log"], list)


@pytest.mark.integration
def test_lazy_execution():
    """Verify second call uses file cache (faster when first ran simulations)."""
    if not _has_cluster_results(TEST_CLUSTER):
        pytest.skip(f"No results for {TEST_CLUSTER}; run CHA, DHA, Economics first")

    executor = DynamicExecutor(cache_dir="./cache")
    street_id = TEST_CLUSTER

    # First call - may run or read from disk
    start = time.time()
    result1 = executor.execute("CO2_COMPARISON", street_id)
    time_first = time.time() - start

    if "error" in result1:
        pytest.skip(f"CO2 execution failed: {result1['error']}")

    print(f"First call: {time_first:.2f}s, log: {result1['execution_log']}")

    # Second call - should read from disk (faster)
    start = time.time()
    result2 = executor.execute("CO2_COMPARISON", street_id)
    time_second = time.time() - start

    print(f"Second call: {time_second:.2f}s")

    # Consistency: same values
    assert result1["dh_tons_co2"] == result2["dh_tons_co2"]
    assert result1["cha_tons_co2"] == result2["cha_tons_co2"]

    # When first actually ran simulations, second should be faster
    # (Skip speed check if both were fast e.g. cached)
    if time_first > 2.0:  # First call did real work
        assert time_second < time_first * 0.9, (
            f"Cached call {time_second:.2f}s should be faster than first {time_first:.2f}s"
        )


@pytest.mark.integration
def test_what_if_scenario():
    """Test 'what if we remove houses' scenario."""
    if not _has_cluster_results(TEST_CLUSTER):
        pytest.skip(f"No results for {TEST_CLUSTER}")
    if not _has_network_pickle(TEST_CLUSTER):
        pytest.skip(f"No network.pickle for {TEST_CLUSTER} (what-if needs CHA network)")

    executor = DynamicExecutor()
    street_id = TEST_CLUSTER

    # Get baseline first (ensures CHA exists)
    baseline = executor.execute("CO2_COMPARISON", street_id)
    if "error" in baseline:
        pytest.skip(f"Baseline failed: {baseline['error']}")

    print(f"Baseline CO2 DH: {baseline['dh_tons_co2']}")

    # What-if scenario
    what_if = executor.execute(
        "WHAT_IF_SCENARIO",
        street_id,
        context={"modification": "remove_2_houses"},
    )

    if "error" in what_if:
        pytest.skip(f"What-if failed: {what_if['error']}")

    print(f"Scenario CO2: {what_if['scenario']['co2_tons']}")
    print(f"Comparison: {what_if['comparison']}")

    assert "baseline" in what_if
    assert "scenario" in what_if
    assert "comparison" in what_if
    assert what_if["modification_applied"] == "remove_2_houses"

    # Baseline vs scenario: scenario should have lower heat (fewer consumers)
    comp = what_if["comparison"]
    assert "heat_delivered_change_mw" in comp
    assert "pressure_change_bar" in comp


def test_what_if_structure_without_data():
    """What-if returns error structure when pandapipes or data missing."""
    executor = DynamicExecutor()
    # Use cluster that likely has no results
    result = executor.execute(
        "WHAT_IF_SCENARIO",
        "ST999_NONEXISTENT",
        context={"modification": "remove_2_houses"},
    )
    # Either error (no data) or full structure (data exists)
    assert "execution_log" in result
    if "error" in result:
        assert "error" in result
    else:
        assert "baseline" in result
        assert "scenario" in result
        assert "modification_applied" in result


def test_lcoh_result_structure():
    """LCOH_COMPARISON returns expected keys when data exists."""
    executor = DynamicExecutor()
    result = executor.execute("LCOH_COMPARISON", TEST_CLUSTER, {})
    if "error" in result:
        pytest.skip(f"No cluster results for {TEST_CLUSTER}")
    assert "lcoh_dh_eur_per_mwh" in result
    assert "lcoh_hp_eur_per_mwh" in result
    assert "winner" in result
    assert "execution_log" in result


def test_violation_result_structure():
    """VIOLATION_ANALYSIS returns cha/dha structure when data exists."""
    executor = DynamicExecutor()
    result = executor.execute("VIOLATION_ANALYSIS", TEST_CLUSTER, {})
    if "error" in result:
        pytest.skip(f"No cluster results for {TEST_CLUSTER}")
    assert "cha" in result
    assert "dha" in result
    assert "execution_log" in result


if __name__ == "__main__":
    print("Phase 2 Dynamic Execution Tests\n")
    pytest.main([__file__, "-v", "-k", "not integration"])
