"""
Tests for consistency of LLM explanations across multiple runs.

Speaker-B requirement: "He needs to say 'no, I don't know exactly' instead
of going crazy" — and when he *does* answer, the numbers must match the
contract every single time.

These tests verify:
1. Decision choice is deterministic across runs
2. Template explanations are perfectly identical
3. LLM explanations contain only numbers from the KPI contract
4. ClaimExtractor finds no mismatches against reference KPIs
5. TNLI validation passes on every run
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from branitz_heat_decision.config import resolve_cluster_path, RESULTS_ROOT
from branitz_heat_decision.validation.logic_auditor import (
    ClaimExtractor,
    GOLDEN_FIXTURES,
    GOLDEN_REFERENCE_KPIS,
    test_golden_fixtures,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_any_cluster() -> Optional[str]:
    """Return the first cluster_id that has decision results, or None."""
    cha_dir = RESULTS_ROOT / "cha"
    if not cha_dir.exists():
        return None
    for d in sorted(cha_dir.iterdir()):
        if d.is_dir() and (d / "cha_kpis.json").exists():
            # Check if the full pipeline has been run
            cid = d.name
            decision_path = resolve_cluster_path(cid, "decision") / f"decision_{cid}.json"
            if decision_path.exists():
                return cid
    return None


def _load_contract_and_decision(cluster_id: str):
    """Load KPI contract and decision JSON for a cluster."""
    decision_dir = resolve_cluster_path(cluster_id, "decision")
    contract_path = decision_dir / f"kpi_contract_{cluster_id}.json"
    decision_path = decision_dir / f"decision_{cluster_id}.json"
    return _load_json(contract_path), _load_json(decision_path)


def _load_economics(cluster_id: str) -> Dict[str, Any]:
    """Load economics deterministic JSON for reference KPIs."""
    econ_dir = resolve_cluster_path(cluster_id, "economics")
    det = econ_dir / "economics_deterministic.json"
    if det.exists():
        return _load_json(det)
    mc = econ_dir / "monte_carlo_summary.json"
    if mc.exists():
        return _load_json(mc)
    return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cluster_id():
    """Find a cluster with completed pipeline results, or skip."""
    cid = _find_any_cluster()
    if cid is None:
        pytest.skip(
            "No cluster with decision results found. "
            "Run the full pipeline first: "
            "PYTHONPATH=src python -m branitz_heat_decision.cli.decision "
            "--cluster-id <CLUSTER_ID>"
        )
    return cid


@pytest.fixture
def contract_and_decision(cluster_id):
    """Load contract and decision for the test cluster."""
    contract, decision = _load_contract_and_decision(cluster_id)
    if not contract or not decision:
        pytest.skip(f"Contract or decision missing for {cluster_id}")
    return contract, decision


@pytest.fixture
def reference_kpis(cluster_id):
    """Build reference KPIs from economics + decision data."""
    econ = _load_economics(cluster_id)
    _, decision = _load_contract_and_decision(cluster_id)
    # Merge economics and decision metrics for cross-validation
    kpis: Dict[str, Any] = {}
    kpis.update(econ)
    kpis.update(decision.get("metrics_used", {}))
    if not kpis:
        pytest.skip(f"No reference KPIs available for {cluster_id}")
    return kpis


# ---------------------------------------------------------------------------
# Test 1: Golden fixture self-test (no external dependencies)
# ---------------------------------------------------------------------------

class TestGoldenFixtures:
    """Verify ClaimExtractor against known-good and known-bad explanations."""

    def test_all_golden_fixtures_pass(self):
        """All golden fixtures must produce the expected pass/fail result."""
        results = test_golden_fixtures()
        for r in results:
            assert r["correct"], (
                f"Golden fixture '{r['name']}' failed: "
                f"expected_pass={r['expected_pass']}, actual_pass={r['actual_pass']}"
            )

    def test_extraction_finds_expected_claims(self):
        """ClaimExtractor must find the expected claim keys in each fixture."""
        for fixture in GOLDEN_FIXTURES:
            extracted = ClaimExtractor.extract_all(fixture["explanation"])
            for key in fixture["expected_claims"]:
                assert key in extracted, (
                    f"Fixture '{fixture['name']}': "
                    f"missing claim '{key}' in extraction. Got: {list(extracted.keys())}"
                )

    def test_wrong_numbers_detected(self):
        """ClaimExtractor must flag wrong numbers as MISMATCH."""
        wrong_fixture = next(f for f in GOLDEN_FIXTURES if f["name"] == "ST010_wrong_numbers")
        extracted = ClaimExtractor.extract_all(wrong_fixture["explanation"])
        xval = ClaimExtractor.cross_validate(extracted, GOLDEN_REFERENCE_KPIS)

        mismatches = [r for r in xval if not r[3]]  # r[3] is is_match
        assert len(mismatches) > 0, "Wrong numbers should produce at least one mismatch"

    def test_correct_numbers_all_match(self):
        """ClaimExtractor must confirm all correct numbers as MATCH."""
        correct_fixture = next(f for f in GOLDEN_FIXTURES if f["name"] == "ST010_CO2_correct")
        extracted = ClaimExtractor.extract_all(correct_fixture["explanation"])
        xval = ClaimExtractor.cross_validate(extracted, GOLDEN_REFERENCE_KPIS)

        assert all(r[3] for r in xval), (
            f"All correct numbers should match. Mismatches: "
            f"{[(r[0], r[1], r[2]) for r in xval if not r[3]]}"
        )


# ---------------------------------------------------------------------------
# Test 2: Template explanation determinism
# ---------------------------------------------------------------------------

class TestTemplateExplanation:
    """Template-based explanations must be perfectly identical across runs."""

    def test_template_determinism(self, contract_and_decision):
        """Generate template explanation 5x and assert all identical."""
        from branitz_heat_decision.uhdc.explainer import _fallback_template_explanation

        contract, decision = contract_and_decision
        explanations = []
        for _ in range(5):
            exp = _fallback_template_explanation(contract, decision, "executive")
            explanations.append(exp)

        # All must be byte-identical
        assert all(e == explanations[0] for e in explanations), (
            "Template explanations must be perfectly deterministic. "
            f"Got {len(set(explanations))} distinct versions."
        )

    def test_template_contains_contract_numbers(self, contract_and_decision, reference_kpis):
        """Template explanation should only use numbers from the contract."""
        from branitz_heat_decision.uhdc.explainer import _fallback_template_explanation

        contract, decision = contract_and_decision
        explanation = _fallback_template_explanation(contract, decision, "executive")

        extracted = ClaimExtractor.extract_all(explanation)
        xval = ClaimExtractor.cross_validate(extracted, reference_kpis)

        mismatches = [(k, tv, kv) for k, tv, kv, m, _ in xval if not m]
        assert len(mismatches) == 0, (
            f"Template explanation contains numbers that don't match KPIs: {mismatches}"
        )


# ---------------------------------------------------------------------------
# Test 3: Decision choice consistency via orchestrator
# ---------------------------------------------------------------------------

class TestDecisionConsistency:
    """Orchestrator must produce the same decision across repeated calls."""

    def test_decision_choice_stable(self, cluster_id):
        """Run 'Explain the decision' 3x and assert same choice each time."""
        from branitz_heat_decision.agents import BranitzOrchestrator

        api_key = os.getenv("GOOGLE_API_KEY", "")
        orchestrator = BranitzOrchestrator(api_key=api_key)

        choices = []
        for _ in range(3):
            result = orchestrator.route_request(
                "Explain the decision",
                cluster_id,
                context={},
                run_missing=False,  # Use cached results, don't re-run sims
            )
            data = result.get("data", {})
            # DecisionResult.to_dict() saves as "choice"; orchestrator reads
            # "recommendation" for the answer but "data" has the full dict
            choice = data.get("choice", data.get("recommendation", "UNKNOWN"))
            choices.append(choice)

        assert len(set(choices)) == 1, (
            f"Decision choice is inconsistent across runs: {choices}"
        )
        assert choices[0] in ("DH", "HP", "UNDECIDED"), (
            f"Unexpected decision choice: {choices[0]}"
        )

    def test_agent_trace_present(self, cluster_id):
        """Every orchestrator response must include an agent trace."""
        from branitz_heat_decision.agents import BranitzOrchestrator

        api_key = os.getenv("GOOGLE_API_KEY", "")
        orchestrator = BranitzOrchestrator(api_key=api_key)

        result = orchestrator.route_request(
            "Explain the decision",
            cluster_id,
            context={},
            run_missing=False,
        )

        trace = result.get("agent_trace", [])
        assert len(trace) >= 3, (
            f"Expected at least 3 agent trace entries, got {len(trace)}: "
            f"{[t.get('agent') for t in trace]}"
        )

        # Verify key agents are present
        agent_names = {t.get("agent", "") for t in trace}
        assert "NLU Intent Classifier" in agent_names
        assert "Conversation Manager" in agent_names


# ---------------------------------------------------------------------------
# Test 4: LLM explanation numeric consistency (requires API key)
# ---------------------------------------------------------------------------

class TestLLMExplanationConsistency:
    """
    Validate that LLM-generated explanations only contain numbers
    present in the KPI contract.

    These tests require GOOGLE_API_KEY and are skipped if unavailable.
    """

    def test_llm_numbers_match_contract(self, contract_and_decision, reference_kpis):
        """LLM explanation numbers must all be found in the KPI contract."""
        try:
            from branitz_heat_decision.uhdc.explainer import (
                explain_with_llm,
                LLM_READY,
            )
        except ImportError:
            pytest.skip("google-genai SDK not installed")

        if not LLM_READY:
            pytest.skip("GOOGLE_API_KEY not set or LLM disabled")

        contract, decision = contract_and_decision
        explanation = explain_with_llm(contract, decision, style="executive")

        # Extract and cross-validate numeric claims
        extracted = ClaimExtractor.extract_all(explanation)
        xval = ClaimExtractor.cross_validate(extracted, reference_kpis)

        mismatches = [(k, tv, kv, reason) for k, tv, kv, m, reason in xval if not m]
        assert len(mismatches) == 0, (
            f"LLM explanation contains hallucinated numbers:\n"
            + "\n".join(f"  {reason}" for _, _, _, reason in mismatches)
        )

    def test_llm_explanation_stable_across_runs(self, contract_and_decision, reference_kpis):
        """
        Run LLM explanation 3x with temperature=0 and assert:
        - Same core claims extracted each time
        - No mismatches with KPIs in any run
        """
        try:
            from branitz_heat_decision.uhdc.explainer import (
                explain_with_llm,
                LLM_READY,
            )
        except ImportError:
            pytest.skip("google-genai SDK not installed")

        if not LLM_READY:
            pytest.skip("GOOGLE_API_KEY not set or LLM disabled")

        contract, decision = contract_and_decision
        all_extracted_keys: list = []
        all_mismatches: list = []

        for run_idx in range(3):
            explanation = explain_with_llm(contract, decision, style="executive")
            extracted = ClaimExtractor.extract_all(explanation)
            xval = ClaimExtractor.cross_validate(extracted, reference_kpis)

            all_extracted_keys.append(set(extracted.keys()))
            run_mismatches = [
                (run_idx, k, tv, kv, reason)
                for k, tv, kv, m, reason in xval if not m
            ]
            all_mismatches.extend(run_mismatches)

        # No mismatches in any run
        assert len(all_mismatches) == 0, (
            f"LLM explanation had hallucinated numbers across runs:\n"
            + "\n".join(f"  Run {r}: {reason}" for r, _, _, _, reason in all_mismatches)
        )

        # Claim keys should be largely consistent (at least 50% overlap)
        if len(all_extracted_keys) >= 2:
            overlap = all_extracted_keys[0] & all_extracted_keys[1]
            union = all_extracted_keys[0] | all_extracted_keys[1]
            if union:
                overlap_ratio = len(overlap) / len(union)
                assert overlap_ratio >= 0.5, (
                    f"LLM explanations are too inconsistent in claim coverage: "
                    f"overlap={overlap_ratio:.0%} "
                    f"(run 0: {all_extracted_keys[0]}, run 1: {all_extracted_keys[1]})"
                )


# ---------------------------------------------------------------------------
# Test 5: TNLI validation passes on actual decision
# ---------------------------------------------------------------------------

class TestTNLIValidation:
    """Verify TNLI validation produces pass/pass_with_warnings on real data."""

    def test_validation_on_decision(self, cluster_id):
        """
        Load the saved decision and run TNLI validation.
        The validation must not produce 'fail' status.
        """
        decision_dir = resolve_cluster_path(cluster_id, "decision")
        decision_path = decision_dir / f"decision_{cluster_id}.json"
        if not decision_path.exists():
            pytest.skip(f"Decision file not found for {cluster_id}")

        decision_data = _load_json(decision_path)
        if not decision_data:
            pytest.skip(f"Empty decision file for {cluster_id}")

        # Add cluster_id for the report
        decision_data["cluster_id"] = cluster_id

        try:
            from branitz_heat_decision.validation import LogicAuditor

            auditor = LogicAuditor()
            report = auditor.validate_decision_explanation(decision_data)

            assert report.validation_status in ("pass", "pass_with_warnings", "warning"), (
                f"Validation failed for {cluster_id}: "
                f"status={report.validation_status}, "
                f"contradictions={[c.statement for c in report.contradictions]}"
            )

            # Verified should be > 0 (at least some claims validated)
            assert report.verified_count > 0, (
                f"No claims were verified for {cluster_id}"
            )
        except ImportError:
            pytest.skip("TNLI model dependencies not available")

    def test_validation_report_serialisable(self, cluster_id):
        """ValidationReport.to_dict() must produce valid JSON."""
        decision_dir = resolve_cluster_path(cluster_id, "decision")
        decision_path = decision_dir / f"decision_{cluster_id}.json"
        if not decision_path.exists():
            pytest.skip(f"Decision file not found for {cluster_id}")

        decision_data = _load_json(decision_path)
        decision_data["cluster_id"] = cluster_id

        try:
            from branitz_heat_decision.validation import LogicAuditor

            auditor = LogicAuditor()
            report = auditor.validate_decision_explanation(decision_data)

            # Must be serialisable
            report_dict = report.to_dict()
            serialised = json.dumps(report_dict, default=str)
            assert len(serialised) > 10, "Serialised report is suspiciously short"

            # Must have required keys
            assert "validation_status" in report_dict
            assert "verified_count" in report_dict
            assert "contradiction_count" in report_dict
            assert "sentence_results" in report_dict
        except ImportError:
            pytest.skip("TNLI model dependencies not available")
