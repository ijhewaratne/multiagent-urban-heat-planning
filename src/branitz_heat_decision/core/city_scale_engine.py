import geopandas as gpd
import numpy as np
from typing import List, Dict, Generator
from shapely.geometry import box, Point
from ..config.schemas import CityConfig
from ..adapters.base import BuildingData

class CityScaleEngine:
    """Handles large-scale processing with progress tracking"""
    
    def __init__(self, city_config: CityConfig):
        self.config = city_config
        self.chunk_size = 100  # Process 100 buildings at a time
    
    def generate_chunks(self, building_data: BuildingData) -> Generator[gpd.GeoDataFrame, None, None]:
        """Split large dataset into manageable chunks"""
        gdf = building_data.gdf
        
        # If plant location exists, process in rings (closest first)
        if 'distance_to_plant_m' in gdf.columns:
            # Sort by distance already done in adapter
            for i in range(0, len(gdf), self.chunk_size):
                yield gdf.iloc[i:i+self.chunk_size]
        else:
            # Spatial tiling for city-wide without plant
            total_bounds = gdf.total_bounds
            n_tiles = int(np.ceil(len(gdf) / self.chunk_size))
            side = int(np.ceil(np.sqrt(n_tiles)))
            
            x_coords = np.linspace(total_bounds[0], total_bounds[2], side+1)
            y_coords = np.linspace(total_bounds[1], total_bounds[3], side+1)
            
            for i in range(side):
                for j in range(side):
                    tile_box = box(x_coords[i], y_coords[j], x_coords[i+1], y_coords[j+1])
                    chunk = gdf[gdf.geometry.centroid.intersects(tile_box)]
                    if len(chunk) > 0:
                        yield chunk
    
    def run(self, building_data: BuildingData, plant_location: Dict = None) -> Dict:
        """
        Orchestrate large-scale simulation
        Returns incremental results suitable for progress tracking
        """
        all_clusters = []
        total_pipe_length = 0
        
        # Phase 1: Clustering (incremental)
        for idx, chunk in enumerate(self.generate_chunks(building_data)):
            chunk_clusters = self.cluster_chunk(chunk, plant_location)
            all_clusters.extend(chunk_clusters)
            
            # Progress would be reported here: (idx+1) * 100 / n_chunks
        
        # Phase 2: Network optimization (plant-centric if plant exists)
        if plant_location:
            network = self.optimize_radial_network(all_clusters, plant_location)
        else:
            network = self.optimize_district_network(all_clusters)
        
        # Phase 3: Economics at scale
        economics = self.calculate_city_scale_economics(network, building_data)
        
        return {
            'clusters': all_clusters,
            'network': network,
            'economics': economics,
            'plant_location': plant_location,
            'total_buildings_processed': len(building_data.gdf)
        }
    
    def cluster_chunk(self, chunk: gpd.GeoDataFrame, plant_location: Dict) -> List[Dict]:
        """Cluster buildings within chunk"""
        # Your existing clustering logic, adapted for smaller chunks
        # This prevents memory issues with 10,000+ buildings
        return []
    
    def optimize_radial_network(self, clusters: List[Dict], plant_location: Dict) -> gpd.GeoDataFrame:
        """
        Create radial network from plant to clusters
        Uses Steiner tree approximation for minimal piping
        """
        plant_point = Point(plant_location['lon'], plant_location['lat'])
        
        # Connect clusters to plant via shortest path along roads
        # Or straight-line if no road constraints
        return gpd.GeoDataFrame()
        
    def optimize_district_network(self, clusters: List[Dict]) -> gpd.GeoDataFrame:
         return gpd.GeoDataFrame()
         
    def calculate_city_scale_economics(self, network: gpd.GeoDataFrame, building_data: BuildingData) -> Dict:
        return {}
