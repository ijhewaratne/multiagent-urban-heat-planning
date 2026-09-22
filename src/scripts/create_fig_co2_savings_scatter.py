"""
CO2 "panel b" analog: since CO2 intensity (kg/MWh) and its Monte Carlo
win-fraction are identical across all 24 clusters (HP wins 65% every time —
the model draws emission factors from the same global distributions
regardless of cluster topology), a deterministic-gap-vs-win-fraction
scatter (fig18 panel b) is degenerate for CO2. The informative equivalent
is absolute annual CO2 stakes: how many tonnes/year separate DH and HP once
the fixed per-MWh gap is scaled by each cluster's heat demand.
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

rows = []
for d in sorted((RESULTS / "economics").glob("ST*")):
    cid = d.name
    det = json.load(open(d / "economics_deterministic.json"))
    co2_dh_t = det["co2_dh_t_per_a"]
    co2_hp_t = det["co2_hp_t_per_a"]
    rows.append({
        "cluster": cid,
        "label": cid.split("_", 1)[1].replace("_", " ").title(),
        "annual_heat_mwh": det["annual_heat_mwh"],
        "co2_savings_t": co2_dh_t - co2_hp_t,  # tonnes/yr saved by choosing HP
    })

df = pd.DataFrame(rows).sort_values("annual_heat_mwh").reset_index(drop=True)

fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))

# ── Panel A: annual CO2 savings from HP, ranked by cluster ─────────────────
ax = axes[0]
colors = plt.cm.viridis(np.linspace(0.15, 0.9, len(df)))
y = np.arange(len(df))
ax.barh(y, df["co2_savings_t"], color=C_HP, alpha=0.85, edgecolor="white", linewidth=0.4)
ax.set_yticks(y)
ax.set_yticklabels([f"{r.cluster.split('_')[0]}  {r.label}" for r in df.itertuples()], fontsize=7)
ax.set_xlabel("Annual CO₂ saved by choosing HP over DH (t/yr)")
ax.set_title("(a) CO₂ Savings Potential — Absolute Stakes\nAll 24 Clusters, sorted by annual heat demand")
ax.axvline(0, color="black", lw=0.8)

# ── Panel B: savings vs. heat demand — shows the fixed-ratio relationship ──
ax2 = axes[1]
ax2.scatter(df["annual_heat_mwh"], df["co2_savings_t"], color=C_HP, s=55,
            edgecolors="black", linewidths=0.6, alpha=0.85, zorder=5)

# fit line to show it's a fixed proportion (16.18 kg/MWh gap)
x_fit = np.array([0, df["annual_heat_mwh"].max() * 1.05])
slope = df["co2_savings_t"].iloc[-1] / df["annual_heat_mwh"].iloc[-1]
ax2.plot(x_fit, slope * x_fit, color=C_GREY, lw=1.3, linestyle="--",
         label=f"Fixed ratio: {slope*1000:.1f} kg CO₂/MWh\n(same in all 24 clusters)")

biggest = df.iloc[-1]
ax2.annotate(f"{biggest.label}\n{biggest.co2_savings_t:.0f} t/yr saved",
             xy=(biggest.annual_heat_mwh, biggest.co2_savings_t),
             xytext=(biggest.annual_heat_mwh * 0.55, biggest.co2_savings_t * 1.05),
             fontsize=8.5, color=C_HP, fontweight="bold",
             arrowprops=dict(arrowstyle="->", color=C_HP, lw=1.1))

ax2.set_xlabel("Annual heat demand (MWh/yr)")
ax2.set_ylabel("Annual CO₂ saved by choosing HP over DH (t/yr)")
ax2.set_title("(b) Savings Scale Linearly with Demand\n— the % win-fraction never changes, only the tonnage at stake")
ax2.legend(loc="upper left", framealpha=0.9)

fig.suptitle("CO₂ Reduction Potential of Heat Pumps over District Heating\n"
             "Win-fraction is identical (HP wins 65% of Monte Carlo draws) in every cluster — "
             "what varies is the absolute tonnage",
             fontsize=12, y=1.06)
fig.tight_layout()

out_path = OUT_DIR / "fig21_co2_savings_all_clusters.png"
fig.savefig(out_path, dpi=280, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved: {out_path}")
