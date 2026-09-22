"""
Dynamic Orchestrator – State-Aware Router for Branitz Heat Decision.

Phase 1: Intent-based tool selection.
Phase 2: DynamicExecutor (agent-based) for lazy, context-aware simulation execution.
Phase 3: ConversationManager for multi-turn context and follow-ups.

Implements: "Try to achieve it with tools" – runs only the simulations needed
for the user's intent, using file-based cache to avoid redundant runs.

The executor now delegates to domain agents (domain_agents.py) instead of
calling ADK tools directly.  Results include per-agent timing, cache status,
and metadata alongside the same flat-dict format the UI expects.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from branitz_heat_decision.config import resolve_cluster_path

logger = logging.getLogger(__name__)

# Simulation intents delegated to DynamicExecutor (Phase 2)
# EXPLAIN_DECISION now routed through executor — DecisionAgent handles it
_EXECUTOR_INTENTS = frozenset({
    "CO2_COMPARISON", "LCOH_COMPARISON", "VIOLATION_ANALYSIS",
    "WHAT_IF_SCENARIO", "NETWORK_DESIGN", "GRID_REINFORCEMENT",
    "EXPLAIN_DECISION",
})

# Lazy imports to avoid circular deps and optional deps
def _get_classify_intent():
    from branitz_heat_decision.nlu import classify_intent
    return classify_intent


def _get_executor():
    from branitz_heat_decision.agents.executor import DynamicExecutor
    return DynamicExecutor


def _get_conversation():
    from branitz_heat_decision.agents.conversation import ConversationManager
    return ConversationManager


def _get_guardrail():
    from branitz_heat_decision.agents.fallback import CapabilityGuardrail
    return CapabilityGuardrail


def _get_available_streets() -> List[str]:
    """Load available cluster IDs (delegates to street_resolution module)."""
    from branitz_heat_decision.agents.street_resolution import get_available_streets
    return get_available_streets()


def _get_building_count(cluster_id: str) -> int:
    """Get building count for a cluster from CHA topology (spurs = buildings)."""
    import json as _json

    cha_path = resolve_cluster_path(cluster_id, "cha") / "cha_kpis.json"
    if not cha_path.exists():
        return 0
    try:
        with open(cha_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        topo = data.get("topology", {})
        return (
            topo.get("spurs")
            or topo.get("buildings_connected")
            or len(data.get("detailed", {}).get("heat_consumers", []))
            or 0
        )
    except Exception:
        return 0


def _has_cha_results(cluster_id: str) -> bool:
    """Check if CHA (District Heating) results exist."""
    path = resolve_cluster_path(cluster_id, "cha") / "cha_kpis.json"
    return path.exists()


def _has_dha_results(cluster_id: str) -> bool:
    """Check if DHA (Heat Pump grid) results exist."""
    path = resolve_cluster_path(cluster_id, "dha") / "dha_kpis.json"
    return path.exists()


def _has_economics_results(cluster_id: str) -> bool:
    """Check if economics results exist."""
    path = resolve_cluster_path(cluster_id, "economics") / "economics_deterministic.json"
    return path.exists()


def _has_decision_results(cluster_id: str) -> bool:
    """Check if decision results exist."""
    base = resolve_cluster_path(cluster_id, "decision")
    return (base / f"decision_{cluster_id}.json").exists()


def _load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file (delegates to answer_formatting module)."""
    from branitz_heat_decision.agents.answer_formatting import load_json
    return load_json(path)


