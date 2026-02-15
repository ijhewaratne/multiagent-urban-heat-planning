# Branitz Heat Decision AI System

A deterministic, auditable multi-agent framework for climate-neutral urban heat planning in the Branitz district of Cottbus, Germany.

---

## Uniqueness

- **True Multi-Physics**: Couples pandapipes (hydraulic-thermal) + pandapower (LV grid) simulations
- **Explainable AI**: Constrained LLM coordinator (read-only, no hallucination) with TNLI-based validation
- **Standards-Aligned**: EN 13941-1 (District Heating), VDE-AR-N 4100 (LV Grid)
- **Uncertainty-Aware**: Monte Carlo win fractions drive robustness flags
- **Street-Level Maps**: Interactive Folium maps with cascading colors and pipe sizing
- **Conversational Interface**: Natural language query processing with multi-turn context
- **Capability Guardrails**: Explicit system boundaries with graceful degradation

---

## System Architecture

### High-Level Overview

The system is an AI-powered decision support platform that compares **District Heating (DH)** vs. **Heat Pump (HP)** options at the street level. It uses a multi-agent architecture with NLU-driven orchestration, lazy simulation execution, and a conversational interface.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│  ┌─────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │  Multi-Tab   │  │  Intent Chat UI  │  │  Conversational UI    │  │
│  │  Dashboard   │  │  (Split-Panel)   │  │  (Chat-First)         │  │
│  │  (app.py)    │  │(app_intent_chat) │  │(app_conversational)   │  │
│  └──────┬───────┘  └────────┬─────────┘  └──────────┬────────────┘  │
└─────────┼──────────────────┼────────────────────────┼───────────────┘
          │                  │                        │
          ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   BranitzOrchestrator                         │   │
│  │  route_request() → 6-Agent Pipeline with Full Trace          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────────┐  │
│  │    NLU     │ │Conversation│ │ Capability │ │    Dynamic      │  │
│  │  Intent    │ │  Manager   │ │ Guardrail  │ │   Executor      │  │
│  │ Classifier │ │  (Memory)  │ │ (Fallback) │ │  (Lazy Cache)   │  │
│  └────────────┘ └────────────┘ └────────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                                       │
          ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ADK TOOLS LAYER                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │prepare_data  │ │  run_cha     │ │  run_dha     │ │run_econom.│  │
│  │   _tool()    │ │  _tool()     │ │  _tool()     │ │  _tool()  │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────┬─────┘  │
└─────────┼────────────────┼────────────────┼────────────────┼────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SIMULATION LAYER                               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │     CHA      │  │     DHA      │  │      Economics          │   │
│  │  (pandapipes)│  │ (pandapower) │  │   (LCOH, CO2, MC)       │   │
│  │  Hydraulic + │  │  LV Grid +   │  │  Monte Carlo +          │   │
│  │   Thermal    │  │  Hosting     │  │  Sensitivity            │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘   │
│                                                                     │
│  ┌──────────────────┐  ┌────────────────────────────────────────┐  │
│  │  Decision Engine  │  │  UHDC (Explanation + Report)           │  │
│  │  (Deterministic   │  │  LLM Explainer + Safety Validator     │  │
│  │   Rules)          │  │  + TNLI Logic Auditor                 │  │
│  └──────────────────┘  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │  Raw GIS     │  │  Processed   │  │     Results             │   │
│  │  (GeoJSON,   │  │  (Parquet,   │  │  (JSON, Pickle, HTML,   │   │
│  │   JSON)      │  │   GeoParquet)│  │   GeoJSON, Parquet)     │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layered Architecture (Detailed)

### Layer 1: User Interface

| File | Role |
|------|------|
| `ui/app.py` | Main multi-tab Streamlit dashboard (Overview, Feasibility, Economics, Compare & Decide, Intent Chat, Portfolio, Jobs) |
| `ui/app_intent_chat.py` | Dedicated chat-first UI with split-panel layout — chat on the left, visualizations (maps, charts, traces) on the right |
| `ui/app_conversational.py` | Alternative conversational UI with auto-context detection |
| `ui/services.py` | Backend services for data loading, job management, and result discovery (`ClusterService`, `JobService`, `ResultService`) |
| `ui/llm.py` | Legacy LLM router for direct chat |
| `ui/registry.py` | Scenario registry defining tool definitions, dependencies, and outputs |
| `ui/env.py` | Environment bootstrapping (API keys, paths) |

### Layer 2: NLU (Natural Language Understanding)

