"""
Per-cluster CO2 intensity Monte Carlo boxplot grid — all 24 street clusters.
Small-multiples companion to create_fig_all_clusters_lcoh.py (LCOH violins),
mirroring fig05_co2_boxplot's style. DH's emission factor is fixed in the
Monte Carlo model (deterministic fuel mix) so its box collapses to a line;
HP's varies with the sampled grid carbon intensity and COP.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines

RESULTS = Path("results")
OUT_DIR = RESULTS / "thesis" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

C_DH, C_HP = "#c0392b", "#1a5276"
C_DH_L, C_HP_L = "#e8a09a", "#7fb3d3"
C_GREY, C_GOLD = "#7f8c8d", "#d4ac0d"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "axes.labelsize": 8.5,
    "axes.titlesize": 9,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
})

econ_dirs = sorted((RESULTS / "economics").glob("ST*"))

records = []
for d in econ_dirs:
    cid = d.name
    det = json.load(open(d / "economics_deterministic.json"))
    mc_summary = json.load(open(d / "monte_carlo_summary.json"))
    mc = pd.read_csv(d / "economics_monte_carlo_samples.csv")
    co2_dh_wf = mc_summary["monte_carlo"]["dh_wins_co2_fraction"]
    records.append({
        "cluster": cid,
        "label": cid.split("_", 1)[1].replace("_", " ").title(),
        "annual_heat_mwh": det["annual_heat_mwh"],
        "dh": mc["co2_dh_kg_per_mwh"].dropna().values,
        "hp": mc["co2_hp_kg_per_mwh"].dropna().values,
        "det_dh": det["co2_dh_kg_per_mwh"],
        "det_hp": det["co2_hp_kg_per_mwh"],
        "co2_dh_wf": co2_dh_wf,
    })

records.sort(key=lambda r: r["annual_heat_mwh"])

n = len(records)
ncols, nrows = 6, 4
fig, axes = plt.subplots(nrows, ncols, figsize=(21, 13))
axes = axes.flatten()

for i, rec in enumerate(records):
    ax = axes[i]
    dh, hp = rec["dh"], rec["hp"]
    bp = ax.boxplot([dh, hp], positions=[1, 2], patch_artist=True,
                     widths=0.5, showfliers=True,
                     flierprops=dict(marker="o", markersize=2, alpha=0.25,
                                      markerfacecolor=C_GREY, markeredgecolor=C_GREY))
    for j, (fc, ec) in enumerate([(C_DH_L, C_DH), (C_HP_L, C_HP)]):
        bp["boxes"][j].set_facecolor(fc)
        bp["boxes"][j].set_edgecolor(ec)
        bp["boxes"][j].set_linewidth(1.0)
        bp["medians"][j].set_color("black")
        bp["medians"][j].set_linewidth(1.5)

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["DH", "HP"])
    ax.set_xlim(0.4, 2.6)

    n_no = rec["cluster"].split("_")[0]
    title = (f"{n_no}  {rec['label']}\n"
             f"{rec['annual_heat_mwh']:,.0f} MWh/yr · HP cleaner in {1-rec['co2_dh_wf']:.0%} MC")
    ax.set_title(title, fontsize=7.8)

for k in range(n, len(axes)):
    axes[k].axis("off")

legend_handles = [
    mpatches.Patch(facecolor=C_DH_L, edgecolor=C_DH, label="DH CO₂ intensity (500 MC draws — fixed fuel mix)"),
    mpatches.Patch(facecolor=C_HP_L, edgecolor=C_HP, label="HP CO₂ intensity (500 MC draws — varies with grid mix & COP)"),
    mlines.Line2D([], [], color="black", lw=1.5, label="Median"),
]
fig.legend(handles=legend_handles, loc="lower center", ncol=3, framealpha=0.95,
           bbox_to_anchor=(0.5, -0.015), fontsize=9.5)

fig.suptitle("CO₂ Intensity Monte Carlo Distributions — All 24 Street Clusters\n"
             "(sorted by annual heat demand, low → high)  ·  "
             "y-axis (kg CO₂/MWh heat) is independent per panel",
             fontsize=13, y=1.03)

fig.tight_layout(rect=[0, 0.03, 1, 0.94])

out_path = OUT_DIR / "fig20_co2_boxplot_all_clusters.png"
fig.savefig(out_path, dpi=220, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved: {out_path}")
