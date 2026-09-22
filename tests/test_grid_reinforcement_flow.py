import json

from branitz_heat_decision.agents.answer_formatting import format_executor_response
from branitz_heat_decision.agents.conversation import ConversationManager
from branitz_heat_decision.agents.executor import DynamicExecutor
from branitz_heat_decision.agents.domain.economics import EconomicsAgent
from branitz_heat_decision.decision.kpi_contract import _build_hp_block
from branitz_heat_decision.economics.lcoh import compute_lcoh_hp
from branitz_heat_decision.economics.params import get_default_economics_params
from branitz_heat_decision.nlu.intent_classifier import classify_intent


QUERY = (
    "Explain the LV-grid reinforcement required for the selected street. "
    "Show the violations, proposed reinforcement measures and costs, then "
    "recalculate HP feasibility, LCOH, and whether the DH-versus-HP decision changes"
)


def test_reinforcement_query_is_not_reduced_to_conversation_memory() -> None:
    intent = classify_intent(QUERY, use_llm=False)
    conversation = ConversationManager()
    conversation.memory.current_street = "ST010_TEST"

    assert intent["intent"] == "GRID_REINFORCEMENT"
    assert conversation.is_follow_up(QUERY) is False
    assert conversation.handle_follow_up(
        QUERY,
        intent["intent"],
        "ST010_TEST",
    ) is None
    assert classify_intent(
        "Explain the LV grid reinforment for this street",
        use_llm=False,
    )["intent"] == "GRID_REINFORCEMENT"


