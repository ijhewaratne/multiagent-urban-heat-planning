"""
Panel-(b) treatment from fig18 (ST021 flip case), repeated per cluster:
same 24-point "deterministic LCOH gap vs. Monte Carlo DH win-fraction"
scatter as backdrop in every subplot, with that panel's own cluster
highlighted (gold ring if it's the flip case, otherwise colored by its
own deterministic winner).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

RESULTS = Path("results")
OUT_DIR = RESULTS / "thesis" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

C_DH, C_HP = "#c0392b", "#1a5276"
C_GREY, C_GOLD = "#7f8c8d", "#d4ac0d"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "axes.labelsize": 8,
    "axes.titlesize": 8.5,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
})

rows = []
for d in sorted((RESULTS / "economics").glob("ST*")):
    cid = d.name
    det = json.load(open(d / "economics_deterministic.json"))
    mc = json.load(open(d / "monte_carlo_summary.json"))
    gap = det["lcoh_dh_eur_per_mwh"] - det["lcoh_hp_eur_per_mwh"]
    dh_wf = mc["monte_carlo"]["dh_wins_fraction"]
    det_w = "DH" if gap < 0 else "HP"
    mc_w = "DH" if dh_wf > 0.5 else "HP"
    rows.append({
        "cluster": cid,
        "label": cid.split("_", 1)[1].replace("_", " ").title(),
        "annual_heat_mwh": det["annual_heat_mwh"],
        "gap": gap,
        "dh_wf": dh_wf,
        "det_winner": det_w,
        "mc_winner": mc_w,
        "flip": det_w != mc_w,
    })

df = pd.DataFrame(rows).sort_values("annual_heat_mwh").reset_index(drop=True)

n = len(df)
ncols, nrows = 6, 4
fig, axes = plt.subplots(nrows, ncols, figsize=(21, 14))
axes = axes.flatten()

bg_colors = np.where(df["flip"], C_GOLD, np.where(df["gap"] < 0, C_DH, C_HP))

for i, rec in df.iterrows():
    ax = axes[i]

    ax.scatter(df["gap"], df["dh_wf"] * 100, c=C_GREY, s=22, alpha=0.35,
               edgecolors="none", zorder=3)

    ax.axvline(0, color=C_GREY, lw=0.8, linestyle=":")
    ax.axhline(50, color=C_GREY, lw=0.8, linestyle=":")

    own_color = C_GOLD if rec["flip"] else (C_DH if rec["gap"] < 0 else C_HP)
    ax.scatter([rec["gap"]], [rec["dh_wf"] * 100], color=own_color, s=140,
               edgecolors="black", linewidths=1.3, zorder=10)

    n_no = rec["cluster"].split("_")[0]
    title_color = "#8a6d00" if rec["flip"] else "black"
    title = (f"{n_no}  {rec['label']}\n"
             f"gap {rec['gap']:+.0f} €/MWh · MC DH-wins {rec['dh_wf']:.0%}")
    ax.set_title(title, fontsize=7.6, color=title_color,
                 fontweight="bold" if rec["flip"] else "normal")

    if rec["flip"]:
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_visible(True)
            ax.spines[side].set_color(C_GOLD)
            ax.spines[side].set_linewidth(2.2)

    ax.set_xlim(df["gap"].min() - 30, df["gap"].max() + 30)
    ax.set_ylim(-5, 105)

for k in range(n, len(axes)):
    axes[k].axis("off")

legend_handles = [
    mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_DH,
                  markeredgecolor="black", markersize=9, label="This cluster — DH wins (both methods)"),
    mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_HP,
                  markeredgecolor="black", markersize=9, label="This cluster — HP wins (both methods)"),
    mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_GOLD,
                  markeredgecolor="black", markersize=10, label="This cluster — flip case"),
    mlines.Line2D([], [], marker="o", color=C_GREY, alpha=0.5, lw=0, markersize=6,
                  label="Other 23 clusters (context)"),
]
fig.legend(handles=legend_handles, loc="lower center", ncol=4, framealpha=0.95,
           bbox_to_anchor=(0.5, -0.015), fontsize=10)

fig.text(0.5, 0.965,
         "x: Deterministic LCOH gap, DH − HP (EUR/MWh)   ·   y: Monte Carlo DH win fraction (%)",
         ha="center", fontsize=10, color=C_GREY)
fig.suptitle("Deterministic vs. Probabilistic Recommendation — Own Position per Cluster\n"
             "All 24 Street Clusters (sorted by annual heat demand, low → high)",
             fontsize=13.5, y=1.03)

fig.tight_layout(rect=[0, 0.03, 1, 0.93])

out_path = OUT_DIR / "fig22_flip_scatter_grid_all_clusters.png"
fig.savefig(out_path, dpi=220, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved: {out_path}")
