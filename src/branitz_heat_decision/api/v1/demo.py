from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import geopandas as gpd
import json
from pathlib import Path

router = APIRouter()

DEMO_DIR = Path("data/demo")

@router.get("/demo/status")
async def demo_status():
    """Check if demo data is available"""
    buildings_file = DEMO_DIR / "cottbus_demo_buildings.geojson"
    return {
        "available": buildings_file.exists(),
        "buildings_count": 200 if buildings_file.exists() else 0,
        "description": "Sample dataset: 200 buildings in Cottbus center"
    }

@router.post("/demo/run")
async def run_demo_simulation():
    """Run quick demo simulation (~10s)"""
    buildings_file = DEMO_DIR / "cottbus_demo_buildings.geojson"
    plant_file = DEMO_DIR / "demo_plant.json"
    
    if not buildings_file.exists():
        raise HTTPException(404, "Demo data not generated. Run 'python scripts/generate_demo_data.py'")
    
    # Load demo data
    gdf = gpd.read_file(buildings_file)
    with open(plant_file) as f:
        plant = json.load(f)
    
    # Mock processing for demo speed
    return {
        "success": True,
        "demo": True,
        "message": "Demo simulation completed (mock data)",
        "summary": {
            "buildings_analyzed": len(gdf),
            "total_heat_demand_mwh": round(gdf['heat_demand_kwh'].sum() / 1000, 1),
            "clusters_identified": 5,
            "network_length_m": 3200,
            "lcoh_eur_mwh": 82.50,
            "co2_savings_tons": 450
        },
        "plant_location": plant,
        "preview_url": "/demo/download/network"
    }

@router.get("/demo/download/{file_type}")
async def download_demo_result(file_type: str):
    """Download demo result files"""
    if file_type == "buildings":
        return FileResponse(DEMO_DIR / "cottbus_demo_buildings.geojson", 
                          media_type="application/geo+json",
                          filename="demo_buildings.geojson")
    elif file_type == "plant":
        return FileResponse(DEMO_DIR / "demo_plant.json",
                          media_type="application/json",
                          filename="plant_config.json")
    else:
        raise HTTPException(404, "File not found")
