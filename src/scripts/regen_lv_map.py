"""
Regenerate hp_lv_map.html from existing buses_results.geojson + lines_results.geojson.
Fixes:
  - Centre on network centroid (not first bus)
  - Overloaded lines (>100%) drawn thicker and on top
  - Combined voltage + line-loading legend
  - Fullscreen + LayerControl plugins
  - Cluster-name title
  - Buses filtered to lines spatial extent (removes off-cluster stray buses)
"""

import sys
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import numpy as np
import folium
import folium.plugins as fplugins
from branca.colormap import LinearColormap

CLUSTER   = "ST010_HEINRICH_ZILLE_STRASSE"
LABEL     = "Heinrich-Zille-Straße (ST010)"
DHA_DIR   = Path("results/dha") / CLUSTER
OUT_PATH  = DHA_DIR / "hp_lv_map.html"

# ── Load GeoJSON ──────────────────────────────────────────────────────────────
buses_geo = json.loads((DHA_DIR / "buses_results.geojson").read_text())
lines_geo = json.loads((DHA_DIR / "lines_results.geojson").read_text())

# ── Derive spatial extent of LINES (the relevant sub-network) ─────────────────
line_coords = [
    coord
    for f in lines_geo["features"]
    for coord in f["geometry"]["coordinates"]
]
if not line_coords:
    print("No line coordinates found — aborting.")
    sys.exit(1)

lons = [c[0] for c in line_coords]
lats = [c[1] for c in line_coords]
lon_min, lon_max = min(lons), max(lons)
lat_min, lat_max = min(lats), max(lats)

# Add 20 % padding for breathing room
pad_lon = (lon_max - lon_min) * 0.20
pad_lat = (lat_max - lat_min) * 0.20
lon_min -= pad_lon;  lon_max += pad_lon
lat_min -= pad_lat;  lat_max += pad_lat

# Filter buses to those within the lines bounding box
def _in_bbox(lon, lat):
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max

buses_filtered = {
    "type": "FeatureCollection",
    "features": [
        f for f in buses_geo["features"]
        if _in_bbox(*f["geometry"]["coordinates"])
    ],
}
print(f"Buses: {len(buses_geo['features'])} total → {len(buses_filtered['features'])} in cluster bbox")
print(f"Lines: {len(lines_geo['features'])}")

# ── Map centre & zoom ─────────────────────────────────────────────────────────
cen_lat = (lat_min + lat_max) / 2
cen_lon = (lon_min + lon_max) / 2

m = folium.Map(
    location=[cen_lat, cen_lon],
    zoom_start=17,
    tiles="CartoDB positron",
    control_scale=True,
)
fplugins.Fullscreen().add_to(m)

# ── Colormaps ─────────────────────────────────────────────────────────────────
line_cmap = LinearColormap(
    ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"],
    vmin=0, vmax=150,
    index=[0, 50, 100, 150],
    caption="Line loading (%)",
)

def _bus_color(v):
    try:
        v = float(v)
    except Exception:
        return "#aaaaaa"
    if v < 0.90:   return "#e74c3c"   # Critical
    if v < 0.95:   return "#e67e22"   # Warning
    if v < 1.00:   return "#f1c40f"   # Caution
    return "#2ecc71"                   # Good

def _line_color(pct):
    try:
        pct = float(pct)
    except Exception:
        pct = 0.0
    return line_cmap(min(pct, 150))

# ── Normal lines layer (loading ≤ 100 %) ──────────────────────────────────────
normal_layer = folium.FeatureGroup(name="LV Lines — normal (≤ 100 %)", show=True)
overload_layer = folium.FeatureGroup(name="LV Lines — overloaded (> 100 %)", show=True)

for f in lines_geo["features"]:
    coords = f["geometry"]["coordinates"]     # [[lon,lat], [lon,lat]]
    props  = f["properties"]
    pct    = float(props.get("loading_percent", 0) or 0)
    color  = _line_color(pct)
    name   = props.get("name", f"Line {props.get('line','?')}")

    popup_html = (
        f"<b>{name}</b><br>"
        f"Loading: <b>{pct:.1f} %</b><br>"
        f"Hour: {props.get('hour', '?')}<br>"
        f"P from: {props.get('p_from_mw', '?')} MW"
    )

    latlons = [[c[1], c[0]] for c in coords]

    if pct > 100:
        folium.PolyLine(
            latlons,
            color=color,
            weight=7,
            opacity=1.0,
            tooltip=f"{name}: {pct:.1f} % ⚠",
            popup=folium.Popup(popup_html, max_width=200),
        ).add_to(overload_layer)
    else:
        folium.PolyLine(
            latlons,
            color=color,
            weight=3.5,
            opacity=0.85,
            tooltip=f"{name}: {pct:.1f} %",
            popup=folium.Popup(popup_html, max_width=200),
        ).add_to(normal_layer)

