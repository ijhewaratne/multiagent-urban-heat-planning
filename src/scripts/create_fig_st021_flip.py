"""
ST021_PYRAMIDENSTRASSE flip-case figure.
Two panels: (a) LCOH Monte Carlo distribution for ST021, (b) deterministic
LCOH gap vs. Monte Carlo DH win-fraction across all 24 clusters, with
ST021 marked as the only cluster where the deterministic and probabilistic
recommendations disagree.
"""
import json
import glob
import os
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

CID = "ST021_PYRAMIDENSTRASSE"
LABEL = "Pyramidenstraße (ST021)"

# Match house palette from create_thesis_figures.py
C_DH, C_HP = "#c0392b", "#1a5276"
C_DH_L, C_HP_L = "#e8a09a", "#7fb3d3"
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
    "axes.titlesize": 11,
    "legend.fontsize": 8.5,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})

# ── Load ST021 Monte Carlo samples ──────────────────────────────────────────
mc = pd.read_csv(RESULTS / "economics" / CID / "economics_monte_carlo_samples.csv")
with open(RESULTS / "economics" / CID / "monte_carlo_summary.json") as f:
    mc_summary = json.load(f)
with open(RESULTS / "economics" / CID / "economics_deterministic.json") as f:
    det = json.load(f)

dh = mc["lcoh_dh_eur_per_mwh"].dropna().values
hp = mc["lcoh_hp_eur_per_mwh"].dropna().values
dh_wf = mc_summary["monte_carlo"]["dh_wins_fraction"]
hp_wf = mc_summary["monte_carlo"]["hp_wins_fraction"]

# ── Load all-cluster deterministic + MC summary for the scatter panel ──────
rows = []
for d in sorted(glob.glob(str(RESULTS / "economics" / "*") + "/")):
    cid = os.path.basename(d.rstrip("/"))
    det_f = os.path.join(d, "economics_deterministic.json")
    mc_f = os.path.join(d, "monte_carlo_summary.json")
    if not (os.path.exists(det_f) and os.path.exists(mc_f)):
        continue
    dd = json.load(open(det_f))
    mm = json.load(open(mc_f))
    gap = dd["lcoh_dh_eur_per_mwh"] - dd["lcoh_hp_eur_per_mwh"]
    rows.append({
        "cluster": cid,
        "gap": gap,
        "dh_wins_fraction": mm["monte_carlo"]["dh_wins_fraction"],
        "annual_heat_mwh": dd["annual_heat_mwh"],
    })
df = pd.DataFrame(rows)
df["det_winner"] = np.where(df["gap"] < 0, "DH", "HP")
df["mc_winner"] = np.where(df["dh_wins_fraction"] > 0.5, "DH", "HP")
df["flip"] = df["det_winner"] != df["mc_winner"]

# ══════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))

# ── Panel A: LCOH violin for ST021 ──────────────────────────────────────────
ax = axes[0]
parts = ax.violinplot([dh, hp], positions=[1, 2], showmedians=True,
                       showextrema=False, widths=0.55)
for i, (fc, ec) in enumerate([(C_DH_L, C_DH), (C_HP_L, C_HP)]):
    parts["bodies"][i].set_facecolor(fc)
    parts["bodies"][i].set_edgecolor(ec)
    parts["bodies"][i].set_linewidth(1.5)
    parts["bodies"][i].set_alpha(0.75)
parts["cmedians"].set_color("black")
parts["cmedians"].set_linewidth(2.5)

for pos, vals, col in zip([1, 2], [dh, hp], [C_DH, C_HP]):
    p05, p95 = np.percentile(vals, 5), np.percentile(vals, 95)
    ax.plot([pos - 0.12, pos + 0.12], [p05, p05], color=col, lw=2)
    ax.plot([pos - 0.12, pos + 0.12], [p95, p95], color=col, lw=2)
    ax.plot([pos, pos], [p05, p95], color=col, lw=1, linestyle="--", alpha=0.5)
    med = np.median(vals)
    ax.text(pos, med + 4, f"{med:.0f}", ha="center", va="bottom",
            fontsize=9, fontweight="bold", color=col)

