"""
Thesis Figures Generator
Produces all 17 publication-quality figures into results/thesis/figures/
"""

import sys
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch

RESULTS = Path("results")
OUT_DIR = RESULTS / "thesis" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Cluster assignments — all figures use ST010
CID_ECON = "ST010_HEINRICH_ZILLE_STRASSE"
CID_HYD  = "ST010_HEINRICH_ZILLE_STRASSE"
CID_DHA  = "ST010_HEINRICH_ZILLE_STRASSE"

LABEL_ECON = "Heinrich-Zille-Straße (ST010)"
LABEL_HYD  = "Heinrich-Zille-Straße (ST010)"

# Colour palette
C_DH   = "#c0392b"
C_HP   = "#1a5276"
C_DH_L = "#e8a09a"
C_HP_L = "#7fb3d3"
C_GREY = "#7f8c8d"
C_GOLD = "#d4ac0d"

FONT    = "DejaVu Sans"
DPI_OUT = 300

plt.rcParams.update({
    "font.family": FONT,
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})


def _save(fig, name: str) -> Path:
    path = OUT_DIR / f"{name}.png"
    fig.savefig(path, dpi=DPI_OUT, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {path.name}")
    return path


# ── Load shared data ────────────────────────────────────────────────────────
mc = pd.read_csv(RESULTS / "economics" / CID_ECON / "economics_monte_carlo_samples.csv")

with open(RESULTS / "economics" / CID_ECON / "monte_carlo_summary.json") as f:
    mc_summary = json.load(f)

with open(RESULTS / "cha" / CID_HYD / "cha_kpis.json") as f:
    cha_kpis = json.load(f)

pipe_full = pd.read_csv(RESULTS / "cha" / CID_HYD / "pipe_velocities_supply_return_with_temp.csv")
pipe_path = pd.read_csv(RESULTS / "cha" / CID_HYD / "pipe_velocities_plant_to_plant_main_path.csv")
pipe_pres = pd.read_csv(RESULTS / "cha" / CID_HYD / "pipe_pressures_supply_return.csv")

with open(RESULTS / "dha" / CID_DHA / "dha_kpis.json") as f:
    dha_kpis = json.load(f)

load_hourly = pd.read_csv(RESULTS / "dha" / CID_DHA / "load_summary_by_hour.csv")

with open(RESULTS / "decision" / CID_HYD / f"kpi_contract_{CID_HYD}.json") as f:
    kpi_contract = json.load(f)


# ══════════════════════════════════════════════════════════════════════════════
# FIG 01 — LCOH Violin Plot
# ══════════════════════════════════════════════════════════════════════════════
def fig01_lcoh_violin():
    dh = mc["lcoh_dh_eur_per_mwh"].dropna().values
    hp = mc["lcoh_hp_eur_per_mwh"].dropna().values

    fig, ax = plt.subplots(figsize=(7, 5))
    parts = ax.violinplot([dh, hp], positions=[1, 2],
                          showmedians=True, showextrema=False, widths=0.55)

    for i, (color_f, color_e) in enumerate([(C_DH_L, C_DH), (C_HP_L, C_HP)]):
        parts["bodies"][i].set_facecolor(color_f)
        parts["bodies"][i].set_edgecolor(color_e)
        parts["bodies"][i].set_linewidth(1.5)
        parts["bodies"][i].set_alpha(0.75)

    parts["cmedians"].set_color("black")
    parts["cmedians"].set_linewidth(2.5)

    # p05 / p95 ticks
    for pos, vals, col in zip([1, 2], [dh, hp], [C_DH, C_HP]):
        p05, p95 = np.percentile(vals, 5), np.percentile(vals, 95)
        ax.plot([pos - 0.12, pos + 0.12], [p05, p05], color=col, lw=2)
        ax.plot([pos - 0.12, pos + 0.12], [p95, p95], color=col, lw=2)
        ax.plot([pos, pos], [p05, p95], color=col, lw=1, linestyle="--", alpha=0.5)

    # Median labels
    for pos, vals, col in zip([1, 2], [dh, hp], [C_DH, C_HP]):
        med = np.median(vals)
        ax.text(pos, med + 4, f"{med:.0f}", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=col)

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["District Heating (DH)", "Heat Pumps (HP)"])
    ax.set_ylabel("Levelised Cost of Heat (EUR / MWh)")
    ax.set_title(f"LCOH Distribution — {len(dh)} Monte Carlo Scenarios\n{LABEL_ECON}")

    legend_handles = [
        mpatches.Patch(facecolor=C_DH_L, edgecolor=C_DH, label="DH distribution"),
        mpatches.Patch(facecolor=C_HP_L, edgecolor=C_HP, label="HP distribution"),
        mlines.Line2D([], [], color="black", lw=2.5, label="Median"),
        mlines.Line2D([], [], color=C_GREY, lw=1.5, linestyle="--", label="P5 – P95 range"),
    ]
    ax.legend(handles=legend_handles, loc="upper right")
    fig.tight_layout()
    return _save(fig, "fig01_lcoh_violin")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 02 — LCOH Cumulative Distribution Function
