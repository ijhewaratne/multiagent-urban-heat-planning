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
        font-size: 22px;
    }

    /* Chat message text */
    .stChatMessage p, .stChatMessage li, .stChatMessage span {
        font-size: 1.3rem;
    }

    /* Metric labels and values */
    [data-testid="stMetricLabel"] { font-size: 1.25rem; }
    [data-testid="stMetricValue"] { font-size: 2rem; }

    /* Markdown text */
    .stMarkdown p { font-size: 1.3rem; line-height: 1.6; }
    .stMarkdown h3 { font-size: 1.75rem; }

    /* Captions slightly larger */
    .stCaption, small { font-size: 1.1rem; }

    /* Buttons */
    .stButton button { font-size: 1.2rem; }

    /* Expander headers */
    .streamlit-expanderHeader { font-size: 1.25rem; }

    /* Tighter padding for wide layout */
    .block-container { padding-top: 1.5rem; padding-bottom: 0; }

    /* Prevent tab strip from clipping under the page top edge */
    [data-testid="column"]:last-child .stTabs { margin-top: 0.4rem; }

    /* Left panel: scrollable chat */
    [data-testid="column"]:first-child {
        border-right: 1px solid #e0e0e0;
        padding-right: 1rem;
    }

    /* Chat messages tighter */
    .stChatMessage { margin-bottom: 0.25rem; }

    /* Context pill */
    .context-pill {
        display: inline-block;
        background: #eef2ff;
        border: 1px solid #1e3c72;
        border-radius: 20px;
        padding: 0.25rem 0.75rem;
        font-size: 1.05rem;
        color: #1e3c72;
        margin-bottom: 0.4rem;
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
    .viz-header h3 { font-size: 1.6rem; }

    /* Compact app header */
    .app-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        background: linear-gradient(135deg, #080f1f 0%, #0d2244 55%, #071830 100%);
        border-radius: 14px;
        padding: 0.85rem 1.2rem;
        margin-bottom: 0.75rem;
        border: 1px solid rgba(64, 224, 208, 0.18);
        box-shadow: 0 4px 20px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.04);
    }
    .app-header-title {
        font-weight: 800;
        font-size: 1.12rem;
        letter-spacing: 0.025em;
        margin: 0;
        background: linear-gradient(95deg, #ffffff 0%, #40e0d0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .app-header-sub {
        color: #5b8fae;
        font-size: 0.76rem;
        margin: 0;
        margin-top: 0.15rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }

    /* Recommendation badge */
    .rec-badge {
        display: inline-block;
        border-radius: 6px;
        padding: 0.35rem 0.9rem;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }
    .rec-dh { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
    .rec-hp { background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9; }
</style>
""", unsafe_allow_html=True)


_LOGO_SVG = """
<svg width="52" height="52" viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ff6b35"/>
      <stop offset="100%" stop-color="#40e0d0"/>
    </linearGradient>
    <linearGradient id="boltGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#40e0d0"/>
      <stop offset="100%" stop-color="#1e90ff"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="1.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <!-- Outer ring -->
  <circle cx="26" cy="26" r="24" fill="none" stroke="url(#ringGrad)" stroke-width="1.8" opacity="0.7"/>
  <!-- Heat-wave sine curve (district heating) -->
  <path d="M 5 26 Q 11 14 17 26 Q 23 38 29 26 Q 35 14 41 26 Q 44 32 47 26"
        fill="none" stroke="#ff6b35" stroke-width="2.4" stroke-linecap="round"
        filter="url(#glow)" opacity="0.9"/>
  <!-- Lightning bolt (heat pump / electricity) -->
  <path d="M 28 9 L 21 27 L 26.5 27 L 22 43 L 36 23 L 30 23 L 35 9 Z"
        fill="url(#boltGrad)" opacity="0.88" filter="url(#glow)"/>
  <!-- Centre dot -->
  <circle cx="26" cy="26" r="2.5" fill="#ffffff" opacity="0.55"/>
</svg>
"""


def _render_app_header() -> None:
    """Creative branded header with SVG heat-network logo."""
    st.markdown(
        f'<div class="app-header">'
        f'{_LOGO_SVG}'
        f'<div>'
        f'<p class="app-header-title">Branitz Heat AI</p>'
        f'<p class="app-header-sub">DH · HP · Decision Intelligence · Cottbus</p>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


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


def _get_cluster_id() -> str:
    """Get current cluster — starts empty, set from query text or street selector."""
    if "intent_chat_cluster" not in st.session_state:
        st.session_state.intent_chat_cluster = ""
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


def _render_hypothetical_what_if_preview(preview: Dict[str, Any]):
    st.markdown("### Hypothetical Preview")
    st.caption(
        preview.get(
            "disclaimer",
            "This preview is advisory only and does not mean the infrastructure change is supported.",
        )
    )

    baseline = preview.get("baseline", {})
    scenario = preview.get("scenario", {})
    comparison = preview.get("comparison", {})

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Current model**")
        st.metric("Approx. CO₂", f"{baseline.get('co2_tons', 0):.1f} t/year")
        st.metric("Max pressure", f"{baseline.get('max_pressure_bar', 0):.3f} bar")
    with c2:
        st.markdown("**Hypothetical scenario**")
        st.metric("Approx. CO₂", f"{scenario.get('co2_tons', 0):.1f} t/year")
        st.metric("Max pressure", f"{scenario.get('max_pressure_bar', 0):.3f} bar")

    if comparison:
        st.info(
            f"Pressure change: {comparison.get('pressure_change_bar', 0):.4f} bar | "
            f"Heat delivered change: {comparison.get('heat_delivered_change_mw', 0):.4f} MW | "
            f"Simplified violation reduction: {comparison.get('violation_reduction', 0)}"
        )


def _render_fallback_ui(response: Dict[str, Any], result_key: str = ""):
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

    hypothetical_preview = data.get("hypothetical_preview")
    if hypothetical_preview:
        _render_hypothetical_what_if_preview(hypothetical_preview)

    # ── Alternative suggestions with icons ──
    alternatives = response.get("alternative_suggestions", [])
    if not alternatives:
        alternatives = data.get("alternatives", [])
    if alternatives:
        st.markdown("### What you CAN do instead:")
        for i, alt in enumerate(alternatives[:4]):
            if st.button(
                f"  {alt}",
                key=f"alt_{hash(str(alt))}_{i}_{result_key}",
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


def _render_all_clusters() -> None:
    """Summary table of every analyzed cluster, read directly from results/ on disk."""
    st.subheader("All Analyzed Clusters")
    try:
        from branitz_heat_decision.ui.services import load_all_decisions
        df = load_all_decisions()
    except Exception as e:
        st.warning(f"Could not load cluster summaries: {e}")
        return

    if df.empty:
        st.info("No decision results found yet. Run simulations first.")
        return

    display_df = df.drop(columns=["_cluster_id"], errors="ignore")

    def _color_rec(val):
        if val == "DH":
            return "background-color: #e8f5e9; color: #2e7d32; font-weight: bold"
        if val == "HP":
            return "background-color: #e3f2fd; color: #1565c0; font-weight: bold"
        return ""

    def _color_feasible(val):
        if val == "✓":
            return "color: #2e7d32; font-weight: bold"
        if val == "✗":
            return "color: #c62828; font-weight: bold"
        return ""

    styled = (
        display_df.style
        .applymap(_color_rec, subset=["Recommendation"])
        .applymap(_color_feasible, subset=["DH Feasible", "HP Feasible"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Quick comparison bar chart
    import altair as alt
    if len(df) > 1:
        chart_data = []
        for _, row in df.iterrows():
            chart_data.append({"Cluster": row["Cluster"][:20], "Option": "DH", "LCOH": row["LCOH DH (€/MWh)"]})
            chart_data.append({"Cluster": row["Cluster"][:20], "Option": "HP", "LCOH": row["LCOH HP (€/MWh)"]})
        chart_df = pd.DataFrame(chart_data)
        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("Cluster:N", axis=alt.Axis(labelAngle=-20)),
                y=alt.Y("LCOH:Q", title="LCOH (€/MWh)"),
                color=alt.Color("Option:N", scale=alt.Scale(
                    domain=["DH", "HP"], range=["#1e3c72", "#e74c3c"]
                )),
                xOffset="Option:N",
            )
            .properties(title="LCOH Comparison Across Clusters", height=250)
        )
        st.altair_chart(chart, use_container_width=True)


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
        import altair as alt

        rec = data.get("choice") or data.get("recommendation", "UNKNOWN")
        reason_codes = data.get("reason_codes", [])
        robust = data.get("robust", False)
        contract = data.get("kpi_contract")

        # ── Verdict badge ──
        if rec == "DH":
            badge_cls = "rec-dh"
            badge_txt = "District Heating (DH)" + (" — robust decision" if robust else "")
        elif rec == "HP":
            badge_cls = "rec-hp"
            badge_txt = "Heat Pumps (HP)" + (" — robust decision" if robust else "")
        else:
            badge_cls, badge_txt = "rec-hp", "Undecided / tied"
        st.markdown(
            f'<span class="rec-badge {badge_cls}">Recommendation: {badge_txt}</span>',
            unsafe_allow_html=True,
        )

        # ── Causal narrative ──
        if contract:
            try:
                from branitz_heat_decision.uhdc.explainer import _build_decision_narrative
                narrative = _build_decision_narrative(
                    contract, {"choice": rec, "robust": robust, "reason_codes": reason_codes}
                )
                st.markdown(narrative)
            except Exception:
                contract = None

        if not contract:
            reason = ", ".join(r.replace("_", " ").lower() for r in reason_codes) if reason_codes else ""
            if reason:
                st.caption(f"Reason: {reason}")

        # ── Monte Carlo robustness bar ──
        if contract:
            mc = contract.get("monte_carlo", {})
            dh_wins = mc.get("dh_wins_fraction")
            hp_wins = mc.get("hp_wins_fraction")
            n_samples = mc.get("n_samples", 0)
            win_frac = (dh_wins if rec == "DH" else hp_wins) if (dh_wins is not None) else None
            if win_frac is not None:
                st.markdown(f"**Monte Carlo robustness** — {rec} preferred in **{win_frac*100:.0f}%** of {n_samples} scenarios")
                st.progress(float(win_frac))

        # ── LCOH + CO₂ comparison charts with 95% CI ──
        if contract:
            dh_c = contract.get("district_heating", {})
            hp_c = contract.get("heat_pumps", {})
            dh_lcoh = dh_c.get("lcoh", {})
            hp_lcoh = hp_c.get("lcoh", {})
            dh_co2 = dh_c.get("co2", {})
            hp_co2 = hp_c.get("co2", {})

            ch1, ch2 = st.columns(2)
            with ch1:
                if dh_lcoh.get("median") and hp_lcoh.get("median"):
                    df_lcoh = pd.DataFrame([
                        {"Option": "DH", "median": dh_lcoh["median"],
                         "p05": dh_lcoh.get("p05", dh_lcoh["median"]),
                         "p95": dh_lcoh.get("p95", dh_lcoh["median"])},
                        {"Option": "HP", "median": hp_lcoh["median"],
                         "p05": hp_lcoh.get("p05", hp_lcoh["median"]),
                         "p95": hp_lcoh.get("p95", hp_lcoh["median"])},
                    ])
                    bars = alt.Chart(df_lcoh).mark_bar(
                        cornerRadiusTopLeft=4, cornerRadiusTopRight=4
                    ).encode(
                        x=alt.X("Option:N", axis=alt.Axis(labelAngle=0), title=None),
                        y=alt.Y("median:Q", title="€/MWh"),
                        color=alt.Color("Option:N", scale=alt.Scale(
                            domain=["DH", "HP"], range=["#1e3c72", "#e74c3c"]
                        ), legend=None),
                    )
                    err = alt.Chart(df_lcoh).mark_errorbar(ticks=True).encode(
                        x="Option:N",
                        y=alt.Y("p05:Q", title="€/MWh"),
                        y2="p95:Q",
                    )
                    st.altair_chart((bars + err).properties(title="LCOH (95% CI)", height=220),
                                   use_container_width=True)

            with ch2:
                if dh_co2.get("median") and hp_co2.get("median"):
                    df_co2 = pd.DataFrame([
                        {"Option": "DH", "median": dh_co2["median"],
                         "p05": dh_co2.get("p05", dh_co2["median"]),
                         "p95": dh_co2.get("p95", dh_co2["median"])},
                        {"Option": "HP", "median": hp_co2["median"],
                         "p05": hp_co2.get("p05", hp_co2["median"]),
                         "p95": hp_co2.get("p95", hp_co2["median"])},
                    ])
                    bars_co2 = alt.Chart(df_co2).mark_bar(
                        cornerRadiusTopLeft=4, cornerRadiusTopRight=4
                    ).encode(
                        x=alt.X("Option:N", axis=alt.Axis(labelAngle=0), title=None),
                        y=alt.Y("median:Q", title="kg/MWh"),
                        color=alt.Color("Option:N", scale=alt.Scale(
                            domain=["DH", "HP"], range=["#1e3c72", "#e74c3c"]
                        ), legend=None),
                    )
                    err_co2 = alt.Chart(df_co2).mark_errorbar(ticks=True).encode(
                        x="Option:N",
                        y=alt.Y("p05:Q", title="kg/MWh"),
                        y2="p95:Q",
                    )
                    st.altair_chart((bars_co2 + err_co2).properties(title="CO₂ (95% CI)", height=220),
                                   use_container_width=True)

        # ── Validation footer ──
        val = data.get("validation", {})
        if val:
            val_status = val.get("validation_status", "")
            verified = val.get("verified_count", 0)
            total = val.get("statements_validated", 0)
            if val_status == "pass":
                st.success(f"Validation: PASS — {verified}/{total} claims verified")
            elif val_status == "fail":
                st.error(f"Validation: FAIL — {val.get('contradiction_count', 0)} contradictions")

        # ── Detailed AI explanation expander ──
        llm_expl = data.get("llm_explanation", "")
        if llm_expl:
            with st.expander("Detailed AI Analysis (Gemini)", expanded=False):
                st.markdown(llm_expl)
    elif rtype == "guardrail_blocked":
        _render_fallback_ui(response, result_key=result_key)
    else:
        st.markdown(
            '<div class="viz-header"><h3>Ask a question to see results here</h3></div>',
            unsafe_allow_html=True,
        )
        st.caption("Try: 'Compare CO2 for Heinrich-Zille-Straße' or 'Show network layout'")





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

    # Sync the pinned street to whatever the orchestrator actually resolved.
    # This handles cases where the Street Resolver found a new street from
    # NLU entities or conversation memory that differs from the UI default.
    resolved_street = (
        response.get("intent_data", {}).get("entities", {}).get("street_name")
    )
    if resolved_street and resolved_street != cluster_id:
        st.session_state.intent_chat_cluster = resolved_street

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
    # Store latest trace in session state so the graph panel can access it
    st.session_state["_latest_agent_trace"] = response.get("agent_trace", [])


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
        # Compact branded header
        _render_app_header()

        # Clear button — right-aligned without an empty ghost column
        _, btn_col = st.columns([4, 1])
        with btn_col:
            if st.button("Clear", key="clear_chat", use_container_width=True):
                st.session_state.intent_chat_messages = []
                st.rerun()

        # Street selector — always visible, no expander
        streets = _get_available_streets()
        options = [""] + streets
        idx = options.index(cluster_id) if cluster_id in options else 0
        chosen = st.selectbox(
            "Active street",
            options,
            index=idx,
            format_func=lambda x: x.replace("_", " ") if x else "— select a street —",
            key="street_selector",
        )
        if chosen != cluster_id:
            st.session_state.intent_chat_cluster = chosen
            st.rerun()

        # Chat history
        chat_container = st.container(height=500)
        with chat_container:
            for msg in messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        # Suggestion chips — full text, no truncation
        suggestions = orch.conversation.get_suggestions()
        if suggestions:
            scols = st.columns(min(len(suggestions), 3))
            for i, s in enumerate(suggestions[:3]):
                with scols[i]:
                    if st.button(s, key=f"sug_{i}", use_container_width=True):
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
            import re

            # Always try to extract a street from the new input so that
            # switching streets mid-conversation updates the pin.
            new_street = None
            m = re.search(r"ST\d{3}_[\w\-]+", user_input, re.I)
            if m:
                new_street = m.group(0)
            else:
                available = _get_available_streets()
                if available:
                    from branitz_heat_decision.nlu import extract_street_entities
                    new_street = extract_street_entities(user_input, available)

            if new_street:
                # User mentioned a (possibly different) street → update pin
                effective = new_street
                st.session_state.intent_chat_cluster = effective
            else:
                # No street in this message → keep current pin (for follow-ups)
                effective = cluster_id

            # Always call orchestrator (e.g. "list the streets" does not require a street)
            _process_message(user_input, effective, messages, orch)
            st.rerun()

    # ===== RIGHT PANEL: Tab per answer (newest first, up to 6) =====
    with col_viz:
        # Spacer so the tab strip aligns below the branded header on the left
        st.markdown(
            '<div style="height:0.55rem"></div>',
            unsafe_allow_html=True,
        )
        # Include every assistant message that has real content —
        # this captures both structured results AND plain follow-up answers.
        all_answers = [
            (i, msg) for i, msg in enumerate(messages)
            if msg.get("role") == "assistant"
            and msg.get("content", "").strip()
        ]
        recent = list(reversed(all_answers))[:6]

        _TYPE_ICON = {
            "explain_decision": "🏛",
            "co2_comparison": "♻️",
            "lcoh_comparison": "💶",
            "network_design": "🗺️",
            "violation_analysis": "⚠️",
            "what_if_scenario": "🔀",
            "guardrail_blocked": "🚧",
            "fallback": "💬",
        }

        def _tab_label(msg_idx: int, msg: dict) -> str:
            user_q = ""
            if msg_idx > 0 and messages[msg_idx - 1].get("role") == "user":
                user_q = messages[msg_idx - 1]["content"]
            icon = _TYPE_ICON.get(msg.get("type", ""), "💬")
            label = (user_q[:20] + "…") if len(user_q) > 20 else user_q
            return f"{icon} {label}" if label else f"{icon} Answer"

        if recent:
            tabs = st.tabs([_tab_label(mi, m) for mi, m in recent])
            for tab, (msg_idx, msg) in zip(tabs, recent):
                with tab:
                    rtype = msg.get("type", "")
                    data = msg.get("data", {})
                    content = msg.get("content", "")

                    # Structured visualizations take priority over raw text
                    _VIZ_TYPES = {
                        "explain_decision", "co2_comparison", "lcoh_comparison",
                        "network_design", "violation_analysis", "what_if_scenario",
                    }
                    if rtype in _VIZ_TYPES and data:
                        _render_visualization(msg, result_key=str(msg_idx))
                    elif rtype == "guardrail_blocked":
                        _render_fallback_ui(msg, result_key=str(msg_idx))
                    else:
                        # Plain text answer (follow-up, clarification, etc.)
                        if content:
                            st.markdown(content)

                    if msg.get("execution_plan"):
                        with st.expander("What was calculated", expanded=False):
                            for p in msg["execution_plan"]:
                                st.caption(f"• {p}")
        else:
            st.markdown(
                '<div class="viz-header"><h3>Results will appear here</h3></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                "**Try asking:** Explain the decision · Compare CO₂ · "
                "Show network layout · Check violations · What is the LCOH?"
            )

    # ===== BOTTOM PANEL: Execution Path Graph =====
    _render_execution_graph(messages)


def _render_execution_graph(messages: list):
    """Render an SVG branching left-to-right agent graph below the chat.

    Layout mirrors the walkthrough.md Mermaid diagram:
      User → UI → Orchestrator ─┬─ Intent Classifier
                                 └─ DynamicExecutor ─┬─ CHA  → 01_run_cha   ──┐
                                                      ├─ DHA  → 02_run_dha   ──┤
                                                      ├─ ECON → 03_run_econ  ──┼─→ results/
                                                      ├─ DEC  → cli/decision ──┤
                                                      └─ UHDC → cli/uhdc     ──┘
    """
    trace = st.session_state.get("_latest_agent_trace", [])

    _MAP = {
        "NLU Intent Classifier": "nlu", "Conversation Manager": "conv",
        "Street Resolver": "street", "Capability Guardrail": "guard",
        "Dynamic Executor": "exec",
        "CHAAgent": "cha", "CHA": "cha",
        "DHAAgent": "dha", "DHA": "dha",
        "EconomicsAgent": "econ", "Economics": "econ",
        "DecisionAgent": "dec", "Decision": "dec",
        "UHDCAgent": "uhdc", "UHDC": "uhdc",
    }

    active: set = set()
    blocked: set = set()
    if trace:
        active.update({"user", "ui", "orch"})
        for step in trace:
            # Handle the main agent for this step
            nid = _MAP.get(step.get("agent", ""))
            if nid:
                active.add(nid)
                out = str(step.get("outcome", ""))
                if "blocked" in out.lower() or "cannot" in out.lower() or "error" in out.lower() or "exception" in out.lower():
                    blocked.add(nid)
            
            # Domain agents are grouped inside the Executor's step under "agents_invoked"
            invoked = step.get("agents_invoked", {})
            for ag_name, info in invoked.items():
                ag_nid = _MAP.get(ag_name) or ag_name.lower()
                if ag_nid in ["cha", "dha", "econ", "dec", "uhdc", "economics", "decision"]:
                    # Normalize 'economics' to 'econ', etc.
                    if ag_nid == "economics": ag_nid = "econ"
                    if ag_nid == "decision": ag_nid = "dec"
                    
                    active.add(ag_nid)
                    if info.get("success") is False:
                        blocked.add(ag_nid)
        sims = {"cha", "dha", "econ", "dec", "uhdc"}
        if active & sims:
            active.update({"res"})
            for s in sims & active:
                active.add(f"s_{s}")

    # ── SVG helpers ──
    W, H = 1200, 380  # viewBox

    def _fill(nid):
        if nid in blocked: return "#ff9800"
        if nid in active:  return "#1e3c72"
        return "#e0e0e0"

    def _fg(nid):
        if nid in blocked: return "#000"
        if nid in active:  return "#fff"
        return "#888"

    def _stroke(nid):
        if nid in blocked: return "#e65100"
        if nid in active:  return "#4caf50"
        return "#ccc"

    def _line_c(a, b):
        if a in active and b in active: return "#4caf50"
        return "#d0d0d0"

    def rect(x, y, w, h, nid, label, rx=6):
        f, fg, s = _fill(nid), _fg(nid), _stroke(nid)
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{f}" stroke="{s}" stroke-width="2"/>'
            f'<text x="{x+w/2}" y="{y+h/2+4}" text-anchor="middle" '
            f'fill="{fg}" font-size="11" font-family="sans-serif">{label}</text>'
        )

    def circle(cx, cy, r, nid, label):
        f, fg, s = _fill(nid), _fg(nid), _stroke(nid)
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{f}" stroke="{s}" stroke-width="2"/>'
            f'<text x="{cx}" y="{cy+4}" text-anchor="middle" '
            f'fill="{fg}" font-size="11" font-family="sans-serif">{label}</text>'
        )

    def cylinder(x, y, w, h, nid, label):
        """Draw a cylinder (database) shape."""
        f, fg, s = _fill(nid), _fg(nid), _stroke(nid)
        ry = 8
        return (
            f'<ellipse cx="{x+w/2}" cy="{y+ry}" rx="{w/2}" ry="{ry}" '
            f'fill="{f}" stroke="{s}" stroke-width="2"/>'
            f'<rect x="{x}" y="{y+ry}" width="{w}" height="{h-2*ry}" '
            f'fill="{f}" stroke="{s}" stroke-width="2"/>'
            f'<ellipse cx="{x+w/2}" cy="{y+h-ry}" rx="{w/2}" ry="{ry}" '
            f'fill="{f}" stroke="{s}" stroke-width="2"/>'
            # Cover the internal border between rect and top ellipse
            f'<rect x="{x+1}" y="{y+ry}" width="{w-2}" height="4" fill="{f}"/>'
            f'<text x="{x+w/2}" y="{y+h/2+4}" text-anchor="middle" '
            f'fill="{fg}" font-size="11" font-family="sans-serif">{label}</text>'
        )

    def line(x1, y1, x2, y2, a_id, b_id):
        c = _line_c(a_id, b_id)
        sw = "2.5" if c == "#4caf50" else "1.5"
        return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="{c}" stroke-width="{sw}"/>')

    def arrow_head(x, y, a_id, b_id, direction="right"):
        c = _line_c(a_id, b_id)
        if direction == "right":
            pts = f"{x-6},{y-4} {x},{y} {x-6},{y+4}"
        else:
            pts = f"{x},{y-4} {x+6},{y} {x},{y+4}"
        return f'<polygon points="{pts}" fill="{c}"/>'

    def edge_label(x, y, text, a_id, b_id):
        c = _line_c(a_id, b_id)
        return (f'<text x="{x}" y="{y}" text-anchor="middle" '
                f'fill="{c}" font-size="9" font-style="italic" '
                f'font-family="sans-serif">{text}</text>')

    # ── Node positions ──
    # Col 1: User (circle)
    user_cx, user_cy = 35, 190
    # Col 2: Streamlit UI
    ui_x, ui_y, ui_w, ui_h = 80, 172, 105, 36
    # Col 3: Orchestrator
    or_x, or_y, or_w, or_h = 225, 172, 110, 36
    # Col 4 top: Intent Classifier
    nlu_x, nlu_y, nlu_w, nlu_h = 410, 40, 130, 32
    # Col 4 bot: DynamicExecutor
    ex_x, ex_y, ex_w, ex_h = 410, 172, 140, 36
    # Col 5: Domain agents (stacked)
    agents = [
        ("cha",  "CHA Agent",    60),
        ("dha",  "DHA Agent",    125),
        ("econ", "Economics",    190),
        ("dec",  "Decision",     255),
        ("uhdc", "UHDC Report",  320),
    ]
    ag_x, ag_w, ag_h = 610, 120, 30
    # Col 6: Scripts
    scripts = [
        ("s_cha",  "01_run_cha.py",      60),
        ("s_dha",  "02_run_dha.py",      125),
        ("s_econ", "03_run_econ.py",     190),
        ("s_dec",  "cli/decision.py",    255),
        ("s_uhdc", "cli/uhdc.py",        320),
    ]
    sc_x, sc_w, sc_h = 790, 130, 30
    # Col 7: results/ (cylinder)
    res_x, res_y, res_w, res_h = 990, 150, 90, 80

    # ── Build SVG ──
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="width:100%; height:auto; max-height:350px;">']

    # Edges first (behind nodes)
    # User → UI
    parts.append(line(user_cx+18, user_cy, ui_x, ui_y+ui_h/2, "user", "ui"))
    parts.append(arrow_head(ui_x, ui_y+ui_h/2, "user", "ui"))
    # UI → Orch
    parts.append(line(ui_x+ui_w, ui_y+ui_h/2, or_x, or_y+or_h/2, "ui", "orch"))
    parts.append(arrow_head(or_x, or_y+or_h/2, "ui", "orch"))
    parts.append(edge_label(170, ui_y-2, "Chat / Click", "ui", "orch"))
    # Orch → NLU (branch up, "classify intent")
    parts.append(line(or_x+or_w/2, or_y, nlu_x+nlu_w/2, nlu_y+nlu_h, "orch", "nlu"))
    parts.append(arrow_head(nlu_x+nlu_w/2, nlu_y+nlu_h, "orch", "nlu", "left"))
    parts.append(edge_label(or_x+or_w/2+35, or_y-10, "classify", "orch", "nlu"))
    # NLU → Orch (return intent result)
    nlu_ret_c = _line_c("nlu", "orch")
    parts.append(
        f'<path d="M {nlu_x} {nlu_y+nlu_h/2} '
        f'Q {or_x+or_w+10} {nlu_y+nlu_h/2} {or_x+or_w} {or_y}" '
        f'fill="none" stroke="{nlu_ret_c}" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )
    parts.append(edge_label(or_x+or_w-15, nlu_y+nlu_h/2-6, "intent result", "nlu", "orch"))
    # Orch → Executor (only the Orchestrator calls the executor)
    parts.append(line(or_x+or_w, or_y+or_h/2, ex_x, ex_y+ex_h/2, "orch", "exec"))
    parts.append(arrow_head(ex_x, ex_y+ex_h/2, "orch", "exec"))
    parts.append(edge_label((or_x+or_w+ex_x)/2, ex_y+ex_h+14, "Execute", "orch", "exec"))
    # Executor → each agent
    for nid, _, ay in agents:
        parts.append(line(ex_x+ex_w, ex_y+ex_h/2, ag_x, ay+ag_h/2, "exec", nid))
        parts.append(arrow_head(ag_x, ay+ag_h/2, "exec", nid))
    # Agent → Script
    for (nid, _, ay), (sid, _, _) in zip(agents, scripts):
        parts.append(line(ag_x+ag_w, ay+ag_h/2, sc_x, ay+sc_h/2, nid, sid))
        parts.append(arrow_head(sc_x, ay+sc_h/2, nid, sid))
    # Script → Results
    for sid, _, sy in scripts:
        parts.append(line(sc_x+sc_w, sy+sc_h/2, res_x, res_y+res_h/2, sid, "res"))
    parts.append(arrow_head(res_x, res_y+res_h/2, "s_econ", "res"))
    # Results → UI (curved return)
    rc = _line_c("res", "ui")
    parts.append(
        f'<path d="M {res_x+res_w/2} {res_y+res_h} '
        f'Q {res_x+res_w/2} {H-10} {ui_x+ui_w/2} {H-10} '
        f'L {ui_x+ui_w/2} {ui_y+ui_h}" '
        f'fill="none" stroke="{rc}" stroke-width="1.5" stroke-dasharray="6,3"/>'
    )

    # Nodes (on top)
    parts.append(circle(user_cx, user_cy, 18, "user", "User"))
    parts.append(rect(ui_x, ui_y, ui_w, ui_h, "ui", "Streamlit UI"))
    parts.append(rect(or_x, or_y, or_w, or_h, "orch", "Orchestrator"))
    parts.append(rect(nlu_x, nlu_y, nlu_w, nlu_h, "nlu", "Intent Classifier"))
    parts.append(rect(ex_x, ex_y, ex_w, ex_h, "exec", "DynamicExecutor"))
    for nid, label, ay in agents:
        parts.append(rect(ag_x, ay, ag_w, ag_h, nid, label))
    for sid, label, sy in scripts:
        parts.append(rect(sc_x, sy, sc_w, sc_h, sid, label))
    parts.append(cylinder(res_x, res_y, res_w, res_h, "res", "results/"))

    # Artifacts label
    parts.append(edge_label(950, 100, "Artifacts", "s_cha", "res"))

    # Legend
    ly = H - 12
    parts.append(f'<circle cx="350" cy="{ly}" r="5" fill="#4caf50"/>')
    parts.append(f'<text x="360" y="{ly+4}" font-size="10" fill="#666" font-family="sans-serif">Active</text>')
    parts.append(f'<circle cx="420" cy="{ly}" r="5" fill="#e0e0e0" stroke="#ccc" stroke-width="1"/>')
    parts.append(f'<text x="430" y="{ly+4}" font-size="10" fill="#666" font-family="sans-serif">Idle</text>')
    parts.append(f'<circle cx="475" cy="{ly}" r="5" fill="#ff9800"/>')
    parts.append(f'<text x="485" y="{ly+4}" font-size="10" fill="#666" font-family="sans-serif">Blocked</text>')

    parts.append('</svg>')

    title = "🔍 Agent Execution Path" if trace else "🔍 Agent Pipeline (idle)"
    wrapper = (
        f'<div style="padding:0.8rem 1rem; background:#f8f9fa; '
        f'border:1px solid #e0e0e0; border-radius:12px; margin-top:1rem;">'
        f'<div style="text-align:center; font-weight:600; color:#1e3c72; '
        f'font-size:0.95rem; margin-bottom:0.4rem;">{title}</div>'
        + "\n".join(parts)
        + '</div>'
    )
    st.markdown(wrapper, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
