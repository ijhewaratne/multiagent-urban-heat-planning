from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict
import time
from datetime import datetime

from .schemas import SimulationRequest, SimulationResult, ErrorResponse, SimulationStatus
from ...core.validation_engine import ValidationEngine
from ...core.output_standardizer import OutputStandardizer
from ...core.simulation_engine import SimulationEngine
from ...adapters import get_adapter
from shapely.geometry import LineString
import geopandas as gpd

router = APIRouter()
validator = ValidationEngine()
standardizer = OutputStandardizer()

# In-memory store (replace with Redis in production)
simulation_jobs: Dict[str, Dict] = {}

@router.post("/simulate", response_model=SimulationResult, 
             responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})
async def run_simulation(request: SimulationRequest, background_tasks: BackgroundTasks):
    """
    Run heat network simulation with strict validation
    """
    job_id = request.request_id
    
    # Phase 1: Schema validation (handled by Pydantic)
    
    # Phase 2: Business logic validation
    is_valid, issues = validator.validate_simulation_request(request)
    
    if not is_valid:
        errors = [e for e in issues if e.get('severity') == 'error']
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                request_id=job_id,
                timestamp=datetime.now().isoformat(),
                code="VALIDATION_ERROR",
                message=f"Simulation request failed validation with {len(errors)} errors",
                details=[{"field": e["field"], "message": e["message"], "type": e["code"]} for e in errors],
                suggestion="Review the error details and adjust request parameters accordingly"
            ).dict()
        )
    
    # Log warnings
    warnings = [w for w in issues if w.get('severity') == 'warning']
    
    # Initialize job
    simulation_jobs[job_id] = {
        "id": job_id,
        "status": SimulationStatus.validating,
        "created_at": datetime.now().isoformat(),
        "warnings": warnings,
        "request": request.dict()
    }
    
    # Run async (or sync for small jobs)
    if request.max_buildings_to_process <= 100:
        result = await _execute_simulation(job_id, request)
        return result
    else:
        background_tasks.add_task(_execute_simulation, job_id, request)
        return {
            "success": True,
            "request_id": job_id,
            "status": SimulationStatus.pending,
            "message": "Large simulation queued for background processing",
            "metadata": {"warnings_issued": len(warnings)},
            "check_status_at": f"/api/v1/status/{job_id}"
        }

async def _execute_simulation(job_id: str, request: SimulationRequest):
    """Execute with full error handling"""
    start_time = time.time()
    
    try:
        simulation_jobs[job_id]["status"] = SimulationStatus.running
        
        # Load data via adapter
        adapter = get_adapter('region' if request.region else 'osm')
        source_config = request.region.dict() if request.region else {}
        if request.plant_location:
            source_config['plant_location'] = request.plant_location.dict()
            source_config['max_pipe_distance_m'] = request.max_pipe_distance_m
        
        building_data = adapter.load_buildings(source_config)
        
        # Validate loaded data
        if len(building_data.gdf) == 0:
            raise ValueError("No buildings found in specified region")
        
        # Sanitize and validate geometry
        clean_gdf, fixes = validator.sanitize_building_data(building_data.gdf)
        valid, geom_errors = validator.validate_uploaded_buildings(clean_gdf)
        
        if not valid:
            raise ValueError(f"Building data validation failed: {geom_errors}")
        
        # Run simulation (your existing logic wrapped)
        from ...config.loader import config_manager
        city_config = config_manager.get_city_config("default")
        engine = SimulationEngine(city_config)
        
        # Prepare results
        metadata = {
            'start_time': datetime.now().isoformat(),
            'duration_seconds': time.time() - start_time,
            'city_config': "default",
            'data_source': 'osm',
            'n_buildings': len(clean_gdf),
            'excluded': 0,
            'exclusion_reasons': {}
        }
        
        # Mock results for structure demo (replace with actual)
        mock_clusters = [{"cluster_id": i, "building_count": 5, "total_heat_demand_kw": 250.0,
                         "centroid_lat": 51.75, "centroid_lon": 14.33, 
                         "specific_demand_kwh_m2a": 120, "suggested_pipe_diameter_mm": 100,
                         "connection_viable": True, "connection_distance_m": 500.0} for i in range(3)]
        
        mock_network = gpd.GeoDataFrame({
            'geometry': [LineString([(14.33, 51.75), (14.34, 51.76)])],
            'diameter_mm': [100],
            'length_m': [1500],
            'flow_direction': ['supply'],
            'velocity_ms': [1.2],
            'pressure_loss_pa': [120],
            'heat_loss_w': [500]
        }, crs="EPSG:4326")
        
        mock_economics = {
            "currency": "EUR",
            "total_capital_cost": 150000.0,
            "pipe_network_cost": 100000.0,
            "plant_cost": 50000.0,
            "connection_costs": 0,
            "annual_o_m_cost": 3000.0,
            "annual_energy_cost": 5000.0,
            "lcoh_eur_mwh": 85.0,
            "cost_breakdown": {"pipes": 66.7, "plant": 33.3, "other": 0.0}
        }
        
        mock_environment = {
            "annual_co2_tons": 20.0,
            "co2_per_mwh": 0.08,
            "comparison_baseline": "gas_boiler",
            "co2_savings_vs_baseline_tons": 15.0,
            "primary_energy_factor": 0.5,
            "renewable_share_percent": 60.0
        }
        
        # Standardize output
        result = standardizer.create_standardized_result(
            request_id=job_id,
            metadata=metadata,
            clusters=mock_clusters,
            network_gdf=mock_network,
            economics=mock_economics,
            environment=mock_environment,
            buildings_gdf=clean_gdf,
            plant_location=request.plant_location.dict() if request.plant_location else None
        )
        
        simulation_jobs[job_id]["status"] = SimulationStatus.completed
        simulation_jobs[job_id]["result"] = result
        
        return SimulationResult(**result)
        
    except Exception as e:
        simulation_jobs[job_id]["status"] = SimulationStatus.failed
        simulation_jobs[job_id]["error"] = str(e)
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                request_id=job_id,
                timestamp=datetime.now().isoformat(),
                code="SIMULATION_ERROR",
                message=str(e),
                suggestion="Check that the region contains buildings and plant location is valid"
            ).dict()
        )

@router.get("/status/{job_id}")
async def get_simulation_status(job_id: str):
    """Get standardized status response"""
    if job_id not in simulation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = simulation_jobs[job_id]
    return {
        "request_id": job_id,
        "status": job["status"],
        "created_at": job.get("created_at"),
        "warnings_count": len(job.get("warnings", [])),
        "result": job.get("result") if job["status"] == "completed" else None
    }
