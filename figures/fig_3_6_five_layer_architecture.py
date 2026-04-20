"""
Fig 3.6: 5-Layer Hierarchical Architecture
TikZ-style layered rectangle with a policy firewall between Domain Agents and ADK Wrappers.
Each layer is described in one concise sentence.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, PathPatch
from matplotlib.path import Path
import numpy as np

fig, ax = plt.subplots(figsize=(10, 11))
ax.set_xlim(0, 10)
ax.set_ylim(0, 11)
ax.axis("off")

# ------------------------------------------------------------------
# Layer geometry
# ------------------------------------------------------------------
layer_x = 1.0
layer_w = 8.0
layer_h = 1.5
gap = 0.35

# Colors (matching description)
colors = {
    "A": "#E1BEE7",  # light purple
    "B": "#BBDEFB",  # light blue
    "C": "#FFE0B2",  # light orange
    "D": "#FFCDD2",  # light red
    "E": "#C8E6C9",  # light green
}

# Y positions (top to bottom)
y_positions = {
    "A": 9.2,
    "B": 9.2 - (layer_h + gap),
    "C": 9.2 - 2 * (layer_h + gap),
    "D": 9.2 - 3 * (layer_h + gap),
    "E": 9.2 - 4 * (layer_h + gap),
}

# ------------------------------------------------------------------
# Helper to draw a layer band
# ------------------------------------------------------------------
def draw_layer(ax, y, label, title, description, color, fontsize_title=12, fontsize_desc=10):
    # Main band
    box = FancyBboxPatch(
        (layer_x, y), layer_w, layer_h,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=color,
        edgecolor="black",
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(box)
    
    # Layer label (horizontal, top-left corner of the band)
    ax.text(
        layer_x + 0.25, y + layer_h - 0.22,
        label,
        ha="left", va="top",
        fontsize=16,
        fontweight="bold",
        color="black",
        zorder=3,
    )
    
    # Title
    ax.text(
        layer_x + 1.05, y + layer_h - 0.22,
        title,
        ha="left", va="top",
        fontsize=fontsize_title,
        fontweight="bold",
        color="black",
        zorder=3,
    )
    
    # Description text (one sentence)
    ax.text(
        layer_x + 0.75, y + 0.25,
        description,
        ha="left", va="bottom",
        fontsize=fontsize_desc,
        color="#222222",
        linespacing=1.15,
        wrap=True,
        zorder=3,
    )
    return box

# ------------------------------------------------------------------
# Draw the 5 layers
# ------------------------------------------------------------------

# Layer A
draw_layer(
    ax, y_positions["A"], "A",
    "Orchestration & UI",
    "Coordinates user intent, conversation memory, and guardrails before\n"
    "dispatching requests to the execution engine.",
    colors["A"],
)

# Arrow A → B
draw_arrow = lambda s, e, c="black", lw=1.5: FancyArrowPatch(s, e, arrowstyle="-|>", mutation_scale=14, color=c, linewidth=lw, zorder=1)
ax.add_patch(draw_arrow((5.0, y_positions["A"]), (5.0, y_positions["B"] + layer_h)))

# Layer B
draw_layer(
    ax, y_positions["B"], "B",
    "Dynamic Executor",
    "Translates classified intents into ordered agent plans and integrates\n"
    "their outputs into a unified UI response.",
    colors["B"],
)

# Arrow B → C
ax.add_patch(draw_arrow((5.0, y_positions["B"]), (5.0, y_positions["C"] + layer_h)))

# Layer C
draw_layer(
    ax, y_positions["C"], "C",
    "Domain Agents",
    "Specialist agents that check file-based caches and delegate only\n"
    "missing simulations down to the ADK layer.",
    colors["C"],
)

# ------------------------------------------------------------------
# Firewall between C and D
# ------------------------------------------------------------------
firewall_y = (y_positions["C"] + y_positions["D"] + layer_h) / 2

# Shield body
shield_x = 5.0
shield_w = 1.4
shield_h = 0.85

shield_verts = [
    (shield_x - shield_w/2, firewall_y + shield_h/2 - 0.12),
    (shield_x + shield_w/2, firewall_y + shield_h/2 - 0.12),
    (shield_x + shield_w/2, firewall_y - 0.08),
    (shield_x, firewall_y - shield_h/2),
    (shield_x - shield_w/2, firewall_y - 0.08),
    (shield_x - shield_w/2, firewall_y + shield_h/2 - 0.12),
]
codes = [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY]
shield = PathPatch(Path(shield_verts, codes), facecolor="#FFEBEE", edgecolor="#C62828", linewidth=2.5, zorder=4)
ax.add_patch(shield)

# Lock body
lock_w = 0.32
lock_h = 0.20
lock = FancyBboxPatch(
    (shield_x - lock_w/2, firewall_y - lock_h/2 + 0.04),
    lock_w, lock_h,
    boxstyle="round,pad=0.01,rounding_size=0.05",
    facecolor="#C62828",
    edgecolor="white",
    linewidth=1.0,
    zorder=5,
)
ax.add_patch(lock)

# Lock shackle
shackle_theta = np.linspace(0, np.pi, 20)
shackle_r = 0.11
ax.plot(
    shield_x + shackle_r * np.cos(shackle_theta),
    firewall_y + 0.04 + shackle_r * np.sin(shackle_theta),
    color="white", linewidth=2.5, zorder=5,
)

# Firewall label
ax.text(
    shield_x + 0.9, firewall_y,
    "Policy Firewall\nLLM cannot bypass",
    ha="left", va="center",
    fontsize=10,
    fontweight="bold",
    color="#C62828",
    linespacing=1.1,
    zorder=5,
)

# Small arrow through firewall (C → D)
ax.add_patch(draw_arrow((5.0, y_positions["C"]), (5.0, y_positions["D"] + layer_h), c="#C62828", lw=2))

# ------------------------------------------------------------------
# Layer D
draw_layer(
    ax, y_positions["D"], "D",
    "ADK Wrappers",
    "Policy-enforced tool wrappers that audit every action and invoke\n"
    "physics engines as guarded subprocesses.",
    colors["D"],
)

# Arrow D → E
ax.add_patch(draw_arrow((5.0, y_positions["D"]), (5.0, y_positions["E"] + layer_h)))

# Layer E
draw_layer(
    ax, y_positions["E"], "E",
    "Physics & Decision Engines",
    "Deterministic simulation engines for district heating, LV grids,\n"
    "economics, and rule-based recommendation logic.",
    colors["E"],
)

# ------------------------------------------------------------------
# Upward result arrow (dashed, right side)
# ------------------------------------------------------------------
result_x = 9.3
for src_y, dst_y in [
    (y_positions["E"] + layer_h/2, y_positions["D"] + layer_h/2),
    (y_positions["D"] + layer_h/2, y_positions["C"] + layer_h/2),
    (y_positions["C"] + layer_h/2, y_positions["B"] + layer_h/2),
    (y_positions["B"] + layer_h/2, y_positions["A"] + layer_h/2),
]:
    ax.annotate(
        "",
        xy=(result_x, dst_y),
        xytext=(result_x, src_y),
        arrowprops=dict(arrowstyle="-|>", color="#555555", lw=1.5, linestyle="--"),
    )

ax.text(
    result_x + 0.15, (y_positions["A"] + y_positions["E"] + layer_h) / 2,
    "Result\nflow",
    ha="left", va="center",
    fontsize=9,
    color="#555555",
    style="italic",
    rotation=90,
)

# ------------------------------------------------------------------
# Title & caption
# ------------------------------------------------------------------
fig.suptitle(
    "5-Layer Hierarchical Architecture",
    fontsize=16,
    fontweight="bold",
    y=0.98,
)

fig.text(
    0.5,
    0.02,
    "Strict top-down delegation from UI to physics engines. The Policy Firewall between Domain Agents and ADK Wrappers "
    "enforces the invariant that no LLM-based component can bypass or override deterministic simulation results.",
    ha="center",
    fontsize=9,
    style="italic",
)

plt.tight_layout(rect=[0, 0.03, 1, 0.97])

# Save outputs
fig.savefig("figures/fig_3_6_five_layer_architecture.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_6_five_layer_architecture.pdf", bbox_inches="tight")
print("Saved figures/fig_3_6_five_layer_architecture.png")
print("Saved figures/fig_3_6_five_layer_architecture.pdf")
