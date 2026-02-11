"""
Dynamic Orchestrator – State-Aware Router for Branitz Heat Decision.

Phase 1: Intent-based tool selection.
Phase 2: DynamicExecutor for lazy, context-aware simulation execution.

Implements: "Try to achieve it with tools" – runs only the simulations needed
for the user's intent, using file-based cache to avoid redundant runs.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from branitz_heat_decision.config import resolve_cluster_path

logger = logging.getLogger(__name__)

# Simulation intents delegated to DynamicExecutor (Phase 2)
_EXECUTOR_INTENTS = frozenset({
    "CO2_COMPARISON", "LCOH_COMPARISON", "VIOLATION_ANALYSIS",
    "WHAT_IF_SCENARIO", "NETWORK_DESIGN",
})

# Lazy imports to avoid circular deps and optional deps
def _get_classify_intent():
    from branitz_heat_decision.nlu import classify_intent
    return classify_intent


def _get_executor():
    from branitz_heat_decision.agents.executor import DynamicExecutor
    return DynamicExecutor


def _get_adk_tools():
    from branitz_heat_decision.adk.tools import (
        run_cha_tool,
        run_dha_tool,
        run_economics_tool,
        run_decision_tool,
    )
    return run_cha_tool, run_dha_tool, run_economics_tool, run_decision_tool


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
    not a fixed sequence. Phase 2: delegates simulation execution to DynamicExecutor.
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

    def route_request(
        self,
        user_query: str,
        cluster_id: str,
        context: Optional[Dict[str, Any]] = None,
        run_missing: bool = True,
    ) -> Dict[str, Any]:
        """
        Main entry point: replaces linear run_pipeline().

        Args:
            user_query: Natural language request
            cluster_id: Street cluster ID (e.g. ST010_HEINRICH_ZILLE_STRASSE)
            context: Optional {"history": [...]}
            run_missing: If True, run simulations that are not yet cached; else only use cache

        Returns:
            {
                "type": "co2_comparison" | "lcoh_comparison" | "violation_analysis" | ...,
                "intent_data": {...},
                "execution_plan": ["cha", "dha", "economics"],
                "data": {...},
                "answer": "..."  (human-readable),
                "sources": ["CHA Simulation", "Cached Data"],
                "can_proceed": True/False
            }
        """
        context = context or {}
        classify_intent_fn = _get_classify_intent()

        # 1. UNDERSTAND (Phase 1)
        intent_data = classify_intent_fn(
            user_query,
            conversation_history=context.get("history", []),
            use_llm=True,
        )
        intent = str(intent_data.get("intent", "UNKNOWN")).upper().replace(" ", "_")

        # 2. UNKNOWN / CAPABILITY → Fallback
        if intent in ("UNKNOWN", "CAPABILITY_QUERY"):
            if intent == "CAPABILITY_QUERY":
                answer = (
                    "I can run: District Heating (CHA), Heat Pump grid (DHA), "
                    "Economics (cost & CO₂), and Decision comparison. Select a cluster and ask "
                    "'Compare CO₂', 'Compare costs', or 'Explain the decision'."
                )
            else:
                answer = _call_fallback_llm(user_query, intent_data)
            return {
                "type": "fallback",
                "intent_data": intent_data,
                "execution_plan": [],
                "data": {},
                "answer": answer,
                "sources": [],
                "can_proceed": False,
                "suggestion": "Try: 'Compare CO₂ emissions' or 'What is the LCOH for district heating?'",
            }

        # 3. ROUTE by intent
        # Phase 2: Simulation intents → DynamicExecutor
        if intent in _EXECUTOR_INTENTS:
            try:
                results = self.executor.execute(
                    intent=intent,
                    street_id=cluster_id,
                    context={
                        "modification": (intent_data.get("entities") or {}).get("modification"),
                        "history": context.get("history", []),
                        "run_missing": run_missing,
                    },
                )
                return self._format_executor_response(
                    intent=intent,
                    intent_data=intent_data,
                    results=results,
                )
            except ValueError as e:
                return {
                    "type": "fallback",
                    "intent_data": intent_data,
                    "execution_plan": [],
                    "data": {},
                    "answer": str(e),
                    "sources": [],
                    "can_proceed": False,
                }
            except Exception as e:
                logger.exception("Executor failed for intent=%s", intent)
                return {
                    "type": "ERROR",
                    "intent_data": intent_data,
                    "execution_plan": [],
                    "data": {},
                    "answer": f"Simulation failed: {str(e)}",
                    "sources": [],
                    "can_proceed": False,
                    "suggestion": "Please try a different query or check the street data.",
                }

        if intent == "EXPLAIN_DECISION":
            return self._handle_explain_request(cluster_id, intent_data, run_missing)

        # Unhandled intent
        return {
            "type": "fallback",
            "intent_data": intent_data,
            "execution_plan": [],
            "data": {},
            "answer": _call_fallback_llm(user_query, intent_data),
            "sources": [],
            "can_proceed": False,
        }

    def _format_executor_response(
        self,
        intent: str,
        intent_data: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Transform DynamicExecutor results to orchestrator response format.
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
            data["co2_hp_t_per_a"] = results.get("cha_tons_co2", 0)
        elif intent == "LCOH_COMPARISON":
            data["lcoh_dh_eur_per_mwh"] = results.get("lcoh_dh_eur_per_mwh", 0)
            data["lcoh_hp_eur_per_mwh"] = results.get("lcoh_hp_eur_per_mwh", 0)

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
        }

    def _format_answer(self, results: Dict[str, Any], intent: str) -> str:
        """Convert executor results to human-readable answer."""
        if intent == "CO2_COMPARISON":
            dh = results.get("dh_tons_co2", 0)
            cha = results.get("cha_tons_co2", 0)
            winner = results.get("winner", "")
            return (
                f"District Heating: {dh:.1f} tCO₂/year vs Heat Pumps: {cha:.1f} tCO₂/year. "
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
            n_pipes = len(pipes) if isinstance(pipes, list) else 0
            return (
                f"Network design: {n_pipes} pipes, topology info available. "
                "See data for details."
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
        return str(results)

    def _create_viz(self, results: Dict[str, Any], intent: str) -> Optional[Dict[str, Any]]:
        """Create visualization hint for UI (chart type, series, etc.)."""
        if intent == "CO2_COMPARISON":
            return {
                "chart_type": "bar",
                "series": [
                    {"name": "District Heating", "value": results.get("dh_tons_co2", 0)},
                    {"name": "Heat Pump", "value": results.get("cha_tons_co2", 0)},
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
        return None

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

    def _handle_explain_request(
        self,
        cluster_id: str,
        intent_data: Dict[str, Any],
        run_missing: bool,
    ) -> Dict[str, Any]:
        """Explain decision requires Decision (which needs CHA, DHA, Economics)."""
        required = ["cha", "dha", "economics", "decision"]
        execution_plan = self._compute_execution_plan(cluster_id, required)
        sources = []
        if execution_plan and run_missing:
            run_cha, run_dha, run_economics, run_decision = _get_adk_tools()
            for phase in execution_plan:
                if phase == "cha":
                    run_cha(cluster_id)
                elif phase == "dha":
                    run_dha(cluster_id)
                elif phase == "economics":
                    run_economics(cluster_id)
                elif phase == "decision":
                    run_decision(cluster_id)
            sources = ["CHA", "DHA", "Economics", "Decision"]
        else:
            sources = ["Cached Data"] if not execution_plan else ["Partial Cache"]

        dec_path = resolve_cluster_path(cluster_id, "decision") / f"decision_{cluster_id}.json"
        dec = _load_json(dec_path)
        rec = dec.get("recommendation", "UNKNOWN")
        reason = dec.get("reason", "") or dec.get("reason_codes", [""])[0] if dec.get("reason_codes") else ""

        answer = f"Recommendation: {rec}. {reason}"
        return {
            "type": "explain_decision",
            "intent_data": intent_data,
            "execution_plan": execution_plan if run_missing else required,
            "data": dec,
            "answer": answer,
            "sources": sources,
            "can_proceed": True,
        }
