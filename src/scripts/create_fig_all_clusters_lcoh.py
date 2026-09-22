"""
Per-cluster LCOH Monte Carlo violin grid — all 24 street clusters.
Small-multiples version of fig01_lcoh_violin, one panel per cluster,
sorted by annual heat demand, each panel's own y-axis (LCOH ranges span
two orders of magnitude across the clusters). ST021 (the only cluster
where the deterministic and Monte Carlo winners disagree) is outlined.
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
    dh_wf = mc_summary["monte_carlo"]["dh_wins_fraction"]
    gap = det["lcoh_dh_eur_per_mwh"] - det["lcoh_hp_eur_per_mwh"]
    det_winner = "DH" if gap < 0 else "HP"
    mc_winner = "DH" if dh_wf > 0.5 else "HP"
    records.append({
        "cluster": cid,
        "label": cid.split("_", 1)[1].replace("_", " ").title(),
        "annual_heat_mwh": det["annual_heat_mwh"],
        "dh": mc["lcoh_dh_eur_per_mwh"].dropna().values,
        "hp": mc["lcoh_hp_eur_per_mwh"].dropna().values,
        "det_dh": det["lcoh_dh_eur_per_mwh"],
        "det_hp": det["lcoh_hp_eur_per_mwh"],
        "dh_wf": dh_wf,
        "flip": det_winner != mc_winner,
    })

records.sort(key=lambda r: r["annual_heat_mwh"])

n = len(records)
ncols, nrows = 6, 4
fig, axes = plt.subplots(nrows, ncols, figsize=(21, 13))
axes = axes.flatten()

for i, rec in enumerate(records):
    ax = axes[i]
    dh, hp = rec["dh"], rec["hp"]
    parts = ax.violinplot([dh, hp], positions=[1, 2], showmedians=True,
                           showextrema=False, widths=0.6)
    for j, (fc, ec) in enumerate([(C_DH_L, C_DH), (C_HP_L, C_HP)]):
        parts["bodies"][j].set_facecolor(fc)
        parts["bodies"][j].set_edgecolor(ec)
        parts["bodies"][j].set_linewidth(1.0)
        parts["bodies"][j].set_alpha(0.75)
    parts["cmedians"].set_color("black")
    parts["cmedians"].set_linewidth(1.5)

    ax.scatter([1, 2], [rec["det_dh"], rec["det_hp"]], marker="D", s=26,
               color="black", zorder=10)

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["DH", "HP"])
    ax.set_xlim(0.5, 2.5)

    n_no = rec["cluster"].split("_")[0]
    title_color = "#8a6d00" if rec["flip"] else "black"
    title = f"{n_no}  {rec['label']}\n{rec['annual_heat_mwh']:,.0f} MWh/yr · DH wins {rec['dh_wf']:.0%} MC"
    ax.set_title(title, fontsize=7.8, color=title_color,
                 fontweight="bold" if rec["flip"] else "normal")

    if rec["flip"]:
        for spine in ax.spines.values():
            spine.set_visible(True)
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_visible(True)
            ax.spines[side].set_color(C_GOLD)
            ax.spines[side].set_linewidth(2.2)

for k in range(n, len(axes)):
    axes[k].axis("off")

legend_handles = [
    mpatches.Patch(facecolor=C_DH_L, edgecolor=C_DH, label="DH distribution (500 MC draws)"),
    mpatches.Patch(facecolor=C_HP_L, edgecolor=C_HP, label="HP distribution (500 MC draws)"),
    mlines.Line2D([], [], marker="D", color="black", lw=0, markersize=6, label="Deterministic estimate"),
    mlines.Line2D([], [], color="black", lw=1.5, label="Median"),
    mpatches.Patch(facecolor="none", edgecolor=C_GOLD, linewidth=2.2, label="Flip case (det. ≠ Monte Carlo winner)"),
]
fig.legend(handles=legend_handles, loc="lower center", ncol=5, framealpha=0.95,
           bbox_to_anchor=(0.5, -0.015), fontsize=9.5)

fig.suptitle("LCOH Monte Carlo Distributions — All 24 Street Clusters\n"
             "(sorted by annual heat demand, low → high)  ·  "
             "y-axis (EUR/MWh) is independent per panel",
             fontsize=13, y=1.03)

fig.tight_layout(rect=[0, 0.03, 1, 0.94])

out_path = OUT_DIR / "fig19_lcoh_violin_all_clusters.png"
fig.savefig(out_path, dpi=220, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved: {out_path}")