| File | Role |
|------|------|
| `nlu/intent_classifier.py` | Classifies user queries into intents via Google Gemini LLM with keyword fallback. Extracts street entities with fuzzy German name matching (handles `ß`, `Straße`/`Strasse` variants). |
| `nlu/intent_mapper.py` | Maps classified intents to execution tool plans (e.g., `CO2_COMPARISON` → `["cha", "dha", "economics"]`) |

**Supported Intents:**

| Intent | Description | Required Tools |
|--------|-------------|----------------|
| `CO2_COMPARISON` | Compare CO2 emissions between DH and HP | CHA + DHA + Economics |
| `LCOH_COMPARISON` | Compare Levelized Cost of Heat | CHA + DHA + Economics |
| `VIOLATION_ANALYSIS` | Check network pressure/velocity violations | CHA |
| `NETWORK_DESIGN` | Show network layout with interactive maps | CHA |
| `WHAT_IF_SCENARIO` | Modify network parameters and compare | CHA (baseline + scenario) |
| `EXPLAIN_DECISION` | Generate decision recommendation with explanation | Decision + UHDC |
| `CAPABILITY_QUERY` | Ask what the system can do | Guardrail |

### Layer 3: Multi-Agent Orchestration

| File | Class | Role |
|------|-------|------|
| `agents/orchestrator.py` | `BranitzOrchestrator` | Central coordinator — routes requests through a 6-agent pipeline with full agent trace logging |
| `agents/executor.py` | `DynamicExecutor` | Lazy execution engine — runs only required simulations, skips cached results |
| `agents/conversation.py` | `ConversationManager` | Multi-turn state management — follow-up detection, anaphora resolution, metric switching, memory tracking |
| `agents/fallback.py` | `CapabilityGuardrail` | Defines explicit system boundaries — blocks unsupported requests with alternative suggestions and research context |

### Layer 4: ADK Tools (Simulation Wrappers)

| Function | Calls Script | Purpose |
|----------|-------------|---------|
| `prepare_data_tool()` | `00_prepare_data.py` | Raw data ingestion and preparation |
| `run_cha_tool()` | `01_run_cha.py` | District Heating hydraulic-thermal simulation |
| `run_dha_tool()` | `02_run_dha.py` | Heat Pump LV grid power flow simulation |
| `run_economics_tool()` | `03_run_economics.py` | LCOH and CO2 economic analysis |
| `run_decision_tool()` | `cli/decision.py` | Deterministic decision evaluation |
| `run_uhdc_tool()` | `cli/uhdc.py` | Unified explanation report generation |

### Layer 5: Simulation Engines

**CHA — Centralized Heating Analysis** (`cha/`)

| Module | Purpose |
|--------|---------|
| `network_builder.py` | Builds pandapipes networks from GIS building data |
| `network_builder_trunk_spur.py` | Trunk-spur topology construction |
| `convergence_optimizer.py` | Iterative optimization for numerical convergence |
| `kpi_extractor.py` | Extracts EN 13941-1 compliance KPIs (velocity, pressure drop) |
| `qgis_export.py` | Generates interactive Folium maps (velocity, temperature, pressure layers) |
| `config.py` | CHA parameters (supply/return temperatures, pump settings, pipe catalog) |

**DHA — Decentralized Heating Analysis** (`dha/`)

| Module | Purpose |
|--------|---------|
| `grid_builder.py` | Builds pandapower LV grids from geodata |
| `loadflow.py` | Power flow analysis for voltage and line loading violations |
| `kpi_extractor.py` | Extracts grid hosting capacity KPIs |
| `hosting_capacity.py` | Monte Carlo hosting capacity analysis |
| `smart_grid_strategies.py` | Smart grid mitigation strategies |
| `reinforcement_optimizer.py` | Automated grid reinforcement cost estimation |
| `mitigations.py` | Mitigation classification and recommendations |
| `config.py` | DHA parameters (COP, power factor, simultaneity) |

**Economics** (`economics/`)

| Module | Purpose |
|--------|---------|
| `lcoh.py` | Levelized Cost of Heat calculation (Capital Recovery Factor method) |
| `co2.py` | CO2 emissions calculation (fuel-specific emission factors) |
| `monte_carlo.py` | Monte Carlo uncertainty propagation (N=1000 samples) |
| `sensitivity.py` | Sensitivity analysis (±5% parameter variations) |
| `stress_tests.py` | Stress testing with counterfactual scenarios |
| `params.py` | Economic parameters (CAPEX, OPEX, discount rates, lifetimes) |
| `plant_context.py` | Cottbus CHP plant context (marginal cost allocation) |

