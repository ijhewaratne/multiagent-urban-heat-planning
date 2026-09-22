"""
Panel-(b) treatment from fig18 (ST021 flip case), one standalone figure
per street cluster (companion to create_fig_flip_scatter_grid.py, which
does the same thing as a single small-multiples grid).
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
OUT_DIR = RESULTS / "thesis" / "figures" / "flip_scatter_per_cluster"
OUT_DIR.mkdir(parents=True, exist_ok=True)

C_DH, C_HP = "#c0392b", "#1a5276"
C_GREY, C_GOLD = "#7f8c8d", "#d4ac0d"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "axes.labelsize": 10,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
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
    robust = "robust" if max(dh_wf, 1 - dh_wf) >= 0.70 else (
        "sensitive" if max(dh_wf, 1 - dh_wf) >= 0.55 else "toss-up")
    rows.append({
        "cluster": cid,
        "label": cid.split("_", 1)[1].replace("_", " ").title(),
        "annual_heat_mwh": det["annual_heat_mwh"],
        "gap": gap,
        "dh_wf": dh_wf,
        "det_winner": det_w,
        "mc_winner": mc_w,
        "robust": robust,
        "flip": det_w != mc_w,
    })

df = pd.DataFrame(rows).sort_values("annual_heat_mwh").reset_index(drop=True)

xmin, xmax = df["gap"].min() - 30, df["gap"].max() + 30

saved = []
for _, rec in df.iterrows():
    fig, ax = plt.subplots(figsize=(7.5, 6))

    ax.scatter(df["gap"], df["dh_wf"] * 100, c=C_GREY, s=55, alpha=0.35,
               edgecolors="none", zorder=3, label="Other 23 clusters")

    ax.axvline(0, color=C_GREY, lw=1, linestyle=":")
    ax.axhline(50, color=C_GREY, lw=1, linestyle=":")
    ax.axhspan(0, 50, xmin=0, xmax=(0 - xmin) / (xmax - xmin), color=C_HP, alpha=0.04)
    ax.axhspan(50, 100, xmin=(0 - xmin) / (xmax - xmin), xmax=1, color=C_DH, alpha=0.04)

    own_color = C_GOLD if rec["flip"] else (C_DH if rec["gap"] < 0 else C_HP)
    ax.scatter([rec["gap"]], [rec["dh_wf"] * 100], color=own_color, s=260,
               edgecolors="black", linewidths=1.6, zorder=10,
               label=f"{rec['cluster'].split('_')[0]} (this cluster)")

    winner_txt = (f"FLIP CASE — deterministic → {rec['det_winner']}, "
                  f"Monte Carlo → {rec['mc_winner']} ({rec['robust']})"
                  if rec["flip"] else
                  f"Both methods agree: {rec['mc_winner']} wins ({rec['robust']})")

    ax.text(0.02, 0.02,
            f"Deterministic gap: {rec['gap']:+.1f} EUR/MWh\n"
            f"Monte Carlo DH win fraction: {rec['dh_wf']:.0%}\n"
            f"{winner_txt}",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor=(C_GOLD if rec["flip"] else C_GREY), alpha=0.95))

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-5, 105)
    ax.set_xlabel("Deterministic LCOH gap, DH − HP (EUR/MWh)")
    ax.set_ylabel("Monte Carlo DH win fraction (%)")

    title_color = "#8a6d00" if rec["flip"] else "black"
    ax.set_title(f"{rec['cluster'].split('_')[0]}  {rec['label']}\n"
                 f"Deterministic vs. Probabilistic Recommendation",
                 color=title_color, fontweight="bold" if rec["flip"] else "normal")

    handles = [
        mlines.Line2D([], [], marker="o", color="none", markerfacecolor=own_color,
                      markeredgecolor="black", markersize=11, label=f"{rec['cluster'].split('_')[0]} (this cluster)"),
        mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_GREY, alpha=0.5,
                      markersize=8, label="Other 23 clusters"),
    ]
    ax.legend(handles=handles, loc="upper right", framealpha=0.9)

    fig.tight_layout()
    out_name = f"{rec['cluster']}.png"
    out_path = OUT_DIR / out_name
    fig.savefig(out_path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    saved.append(out_path)
    print(f"Saved: {out_path}")

print(f"\n{len(saved)} figures written to {OUT_DIR}")
