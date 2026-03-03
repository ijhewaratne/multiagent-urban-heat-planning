import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point
from typing import Dict, Any, Tuple, Optional
from .base import DataAdapter, BuildingData, NetworkConstraints
import requests
import pandas as pd

class RegionAdapter(DataAdapter):
    """Adapter for city, postal code, or province-level extraction"""
    
    def validate_source(self, source: Dict[str, Any]) -> Tuple[bool, str]:
        # Accept postal_code, city_name, or bbox
        if not any(k in source for k in ['postal_code', 'city', 'bbox', 'place_name']):
            return False, "Must provide postal_code, city, place_name, or bbox"
        
        if 'plant_location' in source:
            plant = source['plant_location']
            if 'lat' not in plant or 'lon' not in plant:
                return False, "Plant location must include lat and lon"
        
        return True, "Valid"
    
    def resolve_location(self, source: Dict[str, Any]) -> Tuple[float, float, float, gpd.GeoDataFrame]:
        """
        Returns: (center_lat, center_lon, radius_meters, boundary_gdf)
        """
        # Use Nominatim for geocoding (or your preferred service)
        if 'postal_code' in source:
            query = f"{source['postal_code']}, {source.get('country', 'Germany')}"
        elif 'city' in source:
            query = source['city']
        else:
            query = source['place_name']
        
        # Get bounding box from Nominatim
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': query,
            'format': 'geojson',
            'limit': 1,
            'polygon_geojson': 1
        }
        headers = {'User-Agent': 'BranitzHeatPlanning/2.0'}
        
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        if not data['features']:
            raise ValueError(f"Location not found: {query}")
        
        feature = data['features'][0]
        bbox = feature['bbox']  # [min_lon, min_lat, max_lon, max_lat]
        geometry = feature['geometry']
        
        # Calculate radius from bbox diagonal
        from shapely.geometry import box
        bounds = box(bbox[0], bbox[1], bbox[2], bbox[3])
        center = bounds.centroid
        radius = bounds.bounds[2] - bounds.bounds[0]  # Approximate width in degrees
        radius_meters = radius * 111000  # Rough conversion to meters
        
        # Create boundary GeoDataFrame
        boundary_gdf = gpd.GeoDataFrame(
            {'name': [query], 'geometry': [bounds]},
            crs="EPSG:4326"
        )
        
        return center.y, center.x, radius_meters, boundary_gdf
    
    def load_buildings(self, source: Dict[str, Any]) -> BuildingData:
        """Extract all buildings within region, optionally filtered by plant distance"""
        center_lat, center_lon, radius_m, boundary_gdf = self.resolve_location(source)
        
        # If plant location specified, filter by max distance
        if 'plant_location' in source:
            plant_lat = source['plant_location']['lat']
            plant_lon = source['plant_location']['lon']
            max_dist = source.get('max_pipe_distance_m', 5000)  # Default 5km economic radius
            
            # Create search radius around plant, not region center
            search_point = Point(plant_lon, plant_lat)
            search_gdf = gpd.GeoDataFrame({'geometry': [search_point]}, crs="EPSG:4326")
            search_gdf = search_gdf.to_crs(epsg=3857)  # Web Mercator for meters
            search_buffer = search_gdf.buffer(max_dist).to_crs(epsg=4326)
            
            # Use OSMnx with polygon
            tags = {'building': True}
            try:
                gdf = ox.features_from_polygon(search_buffer.iloc[0], tags=tags)
            except Exception as e:
                # Fallback to bounding box if polygon too complex
                gdf = ox.features_from_point((plant_lat, plant_lon), tags=tags, dist=max_dist)
        else:
            # Original region-based extraction
            tags = {'building': True}
            gdf = ox.features_from_point((center_lat, center_lon), tags=tags, dist=radius_m)
        
        # Filter to polygons and validate
        gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        
        # If plant exists, calculate distance from plant for each building
        if 'plant_location' in source:
            plant_point = Point(plant_lon, plant_lat)
            gdf['distance_to_plant_m'] = gdf.geometry.centroid.apply(
                lambda x: self._haversine_distance(x.y, x.x, plant_lat, plant_lon)
            )
            # Sort by distance for prioritization
            gdf = gdf.sort_values('distance_to_plant_m')
        
        gdf = self.normalize_buildings(gdf)
        
        metadata = {
            'center': {'lat': center_lat, 'lon': center_lon},
            'search_radius_m': radius_m if 'plant_location' not in source else max_dist,
            'n_buildings': len(gdf),
            'plant_location': source.get('plant_location'),
            'extraction_date': pd.Timestamp.now().isoformat()
        }
        
        return BuildingData(
            gdf=gdf,
            crs="EPSG:4326",
            source_type="region",
            metadata=metadata
        )
    
    def load_network_constraints(self, source: Dict[str, Any]) -> NetworkConstraints:
        """Load street network for the region"""
        if 'plant_location' in source:
            # Get network around plant
            lat = source['plant_location']['lat']
            lon = source['plant_location']['lon']
            dist = source.get('max_pipe_distance_m', 5000)
            G = ox.graph_from_point((lat, lon), dist=dist, network_type='drive')
        else:
            # Region-wide network
            center_lat, center_lon, radius_m, _ = self.resolve_location(source)
            G = ox.graph_from_point((center_lat, center_lon), dist=radius_m, network_type='drive')
        
        nodes, edges = ox.graph_to_gdfs(G)
        return NetworkConstraints(roads=edges, existing_grid=None)
    
    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two points"""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371000  # Earth radius in meters
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
