from pydantic import BaseModel, Field, validator, root_validator, ValidationError
from typing import Dict, Any, List, Optional, Union, Literal
from enum import Enum
from datetime import datetime
from shapely.geometry import shape, Point, Polygon, mapping
import geopandas as gpd
import json

# ==================== ENUMS ====================

class BuildingType(str, Enum):
    residential = "residential"
    commercial = "commercial"
    industrial = "industrial"
    school = "school"
    hospital = "hospital"
    office = "office"
    retail = "retail"
    mixed = "mixed"
    other = "other"

class HeatingSystemType(str, Enum):
    district_heating = "district_heating"
    heat_pump = "heat_pump"
    gas_boiler = "gas_boiler"
    biomass = "biomass"
    combined = "combined"

class NetworkTopology(str, Enum):
    radial = "radial"           # From plant outward
    ring = "ring"               # Closed loops
    tree = "tree"               # Minimum spanning tree
    mesh = "mesh"               # Redundant grid

class SimulationStatus(str, Enum):
    pending = "pending"
    validating = "validating"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

# ==================== INPUT SCHEMAS ====================

class GeoJSONGeometry(BaseModel):
    type: str = Field(..., regex="^(Point|Polygon|MultiPolygon)$")
    coordinates: List[Any]
    
    @validator('coordinates')
    def validate_coords(cls, v, values):
        if values.get('type') == 'Point' and len(v) != 2:
            raise ValueError('Point must have [lon, lat] coordinates')
        return v

class PlantLocationInput(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="WGS84 Latitude")
    lon: float = Field(..., ge=-180, le=180, description="WGS84 Longitude")
    name: Optional[str] = Field("Main Plant", max_length=100)
    existing_capacity_kw: Optional[float] = Field(None, gt=0)
    supply_temperature_c: float = Field(80.0, ge=40, le=150)
    return_temperature_c: float = Field(60.0, ge=30, le=100)
    
    @validator('return_temperature_c')
    def validate_temp_delta(cls, v, values):
        if 'supply_temperature_c' in values and v >= values['supply_temperature_c']:
            raise ValueError('Return temperature must be less than supply temperature')
        return v

class RegionInput(BaseModel):
    """Unified region specification - must provide ONE identifier"""
    postal_code: Optional[str] = Field(None, regex=r"^\d{4,5}$", example="03046")
    city: Optional[str] = Field(None, min_length=2, example="Cottbus")
    district: Optional[str] = Field(None, example="Spree-Neiße")
    place_name: Optional[str] = Field(None, example="Heinrich-Zille-Straße, Cottbus")
    bbox: Optional[List[float]] = Field(None, min_items=4, max_items=4, 
                                        example=[14.2, 51.7, 14.5, 51.8])
    
    @root_validator(pre=True)
    def check_one_identifier(cls, values):
        identifiers = ['postal_code', 'city', 'district', 'place_name', 'bbox']
        provided = [k for k in identifiers if values.get(k)]
        if len(provided) != 1:
            raise ValueError(f'Exactly one region identifier required. Provided: {provided}')
        return values

class BuildingConstraints(BaseModel):
    min_building_area_m2: float = Field(50.0, ge=10, description="Filter out small structures")
    max_building_area_m2: Optional[float] = Field(None, ge=1000)
    min_stories: int = Field(1, ge=0, le=50)
    max_stories: Optional[int] = Field(None, ge=1, le=100)
    building_types: Optional[List[BuildingType]] = None
    year_built_after: Optional[int] = Field(None, ge=1800, le=2030)
    year_built_before: Optional[int] = Field(None, ge=1800, le=2030)
    
    @validator('year_built_before')
    def validate_year_range(cls, v, values):
        if v and values.get('year_built_after') and v < values['year_built_after']:
            raise ValueError('year_built_before must be >= year_built_after')
        return v

