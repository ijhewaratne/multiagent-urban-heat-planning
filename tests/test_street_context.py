import json
from types import SimpleNamespace

import branitz_heat_decision.agents.orchestrator as orchestrator_module
import branitz_heat_decision.nlu.intent_classifier as intent_classifier_module
from branitz_heat_decision.agents.conversation import ConversationManager
from branitz_heat_decision.agents.executor import DynamicExecutor
from branitz_heat_decision.agents.orchestrator import BranitzOrchestrator
from branitz_heat_decision.agents.street_resolution import resolve_cluster


FIRST_STREET = "ST001_FIRST_STREET"
SECOND_STREET = "ST002_SECOND_STREET"


def test_selected_street_overrides_conversation_memory() -> None:
    resolved, method = resolve_cluster(
        raw_street_hint=None,
        user_query="Compare CO2 emissions",
        cluster_id=SECOND_STREET,
        memory_street=FIRST_STREET,
        context={},
    )

    assert resolved == SECOND_STREET
    assert method == "pre-validated (UI/API selection)"


def test_conversation_street_switch_discards_stale_calculation() -> None:
    conversation = ConversationManager()
    conversation.update_memory(
        intent="CO2_COMPARISON",
        street_id=FIRST_STREET,
        results={"dh_tons_co2": 10.0, "hp_tons_co2": 20.0},
        execution_log=[],
    )

    conversation.set_current_street(SECOND_STREET)

    assert conversation.memory.current_street == SECOND_STREET
    assert conversation.memory.last_calculation is None
    assert conversation.memory.last_intent is None


def test_reference_resolution_does_not_mutate_classifier_entities() -> None:
    conversation = ConversationManager()
    conversation.set_current_street(FIRST_STREET)
    intent_data = {"intent": "LCOH_COMPARISON", "entities": {}}

    _, enriched, is_follow_up = conversation.resolve_references(
        "What about LCOH?",
        intent_data,
    )

    assert is_follow_up is True
    assert intent_data["entities"] == {}
    assert enriched["entities"]["street_name"] == FIRST_STREET


def test_orchestrator_routes_repeated_question_to_new_selection(monkeypatch) -> None:
    conversation = ConversationManager()
    conversation.update_memory(
        intent="CO2_COMPARISON",
        street_id=FIRST_STREET,
        results={"dh_tons_co2": 10.0, "hp_tons_co2": 20.0},
        execution_log=[],
    )

    executed = {}

    class FakeExecutor:
        def execute(self, intent, street_id, context):
            executed["street_id"] = street_id
            return {
                "dh_tons_co2": 5.0,
                "hp_tons_co2": 7.0,
                "winner": "DH",
                "execution_log": [],
                "agent_results": {},
            }

    class FakeGuardrail:
        def validate_request(self, intent, entities, user_query=""):
            return SimpleNamespace(
                can_handle=True,
                response_type="direct",
                category=SimpleNamespace(value="supported"),
                research_note=None,
            )

    monkeypatch.setattr(
        orchestrator_module,
        "_get_classify_intent",
        lambda: lambda *args, **kwargs: {
            "intent": "CO2_COMPARISON",
            "confidence": 1.0,
            "entities": {},
            "reasoning": "test",
        },
    )

    orchestrator = BranitzOrchestrator.__new__(BranitzOrchestrator)
    orchestrator._session_cache = {}
    orchestrator.executor = FakeExecutor()
    orchestrator.conversation = conversation
    orchestrator.capability_guardrail = FakeGuardrail()

    response = orchestrator.route_request(
        "Compare CO2 emissions",
        cluster_id=SECOND_STREET,
        context={"available_streets": [FIRST_STREET, SECOND_STREET]},
    )

    assert executed["street_id"] == SECOND_STREET
    assert response["intent_data"]["entities"]["street_name"] == SECOND_STREET
    assert orchestrator.conversation.memory.current_street == SECOND_STREET
    assert orchestrator.conversation.memory.last_calculation.street_id == SECOND_STREET


def test_network_design_loads_existing_maps_without_rerunning_cha(
    monkeypatch, tmp_path
) -> None:
    street_id = "ST002_NETWORK_MAP_TEST"

    def fake_resolve_cluster_path(cluster_id, phase):
        assert cluster_id == street_id
        path = tmp_path / phase / cluster_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(
        "branitz_heat_decision.config.resolve_cluster_path",
        fake_resolve_cluster_path,
    )

    cha_dir = fake_resolve_cluster_path(street_id, "cha")
    dha_dir = fake_resolve_cluster_path(street_id, "dha")
    (cha_dir / "cha_kpis.json").write_text(
        json.dumps({"topology": {"buildings_connected": 12}}),
        encoding="utf-8",
    )
    for filename in (
        "interactive_map.html",
        "interactive_map_temperature.html",
        "interactive_map_pressure.html",
    ):
        (cha_dir / filename).write_text("<html>map</html>", encoding="utf-8")
    (dha_dir / "hp_lv_map.html").write_text("<html>lv map</html>", encoding="utf-8")

    executor = DynamicExecutor()
    result = executor.execute(
        "NETWORK_DESIGN",
        street_id,
        context={"history": ["unrelated chat state"]},
    )

    assert "error" not in result
    assert set(result["map_paths"]) == {"velocity", "temperature", "pressure", "lv grid"}
    assert result["topology"]["buildings_connected"] == 12
    assert result["agent_results"]["network_artifacts"]["cache_hit"] is True
    assert executor._agents is None


def test_network_intent_uses_keyword_fallback_when_llm_fails(monkeypatch) -> None:
    monkeypatch.setattr(intent_classifier_module, "GENAI_AVAILABLE", True)

    def fail_llm(_query):
        raise RuntimeError("temporary API failure")

    monkeypatch.setattr(intent_classifier_module, "_call_genai_new_sdk", fail_llm)

    result = intent_classifier_module.classify_intent(
        "What about network design?",
        use_llm=True,
    )

    assert result["intent"] == "NETWORK_DESIGN"
    assert "Keyword fallback" in result["reasoning"]
