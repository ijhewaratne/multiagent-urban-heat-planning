"""
Dynamic Plant Context — Singleton Cottbus CHP shared across all streets.

The same plant serves the entire district; marginal cost allocation
ensures each street pays only for capacity expansion (if any), not the sunk plant cost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
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


# Singleton instance — used across entire application
COTTBUS_CHP = CottbusCHPContext()


def get_plant_context_for_street(
    street_peak_load_kw: float,
) -> Dict[str, Any]:
    """
    Get plant allocation for ANY street dynamically.

    Returns marginal allocation (0€) if capacity available,
    or expansion cost if constrained.
    """
    from .lcoh import PlantContext

    # Always use the same Cottbus CHP context
    plant_ctx = PlantContext(
        total_capacity_kw=COTTBUS_CHP.total_capacity_kw_th,
        total_cost_eur=COTTBUS_CHP.total_cost_eur,
        utilized_capacity_kw=COTTBUS_CHP.utilized_capacity_kw_th,
        is_built=COTTBUS_CHP.is_built,
        marginal_cost_per_kw=COTTBUS_CHP.marginal_cost_per_kw,
    )

    # Check if this specific street triggers expansion
    allocation = plant_ctx.get_marginal_allocation(street_peak_load_kw)

    logger.info(
        "Street %.1f kW: %s (Spare: %.0f kW)",
        street_peak_load_kw,
        allocation.get("rationale", ""),
        COTTBUS_CHP.available_capacity_kw,
    )

    return {
        "context": plant_ctx,
        "allocation": allocation,
        "is_within_capacity": COTTBUS_CHP.can_accommodate(street_peak_load_kw),
    }