# ══════════════════════════════════════════════════════════════════════════════
def fig02_lcoh_cdf():
    dh = np.sort(mc["lcoh_dh_eur_per_mwh"].dropna().values)
    hp = np.sort(mc["lcoh_hp_eur_per_mwh"].dropna().values)
    p  = np.linspace(0, 1, len(dh))

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(dh, p, color=C_DH, linewidth=2.5, label=f"District Heating  (median {np.median(dh):.0f} €/MWh)")
    ax.plot(hp, p, color=C_HP, linewidth=2.5, label=f"Heat Pumps        (median {np.median(hp):.0f} €/MWh)")

    # Median markers
    for med, col in zip([np.median(dh), np.median(hp)], [C_DH, C_HP]):
        ax.axvline(med, color=col, linestyle="--", alpha=0.45, linewidth=1.2)
    ax.axhline(0.5, color="#555", linestyle=":", linewidth=1, alpha=0.5)

    # Shaded bands P5-P95
    ax.fill_betweenx(p,
                     np.percentile(dh, 5) * np.ones_like(p),
                     np.percentile(dh, 95) * np.ones_like(p),
                     alpha=0.07, color=C_DH)
    ax.fill_betweenx(p,
                     np.percentile(hp, 5) * np.ones_like(p),
                     np.percentile(hp, 95) * np.ones_like(p),
                     alpha=0.07, color=C_HP)

    ax.set_xlabel("Levelised Cost of Heat (EUR / MWh)")
    ax.set_ylabel("Cumulative Probability")
    ax.set_title(f"LCOH Cumulative Distribution — {len(dh)} Monte Carlo Scenarios\n{LABEL_ECON}")
    ax.set_ylim(0, 1)
    ax.legend()
    fig.tight_layout()
    return _save(fig, "fig02_lcoh_cdf")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 03 — LCOH Scenario Scatter (DH vs HP)
# ══════════════════════════════════════════════════════════════════════════════
def fig03_lcoh_scatter():
    dh = mc["lcoh_dh_eur_per_mwh"].values
    hp = mc["lcoh_hp_eur_per_mwh"].values
    hp_wins = dh > hp

    fig, ax = plt.subplots(figsize=(7, 6))

    ax.scatter(hp[hp_wins],  dh[hp_wins],  alpha=0.35, s=14, color=C_HP,
               label=f"HP preferred ({hp_wins.sum()} / {len(hp_wins)} scenarios)")
    ax.scatter(hp[~hp_wins], dh[~hp_wins], alpha=0.35, s=14, color=C_DH,
               label=f"DH preferred ({(~hp_wins).sum()} / {len(hp_wins)} scenarios)")

    all_v = np.concatenate([dh, hp])
    vmin, vmax = all_v.min() * 0.95, all_v.max() * 1.05
    ax.plot([vmin, vmax], [vmin, vmax], "k--", linewidth=1.2, alpha=0.5, label="Break-even line")
    ax.fill_between([vmin, vmax], [vmin, vmin], [vmin, vmax],
                    alpha=0.04, color=C_DH)
    ax.fill_between([vmin, vmax], [vmax, vmax], [vmin, vmax],
                    alpha=0.04, color=C_HP)

    ax.text(vmax * 0.98, vmax * 0.97, "DH\ncheaper", ha="right", va="top",
            fontsize=8, color=C_DH, alpha=0.7)
    ax.text(vmin * 1.02, vmin * 1.03, "HP\ncheaper", ha="left", va="bottom",
            fontsize=8, color=C_HP, alpha=0.7)

    ax.set_xlim(vmin, vmax)
    ax.set_ylim(vmin, vmax)
    ax.set_xlabel("HP LCOH (EUR / MWh)")
    ax.set_ylabel("DH LCOH (EUR / MWh)")
    ax.set_title(f"Scenario-by-Scenario LCOH Comparison\n{LABEL_ECON}")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    return _save(fig, "fig03_lcoh_scatter")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 04 — Sensitivity Tornado Chart
# ══════════════════════════════════════════════════════════════════════════════
def fig04_tornado():
    param_labels = {
        "capex_mult":      "CAPEX Multiplier",
        "elec_price_mult": "Electricity Price",
        "fuel_price_mult": "Fuel / Gas Price",
        "grid_co2_mult":   "Grid CO₂ Factor",
        "hp_cop":          "Heat Pump COP",
        "discount_rate":   "Discount Rate",
    }

    corr_dh, corr_hp = {}, {}
    for col, label in param_labels.items():
        if col in mc.columns:
            corr_dh[label] = mc[col].corr(mc["lcoh_dh_eur_per_mwh"], method="spearman")
            corr_hp[label] = mc[col].corr(mc["lcoh_hp_eur_per_mwh"], method="spearman")

    labels  = list(corr_dh.keys())
    dh_vals = [corr_dh[l] for l in labels]
    hp_vals = [corr_hp[l] for l in labels]

    # Sort by combined absolute influence
    order   = np.argsort([max(abs(d), abs(h)) for d, h in zip(dh_vals, hp_vals)])
    labels  = [labels[i] for i in order]
    dh_vals = [dh_vals[i] for i in order]
    hp_vals = [hp_vals[i] for i in order]

    y = np.arange(len(labels))
    w = 0.32
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(y + w / 2, dh_vals, height=w, color=C_DH, alpha=0.85, label="DH LCOH")
    ax.barh(y - w / 2, hp_vals, height=w, color=C_HP, alpha=0.85, label="HP LCOH")
    ax.axvline(0, color="black", linewidth=0.8)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Spearman Rank Correlation with LCOH")
    ax.set_title(f"Parameter Sensitivity — Influence on LCOH\n{LABEL_ECON}")
    ax.set_xlim(-1.05, 1.05)
    ax.legend()
    fig.tight_layout()
    return _save(fig, "fig04_tornado")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 05 — CO₂ Box Plot
