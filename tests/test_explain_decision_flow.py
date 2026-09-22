import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from branitz_heat_decision.agents.answer_formatting import enrich_decision_data
from branitz_heat_decision.agents.domain_agents import DecisionAgent
from branitz_heat_decision.agents.executor import DynamicExecutor
from branitz_heat_decision.validation.rejection_audit import build_rejection_audit
from branitz_heat_decision.validation.logic_auditor import LogicAuditor
from branitz_heat_decision.uhdc.safety_validator import LogicAuditor as UHDCSafetyAuditor


class _FakeResult:
    def __init__(self, success: bool, data: dict):
        self.success = success
        self.data = data


def test_format_decision_only_surfaces_validated_explanation() -> None:
    executor = DynamicExecutor()

    with_validation = {
        "decision": _FakeResult(
            True,
            {
                "decision": {
                    "choice": "DH",
                    "reason_codes": ["COST_DOMINANT_DH"],
                    "metrics_used": {"lcoh_dh_median": 64.6},
                },
                "llm_explanation": "Validated explanation.",
                "explanation_source": "gemini_api",
                "explanation_model": "gemini-2.5-flash",
                "validation": {
                    "validation_status": "pass",
                    "verified_count": 3,
                    "statements_validated": 3,
                },
            },
        )
    }
    formatted = executor._format_decision(with_validation, "ST010")
    assert formatted["llm_explanation"] == "Validated explanation."
    assert formatted["explanation_source"] == "gemini_api"
    assert formatted["validation"]["validation_status"] == "pass"
    assert formatted["rejection_audit"]["global_adversarial_benchmark"]["blocked"] == 20

    without_validation = {
        "decision": _FakeResult(
            True,
            {
                "decision": {"choice": "DH"},
                "llm_explanation": "Unvalidated explanation.",
                "validation": None,
            },
        )
    }
    formatted = executor._format_decision(without_validation, "ST010")
    assert formatted["llm_explanation"] is None
    assert formatted["validation"] is None

    failed_validation = {
        "decision": _FakeResult(
            True,
            {
                "decision": {"choice": "DH"},
                "llm_explanation": "HP is feasible.",
                "explanation_source": "gemini_api",
                "validation": {
                    "validation_status": "fail",
                    "contradiction_count": 1,
                    "statements_validated": 1,
                    "verified_count": 0,
                    "contradictions": [
                        {
                            "statement": "HP is feasible",
                            "context": "hp_feasible=False",
                            "confidence": 1.0,
                        }
                    ],
                },
            },
        )
    }
    formatted = executor._format_decision(failed_validation, "ST010")
    assert formatted["llm_explanation"] is None
    assert formatted["explanation_source"] is None
    live_audit = formatted["rejection_audit"]["current_explanation"]
    assert live_audit["rejected"] == 1
    assert live_audit["rejections"][0]["reason"] == "hp_feasible=False"


def test_decision_agent_regenerates_when_live_gemini_explanation_is_required(
    monkeypatch, tmp_path: Path
) -> None:
    cluster_id = "ST_TEST_EXPLAIN_DECISION"

    def fake_resolve_cluster_path(street_id: str, phase: str) -> Path:
        assert street_id == cluster_id
        path = tmp_path / phase / street_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(
        "branitz_heat_decision.config.resolve_cluster_path",
        fake_resolve_cluster_path,
    )

    agent = DecisionAgent()
    monkeypatch.setattr(agent, "_check_economics_exists", lambda _: True)
    monkeypatch.setattr(
        agent,
        "_check_decision_cache",
        lambda street_id, context=None: (True, {"choice": "DH", "robust": True}),
    )
    monkeypatch.setattr(
        agent,
        "_load_decision_sidecars",
        lambda street_id: {
            "llm_explanation": "Old cached explanation.",
            "validation": {"validation_status": "pass"},
        },
    )

    call_kwargs = {}

    def fake_get_adk_agents() -> dict:
        class FakeDecisionADKAgent:
            def __init__(self, cluster_id: str, verbose: bool = False):
                self.cluster_id = cluster_id
                self.verbose = verbose

            def run(self, **kwargs):
                call_kwargs.update(kwargs)
                return SimpleNamespace(
                    status="success",
                    result={
                        "decision": {
                            "choice": "DH",
                            "recommendation": "DH",
                            "robust": True,
                            "reason_codes": ["COST_DOMINANT_DH"],
                            "metrics_used": {"lcoh_dh_median": 64.6},
                            "explanation_source": "gemini_api",
                            "explanation_model": "gemini-2.5-flash",
                        },
                        "explanation": "Validated explanation.",
                        "validation": {
                            "validation_status": "pass",
                            "verified_count": 3,
                            "statements_validated": 3,
                        },
                        "outputs": {},
                    },
                    timestamp="2026-04-29T00:00:00",
                    error=None,
                )

        return {"Decision": FakeDecisionADKAgent}

    monkeypatch.setattr(
        "branitz_heat_decision.agents.domain.base._get_adk_agents",
        fake_get_adk_agents,
    )

    result = agent.execute(
        cluster_id,
        context={
            "require_validated_explanation": True,
            "require_live_llm_explanation": True,
            "llm_explanation": True,
            "no_fallback": True,
        },
    )

    assert result.success is True
    assert result.cache_hit is False
    assert result.data["llm_explanation"] == "Validated explanation."
    assert result.data["explanation_source"] == "gemini_api"
    assert result.data["validation"]["validation_status"] == "pass"
    assert call_kwargs["llm_explanation"] is True
    assert call_kwargs["no_fallback"] is True


