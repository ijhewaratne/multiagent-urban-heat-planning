#!/usr/bin/env python3
"""
Generate thesis figures and tables for Chapter 4.2 Heat Demand Profiles.

Requires: 00_prepare_data.py to have been run (hourly_heat_profiles.parquet,
          cluster_design_topn.json, building_cluster_map.parquet must exist).

Usage:
  python src/scripts/generate_thesis_figures.py           # All
  python src/scripts/generate_thesis_figures.py --table-only
  python src/scripts/generate_thesis_figures.py --figures-only
"""
import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pandas as pd

from branitz_heat_decision.config import (
    DATA_PROCESSED,
    HOURLY_PROFILES_PATH,
    DESIGN_TOPN_PATH,
    BUILDING_CLUSTER_MAP_PATH,
    PROJECT_ROOT,
)


OUTPUT_DIR = PROJECT_ROOT / "output" / "thesis"
ST010_CLUSTER = "ST010_HEINRICH_ZILLE_STRASSE"
WINTER_WEEK_HOURS = (720, 888)  # Jan 1–7 (approx.)


def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_cluster_summary() -> pd.DataFrame:
    """Build cluster summary table: n_buildings, design_load_kw, annual_heat_mwh."""
    cluster_map = pd.read_parquet(BUILDING_CLUSTER_MAP_PATH)
    profiles = pd.read_parquet(HOURLY_PROFILES_PATH)
    with open(DESIGN_TOPN_PATH, "r", encoding="utf-8") as f:
        design_topn = json.load(f)

    cluster_col = "cluster_id" if "cluster_id" in cluster_map.columns else "street_id"
    if cluster_col not in cluster_map.columns:
        cluster_col = "street_cluster"

    rows = []
    for cid in sorted(cluster_map[cluster_col].unique()):
        bids = cluster_map[cluster_map[cluster_col] == cid]["building_id"].astype(str).tolist()
        available = [b for b in bids if b in profiles.columns]
        n = len(available)
        if n == 0:
            annual_mwh = 0.0
            design_load_kw = design_topn.get("clusters", {}).get(cid, {}).get("design_load_kw", 0.0)
        else:
            annual_mwh = float(profiles[available].sum().sum()) / 1000.0
            design_load_kw = design_topn.get("clusters", {}).get(cid, {}).get("design_load_kw", 0.0)
        rows.append({
            "cluster_id": cid,
            "n_buildings": n,
            "design_load_kw": round(design_load_kw, 1),
            "annual_heat_mwh": round(annual_mwh, 2),
        })
    return pd.DataFrame(rows)


def save_cluster_summary_csv(df: pd.DataFrame) -> Path:
    ensure_output_dir()
    out = OUTPUT_DIR / "cluster_summary.csv"
    df.to_csv(out, index=False)
    print(f"Saved {out}")
    return out


def generate_sfh_winter_week_figure():
    """Sample hourly profiles for residential SFH (winter week)."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping SFH winter week figure")
        return None

    profiles = pd.read_parquet(HOURLY_PROFILES_PATH)
    h_start, h_end = WINTER_WEEK_HOURS
    subset = profiles.iloc[h_start:h_end]

    # Pick up to 3 buildings (low/med/high annual demand)
    totals = profiles.sum()
    sorted_bids = totals.sort_values().index.tolist()
    n_pick = min(3, len(sorted_bids))
    # Low, median, high
    if n_pick >= 3:
        pick = [sorted_bids[0], sorted_bids[len(sorted_bids) // 2], sorted_bids[-1]]
    else:
        pick = sorted_bids[:n_pick]

    fig, ax = plt.subplots(figsize=(10, 4))
    for bid in pick:
        ax.plot(range(len(subset)), subset[bid].values, label=bid[:12] + "...", alpha=0.8)
    ax.set_xlabel("Hour of week (Jan 1–7)")
    ax.set_ylabel("Heat demand (kW)")
    ax.set_title("Sample hourly heat demand – residential SFH (winter week)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    ensure_output_dir()
    out = OUTPUT_DIR / "fig_sfh_winter_week.png"
    fig.savefig(out, dpi=150)
    plt.close()
    print(f"Saved {out}")
    return out


def generate_st010_load_duration_curve():
    """Design hour load duration curve for Heinrich-Zille-Straße."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping load duration curve")
        return None

    cluster_map = pd.read_parquet(BUILDING_CLUSTER_MAP_PATH)
    profiles = pd.read_parquet(HOURLY_PROFILES_PATH)
    with open(DESIGN_TOPN_PATH, "r", encoding="utf-8") as f:
        design_topn = json.load(f)

    cluster_col = "cluster_id" if "cluster_id" in cluster_map.columns else "street_id"
    if cluster_col not in cluster_map.columns:
        cluster_col = "street_cluster"

    bids = cluster_map[cluster_map[cluster_col] == ST010_CLUSTER]["building_id"].astype(str).tolist()
    available = [b for b in bids if b in profiles.columns]
    if not available:
        print(f"No buildings in profiles for {ST010_CLUSTER}; skipping load duration curve")
        return None

    cluster_profile = profiles[available].sum(axis=1)
    sorted_loads = cluster_profile.sort_values(ascending=False).values
    design_load = design_topn.get("clusters", {}).get(ST010_CLUSTER, {}).get("design_load_kw", float(sorted_loads[0]))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(range(1, len(sorted_loads) + 1), sorted_loads, "b-", linewidth=0.8)
    ax.scatter([1], [sorted_loads[0]], color="red", s=50, zorder=5, label=f"Design hour (peak): {design_load:.0f} kW")
    ax.set_xlabel("Rank (hours sorted by load)")
    ax.set_ylabel("Load (kW)")
    ax.set_title(f"Load duration curve – {ST010_CLUSTER}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    ensure_output_dir()
    out = OUTPUT_DIR / "fig_st010_load_duration_curve.png"
    fig.savefig(out, dpi=150)
    plt.close()
    print(f"Saved {out}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate thesis figures and cluster summary table")
    parser.add_argument("--table-only", action="store_true", help="Only generate cluster summary CSV")
    parser.add_argument("--figures-only", action="store_true", help="Only generate figures")
    args = parser.parse_args()

    if not HOURLY_PROFILES_PATH.exists():
        print(f"Missing {HOURLY_PROFILES_PATH}; run 00_prepare_data.py first.")
        sys.exit(1)
    if not DESIGN_TOPN_PATH.exists():
        print(f"Missing {DESIGN_TOPN_PATH}; run 00_prepare_data.py first.")
        sys.exit(1)
    if not BUILDING_CLUSTER_MAP_PATH.exists():
        print(f"Missing {BUILDING_CLUSTER_MAP_PATH}; run 00_prepare_data.py first.")
        sys.exit(1)

    do_table = not args.figures_only
    do_figures = not args.table_only

    if do_table:
        df = generate_cluster_summary()
        save_cluster_summary_csv(df)
        print("\nCluster summary (first 5 rows):")
        print(df.head().to_string(index=False))

    if do_figures:
        generate_sfh_winter_week_figure()
        generate_st010_load_duration_curve()


if __name__ == "__main__":
    main()