# ══════════════════════════════════════════════════════════════════════════════
def fig05_co2_boxplot():
    dh_co2 = mc["co2_dh_kg_per_mwh"].dropna().values
    hp_co2 = mc["co2_hp_kg_per_mwh"].dropna().values

    fig, ax = plt.subplots(figsize=(7, 5))
    bp = ax.boxplot([dh_co2, hp_co2], positions=[1, 2], patch_artist=True,
                    widths=0.45, showfliers=True,
                    flierprops=dict(marker="o", markersize=3, alpha=0.3,
                                   markerfacecolor=C_GREY, markeredgecolor=C_GREY))

    for i, (fcolor, ecolor) in enumerate([(C_DH_L, C_DH), (C_HP_L, C_HP)]):
        bp["boxes"][i].set_facecolor(fcolor)
        bp["boxes"][i].set_edgecolor(ecolor)
        bp["boxes"][i].set_linewidth(1.5)
        bp["medians"][i].set_color("black")
        bp["medians"][i].set_linewidth(2.5)

    # Annotation for constant DH
    ax.annotate("Deterministic\n(fixed fuel mix)",
                xy=(1, np.median(dh_co2)), xytext=(1.6, np.median(dh_co2) + 12),
                arrowprops=dict(arrowstyle="->", color=C_DH, lw=1),
                fontsize=8, color=C_DH, ha="center")

    ax.annotate("Varies with\ngrid carbon factor",
                xy=(2, np.percentile(hp_co2, 75)), xytext=(2.6, np.percentile(hp_co2, 90)),
                arrowprops=dict(arrowstyle="->", color=C_HP, lw=1),
                fontsize=8, color=C_HP, ha="center")

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["District Heating (DH)", "Heat Pumps (HP)"])
    ax.set_ylabel("CO₂ Intensity (kg CO₂ / MWh heat)")
    ax.set_title(f"CO₂ Intensity Distribution — {len(dh_co2)} Monte Carlo Scenarios\n{LABEL_ECON}")
    ax.set_xlim(0.3, 3.2)
    fig.tight_layout()
    return _save(fig, "fig05_co2_boxplot")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 06 — Cost–Emissions Pareto Scatter
# ══════════════════════════════════════════════════════════════════════════════
def fig06_co2_lcoh_pareto():
    dh_lcoh = mc["lcoh_dh_eur_per_mwh"].values
    hp_lcoh = mc["lcoh_hp_eur_per_mwh"].values
    dh_co2  = mc["co2_dh_kg_per_mwh"].values
    hp_co2  = mc["co2_hp_kg_per_mwh"].values

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(dh_co2, dh_lcoh, alpha=0.25, s=12, color=C_DH, label="District Heating")
    ax.scatter(hp_co2, hp_lcoh, alpha=0.25, s=12, color=C_HP, label="Heat Pumps")

    # Median markers (large)
    dh_med_co2, dh_med_lcoh = np.median(dh_co2), np.median(dh_lcoh)
    hp_med_co2, hp_med_lcoh = np.median(hp_co2), np.median(hp_lcoh)

    ax.scatter([dh_med_co2], [dh_med_lcoh], color=C_DH, s=180, zorder=10,
               edgecolors="black", linewidths=1.2, label=f"DH median  ({dh_med_lcoh:.0f} €/MWh, {dh_med_co2:.0f} kg/MWh)")
    ax.scatter([hp_med_co2], [hp_med_lcoh], color=C_HP, s=180, zorder=10,
               edgecolors="black", linewidths=1.2, label=f"HP median  ({hp_med_lcoh:.0f} €/MWh, {hp_med_co2:.0f} kg/MWh)")

    # Crosshair lines through medians
    ax.axvline(dh_med_co2, color=C_DH, linestyle="--", alpha=0.35, linewidth=1)
    ax.axhline(dh_med_lcoh, color=C_DH, linestyle="--", alpha=0.35, linewidth=1)
    ax.axvline(hp_med_co2, color=C_HP, linestyle="--", alpha=0.35, linewidth=1)
    ax.axhline(hp_med_lcoh, color=C_HP, linestyle="--", alpha=0.35, linewidth=1)

    ax.set_xlabel("CO₂ Intensity (kg CO₂ / MWh heat)")
    ax.set_ylabel("LCOH (EUR / MWh)")
    ax.set_title(f"Cost–Emissions Trade-off Space\n500 Monte Carlo Scenarios — {LABEL_ECON}")
    ax.legend(fontsize=8)

    # "Better" corner annotation
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    ax.text(xlim[0] + (xlim[1]-xlim[0])*0.02,
            ylim[0] + (ylim[1]-ylim[0])*0.04,
            "← lower CO₂   lower cost ↓\n(preferred region)",
            fontsize=7.5, color="#27ae60", alpha=0.8, va="bottom")

    fig.tight_layout()
    return _save(fig, "fig06_co2_lcoh_pareto")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 07 — Pipe Velocity Distribution Histogram
