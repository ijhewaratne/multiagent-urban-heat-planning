# Branitz Heat Decision AI System

A deterministic, auditable multi-agent framework for climate-neutral urban heat planning in the Branitz district of Cottbus, Germany. The system compares **District Heating (DH)** vs. **Heat Pumps (HP)** at street level by coupling pandapipes (hydraulic-thermal) and pandapower (LV grid) simulations with rule-based decision making and constrained, validated LLM explanations.

**Key principle:** LLMs only classify intent and narrate — every number and every decision comes from deterministic physics and rules, and all LLM-generated text is verified against the KPI data (TNLI validation).

📖 **Full architecture documentation:** [docs/architecture.md](docs/architecture.md)
🔌 **Web/backend integration guide:** [HANDOFF.md](HANDOFF.md)

## Highlights

- True multi-physics: pandapipes (DH networks) + pandapower (LV grids)
- Standards-aligned: EN 13941-1 (District Heating), VDE-AR-N 4100 (LV Grid)
- Hierarchical 5-layer agent architecture (Orchestrator → Executor → Domain Agents → ADK Agents → Tools) with cache-first execution
- Monte Carlo uncertainty propagation drives robustness flags
- Explainable AI: read-only LLM coordinator with TNLI-based claim validation
- Conversational Streamlit UI with interactive execution traces and street-level maps

## Setup

```bash
conda create -n branitz_heat python=3.10
conda activate branitz_heat
pip install -r requirements.txt
pip install -e .
```

Optional LLM explanations (Gemini): copy `.env.example` to `.env` and set `GOOGLE_API_KEY`. Without a key the system falls back to keyword intent classification and deterministic templates.

## Quick Start

```bash
# Step 0: Prepare data (buildings, clusters, hourly profiles)
PYTHONPATH=src python src/scripts/00_prepare_data.py

# Step 1: CHA — District Heating simulation
PYTHONPATH=src python src/scripts/01_run_cha.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE

# Step 2: DHA — Heat Pump / LV grid simulation
PYTHONPATH=src python src/scripts/02_run_dha.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE

# Step 3: Economics — LCOH, CO2, Monte Carlo
PYTHONPATH=src python src/scripts/03_run_economics.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE

# Conversational UI
PYTHONPATH=src streamlit run src/scripts/run_chat_ui.py
```

## Scenarios (2023 vs 2030)

Economic scenarios live in `scripts/scenarios/*.yaml`. Run any phase against a scenario and compare winners per street:

```bash
PYTHONPATH=src python src/scripts/03_run_economics.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE --scenario 2030_optimistic
PYTHONPATH=src python -m branitz_heat_decision.cli.decision --cluster-id ST010_HEINRICH_ZILLE_STRASSE --scenario 2030_optimistic --format json

# Winner-flip table across scenarios (the Wärmeplanungsgesetz question)
PYTHONPATH=src python src/scripts/04_compare_scenarios.py --all-clusters
```

Scenario outputs are namespaced under `results/{economics,decision}/<cluster>/scenarios/<name>/` — baseline results are never overwritten.

## Web API & Docker

```bash
pip install -e ".[api]"
PYTHONPATH=src uvicorn branitz_heat_decision.api.app:app --port 8000
# or:
docker compose -f docker/docker-compose.yml up --build
```

Endpoints: `POST /clusters/{id}/run` (deterministic pipeline, optional `scenario` + `background`), `GET /clusters/{id}/decision`, `GET /clusters/{id}/kpis`, `POST /query` (agentic NL interface), `GET /clusters`, `GET /scenarios`. Interactive docs at `/docs`.

## Other Districts

The engine is not Branitz-specific: pass your own inputs to data prep (`--buildings`, `--streets`, `--attributes-file`, `--analysis-file`) and point `BRANITZ_PLANT_CONTEXT` at a plant config JSON/YAML (see `config/plant_context_cottbus.json`).

## Programmatic Use

```python
from branitz_heat_decision.agents import BranitzOrchestrator

orchestrator = BranitzOrchestrator()
response = orchestrator.route_request(
    user_query="Compare CO2 for Heinrich-Zille-Strasse",
    cluster_id="ST010_HEINRICH_ZILLE_STRASSE",
)
print(response["answer"])
```

See [HANDOFF.md](HANDOFF.md) for the deterministic (no-LLM) integration path.

## Project Structure

```
src/branitz_heat_decision/
├── agents/        # Orchestrator, executor, domain agents (agents/domain/)
├── adk/           # ADK tool-level agents + policy guardrails
├── nlu/           # Intent classification and mapping
├── cha/           # District heating network physics (pandapipes)
├── dha/           # LV grid / heat pump physics (pandapower)
├── economics/     # LCOH, CO2, Monte Carlo, sensitivity
├── decision/      # KPI contract + rule-based decision engine
├── uhdc/          # Report builder + constrained LLM explainer
├── validation/    # TNLI claim validation of LLM output
└── ui/            # Streamlit chat UI
src/scripts/       # CLI pipeline (00_prepare → 01_cha → 02_dha → 03_economics)
data/              # raw + processed inputs
results/           # per-cluster outputs (cha/, dha/, economics/, decision/)
tests/             # AI safety, consistency, formula-claim tests
```

## Testing

```bash
pytest tests/
```

## License

MIT — see [pyproject.toml](pyproject.toml). Author: Ishantha Hewaratne (Fraunhofer IEG).