class EconomicOverrides(BaseModel):
    electricity_price_eur_kwh: Optional[float] = Field(None, ge=0.05, le=1.0)
    gas_price_eur_kwh: Optional[float] = Field(None, ge=0.02, le=0.5)
    co2_price_eur_ton: Optional[float] = Field(None, ge=0, le=500)
    heat_pump_cop: Optional[float] = Field(None, ge=1.0, le=6.0)
    discount_rate: Optional[float] = Field(None, ge=0, le=0.2)
    currency: Literal["EUR", "USD", "GBP"] = "EUR"

class SimulationRequest(BaseModel):
    """Main request schema - validates complete input"""
    request_id: Optional[str] = Field(None, regex=r"^[a-zA-Z0-9\-_]{6,40}$")
    region: RegionInput
    plant_location: Optional[PlantLocationInput] = None
    constraints: BuildingConstraints = Field(default_factory=BuildingConstraints)
    economic_overrides: Optional[EconomicOverrides] = None
    
    # Processing parameters
    max_pipe_distance_m: float = Field(5000, ge=500, le=20000, 
                                      description="Economic radius from plant")
    network_topology: NetworkTopology = NetworkTopology.radial
    target_velocity_ms: float = Field(1.0, ge=0.1, le=3.0, 
                                     description="Target flow velocity in pipes")
    max_pressure_loss_pa_m: float = Field(150, ge=50, le=1000)
    
    # Scale limits
    max_buildings_to_process: int = Field(2000, ge=5, le=10000)
    clustering_algorithm: Literal["hierarchical", "kmeans", "dbscan"] = "hierarchical"
    
    # Output options
    output_formats: List[Literal["geojson", "shapefile", "csv", "report"]] = ["geojson"]
    include_intermediate_results: bool = False
    
    @validator('request_id', always=True)
    def set_request_id(cls, v):
        return v or f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(str(datetime.now())) % 10000:04d}"
    
    @root_validator
    def validate_scale_consistency(cls, values):
        """Ensure parameters match selected scale"""
        max_dist = values.get('max_pipe_distance_m', 5000)
        max_buildings = values.get('max_buildings_to_process', 2000)
        
        # Warn if requesting too many buildings for small radius
        if max_dist < 1000 and max_buildings > 1000:
            raise ValueError('Small radius (<1km) with >1000 buildings is likely misconfigured')
        
        return values

# ==================== ERROR SCHEMAS ====================

class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    type: str
    value: Optional[Any] = None

class ErrorResponse(BaseModel):
    error: bool = True
    request_id: str
    timestamp: str
    code: str  # machine-readable error code
    message: str  # human-readable message
    details: List[ValidationErrorDetail] = []
    suggestion: Optional[str] = None  # Helpful hint for fixing
    
    class Config:
        schema_extra = {
            "example": {
                "error": True,
                "request_id": "req_20240304123045_1234",
                "timestamp": "2024-03-04T12:30:45Z",
                "code": "INVALID_COORDINATES",
                "message": "Plant location is outside the specified region",
                "details": [{"field": "plant_location.lat", "message": "51.2 is outside bbox", "type": "range_error"}],
                "suggestion": "Ensure plant coordinates fall within the region bounding box or increase region size"
            }
        }

# ==================== OUTPUT SCHEMAS ====================

class ClusterOutput(BaseModel):
    cluster_id: int = Field(..., ge=0)
    building_count: int = Field(..., ge=1)
    total_floor_area_m2: float = Field(..., ge=0)
    total_heat_demand_kw: float = Field(..., ge=0)
    peak_heat_demand_kw: float = Field(..., ge=0)
    specific_demand_kwh_m2a: float = Field(..., ge=0)
    centroid_lat: float = Field(..., ge=-90, le=90)
    centroid_lon: float = Field(..., ge=-180, le=180)
    connection_distance_m: float = Field(..., ge=0)  # Distance to plant or main line
    suggested_pipe_diameter_mm: int = Field(..., ge=20, le=1000)
    estimated_flow_rate_ls: float = Field(..., ge=0)
    building_types_distribution: Dict[str, int]  # {"residential": 15, "commercial": 3}
    
    # Connection viability
    connection_viable: bool
    viability_reason: Optional[str] = None  # Why not viable if False

