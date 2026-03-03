import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box, shape
from shapely.ops import transform
import pyproj
from typing import Tuple, List, Dict, Any, Optional
from pydantic import ValidationError
from ..api.v1.schemas import SimulationRequest, EconomicOverrides

class ValidationEngine:
    """Strict validation with helpful, actionable error messages"""
    
    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
    
    def validate_simulation_request(self, request: SimulationRequest) -> Tuple[bool, List[Dict]]:
        """Master validation pipeline"""
        self.errors = []
        self.warnings = []
        
        # 1. Validate geometry logic
        if request.plant_location:
            self._validate_plant_in_region(request)
            self._validate_plant_on_land(request)
        
        # 2. Validate scale constraints
        self._validate_scale_realism(request)
        
        # 3. Validate economic consistency
        if request.economic_overrides:
            self._validate_economics(request.economic_overrides)
        
        # 4. Check for common misconfigurations
        self._check_common_mistakes(request)
        
        return len(self.errors) == 0, self.errors + self.warnings
    
    def _validate_plant_in_region(self, request: SimulationRequest):
        """Ensure plant is within or near the region"""
        plant = request.plant_location
        plant_point = Point(plant.lon, plant.lat)
        
        # If using bbox, strict check
        if request.region.bbox:
            min_lon, min_lat, max_lon, max_lat = request.region.bbox
            bbox = box(min_lon, min_lat, max_lon, max_lat)
            
            if not bbox.contains(plant_point):
                # Check if it's at least close (within 10% of bbox size)
                expanded_bbox = box(
                    min_lon - (max_lon-min_lon)*0.1,
                    min_lat - (max_lat-min_lat)*0.1,
                    max_lon + (max_lon-min_lon)*0.1,
                    max_lat + (max_lat-min_lat)*0.1
                )
                
                if not expanded_bbox.contains(plant_point):
                    self.errors.append({
                        "field": "plant_location",
                        "code": "PLANT_OUTSIDE_REGION",
                        "message": f"Plant location ({plant.lat}, {plant.lon}) is outside the specified region bounding box",
                        "suggestion": "Move plant location inside the bounding box or expand the bbox to include the plant",
                        "severity": "error"
                    })
                else:
                    self.warnings.append({
                        "field": "plant_location",
                        "code": "PLANT_NEAR_EDGE",
                        "message": "Plant is near the edge of the region boundary",
                        "suggestion": "Consider expanding the region to ensure all viable connections are captured",
                        "severity": "warning"
                    })
    
    def _validate_plant_on_land(self, request: SimulationRequest):
        """Basic check: plant shouldn't be in water (simplified)"""
        # In real implementation, check against water bodies layer
        # For now, just check if coordinates are reasonable
        lat, lon = request.plant_location.lat, request.plant_location.lon
        
        # Rough bounding box for Germany check (if German postal code)
        if request.region.postal_code and request.region.postal_code.startswith('0'):
            if not (47.0 <= lat <= 55.0 and 5.0 <= lon <= 15.0):
                self.errors.append({
                    "field": "plant_location",
                    "code": "COORDINATE_MISMATCH",
                    "message": f"Coordinates ({lat}, {lon}) don't appear to be in Germany",
                    "suggestion": "Verify lat/lon are not swapped. Expected format: lat (47-55), lon (5-15) for Germany",
                    "severity": "error"
                })
    
    def _validate_scale_realism(self, request: SimulationRequest):
        """Check if parameters make sense together"""
        max_dist = request.max_pipe_distance_m
        max_buildings = request.max_buildings_to_process
        
        # Density check
        area_km2 = 3.14159 * (max_dist/1000)**2
        max_density = max_buildings / area_km2
        
        if max_density > 500:  # >500 buildings/km² is very dense
            self.warnings.append({
                "field": "max_buildings_to_process",
                "code": "HIGH_DENSITY_REQUEST",
                "message": f"Requesting up to {max_buildings} buildings in {area_km2:.1f} km² ({max_density:.0f}/km²)",
                "suggestion": "This is a very dense area. Processing may take >5 minutes. Consider reducing max_buildings or increasing pipe distance.",
                "severity": "warning"
            })
        
        # Temperature consistency
        if request.plant_location:
            temp_drop = request.plant_location.supply_temperature_c - request.plant_location.return_temperature_c
            if temp_drop < 10:
                self.warnings.append({
                    "field": "plant_location.return_temperature_c",
                    "code": "LOW_TEMPERATURE_SPREAD",
                    "message": f"Temperature spread is only {temp_drop}°C (supply - return)",
                    "suggestion": "Typical district heating uses 20-40K spread. Low spread increases pumping costs.",
                    "severity": "warning"
                })
    
    def _validate_economics(self, overrides: EconomicOverrides):
        """Check economic parameters for sanity"""
        if overrides.electricity_price_eur_kwh and overrides.electricity_price_eur_kwh > 0.5:
            self.warnings.append({
                "field": "economic_overrides.electricity_price_eur_kwh",
                "code": "HIGH_ELECTRICITY_PRICE",
                "message": f"Electricity price {overrides.electricity_price_eur_kwh} €/kWh is unusually high",
                "suggestion": "Typical German industrial prices are 0.15-0.25 €/kWh. Check if value includes taxes/fees correctly.",
                "severity": "warning"
            })
    
    def _check_common_mistakes(self, request: SimulationRequest):
        """Check for frequent user errors"""
        # Check if lat/lon might be swapped (lat should be > lon for Germany)
        if request.plant_location:
            lat, lon = request.plant_location.lat, request.plant_location.lon
            if lat < lon and lat < 20 and lon > 40:  # Likely swapped
                self.errors.append({
                    "field": "plant_location",
                    "code": "COORDINATE_SWAP_SUSPECTED",
                    "message": f"Lat ({lat}) < Lon ({lon}) - possible coordinate swap",
                    "suggestion": "For Germany, Latitude should be ~47-55, Longitude ~5-15. Check if values are swapped.",
                    "severity": "error"
                })
        
        # Check unrealistic pipe distances
        if request.max_pipe_distance_m > 10000:
            self.warnings.append({
                "field": "max_pipe_distance_m",
                "code": "VERY_LONG_PIPES",
                "message": f"Pipe distance {request.max_pipe_distance_m}m exceeds 10km",
                "suggestion": "Economic viability typically drops beyond 5-8km. Ensure heat demand density justifies long pipes.",
                "severity": "warning"
            })

    def validate_uploaded_buildings(self, gdf: gpd.GeoDataFrame) -> Tuple[bool, List[Dict]]:
        """Validate uploaded GeoJSON/Shapefile"""
        errors = []
        
        # Check CRS
        if gdf.crs is None:
            errors.append({
                "field": "uploaded_file.crs",
                "code": "MISSING_CRS",
                "message": "Coordinate Reference System not defined in file",
                "suggestion": "Save file with EPSG:4326 (WGS84) or EPSG:32633 (UTM 33N) projection",
                "severity": "error"
            })
        elif not gdf.crs.to_string() in ['EPSG:4326', 'EPSG:32633']:
            errors.append({
                "field": "uploaded_file.crs",
                "code": "UNSUPPORTED_CRS",
                "message": f"CRS {gdf.crs} not supported",
                "suggestion": "Reproject to EPSG:4326 (WGS84) for web compatibility",
                "severity": "error"
            })
        
        # Check geometry validity
        invalid_geoms = gdf[~gdf.geometry.is_valid]
        if len(invalid_geoms) > 0:
            errors.append({
                "field": "uploaded_file.geometry",
                "code": "INVALID_GEOMETRIES",
                "message": f"{len(invalid_geoms)} buildings have invalid geometries",
                "suggestion": "Repair geometries using GIS software or buffer(0) operation",
                "severity": "error"
            })
        
        # Check for required columns
        required = ['geometry']
        missing = [col for col in required if col not in gdf.columns]
        if missing:
            errors.append({
                "field": "uploaded_file.columns",
                "code": "MISSING_COLUMNS",
                "message": f"Missing required columns: {missing}",
                "suggestion": "Ensure file has at minimum geometry column. Optional: usage_type, floor_area, stories",
                "severity": "error"
            })
        
        # Check for empty geometries
        empty = gdf[gdf.geometry.is_empty]
        if len(empty) > 0:
            errors.append({
                "field": "uploaded_file.geometry",
                "code": "EMPTY_GEOMETRIES",
                "message": f"{len(empty)} buildings have empty geometries",
                "suggestion": "Remove rows with empty geometries before uploading",
                "severity": "error"
            })
        
        # Size limits
        if len(gdf) > 10000:
            errors.append({
                "field": "uploaded_file.row_count",
                "code": "TOO_MANY_FEATURES",
                "message": f"File contains {len(gdf)} buildings, max allowed is 10,000",
                "suggestion": "Split into smaller areas or filter buildings by size/type first",
                "severity": "error"
            })
        
        return len(errors) == 0, errors

    def sanitize_building_data(self, gdf: gpd.GeoDataFrame) -> Tuple[gpd.GeoDataFrame, List[Dict]]:
        """Auto-fix minor issues, report what was fixed"""
        fixes = []
        
        # Convert MultiPolygon to Polygon (take largest)
        multi_mask = gdf.geometry.type == 'MultiPolygon'
        if multi_mask.any():
            gdf.loc[multi_mask, 'geometry'] = gdf[multi_mask].geometry.apply(
                lambda x: max(x.geoms, key=lambda a: a.area)
            )
            fixes.append(f"Converted {multi_mask.sum()} MultiPolygons to Polygons")
        
        # Remove Z dimension if present
        has_z = gdf.geometry.has_z.any()
        if has_z:
            gdf.geometry = gdf.geometry.apply(lambda x: Point(x.x, x.y) if isinstance(x, Point) else x)
            fixes.append("Removed Z-dimensions from coordinates")
        
        # Ensure positive floor area
        if 'floor_area' in gdf.columns:
            neg_area = gdf['floor_area'] < 0
            if neg_area.any():
                gdf.loc[neg_area, 'floor_area'] = gdf.loc[neg_area, 'floor_area'].abs()
                fixes.append(f"Fixed {neg_area.sum()} negative floor areas")
        
        return gdf, [{"message": f, "severity": "info"} for f in fixes]
