import geopandas as gpd
import pandas as pd
from typing import Dict, Any, List
from shapely.geometry import mapping, Point, LineString
import json
from datetime import datetime

class OutputStandardizer:
    """Ensures consistent GeoJSON + JSON output formats"""
    
    @staticmethod
    def create_feature_collection(features: List[Dict], properties: Dict = None) -> Dict:
        """Standard GeoJSON FeatureCollection wrapper"""
        return {
            "type": "FeatureCollection",
            "timestamp": datetime.now().isoformat(),
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
            },
            "properties": properties or {},
            "features": features
        }
    
    def standardize_network_output(self, network_gdf: gpd.GeoDataFrame, 
                                   plant_location: Dict = None) -> Dict[str, Any]:
        """
        Convert network GeoDataFrame to standardized GeoJSON
        Ensures consistent properties across all export formats
        """
        if network_gdf is None or len(network_gdf) == 0:
            return self.create_feature_collection([], {"error": "No network generated"})
        
        # Ensure required columns exist
        required_props = ['diameter_mm', 'length_m', 'material', 'flow_direction']
        for col in required_props:
            if col not in network_gdf.columns:
                network_gdf[col] = None
        
        # Convert to GeoJSON features
        features = []
        for idx, row in network_gdf.iterrows():
            geom = row.geometry
            if geom is None:
                continue
                
            feature = {
                "type": "Feature",
                "id": f"pipe_{idx}",
                "geometry": mapping(geom),
                "properties": {
                    # Identification
                    "segment_id": str(idx),
                    "segment_type": "distribution" if row.get('is_distribution') else "connection",
                    
                    # Physical properties
                    "diameter_mm": int(row['diameter_mm']) if pd.notna(row['diameter_mm']) else 100,
                    "length_m": round(float(row['length_m']), 2) if pd.notna(row['length_m']) else 0,
                    "material": row.get('material', 'steel'),
                    "flow_direction": row.get('flow_direction', 'supply'),
                    
                    # Hydraulic properties
                    "velocity_ms": round(float(row.get('velocity_ms', 0)), 3),
                    "pressure_loss_pa": round(float(row.get('pressure_loss_pa', 0)), 2),
                    "heat_loss_w": round(float(row.get('heat_loss_w', 0)), 2),
                    
                    # Thermal
                    "supply_temp_c": row.get('supply_temp_c', 80),
                    "return_temp_c": row.get('return_temp_c', 60),
                    
                    # Costs
                    "installation_cost_eur": round(float(row.get('cost_eur', 0)), 2),
                    
                    # Metadata
                    "from_node": str(row.get('from_node', '')),
                    "to_node": str(row.get('to_node', '')),
                    "status": "proposed"  # vs "existing" if retrofit
                }
            }
            features.append(feature)
        
        # Calculate bounding box
        bounds = network_gdf.total_bounds  # [minx, miny, maxx, maxy]
        
        return self.create_feature_collection(
            features,
            properties={
                "network_type": "district_heating",
                "total_segments": len(features),
                "total_length_m": round(network_gdf['length_m'].sum(), 2),
                "bounds": {
                    "west": bounds[0], "south": bounds[1],
                    "east": bounds[2], "north": bounds[3]
                },
                "plant_location": plant_location
            }
        )
    
    def standardize_clusters_output(self, clusters_gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Standardize cluster results"""
        features = []
        
        for idx, row in clusters_gdf.iterrows():
            centroid = row.geometry.centroid if hasattr(row.geometry, 'centroid') else row.geometry
            
            feature = {
                "type": "Feature",
                "id": f"cluster_{row.get('cluster_id', idx)}",
                "geometry": mapping(centroid),
                "properties": {
                    "cluster_id": int(row.get('cluster_id', idx)),
                    "building_count": int(row.get('building_count', 0)),
                    "total_heat_demand_kw": round(float(row.get('total_heat_demand_kw', 0)), 2),
                    "specific_demand_kwh_m2a": round(float(row.get('specific_demand_kwh_m2a', 0)), 2),
                    "suggested_diameter_mm": int(row.get('suggested_pipe_diameter_mm', 100)),
                    "connection_viable": bool(row.get('connection_viable', True)),
                    "distance_to_plant_m": round(float(row.get('connection_distance_m', 0)), 2)
                }
            }
            features.append(feature)
        
        return self.create_feature_collection(
            features,
            properties={"cluster_count": len(features)}
        )
    
    def standardize_buildings_output(self, buildings_gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Standardize input buildings with calculated properties"""
        features = []
        
        for idx, row in buildings_gdf.iterrows():
            feature = {
                "type": "Feature",
                "id": f"bldg_{idx}",
                "geometry": mapping(row.geometry),
                "properties": {
                    "building_id": str(idx),
                    "usage_type": row.get('usage_type', 'unknown'),
                    "floor_area_m2": round(float(row.get('floor_area_m2', 0)), 2),
                    "heat_demand_kwh": round(float(row.get('heat_demand_kwh', 0)), 2),
                    "stories": int(row.get('stories', 1)),
                    "cluster_id": int(row.get('cluster_id', -1)),
                    "connected": bool(row.get('connected', False)),
                    "distance_to_network_m": round(float(row.get('distance_to_network_m', -1)), 2)
                }
            }
            features.append(feature)
        
        return self.create_feature_collection(
            features,
            properties={"building_count": len(features)}
        )
    
    def create_standardized_result(self, 
                                   request_id: str,
                                   metadata: Dict,
                                   clusters: List[Dict],
                                   network_gdf: gpd.GeoDataFrame,
                                   economics: Dict,
                                   environment: Dict,
                                   buildings_gdf: gpd.GeoDataFrame = None,
                                   plant_location: Dict = None) -> Dict[str, Any]:
        """Assemble complete standardized result"""
        
        result = {
            "success": True,
            "request_id": request_id,
            "status": "completed",
            "metadata": {
                "request_id": request_id,
                "timestamp_start": metadata.get('start_time'),
                "timestamp_end": datetime.now().isoformat(),
                "processing_time_seconds": metadata.get('duration_seconds'),
                "version": "2.0.0",
                "city_config_used": metadata.get('city_config', 'default'),
                "data_source": metadata.get('data_source', 'unknown'),
                "buildings_processed": metadata.get('n_buildings', 0),
                "buildings_excluded": metadata.get('excluded', 0),
                "exclusion_reasons": metadata.get('exclusion_reasons', {})
            },
            "clusters": clusters,
            "network": {
                "total_pipe_length_m": round(network_gdf['length_m'].sum(), 2) if network_gdf is not None else 0,
                "supply_line_length_m": round(network_gdf[network_gdf['flow_direction']=='supply']['length_m'].sum(), 2) if network_gdf is not None else 0,
                "return_line_length_m": round(network_gdf[network_gdf['flow_direction']=='return']['length_m'].sum(), 2) if network_gdf is not None else 0,
                "total_heat_loss_kw": round(network_gdf['heat_loss_w'].sum() / 1000, 3) if network_gdf is not None else 0,
                "max_pipe_diameter_mm": int(network_gdf['diameter_mm'].max()) if network_gdf is not None else 0,
                "min_pipe_diameter_mm": int(network_gdf['diameter_mm'].min()) if network_gdf is not None else 0,
                "number_of_heat_exchangers": len(clusters)
            },
            "economics": economics,
            "environment": environment,
            "network_geojson": self.standardize_network_output(network_gdf, plant_location),
            "clusters_geojson": self.standardize_clusters_output(self._clusters_to_gdf(clusters)),
        }
        
        if buildings_gdf is not None:
            result["buildings_geojson"] = self.standardize_buildings_output(buildings_gdf)
        
        return result
    
    def _clusters_to_gdf(self, clusters: List[Dict]) -> gpd.GeoDataFrame:
        """Convert cluster dicts to GeoDataFrame for standardization"""
        if not clusters:
            return gpd.GeoDataFrame()
        
        geometries = [Point(c['centroid_lon'], c['centroid_lat']) for c in clusters]
        gdf = gpd.GeoDataFrame(clusters, geometry=geometries, crs="EPSG:4326")
        return gdf
