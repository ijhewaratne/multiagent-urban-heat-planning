from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from pathlib import Path

class EconomicParams(BaseModel):
    currency: str = "EUR"
    electricity_price_eur_kwh: float = 0.35
    gas_price_eur_kwh: float = 0.08
    co2_price_eur_ton: float = 80.0
    discount_rate: float = 0.05
    inflation_rate: float = 0.02
    plant_lifetime_years: int = 25
    heat_pump_cop: float = 3.2
    
class PhysicsParams(BaseModel):
    design_temp_ambient_c: float = -12.0
    design_temp_supply_c: float = 80.0
    design_temp_return_c: float = 60.0
    soil_temp_c: float = 8.0
    heat_loss_coefficient: float = 0.5  # W/m2K for pipes
    
class ClusteringParams(BaseModel):
    min_buildings_per_cluster: int = 3
    max_buildings_per_cluster: int = 50
    max_distance_to_street_m: float = 50.0
    connection_threshold_m: float = 30.0
    
class SimulationParams(BaseModel):
    timestep_hours: int = 1
    simulation_days: int = 365
    convergence_tolerance: float = 1e-4
    max_iterations: int = 100
    
class CityConfig(BaseModel):
    name: str
    country: str = "Germany"
    climate_zone: str = "Dfb"  # Köppen classification
    crs: str = "EPSG:32633"  # UTM zone for Cottbus
    center_lat: float
    center_lon: float
    
    economic: EconomicParams = Field(default_factory=EconomicParams)
    physics: PhysicsParams = Field(default_factory=PhysicsParams)
    clustering: ClusteringParams = Field(default_factory=ClusteringParams)
    simulation: SimulationParams = Field(default_factory=SimulationParams)
    
    # Specific local adjustments
    specific_heat_demand_kwh_m2a: Dict[str, float] = {
        "residential": 120,
        "commercial": 150,
        "industrial": 200,
        "school": 130
    }

class AppConfig(BaseModel):
    environment: str = "development"
    data_root: Path = Path("./data")
    output_root: Path = Path("./output")
    default_city: str = "cottbus"
    cities: Dict[str, CityConfig] = {}