def _call_fallback_llm(user_query: str, intent_data: Dict[str, Any]) -> str:
    """
    Fallback agent: LLM explains limitations (Speaker B's "I don't know" requirement).
    Uses google-genai; falls back to template if LLM unavailable.
    """
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key or key == "YOUR_ACTUAL_API_KEY_HERE":
        return _fallback_template(user_query, intent_data)

    prompt = f"""You are a District Heating vs Heat Pump planning assistant for Branitz.
The user asked: "{user_query}"

Intent classification: {intent_data.get("intent", "UNKNOWN")} (confidence: {intent_data.get("confidence", 0)})
Reasoning: {intent_data.get("reasoning", "")}

The user's request is outside the system's capabilities or unclear. You must:

1. Clearly state what you CANNOT do (be specific).
2. List what you CAN do: simulate DH networks (CHA), analyze HP grid feasibility (DHA), compare costs/LCOH and CO₂ (Economics), and explain decisions.
3. Offer the closest valid alternative.

Never make up data or pretend to perform unsupported operations.
Keep your response concise (2-4 sentences)."""

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=300)
        resp = client.models.generate_content(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=cfg,
        )
        return resp.text if hasattr(resp, "text") else str(resp)
    except ImportError:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Fallback LLM failed: {e}")

    return _fallback_template(user_query, intent_data)


def _fallback_template(user_query: str, intent_data: Dict[str, Any]) -> str:
    """Template fallback when LLM unavailable."""
    return (
        "I cannot fulfill that request. I can help you: run District Heating (CHA) simulation, "
        "analyze Heat Pump grid feasibility (DHA), compare costs and CO₂ (Economics), "
        "and explain recommendations. Try: 'Compare CO₂ emissions' or 'What is the LCOH for district heating?'"
    )