# ══════════════════════════════════════════════════════════════════════════════
def fig07_velocity_histogram():
    vdist  = cha_kpis["aggregate"]["velocity_distribution"]
    bins   = np.array(vdist["bins"])
    counts = np.array(vdist["counts"])
    bw     = bins[1] - bins[0]
    lefts  = bins[:-1]

    colors = []
    for b in lefts:
        if b < 0.3:
            colors.append("#aed6f1")
        elif b < 1.0:
            colors.append(C_HP)
        elif b < 2.0:
            colors.append("#f39c12")
        else:
            colors.append(C_DH)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(lefts, counts, width=bw * 0.88, color=colors, edgecolor="white", linewidth=0.6)

    ax.axvline(2.0, color=C_DH, linestyle="--", linewidth=2,
               label="Design velocity limit (2.0 m/s)")
    ax.axvline(cha_kpis["aggregate"]["v_mean_ms"], color="black", linestyle=":",
               linewidth=1.5, label=f"Mean velocity ({cha_kpis['aggregate']['v_mean_ms']:.2f} m/s)")

    # Legend for colours
    legend_handles = [
        mpatches.Patch(color="#aed6f1", label="< 0.3 m/s  (low flow / service stubs)"),
        mpatches.Patch(color=C_HP,      label="0.3 – 1.0 m/s  (normal range)"),
        mpatches.Patch(color="#f39c12", label="1.0 – 2.0 m/s  (design range)"),
        mpatches.Patch(color=C_DH,      label="> 2.0 m/s  (above design limit)"),
        mlines.Line2D([], [], color=C_DH, linestyle="--", lw=2, label="Design limit (2.0 m/s)"),
        mlines.Line2D([], [], color="black", linestyle=":", lw=1.5,
                      label=f"Mean ({cha_kpis['aggregate']['v_mean_ms']:.2f} m/s)"),
    ]
    ax.legend(handles=legend_handles, fontsize=8, loc="upper right")
    ax.set_xlabel("Flow Velocity (m/s)")
    ax.set_ylabel("Number of Pipe Segments")
    ax.set_title(f"Pipe Velocity Distribution — {LABEL_HYD}")
    fig.tight_layout()
    return _save(fig, "fig07_velocity_histogram")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 08 — Velocity Profile Along Main Supply Path
# ══════════════════════════════════════════════════════════════════════════════
def fig08_velocity_profile():
    sp = pipe_path[pipe_path["direction"].str.contains("supply", case=False)].copy()
    sp = sp.sort_values("segment_order").reset_index(drop=True)
    sp["cum_dist_m"] = sp["length_m"].cumsum()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.step(sp["cum_dist_m"].values, sp["velocity_m_per_s"].values,
            where="pre", color=C_DH, linewidth=2.5, label="Supply velocity")
    ax.fill_between(sp["cum_dist_m"].values, 0, sp["velocity_m_per_s"].values,
                    step="pre", alpha=0.15, color=C_DH)

    # Diameter annotations (label each DN change)
    prev_dn = None
    for _, row in sp.iterrows():
        dn = int(row["diameter_mm"])
        if dn != prev_dn:
            ax.text(row["cum_dist_m"] - row["length_m"] / 2,
                    row["velocity_m_per_s"] + 0.03,
                    f"DN{dn}", fontsize=7, color="#555", ha="center")
            prev_dn = dn

    ax.axhline(2.0, color="red", linestyle="--", linewidth=1.5,
               label="Design limit (2.0 m/s)")
    ax.set_xlabel("Cumulative Distance from Plant (m)")
    ax.set_ylabel("Flow Velocity (m/s)")
    ax.set_title(f"Supply Velocity — Main Path (Plant → Furthest Consumer)\n{LABEL_HYD}")
    ax.set_ylim(bottom=0)
    ax.legend()
    fig.tight_layout()
    return _save(fig, "fig08_velocity_profile")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 09 — Pressure Profile Along Main Path
