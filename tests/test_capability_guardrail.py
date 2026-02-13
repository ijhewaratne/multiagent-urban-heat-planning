"""
Tests for Phase 5: "I Don't Know" Implementation

Verifies the CapabilityGuardrail correctly identifies supported,
unsupported, and partially supported operations, and provides
research-context fallbacks.
"""

import sys
from pathlib import Path

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from branitz_heat_decision.agents.fallback import (
    CapabilityCategory,
    CapabilityGuardrail,
    CapabilityResponse,
)


@pytest.fixture
def guardrail():
    return CapabilityGuardrail()


# ── Unsupported intents ──


def test_unsupported_intent_add_consumer(guardrail):
    """System must admit it cannot add consumers."""
    response = guardrail.validate_request("add_consumer", {})

    assert response.can_handle is False
    assert "cannot" in response.message.lower()
    assert len(response.alternative_suggestions) > 0
    assert response.category == CapabilityCategory.UNSUPPORTED


def test_unsupported_intent_remove_pipe(guardrail):
    """System must admit it cannot remove pipes."""
    response = guardrail.validate_request("remove_pipe", {})

    assert response.can_handle is False
    assert response.category == CapabilityCategory.UNSUPPORTED
    assert response.escalation_path == "manual_planning"


def test_unsupported_intent_real_time_scada(guardrail):
    """System must admit it has no real-time data."""
    response = guardrail.validate_request("real_time_scada", {})

    assert response.can_handle is False
    assert "SCADA" in response.research_note or "real-time" in response.research_note.lower()


def test_unsupported_intent_legal_compliance(guardrail):
    """System must not give legal advice."""
    response = guardrail.validate_request("legal_compliance_check", {})

    assert response.can_handle is False
    assert response.category == CapabilityCategory.UNSUPPORTED


def test_unsupported_intent_multi_street(guardrail):
    """Multi-street optimization is a future feature."""
    response = guardrail.validate_request("multi_street_optimization", {})

    assert response.can_handle is False
    assert response.category == CapabilityCategory.FUTURE


# ── Supported intents ──


def test_supported_intent_co2_comparison(guardrail):
    """System should handle CO2 comparison."""
    response = guardrail.validate_request("CO2_COMPARISON", {})

    assert response.can_handle is True
    assert response.response_type == "direct"


def test_supported_intent_lcoh_comparison(guardrail):
    """System should handle LCOH comparison."""
    response = guardrail.validate_request("LCOH_COMPARISON", {})

    assert response.can_handle is True


def test_supported_intent_violation_analysis(guardrail):
    """System should handle violation analysis."""
    response = guardrail.validate_request("VIOLATION_ANALYSIS", {})

    assert response.can_handle is True


def test_supported_intent_network_design(guardrail):
    """System should handle network design / map requests."""
    response = guardrail.validate_request("NETWORK_DESIGN", {})

    assert response.can_handle is True


def test_supported_intent_explain_decision(guardrail):
    """System should handle decision explanations."""
    response = guardrail.validate_request("EXPLAIN_DECISION", {})

    assert response.can_handle is True


# ── Partial capabilities (what-if) ──


def test_what_if_valid_remove_houses(guardrail):
    """What-if with house removal should be accepted."""
    response = guardrail.validate_request(
        "WHAT_IF_SCENARIO", {"modification": "remove 2 houses"}
    )

    assert response.can_handle is True


def test_what_if_valid_remove_buildings(guardrail):
    """What-if with building removal should also be accepted."""
    response = guardrail.validate_request(
        "WHAT_IF_SCENARIO", {"modification": "exclude 3 buildings"}
    )

    assert response.can_handle is True


def test_what_if_invalid_change_pipe(guardrail):
    """What-if with unsupported modification should be rejected."""
    response = guardrail.validate_request(
        "WHAT_IF_SCENARIO", {"modification": "change pipe material to steel"}
    )

    assert response.can_handle is False
    assert response.response_type == "clarification"
    assert response.category == CapabilityCategory.PARTIAL


def test_what_if_invalid_change_temperature(guardrail):
    """What-if with temperature change should be rejected."""
    response = guardrail.validate_request(
        "WHAT_IF_SCENARIO", {"modification": "increase supply temperature to 90C"}
    )

    assert response.can_handle is False


# ── Keyword detection ──


def test_keyword_detection_add_consumer(guardrail):
    """Keyword 'add a consumer' in query should trigger guardrail."""
    response = guardrail.validate_request(
        "UNKNOWN", {}, user_query="Can you add a consumer to the network?"
    )

    assert response.can_handle is False
    assert "topology" in response.message.lower() or "cannot" in response.message.lower()


def test_keyword_detection_scada(guardrail):
    """Keyword 'real-time' in query should trigger guardrail."""
    response = guardrail.validate_request(
        "UNKNOWN", {}, user_query="Show me real-time SCADA data"
    )

    assert response.can_handle is False


def test_keyword_detection_legal(guardrail):
    """Keyword 'legal' in query should trigger guardrail."""
    response = guardrail.validate_request(
        "UNKNOWN", {}, user_query="Is this setup compliant with legal regulations?"
    )

    assert response.can_handle is False


def test_keyword_no_false_positive(guardrail):
    """Normal queries should not be blocked by keyword detection."""
    response = guardrail.validate_request(
        "CO2_COMPARISON", {}, user_query="Compare CO2 for Heinrich-Zille-Straße"
    )

    assert response.can_handle is True


# ── Research context ──


def test_fallback_has_research_note(guardrail):
    """Fallback responses should include research notes for thesis."""
    response = guardrail.validate_request("real_time_scada", {})

    assert response.research_note is not None
    assert len(response.research_note) > 0


def test_fallback_has_alternatives(guardrail):
    """Fallback responses should suggest alternatives."""
    response = guardrail.validate_request("add_consumer", {})

    assert len(response.alternative_suggestions) >= 2


def test_fallback_has_escalation_path(guardrail):
    """Unsupported intents should have an escalation path."""
    response = guardrail.validate_request("remove_pipe", {})

    assert response.escalation_path is not None


# ── Capabilities summary ──


def test_capabilities_summary_structure(guardrail):
    """Capabilities summary should have all required sections."""
    caps = guardrail.get_capabilities_summary()

    assert "fully_supported" in caps
    assert "partially_supported" in caps
    assert "not_supported" in caps
    assert "research_objectives" in caps

    assert len(caps["fully_supported"]) > 0
    assert len(caps["not_supported"]) > 0


def test_capabilities_summary_content(guardrail):
    """Capabilities summary should list known features."""
    caps = guardrail.get_capabilities_summary()

    supported_text = " ".join(caps["fully_supported"]).lower()
    assert "co2" in supported_text or "emissions" in supported_text
    assert "lcoh" in supported_text or "cost" in supported_text
    assert "map" in supported_text or "network" in supported_text
