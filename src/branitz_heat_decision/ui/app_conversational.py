"""
Branitz Conversational Interface - Chat-First UI

No pre-selection required. Users just start talking.
The agent extracts context from conversation or asks for clarification.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup path
src_path = str(Path(__file__).parents[2])
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import streamlit as st
import pandas as pd

from branitz_heat_decision.ui.env import bootstrap_env

bootstrap_env()

st.set_page_config(
    page_title="Branitz AI - Conversational Interface",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for chat-first interface
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .chat-container {
        max-width: 800px;
        margin: 0 auto;
    }
    .context-bar {
        background-color: #f8f9fa;
        padding: 1rem;
        border-left: 4px solid #2a5298;
        margin-bottom: 1rem;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


def _get_orchestrator():
    if "orchestrator" not in st.session_state:
        from branitz_heat_decision.agents import BranitzOrchestrator

        api_key = os.getenv("GOOGLE_API_KEY", "")
        try:
            api_key = api_key or st.secrets.get("GOOGLE_API_KEY", "")
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


def _extract_street_from_query(query: str, available_streets: List[str]) -> Optional[str]:
    from branitz_heat_decision.nlu import extract_street_entities
    return extract_street_entities(query, available_streets)


def _display_chat_message(role: str, content: str, metadata: Optional[Dict] = None):
    with st.chat_message(role):
        st.write(content)
        if metadata:
            if metadata.get("execution_log"):
                with st.expander("⚙️ What was calculated"):
                    for log in metadata["execution_log"]:
                        st.caption(f"• {log}")
            if metadata.get("agent_trace"):
                with st.expander("🤖 Agent Duty Trace"):
                    for step in metadata["agent_trace"]:
                        agent_name = step.get("agent", "?")
                        duty = step.get("duty", "")
                        outcome = step.get("outcome", "")
                        st.markdown(f"**{agent_name}**")
                        st.caption(f"Duty: {duty}")
                        if outcome:
                            st.caption(f"Outcome: {outcome}")
                        extras = {k: v for k, v in step.items()
                                  if k not in ("agent", "duty", "outcome") and v}
                        if extras:
                            st.json(extras)
                        st.markdown("---")
            if metadata.get("sources"):
                st.caption(f"📊 Sources: {', '.join(metadata['sources'])}")


def _render_visualization(response: Dict[str, Any]):
    viz_data = response.get("data", {})
    resp_type = response.get("type", "")

    if resp_type == "co2_comparison":
        st.subheader("🌍 CO₂ Emissions Comparison")
        col1, col2 = st.columns(2)
        dh_co2 = viz_data.get("co2_dh_t_per_a", 0)
        hp_co2 = viz_data.get("co2_hp_t_per_a", 0)
        with col1:
            st.metric("District Heating", f"{dh_co2:.1f} t/year")
        with col2:
            st.metric("Heat Pumps", f"{hp_co2:.1f} t/year")
        import altair as alt
        df = pd.DataFrame([
            {"Option": "District Heating", "Emissions": dh_co2},
            {"Option": "Heat Pumps", "Emissions": hp_co2},
        ])
        chart = alt.Chart(df).mark_bar().encode(
            x="Option",
            y="Emissions",
            color=alt.Color("Option", scale=alt.Scale(
                domain=["District Heating", "Heat Pumps"],
                range=["#1e3c72", "#e74c3c"],
            )),
        )
        st.altair_chart(chart, use_container_width=True)
        winner = "District Heating" if dh_co2 < hp_co2 else "Heat Pumps"
        st.success(f"✅ {winner} has lower CO₂ emissions")

    elif resp_type == "lcoh_comparison":
        st.subheader("💰 Levelized Cost of Heat (LCOH)")
        col1, col2 = st.columns(2)
        dh_lcoh = viz_data.get("lcoh_dh_eur_per_mwh", 0)
        hp_lcoh = viz_data.get("lcoh_hp_eur_per_mwh", 0)
        with col1:
            st.metric("District Heating", f"{dh_lcoh:.1f} €/MWh")
        with col2:
            st.metric("Heat Pumps", f"{hp_lcoh:.1f} €/MWh")
        winner = "District Heating" if dh_lcoh < hp_lcoh else "Heat Pumps"
        st.success(f"✅ {winner} is more cost-effective")

    elif resp_type == "violation_analysis":
        st.subheader("⚠️ Network Violations")
        v_share = viz_data.get("v_share_within_limits", 0) or 0
        v_pct = v_share * 100 if v_share <= 1 else v_share
        dp_max = viz_data.get("dp_max_bar_per_100m", 0)
        col1, col2 = st.columns(2)
        col1.metric("Velocity Compliance", f"{v_pct:.1f}%")
        col2.metric("Max Pressure Drop", f"{dp_max:.3f} bar/100m")
        if v_pct < 100:
            st.warning("⚠️ Some velocity violations detected")
        else:
            st.success("✅ All velocities within limits")

    elif resp_type == "network_design":
        st.subheader("🗺️ District Heating Network Layout")
        map_paths = viz_data.get("map_paths", {})
        if map_paths:
            map_types = list(map_paths.keys())
            selected_map = st.selectbox(
                "Select map layer",
                map_types,
                format_func=lambda x: x.capitalize(),
                key="network_map_select",
            )
            map_file = map_paths.get(selected_map)
            if map_file:
                from pathlib import Path as _Path
                html_content = _Path(map_file).read_text(encoding="utf-8")
                import streamlit.components.v1 as components
                components.html(html_content, height=550, scrolling=True)
        else:
            st.info("No interactive maps available for this cluster.")
        # Topology summary
        topo = viz_data.get("topology", {})
        if topo:
            st.markdown("**Network topology**")
            cols = st.columns(3)
            cols[0].metric("Trunk edges", topo.get("trunk_edges", "N/A"))
            cols[1].metric("Buildings connected", topo.get("buildings_connected", "N/A"))
            cols[2].metric("Service connections", topo.get("service_connections", "N/A"))

    elif resp_type == "explain_decision":
        st.subheader("🎯 Decision Recommendation")
        rec = viz_data.get("recommendation", "UNKNOWN")
        if rec == "DH":
            st.success("🏭 Recommended: District Heating")
        elif rec == "HP":
            st.info("⚡ Recommended: Heat Pumps")
        else:
            st.warning("⚖️ Undecided or tied")
        if viz_data.get("reason"):
            st.write(f"**Reason:** {viz_data['reason']}")

    elif resp_type == "guardrail_blocked":
        st.warning(response.get("answer", "This request is not supported."))
        # Research context (Phase 5 — for thesis demonstration)
        if response.get("is_research_boundary"):
            with st.expander("Research Context"):
                st.info(
                    "This limitation is a **research objective**, not a bug. "
                    "Documenting AI capability boundaries is part of the study."
                )
                if viz_data.get("research_note"):
                    st.caption(f"Note: {viz_data['research_note']}")
                if viz_data.get("category"):
                    st.caption(f"Category: {viz_data['category']}")
        # Alternative suggestions
        alternatives = response.get("alternative_suggestions", [])
        if alternatives:
            st.markdown("**Instead, you can:**")
            cols = st.columns(min(len(alternatives), 2))
            for i, suggestion in enumerate(alternatives[:4]):
                with cols[i % 2]:
                    if st.button(f"{suggestion}", key=f"conv_alt_{i}", use_container_width=True):
                        st.session_state.next_prompt = suggestion
                        st.rerun()
        # Escalation path
        if response.get("escalation_path") == "manual_planning":
            st.info("This requires manual urban planning expertise.")


def _render_suggestions(orchestrator):
    suggestions = orchestrator.conversation.get_suggestions()
    if suggestions:
        st.markdown("**Try asking:**")
        cols = st.columns(min(len(suggestions), 3))
        for i, suggestion in enumerate(suggestions[:3]):
            with cols[i]:
                if st.button(f"💡 {suggestion[:35]}", key=f"sugg_{i}", use_container_width=True):
                    st.session_state.next_prompt = suggestion
                    st.rerun()


# Initialize session state
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "current_context" not in st.session_state:
    st.session_state.current_context = {
        "street_id": None,
        "street_name": None,
        "last_visualization": None,
    }

# Header
st.markdown("""
<div class="main-header">
    <h1>🏙️ Branitz Heat Decision AI</h1>
    <p>Just ask me about district heating, heat pumps, or CO₂ emissions for any street</p>