# ══════════════════════════════════════════════════════════════════════════════
def fig09_pressure_profile():
    sp = pipe_path[pipe_path["direction"].str.contains("supply", case=False)].copy()
    sp = sp.sort_values("segment_order").reset_index(drop=True)

    # Join supply pressure from pipe_pres on pipe_name
    sup_pres = sp.merge(
        pipe_pres[pipe_pres["direction"] == "supply"][["pipe_name", "p_from_bar", "p_to_bar"]],
        on="pipe_name", how="left"
    )
    sup_pres["cum_dist_m"] = sup_pres["length_m"].cumsum()
    sup_pres = sup_pres.dropna(subset=["p_from_bar"])

    # Build return pipe pressure along same spatial path
    def _return_name(sname):
        try:
            rest  = sname[len("pipe_S_"):]
            parts = rest.split("_to_", 1)
            if len(parts) == 2:
                return f"pipe_R_{parts[1]}_to_{parts[0]}"
        except Exception:
            pass
        return None

    ret_lookup = pipe_pres[pipe_pres["direction"] == "return"].set_index("pipe_name")
    ret_rows = []
    cum = 0.0
    for _, row in sp.iterrows():
        cum += row["length_m"]
        rname = _return_name(row["pipe_name"])
        if rname and rname in ret_lookup.index:
            r = ret_lookup.loc[rname]
            ret_rows.append({
                "cum_dist_m": cum,
                "p_from_bar": float(r["p_from_bar"]),
                "p_to_bar":   float(r["p_to_bar"]),
            })

    fig, ax = plt.subplots(figsize=(10, 4))

    if len(sup_pres) > 0:
        ax.plot(sup_pres["cum_dist_m"], sup_pres["p_from_bar"],
                color=C_DH, linewidth=2.5, label="Supply pressure")
        ax.fill_between(sup_pres["cum_dist_m"],
                        sup_pres["p_from_bar"] - 0.05, sup_pres["p_from_bar"] + 0.05,
                        alpha=0.15, color=C_DH)

    if ret_rows:
        ret_df = pd.DataFrame(ret_rows)
        ax.plot(ret_df["cum_dist_m"], ret_df["p_from_bar"],
                color=C_HP, linewidth=2.5, linestyle="--", label="Return pressure")
        ax.fill_between(ret_df["cum_dist_m"],
                        ret_df["p_from_bar"] - 0.05, ret_df["p_from_bar"] + 0.05,
                        alpha=0.15, color=C_HP)

    ax.set_xlabel("Cumulative Distance from Plant (m)")
    ax.set_ylabel("Pressure (bar)")
    ax.set_title(f"Pressure Profile — Main Path (Supply & Return)\n{LABEL_HYD}")
    ax.legend()
    fig.tight_layout()
    return _save(fig, "fig09_pressure_profile")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 10 — Temperature Drop Along Supply Main Path
# ══════════════════════════════════════════════════════════════════════════════
def fig10_temperature_profile():
    sp = pipe_path[pipe_path["direction"].str.contains("supply", case=False)].copy()
    sp = sp.sort_values("segment_order").reset_index(drop=True)

    # Join temperature from pipe_full (has pipe_idx)
    temp_data = pipe_full[
        (pipe_full["direction"] == "supply") & (pipe_full["type"] == "trunk")
    ][["pipe_idx", "pipe_name", "t_from_c", "t_to_c", "t_mean_c", "t_drop_c"]].copy()

    merged = sp.merge(temp_data, on="pipe_name", how="left")
    merged["cum_dist_m"] = merged["length_m"].cumsum()
    merged = merged.dropna(subset=["t_from_c"])

    fig, ax = plt.subplots(figsize=(10, 4))
    if len(merged) > 0:
        ax.plot(merged["cum_dist_m"], merged["t_from_c"],
                color=C_DH, linewidth=2.5, label="Supply temperature (from)")
        ax.fill_between(merged["cum_dist_m"],
                        merged["t_from_c"] - 0.5, merged["t_from_c"] + 0.5,
                        alpha=0.15, color=C_DH)

        # Cumulative temperature drop
        total_drop = merged["t_drop_c"].sum()
        ax.text(merged["cum_dist_m"].iloc[-1] * 0.98,
                merged["t_from_c"].iloc[-1] + 0.5,
                f"ΔT total = {total_drop:.1f} °C",
                ha="right", fontsize=9, color=C_DH)

    ax.axhline(70, color="orange", linestyle="--", linewidth=1.5,
               label="Min. supply temperature threshold (70 °C)")
    ax.set_xlabel("Cumulative Distance from Plant (m)")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title(f"Supply Temperature Profile — Main Path\n{LABEL_HYD}")
    ax.legend()
    fig.tight_layout()
    return _save(fig, "fig10_temperature_profile")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 11 — Pipe Diameter Distribution
# ══════════════════════════════════════════════════════════════════════════════
def fig11_diameter_distribution():
    sup = pipe_full[pipe_full["direction"] == "supply"].copy()
    stats = sup.groupby("diameter_mm").agg(
        count=("pipe_name", "count"),
        total_length_m=("length_m", "sum"),
    ).reset_index().sort_values("diameter_mm")

    dn_labels = [f"DN{int(d)}" for d in stats["diameter_mm"]]
    x = np.arange(len(dn_labels))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    ax1.bar(x, stats["count"], color=C_DH, alpha=0.85, edgecolor="white")
    ax1.set_xticks(x)
    ax1.set_xticklabels(dn_labels)
    ax1.set_ylabel("Number of Pipe Segments")
    ax1.set_title("Pipe Segment Count by Diameter")
    for xi, cnt in zip(x, stats["count"]):
        ax1.text(xi, cnt + 0.5, str(cnt), ha="center", fontsize=9, color=C_DH)

    ax2.bar(x, stats["total_length_m"] / 1000, color=C_HP, alpha=0.85, edgecolor="white")
    ax2.set_xticks(x)
    ax2.set_xticklabels(dn_labels)
    ax2.set_ylabel("Total Length (km)")
    ax2.set_title("Total Pipe Length by Diameter")
    for xi, km in zip(x, stats["total_length_m"] / 1000):
        ax2.text(xi, km + 0.01, f"{km:.2f}", ha="center", fontsize=9, color=C_HP)

    fig.suptitle(f"Pipe Diameter Distribution — {LABEL_HYD}", fontweight="bold")
    fig.tight_layout()
    return _save(fig, "fig11_diameter_distribution")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 12 — Grid Feeder Loading Profile
