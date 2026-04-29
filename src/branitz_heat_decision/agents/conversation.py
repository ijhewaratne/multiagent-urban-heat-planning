"""
Multi-Turn Conversation State Manager for Branitz Heat Decision AI

Implements Speaker B's requirement: "Then you can say what about..."
- Maintains session context across turns
- Handles anaphora/ellipsis ("What about LCOH?" → implies same street, compare metrics)
- Tracks available data to avoid re-simulation
- Manages conversation flow state (clarification, confirmation, etc.)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """High-level conversation states."""

    INITIAL = "initial"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    IN_PROGRESS = "in_progress"
    FOLLOW_UP = "follow_up"
    MODIFICATION = "modification"


@dataclass
class CalculationContext:
    """Snapshot of a calculation for reference in follow-ups."""

    intent: str
    street_id: str
    results_summary: Dict[str, Any]
    execution_log: List[str]
    timestamp: str
    visualization_type: Optional[str] = None


@dataclass
class ConversationMemory:
    """Persistent session memory."""

    current_street: Optional[str] = None
    last_calculation: Optional[CalculationContext] = None
    calculation_history: List[CalculationContext] = field(default_factory=list)
    available_data: Dict[str, List[str]] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    pending_modification: Optional[str] = None
    last_intent: Optional[str] = None

    def track_data_availability(self, street_id: str, data_type: str) -> None:
        """Track that we have certain data available for a street."""
        if street_id not in self.available_data:
            self.available_data[street_id] = []
        if data_type not in self.available_data[street_id]:
            self.available_data[street_id].append(data_type)

    def has_data(self, street_id: str, data_type: str) -> bool:
        """Check if we have specific data cached for a street."""
        return data_type in self.available_data.get(street_id, [])


class ConversationManager:
    """
    Manages multi-turn conversation state and context resolution.

    Key capabilities:
    1. Reference resolution: "What about LCOH?" → knows it means "for the same street, compare LCOH"
    2. Reuse detection: Knows when cached data can answer a follow-up
    3. Modification chaining: "What if we remove 2 houses?" → "What about 3 houses?"
    4. Implicit context: Maintains current street across turns
    """

    def __init__(self) -> None:
        self.memory = ConversationMemory()
        self.state = ConversationState.INITIAL

        self.follow_up_patterns = [
            r"what\s+about",
            r"how\s+about",
            r"and\s+(?:the\s+)?",
            r"what\s+(?:is|are)\s+(?:the\s+)?",
            r"compare\s+(?:also\s+)?",
            r"what\s+if\s+we",
            r"how\s+about\s+if\s+we",
            r"can\s+you\s+(?:also\s+)?",
            r"also\s+show",
            r"what\s+about\s+(?:the\s+)?",
        ]

        self.metric_patterns = {
            "co2": r"(?:co2|carbon|emissions?)",
            "lcoh": r"(?:lcoh|cost|price|economics?)",
            "violations": r"(?:violations?|pressure|velocity|limits?)",
            "network": r"(?:network|pipes?|layout|topology)",
            "decision": r"(?:decision|recommendation|why|explain)",
        }

    def is_follow_up(self, user_query: str) -> bool:
        """Detect if this is a follow-up question based on linguistic patterns."""
        query_lower = user_query.lower().strip()

        for pattern in self.follow_up_patterns:
            if re.search(pattern, query_lower):
                return True

        if len(user_query.split()) < 5 and self.memory.current_street:
            return True

        return False

    def resolve_references(
        self,
        user_query: str,
        intent_data: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any], bool]:
        """
        Resolve implicit references in follow-up queries.

        Args:
            user_query: Raw user input
            intent_data: Classified intent from NLU

        Returns:
            (resolved_query, enriched_intent_data, is_follow_up)
        """
        is_follow_up = self.is_follow_up(user_query)

        if not is_follow_up:
            entities = intent_data.get("entities", {})
            if entities.get("street_name"):
                self.memory.current_street = entities["street_name"]
            return user_query, intent_data, False

        enriched_intent = intent_data.copy()

        if not enriched_intent.get("entities", {}).get("street_name"):
            if self.memory.current_street:
                if "entities" not in enriched_intent:
                    enriched_intent["entities"] = {}
                enriched_intent["entities"]["street_name"] = self.memory.current_street
                logger.info("Resolved street reference to %s", self.memory.current_street)

        if self._is_metric_switch_follow_up(user_query):
            new_metric = self._extract_metric(user_query)
            if new_metric:
                enriched_intent["original_intent"] = enriched_intent.get("intent")
                enriched_intent["intent"] = self._metric_to_intent(new_metric)
                enriched_intent["is_metric_switch"] = True
                logger.info("Metric switch detected: %s -> %s", new_metric, enriched_intent["intent"])

        if "what if" in user_query.lower() or "how about if" in user_query.lower():
            if self.memory.last_calculation and self.memory.pending_modification:
                enriched_intent["previous_modification"] = self.memory.pending_modification

        return user_query, enriched_intent, True

    def handle_follow_up(
        self,
        user_query: str,
        current_intent: str,
        street_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle follow-up by determining if we can answer from cache
        or if we need new calculations.

        Returns:
            Response dict if can answer from cache, None if needs new execution
        """
        if self._is_metric_switch_follow_up(user_query) and self.memory.last_calculation:
            last = self.memory.last_calculation
            if self.memory.has_data(street_id, "economics"):
                new_metric = self._extract_metric(user_query)
                econ_data = self._load_cached_economics(street_id)

                if new_metric == "lcoh" and econ_data:
                    return self._format_metric_switch_response(last, econ_data, "lcoh")
                if new_metric == "co2" and econ_data:
                    return self._format_metric_switch_response(last, econ_data, "co2")

        if current_intent == "WHAT_IF_SCENARIO" and self.memory.last_calculation:
            if self.memory.last_calculation.intent == "WHAT_IF_SCENARIO":
                return {
                    "type": "modification_chain",
                    "previous_scenario": self.memory.last_calculation,
                    "message": "Modifying previous scenario",
                    "reuse_baseline": True,
                }

        if current_intent != "EXPLAIN_DECISION" and any(word in user_query.lower() for word in ["why", "how", "explain"]):
            if self.memory.last_calculation:
                return self._generate_clarification(user_query, self.memory.last_calculation)

        return None

    def update_memory(
        self,
        intent: str,
        street_id: str,
        results: Dict[str, Any],
        execution_log: List[str],
    ) -> None:
        """Update conversation memory after successful execution."""
        self.memory.current_street = street_id
        self.memory.last_intent = intent

        for log_entry in execution_log:
            if "CHA" in log_entry or "cha" in log_entry:
                self.memory.track_data_availability(street_id, "cha")
            if "DHA" in log_entry or "dha" in log_entry:
                self.memory.track_data_availability(street_id, "dha")
            if "Economics" in log_entry or "economics" in log_entry:
                self.memory.track_data_availability(street_id, "economics")

        calc_context = CalculationContext(
            intent=intent,
            street_id=street_id,
            results_summary=self._extract_key_metrics(results, intent),
            execution_log=execution_log,
            timestamp=datetime.now().isoformat(),
            visualization_type=self._get_viz_type(intent),
        )

        self.memory.last_calculation = calc_context
        self.memory.calculation_history.append(calc_context)

        if intent == "WHAT_IF_SCENARIO":
            self.memory.pending_modification = results.get("modification_applied")
        else:
            self.memory.pending_modification = None

        logger.info(
            "Memory updated: %s for %s, available data: %s",
            intent,
            street_id,
            self.memory.available_data.get(street_id, []),
        )

    def get_suggestions(self) -> List[str]:
        """Generate contextual suggestions based on conversation state."""
        suggestions: List[str] = []

        if not self.memory.last_calculation:
            return ["Compare CO2 emissions", "Compare LCOH", "Check violations"]

        last_intent = self.memory.last_calculation.intent
        current = self.memory.current_street or "this street"

        if last_intent == "CO2_COMPARISON":
            suggestions.append("What about LCOH?")
            suggestions.append("What about violations?")
            suggestions.append(f"What if we remove 2 houses from {current}?")
        elif last_intent == "LCOH_COMPARISON":
            suggestions.append("What about CO2 emissions?")
            suggestions.append("What about network design?")
        elif last_intent == "VIOLATION_ANALYSIS":
            suggestions.append("What about costs?")
            suggestions.append("Generate a decision report")

        if self.memory.current_street and self.memory.has_data(self.memory.current_street, "cha"):
            suggestions.append("What if we remove some houses?")
            suggestions.append("What if we change pipe diameter?")

        return suggestions[:3]

    def _is_metric_switch_follow_up(self, query: str) -> bool:
        """Detect 'what about X' metric switching."""
        return bool(
            re.search(
                r"what\s+about\s+(?:the\s+)?(co2|lcoh|cost|violations?)",
                query.lower(),
            )
        )

    def _extract_metric(self, query: str) -> Optional[str]:
        """Extract metric name from query."""
        q = query.lower()
        for metric, pattern in self.metric_patterns.items():
            if re.search(pattern, q):
                return metric
        return None

    def _metric_to_intent(self, metric: str) -> str:
        """Convert metric name to intent."""
        mapping = {
            "co2": "CO2_COMPARISON",
            "lcoh": "LCOH_COMPARISON",
            "violations": "VIOLATION_ANALYSIS",
            "network": "NETWORK_DESIGN",
            "decision": "EXPLAIN_DECISION",
        }
        return mapping.get(metric, "UNKNOWN")

    def _format_metric_switch_response(
        self,
        last_calc: CalculationContext,
        econ_data: Dict[str, Any],
        new_metric: str,
    ) -> Dict[str, Any]:
        """Format response when switching metrics using cached data."""
        if new_metric == "lcoh":
            dh = econ_data.get("lcoh_dh_eur_per_mwh", 0)
            hp = econ_data.get("lcoh_hp_eur_per_mwh", 0)
            answer = (
                f"For the same street ({last_calc.street_id}), "
                f"LCOH is {dh:.1f} €/MWh for DH vs {hp:.1f} €/MWh for HP. "
                f"DH is {'cheaper' if dh < hp else 'more expensive'}."
            )
            data: Dict[str, Any] = {
                "lcoh_dh_eur_per_mwh": dh,
                "lcoh_hp_eur_per_mwh": hp,
                "winner": "DH" if dh < hp else "HP",
            }
        else:
            dh = econ_data.get("co2_dh_t_per_a", 0)
            hp = econ_data.get("co2_hp_t_per_a", 0)
            answer = (
                f"For the same street ({last_calc.street_id}), "
                f"CO2 emissions are {dh:.1f} t/year for DH vs {hp:.1f} t/year for HP. "
                f"DH emits {'less' if dh < hp else 'more'}."
            )
            data = {
                "co2_dh_t_per_a": dh,
                "co2_hp_t_per_a": hp,
                "winner": "DH" if dh < hp else "HP",
            }

        return {
            "type": new_metric + "_comparison",
            "answer": answer,
            "data": data,
            "execution_log": ["Used cached Economics data"],
            "sources": ["Cached Economics"],
            "is_follow_up": True,
            "previous_intent": last_calc.intent,
        }

    def _load_cached_economics(self, street_id: str) -> Optional[Dict[str, Any]]:
        """Load economics data from file cache."""
        try:
            from branitz_heat_decision.config import resolve_cluster_path

            path = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Failed to load cached economics: %s", e)
        return None

    def _extract_key_metrics(self, results: Dict[str, Any], intent: str) -> Dict[str, Any]:
        """Extract key metrics for storage."""
        if intent == "CO2_COMPARISON":
            return {
                "dh_co2": results.get("dh_tons_co2"),
                "hp_co2": results.get("hp_tons_co2"),
                "winner": results.get("winner"),
            }
        if intent == "LCOH_COMPARISON":
            return {
                "dh_lcoh": results.get("lcoh_dh_eur_per_mwh"),
                "hp_lcoh": results.get("lcoh_hp_eur_per_mwh"),
                "winner": results.get("winner"),
            }
        return {}

    def _get_viz_type(self, intent: str) -> Optional[str]:
        """Get visualization type for intent."""
        mapping = {
            "CO2_COMPARISON": "bar_chart",
            "LCOH_COMPARISON": "bar_chart",
            "VIOLATION_ANALYSIS": "map",
            "NETWORK_DESIGN": "network_graph",
            "WHAT_IF_SCENARIO": "comparison",
        }
        return mapping.get(intent)

    def _generate_clarification(
        self,
        query: str,
        calc_context: CalculationContext,
    ) -> Dict[str, Any]:
        """Generate clarification about previous calculation."""
        summary = calc_context.results_summary
        summary_str = ", ".join(f"{k}={v}" for k, v in summary.items()) if summary else "see data"
        return {
            "type": "clarification",
            "answer": (
                f"Based on the previous {calc_context.intent.replace('_', ' ').lower()} "
                f"for {calc_context.street_id}: "
                f"Key findings: {summary_str}."
            ),
            "data": calc_context.results_summary,
            "execution_log": ["Retrieved from conversation memory"],
            "sources": ["Conversation history"],
        }