</div>
""", unsafe_allow_html=True)

# Main chat container
with st.container():
    if st.session_state.current_context["street_id"]:
        disp = st.session_state.current_context["street_name"] or st.session_state.current_context["street_id"]
        st.markdown(f"""
        <div class="context-bar">
            <strong>📍 Current Context:</strong> {disp}
            <br><small>All calculations use this street unless you specify another</small>
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.conversation_history:
        _display_chat_message(msg["role"], msg["content"], msg.get("metadata"))

    # Handle pre-filled suggestion
    if "next_prompt" in st.session_state:
        user_input = st.session_state.next_prompt
        del st.session_state.next_prompt
    else:
        user_input = st.chat_input("Ask me anything... (e.g., 'Compare CO2 for Heinrich-Zille-Straße')")

    if user_input:
        st.session_state.conversation_history.append({"role": "user", "content": user_input})

        orchestrator = _get_orchestrator()
        current_street = st.session_state.current_context["street_id"]

        if not current_street:
            available = _get_available_streets()
            extracted = _extract_street_from_query(user_input, available)
            if extracted:
                st.session_state.current_context["street_id"] = extracted
                st.session_state.current_context["street_name"] = extracted
                current_street = extracted

        if not current_street:
            st.session_state.conversation_history.append({
                "role": "assistant",
                "content": (
                    "I'd be happy to help! Could you please specify which street you'd like to analyze? "
                    "You can mention the street name in your question (e.g. 'Compare CO2 for Heinrich-Zille-Straße')."
                ),
                "metadata": {"awaiting_street": True},
            })
            st.rerun()

        with st.spinner("Thinking..."):
            try:
                context = {
                    "street_id": current_street,
                    "history": [m["content"] for m in st.session_state.conversation_history[-5:]],
                    "available_streets": _get_available_streets(),
                }
                response = orchestrator.route_request(user_input, current_street, context)

                if response.get("type") == "CLARIFICATION_NEEDED":
                    st.session_state.conversation_history.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "metadata": {
                            "execution_log": [],
                            "sources": [],
                            "agent_trace": response.get("agent_trace", []),
                        },
                    })
                    st.rerun()
                    st.stop()

                if response.get("intent_data", {}).get("entities", {}).get("street_name"):
                    new_street = response["intent_data"]["entities"]["street_name"]
                    if new_street != current_street:
                        st.session_state.current_context["street_id"] = new_street
                        st.session_state.current_context["street_name"] = new_street

                metadata = {
                    "execution_log": response.get("execution_log", []),
                    "sources": response.get("sources", []),
                    "type": response.get("type"),
                    "agent_trace": response.get("agent_trace", []),
                }
                st.session_state.conversation_history.append({
                    "role": "assistant",
                    "content": response["answer"],
                    "metadata": metadata,
                })
                st.session_state.current_context["last_visualization"] = response
                st.rerun()

            except Exception as e:
                st.session_state.conversation_history.append({
                    "role": "assistant",
                    "content": f"I encountered an error: {str(e)}. Please try again or ask for help.",
                    "metadata": {"error": True},
                })
                st.rerun()

