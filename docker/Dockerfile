# Branitz Heat Decision — API service image
#
# Conda-based build: the geospatial stack (geopandas/pyproj/shapely) needs
# binary dependencies that are painful with pip alone.
#
# Build (from repo root):
#   docker build -f docker/Dockerfile -t branitz-api .
# Run:
#   docker run -p 8000:8000 -v $(pwd)/data:/app/data -v $(pwd)/results:/app/results branitz-api

FROM condaforge/mambaforge:24.3.0-0 AS base

WORKDIR /app

# 1. Solve the conda environment first (best layer-cache behavior)
COPY environment.yml .
RUN mamba env create -f environment.yml && mamba clean -afy

# Make the env the default for all subsequent commands
SHELL ["conda", "run", "-n", "branitz", "/bin/bash", "-c"]
ENV PATH=/opt/conda/envs/branitz/bin:$PATH

# 2. Install the package
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-deps -e .

# 3. Configs + scenario definitions (data/ and results/ are volume mounts)
COPY config/ config/
COPY scripts/scenarios/ scripts/scenarios/

# Defaults (override with -e or compose)
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check against the API
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "branitz_heat_decision.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