class PipeSegment(BaseModel):
    segment_id: str
    from_node: str
    to_node: str
    length_m: float = Field(..., ge=0)
    diameter_mm: int = Field(..., ge=20, le=1000)
    material: str = Field("steel", regex="^(steel|pe_x|composite)$")
    flow_direction: Literal["supply", "return"]
    velocity_ms: float = Field(..., ge=0, le=5)
    pressure_loss_pa: float = Field(..., ge=0)
    heat_loss_w: float = Field(..., ge=0)
    installation_year: int = Field(datetime.now().year, ge=2020, le=2050)
    
    # Geometry
    geometry: GeoJSONGeometry

class NetworkStatistics(BaseModel):
    total_pipe_length_m: float = Field(..., ge=0)
    supply_line_length_m: float = Field(..., ge=0)
    return_line_length_m: float = Field(..., ge=0)
    max_pipe_diameter_mm: int
    min_pipe_diameter_mm: int
    total_heat_loss_kw: float = Field(..., ge=0)
    pump_energy_demand_kwh_a: float = Field(..., ge=0)
    number_of_valves: int
    number_of_heat_exchangers: int

class EconomicResults(BaseModel):
    currency: str = "EUR"
    total_capital_cost: float = Field(..., ge=0, description="Total investment including plant")
    pipe_network_cost: float = Field(..., ge=0)
    plant_cost: float = Field(..., ge=0)
    connection_costs: float = Field(..., ge=0)
    annual_o_m_cost: float = Field(..., ge=0, description="Operation and maintenance")
    annual_energy_cost: float = Field(..., ge=0)
    lcoh_eur_mwh: float = Field(..., ge=0, description="Levelized Cost of Heat")
    npv_25yr: Optional[float] = None
    payback_period_years: Optional[float] = Field(None, ge=0)
    
    # Sensitivity indicators
    cost_breakdown: Dict[str, float]  # Percentages summing to 100
    
    @validator('cost_breakdown')
    def validate_percentages(cls, v):
        total = sum(v.values())
        if abs(total - 100.0) > 0.1:
            raise ValueError(f'Cost breakdown percentages must sum to 100, got {total}')
        return v

class EnvironmentalResults(BaseModel):
    annual_co2_tons: float = Field(..., ge=0)
    co2_per_mwh: float = Field(..., ge=0)
    comparison_baseline: Literal["gas_boiler", "heat_pump", "oil_boiler", "coal"] = "gas_boiler"
    co2_savings_vs_baseline_tons: float
    primary_energy_factor: float = Field(..., ge=0)
    renewable_share_percent: float = Field(..., ge=0, le=100)

class SimulationMetadata(BaseModel):
    request_id: str
    timestamp_start: datetime
    timestamp_end: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    version: str = "2.0.0"
    city_config_used: str
    data_source: str  # OSM, uploaded, etc.
    buildings_processed: int
    buildings_excluded: int
    exclusion_reasons: Dict[str, int]  # {"too_small": 5, "too_far": 12}

class SimulationResult(BaseModel):
    """Standardized complete output"""
    success: bool = True
    request_id: str
    status: SimulationStatus
    
    metadata: SimulationMetadata
    clusters: List[ClusterOutput]
    network: NetworkStatistics
    economics: EconomicResults
    environment: EnvironmentalResults
    
    # GeoJSON outputs (as dicts for JSON serialization)
    network_geojson: Dict[str, Any]  # FeatureCollection of PipeSegments
    clusters_geojson: Dict[str, Any]  # FeatureCollection of cluster centroids
    buildings_geojson: Optional[Dict[str, Any]] = None  # Input buildings with results
    
    # Download links (if async processing)
    download_urls: Optional[Dict[str, str]] = None
