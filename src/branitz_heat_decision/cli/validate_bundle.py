#!/usr/bin/env python3
"""
Speaker-B Stepwise Validation Bundle Generator

One command that produces a single folder with all artifacts for reproducible
validation.  Every intermediate output (CHA KPIs, DHA KPIs, economics,
decision, KPI contract, agent trace) is copied into a timestamped bundle
directory together with a human-readable validation report.

Examples:
  # Generate bundle for a single cluster
  PYTHONPATH=src python -m branitz_heat_decision.cli.validate_bundle \
      --cluster-id ST010_HEINRICH_ZILLE_STRASSE

  # Skip simulations that already have results on disk
  PYTHONPATH=src python -m branitz_heat_decision.cli.validate_bundle \
      --cluster-id ST010_HEINRICH_ZILLE_STRASSE --skip-existing

  # Custom output location
  PYTHONPATH=src python -m branitz_heat_decision.cli.validate_bundle \
      --cluster-id ST010_HEINRICH_ZILLE_STRASSE -o ./my_bundles
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from branitz_heat_decision.config import resolve_cluster_path, RESULTS_ROOT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a complete validation bundle for Speaker-B review.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m branitz_heat_decision.cli.validate_bundle "
            "--cluster-id ST010_HEINRICH_ZILLE_STRASSE\n"
            "  python -m branitz_heat_decision.cli.validate_bundle "
            "--cluster-id ST010_HEINRICH_ZILLE_STRASSE --skip-existing\n"
        ),
    )
    parser.add_argument(
        "--cluster-id",
        required=True,
        help="Cluster identifier (e.g. ST010_HEINRICH_ZILLE_STRASSE)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="./validation_bundle",
        help="Parent directory for the bundle (default: ./validation_bundle)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip simulation steps whose result files already exist on disk",
    )
    parser.add_argument(
        "--llm-explanation",
        action="store_true",
        default=True,
        help="Use LLM-based explanation (default: True, falls back to template)",
    )
    parser.add_argument(
        "--template-only",
        action="store_true",
        help="Force template-based explanation (skip LLM)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file, returning empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return {}


def _save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _step_banner(step: int, total: int, label: str) -> None:
    print(f"\n  [{step}/{total}] {label}")


# ---------------------------------------------------------------------------
# Pipeline steps (thin wrappers around ADK tools)
# ---------------------------------------------------------------------------

def _run_cha(cluster_id: str, skip_existing: bool) -> Dict[str, Any]:
    """Run CHA simulation via ADK tool, return tool result dict."""
    from branitz_heat_decision.adk.tools import run_cha_tool

    kpis_path = resolve_cluster_path(cluster_id, "cha") / "cha_kpis.json"
    if skip_existing and kpis_path.exists():
        print("      -> Skipped (results already exist)")
        return {"status": "skipped"}

    result = run_cha_tool(cluster_id)
    print(f"      -> {result['status']}")
    return result


def _run_dha(cluster_id: str, skip_existing: bool) -> Dict[str, Any]:
    """Run DHA simulation via ADK tool, return tool result dict."""
    from branitz_heat_decision.adk.tools import run_dha_tool

    kpis_path = resolve_cluster_path(cluster_id, "dha") / "dha_kpis.json"
    if skip_existing and kpis_path.exists():
        print("      -> Skipped (results already exist)")
        return {"status": "skipped"}

    result = run_dha_tool(cluster_id)
    print(f"      -> {result['status']}")
    return result


def _run_economics(cluster_id: str, skip_existing: bool) -> Dict[str, Any]:
    """Run Economics pipeline via ADK tool, return tool result dict."""
    from branitz_heat_decision.adk.tools import run_economics_tool

    econ_path = resolve_cluster_path(cluster_id, "economics") / "economics_deterministic.json"
    if skip_existing and econ_path.exists():
        print("      -> Skipped (results already exist)")
        return {"status": "skipped"}

    result = run_economics_tool(cluster_id)
    print(f"      -> {result['status']}")
    return result


def _run_decision(cluster_id: str, skip_existing: bool, template_only: bool) -> Dict[str, Any]:
    """Run Decision pipeline via ADK tool, return tool result dict."""
    from branitz_heat_decision.adk.tools import run_decision_tool

    decision_path = (
        resolve_cluster_path(cluster_id, "decision") / f"decision_{cluster_id}.json"
    )
    if skip_existing and decision_path.exists():
        print("      -> Skipped (results already exist)")
        return {"status": "skipped"}

    result = run_decision_tool(
        cluster_id,
        llm_explanation=not template_only,
    )
    print(f"      -> {result['status']}")
    return result


def _build_kpi_contract(cluster_id: str) -> Dict[str, Any]:
    """Build the KPI contract from available simulation artifacts."""
    from branitz_heat_decision.decision.kpi_contract import build_kpi_contract

    cha_path = resolve_cluster_path(cluster_id, "cha") / "cha_kpis.json"
    dha_path = resolve_cluster_path(cluster_id, "dha") / "dha_kpis.json"

    # Economics summary: current format first, then legacy fallback
    econ_dir = resolve_cluster_path(cluster_id, "economics")
    econ_path = econ_dir / "economics_monte_carlo.json"
    if not econ_path.exists():
        econ_path = econ_dir / "monte_carlo_summary.json"

    cha_kpis = _load_json(cha_path) if cha_path.exists() else {}
    dha_kpis = _load_json(dha_path) if dha_path.exists() else {}
    econ_summary = _load_json(econ_path) if econ_path.exists() else {}

    metadata = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {
            "cha_kpis_path": str(cha_path),
            "dha_kpis_path": str(dha_path),
            "econ_summary_path": str(econ_path),
        },
        "notes": ["Generated by validate_bundle CLI"],
    }

    contract = build_kpi_contract(cluster_id, cha_kpis, dha_kpis, econ_summary, metadata)
    return contract


def _capture_agent_trace(cluster_id: str) -> Dict[str, Any]:
    """
    Run a sample 'Explain the decision' query through the Orchestrator and
    return the full response including agent_trace.
    """
    try:
        from branitz_heat_decision.agents import BranitzOrchestrator

        api_key = os.getenv("GOOGLE_API_KEY", "")
        orchestrator = BranitzOrchestrator(api_key=api_key)
        response = orchestrator.route_request(
            user_query="Explain the decision",
            cluster_id=cluster_id,
            context={},
            run_missing=False,  # Don't re-run simulations; just explain
        )
        return {
            "query": "Explain the decision",
            "cluster_id": cluster_id,
            "agent_trace": response.get("agent_trace", []),
            "answer": response.get("answer", ""),
            "type": response.get("type", ""),
            "sources": response.get("sources", []),
        }
    except Exception as exc:
        logger.warning("Agent trace capture failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Bundle assembly
# ---------------------------------------------------------------------------

_ARTIFACT_MAP: List[Tuple[str, str, str]] = [
    # (phase, filename_in_results, filename_in_bundle)
    ("cha", "cha_kpis.json", "01_cha_kpis.json"),
    ("cha", "network.pickle", "01_cha_network.pickle"),
    ("cha", "interactive_map.html", "01_cha_map_velocity.html"),
    ("cha", "interactive_map_temperature.html", "01_cha_map_temperature.html"),
    ("cha", "interactive_map_pressure.html", "01_cha_map_pressure.html"),
    ("dha", "dha_kpis.json", "02_dha_kpis.json"),
    ("dha", "hp_lv_map.html", "02_dha_map.html"),
    ("dha", "violations.csv", "02_dha_violations.csv"),
    ("economics", "economics_deterministic.json", "03_economics_deterministic.json"),
    ("economics", "monte_carlo_summary.json", "03_monte_carlo_summary.json"),
]


def _assemble_bundle(
    cluster_id: str,
    bundle_path: Path,
    kpi_contract: Dict[str, Any],
    agent_trace: Dict[str, Any],
) -> List[str]:
    """
    Copy all artifacts into the bundle directory.
    Returns list of filenames that were successfully copied.
    """
    copied: List[str] = []

    # Copy simulation artifacts
    for phase, src_name, dst_name in _ARTIFACT_MAP:
        src = resolve_cluster_path(cluster_id, phase) / src_name
        if src.exists():
            shutil.copy2(src, bundle_path / dst_name)
            copied.append(dst_name)

    # Decision artifacts (cluster-id-suffixed filenames)
    decision_dir = resolve_cluster_path(cluster_id, "decision")
    for pattern, dst_name in [
        (f"decision_{cluster_id}.json", "04_decision.json"),
        (f"kpi_contract_{cluster_id}.json", "04_kpi_contract.json"),
        (f"explanation_{cluster_id}.md", "04_explanation.md"),
        (f"explanation_{cluster_id}.html", "04_explanation.html"),
        (f"validation_{cluster_id}.json", "04_validation.json"),
    ]:
        src = decision_dir / pattern
        if src.exists():
            shutil.copy2(src, bundle_path / dst_name)
            copied.append(dst_name)

    # UHDC artifacts
    uhdc_dir = resolve_cluster_path(cluster_id, "uhdc")
    if uhdc_dir.exists():
        for pattern, dst_name in [
            (f"uhdc_report_{cluster_id}.html", "05_uhdc_report.html"),
            (f"uhdc_explanation_{cluster_id}.md", "05_uhdc_explanation.md"),
        ]:
            src = uhdc_dir / pattern
            if src.exists():
                shutil.copy2(src, bundle_path / dst_name)
                copied.append(dst_name)

    # Save generated contract and agent trace
    _save_json(kpi_contract, bundle_path / "06_kpi_contract_rebuilt.json")
    copied.append("06_kpi_contract_rebuilt.json")

    _save_json(agent_trace, bundle_path / "07_agent_trace.json")
    copied.append("07_agent_trace.json")

    return copied


# ---------------------------------------------------------------------------
# Validation report generation
# ---------------------------------------------------------------------------

def _generate_validation_report(
    bundle_path: Path,
    cluster_id: str,
    step_results: Dict[str, Dict[str, Any]],
    copied_artifacts: List[str],
) -> str:
    """Generate a Markdown validation report summarising all steps."""

    # Load key artifacts from the bundle
    cha = _load_json(bundle_path / "01_cha_kpis.json")
    dha = _load_json(bundle_path / "02_dha_kpis.json")
    econ = _load_json(bundle_path / "03_economics_deterministic.json")
    decision = _load_json(bundle_path / "04_decision.json")
    validation = _load_json(bundle_path / "04_validation.json")

    # ---- Validation checks --------------------------------------------------
    checks: List[Tuple[str, str, str]] = []

    # Check 1: CHA completed
    cha_ok = bool(cha) and (
        step_results.get("cha", {}).get("status") in ("success", "skipped")
    )
    checks.append(
        ("pass" if cha_ok else "FAIL", "CHA Simulation",
         step_results.get("cha", {}).get("status", "MISSING"))
    )

    # Check 2: DHA completed
    dha_ok = bool(dha) and (
        step_results.get("dha", {}).get("status") in ("success", "skipped")
    )
    checks.append(
        ("pass" if dha_ok else "FAIL", "DHA Simulation",
         step_results.get("dha", {}).get("status", "MISSING"))
    )

    # Check 3: Economics sanity
    lcoh_dh = econ.get("lcoh_dh_eur_per_mwh", 0)
    lcoh_hp = econ.get("lcoh_hp_eur_per_mwh", 0)
    econ_sane = isinstance(lcoh_dh, (int, float)) and isinstance(lcoh_hp, (int, float))
    econ_sane = econ_sane and (0 < lcoh_dh < 500) and (0 < lcoh_hp < 500)
    checks.append(
        ("pass" if econ_sane else "WARN",
         "Economics Sanity",
         f"DH={lcoh_dh:.1f}, HP={lcoh_hp:.1f} EUR/MWh" if econ_sane else "Values missing or out of range")
    )

    # Check 4: Decision made
    choice = decision.get("choice", decision.get("recommendation", "UNKNOWN"))
    robust = decision.get("robust", False)
    decision_ok = choice in ("DH", "HP")
    checks.append(
        ("pass" if decision_ok else "FAIL",
         "Decision Made",
         f"{choice} (robust: {robust})")
    )

    # Check 5: Explanation validation (TNLI)
    val_status = validation.get("validation_status", "unknown")
    val_ok = val_status in ("pass", "pass_with_warnings")
    checks.append(
        ("pass" if val_ok else ("WARN" if val_status == "unknown" else "FAIL"),
         "Explanation Validation (TNLI)",
         val_status.upper() if val_status != "unknown" else "Not available")
    )

    # Check 6: Interactive maps present
    map_count = sum(1 for a in copied_artifacts if "map" in a.lower() and a.endswith(".html"))
    maps_ok = map_count >= 1
    checks.append(
        ("pass" if maps_ok else "WARN",
         "Interactive Maps",
         f"{map_count} map(s) bundled")
    )

    # ---- Build report --------------------------------------------------------
    all_pass = all(c[0] == "pass" for c in checks)
    some_warn = any(c[0] == "WARN" for c in checks) and not any(c[0] == "FAIL" for c in checks)

    if all_pass:
        verdict = "ALL STAGES PASSED"
        verdict_icon = "PASS"
    elif some_warn:
        verdict = "PASSED WITH WARNINGS"
        verdict_icon = "WARN"
    else:
        verdict = "SOME STAGES FAILED"
        verdict_icon = "FAIL"

    report = f"""# Speaker-B Stepwise Validation Report

