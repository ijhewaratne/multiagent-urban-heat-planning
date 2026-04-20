"""
Fig 3.8: Five-Gate Hierarchical Decision Flow
Renders the deterministic decision cascade from KPI Contract to Delta Decision.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon, Circle
import numpy as np

fig, ax = plt.subplots(figsize=(10, 14))
ax.set_xlim(0, 10)
ax.set_ylim(-2.5, 14)
ax.axis("off")

# ------------------------------------------------------------------
# Colors
# ------------------------------------------------------------------
C_GATE_FILL = "#e3f2fd"
C_GATE_STROKE = "#4285f4"
C_REC_FILL = "#e8f5e9"
C_REC_STROKE = "#34a853"
C_TIE_FILL = "#fff8e1"
C_TIE_STROKE = "#fbbc05"
C_DEC_FILL = "#ffffff"
C_DEC_STROKE = "#3c4043"
C_DARK = "#202124"
C_ARROW = "#5f6368"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def draw_rounded_box(ax, cx, cy, w, h, text, fc, ec, fs=8, fw="normal", ls="solid", lw=1.5):
    box = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls, zorder=3)
    ax.add_patch(box)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=fs, fontweight=fw, color=C_DARK, linespacing=0.95, zorder=4)
    return box

def draw_diamond(ax, cx, cy, size, text, fc, ec):
    diamond = Polygon([
        [cx, cy + size],
        [cx + size*1.4, cy],
        [cx, cy - size],
        [cx - size*1.4, cy],
    ], closed=True, facecolor=fc, edgecolor=ec, linewidth=1.5, zorder=3)
    ax.add_patch(diamond)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=8, fontweight="bold", color=C_DARK, linespacing=0.9, zorder=4)
    return diamond

def arrow(ax, start, end, color=C_ARROW, lw=1.2, ls="solid"):
    ax.add_patch(mpatches.FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=12,
        color=color, linewidth=lw, linestyle=ls, zorder=2))

def label(ax, x, y, text, ha="center", va="center", fs=7, c=C_DARK, fw="normal"):
    ax.text(x, y, text, ha=ha, va=va, fontsize=fs, fontweight=fw, color=c, zorder=5)

# ------------------------------------------------------------------
# Positions
# ------------------------------------------------------------------
cx = 5.0

# Main vertical nodes
y_start = 12.8
y_g1 = 11.3
y_d1 = 10.1
y_g2 = 8.8
y_d2 = 7.6
y_g3 = 6.3
y_d3 = 5.1
y_g4 = 3.8
y_d4 = 2.6
y_g5 = 1.3
y_end = -0.5

# Side recommendation x positions
x_left = 1.6
x_right = 8.4

# ------------------------------------------------------------------
# Start
# ------------------------------------------------------------------
start = draw_rounded_box(ax, cx, y_start, 2.8, 0.7,
    "Input: KPI Contract $\mathcal{K}$", "#f8f9fa", C_DEC_STROKE, fs=9, fw="bold")

# ------------------------------------------------------------------
# Gate 1: Feasibility
# ------------------------------------------------------------------
sub = FancyBboxPatch((2.2, y_g1 - 0.65), 5.6, 1.85,
    boxstyle="round,pad=0.02,rounding_size=0.2",
    facecolor=C_GATE_FILL, edgecolor=C_GATE_STROKE,
    linewidth=1.0, alpha=0.15, linestyle="--", zorder=1)
ax.add_patch(sub)
label(ax, 2.4, y_g1 + 0.55, "Gate 1: Feasibility", ha="left", va="center", fs=8, c=C_GATE_STROKE, fw="bold")

g1 = draw_rounded_box(ax, cx, y_g1, 3.4, 0.75,
    "Feasibility Check:\nEN 13941-1 & VDE-AR-N 4100", C_GATE_FILL, C_GATE_STROKE, fs=8, fw="bold")
arrow(ax, (cx, y_start - 0.35), (cx, y_g1 + 0.375))

d1 = draw_diamond(ax, cx, y_d1, 0.55, "Only 1\nFeasible?", C_DEC_FILL, C_DEC_STROKE)
arrow(ax, (cx, y_g1 - 0.375), (cx, y_d1 + 0.55))

# G1 branches
r1a = draw_rounded_box(ax, x_left, y_d1, 2.2, 0.6, "Recommend A", C_REC_FILL, C_REC_STROKE, fs=8, fw="bold")
r1b = draw_rounded_box(ax, x_right, y_d1, 2.2, 0.6, "Recommend B", C_REC_FILL, C_REC_STROKE, fs=8, fw="bold")
arrow(ax, (cx - 0.55*1.4 + 0.05, y_d1 + 0.30), (x_left + 1.1, y_d1))
label(ax, 3.3, y_d1 + 0.28, "Yes: A", ha="center", va="bottom", fs=7, c=C_DARK)
arrow(ax, (cx + 0.55*1.4 - 0.05, y_d1 + 0.30), (x_right - 1.1, y_d1))
label(ax, 6.7, y_d1 + 0.28, "Yes: B", ha="center", va="bottom", fs=7, c=C_DARK)

# G1 -> G2
arrow(ax, (cx, y_d1 - 0.55), (cx, y_g2 + 0.375))
label(ax, cx + 0.25, (y_d1 + y_g2)/2, "Both", ha="left", va="center", fs=7, c=C_DARK)

# ------------------------------------------------------------------
# Gate 2: Cost Dominance
# ------------------------------------------------------------------
sub = FancyBboxPatch((2.2, y_g2 - 0.65), 5.6, 1.85,
    boxstyle="round,pad=0.02,rounding_size=0.2",
    facecolor=C_GATE_FILL, edgecolor=C_GATE_STROKE,
    linewidth=1.0, alpha=0.15, linestyle="--", zorder=1)
ax.add_patch(sub)
label(ax, 2.4, y_g2 + 0.55, "Gate 2: Cost Dominance", ha="left", va="center", fs=8, c=C_GATE_STROKE, fw="bold")

g2 = draw_rounded_box(ax, cx, y_g2, 3.4, 0.75,
    "Cost Dominance:\n$\Delta$LCOH > 5%", C_GATE_FILL, C_GATE_STROKE, fs=8, fw="bold")

d2 = draw_diamond(ax, cx, y_d2, 0.55, "Clear\nWinner?", C_DEC_FILL, C_DEC_STROKE)
arrow(ax, (cx, y_g2 - 0.375), (cx, y_d2 + 0.55))

# G2 branches
r2 = draw_rounded_box(ax, x_right, y_d2, 2.4, 0.6, "Recommend Cheaper", C_REC_FILL, C_REC_STROKE, fs=8, fw="bold")
indiff = draw_rounded_box(ax, x_left, y_d2, 2.2, 0.6, "$\\varepsilon$-Indifference", C_TIE_FILL, C_TIE_STROKE, fs=8, fw="bold")

arrow(ax, (cx + 0.55*1.4 - 0.05, y_d2 + 0.25), (x_right - 1.2, y_d2))
label(ax, 6.7, y_d2 + 0.25, "Yes", ha="center", va="bottom", fs=7, c=C_DARK)

# Dashed arrow for indifference (matches Mermaid dotted line)
ax.add_patch(mpatches.FancyArrowPatch(
    (cx - 0.55*1.4 + 0.05, y_d2 - 0.10),
    (x_left + 1.1, y_d2),
    arrowstyle="-|>", mutation_scale=12,
    color=C_ARROW, linewidth=1.2, linestyle="--", zorder=2))
label(ax, 3.3, y_d2 - 0.10, "Tie", ha="center", va="top", fs=7, c=C_DARK)

# G2 -> G3
arrow(ax, (cx, y_d2 - 0.55), (cx, y_g3 + 0.375))
label(ax, cx + 0.25, (y_d2 + y_g3)/2, "Tie / Indiff", ha="left", va="center", fs=7, c=C_DARK)

# ------------------------------------------------------------------
# Gate 3: Robustness
# ------------------------------------------------------------------
sub = FancyBboxPatch((2.2, y_g3 - 0.65), 5.6, 1.85,
    boxstyle="round,pad=0.02,rounding_size=0.2",
    facecolor=C_GATE_FILL, edgecolor=C_GATE_STROKE,
    linewidth=1.0, alpha=0.15, linestyle="--", zorder=1)
ax.add_patch(sub)
label(ax, 2.4, y_g3 + 0.55, "Gate 3: Robustness", ha="left", va="center", fs=8, c=C_GATE_STROKE, fw="bold")

g3 = draw_rounded_box(ax, cx, y_g3, 3.4, 0.75,
    "Robustness Check:\nMonte Carlo Win Fraction", C_GATE_FILL, C_GATE_STROKE, fs=8, fw="bold")

d3 = draw_diamond(ax, cx, y_d3, 0.55, "Tied?", C_DEC_FILL, C_DEC_STROKE)
arrow(ax, (cx, y_g3 - 0.375), (cx, y_d3 + 0.55))

# G3 branches
r3 = draw_rounded_box(ax, x_right, y_d3, 2.4, 0.6, "Recommend More Robust", C_REC_FILL, C_REC_STROKE, fs=8, fw="bold")
arrow(ax, (cx + 0.55*1.4 - 0.05, y_d3 + 0.05), (x_right - 1.2, y_d3))
label(ax, 6.7, y_d3 + 0.12, "No", ha="center", va="bottom", fs=7, c=C_DARK)

# G3 -> G4
arrow(ax, (cx, y_d3 - 0.55), (cx, y_g4 + 0.375))
label(ax, cx + 0.25, (y_d3 + y_g4)/2, "Yes", ha="left", va="center", fs=7, c=C_DARK)

# ------------------------------------------------------------------
# Gate 4: Emissions
# ------------------------------------------------------------------
sub = FancyBboxPatch((2.2, y_g4 - 0.65), 5.6, 1.85,
    boxstyle="round,pad=0.02,rounding_size=0.2",
    facecolor=C_GATE_FILL, edgecolor=C_GATE_STROKE,
    linewidth=1.0, alpha=0.15, linestyle="--", zorder=1)
ax.add_patch(sub)
label(ax, 2.4, y_g4 + 0.55, "Gate 4: Emissions", ha="left", va="center", fs=8, c=C_GATE_STROKE, fw="bold")

g4 = draw_rounded_box(ax, cx, y_g4, 3.4, 0.75,
    "Emissions Check:\nLower specific CO$_2$", C_GATE_FILL, C_GATE_STROKE, fs=8, fw="bold")

d4 = draw_diamond(ax, cx, y_d4, 0.55, "Tied?", C_DEC_FILL, C_DEC_STROKE)
arrow(ax, (cx, y_g4 - 0.375), (cx, y_d4 + 0.55))

# G4 branches
r4 = draw_rounded_box(ax, x_right, y_d4, 2.4, 0.6, "Recommend Lower Emission", C_REC_FILL, C_REC_STROKE, fs=8, fw="bold")
arrow(ax, (cx + 0.55*1.4 - 0.05, y_d4 + 0.05), (x_right - 1.2, y_d4))
label(ax, 6.7, y_d4 + 0.12, "No", ha="center", va="bottom", fs=7, c=C_DARK)

# G4 -> G5
arrow(ax, (cx, y_d4 - 0.55), (cx, y_g5 + 0.375))
label(ax, cx + 0.25, (y_d4 + y_g5)/2, "Yes", ha="left", va="center", fs=7, c=C_DARK)

# ------------------------------------------------------------------
# Gate 5: Conservative Default
# ------------------------------------------------------------------
sub = FancyBboxPatch((2.2, y_g5 - 0.65), 5.6, 1.30,
    boxstyle="round,pad=0.02,rounding_size=0.2",
    facecolor=C_GATE_FILL, edgecolor=C_GATE_STROKE,
    linewidth=1.0, alpha=0.15, linestyle="--", zorder=1)
ax.add_patch(sub)
label(ax, 2.4, y_g5 + 0.35, "Gate 5: Conservative Default", ha="left", va="center", fs=8, c=C_GATE_STROKE, fw="bold")

g5 = draw_rounded_box(ax, cx, y_g5, 3.4, 0.75,
    "Default:\nRisk Min / Status Quo", C_GATE_FILL, C_GATE_STROKE, fs=8, fw="bold")

r5 = draw_rounded_box(ax, x_right, y_g5, 2.4, 0.6, "Recommend Lower Risk / DH", C_TIE_FILL, C_TIE_STROKE, fs=8, fw="bold")
arrow(ax, (cx + 0.55*1.4 - 0.05, y_g5 + 0.05), (x_right - 1.2, y_g5))

# ------------------------------------------------------------------
# Final Output
# ------------------------------------------------------------------
end = draw_rounded_box(ax, cx, y_end, 3.2, 0.7,
    "Output: $\\Delta$ Decision", "#f8f9fa", C_DEC_STROKE, fs=9, fw="bold")

# G5 flows to R5, then R5 -> End (no direct G5->End arrow)
pass

# Collecting arrows from all side recommendations to End
rec_nodes = [
    (x_left, y_d1),   # R1A
    (x_right, y_d1),  # R1B
    (x_right, y_d2),  # R2
    (x_left, y_d2),   # Indiff
    (x_right, y_d3),  # R3
    (x_right, y_d4),  # R4
    (x_right, y_g5),  # R5
]

for rx, ry in rec_nodes:
    # Determine target point on End box
    if rx < cx:
        target_x = cx - 1.6
    else:
        target_x = cx + 1.6
    # Draw curved arrow
    ax.add_patch(mpatches.FancyArrowPatch(
        (rx, ry - 0.30),
        (target_x, y_end + 0.35),
        connectionstyle="arc3,rad=0.15",
        arrowstyle="-|>", mutation_scale=10,
        color=C_ARROW, linewidth=1.0, linestyle="solid", alpha=0.6, zorder=2))

# ------------------------------------------------------------------
# Title
# ------------------------------------------------------------------
fig.suptitle("Five-Gate Hierarchical Decision Flow", fontsize=14, fontweight="bold", y=0.98)

plt.tight_layout(rect=[0, 0.02, 1, 0.97])

fig.savefig("figures/fig_3_8_five_gate_decision.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_8_five_gate_decision.pdf", bbox_inches="tight")
print("Saved figures/fig_3_8_five_gate_decision.png")
print("Saved figures/fig_3_8_five_gate_decision.pdf")