**Decision Engine** (`decision/`)

| Module | Purpose |
|--------|---------|
| `rules.py` | Deterministic decision rules: cost dominance → CO2 tiebreaker → robustness check |
| `kpi_contract.py` | Builds unified KPI contract from CHA + DHA + Economics results |
| `schemas.py` | Contract validation schemas |

**UHDC — Unified Heat Decision Context** (`uhdc/`)

| Module | Purpose |
|--------|---------|
| `orchestrator.py` | Artifact discovery and assembly |
| `explainer.py` | LLM-based decision explanation generator (Google Gemini) |
| `report_builder.py` | HTML/Markdown report generation |
| `safety_validator.py` | Safety validation for AI-generated explanations |

### Layer 6: Validation

| Module | Purpose |
|--------|---------|
| `validation/logic_auditor.py` | TNLI-based explanation validation (entailment/contradiction detection) |
| `validation/tnli_model.py` | Textual Natural Language Inference model wrapper (HuggingFace) |
| `validation/claims.py` | Structured claim extraction from LLM explanations |
| `validation/monitoring.py` | Validation monitoring and feedback loops |

### Layer 7: Data

| Module | Purpose |
|--------|---------|
| `data/loader.py` | GeoJSON and building data loading |
| `data/profiles.py` | Hourly heat demand profiles (BDEW standard profiles) |
| `data/typology.py` | Building typology estimation (envelope U-values, areas) |
| `data/cluster.py` | Street clustering and design hour calculation |

### Layer 8: Configuration

| Module | Purpose |
|--------|---------|
| `config.py` | Centralized path resolution — `DATA_RAW`, `DATA_PROCESSED`, `RESULTS_ROOT`, `resolve_cluster_path()` |

---

## Agent Pipeline

When a user sends a natural language query, the orchestrator routes it through a **6-agent pipeline**. Each agent has an explicit duty and produces a traceable output:

```
User Query: "Compare CO2 for Heinrich-Zille-Straße"
│
▼
┌─────────────────────────────────────────────────────────┐
│  AGENT 1: NLU Intent Classifier                         │
│  Duty: Classify user intent and extract entities        │
│  Input:  "Compare CO2 for Heinrich-Zille-Straße"       │
│  Output: intent=CO2_COMPARISON                          │
│          street_hint="Heinrich-Zille-Straße"            │
│          confidence=0.95, method=LLM                    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT 2: Conversation Manager                          │
│  Duty: Resolve references, detect follow-ups,           │
│        maintain memory across turns                     │
│  Input:  Intent data + conversation history             │
│  Output: memory_street, is_follow_up flag,              │
│          available cached data for reuse                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT 3: Street Resolver                               │
│  Duty: Map display name / partial mention → valid       │
│        cluster_id (ST###_...)                            │
│  Priority Order:                                        │
│    1. NLU-extracted raw_street_hint (always resolve)    │
│    2. Conversation memory_street (for follow-ups)       │
│    3. UI default cluster_id                             │
│    4. Extract from full query text                      │
│  Output: ST010_HEINRICH_ZILLE_STRASSE                   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT 4: Capability Guardrail                          │
│  Duty: Validate if request is within system boundaries  │
│  Input:  intent, entities, user_query                   │
│  Output: can_handle=True → continue                     │
│          can_handle=False → fallback response with       │
│          alternatives, research notes, escalation path   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT 5: Execution Planner                             │
│  Duty: Determine required simulation tools              │
│  Input:  intent + cluster_id                            │
│  Output: tool_plan = ["cha", "dha", "economics"]        │
│          (mapped via intent_mapper.py)                   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT 6: Dynamic Executor                              │
│  Duty: Execute simulations lazily (skip if cached)      │
│  Input:  tool_plan + cluster_id                         │
│  Output: Results dict with KPIs, execution_log,         │
│          map_paths, violation data                       │
│  Caching: File-based (JSON, pickle) — checks before     │
│           running each tool                              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  RESPONSE FORMATTER                                     │
│  Produces: { type, answer, data, visualization,         │
│              execution_log, agent_trace, suggestions }   │
└─────────────────────────────────────────────────────────┘
```

### Follow-Up Query Flow (Multi-Turn)

```
User: "Compare CO2 for Heinrich-Zille-Straße"
  → Full pipeline → Results for ST010

User: "What about LCOH?"              (follow-up detected)
  → Agent 1: intent=LCOH_COMPARISON
  → Agent 2: memory_street=ST010 (from previous turn)
  → Agent 3: Resolves to ST010 via conversation memory
  → Agent 4-6: Executes LCOH comparison for same street

User: "Can I see the interactive maps?" (follow-up detected)
  → Agent 1: intent=NETWORK_DESIGN
  → Agent 2: memory_street=ST010 (maintained)
  → Agent 3: Resolves to ST010 via conversation memory
  → Agent 4-6: Returns cached interactive maps
```