**Cluster**: `{cluster_id}`
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Bundle**: `{bundle_path.name}`

---

## Verdict: [{verdict_icon}] {verdict}

---

## Validation Summary

| Status | Stage | Details |
|--------|-------|---------|
"""
    for status, stage, detail in checks:
        icon = {"pass": "PASS", "WARN": "WARN", "FAIL": "FAIL"}.get(status, "?")
        report += f"| {icon} | {stage} | {detail} |\n"

    # Key metrics
    co2_dh = econ.get("co2_dh_t_per_a", "N/A")
    co2_hp = econ.get("co2_hp_t_per_a", "N/A")

    report += f"""
---

## Key Metrics

| Metric | District Heating | Heat Pumps | Winner |
|--------|-----------------|------------|--------|
| LCOH (EUR/MWh) | {lcoh_dh:.2f} | {lcoh_hp:.2f} | {'DH' if isinstance(lcoh_dh, (int, float)) and isinstance(lcoh_hp, (int, float)) and lcoh_dh < lcoh_hp else 'HP'} |
| CO2 (t/year) | {co2_dh} | {co2_hp} | {'DH' if isinstance(co2_dh, (int, float)) and isinstance(co2_hp, (int, float)) and co2_dh < co2_hp else 'HP'} |

**Final Recommendation**: {choice}
**Robust**: {robust}
"""

    # CHA details
    cha_kpis = cha.get("kpis", cha.get("summary", {}))
    if cha_kpis:
        report += f"""