def test_explanation_requests_are_cache_first_unless_refresh_is_explicit(
    monkeypatch,
) -> None:
    executor = DynamicExecutor()
    captured_contexts = []

    monkeypatch.setattr(executor, "_ensure_agents", lambda: None)
    monkeypatch.setattr(
        executor,
        "_create_agent_plan",
        lambda intent, context: ["decision"],
    )

    def fake_run(plan, intent, street_id, context):
        captured_contexts.append(context)
        return {}, []

    monkeypatch.setattr(executor, "_run_agent_plan", fake_run)
    monkeypatch.setattr(
        executor,
        "_integrate_results",
        lambda results, intent, street_id: {},
    )

    executor.execute("EXPLAIN_DECISION", "ST_CACHE_FIRST")
    assert captured_contexts[-1]["require_validated_explanation"] is True
    assert captured_contexts[-1]["llm_explanation"] is True
    assert captured_contexts[-1]["require_live_llm_explanation"] is False

    executor.execute(
        "EXPLAIN_DECISION",
        "ST_CACHE_FIRST",
        context={"require_live_llm_explanation": True},
    )
    assert captured_contexts[-1]["require_live_llm_explanation"] is True


def test_validated_explanation_sidecars_are_reused_without_calling_gemini(
    monkeypatch, tmp_path: Path
) -> None:
    cluster_id = "ST_CACHED_EXPLANATION"

    def fake_resolve_cluster_path(street_id: str, phase: str) -> Path:
        path = tmp_path / phase / street_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(
        "branitz_heat_decision.config.resolve_cluster_path",
        fake_resolve_cluster_path,
    )

    agent = DecisionAgent()
    monkeypatch.setattr(agent, "_check_economics_exists", lambda _: True)
    monkeypatch.setattr(
        agent,
        "_check_decision_cache",
        lambda street_id, context=None: (
            True,
            {
                "choice": "DH",
                "robust": True,
                "explanation_source": "gemini_api",
                "explanation_model": "gemini-2.5-flash",
            },
        ),
    )
    monkeypatch.setattr(
        agent,
        "_load_decision_sidecars",
        lambda street_id: {
            "llm_explanation": "Cached validated Gemini explanation.",
            "validation": {
                "validation_status": "pass",
                "contradiction_count": 0,
            },
        },
    )
    monkeypatch.setattr(
        "branitz_heat_decision.agents.domain.base._get_adk_agents",
        lambda: (_ for _ in ()).throw(AssertionError("Gemini path must not run")),
    )

    result = agent.execute(
        cluster_id,
        context={
            "require_validated_explanation": True,
            "require_live_llm_explanation": False,
            "llm_explanation": True,
        },
    )

    assert result.success is True
    assert result.cache_hit is True
    assert result.data["llm_explanation"] == "Cached validated Gemini explanation."
    assert result.data["explanation_source"] == "gemini_api"


