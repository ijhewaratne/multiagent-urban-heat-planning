# Branitz API Integration Guide for Fraunhofer

## Quick Start

### 1. Docker Deployment

```bash
# Clone repository
git clone https://github.com/ijhewaratne/multiagent-urban-heat-planning.git
cd multiagent-urban-heat-planning

# Start production stack
docker-compose -f docker-compose.prod.yml up -d

# Check health
curl http://localhost/health
```

### 2. Basic Usage

**City-scale analysis with postal code:**

```bash
curl -X POST http://localhost/api/v1/simulate/region \
  -H "Content-Type: application/json" \
  -d '{
    "region": {
      "postal_code": "03046",
      "plant_location": {
        "lat": 51.7563,
        "lon": 14.3329,
        "supply_temperature_c": 80,
        "return_temperature_c": 60
      },
      "max_pipe_distance_m": 3000
    },
    "max_buildings_to_process": 500,
    "city_config": "cottbus"
  }'
```

**Response:**
```json
{
  "success": true,
  "request_id": "req_20240304123045_1234",
  "status": "completed",
  "network_geojson": {
    "type": "FeatureCollection",
    "features": [...]
  },
  "economics": {
    "lcoh_eur_mwh": 85.50,
    "total_capital_cost": 2500000
  }
}
```

### 3. Frontend Integration

**JavaScript Widget Example:**

```javascript
class BranitzHeatPlanner {
  constructor(apiUrl) {
    this.apiUrl = apiUrl;
    this.jobPollInterval = null;
  }

  async analyzeRegion(postalCode, plantLat, plantLon) {
    const response = await fetch(`${this.apiUrl}/api/v1/simulate/region`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        region: {
          postal_code: postalCode,
          plant_location: {lat: plantLat, lon: plantLon},
          max_pipe_distance_m: 5000
        },
        max_buildings_to_process: 1000
      })
    });
    
    const {request_id, status} = await response.json();
    
    if (status === 'pending') {
      return this.pollResults(request_id);
    }
    return this.getResults(request_id);
  }

  async pollResults(jobId) {
    return new Promise((resolve) => {
      this.jobPollInterval = setInterval(async () => {
        const res = await fetch(`${this.apiUrl}/api/v1/status/${jobId}`);
        const data = await res.json();
        
        if (data.status === 'completed') {
          clearInterval(this.jobPollInterval);
          resolve(data.result);
        }
      }, 2000);
    });
  }
}

// Usage
const planner = new BranitzHeatPlanner('https://branitz.yourdomain.com');
const results = await planner.analyzeRegion('03046', 51.7563, 14.3329);
```

### 4. Data Formats

**Supported Input Coordinate Systems:**
- WGS84 (EPSG:4326) - Default for web
- UTM Zone 33N (EPSG:32633) - For Cottbus/Brandenburg region

**Output GeoJSON Schema:**
All spatial outputs follow GeoJSON RFC 7946 with extended properties:
- `network_geojson`: LineString features with `diameter_mm`, `pressure_loss_pa`
- `clusters_geojson`: Point features with `total_heat_demand_kw`
- `buildings_geojson`: Polygon features with `heat_demand_kwh`

### 5. Performance Guidelines

| Buildings | Processing Time | Endpoint Type |
|-----------|----------------|---------------|
| < 100     | < 5s           | Synchronous   |
| 100-1000  | 10-60s         | Async polling |
| 1000-10000| 1-5min         | Async + email |

### 6. Error Handling

Common error codes:
- `PLANT_OUTSIDE_REGION`: Plant coordinates outside bounding box
- `NO_BUILDINGS_FOUND`: Region contains no valid building data
- `COORDINATE_SWAP_SUSPECTED`: Lat/lon appear reversed

All errors include `suggestion` field with fix instructions.

### 7. Webhook Integration

For long simulations, provide webhook URL:

```json
{
  "region": {...},
  "webhook_url": "https://your-portal.com/api/branitz/callback",
  "webhook_secret": "your_secret_key"
}
```

Callback payload:
```json
{
  "job_id": "req_...",
  "status": "completed",
  "download_url": "https://.../results/req_.../report.pdf"
}
```

## Support

Contact: [GitHub Issues](https://github.com/ijhewaratne/multiagent-urban-heat-planning/issues)
