"""
Fig 3.11: Trunk-Spur Topology Synthesis
4-stage horizontal pipeline from OSM geodata to pandapipes network.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(13, 4.5))
ax.set_xlim(0, 13)
ax.set_ylim(0, 4.5)
ax.axis("off")

# ------------------------------------------------------------------
# Box configuration
# ------------------------------------------------------------------
boxes = [
    {
        "x": 1.8,
        "title": "(1) OSM Street Graph",
        "lines": [
            "Load GeoJSON streets",
            "Snap buildings to edges",
            "Build NetworkX graph",
        ],
        "color": "#E3F2FD",
    },
    {
        "x": 4.8,
        "title": "(2) Trunk Identification",
        "lines": [
            "Shortest path from plant",
            "MST over street segments",
            "Closed-loop backbone",
        ],
        "color": "#FFF3E0",
    },
    {
        "x": 7.8,
        "title": "(3) Spur Generation",
        "lines": [
            "Orthogonal projection",
            "Max length constraint",
            "Tee-on-main splitting",
        ],
        "color": "#E8F5E9",
    },
    {
        "x": 10.8,
        "title": "(4) Diameter Tapering",
        "lines": [
            "Cumulative heat load",
            "Pipe catalog lookup",
            "pandapipes instantiation",
        ],
        "color": "#FFEBEE",
    },
]

box_w = 2.4
box_h = 2.6
box_y = 1.0

# ------------------------------------------------------------------
# Draw boxes
# ------------------------------------------------------------------
for b in boxes:
    # Box
    rect = FancyBboxPatch(
        (b["x"] - box_w / 2, box_y),
        box_w, box_h,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        facecolor=b["color"],
        edgecolor="black",
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(rect)
    
    # Title
    ax.text(
        b["x"], box_y + box_h - 0.25,
        b["title"],
        ha="center", va="top",
        fontsize=11,
        fontweight="bold",
        color="black",
        zorder=3,
    )
    
    # Content lines
    content = "\n".join(b["lines"])
    ax.text(
        b["x"], box_y + 0.25,
        content,
        ha="center", va="bottom",
        fontsize=9,
        color="#222222",
        linespacing=1.25,
        zorder=3,
    )

# ------------------------------------------------------------------
# Draw arrows between boxes
# ------------------------------------------------------------------
for i in range(len(boxes) - 1):
    x1 = boxes[i]["x"] + box_w / 2
    x2 = boxes[i + 1]["x"] - box_w / 2
    y = box_y + box_h / 2
    
    arrow = FancyArrowPatch(
        (x1, y), (x2, y),
        arrowstyle="-|>",
        mutation_scale=16,
        color="black",
        linewidth=2,
        zorder=3,
    )
    ax.add_patch(arrow)

# ------------------------------------------------------------------
# Input / Output labels
# ------------------------------------------------------------------
# Input (left of first box)
ax.text(
    0.3, box_y + box_h / 2,
    "OSM\nGeoJSON",
    ha="center", va="center",
    fontsize=10,
    fontweight="bold",
    color="#1565C0",
    zorder=3,
)
arrow_in = FancyArrowPatch(
    (0.7, box_y + box_h / 2), (boxes[0]["x"] - box_w / 2, box_y + box_h / 2),
    arrowstyle="-|>",
    mutation_scale=14,
    color="#1565C0",
    linewidth=1.5,
    zorder=3,
)
ax.add_patch(arrow_in)

# Output (right of last box)
arrow_out = FancyArrowPatch(
    (boxes[-1]["x"] + box_w / 2, box_y + box_h / 2), (12.6, box_y + box_h / 2),
    arrowstyle="-|>",
    mutation_scale=14,
    color="#2E7D32",
    linewidth=1.5,
    zorder=3,
)
ax.add_patch(arrow_out)

ax.text(
    12.8, box_y + box_h / 2,
    "pandapipes\nNet",
    ha="left", va="center",
    fontsize=10,
    fontweight="bold",
    color="#2E7D32",
    zorder=3,
)

# ------------------------------------------------------------------
# Title
# ------------------------------------------------------------------
fig.suptitle(
    "Trunk-Spur Topology Synthesis",
    fontsize=16,
    fontweight="bold",
    y=0.98,
)

plt.tight_layout(rect=[0, 0.02, 1, 0.97])

# Save outputs
fig.savefig("figures/fig_3_11_trunk_spur_topology.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_11_trunk_spur_topology.pdf", bbox_inches="tight")
print("Saved figures/fig_3_11_trunk_spur_topology.png")
print("Saved figures/fig_3_11_trunk_spur_topology.pdf")
