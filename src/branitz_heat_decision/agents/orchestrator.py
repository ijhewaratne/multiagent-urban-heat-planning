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

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from branitz_heat_decision.config import resolve_cluster_path

logger = logging.getLogger(__name__)

# Simulation intents delegated to DynamicExecutor (Phase 2)
# EXPLAIN_DECISION now routed through executor — DecisionAgent handles it
_EXECUTOR_INTENTS = frozenset({
    "CO2_COMPARISON", "LCOH_COMPARISON", "VIOLATION_ANALYSIS",
    "WHAT_IF_SCENARIO", "NETWORK_DESIGN", "EXPLAIN_DECISION",
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
    """Load available cluster IDs from cluster index."""
    try:
        from branitz_heat_decision.ui.services import ClusterService

        svc = ClusterService()
        idx = svc.get_cluster_index()
        if not idx.empty:
            col = "cluster_id" if "cluster_id" in idx.columns else idx.columns[0]
            return idx[col].astype(str).tolist()
    except Exception:
        pass
    try:
        from branitz_heat_decision.config import DATA_PROCESSED

        sc = DATA_PROCESSED / "street_clusters.parquet"
        if sc.exists():
            import pandas as pd

            df = pd.read_parquet(sc)
            if not df.empty and "street_id" in df.columns:
                return df["street_id"].astype(str).tolist()
    except Exception:
        pass
    return []


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
    """Load JSON file or return empty dict."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return {}


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
            model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
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
        # Pick up the raw street hint from NLU entities or conversation memory
        raw_street_hint = enriched_intent.get("entities", {}).get("street_name")

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
        #   2. If follow-up and conversation memory has a street → use memory (overrides UI default)
        #   3. If cluster_id is a valid ST### from the UI → keep it
        #   4. Otherwise extract from query text
        resolver_method = "pending"
        resolve_input = raw_street_hint or user_query
        original_cluster_id = cluster_id  # remember the UI/context default
        memory_street = self.conversation.memory.current_street

        if raw_street_hint:
            # User explicitly mentioned a street — resolve it even if we already have a cluster_id
            raw_is_valid = bool(re.match(r"^ST\d{3}", raw_street_hint))
            if raw_is_valid:
                cluster_id = raw_street_hint
                resolver_method = "NLU returned valid cluster_id"
            else:
                resolved = self._extract_street_from_query(raw_street_hint, context)
                if resolved:
                    cluster_id = resolved
                    resolver_method = "resolved from NLU entity"
                else:
                    resolved = self._extract_street_from_query(user_query, context)
                    if resolved:
                        cluster_id = resolved
                        resolver_method = "resolved from query (NLU hint failed)"
                    else:
                        resolver_method = "failed — NLU hint did not match any cluster"

        elif memory_street and re.match(r"^ST\d{3}", memory_street):
            # No explicit street in query, but conversation memory has one.
            # The user has been talking about this street — maintain continuity.
            # This overrides the UI default (the user may have started with ST001
            # but switched to ST010 mid-conversation).
            cluster_id = memory_street
            resolver_method = "conversation memory (street continuity)"

        elif not cluster_id or not re.match(r"^ST\d{3}", cluster_id):
            # No NLU hint, no memory, no valid cluster_id — extract from query
            resolved = self._extract_street_from_query(user_query, context)
            if resolved:
                cluster_id = resolved
                resolver_method = "resolved from query"
            else:
                resolver_method = "none (not found)"
        else:
            # cluster_id is already valid ST### from UI, and no memory yet
            resolver_method = "pre-validated (UI default)"

        if cluster_id and cluster_id != original_cluster_id:
            if "entities" not in enriched_intent:
                enriched_intent["entities"] = {}
            enriched_intent["entities"]["street_name"] = cluster_id

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
            resp = self._handle_capability_fallback(
                user_query=user_query,
                intent=intent,
                capability=guardrail_result,
                intent_data=enriched_intent,
            )
            resp["agent_trace"] = agent_trace
            return resp

        # 2. UNKNOWN / CAPABILITY → Fallback
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
        """
        Transform DynamicExecutor results to orchestrator response format.

        The executor now returns richer results including:
          - agent_results: per-agent success/cache/timing
          - total_execution_time: end-to-end duration
        These are passed through to the UI for transparency.
        """
        if "error" in results:
            return {
                "type": intent.lower(),
                "intent_data": intent_data,
                "execution_plan": results.get("execution_log", []),
                "data": results,
                "answer": results["error"],
                "sources": [],
                "can_proceed": False,
                "execution_log": results.get("execution_log", []),
                "visualization": None,
            }

        answer = self._format_answer(results, intent)
        viz = self._create_viz(results, intent)

        # Map executor data keys to orchestrator data format for UI compatibility
        data = dict(results)
        if intent == "CO2_COMPARISON":
            data["co2_dh_t_per_a"] = results.get("dh_tons_co2", 0)
            data["co2_hp_t_per_a"] = results.get("hp_tons_co2", 0)
        elif intent == "LCOH_COMPARISON":
            data["lcoh_dh_eur_per_mwh"] = results.get("lcoh_dh_eur_per_mwh", 0)
            data["lcoh_hp_eur_per_mwh"] = results.get("lcoh_hp_eur_per_mwh", 0)
        elif intent == "EXPLAIN_DECISION":
            # Enrich with full decision JSON from disk for UI rendering
            self._enrich_decision_data(data, intent_data)

        return {
            "type": intent.lower(),
            "intent_data": intent_data,
            "execution_plan": results.get("execution_log", []),
            "data": data,
            "answer": answer,
            "sources": ["DynamicExecutor"] + (results.get("execution_log", []) or []),
            "can_proceed": True,
            "execution_log": results.get("execution_log", []),
            "visualization": viz,
            # New: agent-level performance metadata
            "agent_results": results.get("agent_results", {}),
            "total_execution_time": results.get("total_execution_time"),
        }

    def _format_answer(self, results: Dict[str, Any], intent: str) -> str:
        """Convert executor results to human-readable answer."""
        if intent == "CO2_COMPARISON":
            dh = results.get("dh_tons_co2", 0)
            hp = results.get("hp_tons_co2", 0)
            winner = results.get("winner", "")
            return (
                f"District Heating: {dh:.1f} tCO₂/year vs Heat Pumps: {hp:.1f} tCO₂/year. "
                f"{winner} has lower emissions."
            )
        if intent == "LCOH_COMPARISON":
            dh = results.get("lcoh_dh_eur_per_mwh", 0)
            hp = results.get("lcoh_hp_eur_per_mwh", 0)
            winner = results.get("winner", "")
            return (
                f"LCOH DH: {dh:.1f} €/MWh vs HP: {hp:.1f} €/MWh. "
                f"{winner} has lower cost."
            )
        if intent == "VIOLATION_ANALYSIS":
            cha = results.get("cha", {})
            dha = results.get("dha", {})
            v_max = cha.get("velocity_ms_max", "N/A")
            p_max = cha.get("pressure_bar_max", "N/A")
            v_viol = dha.get("voltage_violations", 0)
            l_viol = dha.get("line_violations", 0)
            return (
                f"CHA: max velocity={v_max} m/s, max pressure={p_max} bar. "
                f"DHA: {v_viol} voltage violations, {l_viol} line violations."
            )
        if intent == "NETWORK_DESIGN":
            topo = results.get("topology", {})
            pipes = results.get("pipes", [])
            map_paths = results.get("map_paths", {})
            n_pipes = len(pipes) if isinstance(pipes, list) else 0
            n_buildings = (
                topo.get("spurs")
                or topo.get("buildings_connected")
                or len(results.get("heat_consumers", []))
                or "N/A"
            )
            n_trunk = topo.get("trunk_edges", "N/A")
            n_nodes = topo.get("trunk_nodes", "N/A")
            maps_available = ", ".join(map_paths.keys()) if map_paths else "none"
            return (
                f"The district heating network has {n_buildings} buildings connected, "
                f"{n_pipes} pipes, {n_trunk} trunk edges, and {n_nodes} trunk nodes. "
                f"Interactive maps available: {maps_available}."
            )
        if intent == "WHAT_IF_SCENARIO":
            mod = results.get("modification_applied", "N/A")
            comp = results.get("comparison", {})
            dp = comp.get("pressure_change_bar", 0)
            dq = comp.get("heat_delivered_change_mw", 0)
            return (
                f"What-if ({mod}): pressure change {dp:.4f} bar, "
                f"heat delivered change {dq:.4f} MW."
            )
        if intent == "EXPLAIN_DECISION":
            return self._format_decision_answer(results)
        return str(results)

    def _format_decision_answer(self, results: Dict[str, Any]) -> str:
        """Build rich human-readable answer for EXPLAIN_DECISION."""
        rec = (
            results.get("choice")
            or results.get("recommendation", "UNKNOWN")
        )
        reason_codes = results.get("reason_codes", [])
        reason = results.get("reason", "") or (
            ", ".join(reason_codes) if reason_codes else ""
        )
        robust = results.get("robust", False)
        metrics = results.get("metrics_used", {})

        reason_display = reason.replace("_", " ").lower() if reason else ""

        if rec == "DH":
            answer = (
                f"Recommendation: District Heating (DH). "
                f"Reason: {reason_display}."
            )
        elif rec == "HP":
            answer = (
                f"Recommendation: Heat Pumps (HP). "
                f"Reason: {reason_display}."
            )
        else:
            answer = f"Recommendation: {rec}. {reason_display}."

        # Append LCOH detail if available
        lcoh_dh = metrics.get("lcoh_dh_median")
        lcoh_hp = metrics.get("lcoh_hp_median")
        if lcoh_dh and lcoh_hp:
            answer += f" LCOH: DH = {lcoh_dh:.1f} €/MWh vs HP = {lcoh_hp:.1f} €/MWh."

        if not robust:
            answer += (
                " Note: this result is not robust "
                "(Monte Carlo analysis missing or inconclusive)."
            )
        return answer

    def _enrich_decision_data(
        self, data: Dict[str, Any], intent_data: Dict[str, Any]
    ) -> None:
        """
        Enrich executor result with full decision JSON from disk.

        The executor returns a compact dict from the DecisionAgent.  The UI
        needs the complete decision JSON (choice, reason_codes, metrics_used,
        robustness, etc.) so we load it here and merge into *data* in-place.
        """
        cluster_id = (
            (intent_data.get("entities") or {}).get("street_name")
            or data.get("street_id")
        )
        if not cluster_id:
            return

        dec_path = (
            resolve_cluster_path(cluster_id, "decision")
            / f"decision_{cluster_id}.json"
        )
        dec = _load_json(dec_path)
        if not dec:
            return

        # Normalise keys so UI can always read "recommendation" and "reason"
        rec = dec.get("choice") or dec.get("recommendation", "UNKNOWN")
        reason_codes = dec.get("reason_codes", [])
        dec["recommendation"] = rec
        dec["reason"] = dec.get("reason", "") or (
            ", ".join(reason_codes) if reason_codes else ""
        )

        # Merge full decision fields into data (executor fields win on conflict)
        for key, val in dec.items():
            data.setdefault(key, val)

    def _create_viz(self, results: Dict[str, Any], intent: str) -> Optional[Dict[str, Any]]:
        """Create visualization hint for UI (chart type, series, etc.)."""
        if intent == "CO2_COMPARISON":
            return {
                "chart_type": "bar",
                "series": [
                    {"name": "District Heating", "value": results.get("dh_tons_co2", 0)},
                    {"name": "Heat Pump", "value": results.get("hp_tons_co2", 0)},
                ],
                "x_label": "Option",
                "y_label": "tCO₂/year",
            }
        if intent == "LCOH_COMPARISON":
            return {
                "chart_type": "bar",
                "series": [
                    {"name": "District Heating", "value": results.get("lcoh_dh_eur_per_mwh", 0)},
                    {"name": "Heat Pump", "value": results.get("lcoh_hp_eur_per_mwh", 0)},
                ],
                "x_label": "Option",
                "y_label": "€/MWh",
            }
        if intent == "WHAT_IF_SCENARIO":
            return {
                "chart_type": "comparison",
                "baseline": results.get("baseline", {}),
                "scenario": results.get("scenario", {}),
            }
        if intent == "EXPLAIN_DECISION":
            metrics = results.get("metrics_used", {})
            rec = results.get("choice") or results.get("recommendation", "UNKNOWN")
            return {
                "chart_type": "decision",
                "recommendation": rec,
                "robust": results.get("robust", False),
                "reason_codes": results.get("reason_codes", []),
                "metrics": {
                    "lcoh_dh": metrics.get("lcoh_dh_median"),
                    "lcoh_hp": metrics.get("lcoh_hp_median"),
                    "co2_dh": metrics.get("co2_dh_median"),
                    "co2_hp": metrics.get("co2_hp_median"),
                },
            }
        return None

    def _handle_capability_fallback(
        self,
        user_query: str,
        intent: str,
        capability: Any,  # CapabilityResponse
        intent_data: Dict[str, Any],
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

    def get_system_capabilities(self) -> Dict[str, List[str]]:
        """Public API to show what the system can/cannot do."""
        return self.capability_guardrail.get_capabilities_summary()

    def _extract_street_from_query(self, user_query: str, context: Dict[str, Any]) -> Optional[str]:
        """Extract street/cluster from query using NLU and available streets."""
        from branitz_heat_decision.nlu import extract_street_entities

        available = context.get("available_streets") or _get_available_streets()
        return extract_street_entities(user_query, available)

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

    # NOTE: _handle_explain_request removed — EXPLAIN_DECISION is now routed
    # through the DynamicExecutor (DecisionAgent) with _enrich_decision_data
    # and _format_decision_answer handling the rich formatting.
