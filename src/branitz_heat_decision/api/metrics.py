from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time

# Metrics
REQUEST_COUNT = Counter('branitz_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('branitz_request_duration_seconds', 'Request latency')
SIMULATION_COUNT = Counter('branitz_simulations_total', 'Simulations run', ['city', 'status'])

async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.observe(process_time)
    return response

def get_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
