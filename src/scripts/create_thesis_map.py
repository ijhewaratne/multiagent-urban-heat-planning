"""
Thesis Overview Map — Branitz District Heating Study Area

Generates two outputs:
  results/thesis/thesis_overview_map.png   — high-res static figure (300 DPI)
  results/thesis/thesis_overview_map.html  — interactive Folium version

Shows all 24 street clusters and 550 residential buildings in Cottbus/Branitz.
"""

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.patheffects as pe
import contextily as cx
import folium
import folium.plugins as fplugins
from branitz_heat_decision.config import DATA_PROCESSED

# ── Paths ──────────────────────────────────────────────────────────────────────
OUT_DIR = Path("results/thesis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Load data ──────────────────────────────────────────────────────────────────
sc    = gpd.read_parquet(DATA_PROCESSED / "street_clusters.parquet")
bldgs = gpd.read_parquet(DATA_PROCESSED / "buildings.parquet")

print(f"Loaded {len(sc)} street clusters, {len(bldgs)} residential buildings")

# ── Colour scheme ──────────────────────────────────────────────────────────────
C_STREET    = "#2c5f8a"   # steel blue for all street clusters
C_BLDG_FILL = "#f0a500"   # warm amber for all buildings
C_BLDG_EDGE = "#b8860b"

FONT = "DejaVu Sans"


# ══════════════════════════════════════════════════════════════════════════════
#  PART 1 — Static matplotlib / contextily map
# ══════════════════════════════════════════════════════════════════════════════

def make_static_map() -> Path:
    sc_m    = sc.to_crs(3857)
    bldgs_m = bldgs.to_crs(3857)

    bounds = sc_m.total_bounds          # [xmin, ymin, xmax, ymax]
    pad_x  = (bounds[2] - bounds[0]) * 0.10
    pad_y  = (bounds[3] - bounds[1]) * 0.10

    fig, ax = plt.subplots(figsize=(14, 11), dpi=300)
    ax.set_xlim(bounds[0] - pad_x, bounds[2] + pad_x)
    ax.set_ylim(bounds[1] - pad_y, bounds[3] + pad_y)

    # ── Basemap ───────────────────────────────────────────────────────────────
    cx.add_basemap(
        ax,
        crs=sc_m.crs.to_string(),
        source=cx.providers.CartoDB.Positron,
        zoom=16,
        attribution_size=6,
    )

    # ── Residential buildings ─────────────────────────────────────────────────
    bldgs_m.plot(
        ax=ax,
        facecolor=C_BLDG_FILL,
        edgecolor=C_BLDG_EDGE,
        linewidth=0.4,
        alpha=0.75,
        zorder=2,
    )

    # ── Street cluster lines ──────────────────────────────────────────────────
    sc_m.plot(
        ax=ax,
        color=C_STREET,
        linewidth=2.5,
        alpha=0.85,
        zorder=4,
    )

    # ── Street name labels (white halo for readability) ───────────────────────
    for _, row in sc_m.iterrows():
        cid  = row["cluster_id"]
        name = row.get("cluster_name", cid.replace("_", " "))
        cx_  = row.geometry.centroid.x
        cy_  = row.geometry.centroid.y

        txt = ax.text(
            cx_, cy_, name,
            ha="center", va="center",
            fontsize=6.5, fontweight="bold",
            color=C_STREET,
            fontfamily=FONT,
            zorder=6,
        )
        txt.set_path_effects([
            pe.withStroke(linewidth=2.5, foreground="white"),
        ])

    # ── Scale bar (bottom left) ───────────────────────────────────────────────
    xmin = bounds[0] - pad_x
    ymin = bounds[1] - pad_y
    xmax = bounds[2] + pad_x
    ymax = bounds[3] + pad_y
    sb_len = 200
    sb_x0  = xmin + (xmax - xmin) * 0.05
    sb_y0  = ymin + (ymax - ymin) * 0.04
    ax.plot([sb_x0, sb_x0 + sb_len], [sb_y0, sb_y0],
            color="black", linewidth=2.5, solid_capstyle="butt", zorder=8)
    ax.plot([sb_x0, sb_x0], [sb_y0 - 8, sb_y0 + 8],
            color="black", linewidth=1.5, zorder=8)
    ax.plot([sb_x0 + sb_len, sb_x0 + sb_len], [sb_y0 - 8, sb_y0 + 8],
            color="black", linewidth=1.5, zorder=8)
    ax.text(sb_x0 + sb_len / 2, sb_y0 + 18, "200 m",
            ha="center", va="bottom", fontsize=7, fontfamily=FONT, zorder=8)

    # ── North arrow (top right) ───────────────────────────────────────────────
    na_x    = xmax - (xmax - xmin) * 0.06
    na_y    = ymax - (ymax - ymin) * 0.06
    arr_len = (ymax - ymin) * 0.035
    ax.annotate(
        "", xy=(na_x, na_y), xytext=(na_x, na_y - arr_len),
        arrowprops=dict(arrowstyle="->, head_length=0.4, head_width=0.25",
                        color="black", lw=1.5),
        zorder=9,
    )
    ax.text(na_x, na_y + arr_len * 0.3, "N",
            ha="center", va="bottom", fontsize=9, fontweight="bold",
            fontfamily=FONT, zorder=9)

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(facecolor=C_BLDG_FILL, edgecolor=C_BLDG_EDGE,
                       label="Residential building"),
        mlines.Line2D([], [], color=C_STREET, linewidth=2.5,
                      label="Street cluster of interest"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower right",
        fontsize=8,
        framealpha=0.92,
        edgecolor="#cccccc",
        facecolor="white",
        title="Map Legend",
        title_fontsize=9,
    )

    # ── Title and axis labels ─────────────────────────────────────────────────
    ax.set_title(
        "Branitz Study Area — Street Clusters and Residential Buildings\n"
        "Cottbus, Brandenburg, Germany",
        fontsize=11, fontweight="bold", fontfamily=FONT, pad=10,
    )
    ax.set_xlabel("Easting (m, EPSG:3857)", fontsize=7, color="#666666")
    ax.set_ylabel("Northing (m, EPSG:3857)", fontsize=7, color="#666666")
    ax.tick_params(labelsize=6, colors="#888888")
    for spine in ax.spines.values():
        spine.set_edgecolor("#cccccc")
        spine.set_linewidth(0.8)

    plt.tight_layout()
    out = OUT_DIR / "thesis_overview_map.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved static map: {out}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  PART 2 — Interactive Folium map
# ══════════════════════════════════════════════════════════════════════════════

def make_interactive_map() -> Path:
    sc_wgs    = sc.to_crs(4326)
    bldgs_wgs = bldgs.to_crs(4326)

    cen = sc_wgs.geometry.unary_union.centroid
    m = folium.Map(
        location=[cen.y, cen.x],
        zoom_start=16,
        tiles="CartoDB positron",
        control_scale=True,
    )

    # ── Residential buildings ─────────────────────────────────────────────────
    bldg_layer = folium.FeatureGroup(name="Residential Buildings", show=True)
    for _, b in bldgs_wgs.iterrows():
        demand = b.get("annual_heat_demand_kwh_a", 0) or 0
        area   = b.get("footprint_m2", 0) or 0
        coords = [[pt[1], pt[0]] for pt in b.geometry.exterior.coords]
        popup  = (
            f"<b>Building</b>: {b['building_id']}<br>"
            f"<b>Heat demand</b>: {demand:,.0f} kWh/a<br>"
            f"<b>Footprint</b>: {area:.0f} m²"
        )
        folium.Polygon(
            locations=coords,
            color=C_BLDG_EDGE,
            weight=0.8,
            fill=True,
            fill_color=C_BLDG_FILL,
            fill_opacity=0.75,
            tooltip=f"{b['building_id']} — {demand:,.0f} kWh/a",
            popup=folium.Popup(popup, max_width=260),
        ).add_to(bldg_layer)
    bldg_layer.add_to(m)

    # ── Street clusters ───────────────────────────────────────────────────────
    street_layer = folium.FeatureGroup(name="Street Clusters", show=True)
    for _, row in sc_wgs.iterrows():
        cid  = row["cluster_id"]
        name = row.get("cluster_name", cid.replace("_", " "))
        geom = row.geometry
        if geom.geom_type == "LineString":
            line_parts = [list(geom.coords)]
        elif geom.geom_type == "MultiLineString":
            line_parts = [list(part.coords) for part in geom.geoms]
        else:
            continue

        popup_html = (
            f"<div style='font-family:Arial'>"
            f"<b>{name}</b>"
            f"<br><b>Buildings</b>: {row.get('building_count', '?')}"
            f"</div>"
        )
        for coords in line_parts:
            folium.PolyLine(
                locations=[[c[1], c[0]] for c in coords],
                color=C_STREET,
                weight=4,
                opacity=0.85,
                tooltip=name,
                popup=folium.Popup(popup_html, max_width=280),
            ).add_to(street_layer)
    street_layer.add_to(m)

    # ── Street name labels (permanent DivIcon) ────────────────────────────────
    label_layer = folium.FeatureGroup(name="Street Labels", show=True)
    for _, row in sc_wgs.iterrows():
        cid    = row["cluster_id"]
        name   = row.get("cluster_name", cid.replace("_", " "))
        cen_pt = row.geometry.centroid
        label_html = (
            f'<div style="font-family:Arial; font-size:10px; font-weight:bold; '
            f'color:{C_STREET}; white-space:nowrap; '
            f'text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, '
            f'-1px 1px 0 #fff, 1px 1px 0 #fff;">'
            f'{name}</div>'
        )
        folium.Marker(
            location=[cen_pt.y, cen_pt.x],
            icon=folium.DivIcon(
                html=label_html,
                icon_size=(180, 20),
                icon_anchor=(90, 10),
            ),
        ).add_to(label_layer)
    label_layer.add_to(m)

    # ── Title box ─────────────────────────────────────────────────────────────
    title_html = """
    <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
                z-index: 9999; background: rgba(255,255,255,0.92);
                border: 1px solid #ccc; border-radius: 8px;
                padding: 8px 18px; text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
        <b style="font-size:14px; font-family:Arial;">Branitz Study Area</b><br>
        <span style="font-size:11px; color:#555; font-family:Arial;">
            Street Clusters &amp; Residential Buildings — Cottbus, Germany
        </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # ── Legend box ────────────────────────────────────────────────────────────
    legend_html = f"""
    <div style="position: fixed; bottom: 30px; left: 15px; z-index: 9998;
                background: rgba(255,255,255,0.95); border: 1px solid #ccc;
                border-radius: 8px; padding: 10px 14px; font-family: Arial;
                font-size: 11px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
        <b style="font-size:12px;">Legend</b><br><br>
        <span style="background:{C_BLDG_FILL}; border:1px solid {C_BLDG_EDGE};
              padding:1px 10px; border-radius:3px;">&nbsp;</span>
        &nbsp;Residential building<br><br>
        <span style="background:{C_STREET};
              padding:1px 10px; border-radius:3px;">&nbsp;</span>
        &nbsp;Street cluster of interest
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    fplugins.Fullscreen().add_to(m)

    out = OUT_DIR / "thesis_overview_map.html"
    m.save(str(out))
    print(f"  Saved interactive map: {out}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating thesis overview maps …")
    static_path      = make_static_map()
    interactive_path = make_interactive_map()
    print("\nDone.")
    print(f"  Static PNG  : {static_path}")
    print(f"  Interactive : {interactive_path}")
