from typing import Dict, Type
from .base import DataAdapter
from .osm_adapter import OSMAdapter, GeoJSONAdapter
from .region_adapter import RegionAdapter

ADAPTER_REGISTRY: Dict[str, Type[DataAdapter]] = {
    'osm': OSMAdapter,
    'geojson': GeoJSONAdapter,
    'shapefile': GeoJSONAdapter,  # Uses same logic
    # Add 'fraunhofer': FraunhoferAdapter later
    'postal_code': RegionAdapter,
    'city': RegionAdapter,
    'region': RegionAdapter
}

def get_adapter(source_type: str) -> DataAdapter:
    if source_type not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter type: {source_type}. Available: {list(ADAPTER_REGISTRY.keys())}")
    return ADAPTER_REGISTRY[source_type]()
