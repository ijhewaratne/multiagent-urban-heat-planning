from sqlalchemy import create_engine, Column, String, JSON, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

# Dummy engine for example purposes
engine = create_engine('sqlite:///:memory:')

class SimulationRecord(Base):
    """Tenant-scoped simulation results"""
    __tablename__ = "simulations"
    
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)  # Fraunhofer IIS, EAS, etc.
    user_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    request_params = Column(JSON)
    results_summary = Column(JSON)
    status = Column(String)
    output_files = Column(JSON)  # Paths to GeoJSON results

class TenantConfig(Base):
    """Per-tenant configuration overrides"""
    __tablename__ = "tenant_configs"
    
    tenant_id = Column(String, primary_key=True)
    theme_overrides = Column(JSON)  # Custom colors/logos
    default_city = Column(String)
    max_buildings_limit = Column(Integer, default=10000)
    allowed_export_formats = Column(JSON, default=["geojson", "csv"])
    custom_economic_params = Column(JSON)  # Tenant-specific pricing

def get_tenant_db_session(tenant_id: str):
    """Get database session scoped to tenant"""
    # In production, use connection pooling with schema separation
    Session = sessionmaker(bind=engine)
    return Session()