# ══════════════════════════════════════════════════════════════════════════════
def fig12_line_loading():
    peak_p   = float(dha_kpis.get("peak_p_total_kw_total") or load_hourly["p_total_kw_total"].max())
    peak_pct = float(dha_kpis.get("max_feeder_loading_pct") or 100.0)

    df = load_hourly.copy().reset_index(drop=True)
    df["est_loading_pct"] = (df["p_total_kw_total"] / peak_p) * peak_pct

    fig, ax = plt.subplots(figsize=(10, 4))
    hours = np.arange(len(df))

    ax.fill_between(hours, 0, df["est_loading_pct"].clip(upper=100),
                    alpha=0.25, color=C_HP)
    ax.fill_between(hours, 100, df["est_loading_pct"].clip(lower=100),
                    alpha=0.35, color=C_DH, label="Overload (> 100 %)")
    ax.plot(hours, df["est_loading_pct"], color=C_DH, linewidth=1.8, alpha=0.9,
            label="Estimated feeder loading")

    ax.axhline(100, color="orange", linestyle="--", linewidth=2,
               label="Thermal capacity limit (100 %)")
    ax.axhline(peak_pct, color="red", linestyle=":", linewidth=1.5, alpha=0.7,
               label=f"Peak loading ({peak_pct:.0f} %)")

    ax.set_xlabel("Simulation Hour (index)")
    ax.set_ylabel("Estimated Feeder Loading (%)")
    ax.set_title(f"LV Grid Feeder Loading — HP Scenario\n{LABEL_HYD}")
    ax.legend()
    fig.tight_layout()
    return _save(fig, "fig12_line_loading")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 13 — Stacked Load Profile (Base + HP)
# ══════════════════════════════════════════════════════════════════════════════
def fig13_load_stacked():
    df = load_hourly.copy().reset_index(drop=True)
    hours = np.arange(len(df))
    base  = df["p_base_kw_total"].values
    hp    = df["p_hp_kw_total"].values

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.stackplot(hours, base, hp,
                 labels=["Baseline load (kW)", "HP additional demand (kW)"],
                 colors=[C_GREY, C_HP], alpha=0.85)

    ax.set_xlabel("Simulation Hour (index)")
    ax.set_ylabel("Active Power (kW)")
    ax.set_title(f"LV Grid Load Profile — Baseline + Heat Pump Demand\n{LABEL_HYD}")
    ax.legend(loc="upper left")

    # Annotate peak
    peak_idx = df["p_total_kw_total"].idxmax()
    peak_kw  = df["p_total_kw_total"].max()
    ax.annotate(f"Peak: {peak_kw:.0f} kW",
                xy=(peak_idx, peak_kw),
                xytext=(peak_idx + 0.5, peak_kw * 0.85),
                arrowprops=dict(arrowstyle="->", color="black", lw=1),
                fontsize=8)

    fig.tight_layout()
    return _save(fig, "fig13_load_stacked")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 14 — Grid Constraint Violations Summary
# ══════════════════════════════════════════════════════════════════════════════
def fig14_grid_violations():
    total   = int(dha_kpis.get("hours_total", 1))
    v_viol  = int(dha_kpis.get("voltage_violated_hours", 0))
    l_viol  = int(dha_kpis.get("line_overload_hours", 0))
    t_viol  = int(dha_kpis.get("trafo_overload_hours", 0))

    categories  = ["Voltage\nViolations", "Line\nOverloads", "Trafo\nOverloads"]
    viol_hours  = [v_viol, l_viol, t_viol]
    ok_hours    = [total - v for v in viol_hours]

    x = np.arange(len(categories))
    w = 0.35

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x - w / 2, ok_hours,    width=w, label="Within limits",   color="#27ae60", alpha=0.85)
    ax.bar(x + w / 2, viol_hours,  width=w, label="Violation hours", color=C_DH,     alpha=0.85)

    ax.axhline(total, color=C_GREY, linestyle=":", linewidth=1.2,
               label=f"Total simulated hours ({total})")

    # Percentage labels above violation bars
    for xi, viol in zip(x, viol_hours):
        pct = viol / total * 100 if total > 0 else 0
        ax.text(xi + w / 2, viol + 0.1, f"{pct:.0f} %",
                ha="center", fontsize=9, fontweight="bold", color=C_DH)

    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel("Simulation Hours")
    ax.set_title(f"Grid Constraint Violations — HP Scenario\n{LABEL_HYD}")
    ax.legend()

    # Feasibility verdict
    feasible = dha_kpis.get("feasible", False)
    verdict  = "Grid: NOT FEASIBLE without reinforcement" if not feasible else "Grid: FEASIBLE"
    vcolor   = C_DH if not feasible else "#27ae60"
    ax.text(0.5, 0.97, verdict, transform=ax.transAxes,
            ha="center", va="top", fontsize=9, fontweight="bold",
            color=vcolor,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=vcolor, alpha=0.9))
    fig.tight_layout()
    return _save(fig, "fig14_grid_violations")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 15 — Agent Pipeline Architecture Flowchart