---

## Complete Agent Inventory

The system contains **15 agents** organized into three tiers: the main request pipeline, on-demand simulation agents, and specialized agents.

### Tier 1: Request Pipeline Agents (execute on every query)

These 6 agents run sequentially inside `BranitzOrchestrator.route_request()` for every user query. Each agent logs its duty and outcome to the **agent trace**, which is visible in the UI for full transparency.

#### Agent 1: NLU Intent Classifier

| | |
|---|---|
| **File** | `nlu/intent_classifier.py` |
| **Class/Function** | `classify_intent()` |
| **Duty** | Classify the user's natural language query into a structured intent and extract entities (street names, parameters) |
| **How it works** | Sends the query to Google Gemini LLM with a constrained system prompt that defines the 7 supported intents. If the LLM is unavailable, falls back to keyword matching against known patterns. Street entities are extracted using fuzzy matching with German name normalization (handles `ss`/`ß`, `Straße`/`Strasse` variants). |
| **Input** | Raw user query string + conversation history |
| **Output** | `{ intent: "CO2_COMPARISON", confidence: 0.95, method: "LLM", entities: { street_name: "Heinrich-Zille-Straße" } }` |

#### Agent 2: Conversation Manager

| | |
|---|---|
| **File** | `agents/conversation.py` |
| **Class** | `ConversationManager` |
| **Duty** | Maintain multi-turn conversation state, detect follow-up queries, resolve anaphora (implicit references), and track available cached data |
| **How it works** | Checks if the current query is a follow-up using linguistic patterns ("what about", "how about", "also show", short queries without street mentions). If it is a follow-up, enriches the intent with the current street from memory, detects metric switching ("What about LCOH?" after a CO2 query), and checks if cached data can answer without re-running simulations. Tracks `ConversationMemory` with `current_street`, `last_calculation`, `calculation_history`, and `available_data` per street. |
| **Input** | Classified intent + conversation history + memory state |
| **Output** | `{ is_follow_up: true, memory_street: "ST010_HEINRICH_ZILLE_STRASSE", available_data: ["cha", "dha", "economics"] }` |

#### Agent 3: Street Resolver

| | |
|---|---|
| **File** | Logic in `agents/orchestrator.py` |
| **Duty** | Map a display name, partial mention, or German street name to a valid cluster ID (`ST###_STREET_NAME`) |
| **How it works** | Resolves the street using a strict priority order: **(1)** NLU-extracted `raw_street_hint` — always resolve even if the UI has a pre-set default; **(2)** Conversation `memory_street` — for follow-up queries where no new street is mentioned; **(3)** UI default `cluster_id` — the street currently shown in the interface; **(4)** Full query text extraction — last resort fuzzy match. Uses `extract_street_entities()` with scoring based on distinguishing word parts (excluding generic suffixes like "strasse", "platz", "allee"). |
| **Input** | NLU street hint + conversation memory + UI default + available streets list |
| **Output** | `{ resolved_cluster_id: "ST010_HEINRICH_ZILLE_STRASSE", method: "NLU street extraction" }` |

#### Agent 4: Capability Guardrail

| | |
|---|---|
| **File** | `agents/fallback.py` |
| **Class** | `CapabilityGuardrail` |
| **Duty** | Validate whether the system can handle the request before any execution begins. If not, return a structured fallback with alternatives and research context. |
| **How it works** | Checks the intent against an explicit registry of `UNSUPPORTED_INTENTS` (add_consumer, remove_pipe, real_time_scada, legal_compliance_check, multi_street_optimization). Also scans the query text for unsupported keywords. For `WHAT_IF_SCENARIO`, checks if the specific modification type is supported (removing houses = yes, changing pipe material = no). When blocking, generates a response with alternative suggestions, a research note explaining why this is a thesis boundary, and an escalation path. Uses `FallbackLLM` (Gemini) for context-aware explanations. |
| **Input** | Intent + entities + raw user query |
| **Output (if blocked)** | `{ can_handle: false, category: "unsupported", message: "...", alternative_suggestions: [...], research_note: "...", escalation_path: "manual_planning" }` |

#### Agent 5: Execution Planner