class BranitzOrchestrator:
    """
    Central orchestrator: dynamically selects which tools to run based on intent,
    not a fixed sequence. Phase 2: DynamicExecutor. Phase 3: ConversationManager.
    """

    def __init__(self, api_key: Optional[str] = None, cache_dir: str = "./cache"):
        """
        Args:
            api_key: Optional GOOGLE_API_KEY override; else uses env.
            cache_dir: Directory for DynamicExecutor simulation cache.
        """
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        self._session_cache: Dict[str, Any] = {}
        self.executor = _get_executor()(cache_dir=cache_dir)
        self.conversation = _get_conversation()()
        self.capability_guardrail = _get_guardrail()()  # Phase 5

    def route_request(
        self,
        user_query: str,
        cluster_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        run_missing: bool = True,
    ) -> Dict[str, Any]:
        """
        Main entry point: replaces linear run_pipeline().

        Args:
            user_query: Natural language request
            cluster_id: Street cluster ID (optional; extracted from query or context if None)
            context: Optional {"history": [...], "available_streets": [...]}
            run_missing: If True, run simulations that are not yet cached; else only use cache

        Returns:
            {
                "type": "co2_comparison" | "lcoh_comparison" | "CLARIFICATION_NEEDED" | ...,
                "intent_data": {...},
                "execution_plan": ["cha", "dha", "economics"],
                "data": {...},
                "answer": "..."  (human-readable),
                "sources": ["CHA Simulation", "Cached Data"],
                "can_proceed": True/False,
                "agent_trace": [
                    {"agent": "NLU Intent Classifier", "duty": "...", "outcome": "..."},
                    {"agent": "Conversation Manager", "duty": "...", ...},
                    {"agent": "Street Resolver", "duty": "...", ...},
                    {"agent": "Capability Guardrail", "duty": "...", "can_handle": True/False},
                    {"agent": "Execution Planner", "duty": "...", ...},
                    {"agent": "Dynamic Executor", "duty": "...", "outcome": "..."},
                ]
            }
        """
        context = context or {}
        classify_intent_fn = _get_classify_intent()
        from branitz_heat_decision.nlu.intent_mapper import INTENT_TO_PLAN

        # ── Agent Trace: tracks what each agent did ──
        agent_trace: List[Dict[str, Any]] = []

        # ── AGENT 1: NLU Intent Classifier ──
        # Duty: Understand the user's intent and extract entities (metric, street, modification)
        intent_data = classify_intent_fn(
            user_query,
            conversation_history=context.get("history", []),
            use_llm=True,
        )
        explicit_street_hint = intent_data.get("entities", {}).get("street_name")
        agent_trace.append({
            "agent": "NLU Intent Classifier",
            "duty": "Classify user intent and extract entities",
            "outcome": intent_data.get("intent", "UNKNOWN"),
            "confidence": intent_data.get("confidence", 0),
            "entities": intent_data.get("entities", {}),
            "method": "LLM" if intent_data.get("reasoning", "") != "Keyword fallback" else "keyword",
        })

        # ── AGENT 2: Conversation Manager ──
        # Duty: Resolve references (follow-ups, same-street), check memory for cached answers
        resolved_query, enriched_intent, is_follow_up = self.conversation.resolve_references(
            user_query, intent_data
        )
        # Keep an explicit query mention distinct from a street injected by
        # conversation memory. The caller's selected cluster must remain
        # authoritative when the user changes the UI selector.
        raw_street_hint = explicit_street_hint

        agent_trace.append({
            "agent": "Conversation Manager",
            "duty": "Resolve references, detect follow-ups, maintain context",
            "is_follow_up": is_follow_up,
            "raw_street_hint": raw_street_hint,
            "current_memory_street": self.conversation.memory.current_street,
            "available_data": dict(self.conversation.memory.available_data),
        })

        # ── AGENT 3: Street Resolver ──
        # Duty: Map raw street mention (display name / partial / cluster ID) → valid cluster_id
        #
        # Priority order:
        #   1. If NLU extracted an explicit street → resolve it (overrides everything)
        #   2. If cluster_id is a valid ST### from the UI/API → keep it
        #   3. If conversation memory has a street → use it for an implicit follow-up
        #   4. Otherwise extract from query text
        resolve_input = raw_street_hint or user_query
        original_cluster_id = cluster_id  # remember the UI/context default
        memory_street = self.conversation.memory.current_street

        # Resolution logic lives in agents/street_resolution.py
        from branitz_heat_decision.agents.street_resolution import resolve_cluster

        cluster_id, resolver_method = resolve_cluster(
            raw_street_hint, user_query, cluster_id, memory_street, context
        )

        if cluster_id:
            entities = dict(enriched_intent.get("entities", {}))
            entities["street_name"] = cluster_id
            enriched_intent["entities"] = entities

            # A selected/resolved street change starts a fresh conversational
            # context so follow-up answers cannot reuse the previous street's
            # last calculation.
            self.conversation.set_current_street(cluster_id)

        agent_trace.append({
            "agent": "Street Resolver",
            "duty": "Map display name / partial mention → valid cluster_id (ST###_...)",
            "input": resolve_input,
            "original_cluster_id": original_cluster_id,
            "resolved_cluster_id": cluster_id,
            "method": resolver_method,
        })

        # Clarification needed when no street and intent requires one
        intent = str(enriched_intent.get("intent", "UNKNOWN")).upper().replace(" ", "_")
        if not cluster_id and intent not in ("UNKNOWN", "CAPABILITY_QUERY"):
            available = context.get("available_streets") or _get_available_streets()
            agent_trace.append({
                "agent": "Orchestrator",
                "duty": "Route request to correct agent",
                "outcome": "CLARIFICATION_NEEDED — no street identified",
            })
            return {
                "type": "CLARIFICATION_NEEDED",
                "intent_data": enriched_intent,
                "execution_plan": [],
                "data": {"available_streets": available[:20]},
                "answer": (
                    "I'd be happy to help! Could you please specify which street you'd like to analyze? "
                    "You can mention the street name in your question (e.g. 'Compare CO2 for Heinrich-Zille-Straße')."
                ),
                "clarification_type": "street_selection",
                "can_proceed": False,
                "sources": [],
                "agent_trace": agent_trace,
            }

        # Phase 3: Handle follow-ups from memory/cache
        if is_follow_up:
            follow_up_response = self.conversation.handle_follow_up(
                resolved_query, intent, cluster_id
            )
            if follow_up_response:
                agent_trace.append({
                    "agent": "Conversation Manager",
                    "duty": "Answer from memory/cache (no new simulation)",
                    "outcome": f"Follow-up answered from cache: {follow_up_response.get('type', '')}",
                })
                follow_up_response["intent_data"] = enriched_intent
                follow_up_response.setdefault("execution_plan", follow_up_response.get("execution_log", []))
                follow_up_response.setdefault("can_proceed", True)
                follow_up_response.setdefault("suggestions", self.conversation.get_suggestions())
                follow_up_response["agent_trace"] = agent_trace
                return follow_up_response

        # ── AGENT 4: Capability Guardrail (Phase 5) ──
        # Duty: Check if the request is within system boundaries BEFORE execution.
        # Speaker B: "He needs to say 'no, I don't know exactly' instead of going crazy"
        guardrail_result = self.capability_guardrail.validate_request(
            intent=intent,
            entities=enriched_intent.get("entities", {}),
            user_query=user_query,
        )
        agent_trace.append({
            "agent": "Capability Guardrail",
            "duty": "Validate request is within system boundaries",
            "can_handle": guardrail_result.can_handle,
            "response_type": guardrail_result.response_type,
            "category": guardrail_result.category.value if guardrail_result.category else None,
            "research_note": guardrail_result.research_note,
        })

        if not guardrail_result.can_handle:
            # Speaker B: "He needs to say 'no, I don't know exactly'"
            preview = None
            if intent == "WHAT_IF_SCENARIO" and cluster_id:
                preview = self._build_hypothetical_what_if_preview(
                    cluster_id=cluster_id,
                    intent_data=enriched_intent,
                    context=context,
                    run_missing=run_missing,
                )
            resp = self._handle_capability_fallback(
                user_query=user_query,
                intent=intent,
                capability=guardrail_result,
                intent_data=enriched_intent,
                hypothetical_preview=preview,
            )
            resp["agent_trace"] = agent_trace
            return resp

        # 2. DATA_QUERY → Load and display building data directly
        if intent == "DATA_QUERY":
            agent_trace.append({
                "agent": "Data Query Agent",
                "duty": "Load building data from processed files",
                "outcome": "loading",
            })
            data_response = self._handle_data_query(
                user_query=user_query,
                cluster_id=cluster_id,
                entities=enriched_intent.get("entities", {}),
            )
            data_response["intent_data"] = enriched_intent
            data_response["agent_trace"] = agent_trace
            return data_response

        # 3. UNKNOWN / CAPABILITY → Fallback
        if intent in ("UNKNOWN", "CAPABILITY_QUERY"):
            agent_trace.append({
                "agent": "Fallback Agent",
                "duty": "Explain limitations or list capabilities",
                "outcome": intent,
            })
            if intent == "CAPABILITY_QUERY":
                sub_query = enriched_intent.get("entities", {}).get("sub_query", "")

                # Street listing sub-query
                if sub_query == "list_streets" or any(
                    w in user_query.lower()
                    for w in ["which street", "what street", "list street",
                              "available street", "streets in", "all streets",
                              "list street", "number of house", "number of building"]
                ):
                    streets = _get_available_streets()
                    if streets:
                        # Gather building counts from CHA topology
                        street_lines = []
                        total_buildings = 0
                        for s in streets:
                            n_buildings = _get_building_count(s)
                            total_buildings += n_buildings if isinstance(n_buildings, int) else 0
                            label = s.replace("_", " ")
                            street_lines.append(
                                f"- **{label}** — {n_buildings} buildings"
                            )
                        street_list = "\n".join(street_lines)
                        answer = (
                            f"There are **{len(streets)} streets** in the Branitz district "
                            f"with a total of **{total_buildings} buildings**:\n\n"
                            f"{street_list}\n\n"
                            f"You can ask about any of these, e.g. "
                            f"'Compare CO₂ for {streets[0].replace('_', ' ')}'"
                        )
                    else:
                        answer = (
                            "I couldn't find the street cluster index. "
                            "Please ensure the data has been prepared with `00_prepare_data.py`."
                        )
                else:
                    caps = self.capability_guardrail.get_capabilities_summary()
                    supported = "; ".join(caps["fully_supported"][:5])
                    not_supported = "; ".join(caps["not_supported"][:3])
                    answer = (
                        f"Here's what I can do:\n\n"
                        f"**Supported:** {supported}.\n\n"
                        f"**Not supported:** {not_supported}.\n\n"
                        f"Try: 'Compare CO₂ emissions' or 'Show me the network layout'."
                    )
            else:
                answer = _call_fallback_llm(user_query, enriched_intent)
            return {
                "type": "fallback",
                "intent_data": enriched_intent,
                "execution_plan": [],
                "data": {},
                "answer": answer,
                "sources": [],
                "can_proceed": False,
                "suggestion": "Try: 'Compare CO₂ emissions' or 'What is the LCOH for district heating?'",
                "agent_trace": agent_trace,
            }

        # ── AGENT 5: Execution Planner ──
        # Duty: Determine which simulations are needed for this intent
        required_tools = INTENT_TO_PLAN.get(intent, [])
        agent_trace.append({
            "agent": "Execution Planner",
            "duty": f"Determine required simulations for {intent}",
            "required_tools": required_tools,
            "cluster_id": cluster_id,
        })

        # 3. ROUTE by intent
        # Phase 2: Simulation intents → DynamicExecutor
        if intent in _EXECUTOR_INTENTS:
            # ── AGENT 6: Dynamic Executor (agent-based) ──
            # Duty: Delegate to domain agents, run only what's missing, use cache
            try:
                results = self.executor.execute(
                    intent=intent,
                    street_id=cluster_id,
                    context={
                        "modification": (enriched_intent.get("entities") or {}).get("modification"),
                        "history": context.get("history", []),
                        "run_missing": run_missing,
                    },
                )

                # Richer agent trace — per-agent success/cache/timing
                per_agent = results.get("agent_results", {})
                agent_trace.append({
                    "agent": "Dynamic Executor",
                    "duty": f"Execute {intent} for {cluster_id} (agent-based, lazy)",
                    "outcome": "error" if "error" in results else "success",
                    "execution_log": results.get("execution_log", []),
                    "total_execution_time": results.get("total_execution_time"),
                    "agents_invoked": {
                        name: {
                            "success": info.get("success"),
                            "cache_hit": info.get("cache_hit"),
                            "execution_time": info.get("execution_time"),
                        }
                        for name, info in per_agent.items()
                    },
                })

                response = self._format_executor_response(
                    intent=intent,
                    intent_data=enriched_intent,
                    results=results,
                )

                # Phase 3: Update conversation memory and add suggestions
                if "error" not in results:
                    self.conversation.update_memory(
                        intent=intent,
                        street_id=cluster_id,
                        results=results,
                        execution_log=results.get("execution_log", []),
                    )
                    response["suggestions"] = self.conversation.get_suggestions()
                response["agent_trace"] = agent_trace
                return response

            except ValueError as e:
                agent_trace.append({
                    "agent": "Dynamic Executor",
                    "duty": f"Execute {intent}",
                    "outcome": f"ValueError: {e}",
                })
                return {
                    "type": "fallback",
                    "intent_data": enriched_intent,
                    "execution_plan": [],
                    "data": {},
                    "answer": str(e),
                    "sources": [],
                    "can_proceed": False,
                    "agent_trace": agent_trace,
                }
            except Exception as e:
                logger.exception("Executor failed for intent=%s", intent)
                agent_trace.append({
                    "agent": "Dynamic Executor",
                    "duty": f"Execute {intent}",
                    "outcome": f"Exception: {e}",
                })
                return {
                    "type": "ERROR",
                    "intent_data": enriched_intent,
                    "execution_plan": [],
                    "data": {},
                    "answer": f"Simulation failed: {str(e)}",
                    "sources": [],
                    "can_proceed": False,
                    "suggestion": "Please try a different query or check the street data.",
                    "agent_trace": agent_trace,
                }

        # Unhandled intent
        agent_trace.append({
            "agent": "Fallback Agent",
            "duty": "Handle unrecognized intent",
            "outcome": f"Unhandled: {intent}",
        })
        return {
            "type": "fallback",
            "intent_data": enriched_intent,
            "execution_plan": [],
            "data": {},
            "answer": _call_fallback_llm(user_query, enriched_intent),
            "sources": [],
            "can_proceed": False,
            "agent_trace": agent_trace,
        }

    def _format_executor_response(
        self,
        intent: str,
        intent_data: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Transform DynamicExecutor results to orchestrator response format.

        Implementation lives in ``agents/answer_formatting.py``.
        """
        from branitz_heat_decision.agents.answer_formatting import format_executor_response
        return format_executor_response(intent, intent_data, results)

    def _format_answer(self, results: Dict[str, Any], intent: str) -> str:
        """Convert executor results to human-readable answer (see answer_formatting)."""
        from branitz_heat_decision.agents.answer_formatting import format_answer
        return format_answer(results, intent)

    def _format_decision_answer(self, results: Dict[str, Any]) -> str:
        """Rich human-readable answer for EXPLAIN_DECISION (see answer_formatting)."""
        from branitz_heat_decision.agents.answer_formatting import format_decision_answer
        return format_decision_answer(results)

    def _enrich_decision_data(
        self, data: Dict[str, Any], intent_data: Dict[str, Any]
    ) -> None:
        """Enrich executor result with full decision JSON (see answer_formatting)."""
        from branitz_heat_decision.agents.answer_formatting import enrich_decision_data
        enrich_decision_data(data, intent_data)

    def _create_viz(self, results: Dict[str, Any], intent: str) -> Optional[Dict[str, Any]]:
        """Create visualization hint for UI (see answer_formatting)."""
        from branitz_heat_decision.agents.answer_formatting import create_viz
        return create_viz(results, intent)

    def _handle_capability_fallback(
        self,
        user_query: str,
        intent: str,
        capability: Any,  # CapabilityResponse
        intent_data: Dict[str, Any],
        hypothetical_preview: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle unsupported requests gracefully (Speaker B requirement).

        Phase 5: Instead of crashing or hallucinating, return a structured
        explanation of why the request cannot be fulfilled, with alternatives.
        """
        from branitz_heat_decision.agents.fallback import CapabilityGuardrail

        # Use LLM to generate contextual fallback if needed
        if capability.response_type == "fallback":
            message = self.capability_guardrail.fallback_llm.generate_fallback_response(
                user_query, intent, capability.message
            )
        else:
            message = capability.message

        if hypothetical_preview:
            message = (
                f"{message}\n\n"
                f"{self._format_hypothetical_preview_answer(hypothetical_preview)}"
            )

        # Look up research note from registry
        unsupported_info = CapabilityGuardrail.UNSUPPORTED_INTENTS.get(intent.lower(), {})

        cat_value = capability.category.value if capability.category else "unknown"
        research_note = capability.research_note or unsupported_info.get("research_note")

        return {
            "type": "guardrail_blocked",
            "subtype": "capability_limitation",
            "intent_data": intent_data,
            "execution_plan": [],
            "data": {
                "limitation": intent,
                "guardrail_reason": capability.message,
                "category": cat_value,
                "research_note": research_note,
                "alternatives": capability.alternative_suggestions,
                "escalation_path": capability.escalation_path,
                "hypothetical_preview": hypothetical_preview,
            },
            "answer": message,
            "alternative_suggestions": capability.alternative_suggestions,
            "suggestions": capability.alternative_suggestions[:3],
            "sources": ["Capability Guardrail"],
            "can_proceed": False,
            # Top-level fields for easy UI/CLI access
            "category": cat_value,
            "research_note": research_note,
            "escalation_path": capability.escalation_path,
            # Important for thesis: document this as research objective
            "is_research_boundary": True,
        }

    def _build_hypothetical_what_if_preview(
        self,
        cluster_id: str,
        intent_data: Dict[str, Any],
        context: Dict[str, Any],
        run_missing: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Best-effort advisory preview for blocked what-if requests.

        This does not change the guardrail outcome. It only provides a clearly
        labeled hypothetical result so the UI can say "not supported, but if it
        were simulated these could be the effects."
        """
        try:
            preview = self.executor.execute(
                intent="WHAT_IF_SCENARIO",
                street_id=cluster_id,
                context={
                    "modification": (intent_data.get("entities") or {}).get("modification"),
                    "history": context.get("history", []),
                    "run_missing": run_missing,
                },
            )
        except Exception as e:
            logger.warning("Hypothetical what-if preview failed for %s: %s", cluster_id, e)
            return None

        if "error" in preview:
            logger.warning(
                "Hypothetical what-if preview returned error for %s: %s",
                cluster_id,
                preview["error"],
            )
            return None

        return {
            "cluster_id": cluster_id,
            "baseline": preview.get("baseline", {}),
            "scenario": preview.get("scenario", {}),
            "comparison": preview.get("comparison", {}),
            "modification_applied": preview.get("modification_applied", ""),
            "execution_log": preview.get("execution_log", []),
            "agent_results": preview.get("agent_results", {}),
            "total_execution_time": preview.get("total_execution_time"),
            "disclaimer": (
                "This is a hypothetical preview only. The system still does not allow "
                "infrastructure modifications as a supported workflow."
            ),
        }

    @staticmethod
    def _format_hypothetical_preview_answer(preview: Dict[str, Any]) -> str:
        mod = preview.get("modification_applied", "the requested change")
        comparison = preview.get("comparison", {})
        baseline = preview.get("baseline", {})
        scenario = preview.get("scenario", {})

        dp = comparison.get("pressure_change_bar", 0.0)
        dq = comparison.get("heat_delivered_change_mw", 0.0)
        vr = comparison.get("violation_reduction", 0)
        base_p = baseline.get("max_pressure_bar", 0.0)
        scen_p = scenario.get("max_pressure_bar", 0.0)

        return (
            "The requested modification is still outside the supported workflow. "
            f"However, as a hypothetical preview, if {mod} were simulated on the current "
            f"district-heating model, the estimated maximum pressure would change from "
            f"{base_p:.3f} bar to {scen_p:.3f} bar, heat delivered would change by "
            f"{dq:.4f} MW, and the simplified violation count would change by {vr}. "
            f"Net pressure change: {dp:.4f} bar."
        )

    def get_system_capabilities(self) -> Dict[str, List[str]]:
        """Public API to show what the system can/cannot do."""
        return self.capability_guardrail.get_capabilities_summary()

    def _extract_street_from_query(self, user_query: str, context: Dict[str, Any]) -> Optional[str]:
        """Extract street/cluster from query (see street_resolution)."""
        from branitz_heat_decision.agents.street_resolution import extract_street_from_query
        return extract_street_from_query(user_query, context)

    def _compute_execution_plan(
        self,
        cluster_id: str,
        required: List[str],
    ) -> List[str]:
        """Determine which scenarios need to be run (not yet cached), in dependency order."""
        order = ["cha", "dha", "economics", "decision"]
        checks = {
            "cha": _has_cha_results,
            "dha": _has_dha_results,
            "economics": _has_economics_results,
            "decision": _has_decision_results,
        }
        missing = []
        for phase in required:
            if phase in checks and not checks[phase](cluster_id):
                missing.append(phase)
        return [p for p in order if p in missing]

    def _handle_data_query(self, user_query: str, cluster_id: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Load building data directly from processed data files to answer data queries."""
        from branitz_heat_decision.config import DATA_PROCESSED
        import pandas as pd
        
        buildings_path = DATA_PROCESSED / "buildings.parquet"
        cluster_map_path = DATA_PROCESSED / "building_cluster_map.parquet"
        
        if not buildings_path.exists() or not cluster_map_path.exists():
            return {
                "type": "data_query",
                "execution_plan": [],
                "data": {},
                "answer": "I cannot provide the data because the processed data files (buildings.parquet or building_cluster_map.parquet) are missing.",
                "sources": [],
                "can_proceed": False
            }
            
        try:
            # Read buildings and map
            buildings = pd.read_parquet(buildings_path)
            cluster_map = pd.read_parquet(cluster_map_path)
            
            # Merge to filter by cluster
            merged = pd.merge(buildings, cluster_map, on="building_id", how="inner")
            
            if cluster_id:
                # Filter for the specific street (case insensitive)
                merged = merged[merged["cluster_id"].str.upper() == cluster_id.upper()]
                street_display = cluster_id.replace("_", " ")
            else:
                street_display = "the district"
                
            if merged.empty:
                return {
                    "type": "data_query",
                    "execution_plan": [],
                    "data": {},
                    "answer": f"No buildings found for {street_display}.",
                    "sources": ["Data Query"],
                    "can_proceed": False
                }
                
            # Compute stats
            total_buildings = len(merged)
            
            # Formulate answer based on the requested metric
            metric = entities.get("metric", "heat_demand")
            
            if metric == "design_hour":
                # Look up design load from design_topn.json
                design_path = DATA_PROCESSED / "cluster_design_topn.json"
                if design_path.exists():
                    import json
                    with open(design_path, "r", encoding="utf-8") as f:
                        design_data = json.load(f)
                    cluster_data = {}
                    for k, v in design_data.get("clusters", {}).items():
                        if k.upper() == cluster_id.upper():
                            cluster_data = v
                            break
                    design_load_kw = cluster_data.get("design_load_kw", 0)
                    answer = f"The design hour heat load for {street_display} is **{design_load_kw:.2f} kW** (sum for {total_buildings} buildings)."
                else:
                    answer = f"Design hour data is not available (missing cluster_design_topn.json)."
            else:
                # Default: heat demand
                if "annual_heat_demand_kwh_a" in merged.columns and "specific_heat_demand_kwh_m2a" in merged.columns:
                    total_demand = merged["annual_heat_demand_kwh_a"].sum()
                    avg_spec_demand = merged["specific_heat_demand_kwh_m2a"].mean()
                    
                    # Create a small summary text
                    answer = f"In {street_display}, there are **{total_buildings} residential buildings**.\n"
                    answer += f"- Total annual heat demand: **{total_demand:,.0f} kWh/a**\n"
                    answer += f"- Average specific heat demand: **{avg_spec_demand:.1f} kWh/(m²a)**\n\n"
                    
                    # Create a breakdown by renovation state
                    if "sanierungszustand" in merged.columns:
                        breakdown = merged.groupby("sanierungszustand")["building_id"].count()
                        answer += "Renovation state breakdown:\n"
                        for state, count in breakdown.items():
                            answer += f"- {state}: {count} buildings\n"
                else:
                    answer = f"Detailed heat demand columns are missing in the dataset for {street_display}."

            return {
                "type": "data_query",
                "execution_plan": [],
                "data": {"buildings_count": total_buildings},
                "answer": answer,
                "sources": ["buildings.parquet", "building_cluster_map.parquet"],
                "can_proceed": True
            }
            
        except Exception as e:
            logger.exception("Failed to handle DATA_QUERY")
            return {
                "type": "ERROR",
                "execution_plan": [],
                "data": {},
                "answer": f"Error loading data: {str(e)}",
                "sources": [],
                "can_proceed": False
            }
