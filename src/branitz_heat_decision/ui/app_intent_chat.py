"""
Branitz Intent Chat – Split Layout UI

Left panel:  Conversation (chat messages + input)
Right panel: Visualizations (maps, charts, metrics, agent trace)

Run: cd /path/to/Branitz2 && PYTHONPATH=src streamlit run src/branitz_heat_decision/ui/app_intent_chat.py
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure src is in path
src_path = str(Path(__file__).parents[2])
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from branitz_heat_decision.ui.env import bootstrap_env
from branitz_heat_decision.config import resolve_cluster_path

bootstrap_env()

st.set_page_config(
    page_title="Branitz Heat Decision AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ──
st.markdown("""
<style>
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Global font size increase */
    html, body, [class*="css"] {
        font-size: 18px;
    }

    /* Chat message text */
    .stChatMessage p, .stChatMessage li, .stChatMessage span {
        font-size: 1.05rem;
    }

    /* Metric labels and values */
    [data-testid="stMetricLabel"] { font-size: 1rem; }
    [data-testid="stMetricValue"] { font-size: 1.6rem; }

    /* Markdown text */
    .stMarkdown p { font-size: 1.05rem; line-height: 1.6; }
    .stMarkdown h3 { font-size: 1.4rem; }

    /* Captions slightly larger */
    .stCaption, small { font-size: 0.9rem; }

    /* Buttons */
    .stButton button { font-size: 0.95rem; }

    /* Expander headers */
    .streamlit-expanderHeader { font-size: 1rem; }

    /* Tighter padding for wide layout */
    .block-container { padding-top: 1.5rem; padding-bottom: 0; }

    /* Left panel: scrollable chat */
    [data-testid="column"]:first-child {
        border-right: 1px solid #e0e0e0;
        padding-right: 1rem;
    }

    /* Chat messages tighter */
    .stChatMessage { margin-bottom: 0.25rem; }

    /* Header bar */
    .header-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 2px solid #1e3c72;
        margin-bottom: 0.75rem;
    }
    .header-bar h2 { margin: 0; color: #1e3c72; }

    /* Context pill */
    .context-pill {
        display: inline-block;
        background: #eef2ff;
        border: 1px solid #1e3c72;
        border-radius: 20px;
        padding: 0.3rem 0.85rem;
        font-size: 0.95rem;
        color: #1e3c72;
        margin-bottom: 0.5rem;
    }

    /* Right panel header */
    .viz-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin-bottom: 0.75rem;
        text-align: center;
    }
    .viz-header h3 { font-size: 1.3rem; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──

def _get_orchestrator():
    if "orchestrator" not in st.session_state:
        from branitz_heat_decision.agents import BranitzOrchestrator
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            try:
                api_key = st.secrets.get("GOOGLE_API_KEY", "")
            except Exception:
                pass
        st.session_state.orchestrator = BranitzOrchestrator(api_key=api_key)
    return st.session_state.orchestrator


def _get_available_streets() -> List[str]:
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
            df = pd.read_parquet(sc)
            if not df.empty and "street_id" in df.columns:
                return df["street_id"].astype(str).tolist()
    except Exception:
        pass
    return []


def _get_default_cluster() -> str:
    streets = _get_available_streets()
    return streets[0] if streets else ""


def _get_cluster_id() -> str:
    if "intent_chat_cluster" not in st.session_state:
        st.session_state.intent_chat_cluster = _get_default_cluster()
    return st.session_state.intent_chat_cluster or ""


# ── Visualization Renderers (right panel) ──

def _render_co2(data: Dict[str, Any]):
    import altair as alt
    st.subheader("CO₂ Emissions Comparison")
    dh = data.get("co2_dh_t_per_a", 0)
    hp = data.get("co2_hp_t_per_a", 0)
    c1, c2 = st.columns(2)
    c1.metric("District Heating", f"{dh:.1f} t/year")
    c2.metric("Heat Pumps", f"{hp:.1f} t/year")
    df = pd.DataFrame([
        {"Option": "District Heating", "tCO₂/year": dh},
        {"Option": "Heat Pump", "tCO₂/year": hp},
    ])
    chart = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Option", axis=alt.Axis(labelAngle=0)),
        y="tCO₂/year",
        color=alt.Color("Option", scale=alt.Scale(
            domain=["District Heating", "Heat Pump"],
            range=["#1e3c72", "#e74c3c"],
        ), legend=None),
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)
    winner = "District Heating" if dh < hp else "Heat Pumps"
    st.success(f"{winner} has lower CO₂ emissions")