normal_layer.add_to(m)
overload_layer.add_to(m)   # rendered on top

# ── Bus voltage markers ───────────────────────────────────────────────────────
bus_layer = folium.FeatureGroup(name="LV Buses — voltage", show=True)
for f in buses_filtered["features"]:
    lon, lat = f["geometry"]["coordinates"]
    props = f["properties"]
    v     = props.get("v_min_pu") or props.get("vm_pu")
    color = _bus_color(v)
    v_str = f"{float(v):.4f} pu" if v is not None else "N/A"
    folium.CircleMarker(
        location=[lat, lon],
        radius=5,
        fill=True,
        fill_opacity=0.9,
        color="#333333",
        weight=0.8,
        fill_color=color,
        tooltip=f"Bus {props.get('bus','?')} — V: {v_str}",
        popup=folium.Popup(
            f"<b>Bus {props.get('bus','?')}</b><br>Voltage: <b>{v_str}</b><br>Hour: {props.get('hour','?')}",
            max_width=180,
        ),
    ).add_to(bus_layer)
bus_layer.add_to(m)

# ── Line loading colormap legend ──────────────────────────────────────────────
line_cmap.add_to(m)

# ── Combined HTML legend ──────────────────────────────────────────────────────
n_overload = sum(
    1 for f in lines_geo["features"]
    if float(f["properties"].get("loading_percent", 0) or 0) > 100
)
max_loading = max(
    (float(f["properties"].get("loading_percent", 0) or 0) for f in lines_geo["features"]),
    default=0,
)
all_v = [
    float(f["properties"].get("v_min_pu") or f["properties"].get("vm_pu") or 1.0)
    for f in buses_filtered["features"]
]
min_v = min(all_v) if all_v else 1.0

legend_html = f"""
<div style="position: fixed; bottom: 30px; left: 15px; z-index: 9998;
            background: rgba(255,255,255,0.96); border: 1px solid #ccc;
            border-radius: 10px; padding: 12px 16px; font-family: Arial;
            font-size: 11px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); min-width: 200px;">
  <b style="font-size:13px;">LV Grid Legend</b><br><br>

  <b>Bus Voltage</b><br>
  <span style="color:#2ecc71;">&#9679;</span> Good  (≥ 1.00 pu)<br>
  <span style="color:#f1c40f;">&#9679;</span> Caution (0.95 – 1.00 pu)<br>
  <span style="color:#e67e22;">&#9679;</span> Warning (0.90 – 0.95 pu)<br>
  <span style="color:#e74c3c;">&#9679;</span> Critical (< 0.90 pu)<br><br>

  <b>Line Loading</b><br>
  <span style="background:#2ecc71; padding:1px 8px; border-radius:2px;">&nbsp;</span> &lt; 50 %<br>
  <span style="background:#f1c40f; padding:1px 8px; border-radius:2px;">&nbsp;</span> 50 – 100 %<br>
  <span style="background:#e67e22; padding:1px 8px; border-radius:2px;">&nbsp;</span> 100 – 150 %<br>
  <span style="background:#e74c3c; padding:1px 8px; border-radius:2px;">&nbsp;</span> &gt; 150 % (overloaded)<br><br>

  <b>Network Summary</b><br>
  Overloaded lines: <b style="color:#e74c3c;">{n_overload}</b><br>
  Max loading: <b>{max_loading:.1f} %</b><br>
  Min voltage: <b>{min_v:.4f} pu</b>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Title box ─────────────────────────────────────────────────────────────────
title_html = f"""
<div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
            z-index: 9999; background: rgba(255,255,255,0.95);
            border: 1px solid #ccc; border-radius: 8px;
            padding: 8px 20px; text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
  <b style="font-size:14px; font-family:Arial;">LV Grid — HP Hosting Capacity</b><br>
  <span style="font-size:11px; color:#555; font-family:Arial;">
    {LABEL} &nbsp;|&nbsp; Worst-case hour &nbsp;|&nbsp;
    {n_overload} overloaded lines &nbsp;|&nbsp; Max loading {max_loading:.1f} %
  </span>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

# ── Layer control ─────────────────────────────────────────────────────────────
folium.LayerControl(collapsed=False).add_to(m)

# ── Fit bounds to lines extent ────────────────────────────────────────────────
m.fit_bounds([[lat_min, lon_min], [lat_max, lon_max]])

# ── Save ──────────────────────────────────────────────────────────────────────
m.save(str(OUT_PATH))
print(f"\nSaved: {OUT_PATH}")
print(f"  Centre: ({cen_lat:.5f}, {cen_lon:.5f})")
print(f"  Buses in view: {len(buses_filtered['features'])}")
print(f"  Lines: {len(lines_geo['features'])} ({n_overload} overloaded)")
print(f"  Max loading: {max_loading:.1f} %   Min voltage: {min_v:.4f} pu")
