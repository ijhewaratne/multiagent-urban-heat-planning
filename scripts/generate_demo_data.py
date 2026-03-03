#!/usr/bin/env python3
"""
Generate sample data for demo instance
Creates mock building data for Cottbus center
"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
import numpy as np
import json
import os

def generate_cottbus_demo():
    """Generate ~200 buildings around Cottbus center"""
    np.random.seed(42)
    
    # Cottbus center coordinates
    center_lon, center_lat = 14.3329, 51.7563
    
    # Generate grid of buildings
    n_buildings = 200
    x_offset = np.random.normal(0, 0.01, n_buildings)  # ~1km spread
    y_offset = np.random.normal(0, 0.008, n_buildings)
    
    geometries = []
    properties = []
    
    for i in range(n_buildings):
        lon = center_lon + x_offset[i]
        lat = center_lat + y_offset[i]
        
        # Create building footprint (20x20m avg)
        size = np.random.uniform(0.0001, 0.0003)
        footprint = Polygon([
            (lon, lat),
            (lon + size, lat),
            (lon + size, lat + size*0.8),
            (lon, lat + size*0.8)
        ])
        geometries.append(footprint)
        
        # Random properties
        usage = np.random.choice(
            ['residential', 'commercial', 'school'], 
            p=[0.7, 0.25, 0.05]
        )
        stories = int(np.random.choice([1, 2, 3, 4, 5], p=[0.1, 0.3, 0.4, 0.15, 0.05]))
        floor_area = footprint.area * (111320**2) * stories  # Convert to m2
        
        # Heat demand based on type
        specific = {'residential': 120, 'commercial': 150, 'school': 130}[usage]
        heat_demand = floor_area * specific
        
        properties.append({
            'building_id': f'DEMO_{i:03d}',
            'usage_type': usage,
            'stories': stories,
            'floor_area_m2': round(floor_area, 1),
            'year_built': int(np.random.uniform(1950, 2020)),
            'heat_demand_kwh': round(heat_demand, 0),
            'street_name': f"Demo Street {i//20 + 1}",
            'house_number': str(i % 20 + 1)
        })
    
    gdf = gpd.GeoDataFrame(properties, geometry=geometries, crs="EPSG:4326")
    
    # Save as GeoJSON
    output_dir = "data/demo"
    os.makedirs(output_dir, exist_ok=True)
    
    gdf.to_file(f"{output_dir}/cottbus_demo_buildings.geojson", driver="GeoJSON")
    
    # Generate plant location
    plant = {
        "name": "Cottbus Demo CHP",
        "lat": center_lat + 0.002,
        "lon": center_lon + 0.001,
        "capacity_kw": 5000,
        "supply_temp_c": 80,
        "return_temp_c": 60
    }
    
    with open(f"{output_dir}/demo_plant.json", "w") as f:
        json.dump(plant, f, indent=2)
    
    print(f"Generated {n_buildings} demo buildings")
    print(f"Total heat demand: {gdf['heat_demand_kwh'].sum()/1000:.1f} MWh/a")
    print(f"Saved to {output_dir}/")

if __name__ == "__main__":
    generate_cottbus_demo()