# Visualization area
if st.session_state.current_context["last_visualization"]:
    st.markdown("---")
    st.subheader("📊 Analysis Results")
    _render_visualization(st.session_state.current_context["last_visualization"])
    _render_suggestions(st.session_state.orchestrator)

# Sidebar
with st.sidebar:
    st.title("💬 Help")
    st.markdown("""
    **I can help you with:**
    - Compare CO₂ emissions between District Heating and Heat Pumps
    - Calculate LCOH (Levelized Cost of Heat)
    - Check network violations (pressure, velocity)
    - Explain recommendations
    - "What-if" scenarios (e.g., removing houses)

    **Example questions:**
    - "Compare CO2 for Heinrich-Zille-Straße"
    - "What is the LCOH?"
    - "What about violations?" (follow-up)
    - "What if we remove 2 houses?"
    """)
    with st.expander("📍 Available Streets"):
        streets = _get_available_streets()
        if streets:
            for street in streets[:10]:
                st.caption(f"• {street}")
            if len(streets) > 10:
                st.caption(f"... and {len(streets) - 10} more")
        else:
            st.warning("No streets found in database")
    if st.button("🗑️ Clear Conversation"):
        st.session_state.conversation_history = []
        st.session_state.current_context = {
            "street_id": None,
            "street_name": None,
            "last_visualization": None,
        }
        st.rerun()
