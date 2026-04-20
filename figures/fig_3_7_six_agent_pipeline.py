"""
Fig 3.7: 6-Agent Pipeline Sequence
A TikZ-style sequence diagram showing the Perceive→Recognize→Plan→Act cycle
with 6 vertical swimlanes and numbered arrows. No timing annotations.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(0, 10.3)
ax.axis("off")

# ------------------------------------------------------------------
# Swimlane configuration
# ------------------------------------------------------------------
swimlanes = [
    ("NLU\nIntent\nClassifier", "#E3F2FD"),
    ("Conversation\nManager", "#FFF3E0"),
    ("Street\nResolver", "#E8F5E9"),
    ("Capability\nGuardrail", "#FFEBEE"),
    ("Execution\nPlanner", "#FFF9C4"),
    ("Dynamic\nExecutor", "#E1BEE7"),
]

n_lanes = len(swimlanes)
lane_x = [1.5 + i * 2.1 for i in range(n_lanes)]
lane_top = 9.0
lane_bottom = 1.0

# ------------------------------------------------------------------
# Draw swimlane headers and lifelines
# ------------------------------------------------------------------
for i, (name, color) in enumerate(swimlanes):
    x = lane_x[i]
    
    # Header box
    header = FancyBboxPatch(
        (x - 0.9, lane_top), 1.8, 0.8,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=color,
        edgecolor="black",
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(header)
    ax.text(
        x, lane_top + 0.4, name,
        ha="center", va="center",
        fontsize=11,
        fontweight="bold",
        color="black",
        linespacing=1.0,
        zorder=3,
    )
    
    # Lifeline (dashed)
    ax.plot([x, x], [lane_top, lane_bottom], color="#888888", linewidth=1.0, linestyle="--", zorder=1)
    
    # Bottom marker
    ax.plot(x, lane_bottom, marker="s", markersize=8, color="black", zorder=2)

# ------------------------------------------------------------------
# Helper for sequence arrows
# ------------------------------------------------------------------
def seq_arrow(ax, x1, x2, y, color="black", lw=1.5, label="", label_offset=(0, 0.25), number=None):
    style = "-|>" if x2 > x1 else "<|-"
    arrow = FancyArrowPatch(
        (x1, y), (x2, y),
        arrowstyle=style,
        mutation_scale=14,
        color=color,
        linewidth=lw,
        zorder=3,
    )
    ax.add_patch(arrow)
    
    # Label above arrow
    mid_x = (x1 + x2) / 2 + label_offset[0]
    mid_y = y + label_offset[1]
    ax.text(
        mid_x, mid_y, label,
        ha="center", va="bottom",
        fontsize=10,
        color="black",
        zorder=4,
    )
    
    # Numbered circle
    if number is not None:
        num_x = mid_x
        num_y = y + 0.08
        circle = Circle((num_x, num_y), 0.20, facecolor="white", edgecolor="black", linewidth=1.0, zorder=5)
        ax.add_patch(circle)
        ax.text(
            num_x, num_y, str(number),
            ha="center", va="center",
            fontsize=10,
            fontweight="bold",
            color="black",
            zorder=6,
        )


def self_arrow(ax, x, y, label, color="black", number=None):
    # Small curved arrow on the lifeline
    arc = mpatches.FancyArrowPatch(
        (x + 0.15, y + 0.3),
        (x + 0.15, y - 0.3),
        connectionstyle="arc3,rad=0.3",
        arrowstyle="-|>",
        mutation_scale=12,
        color=color,
        linewidth=1.2,
        zorder=3,
    )
    ax.add_patch(arc)
    ax.text(
        x + 0.55, y, label,
        ha="left", va="center",
        fontsize=10,
        color="black",
        zorder=4,
    )
    if number is not None:
        circle = Circle((x + 0.35, y), 0.18, facecolor="white", edgecolor="black", linewidth=1.0, zorder=5)
        ax.add_patch(circle)
        ax.text(
            x + 0.35, y, str(number),
            ha="center", va="center",
            fontsize=10,
            fontweight="bold",
            color="black",
            zorder=6,
        )


def return_arrow(ax, x1, x2, y, color="#555555", label=""):
    style = "-|>" if x2 > x1 else "<|-"
    arrow = FancyArrowPatch(
        (x1, y), (x2, y),
        arrowstyle=style,
        mutation_scale=12,
        color=color,
        linewidth=1.2,
        linestyle="--",
        zorder=3,
    )
    ax.add_patch(arrow)
    if label:
        mid_x = (x1 + x2) / 2
        ax.text(
            mid_x, y - 0.15, label,
            ha="center", va="top",
            fontsize=9,
            color="#555555",
            style="italic",
            zorder=4,
        )

# ------------------------------------------------------------------
# Sequence steps (top to bottom)
# ------------------------------------------------------------------

y_level = 8.3

# 1. NLU classifies intent
seq_arrow(ax, lane_x[0], lane_x[1], y_level, label="intent, entities, confidence", number=1)

y_level -= 0.85

# 2. Conversation Manager resolves follow-ups
seq_arrow(ax, lane_x[1], lane_x[2], y_level, label="memory_street, is_follow_up", number=2)

y_level -= 0.85

# 3. Street Resolver maps to cluster_id
self_arrow(ax, lane_x[2], y_level, label="fuzzy match → cluster_id", number=3)

y_level -= 0.85

# Return to guardrail
return_arrow(ax, lane_x[2], lane_x[3], y_level, label="resolved_cluster_id")

y_level -= 0.85

# 4. Guardrail validates capability
self_arrow(ax, lane_x[3], y_level, label="can_handle = True / False", number=4)

y_level -= 0.85

# Return to planner (or block)
return_arrow(ax, lane_x[3], lane_x[4], y_level, label="capability status")

y_level -= 0.85

# 5. Execution Planner creates plan
self_arrow(ax, lane_x[4], y_level, label='agent_plan = ["cha", "dha", ...]', number=5)

y_level -= 0.85

# Planner → Executor
seq_arrow(ax, lane_x[4], lane_x[5], y_level, label="agent_plan + context", number=6)

y_level -= 0.85

# 6. Executor runs agents (self-loop)
self_arrow(ax, lane_x[5], y_level, label="lazy execution\ncache-first", number=6)

y_level -= 0.85

# Return result back up through all lanes
return_arrow(ax, lane_x[5], lane_x[0], y_level, label="response dict")

# ------------------------------------------------------------------
# Perceive→Recognize→Plan→Act annotation (left side)
# ------------------------------------------------------------------
phases = [
    (8.3, "PERCEIVE", "#E3F2FD"),
    (6.6, "RECOGNIZE", "#FFF3E0"),
    (5.0, "PLAN", "#FFF9C4"),
    (3.3, "ACT", "#E1BEE7"),
]

for y, phase, color in phases:
    ax.text(
        0.4, y, phase,
        ha="left", va="center",
        fontsize=12,
        fontweight="bold",
        color="black",
        rotation=90,
        zorder=4,
    )
    # Bracket line
    ax.plot([0.7, 0.7], [y - 0.9, y + 0.9], color="black", linewidth=1.5, zorder=3)
    ax.plot([0.7, 0.9], [y - 0.9, y - 0.9], color="black", linewidth=1.5, zorder=3)
    ax.plot([0.7, 0.9], [y + 0.9, y + 0.9], color="black", linewidth=1.5, zorder=3)

# ------------------------------------------------------------------
# Title & caption
# ------------------------------------------------------------------
fig.suptitle(
    "6-Agent Pipeline Sequence",
    fontsize=18,
    fontweight="bold",
    y=0.99,
)

plt.tight_layout(rect=[0, 0.00, 1, 0.98])

# Save outputs
fig.savefig("figures/fig_3_7_six_agent_pipeline.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_7_six_agent_pipeline.pdf", bbox_inches="tight")
print("Saved figures/fig_3_7_six_agent_pipeline.png")
print("Saved figures/fig_3_7_six_agent_pipeline.pdf")