# ══════════════════════════════════════════════════════════════════════════════
def fig15_agent_flowchart():
    fig, ax = plt.subplots(figsize=(13, 9))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9)
    ax.axis("off")

    def _box(cx, cy, w, h, text, bg, fg="white", fs=9, bold=True):
        rect = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                              boxstyle="round,pad=0.12",
                              facecolor=bg, edgecolor="white",
                              linewidth=1.8, alpha=0.92, zorder=3)
        ax.add_patch(rect)
        ax.text(cx, cy, text, ha="center", va="center",
                color=fg, fontsize=fs,
                fontweight="bold" if bold else "normal",
                multialignment="center", zorder=4)

    def _arrow(x1, y1, x2, y2, color="#444"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->,head_length=0.35,head_width=0.2",
                                   color=color, lw=1.8), zorder=2)

    def _side_label(cx, cy, text, col):
        ax.text(cx, cy, text, ha="left", va="center",
                fontsize=8, color=col, style="italic", zorder=4)

    # ── Input data (top row)
    input_bg = "#5d6d7e"
    _box(2.2, 8.4, 3.2, 0.65, "GIS Street Network\n& Building Footprints", input_bg, fs=8)
    _box(6.5, 8.4, 3.2, 0.65, "Weather Data\n& Load Profiles", input_bg, fs=8)
    _box(10.8, 8.4, 3.2, 0.65, "Energy Prices\n& Carbon Intensity", input_bg, fs=8)

    # Arrows from inputs → orchestrator
    _arrow(2.2,  8.07, 4.5, 7.55)
    _arrow(6.5,  8.07, 6.5, 7.55)
    _arrow(10.8, 8.07, 8.5, 7.55)

    # ── Orchestrator
    _box(6.5, 7.2, 4.2, 0.65, "Orchestrator Agent\n(Intent Routing & Coordination)", "#2c3e50", fs=9)

    # ── Pipeline agents (left-centre column)
    agents = [
        (6.5, 6.1, "CHA Agent\n(Pandapipes — DH Hydraulic & Thermal Sim)", C_DH),
        (6.5, 5.0, "DHA Agent\n(Pandapower — LV Grid Simulation)", "#7d3c98"),
        (6.5, 3.9, "Economics Agent\n(Monte Carlo — 500 LCOH Scenarios)", C_GOLD, "#222"),
        (6.5, 2.8, "Decision Agent\n(KPI Contract — DH vs HP Ranking)", "#1a6632"),
        (6.5, 1.7, "LLM Explainer\n(Gemini 2.5 Flash — Narrative Generation)", "#154360"),
    ]

    prev_y = 6.87
    for entry in agents:
        cx, cy = entry[0], entry[1]
        text   = entry[2]
        bg     = entry[3]
        fg     = entry[4] if len(entry) > 4 else "white"
        _box(cx, cy, 5.5, 0.72, text, bg, fg=fg, fs=9)
        _arrow(cx, prev_y, cx, cy + 0.36)
        prev_y = cy - 0.36

    # ── Output boxes (right column)
    outputs = [
        (11.0, 6.1,  "Hydraulic KPIs\n(velocity, pressure, heat loss)", C_DH),
        (11.0, 5.0,  "Grid KPIs\n(loading %, violations, feasibility)", "#7d3c98"),
        (11.0, 3.9,  "LCOH Distributions\n(P5 / P50 / P95  DH & HP)", C_GOLD, "#222"),
        (11.0, 2.8,  "Decision Report\n(DH / HP + robustness flag)", "#1a6632"),
        (11.0, 1.7,  "AI Narrative\n(Explanation + Recommendations)", "#154360"),
    ]
    for entry in outputs:
        cx, cy = entry[0], entry[1]
        text   = entry[2]
        bg     = entry[3]
        fg     = entry[4] if len(entry) > 4 else "white"
        _box(cx, cy, 3.6, 0.65, text, bg, fg=fg, fs=8)
        _arrow(6.5 + 2.75, cy, cx - 1.8, cy)

    # ── Streamlit UI (bottom)
    _arrow(6.5, 1.34, 6.5, 0.72)
    _box(6.5, 0.4, 5.5, 0.6, "Streamlit Chat Interface — Intent-Based Interaction", "#0d2244", fs=9)

    # Title
    ax.set_title("Branitz AI System — Multi-Agent Pipeline Architecture",
                 fontsize=14, fontweight="bold", y=1.01)

    # Section labels
    ax.text(0.15, 8.4, "Inputs", fontsize=9, color="#5d6d7e",
            fontweight="bold", va="center", rotation=90)
    ax.text(0.15, 4.0, "Agent\nPipeline", fontsize=9, color="#2c3e50",
            fontweight="bold", va="center", rotation=90, multialignment="center")
    ax.text(0.15, 0.4, "UI", fontsize=9, color="#0d2244",
            fontweight="bold", va="center", rotation=90)

    fig.tight_layout()
    return _save(fig, "fig15_agent_flowchart")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 16 — Study Area Overview Map (reference existing)
# ══════════════════════════════════════════════════════════════════════════════
def fig16_study_area():
    src = RESULTS / "thesis" / "thesis_overview_map.png"
    if not src.exists():
        print("  [SKIP] thesis_overview_map.png not found — run create_thesis_map.py first")
        return None

    import shutil
    dst = OUT_DIR / "fig16_study_area_map.png"
    shutil.copy2(src, dst)
    print(f"  Copied: {dst.name}")
    return dst


