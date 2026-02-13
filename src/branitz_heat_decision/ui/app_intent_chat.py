"""
Standalone Intent Chat – chat-only UI with no street selection.

A minimal interface: just chat input and answers. Street/cluster is inferred
from the conversation or specified in the first message.

Run: PYTHONPATH=src streamlit run branitz_heat_decision.ui.app_intent_chat
Or:  cd /path/to/Branitz2 && PYTHONPATH=src streamlit run src/branitz_heat_decision/ui/app_intent_chat.py
"""

import os
import sys
from pathlib import Path

# Ensure src is in path
src_path = str(Path(__file__).parents[2])
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import streamlit as st
import pandas as pd

from branitz_heat_decision.ui.env import bootstrap_env
from branitz_heat_decision.config import resolve_cluster_path

bootstrap_env()

st.set_page_config(
    page_title="Branitz Intent Chat",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Minimal styling for a clean chat layout
st.markdown("""
<style>
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stChatInput { max-width: 700px; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)


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


def _get_default_cluster() -> str:
    """First available cluster, or empty string."""
    try:
        from branitz_heat_decision.ui.services import ClusterService
        svc = ClusterService()
        idx = svc.get_cluster_index()
        if not idx.empty:
            col = "cluster_id" if "cluster_id" in idx.columns else idx.columns[0]
            return str(idx.iloc[0][col])
    except Exception:
        pass
    try:
        from branitz_heat_decision.config import DATA_PROCESSED
        sc = DATA_PROCESSED / "street_clusters.parquet"
        if sc.exists():
            import pandas as pd
            df = pd.read_parquet(sc)
            if not df.empty and "street_id" in df.columns:
                return str(df.iloc[0]["street_id"])
    except Exception:
        pass
    return ""


def _get_cluster_id() -> str:
    """Cluster from session state or default."""
    if "intent_chat_cluster" not in st.session_state:
        st.session_state.intent_chat_cluster = _get_default_cluster()
    return st.session_state.intent_chat_cluster or ""


def main():
    col_title, col_clear = st.columns([3, 1])
    with col_title:
        st.title("🔧 Branitz Intent Chat")
        st.caption("Ask about CO₂, LCOH, violations, or decisions. No street selection needed.")
    with col_clear:
        if st.button("Clear chat", key="clear_chat"):
            st.session_state.intent_chat_messages = []
            st.rerun()

    # Collapsible street input – user can specify street in chat or here
    with st.expander("Street (optional)", expanded=False):
        default = _get_cluster_id()
        cluster_input = st.text_input(
            "Street ID",
            value=default,
            placeholder="e.g. ST010_HEINRICH_ZILLE_STRASSE",
            key="intent_chat_street_input",
            help="Leave empty to specify in your message, e.g. 'Compare CO2 for ST010'",
        )
        if cluster_input:
            st.session_state.intent_chat_cluster = cluster_input.strip()

    cluster_id = _get_cluster_id()

    # Messages – single session, no per-cluster split
    if "intent_chat_messages" not in st.session_state:
        st.session_state.intent_chat_messages = []

    messages = st.session_state.intent_chat_messages
    orch = _get_orchestrator()

    # Chat messages
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("execution_plan"):
                with st.expander("⚙️ What I calculated"):
                    for p in msg["execution_plan"]:
                        st.write(f"- {p}")
            # Inline mini-charts for CO2/LCOH
            if msg.get("role") == "assistant" and msg.get("type") not in ("fallback",):
                data = msg.get("data", {})
                if msg.get("type") == "co2_comparison" and data:
                    import altair as alt
                    df = pd.DataFrame([
                        {"Option": "District Heating", "tCO₂/year": data.get("co2_dh_t_per_a", 0)},
                        {"Option": "Heat Pump", "tCO₂/year": data.get("co2_hp_t_per_a", 0)},
                    ])
                    st.altair_chart(alt.Chart(df).mark_bar().encode(x="Option", y="tCO₂/year"), use_container_width=True)
                elif msg.get("type") == "lcoh_comparison" and data:
                    import altair as alt
                    df = pd.DataFrame([
                        {"Option": "District Heating", "€/MWh": data.get("lcoh_dh_eur_per_mwh", 0)},
                        {"Option": "Heat Pump", "€/MWh": data.get("lcoh_hp_eur_per_mwh", 0)},
                    ])
                    st.altair_chart(alt.Chart(df).mark_bar().encode(x="Option", y="€/MWh"), use_container_width=True)

    # Suggestions
    suggestions = orch.conversation.get_suggestions()
    if suggestions and cluster_id:
        st.caption("💡 Try asking:")
        cols = st.columns(min(len(suggestions), 3))
        for i, suggestion in enumerate(suggestions[:3]):
            with cols[i % 3]:
                if st.button(suggestion[:40], key=f"suggest_{i}"):
                    _process_message(suggestion, cluster_id, messages, orch)
                    st.rerun()

    # Chat input
    user_input = st.chat_input("Ask about CO₂, LCOH, violations...")
    if user_input:
        # Use cluster from input or session; if empty, try to extract from message
        effective_cluster = cluster_id
        if not effective_cluster:
            # Heuristic: look for ST### in message
            import re
            m = re.search(r"ST\d{3}_[\w_]+", user_input, re.I)
            if m:
                effective_cluster = m.group(0)
                st.session_state.intent_chat_cluster = effective_cluster
            else:
                effective_cluster = _get_default_cluster()
                if not effective_cluster:
                    messages.append({"role": "user", "content": user_input})
                    messages.append({
                        "role": "assistant",
                        "content": "Please specify a street: type the street ID (e.g. ST010_HEINRICH_ZILLE_STRASSE) in your message, or set it in the 'street' section above.",
                        "execution_plan": [],
                        "type": "fallback",
                        "data": {},
                    })
                    st.rerun()
                    return

        _process_message(user_input, effective_cluster, messages, orch)
        st.rerun()


def _process_message(user_input: str, cluster_id: str, messages: list, orch) -> None:
    messages.append({"role": "user", "content": user_input})
    context = {
        "street_id": cluster_id,
        "history": [m["content"] for m in messages[-5:]],
    }
    with st.spinner("Understanding request..."):
        try:
            response = orch.route_request(user_input, cluster_id, context)
        except Exception as e:
            response = {
                "type": "fallback",
                "answer": str(e),
                "suggestion": "Try: Compare CO₂ emissions",
            }
    if response["type"] == "fallback":
        messages.append({
            "role": "assistant",
            "content": response["answer"],
            "execution_plan": [],
            "type": "fallback",
            "data": {},
        })
    else:
        messages.append({
            "role": "assistant",
            "content": response["answer"],
            "execution_plan": response.get("execution_plan", []),
            "data": response.get("data", {}),
            "type": response.get("type", ""),
            "sources": response.get("sources", []),
        })


if __name__ == "__main__":
    main()