---

## CHA Details (District Heating)

| KPI | Value |
|-----|-------|
"""
        for key, val in cha_kpis.items():
            if isinstance(val, float):
                report += f"| {key} | {val:.4f} |\n"
            else:
                report += f"| {key} | {val} |\n"

    # DHA details
    dha_kpis = dha.get("kpis", dha.get("summary", {}))
    if dha_kpis:
        report += f"""
---

## DHA Details (Heat Pump Grid)

| KPI | Value |
|-----|-------|
"""
        for key, val in dha_kpis.items():
            if isinstance(val, float):
                report += f"| {key} | {val:.4f} |\n"
            else:
                report += f"| {key} | {val} |\n"

    # TNLI validation details
    if validation:
        verified = validation.get("verified_count", "?")
        total_stmts = validation.get("statements_validated", "?")
        contradictions = validation.get("contradictions", [])
        report += f"""
---

## Explanation Validation (TNLI)

- **Status**: {val_status.upper()}
- **Verified**: {verified} / {total_stmts} statements
- **Contradictions**: {len(contradictions)}
"""
        if contradictions:
            report += "\n### Contradictions Found\n\n"
            for i, c in enumerate(contradictions, 1):
                stmt = c.get("statement", str(c)) if isinstance(c, dict) else str(c)
                report += f"{i}. {stmt[:200]}\n"

    # Bundle contents
    report += f"""