def test_ordinary_cached_decision_does_not_attach_explanation_sidecars(
    monkeypatch, tmp_path: Path
) -> None:
    cluster_id = "ST_TEST_BASELINE_DECISION"

    def fake_resolve_cluster_path(street_id: str, phase: str) -> Path:
        path = tmp_path / phase / street_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(
        "branitz_heat_decision.config.resolve_cluster_path",
        fake_resolve_cluster_path,
    )

    agent = DecisionAgent()
    monkeypatch.setattr(agent, "_check_economics_exists", lambda _: True)
    monkeypatch.setattr(
        agent,
        "_check_decision_cache",
        lambda street_id, context=None: (
            True,
            {
                "choice": "DH",
                "robust": True,
                "reason_codes": ["ONLY_DH_FEASIBLE"],
            },
        ),
    )
    monkeypatch.setattr(
        agent,
        "_load_decision_sidecars",
        lambda street_id: {
            "llm_explanation": "Stale reinforced explanation.",
            "validation": {"validation_status": "pass"},
        },
    )

    result = agent.execute(cluster_id, context={"llm_explanation": False})

    assert result.success is True
    assert result.cache_hit is True
    assert result.data["decision"]["reason_codes"] == ["ONLY_DH_FEASIBLE"]
    assert result.data["llm_explanation"] is None
    assert result.data["validation"] is None


