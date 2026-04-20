"""
Fig 3.9: KPI Contract as Information Boundary
Clean matplotlib rendering matching the TikZ specification.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Ellipse, Circle
import numpy as np

fig, ax = plt.subplots(figsize=(11, 7.5))
ax.set_xlim(0, 11)
ax.set_ylim(0, 7.5)
ax.axis("off")

# ------------------------------------------------------------------
# Colors
# ------------------------------------------------------------------
C_DOMAIN = "#2E86AB"
C_LLM = "#A23B72"
C_GOLD = "#DAA520"
C_GREEN = "#4CAF50"
C_RED = "#DC3545"
C_DARK = "#404040"

# ------------------------------------------------------------------
# Domain Agents (Left)
# ------------------------------------------------------------------
agent_x = 1.9
agent_w = 2.1
agent_h = 0.85
agent_ys = [5.4, 4.3, 3.2]
agent_texts = [
    ("CHA Agent\n(pandapipes)", "Thermo-hydraulic"),
    ("DHA Agent\n(pandapower)", "LV Grid Analysis"),
    ("Econ Agent\n(Monte Carlo)", "LCOH / CO₂"),
]

for y, (main, sub) in zip(agent_ys, agent_texts):
    box = FancyBboxPatch(
        (agent_x - agent_w/2, y - agent_h/2), agent_w, agent_h,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        facecolor=C_DOMAIN, edgecolor=C_DARK, linewidth=1.0,
        alpha=0.18, zorder=2,
    )
    ax.add_patch(box)
    ax.text(agent_x, y + 0.12, main, ha="center", va="center",
            fontsize=9, fontweight="bold", color=C_DARK, linespacing=0.9, zorder=3)
    ax.text(agent_x, y - 0.28, sub, ha="center", va="center",
            fontsize=7, color=C_DARK, style="italic", zorder=3)

# Dashed bounding box
bbox_y = (agent_ys[0] + agent_ys[-1]) / 2
bbox_h = agent_ys[0] - agent_ys[-1] + agent_h + 0.6
bbox = FancyBboxPatch(
    (agent_x - agent_w/2 - 0.2, bbox_y - bbox_h/2), agent_w + 0.4, bbox_h,
    boxstyle="round,pad=0.02,rounding_size=0.15",
    facecolor=C_DOMAIN, edgecolor=C_DARK, linewidth=1.0,
    alpha=0.06, linestyle="--", zorder=1,
)
ax.add_patch(bbox)
ax.text(agent_x, agent_ys[0] + agent_h/2 + 0.40,
        "Domain Agents (Layer C)", ha="center", va="bottom",
        fontsize=10, fontweight="bold", color=C_DARK, zorder=3)

# ------------------------------------------------------------------
# KPI Contract Cylinder (Center)
# ------------------------------------------------------------------
cx, cy = 5.5, 4.3
cw, ch = 2.4, 3.0

top = Ellipse((cx, cy + ch/2), cw, 0.5, facecolor="#F5E6C8", edgecolor=C_GOLD, linewidth=2.0, zorder=2)
ax.add_patch(top)
body = FancyBboxPatch((cx - cw/2, cy - ch/2), cw, ch,
    boxstyle="square,pad=0", facecolor="#EAD595", edgecolor=C_GOLD, linewidth=2.0, zorder=1)
ax.add_patch(body)
bottom = Ellipse((cx, cy - ch/2), cw, 0.5, facecolor="#D4B86A", edgecolor=C_GOLD, linewidth=2.0, zorder=3)
ax.add_patch(bottom)

ax.text(cx, cy + 0.55, "KPI Contract", ha="center", va="center",
        fontsize=12, fontweight="bold", color=C_DARK, zorder=4)
ax.text(cx, cy + 0.10, r"$\mathcal{K} = \{\mathcal{M}, \delta, \mathcal{R}, \tau\}$",
        ha="center", va="center", fontsize=10, color=C_DARK, zorder=4)
ax.text(cx, cy - 0.45, r"$k_{lcoh}, k_{co2},$" + "\n" + r"$k_{feas}, k_{phys},$" + "\n" + r"$k_{robust}$",
        ha="center", va="center", fontsize=8, color=C_DARK, linespacing=1.05, zorder=4)

# ------------------------------------------------------------------
# UHDC / LLM / Explanation (Right)
# ------------------------------------------------------------------
ux, uw = 9.1, 2.1

# UHDC
uy = 4.3
uh = 1.0
box = FancyBboxPatch((ux - uw/2, uy - uh/2), uw, uh,
    boxstyle="round,pad=0.02,rounding_size=0.15",
    facecolor=C_LLM, edgecolor=C_LLM, linewidth=1.2, alpha=0.15, zorder=2)
ax.add_patch(box)
ax.text(ux, uy + 0.12, "UHDC Agent\n(Layer A)", ha="center", va="center",
        fontsize=9, fontweight="bold", color=C_DARK, linespacing=0.9, zorder=3)
ax.text(ux, uy - 0.28, "Urban Heat Decision\nCoordinator", ha="center", va="center",
        fontsize=7, color=C_DARK, style="italic", linespacing=0.9, zorder=3)

# LLM
ly = uy + 1.6
lh = 0.75
box = FancyBboxPatch((ux - uw/2, ly - lh/2), uw, lh,
    boxstyle="round,pad=0.02,rounding_size=0.12",
    facecolor=C_LLM, edgecolor=C_LLM, linewidth=1.2, alpha=0.28, zorder=2)
ax.add_patch(box)
ax.text(ux, ly + 0.05, "LLM\n(Gemini)", ha="center", va="center",
        fontsize=9, fontweight="bold", color=C_DARK, linespacing=0.85, zorder=3)
ax.text(ux, ly - 0.30, r"$T=0.0$ deterministic", ha="center", va="center",
        fontsize=7, color=C_DARK, zorder=3)

# Explanation
ey = uy - 1.6
eh = 0.75
box = FancyBboxPatch((ux - uw/2, ey - eh/2), uw, eh,
    boxstyle="round,pad=0.02,rounding_size=0.12",
    facecolor=C_GREEN, edgecolor=C_GREEN, linewidth=1.2, alpha=0.18, zorder=2)
ax.add_patch(box)
ax.text(ux, ey + 0.05, "Explanation", ha="center", va="center",
        fontsize=9, fontweight="bold", color=C_DARK, zorder=3)
ax.text(ux, ey - 0.25, "validated output\nfor stakeholders", ha="center", va="center",
        fontsize=7, color=C_DARK, style="italic", linespacing=0.9, zorder=3)

# ------------------------------------------------------------------
# Valid arrows
# ------------------------------------------------------------------
def arrow(ax, s, e, c, lw=1.5, ls="solid"):
    ax.add_patch(FancyArrowPatch(s, e, arrowstyle="-|>", mutation_scale=12,
                                 color=c, linewidth=lw, linestyle=ls, zorder=3))

# Domain -> KPI (writes)
for y in agent_ys:
    arrow(ax, (agent_x + agent_w/2, y), (cx - cw/2 - 0.02, y), C_DOMAIN, lw=2.0)
ax.text((agent_x + agent_w/2 + cx - cw/2)/2, 5.65, "writes",
        ha="center", va="bottom", fontsize=8, fontweight="bold", color=C_DOMAIN, zorder=4)

# KPI -> UHDC (read-only)
arrow(ax, (cx + cw/2 + 0.02, cy + 0.15), (ux - uw/2, uy), C_LLM, lw=2.0, ls="--")
ax.text((cx + cw/2 + ux - uw/2)/2 + 0.1, cy + 0.72, "read-only",
        ha="center", va="bottom", fontsize=8, fontweight="bold", color=C_LLM, zorder=4)

# UHDC -> LLM
arrow(ax, (ux, uy + uh/2), (ux, ly - lh/2), C_LLM, lw=1.5)

# UHDC -> Explanation
arrow(ax, (ux, uy - uh/2), (ux, ey + eh/2), C_GREEN, lw=2.0)

# ------------------------------------------------------------------
# Forbidden arrows (curved around the cylinder)
# ------------------------------------------------------------------

# 1) LLM -> CHA Agent (curved arc going OVER the cylinder)
arc1 = mpatches.FancyArrowPatch(
    (ux - uw/2, ly - lh/2 + 0.1),
    (agent_x + agent_w/2 + 0.05, agent_ys[0] + agent_h/2 - 0.1),
    connectionstyle="arc3,rad=0.35",
    arrowstyle="-|>",
    mutation_scale=12,
    color=C_RED,
    linewidth=1.5,
    linestyle="--",
    alpha=0.8,
    zorder=5,
)
ax.add_patch(arc1)

# X mark above cylinder
x1 = (cx + ux)/2 - 0.3
y1 = cy + ch/2 + 0.9
cs = 0.20
ax.plot([x1-cs, x1+cs], [y1-cs, y1+cs], color=C_RED, lw=3.5, zorder=6)
ax.plot([x1-cs, x1+cs], [y1+cs, y1-cs], color=C_RED, lw=3.5, zorder=6)
ax.text(x1 + 0.45, y1, "FORBIDDEN",
        ha="left", va="center", fontsize=9, fontweight="bold", color=C_RED,
        bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor=C_RED, alpha=0.95), zorder=6)

# 2) LLM -> Domain layer (curved arc going UNDER the cylinder)
arc2 = mpatches.FancyArrowPatch(
    (ux - uw/2, ly),
    (agent_x + agent_w/2 + 0.2, agent_ys[-1]),
    connectionstyle="arc3,rad=-0.48",
    arrowstyle="-|>",
    mutation_scale=12,
    color=C_RED,
    linewidth=1.5,
    linestyle="--",
    alpha=0.8,
    zorder=5,
)
ax.add_patch(arc2)

# X mark below cylinder
x2 = (cx + ux)/2 - 0.3
y2 = cy - ch/2 - 0.8
ax.plot([x2-cs, x2+cs], [y2-cs, y2+cs], color=C_RED, lw=3.5, zorder=6)
ax.plot([x2-cs, x2+cs], [y2+cs, y2-cs], color=C_RED, lw=3.5, zorder=6)
ax.text(x2 + 0.45, y2, "BLOCKED",
        ha="left", va="center", fontsize=9, fontweight="bold", color=C_RED,
        bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor=C_RED, alpha=0.95), zorder=6)

# ------------------------------------------------------------------
# Annotations & badges
# ------------------------------------------------------------------
ax.text(agent_x, agent_ys[-1] - agent_h/2 - 0.45,
        "Deterministic Simulation\n(Layers C–E)",
        ha="center", va="top", fontsize=8, color=C_DARK, style="italic", linespacing=1.05, zorder=3)

ax.text(cx, cy - ch/2 - 0.42,
        "Immutable\nInformation Boundary",
        ha="center", va="top", fontsize=8, color=C_GOLD, fontweight="bold",
        style="italic", linespacing=1.05, zorder=3)

ax.text(ux, ey - eh/2 - 0.42,
        "AI Explanation\n(Layer A)",
        ha="center", va="top", fontsize=8, color=C_LLM, style="italic", linespacing=1.05, zorder=3)

# Schema-Validated badge (cleanly to the right of cylinder)
badge = FancyBboxPatch((cx + cw/2 + 0.3, cy + 0.15), 1.5, 0.40,
    boxstyle="round,pad=0.02,rounding_size=0.08",
    facecolor=C_GREEN, edgecolor=C_GREEN, linewidth=1.0, alpha=0.12, zorder=4)
ax.add_patch(badge)
ax.text(cx + cw/2 + 1.05, cy + 0.35, "Schema-Validated",
        ha="center", va="center", fontsize=8, fontweight="bold", color=C_GREEN, zorder=5)

# Safety label (below blocked arc)
ax.text(x2, y2 - 0.55, "LLM cannot access\nraw simulation data",
        ha="center", va="top", fontsize=8, fontweight="bold", color=C_RED,
        bbox=dict(boxstyle="round,pad=0.15", facecolor=C_RED, edgecolor=C_RED, alpha=0.10), zorder=6)

# ------------------------------------------------------------------
# Title & quote
# ------------------------------------------------------------------
fig.suptitle(r"KPI Contract $\mathcal{K}$ as Information Boundary",
             fontsize=15, fontweight="bold", y=0.98)

fig.text(0.5, 0.02, r"``The LLM is a narrator, not a decider''",
         ha="center", fontsize=10, style="italic")

plt.tight_layout(rect=[0, 0.03, 1, 0.97])

fig.savefig("figures/fig_3_9_kpi_contract_boundary.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_9_kpi_contract_boundary.pdf", bbox_inches="tight")
print("Saved figures/fig_3_9_kpi_contract_boundary.png")
print("Saved figures/fig_3_9_kpi_contract_boundary.pdf")
