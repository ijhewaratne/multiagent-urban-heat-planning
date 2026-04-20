"""
Fig 3.16: LCOH Calculation — Discounted Lifecycle Cash Flow
Matplotlib rendering of the TikZ cash-flow diagram (no external LaTeX).
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

fig = plt.figure(figsize=(12, 8))

# Gridspec for complex layout
gs = fig.add_gridspec(3, 3, height_ratios=[1.2, 1.8, 0.6], width_ratios=[1.5, 1, 1],
                      left=0.08, right=0.95, top=0.90, bottom=0.10,
                      hspace=0.35, wspace=0.30)

# Main axis for timeline + CAPEX + OPEX
ax_main = fig.add_subplot(gs[1, :2])
ax_main.set_xlim(-0.5, 11)
ax_main.set_ylim(-1.0, 5.0)
ax_main.axis("off")

# Discount curve axis (top)
ax_discount = fig.add_subplot(gs[0, :2])
ax_discount.set_xlim(-0.5, 11)
ax_discount.set_ylim(0, 1.2)

# LCOH formula box axis (right side)
ax_formula = fig.add_subplot(gs[:2, 2])
ax_formula.set_xlim(0, 1)
ax_formula.set_ylim(0, 1)
ax_formula.axis("off")

# Energy delivered axis (bottom)
ax_energy = fig.add_subplot(gs[2, :2])
ax_energy.set_xlim(0, 1)
ax_energy.set_ylim(0, 1)
ax_energy.axis("off")

# ------------------------------------------------------------------
# Colors
# ------------------------------------------------------------------
C_CAPEX = np.array([52, 103, 81]) / 255.0
C_OPEX = np.array([86, 160, 211]) / 255.0
C_DISCOUNT = np.array([200, 82, 45]) / 255.0
C_RESULT = np.array([162, 59, 114]) / 255.0
C_ENERGY = np.array([218, 165, 32]) / 255.0

# ------------------------------------------------------------------
# TIMELINE AXIS (in ax_main)
# ------------------------------------------------------------------
ax_main.annotate("", xy=(11, 0), xytext=(-0.5, 0),
                 arrowprops=dict(arrowstyle="->", color="black", lw=1.5))
ax_main.text(11.1, 0, "Time [years]", ha="left", va="center", fontsize=9, fontweight="bold")

for x in [0, 2, 4, 6, 8, 10]:
    ax_main.plot([x, x], [0, -0.12], "k-", lw=1.2)
    ax_main.text(x, -0.22, str(x*2), ha="center", va="top", fontsize=8)

ax_main.plot([10.5, 10.5], [0, -0.12], "k-", lw=1.2)
ax_main.text(10.5, -0.22, "20", ha="center", va="top", fontsize=8)

# ------------------------------------------------------------------
# CAPEX BAR (Year 0)
# ------------------------------------------------------------------
bar = Rectangle((0, 0), 0.3, 3.5, facecolor=C_CAPEX, edgecolor=C_CAPEX, alpha=0.7, lw=2, zorder=3)
ax_main.add_patch(bar)
ax_main.plot([0, 0, 0.3, 0.3], [0, 3.5, 3.5, 0], color=C_CAPEX, lw=2, zorder=4)
ax_main.text(0.15, 3.5, "CAPEX", ha="center", va="bottom", fontsize=10, fontweight="bold", color=C_CAPEX)
ax_main.text(0.15, 4.15, r"$C_{inv}(0)$" + "\nInitial Network\nInvestment",
             ha="center", va="bottom", fontsize=7, color="black", linespacing=0.95)

# ------------------------------------------------------------------
# OPEX ARROWS (Annual)
# ------------------------------------------------------------------
opex_years = np.arange(1, 11)
opex_heights = np.array([2.8, 2.6, 2.4, 2.2, 2.0, 1.9, 1.8, 1.7, 1.6, 1.5])

for yr, h in zip(opex_years, opex_heights):
    ax_main.annotate("", xy=(yr, h), xytext=(yr, 0),
                     arrowprops=dict(arrowstyle="-|>", color=C_OPEX, lw=1.5))
    ax_main.plot(yr, h, "o", color=C_OPEX, markersize=4, zorder=4)

# Dotted continuation
ax_main.plot([10.5, 10.5], [1.45, 0.8], ":", color=C_OPEX, lw=1.5)
ax_main.text(10.6, 1.1, r"$\cdots$", ha="left", va="center", fontsize=10, color=C_OPEX)

ax_main.text(5, 2.5, "OPEX (Annual)\n" + r"$C_{op}(t) + C_{main}(t)$",
             ha="center", va="bottom", fontsize=10, fontweight="bold", color=C_OPEX, linespacing=0.95)

# ------------------------------------------------------------------
# DISCOUNT CURVE (ax_discount)
# ------------------------------------------------------------------
x_disc = np.linspace(0, 10, 200)
y_disc = np.exp(-0.04 * x_disc)

ax_discount.fill_between(x_disc, 0, y_disc, color=C_DISCOUNT, alpha=0.30)
ax_discount.plot(x_disc, y_disc, color=C_DISCOUNT, lw=2.5)

ax_discount.set_xticks([0, 2, 4, 6, 8, 10])
ax_discount.set_xticklabels(["0", "4", "8", "12", "16", "20"], fontsize=8)
ax_discount.set_yticks([0, 0.5, 1.0])
ax_discount.set_yticklabels(["0", "0.5", "1"], fontsize=8)
ax_discount.set_ylabel(r"$(1+r)^{-t}$", fontsize=10, fontweight="bold", color=C_DISCOUNT)
ax_discount.set_xlim(-0.5, 11)
ax_discount.set_ylim(0, 1.2)
ax_discount.spines["top"].set_visible(False)
ax_discount.spines["right"].set_visible(False)
for spine in ["left", "bottom"]:
    ax_discount.spines[spine].set_linewidth(1.5)
    ax_discount.spines[spine].set_color(C_DISCOUNT)
ax_discount.tick_params(axis="both", colors=C_DISCOUNT, width=1.5)

ax_discount.text(8.5, 0.9, r"$r = 4\%$" + "\n" + r"$T = 20$ years",
                 ha="left", va="top", fontsize=8, color=C_DISCOUNT)

# ------------------------------------------------------------------
# LCOH FORMULA BOX (ax_formula)
# ------------------------------------------------------------------
formula_box = FancyBboxPatch((0.05, 0.15), 0.90, 0.70,
    boxstyle="round,pad=0.02,rounding_size=0.08",
    facecolor=C_RESULT, edgecolor=C_RESULT,
    linewidth=1.5, alpha=0.12, zorder=2)
ax_formula.add_patch(formula_box)

# Subtle shadow
shadow = FancyBboxPatch((0.07, 0.13), 0.90, 0.70,
    boxstyle="round,pad=0.02,rounding_size=0.08",
    facecolor="gray", edgecolor="none", alpha=0.15, zorder=1)
ax_formula.add_patch(shadow)

# Title + formula
ax_formula.text(0.50, 0.78, r"$\mathbf{Levelized\ Cost\ of\ Heat}$",
                ha="center", va="center", fontsize=11, color="black", transform=ax_formula.transAxes)

ax_formula.text(0.50, 0.58,
                r"$\mathrm{LCOH} = \dfrac{\sum_{t=0}^{T} \dfrac{C_{inv}(t) + C_{op}(t) + C_{main}(t)}{(1+r)^t}}{\sum_{t=0}^{T} \dfrac{E_{th}(t)}{(1+r)^t}}$",
                ha="center", va="center", fontsize=10, color="black", transform=ax_formula.transAxes)

# Legend items with colored squares
legend_items = [
    ("CAPEX (Capital)", C_CAPEX),
    ("OPEX (Operating)", C_OPEX),
    ("Discount factor", C_DISCOUNT),
    ("Energy delivered", C_ENERGY),
]
ly = 0.32
for label_text, color in legend_items:
    sq = Rectangle((0.18, ly - 0.012), 0.04, 0.024,
                   facecolor=color, edgecolor="none", transform=ax_formula.transAxes, zorder=3)
    ax_formula.add_patch(sq)
    ax_formula.text(0.24, ly, label_text, ha="left", va="center",
                    fontsize=8, color="black", transform=ax_formula.transAxes, zorder=3)
    ly -= 0.065

# Arrow from discount plot to formula box (figure coords)
fig.patches.append(mpatches.FancyArrowPatch(
    (0.62, 0.72), (0.73, 0.72),
    transform=fig.transFigure,
    arrowstyle="-|>", mutation_scale=15,
    color=C_RESULT, lw=2.0, zorder=5
))

# ------------------------------------------------------------------
# ENERGY DELIVERED BOX (ax_energy)
# ------------------------------------------------------------------
energy_box = FancyBboxPatch((0.05, 0.20), 0.90, 0.60,
    boxstyle="round,pad=0.02,rounding_size=0.08",
    facecolor=C_ENERGY, edgecolor=C_ENERGY,
    linewidth=1.5, alpha=0.20, zorder=2)
ax_energy.add_patch(energy_box)

ax_energy.text(0.50, 0.55,
               r"$\mathbf{Energy\ Delivered:}\ E_{th}(t) = \sum_{i \in \mathcal{S}} q_i(t)$",
               ha="center", va="center", fontsize=10, color="black",
               transform=ax_energy.transAxes, zorder=3)
ax_energy.text(0.50, 0.30,
               "(Thermal energy normalized across planning horizon)",
               ha="center", va="center", fontsize=8, color="black",
               transform=ax_energy.transAxes, zorder=3)

# ------------------------------------------------------------------
# Title & Caption
# ------------------------------------------------------------------
fig.suptitle("LCOH Calculation: Discounted Lifecycle Cash Flow",
             fontsize=14, fontweight="bold", y=0.97)

fig.text(0.5, 0.02, r"AGFW cost conventions applied over $T = 20$ year planning horizon",
         ha="center", fontsize=9, style="italic", color="gray")

fig.savefig("figures/fig_3_16_lcoh_cashflow.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_16_lcoh_cashflow.pdf", bbox_inches="tight")
print("Saved figures/fig_3_16_lcoh_cashflow.png")
print("Saved figures/fig_3_16_lcoh_cashflow.pdf")
