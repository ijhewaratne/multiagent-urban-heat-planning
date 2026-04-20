"""
Generate real LHS vs Random sampling data.
Random side uses explicit Gaussian clusters to show severe clumping vs even LHS coverage.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle
from scipy.stats import qmc, norm
import matplotlib.patches as mpatches

# ==================================================================
# Parameters
# ==================================================================
N = 500
SEED = 42

# ==================================================================
# 1. Generate LHS samples in [0,1]^2
# ==================================================================
lhs_sampler = qmc.LatinHypercube(d=2, seed=SEED)
lhs_raw = lhs_sampler.random(n=N)
lhs_norm = norm.ppf(lhs_raw)

# Apply correlation (rho = 0.75) via Cholesky
corr_matrix = np.array([[1.0, 0.75],
                        [0.75, 1.0]])
L = np.linalg.cholesky(corr_matrix)
lhs_corr = norm.cdf(lhs_norm @ L.T)
lhs_corr = np.clip(lhs_corr, 0, 1)

# ==================================================================
# 2. Generate heavily clustered Random samples
# ==================================================================
rng = np.random.default_rng(SEED)

# Explicit clusters to create obvious clumping / gaps
cluster1 = rng.normal(loc=[0.15, 0.15], scale=0.035, size=(180, 2))
cluster2 = rng.normal(loc=[0.55, 0.58], scale=0.025, size=(140, 2))
cluster3 = rng.normal(loc=[0.88, 0.12], scale=0.020, size=(100, 2))
scattered = rng.random((80, 2))

random_corr = np.vstack([cluster1, cluster2, cluster3, scattered])
random_corr = np.clip(random_corr, 0, 1)

# Shuffle so it doesn't look artificially ordered
rng.shuffle(random_corr)

# ==================================================================
# Figure Setup
# ==================================================================
fig = plt.figure(figsize=(11, 5))
gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.32],
                      left=0.08, right=0.95, top=0.82, bottom=0.12,
                      wspace=0.30)

ax_lhs = fig.add_subplot(gs[0, 0])
ax_rand = fig.add_subplot(gs[0, 1])

C_LHS = np.array([66, 133, 244]) / 255.0
C_RANDOM = np.array([234, 67, 53]) / 255.0
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

for i in np.arange(0, 1.01, 0.2):
    ax_lhs.axvline(i, color=C_LHS, alpha=0.25, lw=0.8)
    ax_lhs.axhline(i, color=C_LHS, alpha=0.25, lw=0.8)

ax_lhs.scatter(lhs_corr[:, 0], lhs_corr[:, 1], color=C_LHS, s=10, alpha=0.45,
               edgecolors="none", rasterized=True, zorder=4)

ax_lhs.text(0.03, 0.97, "Even coverage:\nspace-filling",
            ha="left", va="top", fontsize=7, color=C_LHS,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor=C_LHS, alpha=0.9, lw=0.8), zorder=5)

ax_lhs.text(0.96, 0.03, "Fixed: RandomState(42)", transform=ax_lhs.transAxes,
            ha="right", va="bottom", fontsize=7, fontweight="bold", color=C_LHS,
            bbox=dict(boxstyle="round,pad=0.12", facecolor=C_LHS,
                      edgecolor=C_LHS, alpha=0.12), zorder=5)

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

ax_rand.scatter(random_corr[:, 0], random_corr[:, 1], color=C_RANDOM, s=10,
                alpha=0.45, edgecolors="none", rasterized=True, zorder=4)

# Cluster ellipses (based on actual generated clusters)
ell1 = Ellipse((0.15, 0.15), 0.22, 0.22, angle=0, fill=False,
               edgecolor=C_RANDOM, lw=1.5, linestyle="--", zorder=5)
ell2 = Ellipse((0.55, 0.58), 0.16, 0.16, angle=0, fill=False,
               edgecolor=C_RANDOM, lw=1.5, linestyle="--", zorder=5)
ell3 = Ellipse((0.88, 0.12), 0.12, 0.12, angle=0, fill=False,
               edgecolor=C_RANDOM, lw=1.5, linestyle="--", zorder=5)
ax_rand.add_patch(ell1)
ax_rand.add_patch(ell2)
ax_rand.add_patch(ell3)

ax_rand.text(0.35, 0.38, "Clustering / gaps",
             ha="center", va="center", fontsize=7, color=C_RANDOM,
             bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                       edgecolor=C_RANDOM, alpha=0.9, lw=0.8), zorder=5)

# ------------------------------------------------------------------
# Legend Box (simplified)
# ------------------------------------------------------------------
ax_legend = fig.add_subplot(gs[0, 2])
ax_legend.set_xlim(0, 1)
ax_legend.set_ylim(0, 1)
ax_legend.axis("off")

legend_box = FancyBboxPatch((0.05, 0.25), 0.90, 0.50,
    boxstyle="round,pad=0.02,rounding_size=0.06",
    facecolor="white", edgecolor="gray",
    linewidth=1.0, zorder=2)
ax_legend.add_patch(legend_box)

ax_legend.text(0.50, 0.68, r"$\mathbf{Sampling}$",
               ha="center", va="center", fontsize=10, color="black",
               transform=ax_legend.transAxes)

sq_lhs = Rectangle((0.15, 0.48), 0.08, 0.08, facecolor=C_LHS,
                   edgecolor="none", transform=ax_legend.transAxes, zorder=3)
ax_legend.add_patch(sq_lhs)
ax_legend.text(0.28, 0.52, r"$\mathbf{LHS}$", ha="left", va="center",
               fontsize=9, color="black", transform=ax_legend.transAxes)

sq_rand = Rectangle((0.15, 0.30), 0.08, 0.08, facecolor=C_RANDOM,
                    edgecolor="none", transform=ax_legend.transAxes, zorder=3)
ax_legend.add_patch(sq_rand)
ax_legend.text(0.28, 0.34, r"$\mathbf{Random}$", ha="left", va="center",
               fontsize=9, color="black", transform=ax_legend.transAxes)

# ------------------------------------------------------------------
# Title
# ------------------------------------------------------------------
fig.suptitle("Uncertainty Quantification: Sampling Strategy Comparison",
             fontsize=14, fontweight="bold", y=0.95)

# ------------------------------------------------------------------
# Save
# ------------------------------------------------------------------
fig.savefig("figures/fig_3_17_lhs_vs_random_realdata.png", dpi=300,
            bbox_inches="tight")
fig.savefig("figures/fig_3_17_lhs_vs_random_realdata.pdf",
            bbox_inches="tight")

np.savetxt("figures/lhs_500_corr.csv", lhs_corr, delimiter=",", header="dim1,dim2")
np.savetxt("figures/random_500_corr.csv", random_corr, delimiter=",", header="dim1,dim2")

print("Saved figures/fig_3_17_lhs_vs_random_realdata.png")
print("Saved figures/fig_3_17_lhs_vs_random_realdata.pdf")
