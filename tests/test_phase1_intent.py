"""
Phase 1 Intent Classifier Tests.

Validates intent classification before moving to Phase 2.
Uses classify_intent() (no LLM required for keyword fallback).
Run with: PYTHONPATH=src pytest tests/test_phase1_intent.py -v
"""

import os
import pytest

from branitz_heat_decision.nlu.intent_classifier import classify_intent


# Test cases: (query, expected_intent) - keyword fallback works without LLM
TEST_CASES = [
    ("Compare CO2 emissions", "CO2_COMPARISON"),
    ("What is the carbon footprint?", "CO2_COMPARISON"),  # Semantic: carbon -> CO2
    ("How much does it cost?", "LCOH_COMPARISON"),
    ("What if we remove 2 houses?", "WHAT_IF_SCENARIO"),
    ("Add a new consumer", "UNKNOWN"),  # Should trigger fallback
    ("What if we use fewer buildings?", "WHAT_IF_SCENARIO"),  # what-if
    ("Why was DH chosen?", "EXPLAIN_DECISION"),
    ("Check velocity violations", "VIOLATION_ANALYSIS"),
    ("Show pipe layout", "NETWORK_DESIGN"),
    ("What can you do?", "CAPABILITY_QUERY"),
]


def test_intent_keyword_fallback():
    """Without LLM, keyword fallback must return expected intents."""
    for query, expected in TEST_CASES:
        result = classify_intent(query, use_llm=False)
        assert "intent" in result
        assert "confidence" in result
        assert "reasoning" in result
        # Normalize for comparison (e.g. CO2_COMPARISON vs co2_comparison)
        got = str(result["intent"]).upper().replace(" ", "_")
        exp = str(expected).upper().replace(" ", "_")
        assert got == exp, f"Query: '{query}' expected {exp}, got {got}"


def test_intent_structure():
    """Result must have required keys."""
    result = classify_intent("Compare CO2", use_llm=False)
    assert "intent" in result
    assert "confidence" in result
    assert "entities" in result
    assert "reasoning" in result
    assert 0 <= result["confidence"] <= 1


def test_empty_query():
    """Empty query -> UNKNOWN."""
    result = classify_intent("", use_llm=False)
    assert result["intent"] == "UNKNOWN"
    assert result["confidence"] == 0


@pytest.mark.integration
def test_intent_with_llm():
    """With LLM, classification may differ; must return valid structure."""
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")
    result = classify_intent("Compare CO2 emissions", use_llm=True)
    assert "intent" in result
    assert result["intent"] in (
        "CO2_COMPARISON",
        "LCOH_COMPARISON",
        "VIOLATION_ANALYSIS",
        "NETWORK_DESIGN",
        "WHAT_IF_SCENARIO",
        "EXPLAIN_DECISION",
        "CAPABILITY_QUERY",
        "UNKNOWN",
    )
    assert 0 <= result["confidence"] <= 1


def test_intent_understanding_script():
    """Script-style test: print results for manual inspection."""
    for query, expected in TEST_CASES[:5]:  # First 5 for brevity
        result = classify_intent(query, use_llm=False)
        got = str(result["intent"]).upper().replace(" ", "_")
        exp = str(expected).upper().replace(" ", "_")
        status = "✓" if got == exp else "✗"
        print(f"{status} Query: '{query}'")
        print(f"  Expected: {exp}, Got: {got}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Reasoning: {result['reasoning']}")
        print("---")


if __name__ == "__main__":
    print("Phase 1 Intent Classifier Test (keyword fallback)\n")
    test_intent_understanding_script()
    print("\nRunning pytest...")
    pytest.main([__file__, "-v", "-k", "not integration"])