def _render_lcoh(data: Dict[str, Any]):
    import altair as alt
    st.subheader("Levelized Cost of Heat (LCOH)")
    dh = data.get("lcoh_dh_eur_per_mwh", 0)
    hp = data.get("lcoh_hp_eur_per_mwh", 0)
    c1, c2 = st.columns(2)
    c1.metric("District Heating", f"{dh:.1f} €/MWh")
    c2.metric("Heat Pumps", f"{hp:.1f} €/MWh")
    df = pd.DataFrame([
        {"Option": "District Heating", "€/MWh": dh},
        {"Option": "Heat Pump", "€/MWh": hp},
    ])
    chart = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Option", axis=alt.Axis(labelAngle=0)),
        y="€/MWh",
        color=alt.Color("Option", scale=alt.Scale(
            domain=["District Heating", "Heat Pump"],
            range=["#1e3c72", "#e74c3c"],
        ), legend=None),
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)
    winner = "District Heating" if dh < hp else "Heat Pumps"
    st.success(f"{winner} is more cost-effective")


def _render_violations(data: Dict[str, Any]):
    st.subheader("Network Violation Analysis")
    v_share = data.get("v_share_within_limits", 0) or 0
    v_pct = v_share * 100 if v_share <= 1 else v_share
    dp_max = data.get("dp_max_bar_per_100m", 0)
    c1, c2 = st.columns(2)
    c1.metric("Velocity Compliance", f"{v_pct:.1f}%")
    c2.metric("Max Pressure Drop", f"{dp_max:.3f} bar/100m")
    if v_pct < 100:
        st.warning("Some velocity violations detected")
    else:
        st.success("All velocities within limits")


def _render_network_design(data: Dict[str, Any], result_key: str = ""):
    st.subheader("District Heating Network")
    map_paths = data.get("map_paths", {})
    if map_paths:
        map_types = list(map_paths.keys())
        selected = st.selectbox(
            "Map layer",
            map_types,
            format_func=lambda x: x.capitalize(),
            key=f"viz_map_select_{result_key}",
        )
        html = Path(map_paths[selected]).read_text(encoding="utf-8")
        components.html(html, height=520, scrolling=True)
    else:
        st.info("No interactive maps available for this cluster.")
    topo = data.get("topology", {})
    if topo:
        c1, c2, c3 = st.columns(3)
        c1.metric("Trunk edges", topo.get("trunk_edges", "N/A"))
        c2.metric("Buildings", topo.get("buildings_connected", "N/A"))
        c3.metric("Service conns", topo.get("service_connections", "N/A"))


def _render_what_if(data: Dict[str, Any]):
    st.subheader("What-If Comparison")
    baseline = data.get("baseline", {})
    scenario = data.get("scenario", {})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Baseline**")
        st.metric("CO₂", f"{baseline.get('co2', 0):.1f} t/year")
        st.metric("LCOH", f"{baseline.get('lcoh', 0):.1f} €/MWh")
    with c2:
        st.markdown("**Scenario**")
        st.metric("CO₂", f"{scenario.get('co2', 0):.1f} t/year")
        st.metric("LCOH", f"{scenario.get('lcoh', 0):.1f} €/MWh")
    comp = data.get("comparison", {})
    if comp:
        st.caption(f"Pressure change: {comp.get('pressure_change_bar', 0):.4f} bar | "
                   f"Heat change: {comp.get('heat_delivered_change_mw', 0):.4f} MW")