| | |
|---|---|
| **File** | `nlu/intent_mapper.py` |
| **Data** | `INTENT_TO_PLAN` dictionary |
| **Duty** | Determine which simulation tools are required for the given intent |
| **How it works** | Pure mapping lookup: each intent maps to a list of required tools. Then checks which tools already have cached results on disk (e.g., `cha_kpis.json` exists?) and returns only the missing ones. Respects dependency order: CHA before DHA before Economics before Decision. |
| **Input** | Intent + cluster_id |
| **Output** | `{ required_tools: ["cha", "dha", "economics"], already_cached: ["cha"], to_run: ["dha", "economics"] }` |

#### Agent 6: Dynamic Executor

| | |
|---|---|
| **File** | `agents/executor.py` |
| **Class** | `DynamicExecutor` |
| **Duty** | Execute only the required simulations lazily, using file-based caching to avoid redundant runs |
| **How it works** | For each tool in the execution plan: checks if result files exist on disk (JSON, pickle). If cached, loads and returns them. If missing, calls the ADK tool wrapper which launches the simulation script as a subprocess. Collects KPIs, interactive map paths, violation data, and topology information. For `WHAT_IF_SCENARIO`, clones the baseline network, applies modifications (e.g., disable heat consumers), re-runs only the modified simulation, and compares against the cached baseline. |
| **Input** | Tool plan + cluster_id + context (modification parameters) |
| **Output** | `{ dh_tons_co2: 45.2, hp_tons_co2: 67.3, winner: "DH", execution_log: ["CHA results available", "DHA ran (cache miss)"], map_paths: {...} }` |

### Tier 2: Simulation Agents (called on demand by the Executor)

These agents are invoked by the Dynamic Executor when their results are not cached.

| # | Agent | File | How It Works |
|---|-------|------|-------------|
| 7 | **CHA Simulation Agent** | `adk/tools.py` → `01_run_cha.py` | Builds a pandapipes hydraulic-thermal network from GIS building data using trunk-spur topology. Runs pipeflow with convergence optimization. Extracts EN 13941-1 KPIs (velocity compliance, pressure drop). Generates 3 interactive Folium maps (velocity, temperature, pressure layers). |
| 8 | **DHA Simulation Agent** | `adk/tools.py` → `02_run_dha.py` | Builds a pandapower LV grid from geodata. Models heat pump loads (balanced 3-phase, COP-based). Runs power flow analysis. Extracts hosting capacity KPIs (voltage violations, line loading). Generates grid violation map. |
| 9 | **Economics Agent** | `adk/tools.py` → `03_run_economics.py` | Calculates LCOH using the Capital Recovery Factor method for both DH and HP. Computes CO2 emissions with fuel-specific emission factors. Runs Monte Carlo uncertainty propagation (N=1000 samples) for robustness. Performs sensitivity analysis (±5% parameter variations). |
| 10 | **Decision Agent** | `adk/tools.py` → `cli/decision.py` | Builds a unified KPI contract from CHA + DHA + Economics results. Applies deterministic decision rules: (1) feasibility gate, (2) cost dominance (>5% LCOH difference), (3) CO2 tiebreaker, (4) Monte Carlo robustness check. Produces `decision_{cluster_id}.json`. |
| 11 | **UHDC Explainer Agent** | `adk/tools.py` → `cli/uhdc.py` | Assembles all artifacts (maps, KPIs, decision). Generates a natural language explanation via Google Gemini (temperature=0.0 for determinism). Falls back to template if LLM unavailable. Validates the explanation against the KPI contract using TNLI. Produces HTML/Markdown reports. |

### Tier 3: Specialized Agents

| # | Agent | File | How It Works |
|---|-------|------|-------------|
| 12 | **Fallback LLM** | `agents/fallback.py` (`FallbackLLM`) | Generates context-aware natural language explanations for unsupported requests. Uses Gemini to explain *why* a request cannot be fulfilled and suggests what the user can do instead. Falls back to templates if the API is unavailable. |
| 13 | **TNLI Logic Auditor** | `validation/logic_auditor.py` | Validates LLM-generated explanations against numerical KPI data using Textual Natural Language Inference. Splits explanations into individual sentences, checks each for entailment/contradiction against the KPI table. Reports verified, unverified, and contradicted statements. Includes `ClaimExtractor` for regex-based quantitative claim cross-validation. |
| 14 | **Claim Extractor** | `validation/logic_auditor.py` (`ClaimExtractor`) | Extracts quantitative claims from free-text explanations using 13 regex patterns (CO2, LCOH, losses, pressure, Monte Carlo metrics). Cross-validates extracted numbers against reference KPIs with configurable tolerance (default 10%). Catches hallucinated numbers that TNLI alone might miss. |
| 15 | **Data Preparation Agent** | `adk/tools.py` → `00_prepare_data.py` | Ingests raw GIS data (GeoJSON buildings, streets). Generates BDEW standard hourly heat demand profiles. Estimates building typology (envelope U-values). Clusters buildings into street-level groups with design hour calculations. Produces pipeline-ready Parquet files. |

