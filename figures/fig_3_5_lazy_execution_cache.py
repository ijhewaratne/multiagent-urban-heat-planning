"""
Fig 3.5: Lazy Execution & Cache Invalidation Workflow
Renders the actual repository implementation as a clean top-down flowchart.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon, FancyArrowPatch

fig, ax = plt.subplots(figsize=(11, 14))
ax.set_xlim(0, 11)
ax.set_ylim(0, 14)
ax.axis("off")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def draw_box(ax, cx, cy, w, h, text, facecolor, fontsize=9, text_color="black", fontweight="bold"):
    box = FancyBboxPatch(
        (cx - w / 2, cy - h / 2),
        w, h,
        boxstyle="round,pad=0.01,rounding_size=0.15",
        facecolor=facecolor,
        edgecolor="black",
        linewidth=1.2,
        zorder=2,
    )
    ax.add_patch(box)
    ax.text(
        cx, cy, text,
        ha="center", va="center",
        fontsize=fontsize,
        color=text_color,
        fontweight=fontweight,
        linespacing=1.05,
        zorder=3,
    )
    return box


def draw_diamond(ax, cx, cy, size, text, facecolor, fontsize=9):
    diamond = Polygon(
        [(cx, cy + size), (cx + size * 1.25, cy), (cx, cy - size), (cx - size * 1.25, cy)],
        facecolor=facecolor,
        edgecolor="black",
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(diamond)
    ax.text(
        cx, cy, text,
        ha="center", va="center",
        fontsize=fontsize,
        color="black",
        fontweight="bold",
        linespacing=1.0,
        zorder=3,
    )
    return diamond


def draw_start_end(ax, cx, cy, w, h, text, facecolor, fontsize=10):
    box = FancyBboxPatch(
        (cx - w / 2, cy - h / 2),
        w, h,
        boxstyle="round,pad=0.01,rounding_size=0.4",
        facecolor=facecolor,
        edgecolor="black",
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(box)
    ax.text(
        cx, cy, text,
        ha="center", va="center",
        fontsize=fontsize,
        color="black",
        fontweight="bold",
        zorder=3,
    )
    return box


def draw_arrow(ax, start, end, color="black", lw=1.2, style="-|>"):
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle=style,
        mutation_scale=12,
        color=color,
        linewidth=lw,
        zorder=1,
    )
    ax.add_patch(arrow)


# ------------------------------------------------------------------
# Color palette (matching mermaid class styles)
# ------------------------------------------------------------------
C_EXECUTOR = "#E3F2FD"   # blue
C_AGENT = "#FFF3E0"      # orange
C_CACHE = "#E8F5E9"      # green
C_COMPUTE = "#FFEBEE"    # red
C_ADK = "#F3E5F5"        # purple
C_DECISION = "#FFF9C4"   # yellow
C_OUTPUT = "#ECEFF1"     # grey
C_START = "#D1C4E9"      # deep purple

# ------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------
CX = 5.5

# Y positions (top to bottom)
Y_START = 13.2
Y_EXECUTOR = 12.0
Y_PLAN = 10.8
Y_LOOP = 9.7
Y_KEY = 8.6
Y_CHECK = 7.4

# Branch Y positions
Y_HIT = 5.9
Y_RESULT_HIT = 4.8

Y_MISS_ADK = 5.9
Y_MISS_POLICY = 5.0
Y_MISS_TOOL = 4.1
Y_MISS_ENGINE = 3.2
Y_MISS_WRITE = 2.3
Y_RESULT_MISS = 1.4

Y_INTEGRATE = 5.9
Y_MORE = 4.6
Y_FORMAT = 3.3
Y_END = 2.0

# X positions
X_HIT = 1.8
X_MISS = 9.2
X_INVAL = 9.8

# ------------------------------------------------------------------
# 1. Entry
# ------------------------------------------------------------------
draw_start_end(ax, CX, Y_START, 2.4, 0.6, "User Query", C_START, fontsize=11)
draw_arrow(ax, (CX, Y_START - 0.3), (CX, Y_EXECUTOR + 0.35))

# ------------------------------------------------------------------
# 2. Executor
# ------------------------------------------------------------------
draw_box(ax, CX, Y_EXECUTOR, 3.6, 0.7, "DynamicExecutor\nexecute()", C_EXECUTOR, fontsize=11)
draw_arrow(ax, (CX, Y_EXECUTOR - 0.35), (CX, Y_PLAN + 0.35))

# ------------------------------------------------------------------
# 3. Plan
# ------------------------------------------------------------------
draw_box(ax, CX, Y_PLAN, 3.6, 0.7, "_create_agent_plan()\nintent → ordered agent list", C_EXECUTOR, fontsize=10)
draw_arrow(ax, (CX, Y_PLAN - 0.35), (CX, Y_LOOP + 0.55))

# ------------------------------------------------------------------
# 4. Loop diamond
# ------------------------------------------------------------------
draw_diamond(ax, CX, Y_LOOP, 0.55, "For each\nagent key", C_DECISION, fontsize=10)
draw_arrow(ax, (CX, Y_LOOP - 0.55), (CX, Y_KEY + 0.35))

# ------------------------------------------------------------------
# 5. Cache key
# ------------------------------------------------------------------
draw_box(ax, CX, Y_KEY, 3.0, 0.6, "_compute_cache_key()\nSHA-256(context)", C_AGENT, fontsize=10)
draw_arrow(ax, (CX, Y_KEY - 0.3), (CX, Y_CHECK + 0.55))

# ------------------------------------------------------------------
# 6. Cache check diamond
# ------------------------------------------------------------------
draw_diamond(ax, CX, Y_CHECK, 0.65, "_check_*_cache\nk ∈ Domain(Cache)?", C_DECISION, fontsize=10)

# YES branch (left)
draw_arrow(ax, (CX - 0.82, Y_CHECK), (X_HIT + 1.1, Y_CHECK), color="#2E7D32", lw=2.5)
ax.text(
    CX - 0.3, Y_CHECK + 0.4,
    "YES",
    ha="center", va="bottom",
    fontsize=10, fontweight="bold", color="#2E7D32",
)

# NO branch (right)
draw_arrow(ax, (CX + 0.82, Y_CHECK), (X_MISS - 1.1, Y_CHECK), color="#C62828", lw=2.5)
ax.text(
    CX + 0.3, Y_CHECK + 0.4,
    "NO",
    ha="center", va="bottom",
    fontsize=10, fontweight="bold", color="#C62828",
)

# ------------------------------------------------------------------
# 7. Hit branch (left)
# ------------------------------------------------------------------
draw_box(ax, X_HIT, Y_HIT, 2.4, 0.6, "Cache Hit\nLoad JSON / pickle", C_CACHE, fontsize=10)
draw_arrow(ax, (X_HIT, Y_HIT - 0.3), (X_HIT, Y_RESULT_HIT + 0.3), color="#2E7D32", lw=1.5)

draw_box(ax, X_HIT, Y_RESULT_HIT, 2.4, 0.6, "AgentResult\ncache_hit = True", C_CACHE, fontsize=9)
ax.text(
    X_HIT, Y_RESULT_HIT - 0.5,
    "~0.002 s",
    ha="center", va="top",
    fontsize=8, color="#2E7D32", style="italic",
)

# Arrow from hit to integrate
draw_arrow(ax, (X_HIT + 1.2, Y_RESULT_HIT), (CX - 1.8, Y_RESULT_HIT), color="#2E7D32", lw=1.5)
draw_arrow(ax, (CX - 1.8, Y_RESULT_HIT), (CX - 1.8, Y_INTEGRATE), color="#2E7D32", lw=1.5)

# ------------------------------------------------------------------
# 8. Miss branch (right, vertical stack)
# ------------------------------------------------------------------
draw_box(ax, X_MISS, Y_MISS_ADK, 2.4, 0.6, "Delegate to\nADK Agent", C_COMPUTE, fontsize=10)
draw_arrow(ax, (X_MISS, Y_MISS_ADK - 0.3), (X_MISS, Y_MISS_POLICY + 0.3), color="#C62828", lw=1.5)

draw_box(ax, X_MISS, Y_MISS_POLICY, 2.4, 0.6, "Policy Enforcement\nadk/policies.py", C_COMPUTE, fontsize=9)
draw_arrow(ax, (X_MISS, Y_MISS_POLICY - 0.3), (X_MISS, Y_MISS_TOOL + 0.3), color="#C62828", lw=1.5)

draw_box(ax, X_MISS, Y_MISS_TOOL, 2.4, 0.6, "Tool Layer\nadk/tools.py", C_COMPUTE, fontsize=9)
draw_arrow(ax, (X_MISS, Y_MISS_TOOL - 0.3), (X_MISS, Y_MISS_ENGINE + 0.3), color="#C62828", lw=1.5)

draw_box(ax, X_MISS, Y_MISS_ENGINE, 2.4, 0.6, "Physics Engine\npandapipes / pandapower", C_COMPUTE, fontsize=9)
ax.text(
    X_MISS, Y_MISS_ENGINE - 0.5,
    "~12–120 s",
    ha="center", va="top",
    fontsize=8, color="#C62828", style="italic",
)
draw_arrow(ax, (X_MISS, Y_MISS_ENGINE - 0.3), (X_MISS, Y_MISS_WRITE + 0.3), color="#C62828", lw=1.5)

draw_box(ax, X_MISS, Y_MISS_WRITE, 2.4, 0.6, "Write Cache\n_cache_manifest.json", C_COMPUTE, fontsize=9)
draw_arrow(ax, (X_MISS, Y_MISS_WRITE - 0.3), (X_MISS, Y_RESULT_MISS + 0.3), color="#C62828", lw=1.5)

draw_box(ax, X_MISS, Y_RESULT_MISS, 2.4, 0.6, "AgentResult\ncache_hit = False", C_COMPUTE, fontsize=9)

# Arrow from miss to integrate
draw_arrow(ax, (X_MISS - 1.2, Y_RESULT_MISS), (CX + 1.8, Y_RESULT_MISS), color="#C62828", lw=1.5)
draw_arrow(ax, (CX + 1.8, Y_RESULT_MISS), (CX + 1.8, Y_INTEGRATE), color="#C62828", lw=1.5)

# ------------------------------------------------------------------
# 9. Integrate Results
# ------------------------------------------------------------------
# Merge bar
ax.plot([CX - 1.8, CX + 1.8], [Y_INTEGRATE, Y_INTEGRATE], color="black", linewidth=2, zorder=1)
draw_arrow(ax, (CX, Y_INTEGRATE), (CX, Y_INTEGRATE + 0.35), color="black", lw=2)

draw_box(ax, CX, Y_INTEGRATE, 3.0, 0.7, "_integrate_results()\nFlatten to UI schema", C_OUTPUT, fontsize=11)
draw_arrow(ax, (CX, Y_INTEGRATE - 0.35), (CX, Y_MORE + 0.45))

# ------------------------------------------------------------------
# 10. More agents? diamond
# ------------------------------------------------------------------
draw_diamond(ax, CX, Y_MORE, 0.5, "More\nagents?", C_DECISION, fontsize=10)

# Loop back (curved left)
curved = mpatches.FancyArrowPatch(
    (CX - 1.55, Y_MORE),
    (CX - 1.55, Y_LOOP + 0.55),
    connectionstyle="arc3,rad=0.30",
    arrowstyle="-|>",
    mutation_scale=12,
    color="#555555",
    linewidth=1.5,
    linestyle="--",
    zorder=1,
)
ax.add_patch(curved)
ax.text(
    0.6, 7.2,
    "YES\n(next k)",
    ha="center", va="center",
    fontsize=9, color="#555555",
)

# Continue down
draw_arrow(ax, (CX, Y_MORE - 0.45), (CX, Y_FORMAT + 0.35))

# ------------------------------------------------------------------
# 11. Format response
# ------------------------------------------------------------------
draw_box(ax, CX, Y_FORMAT, 3.4, 0.7, "_format_executor_response()\nanswer + trace + viz metadata", C_OUTPUT, fontsize=10)
draw_arrow(ax, (CX, Y_FORMAT - 0.35), (CX, Y_END + 0.3))

# ------------------------------------------------------------------
# 12. End
# ------------------------------------------------------------------
draw_start_end(ax, CX, Y_END, 2.4, 0.6, "UI Response", C_START, fontsize=11)

# ------------------------------------------------------------------
# 13. Cache Invalidation (side branch, dashed)
# ------------------------------------------------------------------
draw_start_end(ax, X_INVAL, 11.4, 2.0, 0.6, "Input Change", C_ADK, fontsize=10)
draw_arrow(ax, (X_INVAL, 11.1), (X_INVAL, 10.5), color="#6A1B9A", lw=1.5, style="->")

draw_box(ax, X_INVAL, 10.0, 2.2, 0.6, "Cache Invalidation\nDelete C[k]  k'≠k", C_ADK, fontsize=9)

# Dashed arrow from invalidation to cache key
draw_arrow(ax, (X_INVAL - 1.1, 10.0), (CX + 1.5, Y_KEY), color="#6A1B9A", lw=1.5, style="->")

# ------------------------------------------------------------------
# Title & caption
# ------------------------------------------------------------------
fig.suptitle(
    "Lazy Execution & Cache Invalidation Workflow",
    fontsize=14,
    fontweight="bold",
    y=0.98,
)

fig.text(
    0.5,
    0.01,
    "Cache hits bypass expensive simulation engines; cache misses trigger full ADK → Tool → Engine delegation.\n"
    "Input changes automatically invalidate cached manifests via SHA-256 hash mismatch.",
    ha="center",
    fontsize=9,
    style="italic",
)

plt.tight_layout(rect=[0, 0.03, 1, 0.97])

# Save outputs
fig.savefig("figures/fig_3_5_lazy_execution_cache.png", dpi=300, bbox_inches="tight")
fig.savefig("figures/fig_3_5_lazy_execution_cache.pdf", bbox_inches="tight")
print("Saved figures/fig_3_5_lazy_execution_cache.png")
print("Saved figures/fig_3_5_lazy_execution_cache.pdf")