def _render_fallback_ui(response: Dict[str, Any]):
    """Display fallback with structured capability information (Phase 5)."""
    data = response.get("data", {})
    category = data.get("category", response.get("category", "unknown"))

    # ── Main warning ──
    st.warning(response.get("answer", "This request is not supported."))

    # ── Capability category badge ──
    if category == "unsupported":
        st.error("**Not Supported** — This operation is outside the research scope")
    elif category == "partial":
        st.info("**Partially Supported** — Limited functionality available")
    elif category == "future":
        st.caption("**Future Work** — Planned for Phase 2 research")

    # ── Research context expander ──
    if response.get("is_research_boundary"):
        with st.expander("Research Context"):
            st.info(
                "This limitation is a **research objective**, not a bug. "
                "Documenting AI capability boundaries is part of the study."
            )
            research_note = data.get("research_note") or response.get("research_note")
            if research_note:
                st.caption(f"**Note**: {research_note}")

    # ── Alternative suggestions with icons ──
    alternatives = response.get("alternative_suggestions", [])
    if not alternatives:
        alternatives = data.get("alternatives", [])
    if alternatives:
        st.markdown("### What you CAN do instead:")
        for i, alt in enumerate(alternatives[:4]):
            if st.button(
                f"  {alt}",
                key=f"alt_{hash(str(alt))}_{i}",
                use_container_width=True,
            ):
                st.session_state._fallback_suggestion = alt
                st.rerun()

    # ── Full capabilities panel ──
    with st.expander("Full Capability List"):
        try:
            caps = _get_orchestrator().get_system_capabilities()
        except Exception:
            caps = {}

        supported = caps.get("fully_supported", [
            "Simulate DH networks (pandapipes)",
            "Analyze HP grid feasibility (pandapower)",
            "Compare LCOH and CO\u2082 emissions",
            "Check pressure/velocity violations",
            "Run what-if scenarios (remove houses)",
            "Generate decision explanations",
        ])
        partial = caps.get("partially_supported", [
            "Custom load profiles (BDEW only)",
        ])
        unsupported = caps.get("not_supported", [
            "Add/remove network components",
            "Real-time SCADA integration",
            "Legal compliance verification",
            "Multi-street optimization",
        ])

        st.markdown("**Fully Supported**")
        for item in supported:
            st.caption(f"  \u2022 {item}")

        st.markdown("**Partially Supported**")
        for item in partial:
            st.caption(f"  \u2022 {item}")

        st.markdown("**Not Supported**")
        for item in unsupported:
            st.caption(f"  \u2022 {item}")

    # ── Escalation path for manual intervention ──
    escalation = response.get("escalation_path") or data.get("escalation_path")
    if escalation == "manual_planning":
        st.info("This requires manual urban planning expertise.")


def _render_visualization(response: Dict[str, Any], result_key: str = ""):
    """Render the right-panel visualization for a response."""
    data = response.get("data", {})
    rtype = response.get("type", "")

    if rtype == "co2_comparison" and data:
        _render_co2(data)
    elif rtype == "lcoh_comparison" and data:
        _render_lcoh(data)
    elif rtype == "violation_analysis" and data:
        _render_violations(data)
    elif rtype == "network_design" and data:
        _render_network_design(data, result_key=result_key)
    elif rtype == "what_if_scenario" and data:
        _render_what_if(data)
    elif rtype == "explain_decision" and data:
        st.subheader("Decision Recommendation")
        rec = data.get("recommendation", "UNKNOWN")
        if rec == "DH":
            st.success("Recommended: District Heating")
        elif rec == "HP":
            st.info("Recommended: Heat Pumps")
        else:
            st.warning("Undecided or tied")
        if data.get("reason"):
            st.write(f"**Reason:** {data['reason']}")
    elif rtype == "guardrail_blocked":
        _render_fallback_ui(response)
    else:
        st.markdown(
            '<div class="viz-header"><h3>Ask a question to see results here</h3></div>',
            unsafe_allow_html=True,
        )
        st.caption("Try: 'Compare CO2 for Heinrich-Zille-Straße' or 'Show network layout'")