### Agent Communication Flow

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│           PIPELINE AGENTS (sequential)               │
│                                                       │
│  [1] NLU ──► [2] Conversation ──► [3] Street Resolver│
│                                          │            │
│                                          ▼            │
│  [4] Guardrail ──► [5] Planner ──► [6] Executor     │
│       │                                  │            │
│       │ (if blocked)                     │ (on demand)│
│       ▼                                  ▼            │
│  [12] Fallback LLM          [7-11] Simulation Agents │
│                                          │            │
│                                          ▼            │
│                               [13-14] Validation      │
└─────────────────────────────────────────────────────┘
    │
    ▼
Structured Response
{ type, answer, data, agent_trace, suggestions }
```

### Agent Trace Example

Every request produces a full agent trace visible in the UI. Example for "Compare CO2 for Heinrich-Zille-Straße":

```json
[
  {
    "agent": "NLU Intent Classifier",
    "duty": "Classify user intent and extract entities",
    "outcome": "CO2_COMPARISON",
    "confidence": 0.95,
    "method": "LLM",
    "entities": { "street_name": "Heinrich-Zille-Straße" }
  },
  {
    "agent": "Conversation Manager",
    "duty": "Resolve references, detect follow-ups, maintain context",
    "is_follow_up": false,
    "current_memory_street": null
  },
  {
    "agent": "Street Resolver",
    "duty": "Map display name → valid cluster_id",
    "resolved_cluster_id": "ST010_HEINRICH_ZILLE_STRASSE",
    "method": "NLU street extraction"
  },
  {
    "agent": "Capability Guardrail",
    "duty": "Validate request is within system boundaries",
    "can_handle": true
  },
  {
    "agent": "Execution Planner",
    "duty": "Determine required simulations",
    "required_tools": ["cha", "dha", "economics"]
  },
  {
    "agent": "Dynamic Executor",
    "duty": "Execute CO2_COMPARISON for ST010 (lazy: skip cached)",
    "outcome": "success",
    "execution_log": ["CHA results available", "DHA results available", "Economics ran"]
  }
]
```

---

## End-to-End Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    RAW DATA                              │
│  GeoJSON (buildings, streets, pipes)                    │
│  JSON (Wärmekataster, heating demand)                   │
│  OSM data, Stadtwerke infrastructure                    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼  [00_prepare_data.py]
┌─────────────────────────────────────────────────────────┐
│                  PROCESSED DATA                         │
│  data/processed/                                        │
│  ├── buildings.parquet        (building geometries)     │
│  ├── street_clusters.parquet  (street-level clusters)   │
│  ├── building_cluster_map.parquet (building↔cluster)    │
│  ├── hourly_heat_profiles.parquet (BDEW profiles)       │
│  └── cluster_design_topn.json (design hour params)      │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ 01_run_cha   │ │ 02_run_dha   │ │03_run_econom.│
│  pandapipes  │ │  pandapower  │ │  LCOH + CO2  │
│  hydraulic + │ │  LV grid +   │ │  Monte Carlo │
│  thermal     │ │  hosting cap │ │  sensitivity │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐
│results/cha/  │ │results/dha/  │ │results/economics/    │
│{cluster_id}/ │ │{cluster_id}/ │ │{cluster_id}/         │
│              │ │              │ │                      │
│cha_kpis.json │ │dha_kpis.json │ │economics_determin.   │
│network.pickle│ │buses_results │ │  .json               │
│interactive_  │ │  .geojson    │ │monte_carlo_summary   │
│  map.html    │ │lines_results │ │  .json               │
│interactive_  │ │  .geojson    │ │monte_carlo_samples   │
│  map_temp.   │ │violations.csv│ │  .parquet            │
│  html        │ │hp_lv_map.html│ │                      │
│interactive_  │ │              │ │                      │
│  map_press.  │ │              │ │                      │
│  html        │ │              │ │                      │
└──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘
       │                │                     │
       └────────────────┼─────────────────────┘
                        ▼
              ┌──────────────────┐
              │  Decision Engine │
              │  (rules.py)      │
              │  Cost dominance  │
              │  → CO2 tiebreak  │
              │  → Robustness    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │results/decision/ │
              │{cluster_id}/     │
              │                  │
              │decision_*.json   │
              │kpi_contract_*    │
              │  .json           │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  UHDC Explainer  │
              │  LLM explanation │
              │  + TNLI safety   │
              │    validation    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │results/uhdc/     │
              │{cluster_id}/     │
              │                  │
              │uhdc_report_*     │
              │  .html           │
              │uhdc_explanation_*│
              │  .md             │
              └──────────────────┘
```

