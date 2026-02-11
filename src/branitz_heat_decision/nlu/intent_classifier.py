"""
Intent Classifier for Branitz Heat Decision System.

Replaces keyword matching with semantic understanding to decide
WHICH simulations to run (CHA, DHA, Economics, Decision, UHDC).
"""

from enum import Enum
from typing import Any, Dict, List, Optional

import json
import logging
import os

logger = logging.getLogger(__name__)

# Try google-genai (uhdc/explainer style) first
try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

# Fallback: google.generativeai (ui/llm style)
if not GENAI_AVAILABLE:
    try:
        import google.generativeai as genai_legacy  # noqa: F401

        GENAI_AVAILABLE = True
    except ImportError:
        GENAI_AVAILABLE = False


class BranitzIntent(Enum):
    """Explicit intents that map to simulation strategies."""

    CO2_COMPARISON = "co2_comparison"
    LCOH_COMPARISON = "lcoh_comparison"
    VIOLATION_ANALYSIS = "violation_analysis"
    NETWORK_DESIGN = "network_design"
    WHAT_IF_SCENARIO = "what_if_scenario"
    EXPLAIN_DECISION = "explain_decision"
    CAPABILITY_QUERY = "capability_query"
    UNKNOWN = "unknown"


CLASSIFIER_SYSTEM_PROMPT = """
You are an intent classifier for a District Heating vs Heat Pump decision system (Branitz).
Analyze the user query and determine their intent.

Available intents (return ONLY one):
- CO2_COMPARISON: User wants carbon emissions comparison (needs DH + HP simulations)
- LCOH_COMPARISON: User wants cost/LCOH analysis (needs DH + HP simulations)
- VIOLATION_ANALYSIS: User asks about pressure/velocity/temperature violations (needs DH sim only)
- NETWORK_DESIGN: User asks about pipe layout, diameters, network topology (needs DH sim only)
- WHAT_IF_SCENARIO: User asks hypotheticals: "what if we remove houses", "different temperatures"
- EXPLAIN_DECISION: User asks why a decision was made or wants KPI explanation (needs cached results only)
- CAPABILITY_QUERY: User asks "what can you do?", "help", capabilities
- UNKNOWN: Outside capabilities (adding consumers, changing building geometry, legal advice, etc.)

Return STRICTLY this JSON (no other text):
{"intent": "ONE_OF_ABOVE", "confidence": 0.0_to_1.0, "entities": {"street_name": null, "metric": "co2|lcoh|pressure|velocity|etc", "modification": "what-if desc or null"}, "reasoning": "brief why"}

Examples:
"Compare CO2" -> {"intent": "CO2_COMPARISON", "confidence": 0.95, "entities": {"metric": "co2"}, "reasoning": "..."}
"What if we remove 2 houses?" -> {"intent": "WHAT_IF_SCENARIO", "entities": {"modification": "remove 2 houses"}, ...}
"Add a new consumer" -> {"intent": "UNKNOWN", "confidence": 0.9, "reasoning": "Cannot modify network topology"}
"""

VALID_INTENTS = {e.value.upper().replace(" ", "_") for e in BranitzIntent}


def _call_genai_new_sdk(user_query: str) -> str:
    """Call Gemini via google.genai (new SDK)."""
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key or key in ("", "YOUR_ACTUAL_API_KEY_HERE"):
        raise RuntimeError("GOOGLE_API_KEY not set")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=500)
    resp = client.models.generate_content(
        model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
        contents=f"{CLASSIFIER_SYSTEM_PROMPT}\n\nUser: {user_query}",
        config=cfg,
    )
    return resp.text if hasattr(resp, "text") else str(resp)


def _call_genai_legacy(user_query: str) -> str:
    """Call Gemini via google.generativeai (legacy SDK)."""
    import google.generativeai as genai

    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        f"{CLASSIFIER_SYSTEM_PROMPT}\n\nUser: {user_query}"
    )
    return response.text


def _parse_json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON from model output (handles markdown code blocks)."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    text = text.strip()
    return json.loads(text)


def classify_intent(
    user_query: str,
    conversation_history: Optional[List[str]] = None,
    use_llm: bool = True,
    confidence_threshold: float = 0.7,
) -> Dict[str, Any]:
    """
    Classify user query into BranitzIntent.

    Returns:
        {
            "intent": "CO2_COMPARISON" | ...,
            "confidence": 0.0-1.0,
            "entities": {"street_name": ..., "metric": ..., "modification": ...},
            "reasoning": "..."
        }
    """
    if not user_query or not str(user_query).strip():
        return {
            "intent": "UNKNOWN",
            "confidence": 0.0,
            "entities": {},
            "reasoning": "Empty query",
        }

    if use_llm and GENAI_AVAILABLE:
        try:
            try:
                text = _call_genai_new_sdk(user_query)
            except (ImportError, AttributeError):
                text = _call_genai_legacy(user_query)

            result = _parse_json_from_text(text)
            result.setdefault("entities", {})
            intent_raw = str(result.get("intent", "UNKNOWN")).upper().replace(" ", "_")
            result["intent"] = (
                intent_raw if intent_raw in VALID_INTENTS else "UNKNOWN"
            )
            if result.get("confidence", 0) < confidence_threshold:
                result["intent"] = "UNKNOWN"
                result["reasoning"] = (
                    str(result.get("reasoning", "")) + " [Low confidence]"
                )
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Intent classifier: JSON parse error: {e}")
            return {
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "entities": {},
                "reasoning": "Failed to parse classifier output",
            }
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")
            return {
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "entities": {},
                "reasoning": str(e),
            }

    # Non-LLM fallback: simple keyword heuristics
    q = user_query.lower()
    if any(w in q for w in ["co2", "carbon", "emission", "emissions"]):
        return {
            "intent": "CO2_COMPARISON",
            "confidence": 0.6,
            "entities": {"metric": "co2"},
            "reasoning": "Keyword fallback",
        }
    if any(w in q for w in ["cost", "lcoh", "price", "money", "expensive"]):
        return {
            "intent": "LCOH_COMPARISON",
            "confidence": 0.6,
            "entities": {"metric": "lcoh"},
            "reasoning": "Keyword fallback",
        }
    if any(w in q for w in ["violation", "pressure", "velocity", "limit"]):
        return {
            "intent": "VIOLATION_ANALYSIS",
            "confidence": 0.6,
            "entities": {},
            "reasoning": "Keyword fallback",
        }
    if any(w in q for w in ["network", "pipe", "layout", "topology", "diameter"]):
        return {
            "intent": "NETWORK_DESIGN",
            "confidence": 0.6,
            "entities": {},
            "reasoning": "Keyword fallback",
        }
    if any(w in q for w in ["what if", "what if we", "hypothetical"]):
        return {
            "intent": "WHAT_IF_SCENARIO",
            "confidence": 0.6,
            "entities": {"modification": user_query[:80]},
            "reasoning": "Keyword fallback",
        }
    if any(w in q for w in ["explain", "why", "decision", "recommend"]):
        return {
            "intent": "EXPLAIN_DECISION",
            "confidence": 0.6,
            "entities": {},
            "reasoning": "Keyword fallback",
        }
    if any(w in q for w in ["help", "what can you", "capabilities"]):
        return {
            "intent": "CAPABILITY_QUERY",
            "confidence": 0.8,
            "entities": {},
            "reasoning": "Keyword fallback",
        }

    return {
        "intent": "UNKNOWN",
        "confidence": 0.0,
        "entities": {},
        "reasoning": "No match",
    }
