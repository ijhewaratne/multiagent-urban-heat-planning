"""
Intent → Tool Plan Mapper.

Maps BranitzIntent to the tool IDs used by LLMRouter and SCENARIO_REGISTRY
(cha, dha, economics, decision, uhdc).
"""

from typing import Any, Dict, List

# Intent → Tool plan (registry keys)
INTENT_TO_PLAN: Dict[str, List[str]] = {
    "CO2_COMPARISON": ["cha", "dha", "economics"],
    "LCOH_COMPARISON": ["cha", "dha", "economics"],
    "VIOLATION_ANALYSIS": ["cha"],
    "NETWORK_DESIGN": ["cha"],
    "WHAT_IF_SCENARIO": ["cha"],
    "EXPLAIN_DECISION": ["decision"],
    "CAPABILITY_QUERY": [],
    "UNKNOWN": [],
}


def intent_to_plan(intent_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert classifier output to tool plan compatible with LLMRouter.

    Returns:
        [{"tool": "cha", "reason": "..."}, {"tool": "dha", "reason": "..."}, ...]
    """
    intent = str(intent_result.get("intent", "UNKNOWN")).upper().replace(" ", "_")
    reasoning = intent_result.get("reasoning", "")

    tool_ids = INTENT_TO_PLAN.get(intent, INTENT_TO_PLAN["UNKNOWN"])

    plan = []
    for t in tool_ids:
        plan.append({"tool": t, "reason": reasoning or f"Intent {intent} requires {t}"})

    return plan