---

## Results Directory Structure

```
results/
├── cha/{cluster_id}/
│   ├── cha_kpis.json                   # EN 13941-1 compliance KPIs
│   ├── network.pickle                  # Serialized pandapipes network
│   ├── interactive_map.html            # Velocity layer (Folium)
│   ├── interactive_map_temperature.html # Temperature layer
│   └── interactive_map_pressure.html   # Pressure drop layer
│
├── dha/{cluster_id}/
│   ├── dha_kpis.json                   # Grid hosting capacity KPIs
│   ├── buses_results.geojson           # Bus-level voltage results
│   ├── lines_results.geojson           # Line-level loading results
│   ├── violations.csv                  # Violation summary
│   └── hp_lv_map.html                  # Heat pump grid map
│
├── economics/{cluster_id}/
│   ├── economics_deterministic.json    # LCOH, CO2, annualized costs
│   ├── monte_carlo_summary.json        # MC statistics and win fractions
│   └── monte_carlo_samples.parquet     # Raw MC samples (N=1000)
│
├── decision/{cluster_id}/
│   ├── decision_{cluster_id}.json      # Final recommendation + reasoning
│   └── kpi_contract_{cluster_id}.json  # Unified KPI contract
│
└── uhdc/{cluster_id}/
    ├── uhdc_report_{cluster_id}.html   # Full HTML decision report
    └── uhdc_explanation_{cluster_id}.md # LLM-generated explanation
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Hydraulic-Thermal Simulation | **pandapipes** | District heating pipeflow (EN 13941-1) |
| Electrical Simulation | **pandapower** | LV grid power flow (VDE-AR-N 4100) |
| GIS Processing | **geopandas**, **shapely** | Spatial operations, coordinate handling |
| LLM / NLU | **Google Gemini API** | Intent classification, decision explanations |
| Explanation Validation | **TNLI** (HuggingFace transformers) | Entailment/contradiction detection |
| UI Framework | **Streamlit** | Interactive web dashboard |
| Map Visualization | **Folium** + `streamlit.components.v1.html` | Interactive HTML maps |
| Chart Visualization | **Altair** | Declarative statistical charts |
| Uncertainty Analysis | **NumPy**, **SciPy** | Monte Carlo simulation, sensitivity |
| Caching | File-based (JSON, pickle) + session state | Avoids redundant simulation runs |
| Graph Algorithms | **NetworkX** | Network topology construction |

---

## Phase Implementation

The system was developed in five incremental phases:

| Phase | Component | Key Capability |
|-------|-----------|----------------|
| **Phase 1** | NLU + Orchestrator | Intent classification, entity extraction, request routing |
| **Phase 2** | Dynamic Executor | Lazy simulation execution with file-based caching |
| **Phase 3** | Conversation Manager | Multi-turn context, follow-up detection, reference resolution |
| **Phase 4** | UHDC + Validation | LLM decision explanations with TNLI safety validation |
| **Phase 5** | Capability Guardrail | Explicit boundaries, graceful "I don't know" fallback |

---

## Setup

### Prerequisites

- Python 3.10+
- Git
- Conda (recommended) or pip

### Installation

1. **Clone the repository** (if applicable):

```bash
git clone <repository-url>
cd branitz_heat_decision
```

2. **Create a virtual environment and install dependencies**:

```bash
# Option A: Using conda
conda create -n branitz_heat python=3.10
conda activate branitz_heat
pip install -r requirements.txt

# Option B: Using pip + venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. **Install the package in editable mode** (optional, for development):

```bash
pip install -e .
```

4. **Set up data directory** (optional):

```bash
export BRANITZ_DATA_ROOT=/path/to/your/data
```

5. **Verify installation**:

```bash
python -c "import pandas, geopandas, pandapipes, pandapower; print('All packages installed successfully!')"
```

---

## Quick Start

### Run the Full Pipeline (CLI)

```bash
export BRANITZ_DATA_ROOT=/path/to/your/data
python -m src.scripts.pipeline --cluster-id ST001_HEINRICH_ZILLE_STRASSE
```

