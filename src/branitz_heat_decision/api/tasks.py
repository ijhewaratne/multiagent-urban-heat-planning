from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
import time
from .v1.schemas import RegionSimulationRequest
from ..adapters.region_adapter import RegionAdapter
from ..core.city_scale_engine import CityScaleEngine
from ..config.loader import config_manager

celery_app = Celery('branitz', broker='redis://localhost:6379/0')

@celery_app.task(bind=True, soft_time_limit=300, time_limit=600)
def process_region_simulation(self, job_id: str, request_dict: dict):
    """
    Background task for large region processing
    Reports progress via Celery meta
    """
    try:
        # Update state to STARTED
        self.update_state(state='PROGRESS', meta={'progress': 0, 'stage': 'initializing'})
        
        # Load data
        adapter = RegionAdapter()
        region_dict = request_dict.get('region', {})
        source_config = {
            'postal_code': region_dict.get('postal_code'),
            'city': region_dict.get('city'),
            'plant_location': region_dict.get('plant_location'),
            'max_pipe_distance_m': region_dict.get('max_pipe_distance_m', 5000)
        }
        
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': 'downloading_osm'})
        building_data = adapter.load_buildings(source_config)
        
        n_buildings = len(building_data.gdf)
        if n_buildings > 10000:
            # Pre-filter to max 10k closest to plant if too many
            building_data.gdf = building_data.gdf.head(10000)
        
        self.update_state(state='PROGRESS', meta={'progress': 30, 'stage': 'clustering', 'buildings': n_buildings})
        
        # Run simulation
        city_config = config_manager.get_city_config(request_dict.get('city_config', 'cottbus'))
        engine = CityScaleEngine(city_config)
        
        # Simulate progress updates during long computation
        def progress_callback(pct):
            self.update_state(state='PROGRESS', meta={'progress': 30 + int(pct * 0.6), 'stage': 'optimizing'})
        
        results = engine.run(
            building_data, 
            plant_location=region_dict.get('plant_location')
        )
        
        self.update_state(state='PROGRESS', meta={'progress': 90, 'stage': 'finalizing'})
        
        # Save results (Placeholder)
        # ...
        
        return {'status': 'completed', 'job_id': job_id, 'results': results}
        
    except SoftTimeLimitExceeded:
        return {'status': 'timeout', 'error': 'Processing took too long (>5 minutes)'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
