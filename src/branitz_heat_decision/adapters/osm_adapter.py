import osmnx as ox
import geopandas as gpd
from typing import Dict, Any, Tuple
from .base import DataAdapter, BuildingData, NetworkConstraints
import pandas as pd

class OSMAdapter(DataAdapter):
    """Adapter for OpenStreetMap data extraction"""
    
    def validate_source(self, source: Dict[str, Any]) -> Tuple[bool, str]:
        required = ['location', 'distance_meters']
        for key in required:
            if key not in source:
                return False, f"Missing required key: {key}"
        return True, "Valid"
    
    def load_buildings(self, source: Dict[str, Any]) -> BuildingData:
        """Extract buildings from OSM"""
        location = source['location']  # e.g., "Heinrich-Zille-Straße, Cottbus"
        dist = source.get('distance_meters', 1000)
        
        # Your existing OSM extraction logic
        tags = {'building': True}
        gdf = ox.features_from_place(location, tags=tags, dist=dist)
        
        # Filter to actual building polygons
        gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        
        # Normalize to standard schema
        gdf = self.normalize_buildings(gdf)
        
        return BuildingData(
            gdf=gdf,
            crs=str(gdf.crs),
            source_type="osm",
            metadata={
                'location': location,
                'n_buildings': len(gdf),
                'extraction_date': pd.Timestamp.now().isoformat()
            }
        )
    
    def load_network_constraints(self, source: Dict[str, Any]) -> NetworkConstraints:
        """Extract street network from OSM"""
        location = source['location']
        dist = source.get('distance_meters', 1000)
        
        # Get street network
        G = ox.graph_from_place(location, dist=dist, network_type='drive')
        nodes, edges = ox.graph_to_gdfs(G)
        
        return NetworkConstraints(
            roads=edges,
            existing_grid=None  # OSM doesn't have DH grid typically
        )

class GeoJSONAdapter(DataAdapter):
    """Adapter for uploaded GeoJSON/Shapefile data"""
    
    def validate_source(self, source: Dict[str, Any]) -> Tuple[bool, str]:
        if 'file_path' not in source and 'geojson_dict' not in source:
            return False, "Must provide file_path or geojson_dict"
        return True, "Valid"
    
    def load_buildings(self, source: Dict[str, Any]) -> BuildingData:
        if 'file_path' in source:
            gdf = gpd.read_file(source['file_path'])
        else:
            gdf = gpd.GeoDataFrame.from_features(
                source['geojson_dict']['features'],
                crs=source.get('crs', 'EPSG:4326')
            )
        
        gdf = self.normalize_buildings(gdf)
        
        return BuildingData(
            gdf=gdf,
            crs=str(gdf.crs),
            source_type="geojson",
            metadata={'file_name': source.get('file_path', 'inline')}
        )
    
    def load_network_constraints(self, source: Dict[str, Any]) -> NetworkConstraints:
        # Optional separate files for roads/grid
        roads = None
        if 'roads_file' in source:
            roads = gpd.read_file(source['roads_file'])
        
        return NetworkConstraints(roads=roads)
