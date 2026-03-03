#!/bin/bash
set -e

echo "🚀 Branitz API Deployment Script"

# Check dependencies
command -v docker-compose >/dev/null 2>&1 || { echo "docker-compose required"; exit 1; }

# Create directories
mkdir -p data/demo data/osm_cache output logs
chmod 777 output logs

# Generate demo data if not exists
if [ ! -f "data/demo/cottbus_demo_buildings.geojson" ]; then
    echo "📊 Generating demo data..."
    python3 scripts/generate_demo_data.py
fi

# Environment setup
if [ ! -f ".env" ]; then
    echo "⚙️ Creating default .env file..."
    cat > .env << EOF
SECRET_KEY=$(openssl rand -hex 32)
ALLOWED_ORIGINS=https://*.fraunhofer.de,http://localhost:*
REDIS_URL=redis://redis:6379
DATA_ROOT=./data
OUTPUT_ROOT=./output
GRAFANA_PASSWORD=admin
EOF
fi

# Start services
echo "🐳 Starting Docker services..."
docker-compose -f docker-compose.prod.yml up -d --build

# Health check
echo "⏳ Waiting for API to be ready..."
sleep 10

if curl -s http://localhost/health | grep -q "healthy"; then
    echo "✅ Deployment successful!"
    echo "📖 API Docs: http://localhost/docs"
    echo "🔍 Demo: http://localhost/api/v1/demo/status"
else
    echo "❌ Health check failed. Check logs: docker-compose -f docker-compose.prod.yml logs"
    exit 1
fi
