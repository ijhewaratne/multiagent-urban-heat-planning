"""
Fig 3.17: Uncertainty Quantification — Sampling Strategy Comparison
Matplotlib fallback for the LHS vs Random sampling TikZ figure.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle
import numpy as np

fig = plt.figure(figsize=(12, 6.5))

# Main gridspec: left plot | right plot | legend
gs = fig.add_gridspec(2, 3, height_ratios=[1.8, 0.8], width_ratios=[1, 1, 0.45],
                      left=0.08, right=0.95, top=0.88, bottom=0.10,
                      hspace=0.35, wspace=0.30)

ax_lhs = fig.add_subplot(gs[0, 0])
ax_rand = fig.add_subplot(gs[0, 1])

# ------------------------------------------------------------------
# Colors
# ------------------------------------------------------------------
C_LHS = np.array([66, 133, 244]) / 255.0
C_RANDOM = np.array([234, 67, 53]) / 255.0
C_CORR = np.array([162, 59, 114]) / 255.0
C_GRID = np.array([189, 189, 189]) / 255.0

# ------------------------------------------------------------------
# LHS Plot
# ------------------------------------------------------------------
ax_lhs.set_xlim(0, 1)
ax_lhs.set_ylim(0, 1)
ax_lhs.set_aspect("equal", adjustable="box")
ax_lhs.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax_lhs.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax_lhs.tick_params(axis="both", labelsize=8)
ax_lhs.set_xlabel("Stratified Dimension 1 (e.g., Electricity Price)", fontsize=8)
ax_lhs.set_ylabel("Stratified Dimension 2 (e.g., Biomass Price)", fontsize=8)
ax_lhs.set_title(r"$\mathbf{Latin\ Hypercube\ Sampling\ (LHS)}$" + "\n$N=500$ samples",
                 fontsize=10, linespacing=0.95)

# Grid
for i in np.arange(0, 1.01, 0.2):
    ax_lhs.axvline(i, color=C_LHS, alpha=0.30, lw=0.8, linestyle="-")
    ax_lhs.axhline(i, color=C_LHS, alpha=0.30, lw=0.8, linestyle="-")

# LHS points (one per visible stratum)
lhs_pts = np.array([
    [0.1,0.15], [0.3,0.05], [0.5,0.25], [0.7,0.1], [0.9,0.2],
    [0.15,0.35], [0.35,0.3], [0.55,0.4], [0.75,0.35], [0.95,0.45],
    [0.05,0.55], [0.25,0.5], [0.45,0.6], [0.65,0.5], [0.85,0.65],
    [0.2,0.75], [0.4,0.7], [0.6,0.8], [0.8,0.75], [0.1,0.9],
    [0.12,0.95], [0.32,0.85], [0.52,0.95], [0.72,0.9], [0.92,0.85]
])
ax_lhs.scatter(lhs_pts[:, 0], lhs_pts[:, 1], color=C_LHS, s=45, alpha=0.7, edgecolors="none", zorder=4)

# Annotation
ax_lhs.text(0.03, 0.97, "Even coverage:\none sample per stratum",
            ha="left", va="top", fontsize=7, color=C_LHS,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=C_LHS, alpha=0.9), zorder=5)

# Fixed seed badge
ax_lhs.text(0.96, 0.03, "Fixed: RandomState(42)", transform=ax_lhs.transAxes,
            ha="right", va="bottom", fontsize=7, fontweight="bold", color=C_LHS,
            bbox=dict(boxstyle="round,pad=0.12", facecolor=C_LHS, edgecolor=C_LHS, alpha=0.12), zorder=5)

# ------------------------------------------------------------------
# Random Plot
# ------------------------------------------------------------------
ax_rand.set_xlim(0, 1)
ax_rand.set_ylim(0, 1)
ax_rand.set_aspect("equal", adjustable="box")
ax_rand.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax_rand.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax_rand.tick_params(axis="both", labelsize=8)
ax_rand.set_xlabel("Random Dimension 1 (e.g., Electricity Price)", fontsize=8)
ax_rand.set_ylabel("Random Dimension 2 (e.g., Biomass Price)", fontsize=8)
ax_rand.set_title(r"$\mathbf{Random\ (Pseudo-Monte\ Carlo)}$" + "\n$N=500$ samples",
                  fontsize=10, linespacing=0.95)

# Random points
rand_pts = np.array([
    [0.15,0.2], [0.18,0.22], [0.12,0.18], [0.2,0.25], [0.14,0.24],
    [0.16,0.19], [0.19,0.21], [0.13,0.23], [0.17,0.17], [0.11,0.21],
    [0.8,0.8], [0.85,0.75], [0.9,0.85],
    [0.4,0.6], [0.45,0.55], [0.42,0.58], [0.38,0.62], [0.44,0.52],
    [0.41,0.57], [0.46,0.53], [0.39,0.59], [0.43,0.61], [0.37,0.56],
    [0.6,0.3], [0.65,0.35], [0.55,0.28], [0.62,0.32], [0.58,0.25],
    [0.7,0.7], [0.75,0.72], [0.68,0.68], [0.72,0.75], [0.66,0.73],
    [0.95,0.1], [0.92,0.12], [0.9,0.08], [0.93,0.15], [0.88,0.11]
])
ax_rand.scatter(rand_pts[:, 0], rand_pts[:, 1], color=C_RANDOM, s=45, alpha=0.6, edgecolors="none", zorder=4)

# Clumping ellipses
ellipse1 = Ellipse((0.15, 0.20), 0.12, 0.12, angle=0, fill=False, edgecolor=C_RANDOM, lw=1.5, linestyle="--", zorder=5)
ellipse2 = Ellipse((0.42, 0.57), 0.10, 0.10, angle=0, fill=False, edgecolor=C_RANDOM, lw=1.5, linestyle="--", zorder=5)
ax_rand.add_patch(ellipse1)
ax_rand.add_patch(ellipse2)

ax_rand.text(0.42, 0.38, "Clustering / gaps",
             ha="center", va="center", fontsize=7, color=C_RANDOM,
             bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=C_RANDOM, alpha=0.9), zorder=5)

# ------------------------------------------------------------------
# Arrow between plots
# ------------------------------------------------------------------
fig.patches.append(mpatches.FancyArrowPatch(
    (0.405, 0.62), (0.555, 0.62),
    transform=fig.transFigure,
    arrowstyle="-|>", mutation_scale=18,
    color=C_LHS, lw=2.5, zorder=5
))
fig.text(0.48, 0.645, "Preferred for robustness",
         ha="center", va="bottom", fontsize=8, fontweight="bold",
         bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor=C_LHS, alpha=0.95), zorder=6)

# ------------------------------------------------------------------
# Correlation Structure Box (bottom center)
# ------------------------------------------------------------------
ax_corr = fig.add_subplot(gs[1, :2])
ax_corr.set_xlim(0, 1)
ax_corr.set_ylim(0, 1)
ax_corr.axis("off")

corr_box = FancyBboxPatch((0.22, 0.15), 0.56, 0.70,
    boxstyle="round,pad=0.02,rounding_size=0.06",
    facecolor="white", edgecolor=C_CORR,
    linewidth=1.5, zorder=2)
ax_corr.add_patch(corr_box)

ax_corr.text(0.50, 0.72, r"$\mathbf{Correlation\ Structures}$",
             ha="center", va="center", fontsize=10, color="black", transform=ax_corr.transAxes)

ax_corr.text(0.50, 0.42,
             r"$\rho_{bio-elec} = 0.75$ (price coupling)" + "\n"
             + r"$\rho_{demand-COP} = -0.3$ (physical)" + "\n"
             + "Cholesky decomposition ensures\nrealistic dependency structure",
             ha="center", va="center", fontsize=9, color="black", linespacing=1.05, transform=ax_corr.transAxes)

# ------------------------------------------------------------------
# Legend Box (right side)
# ------------------------------------------------------------------
ax_legend = fig.add_subplot(gs[:, 2])
ax_legend.set_xlim(0, 1)
ax_legend.set_ylim(0, 1)
ax_legend.axis("off")

legend_box = FancyBboxPatch((0.05, 0.25), 0.90, 0.55,
    boxstyle="round,pad=0.02,rounding_size=0.06",
    facecolor="white", edgecolor="gray",
    linewidth=1.0, zorder=2)
ax_legend.add_patch(legend_box)

ax_legend.text(0.50, 0.74, r"$\mathbf{Sampling\ Comparison}$",
               ha="center", va="center", fontsize=10, color="black", transform=ax_legend.transAxes)

# LHS legend item
sq_lhs = Rectangle((0.12, 0.62), 0.06, 0.04, facecolor=C_LHS, edgecolor="none", transform=ax_legend.transAxes, zorder=3)
ax_legend.add_patch(sq_lhs)
ax_legend.text(0.21, 0.64, r"$\mathbf{LHS\ (Fixed\ Seed\ 42):}$", ha="left", va="center", fontsize=8, color="black", transform=ax_legend.transAxes)
ax_legend.text(0.21, 0.57, "Stratified, even coverage", ha="left", va="center", fontsize=7, color="black", transform=ax_legend.transAxes)
ax_legend.text(0.21, 0.51, "Guaranteed space filling", ha="left", va="center", fontsize=7, color="black", transform=ax_legend.transAxes)
ax_legend.text(0.21, 0.45, r"Reproducible $\omega_{DH}$", ha="left", va="center", fontsize=7, color="black", transform=ax_legend.transAxes)

# Random legend item
sq_rand = Rectangle((0.12, 0.36), 0.06, 0.04, facecolor=C_RANDOM, edgecolor="none", transform=ax_legend.transAxes, zorder=3)
ax_legend.add_patch(sq_rand)
ax_legend.text(0.21, 0.38, r"$\mathbf{Random:}$", ha="left", va="center", fontsize=8, color="black", transform=ax_legend.transAxes)
ax_legend.text(0.21, 0.31, "Unstructured clumping", ha="left", va="center", fontsize=7, color="black", transform=ax_legend.transAxes)
ax_legend.text(0.21, 0.25, "Gaps in parameter space", ha="left", va="center", fontsize=7, color="black", transform=ax_legend.transAxes)
ax_legend.text(0.21, 0.19, "Higher variance in estimates", ha="left", va="center", fontsize=7, color="black", transform=ax_legend.transAxes)

# ------------------------------------------------------------------
# Title
# ------------------------------------------------------------------
fig.suptitle("Uncertainty Quantification: Sampling Strategy Comparison",
             fontsize=14, fontweight="bold", y=0.97)

fig.savefig("figures/fig_3_17_lhs_vs_random.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_17_lhs_vs_random.pdf", bbox_inches="tight")
print("Saved figures/fig_3_17_lhs_vs_random.png")
print("Saved figures/fig_3_17_lhs_vs_random.pdf")
