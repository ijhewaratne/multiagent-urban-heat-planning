"""
Scenario resolution for economics + decision runs.

A *scenario* is a YAML file of ``EconomicParameters`` overrides
(see ``scripts/scenarios/*.yaml``, e.g. ``2023_baseline``, ``2030_optimistic``).

Scenarios can be referenced by:
  - bare name:      ``--scenario 2030_optimistic``
  - explicit path:  ``--scenario /path/to/my_scenario.yaml``

Scenario-specific outputs are namespaced under
``results/economics/<cluster_id>/scenarios/<scenario_name>/`` and
``results/decision/<cluster_id>/scenarios/<scenario_name>/`` so that
baseline (no-scenario) results are never overwritten.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from .params import EconomicParameters, load_params_from_yaml

#: Default directory containing scenario YAML files (repo: ``scripts/scenarios/``).
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENARIOS_DIR = _REPO_ROOT / "scripts" / "scenarios"


def get_scenarios_dir() -> Path:
    """Scenario directory (override with env BRANITZ_SCENARIOS_DIR)."""
    env = os.getenv("BRANITZ_SCENARIOS_DIR")
    return Path(env) if env else DEFAULT_SCENARIOS_DIR


def list_scenarios() -> List[str]:
    """Names of all available scenario YAML files."""
    d = get_scenarios_dir()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def resolve_scenario_path(scenario: str) -> Path:
    """Resolve a scenario name or path to an existing YAML file.

    Raises:
        FileNotFoundError: if the scenario cannot be found.
    """
    p = Path(scenario)
    if p.suffix in (".yaml", ".yml") and p.exists():
        return p
    candidate = get_scenarios_dir() / f"{scenario}.yaml"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"Scenario '{scenario}' not found. Looked for {candidate}. "
        f"Available: {list_scenarios()}"
    )


def scenario_name(scenario: str) -> str:
    """Canonical scenario name (file stem) from a name or path."""
    return Path(scenario).stem


def load_scenario_params(scenario: str) -> EconomicParameters:
    """Load ``EconomicParameters`` for a scenario name or YAML path."""
    return load_params_from_yaml(str(resolve_scenario_path(scenario)))


def scenario_results_subdir(base_dir: Path, scenario: Optional[str]) -> Path:
    """Return *base_dir* or its scenario-namespaced subdirectory."""
    if not scenario:
        return base_dir
    return base_dir / "scenarios" / scenario_name(scenario)
