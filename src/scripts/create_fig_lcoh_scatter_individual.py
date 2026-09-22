"""
fig03_lcoh_scatter ("Scenario-by-Scenario LCOH Comparison"), generalized
from ST010-only to one standalone figure per street cluster.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path("results")
OUT_DIR = RESULTS / "thesis" / "figures" / "lcoh_scatter_per_cluster"
OUT_DIR.mkdir(parents=True, exist_ok=True)

C_DH, C_HP = "#c0392b", "#1a5276"

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
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})

saved = []
for d in sorted((RESULTS / "economics").glob("ST*")):
    cid = d.name
    label = cid.split("_", 1)[1].replace("_", " ").title() + f" ({cid.split('_')[0]})"
    mc = pd.read_csv(d / "economics_monte_carlo_samples.csv")

    dh = mc["lcoh_dh_eur_per_mwh"].values
    hp = mc["lcoh_hp_eur_per_mwh"].values
    hp_wins = dh > hp

    fig, ax = plt.subplots(figsize=(7, 6))

    ax.scatter(hp[hp_wins], dh[hp_wins], alpha=0.35, s=14, color=C_HP,
               label=f"HP preferred ({hp_wins.sum()} / {len(hp_wins)} scenarios)")
    ax.scatter(hp[~hp_wins], dh[~hp_wins], alpha=0.35, s=14, color=C_DH,
               label=f"DH preferred ({(~hp_wins).sum()} / {len(hp_wins)} scenarios)")

    all_v = np.concatenate([dh, hp])
    vmin, vmax = all_v.min() * 0.95, all_v.max() * 1.05
    ax.plot([vmin, vmax], [vmin, vmax], "k--", linewidth=1.2, alpha=0.5, label="Break-even line")
    ax.fill_between([vmin, vmax], [vmin, vmin], [vmin, vmax], alpha=0.04, color=C_DH)
    ax.fill_between([vmin, vmax], [vmax, vmax], [vmin, vmax], alpha=0.04, color=C_HP)

    ax.text(vmax * 0.98, vmax * 0.97, "DH\ncheaper", ha="right", va="top",
            fontsize=8, color=C_DH, alpha=0.7)
    ax.text(vmin * 1.02, vmin * 1.03, "HP\ncheaper", ha="left", va="bottom",
            fontsize=8, color=C_HP, alpha=0.7)

    ax.set_xlim(vmin, vmax)
    ax.set_ylim(vmin, vmax)
    ax.set_xlabel("HP LCOH (EUR / MWh)")
    ax.set_ylabel("DH LCOH (EUR / MWh)")
    ax.set_title(f"Scenario-by-Scenario LCOH Comparison\n{label}")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()

    out_path = OUT_DIR / f"{cid}.png"
    fig.savefig(out_path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    saved.append(out_path)
    print(f"Saved: {out_path}")

print(f"\n{len(saved)} figures written to {OUT_DIR}")
