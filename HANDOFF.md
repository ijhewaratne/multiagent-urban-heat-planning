# Branitz Heat Decision AI - Integration Handoff Guide

This repository has been cleaned up and restructured to separate the **Core Product** from research artifacts and exploratory notebooks. This guide is intended for developers integrating the Branitz computational engine into web platforms, specifically the Fraunhofer website integration.

## 1. Repository Structure Overview

### Active Codebase (Keep)
*   **`src/branitz_heat_decision/`**: The core Python package.
    *   `agents/`: Orchestrator, Executor, Domain Agents (CHA, DHA, Economics, etc.). This is the primary intelligence layer.
    *   `adk/`: Agent Development Kit. Contains policy guardrails and tool wrappers that execute the heavy simulation scripts safely.
    *   `nlu/`: Natural Language Understanding for intent classification.
    *   `decision/` & `uhdc/`: Rule-based decision making and report generation.
*   **`src/scripts/`**: The heavy lifting CLI scripts.
    *   `01_run_cha.py`: Runs District Heating simulations (pandapipes).
    *   `02_run_dha.py`: Runs Heat Pump / LV grid simulations (pandapower).
    *   `03_run_economics.py`: Calculates Capex, Opex, LCOH, CO2.
*   **`ui/app_intent_chat.py`**: The sole remaining Streamlit UI, demonstrating the NLU -> Orchestrator -> Executor flow.

### Archived Code (Ignore)
*   **`archive/`**: Contains old legacy code (`ui/app.py`, old prompt iterations), meeting notes, `docs/`, and exploratory Jupyter notebooks. These are kept strictly for PhD research history and should be ignored for software integration.

## 2. Integration Points for Web Developers

To integrate the Branitz engine into a web backend (e.g., a FastAPI or Node server), you do not need to run the Streamlit UI. Instead, you interact directly with the Python API.

### Option A: The "Agentic" Way (Recommended)
You can submit natural language queries directly to the Orchestrator, exactly as the Streamlit app does. The system will figure out which simulations to run.

```python
from branitz_heat_decision.agents import BranitzOrchestrator

orchestrator = BranitzOrchestrator(verbose=True)

# The orchestrator handles intent parsing, dependency planning, caching,
# execution, and LLM explanation generation automatically.
response = orchestrator.route_request(
    query="Compare heat pumps with district heating for Thiemstrasse",
    cluster_id="thiemstrasse_cluster_01"
)

# Parse response
print(response["answer"])          # LLM explanation
print(response["data"])            # Raw KPI data dictionary
print(response["agent_results"])   # Timings and status of which agents ran
```

### Option B: The "Deterministic" Way
If you want to bypass the NLU and LLM layers and just run the raw simulations programmatically from your own backend:

```python
from branitz_heat_decision.adk.tools import (
    run_cha_tool,
    run_dha_tool,
    run_economics_tool,
    run_decision_tool
)

cluster = "thiemstrasse_cluster_01"

# 1. Run District Heating Physics
cha_status = run_cha_tool(cluster_id=cluster)

# 2. Run Heat Pump Physics
dha_status = run_dha_tool(cluster_id=cluster)

# 3. Calculate Economics (Capex, Opex, LCOH, CO2)
econ_status = run_economics_tool(cluster_id=cluster)

# 4. Run rules engine to pick the winner
decision_status = run_decision_tool(cluster_id=cluster)
```
*Note: The results from the tools are saved to disk in `results/clusters/{cluster_id}/`. Your backend will need to read these JSON files.*

## 3. Data Requirements

The simulation engine heavily relies on the pre-processed cluster topologies built by `00_prepare_data.py`. 

Before running any simulations, ensure that your `data/processed/` directory contains:
*   `street_clusters.parquet`
*   `buildings.parquet`
*   `building_cluster_map.parquet`

The system expects `cluster_id` strings (e.g. `thiemstrasse_cluster_01`) to match the keys found in these files.

## 4. Environment Setup

It is highly recommended to use `conda` or `mamba` to handle the geospatial and simulation dependencies (`geopandas`, `pandapipes`, `pandapower`).

```bash
conda env create -f environment.yml
conda activate branitz
pip install -e .
```

*Ensure your `.env` file contains your `OPENAI_API_KEY` for the NLU/Explanation layers.*