---

## Bundle Contents

"""
    for artifact in sorted(copied_artifacts):
        report += f"- `{artifact}`\n"

    # Reproducibility
    report += f"""
---

## Reproducibility

This bundle contains all intermediate artifacts for stepwise validation.
Each file is prefixed with its pipeline stage number:

- `01_*` : CHA simulation outputs (network KPIs, interactive maps)
- `02_*` : DHA simulation outputs (grid KPIs, violations, map)
- `03_*` : Economics outputs (deterministic, Monte Carlo)
- `04_*` : Decision outputs (contract, decision, explanation, validation)
- `05_*` : UHDC report outputs (HTML report, explanation)
- `06_*` : KPI contract (rebuilt from current artifacts)
- `07_*` : Agent trace (orchestrator execution log)

To re-run the full pipeline:

```bash
PYTHONPATH=src python -m branitz_heat_decision.cli.validate_bundle \\
    --cluster-id {cluster_id}
```
"""

    return report


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    cluster_id: str = args.cluster_id
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_path = Path(args.output_dir) / f"validation_bundle_{cluster_id}_{timestamp}"
    bundle_path.mkdir(parents=True, exist_ok=True)

    total_steps = 7
    step_results: Dict[str, Dict[str, Any]] = {}

    print("=" * 70)
    print(f"  Branitz Validation Bundle Generator")
    print(f"  Cluster : {cluster_id}")
    print(f"  Output  : {bundle_path}")
    print("=" * 70)

    # Step 1: CHA Simulation
    _step_banner(1, total_steps, "CHA Simulation (District Heating)")
    try:
        step_results["cha"] = _run_cha(cluster_id, args.skip_existing)
    except Exception as exc:
        print(f"      -> FAILED: {exc}")
        step_results["cha"] = {"status": "error", "error": str(exc)}

    # Step 2: DHA Simulation
    _step_banner(2, total_steps, "DHA Simulation (Heat Pump Grid)")
    try:
        step_results["dha"] = _run_dha(cluster_id, args.skip_existing)
    except Exception as exc:
        print(f"      -> FAILED: {exc}")
        step_results["dha"] = {"status": "error", "error": str(exc)}

    # Step 3: Economics
    _step_banner(3, total_steps, "Economics (LCOH + CO2 + Monte Carlo)")
    try:
        step_results["economics"] = _run_economics(cluster_id, args.skip_existing)
    except Exception as exc:
        print(f"      -> FAILED: {exc}")
        step_results["economics"] = {"status": "error", "error": str(exc)}

    # Step 4: Decision
    _step_banner(4, total_steps, "Decision (Rules + Explanation + Validation)")
    try:
        step_results["decision"] = _run_decision(
            cluster_id, args.skip_existing, args.template_only,
        )
    except Exception as exc:
        print(f"      -> FAILED: {exc}")
        step_results["decision"] = {"status": "error", "error": str(exc)}

    # Step 5: Build KPI Contract
    _step_banner(5, total_steps, "KPI Contract (rebuild from artifacts)")
    try:
        kpi_contract = _build_kpi_contract(cluster_id)
        print("      -> Built successfully")
    except Exception as exc:
        print(f"      -> FAILED: {exc}")
        kpi_contract = {"error": str(exc)}

    # Step 6: Capture Agent Trace
    _step_banner(6, total_steps, "Agent Trace (orchestrator execution log)")
    agent_trace = _capture_agent_trace(cluster_id)
    if "error" in agent_trace:
        print(f"      -> Warning: {agent_trace['error']}")
    else:
        trace_len = len(agent_trace.get("agent_trace", []))
        print(f"      -> Captured {trace_len} agent steps")

    # Step 7: Assemble Bundle
    _step_banner(7, total_steps, "Assemble Bundle")
    copied = _assemble_bundle(cluster_id, bundle_path, kpi_contract, agent_trace)
    print(f"      -> {len(copied)} artifacts copied")

    # Generate validation report
    print("\n  Generating validation report...")
    report = _generate_validation_report(bundle_path, cluster_id, step_results, copied)
    report_path = bundle_path / "00_VALIDATION_REPORT.md"
    report_path.write_text(report, encoding="utf-8")

    # Save step results as metadata
    _save_json(
        {
            "cluster_id": cluster_id,
            "timestamp": timestamp,
            "step_results": step_results,
            "artifacts_copied": copied,
        },
        bundle_path / "00_bundle_metadata.json",
    )

    # Summary
    print("\n" + "=" * 70)
    print(f"  Bundle complete!")
    print(f"  Location : {bundle_path}")
    print(f"  Report   : {report_path}")
    print(f"  Artifacts: {len(copied)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
