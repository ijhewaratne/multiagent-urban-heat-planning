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
- NETWORK_DESIGN: User asks about pipe layout, diameters, network topology, interactive maps, grid layout, show the network, see the map, heating grid, how many buildings/houses, building count, network statistics (needs DH sim only)
- WHAT_IF_SCENARIO: User asks hypotheticals: "what if we remove houses", "different temperatures"
- EXPLAIN_DECISION: User asks why a decision was made, wants KPI explanation, asks "what is recommended", "what's the recommendation", or asks for decision summary (needs cached results only)
- CAPABILITY_QUERY: User asks "what can you do?", "help", capabilities, OR asks "what streets", "which streets are available", "list the streets", "how many streets" (ONLY when the user is explicitly asking about system capabilities or available data, NOT when they want to see specific data or maps)
- UNKNOWN: Outside capabilities (adding consumers, changing building geometry, legal advice, etc.)

IMPORTANT: If the user asks to "see", "show", or "view" something specific (maps, network, grid, layout, results), classify based on WHAT they want to see, NOT as CAPABILITY_QUERY.

Return STRICTLY this JSON (no other text):
{"intent": "ONE_OF_ABOVE", "confidence": 0.0_to_1.0, "entities": {"street_name": null, "metric": "co2|lcoh|pressure|velocity|etc", "modification": "what-if desc or null"}, "reasoning": "brief why"}

Examples:
"Compare CO2" -> {"intent": "CO2_COMPARISON", "confidence": 0.95, "entities": {"metric": "co2"}, "reasoning": "..."}
"What if we remove 2 houses?" -> {"intent": "WHAT_IF_SCENARIO", "entities": {"modification": "remove 2 houses"}, ...}
"Can I see the interactive maps" -> {"intent": "NETWORK_DESIGN", "confidence": 0.9, "entities": {}, "reasoning": "User wants to view network maps"}
"Show me the heating grid layout" -> {"intent": "NETWORK_DESIGN", "confidence": 0.9, "entities": {}, "reasoning": "User wants network visualization"}
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

            # Safety net: if LLM returned UNKNOWN, try keyword fallback
            if result["intent"] == "UNKNOWN":
                keyword_result = _keyword_fallback(user_query)
                if keyword_result["intent"] != "UNKNOWN":
                    keyword_result["reasoning"] = (
                        f"LLM returned UNKNOWN ({result.get('reasoning', '')}); "
                        f"keyword override: {keyword_result['reasoning']}"
                    )
                    return keyword_result

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
    return _keyword_fallback(user_query)


def _keyword_fallback(user_query: str) -> Dict[str, Any]:
    """Keyword-based intent classification as fallback when LLM is unavailable or returns UNKNOWN."""
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
    if any(w in q for w in ["network", "pipe", "layout", "topology", "diameter",
                              "map", "grid", "interactive map", "heating grid",
                              "how many building", "how many house", "building count",
                              "number of building", "number of house"]):
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
    if any(w in q for w in ["which street", "what street", "list street", "available street",
                              "streets in the", "all streets", "show street",
                              "streets and", "street and house", "street and building"]):
        return {
            "intent": "CAPABILITY_QUERY",
            "confidence": 0.7,
            "entities": {"sub_query": "list_streets"},
            "reasoning": "Keyword fallback: street listing query",
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


def extract_street_entities(user_query: str, available_streets: List[str]) -> Optional[str]:
    """
    Extract street name from natural language query.
    Uses direct and fuzzy matching for flexibility.
    """
    import re
    from difflib import get_close_matches

    if not available_streets:
        return None

    query_lower = user_query.lower()
    query_clean = re.sub(
        r"\b(compare|show|analyze|calculate|what is|what are|the|for|in|on)\b",
        " ",
        query_lower,
        flags=re.IGNORECASE,
    )
    # Normalize German ß and Straße for matching
    query_clean = query_clean.replace("ß", "ss").replace("straße", "strasse")

    # Direct substring match (full cluster_id)
    for street in available_streets:
        street_clean = street.lower().replace("_", " ").replace("-", " ")
        if street_clean in query_clean or street.lower() in query_lower:
            return street

    # ST### pattern match
    st_match = re.search(r"ST\d{3}_[\w\-]+", user_query, re.I)
    if st_match:
        candidate = st_match.group(0)
        if candidate in available_streets:
            return candidate
        for s in available_streets:
            if s.upper().startswith(candidate.upper()[:10]):
                return s

    # Partial match (e.g. "Heinrich Zille" in "Heinrich-Zille-Straße")
    # Generic suffixes that appear in many street names should not count as matches
    _GENERIC_SUFFIXES = {
        "strasse", "str", "platz", "allee", "weg", "gasse", "ring", "damm",
        "siedlung", "park", "hof",
    }
    # Score each street by how many distinguishing parts match the query
    best_street = None
    best_score = 0
    for street in available_streets:
        street_parts = (
            street.lower()
            .replace("-", " ")
            .replace("_", " ")
            .replace("straße", "strasse")
            .split()
        )
        meaningful = [
            p for p in street_parts
            if len(p) > 2 and p not in ("st", "str") and p not in _GENERIC_SUFFIXES
            and not re.match(r"^st\d+$", p)  # exclude cluster prefix like "st010"
        ]
        matched = [p for p in meaningful if p in query_clean]
        if matched and len(matched) > best_score:
            best_score = len(matched)
            best_street = street
    if best_street:
        return best_street

    # Fuzzy matching for typos
    words = query_clean.split()
    for i in range(len(words)):
        for j in range(i + 1, min(i + 5, len(words) + 1)):
            phrase = " ".join(words[i:j])
            if len(phrase) < 4:
                continue
            matches = get_close_matches(
                phrase,
                [s.lower().replace("_", " ") for s in available_streets],
                n=1,
                cutoff=0.5,
            )
            if matches:
                for s in available_streets:
                    if s.lower().replace("_", " ") == matches[0]:
                        return s

    return None
