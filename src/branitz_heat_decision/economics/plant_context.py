"""
Dynamic Plant Context — Singleton Cottbus CHP shared across all streets.

The same plant serves the entire district; marginal cost allocation
ensures each street pays only for capacity expansion (if any), not the sunk plant cost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CottbusCHPContext:
    """
    Singleton context for Cottbus CHP plant.
    Shared across ALL streets — same plant serves entire district.
    """

    # Plant specifications aligned to HKW Cottbus modernization context
    total_capacity_kw_th: float = 170_000  # ~170 MW thermal site capacity
    utilized_capacity_kw_th: float = 85_000  # ~50% utilized baseline load
    total_cost_eur: float = 90_000_000  # Midpoint of 75-100M€ modernization estimate
    is_built: bool = True  # Existing/operating asset
    marginal_cost_per_kw: float = 700.0  # Midpoint of 600-800 €/kW expansion estimate
    fuel_type: str = "natural_gas"
    # Fixed plant location (WGS84) for consistent geospatial references
    plant_wgs84_lat: float = 51.758
    plant_wgs84_lon: float = 14.364

    @property
    def available_capacity_kw(self) -> float:
        """Spare capacity available for new street connections."""
        return self.total_capacity_kw_th - self.utilized_capacity_kw_th

    def can_accommodate(self, street_peak_kw: float, safety_factor: float = 1.2) -> bool:
        """Check if street can be served without plant expansion."""
        required = street_peak_kw * safety_factor
        return required <= self.available_capacity_kw


# Generic alias — the dataclass models any district heat plant, not just Cottbus
DistrictPlantContext = CottbusCHPContext

# Default instance (Cottbus CHP / Branitz case study)
COTTBUS_CHP = CottbusCHPContext()

# Active plant context (module-level cache, set via config or default)
_ACTIVE_PLANT: Optional[CottbusCHPContext] = None


def load_plant_context(path: "str | Path") -> CottbusCHPContext:
    """
    Load a plant context from a JSON or YAML config file.

    Expected keys (all optional; defaults = Cottbus CHP):
      total_capacity_kw_th, utilized_capacity_kw_th, total_cost_eur,
      is_built, marginal_cost_per_kw, fuel_type,
      plant_wgs84_lat, plant_wgs84_lon
    """
    import json
    from pathlib import Path as _P

    p = _P(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text)
    valid = {f for f in CottbusCHPContext.__dataclass_fields__}
    unknown = set(data) - valid
    if unknown:
        raise ValueError(f"Unknown plant context keys in {p}: {sorted(unknown)}")
    ctx = CottbusCHPContext(**data)
    logger.info("Loaded plant context from %s: %.0f kW_th, fuel=%s",
                p, ctx.total_capacity_kw_th, ctx.fuel_type)
    return ctx


def get_plant_context() -> CottbusCHPContext:
    """
    Active plant context.

    Resolution order:
      1. Path in env var BRANITZ_PLANT_CONTEXT (JSON/YAML) — for other districts
      2. Default Cottbus CHP (Branitz case study)
    """
    global _ACTIVE_PLANT
    if _ACTIVE_PLANT is None:
        import os

        cfg = os.getenv("BRANITZ_PLANT_CONTEXT")
        _ACTIVE_PLANT = load_plant_context(cfg) if cfg else COTTBUS_CHP
    return _ACTIVE_PLANT


def set_plant_context(ctx: Optional[CottbusCHPContext]) -> None:
    """Override the active plant context programmatically (None resets to default)."""
    global _ACTIVE_PLANT
    _ACTIVE_PLANT = ctx


def get_plant_context_for_street(
    street_peak_load_kw: float,
) -> Dict[str, Any]:
    """
    Get plant allocation for ANY street dynamically.

    Returns marginal allocation (0€) if capacity available,
    or expansion cost if constrained.
    """
    from .lcoh import PlantContext

    # Use the active district plant context (configurable via BRANITZ_PLANT_CONTEXT)
    plant = get_plant_context()
    plant_ctx = PlantContext(
        total_capacity_kw=plant.total_capacity_kw_th,
        total_cost_eur=plant.total_cost_eur,
        utilized_capacity_kw=plant.utilized_capacity_kw_th,
        is_built=plant.is_built,
        marginal_cost_per_kw=plant.marginal_cost_per_kw,
    )

    # Check if this specific street triggers expansion
    allocation = plant_ctx.get_marginal_allocation(street_peak_load_kw)

    logger.info(
        "Street %.1f kW: %s (Spare: %.0f kW)",
        street_peak_load_kw,
        allocation.get("rationale", ""),
        plant.available_capacity_kw,
    )

    return {
        "context": plant_ctx,
        "allocation": allocation,
        "is_within_capacity": plant.can_accommodate(street_peak_load_kw),
    }