def test_explanation_must_match_current_contract(monkeypatch, tmp_path: Path) -> None:
    cluster_id = "ST_TEST_EXPLANATION_PROVENANCE"

    def fake_resolve_cluster_path(street_id: str, phase: str) -> Path:
        path = tmp_path / phase / street_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(
        "branitz_heat_decision.agents.answer_formatting.resolve_cluster_path",
        fake_resolve_cluster_path,
    )
    decision_dir = fake_resolve_cluster_path(cluster_id, "decision")
    contract = {"cluster_id": cluster_id, "heat_pumps": {"feasible": False}}
    (decision_dir / f"kpi_contract_{cluster_id}.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )
    (decision_dir / f"decision_{cluster_id}.json").write_text(
        json.dumps({"choice": "DH", "reason_codes": ["ONLY_DH_FEASIBLE"]}),
        encoding="utf-8",
    )
    (decision_dir / f"explanation_{cluster_id}.md").write_text(
        "Stale explanation says both feasible.", encoding="utf-8"
    )
    (decision_dir / f"validation_{cluster_id}.json").write_text(
        json.dumps({"validation_status": "pass"}), encoding="utf-8"
    )

    stale_data = {"llm_explanation": "Stale explanation says both feasible."}
    enrich_decision_data(stale_data, {"entities": {"street_name": cluster_id}})
    assert "llm_explanation" not in stale_data
    assert "validation" not in stale_data

    digest = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (decision_dir / f"explanation_{cluster_id}_metadata.json").write_text(
        json.dumps({"contract_sha256": digest}), encoding="utf-8"
    )
    current_data = {}
    enrich_decision_data(current_data, {"entities": {"street_name": cluster_id}})
    assert "Stale explanation" in current_data["llm_explanation"]
    assert current_data["validation"]["validation_status"] == "pass"


def test_rejection_audit_lists_all_test_injections_and_infrastructure_reasons() -> None:
    audit = build_rejection_audit(
        {
            "validation_status": "pass",
            "statements_validated": 4,
            "verified_count": 4,
            "contradiction_count": 0,
            "contradictions": [],
        }
    )
    adversarial = audit["global_adversarial_benchmark"]
    assert adversarial["street_specific"] is False
    assert adversarial["total"] == 20
    assert adversarial["blocked"] == 20
    assert len(adversarial["cases"]) == 20
    detector_counts = {}
    for case in adversarial["cases"]:
        detector_counts[case["detector"]] = detector_counts.get(case["detector"], 0) + 1
        assert case["reason"]
    assert detector_counts == {
        "ClaimExtractor": 9,
        "TNLI": 11,
    }

    infrastructure = audit["unsupported_infrastructure_changes"]
    assert infrastructure["policy"] == "refused"
    assert len(infrastructure["cases"]) == 4
    assert all(case["reason"] and case["required_step"] for case in infrastructure["cases"])


def test_decision_validation_audits_the_actual_generated_sentences() -> None:
    report = LogicAuditor().validate_decision_explanation(
        {
            "choice": "DH",
            "reason_codes": ["ONLY_DH_FEASIBLE", "ROBUST_DECISION"],
            "robust": True,
            "cluster_id": "ST_LIVE_AUDIT",
            "kpis": {
                "lcoh_dh_median": 80.0,
                "lcoh_hp_median": 120.0,
                "dh_wins_fraction": 0.9,
                "hp_wins_fraction": 0.1,
            },
            "explanation": (
                "District heating is the recommended choice. "
                "Heat pumps are feasible on the current grid. "
                "Heat pumps are not feasible without grid reinforcement."
            ),
        }
    ).to_dict()

    generated = report["evidence"]["generated_explanation_audit"]
    assert generated["scope"] == "actual_generated_text"
    assert len(generated["sentence_results"]) == 3
    assert generated["sentence_results"][0]["status"] == "ENTAILMENT"
    assert generated["sentence_results"][1]["status"] == "CONTRADICTION"
    assert generated["sentence_results"][2]["status"] == "ENTAILMENT"
    assert report["validation_status"] == "fail"

    audit = build_rejection_audit(report)
    live = audit["current_explanation"]
    assert live["scope"] == "actual_generated_text"
    assert live["statements_checked"] == 3
    assert live["verified"] == 2
    assert live["rejected"] == 1
    assert live["statements"][1]["status"] == "rejected"


def test_selected_street_audit_is_not_the_fixed_twenty_case_benchmark() -> None:
    first = build_rejection_audit(
        {
            "validation_status": "pass",
            "evidence": {
                "generated_explanation_audit": {
                    "validation_status": "pass",
                    "sentence_results": [
                        {
                            "statement": "DH is recommended.",
                            "status": "ENTAILMENT",
                            "confidence": 0.95,
                            "evidence": "Recommendation is DH",
                        }
                    ],
                    "contradictions": [],
                }
            },
        }
    )
    second = build_rejection_audit(
        {
            "validation_status": "pass",
            "evidence": {
                "generated_explanation_audit": {
                    "validation_status": "pass",
                    "sentence_results": [
                        {
                            "statement": "HP is recommended.",
                            "status": "ENTAILMENT",
                            "confidence": 0.95,
                            "evidence": "Recommendation is HP",
                        },
                        {
                            "statement": "Both options are feasible.",
                            "status": "NEUTRAL",
                            "confidence": 0.5,
                            "evidence": "Not enough evidence",
                        },
                    ],
                    "contradictions": [],
                }
            },
        }
    )

    assert first["current_explanation"]["statements_checked"] == 1
    assert second["current_explanation"]["statements_checked"] == 2
    assert first["global_adversarial_benchmark"]["total"] == 20
    assert second["global_adversarial_benchmark"]["total"] == 20


def test_unverifiable_generated_sentence_is_withheld_fail_closed() -> None:
    report = LogicAuditor().validate_decision_explanation(
        {
            "choice": "DH",
            "reason_codes": ["COST_DOMINANT_DH"],
            "cluster_id": "ST_UNKNOWN_PROSE",
            "kpis": {
                "lcoh_dh_median": 80.0,
                "lcoh_hp_median": 120.0,
            },
            "explanation": "Construction will finish in 2027.",
        }
    ).to_dict()

    generated = report["evidence"]["generated_explanation_audit"]
    assert generated["sentence_results"][0]["status"] == "NEUTRAL"
    assert report["validation_status"] == "warning"


def test_uhdc_safety_parser_keeps_feasibility_subjects_within_sentence() -> None:
    contract = {
        "district_heating": {"feasible": True},
        "heat_pumps": {"feasible": False},
    }
    explanation = (
        "District heating is the only viable option for this area. "
        "Heat pumps are not feasible because the grid is overloaded. "
        "The heat-pump alternative, if it were feasible, would cost more."
    )

    auditor = UHDCSafetyAuditor(contract)
    is_valid, violations = auditor.validate_explanation(explanation)

    assert is_valid is True
    assert violations == []
    categorical = [
        (claim.subject, claim.value)
        for claim in auditor.extracted_claims
        if claim.claim_type.value == "categorical"
    ]
    assert ("district heating", "feasible") in categorical
    assert ("heat pumps", "infeasible") in categorical
    assert ("heat pumps", "feasible") not in categorical