# ══════════════════════════════════════════════════════════════════════════════
# FIG 17 — Cluster Decision Comparison Table
# ══════════════════════════════════════════════════════════════════════════════
def fig17_cluster_table():
    dec_dir = RESULTS / "decision"
    rows = []
    for cdir in sorted(dec_dir.iterdir()):
        if not cdir.is_dir():
            continue
        cid = cdir.name
        dec_path  = cdir / f"decision_{cid}.json"
        cont_path = cdir / f"kpi_contract_{cid}.json"
        if not (dec_path.exists() and cont_path.exists()):
            continue
        dec  = json.loads(dec_path.read_text())
        cont = json.loads(cont_path.read_text())
        dh   = cont.get("district_heating", {})
        hp   = cont.get("heat_pumps", {})
        mc_r = cont.get("monte_carlo", {})
        rows.append({
            "Cluster": cid.replace("_", " "),
            "Decision": dec.get("choice", "?"),
            "Robust": "Yes" if dec.get("robust", False) else "No",
            "LCOH DH\n(€/MWh)": f"{dh.get('lcoh',{}).get('median', float('nan')):.0f}",
            "LCOH HP\n(€/MWh)": f"{hp.get('lcoh',{}).get('median', float('nan')):.0f}",
            "DH Feasible": "Yes" if dh.get("feasible", False) else "No",
            "HP Feasible": "Yes" if hp.get("feasible", False) else "No",
            "HP Wins (%)": f"{mc_r.get('hp_wins_fraction', 0) * 100:.0f} %",
        })

    if not rows:
        print("  [SKIP] No decision results found.")
        return None

    df = pd.DataFrame(rows)
    n_cols = len(df.columns)
    n_rows = len(df)

    fig, ax = plt.subplots(figsize=(13, max(2.5, n_rows * 0.75 + 1.8)))
    ax.axis("off")

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.1, 2.0)

    # Header row styling
    for j in range(n_cols):
        cell = table[0, j]
        cell.set_facecolor("#2c3e50")
        cell.set_text_props(color="white", fontweight="bold")

    # Data row styling
    for i in range(1, n_rows + 1):
        row_bg = "#f0f4f8" if i % 2 == 0 else "white"
        dec_val = df.iloc[i - 1]["Decision"]
        dec_col = C_DH if dec_val == "DH" else C_HP

        for j in range(n_cols):
            table[i, j].set_facecolor(row_bg)
        # Colour decision cell
        table[i, 1].set_facecolor(dec_col)
        table[i, 1].set_text_props(color="white", fontweight="bold")
        # Colour robust cell
        robust_val = df.iloc[i - 1]["Robust"]
        table[i, 2].set_facecolor("#27ae60" if robust_val == "Yes" else "#e74c3c")
        table[i, 2].set_text_props(color="white", fontweight="bold")

    ax.set_title("District Cluster Decision Summary",
                 fontsize=13, fontweight="bold", y=0.97)
    fig.tight_layout()
    return _save(fig, "fig17_cluster_table")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating thesis figures …\n")

    funcs = [
        ("Fig 01 — LCOH Violin",               fig01_lcoh_violin),
        ("Fig 02 — LCOH CDF",                  fig02_lcoh_cdf),
        ("Fig 03 — LCOH Scenario Scatter",     fig03_lcoh_scatter),
        ("Fig 04 — Sensitivity Tornado",        fig04_tornado),
        ("Fig 05 — CO₂ Box Plot",              fig05_co2_boxplot),
        ("Fig 06 — Cost–Emissions Pareto",     fig06_co2_lcoh_pareto),
        ("Fig 07 — Velocity Histogram",         fig07_velocity_histogram),
        ("Fig 08 — Velocity Profile",           fig08_velocity_profile),
        ("Fig 09 — Pressure Profile",           fig09_pressure_profile),
        ("Fig 10 — Temperature Profile",        fig10_temperature_profile),
        ("Fig 11 — Diameter Distribution",      fig11_diameter_distribution),
        ("Fig 12 — Line Loading Profile",       fig12_line_loading),
        ("Fig 13 — Stacked Load Profile",       fig13_load_stacked),
        ("Fig 14 — Grid Violations",            fig14_grid_violations),
        ("Fig 15 — Agent Flowchart",            fig15_agent_flowchart),
        ("Fig 16 — Study Area Map",             fig16_study_area),
        ("Fig 17 — Cluster Decision Table",     fig17_cluster_table),
    ]

    results = []
    for label, fn in funcs:
        print(f"\n{label}")
        try:
            path = fn()
            results.append((label, "OK", str(path.name) if path else "—"))
        except Exception as exc:
            import traceback
            print(f"  ERROR: {exc}")
            traceback.print_exc()
            results.append((label, "FAILED", str(exc)[:60]))

    print("\n" + "=" * 70)
    print(f"{'Figure':<42} {'Status':<8} {'Output'}")
    print("=" * 70)
    for lbl, status, out in results:
        mark = "✓" if status == "OK" else "✗"
        print(f"  {mark}  {lbl:<40} {status:<8} {out}")
    print("=" * 70)
    print(f"\nOutput directory: {OUT_DIR.resolve()}")