### Run Individual Steps

```bash
# Step 0: Prepare data
PYTHONPATH=src python src/scripts/00_prepare_data.py

# Step 1: CHA simulation (District Heating)
PYTHONPATH=src python src/scripts/01_run_cha.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE

# Step 2: DHA simulation (Heat Pumps)
PYTHONPATH=src python src/scripts/02_run_dha.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE

# Step 3: Economics (LCOH + CO2)
PYTHONPATH=src python src/scripts/03_run_economics.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE
```

### Launch the Conversational UI

```bash
PYTHONPATH=src streamlit run src/scripts/run_chat_ui.py
```

---

## Optional: Enable LLM Explanations (Gemini)

LLM explanations are **optional**. Without a key, the decision pipeline will automatically fall back to a safe template explanation.

1. **Create `.env` in the repo root** (never commit this file):

```bash
echo 'GOOGLE_API_KEY=your_key_here' > .env
echo 'GOOGLE_MODEL=gemini-2.0-flash' >> .env   # optional
echo 'LLM_TIMEOUT=30' >> .env                  # optional
echo 'UHDC_FORCE_TEMPLATE=false' >> .env       # optional
```

2. **Verify environment wiring**:

```bash
PYTHONPATH=src python -c "from branitz_heat_decision.uhdc.explainer import LLM_READY; print('LLM ready:', LLM_READY)"
```

3. **Run decision with LLM explanation**:

```bash
PYTHONPATH=src python -m branitz_heat_decision.cli.decision \
  --cluster-id ST010_HEINRICH_ZILLE_STRASSE \
  --llm-explanation \
  --explanation-style executive
```

### Security Notes

- **Do not commit keys**: `.env` is gitignored (see `.gitignore`).
- **CI/CD**: inject `GOOGLE_API_KEY` via environment variables/secrets, not files.
- **If a key was committed accidentally**: remove it from git history and **rotate the key** immediately.

---

## Project Structure

```
Branitz2/
├── data/
│   ├── raw/                    # Original Wärmekataster, OSM, Stadtwerke data
│   └── processed/              # Validated, pipeline-ready data (GeoParquet)
│
├── results/                    # All outputs (deterministic, versioned)
│   ├── cha/                    # District heating simulation results
│   ├── dha/                    # Heat pump grid simulation results
│   ├── economics/              # Economic analysis results
│   ├── decision/               # Decision outputs
│   └── uhdc/                   # Explanation reports
│
├── src/
│   ├── branitz_heat_decision/  # Main Python package
│   │   ├── agents/             # Multi-agent orchestration
│   │   │   ├── orchestrator.py #   Central coordinator
│   │   │   ├── executor.py     #   Dynamic execution engine
│   │   │   ├── conversation.py #   Conversation state manager
│   │   │   └── fallback.py     #   Capability guardrail
│   │   │
│   │   ├── nlu/                # Natural Language Understanding
│   │   │   ├── intent_classifier.py  # Intent classification + entity extraction
│   │   │   └── intent_mapper.py      # Intent → tool plan mapping
│   │   │
│   │   ├── cha/                # CHA simulation modules (pandapipes)
│   │   ├── dha/                # DHA simulation modules (pandapower)
│   │   ├── economics/          # Economic analysis modules
│   │   ├── decision/           # Deterministic decision engine
│   │   ├── uhdc/               # Unified explanation framework
│   │   ├── validation/         # TNLI-based explanation validation
│   │   ├── data/               # Data loading and processing
│   │   ├── adk/                # Agent Development Kit (tool wrappers)
│   │   ├── ui/                 # Streamlit UI components
│   │   ├── cli/                # CLI entry points
│   │   └── config.py           # Centralized configuration
│   │
│   └── scripts/                # Pipeline entry points
│       ├── 00_prepare_data.py
│       ├── 01_run_cha.py
│       ├── 02_run_dha.py
│       ├── 03_run_economics.py
│       └── run_chat_ui.py
│
├── tests/                      # Test suite
├── docs/                       # Documentation
├── Legacy/                     # Legacy reference implementations
├── requirements.txt            # Python package dependencies
├── .env                        # API keys (gitignored)
└── README.md                   # This file
```

---

## Testing

```bash
# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run specific test suites
PYTHONPATH=src pytest tests/test_phase2_execution.py -v
PYTHONPATH=src pytest tests/test_capability_guardrail.py -v
```

---

## License

This project is part of a Master's thesis research at BTU Cottbus-Senftenberg. All rights reserved.