# Deterministic point estimates
ax.scatter([1], [det["lcoh_dh_eur_per_mwh"]], marker="D", s=70, color="black",
           zorder=10, label="_nolegend_")
ax.scatter([2], [det["lcoh_hp_eur_per_mwh"]], marker="D", s=70, color="black",
           zorder=10, label="_nolegend_")

ax.set_xticks([1, 2])
ax.set_xticklabels(["District Heating (DH)", "Heat Pumps (HP)"])
ax.set_ylabel("Levelised Cost of Heat (EUR / MWh)")
ax.set_title(f"(a) LCOH Distribution — {len(dh)} Monte Carlo Scenarios\n{LABEL}")

legend_handles = [
    mpatches.Patch(facecolor=C_DH_L, edgecolor=C_DH, label="DH distribution"),
    mpatches.Patch(facecolor=C_HP_L, edgecolor=C_HP, label="HP distribution"),
    mlines.Line2D([], [], color="black", lw=2.5, label="Median"),
    mlines.Line2D([], [], marker="D", color="black", lw=0, label="Deterministic estimate"),
    mlines.Line2D([], [], color=C_GREY, lw=1.5, linestyle="--", label="P5 – P95 range"),
]
ax.legend(handles=legend_handles, loc="upper left", framealpha=0.9)

ax.text(0.98, 0.03,
        f"MC win fraction:  DH {dh_wf:.0%}  |  HP {hp_wf:.0%}\n"
        f"Deterministic gap: {det['lcoh_dh_eur_per_mwh']-det['lcoh_hp_eur_per_mwh']:+.1f} EUR/MWh (DH)",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=C_GREY, alpha=0.9))

# ── Panel B: deterministic gap vs MC win fraction, all 24 clusters ─────────
ax2 = axes[1]
colors = np.where(df["flip"], C_GOLD, np.where(df["gap"] < 0, C_DH, C_HP))
sizes = np.where(df["flip"], 140, 55)
edgecolors = np.where(df["flip"], "black", "none")

ax2.scatter(df["gap"], df["dh_wins_fraction"] * 100, c=colors, s=sizes,
            edgecolors=edgecolors, linewidths=1.3, alpha=0.85, zorder=5)

ax2.axvline(0, color=C_GREY, lw=1, linestyle=":")
ax2.axhline(50, color=C_GREY, lw=1, linestyle=":")
ax2.axhspan(0, 50, xmin=0, xmax=0.5, color=C_HP, alpha=0.04)
ax2.axhspan(50, 100, xmin=0.5, xmax=1, color=C_DH, alpha=0.04)

flip_row = df[df["flip"]].iloc[0]
ax2.annotate("ST021 (flip case)\ndeterministic → DH\nMonte Carlo → HP (sensitive)",
             xy=(flip_row["gap"], flip_row["dh_wins_fraction"] * 100),
             xytext=(flip_row["gap"] + 60, flip_row["dh_wins_fraction"] * 100 + 18),
             fontsize=8.5, color="#8a6d00", fontweight="bold",
             arrowprops=dict(arrowstyle="->", color="#8a6d00", lw=1.3))

ax2.set_xlabel("Deterministic LCOH gap, DH − HP (EUR/MWh)")
ax2.set_ylabel("Monte Carlo DH win fraction (%)")
ax2.set_title("(b) Deterministic vs. Probabilistic Recommendation\nAll 24 Street Clusters")

legend_handles2 = [
    mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_DH, markersize=8, label="DH wins (both)"),
    mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_HP, markersize=8, label="HP wins (both)"),
    mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_GOLD, markeredgecolor="black",
                  markersize=10, label="Flip case"),
]
ax2.legend(handles=legend_handles2, loc="lower right", framealpha=0.9)

fig.suptitle("ST021_PYRAMIDENSTRASSE: the one cluster where deterministic and\n"
              "Monte Carlo LCOH comparisons disagree on the winning technology",
              fontsize=11.5, y=1.03)
fig.tight_layout()

out_path = OUT_DIR / "fig18_st021_flip_case.png"
fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved: {out_path}")
