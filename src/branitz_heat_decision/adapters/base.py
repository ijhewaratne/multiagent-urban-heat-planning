from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
import geopandas as gpd
import pandas as pd
from pydantic import BaseModel

class BuildingData(BaseModel):
    """Standardized building data container"""
    gdf: gpd.GeoDataFrame
    crs: str
    source_type: str
    metadata: Dict[str, Any]
    
    class Config:
        arbitrary_types_allowed = True

class NetworkConstraints(BaseModel):
    """Roads, rivers, existing infrastructure"""
    roads: Optional[gpd.GeoDataFrame] = None
    water_bodies: Optional[gpd.GeoDataFrame] = None
    existing_grid: Optional[gpd.GeoDataFrame] = None
    
    class Config:
        arbitrary_types_allowed = True

class DataAdapter(ABC):
    """Abstract base for all data sources"""
    
    @abstractmethod
    def load_buildings(self, source: Dict[str, Any]) -> BuildingData:
        """Load and standardize building footprints and attributes"""
        pass
    
    @abstractmethod
    def load_network_constraints(self, source: Dict[str, Any]) -> NetworkConstraints:
        """Load street network and constraints"""
        pass
    
    @abstractmethod
    def validate_source(self, source: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate input source configuration"""
        pass
    
    def normalize_buildings(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Standardize column names and schema"""
        column_mapping = {
            'building': 'usage_type',
            'height': 'building_height',
            'levels': 'stories',
            'addr:street': 'street_name',
            'addr:housenumber': 'house_number'
        }
        
        # Rename columns if they exist
        for old, new in column_mapping.items():
            if old in gdf.columns:
                gdf = gdf.rename(columns={old: new})
        
        # Ensure required columns exist
        required = ['geometry', 'usage_type']
        for col in required:
            if col not in gdf.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Calculate derived fields if missing
        if 'floor_area_m2' not in gdf.columns:
            if 'stories' in gdf.columns:
                gdf['floor_area_m2'] = gdf.geometry.area * gdf['stories'].astype(float)
            else:
                gdf['floor_area_m2'] = gdf.geometry.area * 3  # Default 3 stories
        
        if 'heat_demand_kwh' not in gdf.columns:
            # Use default specific heat demand if not provided
            gdf['heat_demand_kwh'] = gdf['floor_area_m2'] * 100  # 100 kWh/m2a default
            
        return gdf