def _render_agent_trace(trace: List[Dict[str, Any]]):
    """Agent duty trace in an expander."""
    if not trace:
        return
    with st.expander("Agent Duty Trace", expanded=False):
        for step in trace:
            agent = step.get("agent", "?")
            duty = step.get("duty", "")
            outcome = step.get("outcome", "")
            st.markdown(f"**{agent}**")
            st.caption(f"Duty: {duty}")
            if outcome:
                st.caption(f"Outcome: {outcome}")
            extras = {k: v for k, v in step.items()
                      if k not in ("agent", "duty", "outcome") and v}
            if extras:
                st.json(extras)
            st.markdown("---")


# ── Message Processing ──

def _process_message(user_input: str, cluster_id: str, messages: list, orch) -> None:
    messages.append({"role": "user", "content": user_input})
    context = {
        "street_id": cluster_id,
        "history": [m["content"] for m in messages[-5:]],
        "available_streets": _get_available_streets(),
    }
    with st.spinner("Thinking..."):
        try:
            response = orch.route_request(user_input, cluster_id, context)
        except Exception as e:
            response = {
                "type": "fallback",
                "answer": str(e),
                "suggestion": "Try: Compare CO₂ emissions",
            }
    msg: Dict[str, Any] = {
        "role": "assistant",
        "content": response.get("answer", ""),
        "execution_plan": response.get("execution_plan", []),
        "data": response.get("data", {}),
        "type": response.get("type", "fallback"),
        "sources": response.get("sources", []),
        "agent_trace": response.get("agent_trace", []),
    }
    # Preserve guardrail-specific fields for _render_fallback_ui
    if response.get("type") == "guardrail_blocked":
        msg["is_research_boundary"] = response.get("is_research_boundary", False)
        msg["alternative_suggestions"] = response.get("alternative_suggestions", [])
        msg["escalation_path"] = response.get("escalation_path")
        msg["category"] = response.get("category", "unknown")
        msg["research_note"] = response.get("research_note")
    messages.append(msg)


# ── Main Layout ──