def test_reinforcement_response_reports_evidence_and_decision_impact(
    monkeypatch,
    tmp_path,
) -> None:
    street_id = "ST010_TEST"

    def fake_resolve_cluster_path(cluster_id, phase):
        assert cluster_id == street_id
        path = tmp_path / phase / cluster_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(
        "branitz_heat_decision.config.resolve_cluster_path",
        fake_resolve_cluster_path,
    )

    dha_dir = fake_resolve_cluster_path(street_id, "dha")
    econ_dir = fake_resolve_cluster_path(street_id, "economics")
    decision_dir = fake_resolve_cluster_path(street_id, "decision")
    reinforced_econ_dir = econ_dir / "reinforcement"
    reinforced_econ_dir.mkdir(parents=True, exist_ok=True)

    (dha_dir / "dha_kpis.json").write_text(
        json.dumps(
            {
                "feasible": False,
                "max_feeder_loading_pct": 201.5,
                "line_violations_total": 116,
                "voltage_violations_total": 0,
                "trafo_violations_total": 0,
                "line_overload_hours": 10,
                "hours_total": 10,
                "max_loading_line": "1449",
                "mitigations": {
                    "mitigation_class": "reinforcement",
                    "feasible_with_mitigation": True,
                    "recommendations": [
                        {
                            "title": "Line overload - cable capacity insufficient",
                            "actions": ["Upgrade to higher-capacity cable"],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    (econ_dir / "economics_deterministic.json").write_text(
        json.dumps(
            {
                "analysis_case": "baseline_current_grid",
                "lcoh_dh_eur_per_mwh": 62.0,
                "lcoh_hp_eur_per_mwh": 123.0,
                "lcoh_hp_breakdown": {"capex_lv_upgrade": 351_548.0},
            }
        ),
        encoding="utf-8",
    )
    (reinforced_econ_dir / "economics_deterministic.json").write_text(
        json.dumps(
            {
                "analysis_case": "verified_reinforcement",
                "lcoh_dh_eur_per_mwh": 62.0,
                "lcoh_hp_eur_per_mwh": 118.0,
                "lcoh_hp_breakdown": {"capex_lv_upgrade": 5_000.0},
            }
        ),
        encoding="utf-8",
    )
    (reinforced_econ_dir / "economics_monte_carlo.json").write_text(
        json.dumps(
            {
                "analysis_case": "verified_reinforcement",
                "monte_carlo": {"dh_wins_fraction": 1.0, "hp_wins_fraction": 0.0},
            }
        ),
        encoding="utf-8",
    )
    (dha_dir / "dha_reinforcement.json").write_text(
        json.dumps(
            {
                "is_sufficient": True,
                "remaining_violations": 0,
                "total_cost_eur": 5_000.0,
                "before_kpis": {
                    "feasible": False,
                    "max_feeder_loading_pct": 201.5,
                    "line_violations_total": 116,
                },
                "after_kpis": {
                    "feasible": True,
                    "max_feeder_loading_pct": 77.4,
                    "line_violations_total": 0,
                    "voltage_violations_total": 0,
                    "trafo_violations_total": 0,
                },
                "measures": [
                    {
                        "description": "Install parallel cable on line 1449",
                        "cost_eur": 5_000.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (decision_dir / f"decision_{street_id}.json").write_text(
        json.dumps(
            {
                "choice": "DH",
                "reason_codes": ["ONLY_DH_FEASIBLE"],
                "metrics_used": {
                    "lcoh_dh_median": 62.9,
                    "lcoh_hp_median": 123.7,
                    "dh_wins_fraction": 1.0,
                    "hp_wins_fraction": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    (decision_dir / f"kpi_contract_{street_id}.json").write_text(
        json.dumps(
            {
                "district_heating": {
                    "feasible": True,
                    "reasons": ["DH_OK"],
                    "lcoh": {"median": 62.9},
                    "co2": {"median": 1116.3},
                },
                "heat_pumps": {
                    "feasible": False,
                    "reasons": ["HP_OVERCURRENT_OR_OVERLOAD"],
                    "lcoh": {"median": 123.7},
                    "co2": {"median": 1006.8},
                },
                "monte_carlo": {
                    "dh_wins_fraction": 1.0,
                    "hp_wins_fraction": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    reinforced_decision = {
        "choice": "DH",
        "reason_codes": ["COST_DOMINANT_DH"],
        "metrics_used": {
            "lcoh_dh_median": 62.9,
            "lcoh_hp_median": 120.2,
            "dh_wins_fraction": 1.0,
            "hp_wins_fraction": 0.0,
        },
    }
    (decision_dir / f"decision_reinforced_{street_id}.json").write_text(
        json.dumps(reinforced_decision),
        encoding="utf-8",
    )
    (decision_dir / f"kpi_contract_reinforced_{street_id}.json").write_text(
        json.dumps({"metadata": {"analysis_case": "verified_reinforcement"}}),
        encoding="utf-8",
    )
    (decision_dir / "reinforcement_before_after.json").write_text(
        json.dumps(
            {
                "before_reinforcement": {
                    "decision": {
                        "choice": "DH",
                        "reason_codes": ["ONLY_DH_FEASIBLE"],
                    }
                },
                "after_reinforcement": {"decision": reinforced_decision},
                "decision_changes": False,
            }
        ),
        encoding="utf-8",
    )
    for phase_dir, duration in (
        (dha_dir, 1.0),
        (econ_dir, 2.0),
        (decision_dir, 3.0),
    ):
        (phase_dir / "_cache_manifest.json").write_text(
            json.dumps(
                {
                    "cache_schema_version": 2,
                    "input_hash": "test",
                    "calculation_duration_seconds": duration,
                    "calculated_at_utc": "2026-08-23T12:00:00Z",
                }
            ),
            encoding="utf-8",
        )

    intent_data = {
        "intent": "GRID_REINFORCEMENT",
        "entities": {"street_name": street_id},
    }
    result = DynamicExecutor().execute("GRID_REINFORCEMENT", street_id)
    response = format_executor_response(
        "GRID_REINFORCEMENT",
        intent_data,
        result,
    )

    assert result["current_grid"]["line_violations_total"] == 116
    assert result["reinforcement"]["cost_eur"] == 5_000.0
    assert result["reinforcement"]["cost_is_estimate"] is False
    assert result["post_reinforcement_grid"]["line_violations_total"] == 0
    assert result["decision_impact"]["post_reinforcement_feasibility_is_assumption"] is False
    assert result["decision_impact"]["counterfactual_choice"] == "DH"
    assert result["decision_impact"]["decision_changes"] is False
    assert "No, the decision remains DH" in response["answer"]
    assert "Retrieved from conversation memory" not in response["answer"]
    assert "original calculation 6.0s" in result["execution_log"][0]


def test_baseline_contract_ignores_nested_reinforcement_evidence() -> None:
    dha = {
        "feasible": False,
        "max_feeder_loading_pct": 201.5,
        "line_violations_total": 116,
        "voltage_violations_total": 0,
        "reinforcement": {
            "is_sufficient": True,
            "post_reinforcement_kpis": {
                "feasible": True,
                "max_feeder_loading_pct": 77.4,
                "line_violations_total": 0,
                "voltage_violations_total": 0,
                "planning_warnings_total": 0,
            },
        },
    }
    economics = {
        "lcoh_dh_eur_per_mwh": 62.0,
        "lcoh_hp_eur_per_mwh": 118.0,
        "co2_dh_t_per_a": 100.0,
        "co2_hp_t_per_a": 90.0,
    }
    hp_block = _build_hp_block("ST010_TEST", dha, economics)

    assert hp_block["feasible"] is False
    assert hp_block["reasons"] == ["HP_OVERCURRENT_OR_OVERLOAD"]
    assert hp_block["lv_grid"]["max_feeder_loading_pct"] == 201.5
    assert hp_block["lv_grid"]["line_violations_total"] == 116

    value, breakdown = compute_lcoh_hp(
        annual_heat_mwh=1_000.0,
        hp_total_capacity_kw_th=500.0,
        cop_annual_average=2.8,
        max_feeder_loading_pct=77.4,
        params=get_default_economics_params(),
        lv_reinforcement_cost_eur=6_633.96,
    )
    assert value > 0
    assert breakdown["capex_lv_upgrade"] == 6_633.96
    assert breakdown["lv_upgrade_cost_source"] == "verified_reinforcement_plan"


def test_cache_key_ignores_chat_context_but_keeps_model_inputs() -> None:
    agent = EconomicsAgent()
    first = agent._compute_cache_key(
        {"history": ["first question"], "requested_intent": "LCOH_COMPARISON", "seed": 42}
    )
    second = agent._compute_cache_key(
        {"history": ["different question"], "requested_intent": "CO2_COMPARISON", "seed": 42}
    )
    changed_model_input = agent._compute_cache_key({"seed": 7})

    assert first == second
    assert first != changed_model_input


def test_legacy_cache_is_adopted_without_rerunning_completed_results(tmp_path) -> None:
    manifest_path = tmp_path / "_cache_manifest.json"
    manifest_path.write_text(json.dumps({"input_hash": "same"}), encoding="utf-8")
    (tmp_path / "completed_result.json").write_text("{}", encoding="utf-8")

    assert EconomicsAgent._manifest_matches(
        {"input_hash": "same"},
        "same",
        manifest_path,
    ) is True
    adopted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert adopted["cache_schema_version"] == 2
    assert adopted["input_hash"] == "same"
    assert adopted["legacy_cache_adopted"] is True
