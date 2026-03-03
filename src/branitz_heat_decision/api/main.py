from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from typing import Dict
from pathlib import Path

from ..config.loader import config_manager
from .middleware import validation_exception_handler
from .v1.endpoints import router as v1_router
from ..adapters.region_adapter import RegionAdapter

app = FastAPI(
    title="Branitz Heat Planning API",
    description="Multi-agent urban heat network planning engine - Standardized",
    version="2.0.0"
)

# CORS for Fraunhofer web integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, validation_exception_handler)

# Routers
app.include_router(v1_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/orchestration"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "available_cities": list(config_manager.load_app_config().cities.keys())
    }

@app.post("/geocode")
async def geocode_location(query: str):
    """Convert postal code or address to lat/lon with boundary"""
    adapter = RegionAdapter()
    center_lat, center_lon, radius, boundary = adapter.resolve_location({'place_name': query})
    return {
        "center": {"lat": center_lat, "lon": center_lon},
        "radius_m": radius,
        "boundary_geojson": boundary.__geo_interface__
    }

@app.post("/validate-plant-location")
async def validate_plant_location(lat: float, lon: float, postal_code: str):
    """Check if plant location is within reasonable distance of buildings"""
    # Quick check: are there buildings within 5km?
    adapter = RegionAdapter()
    test_data = adapter.load_buildings({
        'postal_code': postal_code,
        'plant_location': {'lat': lat, 'lon': lon},
        'max_pipe_distance_m': 5000
    })
    
    return {
        "buildings_in_radius": len(test_data.gdf),
        "estimated_connection_potential": "high" if len(test_data.gdf) > 50 else "low",
        "recommended_max_distance": min(5000, max(1000, len(test_data.gdf) * 50))  # Dynamic suggestion
    }