def main():
    orch = _get_orchestrator()
    cluster_id = _get_cluster_id()

    if "intent_chat_messages" not in st.session_state:
        st.session_state.intent_chat_messages = []
    messages = st.session_state.intent_chat_messages

    # ── Two-column split ──
    col_chat, col_viz = st.columns([2, 3], gap="medium")

    # ===== LEFT PANEL: Chat =====
    with col_chat:
        # Header
        hdr1, hdr2 = st.columns([3, 1])
        with hdr1:
            st.markdown("### Branitz Heat AI")
        with hdr2:
            if st.button("Clear", key="clear_chat", use_container_width=True):
                st.session_state.intent_chat_messages = []
                st.rerun()

        # Context pill
        if cluster_id:
            display_name = cluster_id.replace("_", " ").replace("ST0", "ST0")
            st.markdown(f'<span class="context-pill">📍 {display_name}</span>', unsafe_allow_html=True)

        # Street selector (collapsed)
        with st.expander("Change street", expanded=False):
            streets = _get_available_streets()
            if streets:
                idx = streets.index(cluster_id) if cluster_id in streets else 0
                chosen = st.selectbox(
                    "Street",
                    streets,
                    index=idx,
                    format_func=lambda x: x.replace("_", " "),
                    key="street_selector",
                    label_visibility="collapsed",
                )
                if chosen != cluster_id:
                    st.session_state.intent_chat_cluster = chosen
                    st.rerun()

        # Chat history
        chat_container = st.container(height=450)
        with chat_container:
            for msg in messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        # Suggestions
        suggestions = orch.conversation.get_suggestions()
        if suggestions:
            scols = st.columns(min(len(suggestions), 3))
            for i, s in enumerate(suggestions[:3]):
                with scols[i]:
                    if st.button(s[:35], key=f"sug_{i}", use_container_width=True):
                        _process_message(s, cluster_id, messages, orch)
                        st.rerun()

        # Handle fallback alternative suggestion clicks (from right panel)
        if "_fallback_suggestion" in st.session_state:
            _fb = st.session_state._fallback_suggestion
            del st.session_state._fallback_suggestion
            _process_message(_fb, cluster_id, messages, orch)
            st.rerun()

        # Chat input
        user_input = st.chat_input("Ask about CO₂, LCOH, violations, network...")
        if user_input:
            effective = cluster_id
            if not effective:
                import re
                m = re.search(r"ST\d{3}_[\w\-]+", user_input, re.I)
                if m:
                    effective = m.group(0)
                else:
                    available = _get_available_streets()
                    if available:
                        from branitz_heat_decision.nlu import extract_street_entities
                        effective = extract_street_entities(user_input, available)
                if effective:
                    st.session_state.intent_chat_cluster = effective
                else:
                    effective = _get_default_cluster()

            if not effective:
                messages.append({"role": "user", "content": user_input})
                messages.append({
                    "role": "assistant",
                    "content": "Please specify a street name in your message (e.g. 'Compare CO2 for Heinrich-Zille-Straße').",
                    "type": "fallback", "data": {}, "execution_plan": [], "agent_trace": [],
                })
                st.rerun()
                return

            _process_message(user_input, effective, messages, orch)
            st.rerun()

    # ===== RIGHT PANEL: All Results (scrollable) =====
    with col_viz:
        # Collect all assistant messages that have real results (not fallback)
        result_messages = [
            (i, msg) for i, msg in enumerate(messages)
            if msg.get("role") == "assistant"
            and msg.get("type") not in ("fallback", "", None)
            and msg.get("data")
        ]

        if result_messages:
            st.markdown(f"**{len(result_messages)} result(s)** — scroll to see all")
            viz_container = st.container(height=600)
            with viz_container:
                # Render each result in reverse chronological order (newest first)
                for idx, (msg_idx, msg) in enumerate(reversed(result_messages)):
                    turn_num = len(result_messages) - idx
                    # Find the user question that preceded this answer
                    user_q = ""
                    if msg_idx > 0 and messages[msg_idx - 1].get("role") == "user":
                        user_q = messages[msg_idx - 1]["content"]

                    # Section header
                    st.markdown(f"---")
                    st.markdown(f"**Result {turn_num}** — _{user_q}_" if user_q else f"**Result {turn_num}**")
                    st.caption(msg.get("content", ""))

                    # Visualization
                    _render_visualization(msg, result_key=str(msg_idx))

                    # Execution log + agent trace (collapsed)
                    detail_cols = st.columns(2)
                    with detail_cols[0]:
                        if msg.get("execution_plan"):
                            with st.expander("What was calculated"):
                                for p in msg["execution_plan"]:
                                    st.caption(f"• {p}")
                    with detail_cols[1]:
                        if msg.get("agent_trace"):
                            _render_agent_trace(msg["agent_trace"])

        else:
            st.markdown("")
            st.markdown("")
            st.markdown(
                '<div class="viz-header"><h3>Results will appear here</h3></div>',
                unsafe_allow_html=True,
            )
            st.markdown("")
            st.markdown("**Example questions:**")
            st.markdown("- Compare CO₂ for Heinrich-Zille-Straße")
            st.markdown("- What is the LCOH?")
            st.markdown("- Show me the network layout")
            st.markdown("- Check violations")
            st.markdown("- What if we remove 2 houses?")


if __name__ == "__main__":
    main()
