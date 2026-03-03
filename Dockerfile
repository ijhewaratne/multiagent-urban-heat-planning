# syntax=docker/dockerfile:1
FROM python:3.11-slim as base

# System dependencies for geospatial processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgeos-dev \
    libproj-dev \
    libgdal-dev \
    libspatialindex-dev \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

# Install dependencies separately for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==================== DEVELOPMENT ====================
FROM base as development
ENV APP_ENV=development \
    LOG_LEVEL=debug \
    RELOAD=true

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt || true

COPY . .
CMD ["uvicorn", "branitz_heat_decision.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ==================== PRODUCTION ====================
FROM base as production
ENV APP_ENV=production \
    LOG_LEVEL=info \
    RELOAD=false \
    WORKERS=4

# Create non-root user
RUN groupadd -r branitz && useradd -r -g branitz branitz

# Copy application code
COPY --chown=branitz:branitz . .

# Switch to non-root
USER branitz

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

EXPOSE 8000
CMD ["gunicorn", "branitz_heat_decision.api.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]
