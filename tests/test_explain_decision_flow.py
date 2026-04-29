from pathlib import Path
from types import SimpleNamespace

from branitz_heat_decision.agents.domain_agents import DecisionAgent
from branitz_heat_decision.agents.executor import DynamicExecutor


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
    assert formatted["validation"]["validation_status"] == "pass"

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


def test_decision_agent_regenerates_when_validated_explanation_is_required(
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
        lambda street_id: {"llm_explanation": None, "validation": None},
    )

    def fake_get_adk_agents() -> dict:
        class FakeDecisionADKAgent:
            def __init__(self, cluster_id: str, verbose: bool = False):
                self.cluster_id = cluster_id
                self.verbose = verbose

            def run(self, **kwargs):
                return SimpleNamespace(
                    status="success",
                    result={
                        "decision": {
                            "choice": "DH",
                            "recommendation": "DH",
                            "robust": True,
                            "reason_codes": ["COST_DOMINANT_DH"],
                            "metrics_used": {"lcoh_dh_median": 64.6},
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
        "branitz_heat_decision.agents.domain_agents._get_adk_agents",
        fake_get_adk_agents,
    )

    result = agent.execute(
        cluster_id,
        context={"require_validated_explanation": True},
    )

    assert result.success is True
    assert result.cache_hit is False
    assert result.data["llm_explanation"] == "Validated explanation."
    assert result.data["validation"]["validation_status"] == "pass"
