"""
Capability Guardrail & Fallback Agent for Branitz Heat Decision AI

Implements Speaker B's critical requirement:
"He needs to say 'no, I don't know exactly' instead of going crazy"

Phase 5: Explicit capability boundaries, graceful degradation,
and research-aware limitation documentation.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CapabilityCategory(Enum):
    """Categories of system capabilities."""

    SUPPORTED = "supported"        # Fully implemented
    PARTIAL = "partial"            # Limited implementation
    UNSUPPORTED = "unsupported"    # Explicitly not supported (research boundary)
    FUTURE = "future"              # Planned but not implemented


@dataclass
class CapabilityResponse:
    """Structured response for capability queries."""

    can_handle: bool
    response_type: str  # "direct", "fallback", "clarification", "alternative"
    message: str
    alternative_suggestions: List[str] = field(default_factory=list)
    escalation_path: Optional[str] = None
    category: Optional[CapabilityCategory] = None
    research_note: Optional[str] = None


class CapabilityGuardrail:
    """
    Central guardrail for system capabilities.

    Speaker B: "He needs to say 'no, I don't know exactly'"

    This class:
    1. Defines explicit boundaries of what the system CANNOT do
    2. Provides graceful fallbacks with alternative suggestions
    3. Documents limitations as research objectives (not bugs)
    4. Prevents hallucination by blocking unsupported intents
    """

    # Explicitly unsupported operations (research boundaries)
    UNSUPPORTED_INTENTS: Dict[str, Dict[str, Any]] = {
        "add_consumer": {
            "reason": "Network topology modification not supported",
            "research_note": "Adding consumers requires network redesign algorithms not in scope",
            "alternative": "Analyze existing network capacity",
            "category": CapabilityCategory.UNSUPPORTED,
        },
        "remove_pipe": {
            "reason": "Cannot modify existing infrastructure",
            "research_note": "Infrastructure modification is municipal planner's decision, not AI",
            "alternative": "Run what-if scenario with modified network",
            "category": CapabilityCategory.UNSUPPORTED,
        },
        "change_building_geometry": {
            "reason": "Building data is read-only from OSM",
            "research_note": "OSM data is static input, not modifiable within session",
            "alternative": "Analyze current building configuration",
            "category": CapabilityCategory.UNSUPPORTED,
        },
        "real_time_scada": {
            "reason": "No real-time data connection",
            "research_note": "System uses annual design load profiles, not real-time SCADA",
            "alternative": "Use design-hour simulation",
            "category": CapabilityCategory.UNSUPPORTED,
        },
        "legal_compliance_check": {
            "reason": "Legal interpretation not within AI scope",
            "research_note": "EN 13941-1 compliance is simulation target, not legal advice",
            "alternative": "Show technical compliance metrics",
            "category": CapabilityCategory.UNSUPPORTED,
        },
        "change_ownership": {
            "reason": "Economic ownership models not implemented",
            "research_note": "LCOH calculation uses standard utility economics only",
            "alternative": "Compare LCOH between DH and HP",
            "category": CapabilityCategory.UNSUPPORTED,
        },
        "custom_load_profile": {
            "reason": "Only BDEW standard profiles available",
            "research_note": "Custom profiles require preprocessing pipeline not exposed",
            "alternative": "Use BDEW standard profiles",
            "category": CapabilityCategory.PARTIAL,
        },
        "multi_street_optimization": {
            "reason": "Single-street analysis only",
            "research_note": "Portfolio optimization across multiple streets is Phase 2 research",
            "alternative": "Analyze streets individually",
            "category": CapabilityCategory.FUTURE,
        },
    }

    # Keywords that hint at unsupported operations (for NLU fallback detection)
    UNSUPPORTED_KEYWORDS: Dict[str, str] = {
        "add a consumer": "add_consumer",
        "add consumer": "add_consumer",
        "add building": "add_consumer",
        "add house": "add_consumer",
        "new consumer": "add_consumer",
        "new building": "add_consumer",
        "remove pipe": "remove_pipe",
        "delete pipe": "remove_pipe",
        "change pipe": "remove_pipe",
        "modify pipe": "remove_pipe",
        "change building": "change_building_geometry",
        "modify building": "change_building_geometry",
        "building geometry": "change_building_geometry",
        "real time": "real_time_scada",
        "real-time": "real_time_scada",
        "scada": "real_time_scada",
        "live data": "real_time_scada",
        "legal": "legal_compliance_check",
        "compliance": "legal_compliance_check",
        "regulation": "legal_compliance_check",
        "ownership": "change_ownership",
        "custom load": "custom_load_profile",
        "custom profile": "custom_load_profile",
        "multiple streets": "multi_street_optimization",
        "all streets": "multi_street_optimization",
        "portfolio": "multi_street_optimization",
        "optimize all": "multi_street_optimization",
    }

    # Tools available in the system
    AVAILABLE_TOOLS = [
        "cha_simulation",        # District Heating hydraulic simulation
        "dha_simulation",        # Heat Pump grid analysis
        "economics_analysis",    # LCOH and CO2 calculation
        "decision_engine",       # Deterministic rules engine
        "violation_checker",     # Pressure/velocity/voltage limits
        "what_if_scenario",      # Network modification (remove houses only)
        "explanation_generator",  # LLM explanation of decisions
    ]

    def __init__(self):
        self.fallback_llm = FallbackLLM()

    def validate_request(
        self, intent: str, entities: Dict[str, Any], user_query: str = ""
    ) -> CapabilityResponse:
        """
        Validate if intent is within system capabilities.

        Returns CapabilityResponse with:
        - can_handle: True/False
        - message: Direct answer or fallback explanation
        - alternative_suggestions: What the user CAN do instead
        """
        # 1. Check explicit unsupported intents (from NLU)
        intent_lower = intent.lower().replace(" ", "_")
        if intent_lower in self.UNSUPPORTED_INTENTS:
            return self._handle_unsupported(intent_lower)

        # 2. Check keywords in query for unsupported operations
        # (catches cases where NLU returns UNKNOWN but the query is clearly unsupported)
        if user_query:
            keyword_match = self._detect_unsupported_keyword(user_query)
            if keyword_match:
                return self._handle_unsupported(keyword_match)

        # 3. Check if intent requires tools we don't have
        required_tools = self._map_intent_to_tools(intent)
        missing_tools = [t for t in required_tools if t not in self.AVAILABLE_TOOLS]
        if missing_tools:
            return self._handle_missing_tools(intent, missing_tools)

        # 4. Check for partial implementations
        partial = self._check_partial_capabilities(intent, entities)
        if partial:
            return partial

        return CapabilityResponse(
            can_handle=True,
            response_type="direct",
            message="Request is within system capabilities",
            alternative_suggestions=[],
            category=CapabilityCategory.SUPPORTED,
        )

    def _detect_unsupported_keyword(self, user_query: str) -> Optional[str]:
        """Scan user query for keywords that indicate unsupported operations."""
        q = user_query.lower()
        for keyword, unsupported_intent in self.UNSUPPORTED_KEYWORDS.items():
            if keyword in q:
                return unsupported_intent
        return None

    def _handle_unsupported(self, intent: str) -> CapabilityResponse:
        """Generate graceful fallback for unsupported intent."""
        info = self.UNSUPPORTED_INTENTS[intent]

        message = (
            f"I cannot {intent.replace('_', ' ')}. "
            f"{info['reason']}. "
            f"This is a research boundary: {info['research_note']}."
        )

        alternatives = [
            info["alternative"],
            "Compare CO2 emissions for existing network",
            "Check technical feasibility",
            "Generate economic analysis",
        ]

        return CapabilityResponse(
            can_handle=False,
            response_type="fallback",
            message=message,
            alternative_suggestions=alternatives,
            escalation_path=(
                "manual_planning"
                if info["category"] == CapabilityCategory.UNSUPPORTED
                else None
            ),
            category=info["category"],
            research_note=info["research_note"],
        )

    def _handle_missing_tools(
        self, intent: str, missing: List[str]
    ) -> CapabilityResponse:
        """Handle cases where required tools are unavailable."""
        return CapabilityResponse(
            can_handle=False,
            response_type="fallback",
            message=(
                f"I understand you want {intent.replace('_', ' ')}, "
                f"but I'm missing required components: {', '.join(missing)}. "
                f"My available capabilities are: {', '.join(self.AVAILABLE_TOOLS)}."
            ),
            alternative_suggestions=[
                "Run CHA (District Heating) simulation",
                "Run DHA (Heat Pump) analysis",
                "Compare economics with available tools",
                "Check what technical analyses are available",
            ],
            escalation_path="technical_support",
            category=CapabilityCategory.UNSUPPORTED,
        )

    def _check_partial_capabilities(
        self, intent: str, entities: Dict[str, Any]
    ) -> Optional[CapabilityResponse]:
        """Check for edge cases where we have partial capability."""
        if intent == "WHAT_IF_SCENARIO":
            # ALL infrastructure modifications are out of scope.
            # Users must provide a new dataset if they want different
            # building configurations, pipe layouts, or network topology.
            return CapabilityResponse(
                can_handle=False,
                response_type="clarification",
                message=(
                    "I cannot modify the existing infrastructure (removing houses, "
                    "changing pipes, altering temperatures, etc.). Infrastructure "
                    "changes are complex decisions that require municipal planning "
                    "expertise and are outside the scope of my current research "
                    "capabilities. If you need a different building configuration, "
                    "please provide a new GeoJSON dataset and re-run the data "
                    "preparation step."
                ),
                alternative_suggestions=[
                    "Compare CO₂ emissions for the current configuration",
                    "Compare LCOH for the current configuration",
                    "Show the current network layout",
                    "Check violations in the current network",
                ],
                category=CapabilityCategory.PARTIAL,
                research_note=(
                    "What-if scenarios involving infrastructure modification are "
                    "not supported. Users should prepare new input data for "
                    "alternative building/network configurations."
                ),
            )
        return None

    def _map_intent_to_tools(self, intent: str) -> List[str]:
        """Map intent to required tools."""
        mapping = {
            "CO2_COMPARISON": [
                "cha_simulation",
                "dha_simulation",
                "economics_analysis",
            ],
            "LCOH_COMPARISON": [
                "cha_simulation",
                "dha_simulation",
                "economics_analysis",
            ],
            "VIOLATION_ANALYSIS": [
                "cha_simulation",
                "dha_simulation",
                "violation_checker",
            ],
            "NETWORK_DESIGN": ["cha_simulation"],
            "WHAT_IF_SCENARIO": ["cha_simulation", "what_if_scenario"],
            "EXPLAIN_DECISION": ["decision_engine", "explanation_generator"],
        }
        return mapping.get(intent, [])

    def get_capabilities_summary(self) -> Dict[str, List[str]]:
        """Return human-readable capability summary."""
        return {
            "fully_supported": [
                "Simulate District Heating networks (CHA)",
                "Analyze Heat Pump grid feasibility (DHA)",
                "Compare LCOH (Levelized Cost of Heat)",
                "Compare CO2 emissions",
                "Check pressure/velocity violations",
                "Check voltage/line violations",
                "Run what-if scenarios (remove houses only)",
                "Generate decision explanations",
                "View interactive network maps",
            ],
            "partially_supported": [
                "Custom load profiles (BDEW standards only)",
            ],
            "not_supported": [
                "Add/remove pipes or consumers",
                "Real-time SCADA data",
                "Legal compliance verification",
                "Multi-street portfolio optimization",
                "Building geometry modification",
            ],
            "research_objectives": [
                "LLM semantic understanding robustness",
                "What-if scenario chaining",
                "Multi-objective optimization",
            ],
        }


class FallbackLLM:
    """
    LLM-based fallback for graceful degradation.
    Used when we need to explain why we can't do something.
    """

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY", "")

    def generate_fallback_response(
        self,
        user_query: str,
        intent: str,
        reason: str,
    ) -> str:
        """Generate contextual fallback response using LLM."""
        if not self.api_key or self.api_key == "YOUR_ACTUAL_API_KEY_HERE":
            return self._template_fallback(intent, reason)

        prompt = f"""You are a District Heating planning assistant.
The user asked: "{user_query}"

You cannot fulfill this request because: {reason}

Explain:
1. Clearly what you CANNOT do (be specific)
2. What you CAN do instead (list 2-3 specific alternatives)
3. Why this limitation exists (research context)

Keep it concise (3-4 sentences) and helpful."""

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            cfg = types.GenerateContentConfig(temperature=0.3, max_output_tokens=200)
            resp = client.models.generate_content(
                model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=cfg,
            )
            return resp.text if hasattr(resp, "text") else self._template_fallback(intent, reason)
        except Exception as e:
            logger.warning(f"Fallback LLM failed: {e}")
            return self._template_fallback(intent, reason)

    def _template_fallback(self, intent: str, reason: str) -> str:
        """Template fallback when LLM unavailable."""
        return (
            f"I cannot perform {intent.replace('_', ' ')}. {reason}. "
            f"I can help you simulate existing networks, compare DH vs Heat Pump solutions, "
            f"check technical violations, or explain decision recommendations. "
            f"Would you like to analyze a specific street instead?"
        )
