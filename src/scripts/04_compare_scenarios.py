#!/usr/bin/env python3
"""
Scenario comparison — DH vs HP winner per cluster across economic scenarios.

Answers the core Wärmeplanungsgesetz question: *does the recommendation flip
between today's prices and a future scenario?*

For each cluster and each scenario this script:
  1. Runs economics with ``--scenario <name>``   (skipped with --no-run)
  2. Runs the decision engine with ``--scenario <name>`` (JSON only, no LLM)
  3. Reads ``decision_<cluster>.json`` and collects choice / robustness / LCOH

Outputs (results/decision/scenario_comparison/):
  - scenario_comparison.json
  - scenario_comparison.csv
  - scenario_comparison.md   (human-readable flip table)

Usage:
  PYTHONPATH=src python src/scripts/04_compare_scenarios.py \\
      --cluster-id ST010_HEINRICH_ZILLE_STRASSE \\
      --scenarios 2023_baseline,2030_optimistic

  PYTHONPATH=src python src/scripts/04_compare_scenarios.py --all-clusters
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parents[1]))

from branitz_heat_decision.config import RESULTS_ROOT
from branitz_heat_decision.economics.scenarios import (
    list_scenarios,
    resolve_scenario_path,
    scenario_name,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = Path(__file__).resolve().parents[1]


def _list_clusters() -> List[str]:
    base = Path(RESULTS_ROOT) / "cha"
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def _decision_config_for_scenario(name: str) -> Optional[Path]:
    """Match e.g. '2030_optimistic' -> config/decision_config_2030.json (if present)."""
    year = name.split("_", 1)[0]
    candidate = REPO_ROOT / "config" / f"decision_config_{year}.json"
    return candidate if candidate.exists() else None


def _run(cmd: List[str]) -> bool:
    print(f"  $ {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  ✗ failed (rc={res.returncode}): {res.stderr.strip().splitlines()[-1:] }",
              file=sys.stderr)
        return False
    return True


def run_scenario(cluster_id: str, scenario: str, no_run: bool) -> Optional[Dict[str, Any]]:
    """Run economics + decision for one cluster/scenario; return decision dict."""
    name = scenario_name(scenario)

    if not no_run:
        ok = _run([
            sys.executable, str(SRC_DIR / "scripts" / "03_run_economics.py"),
            "--cluster-id", cluster_id, "--scenario", scenario,
        ])
        if ok:
            dec_cmd = [
                sys.executable, "-m", "branitz_heat_decision.cli.decision",
                "--cluster-id", cluster_id, "--scenario", name,
                "--format", "json",  # decision only — no LLM explanation
            ]
            cfg = _decision_config_for_scenario(name)
            if cfg:
                dec_cmd += ["--config", str(cfg)]
            _run(dec_cmd)

    dec_path = (
        Path(RESULTS_ROOT) / "decision" / cluster_id / "scenarios" / name
        / f"decision_{cluster_id}.json"
    )
    if not dec_path.exists():
        print(f"  ! missing {dec_path}", file=sys.stderr)
        return None
    return json.loads(dec_path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--cluster-id", action="append", help="Cluster ID (repeatable)")
    group.add_argument("--all-clusters", action="store_true",
                       help="All clusters under results/cha/")
    ap.add_argument(
        "--scenarios", default="2023_baseline,2030_optimistic",
        help="Comma-separated scenario names or YAML paths "
             f"(available: {', '.join(list_scenarios()) or 'none'})",
    )
    ap.add_argument("--no-run", action="store_true",
                    help="Only aggregate existing results; do not run pipelines")
    ap.add_argument("--out-dir", default=None, help="Output directory")
    args = ap.parse_args()

    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    for s in scenarios:
        resolve_scenario_path(s)  # fail fast on typos
    names = [scenario_name(s) for s in scenarios]

    clusters = args.cluster_id if args.cluster_id else _list_clusters()
    if not clusters:
        raise SystemExit("No clusters found (run CHA first) and none given via --cluster-id.")

    rows: List[Dict[str, Any]] = []
    for cid in clusters:
        print(f"\n=== {cid} ===")
        row: Dict[str, Any] = {"cluster_id": cid}
        choices: List[Optional[str]] = []
        for scen, name in zip(scenarios, names):
            print(f"-- scenario: {name}")
            dec = run_scenario(cid, scen, args.no_run)
            choice = dec.get("choice") if dec else None
            metrics = (dec or {}).get("metrics_used", {})
            row[f"{name}_choice"] = choice
            row[f"{name}_robust"] = (dec or {}).get("robust")
            row[f"{name}_lcoh_dh"] = metrics.get("lcoh_dh_median")
            row[f"{name}_lcoh_hp"] = metrics.get("lcoh_hp_median")
            choices.append(choice)
        valid = [c for c in choices if c]
        row["winner_flips"] = len(set(valid)) > 1 if len(valid) > 1 else None
        rows.append(row)

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(RESULTS_ROOT) / "decision" / "scenario_comparison"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    payload = {"scenarios": names, "clusters": rows}
    (out_dir / "scenario_comparison.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    # CSV (no pandas dependency)
    import csv

    fieldnames = list(rows[0].keys()) if rows else ["cluster_id"]
    with open(out_dir / "scenario_comparison.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # Markdown flip table
    md = ["# Scenario Comparison — DH vs HP\n",
          f"Scenarios: {', '.join(names)}\n"]
    header = "| Cluster | " + " | ".join(f"{n} (LCOH DH/HP)" for n in names) + " | Flips? |"
    sep = "|---" * (len(names) + 2) + "|"
    md += [header, sep]
    n_flips = 0
    for row in rows:
        cells = []
        for name in names:
            c = row.get(f"{name}_choice") or "—"
            dh = row.get(f"{name}_lcoh_dh")
            hp = row.get(f"{name}_lcoh_hp")
            lcoh = (f" ({dh:.0f}/{hp:.0f} €/MWh)"
                    if isinstance(dh, (int, float)) and isinstance(hp, (int, float)) else "")
            robust = "" if row.get(f"{name}_robust") in (None, True) else " ⚠ sensitive"
            cells.append(f"**{c}**{lcoh}{robust}")
        flip = row.get("winner_flips")
        flip_label = "🔄 **YES**" if flip else ("no" if flip is False else "—")
        if flip:
            n_flips += 1
        md.append(f"| {row['cluster_id']} | " + " | ".join(cells) + f" | {flip_label} |")
    md.append(f"\n**{n_flips}/{len(rows)} clusters flip winner across scenarios.**\n")
    (out_dir / "scenario_comparison.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\n✓ Wrote: {out_dir}/scenario_comparison.{{json,csv,md}}")
    print(f"  Winner flips: {n_flips}/{len(rows)} clusters")


if __name__ == "__main__":
    main()
