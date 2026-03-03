from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
import time
from contextlib import asynccontextmanager

from .v1.endpoints import router as v1_router
from .v1.demo import router as demo_router
from .middleware import validation_exception_handler
from .metrics import metrics_middleware, get_metrics
from ..api.tasks import celery_app
from ..config.loader import config_manager

# Custom OpenAPI schema metadata
tags_metadata = [
    {
        "name": "Simulation",
        "description": "Core heat network planning calculations. All simulations are asynchronous for regions >100 buildings.",
        "externalDocs": {
            "description": "Engineering methodology",
            "url": "https://github.com/ijhewaratne/multiagent-urban-heat-planning/docs/methodology.md"
        }
    },
    {
        "name": "Data",
        "description": "Geographic data retrieval and validation endpoints for OSM and custom uploads."
    },
    {
        "name": "System",
        "description": "Health checks, configuration, and monitoring endpoints."
    }
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting Branitz API v2.0.0")
    print(f"Available cities: {list(config_manager.load_app_config().cities.keys())}")
    yield
    # Shutdown
    celery_app.close()

app = FastAPI(
    title="Branitz Heat Planning API",
    description="""
    **Production-ready district heating network planning engine.**
    
    This API provides multi-agent simulation for urban heat network planning, 
    optimized for integration with municipal planning tools.
    
    ## Key Features
    * **City-scale processing**: Handle 10,000+ buildings via asynchronous job queue
    * **Plant-centric design**: Specify existing or planned heat plant locations
    * **Standardized outputs**: GeoJSON compliant with DIN 18599 and VDI 4655
    
    ## Authentication
    Production instances require API key in header: `X-API-Key: your_key_here`
    
    ## Rate Limits
    * Synchronous requests: 10/minute (max 100 buildings)
    * Async requests: 100/hour (max 10,000 buildings)
    
    ## Fraunhofer Integration
    For embedding in external planning portals, use the `/simulate/region` endpoint 
    with postal code and plant location parameters.
    """,
    version="2.0.0",
    openapi_tags=tags_metadata,
    docs_url=None,  # Custom docs below
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "API Support",
        "url": "https://github.com/ijhewaratne/multiagent-urban-heat-planning/issues",
        "email": "support@branitz.example"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Exception handlers
app.add_exception_handler(Exception, validation_exception_handler)

# CORS - configurable via env
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production via nginx
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Metrics middleware
app.middleware("http")(metrics_middleware)

# Custom Swagger UI
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Branitz API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        init_oauth={
            "clientId": "your-client-id",
            "appName": "Branitz API"
        }
    )

# Metrics endpoint
@app.get("/metrics", include_in_schema=False)
async def metrics():
    return get_metrics()

# Include versioned routers
app.include_router(v1_router, prefix="/api/v1", tags=["Simulation"])
app.include_router(demo_router, prefix="/api/v1", tags=["Demo"])

@app.get("/health", tags=["System"])
async def health_check():
    """Comprehensive health check for load balancers"""
    try:
        # Check Redis
        celery_app.broker_connection().ensure_connection(max_retries=1)
        redis_status = "connected"
    except:
        redis_status = "disconnected"
    
    return {
        "status": "healthy" if redis_status == "connected" else "degraded",
        "version": "2.0.0",
        "timestamp": time.time(),
        "services": {
            "api": "up",
            "redis": redis_status,
            "celery": "up" if redis_status == "connected" else "down"
        },
        "cities_loaded": len(config_manager.load_app_config().cities)
    }

@app.get("/config/schema", tags=["System"])
async def get_config_schema():
    """Get valid configuration parameters for all cities"""
    config = config_manager.load_app_config()
    return {
        "cities": {
            name: {
                "climate_zone": city.climate_zone,
                "crs": city.crs,
                "economic_params": city.economic.dict(),
                "physics_params": city.physics.dict()
            }
            for name, city in config.cities.items()
        }
    }
