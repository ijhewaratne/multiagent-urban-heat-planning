# Branitz Heat Decision AI System

A deterministic, auditable multi-agent framework for climate-neutral urban heat planning in the Branitz district of Cottbus, Germany.

---

## Uniqueness

- **True Multi-Physics**: Couples pandapipes (hydraulic-thermal) + pandapower (LV grid) simulations
- **Explainable AI**: Constrained LLM coordinator (read-only, no hallucination) with TNLI-based validation
- **Hierarchical Agent Architecture**: 5-layer delegation (Orchestrator → Executor → Domain Agents → ADK Agents → Tools)
- **Standards-Aligned**: EN 13941-1 (District Heating), VDE-AR-N 4100 (LV Grid)
- **Uncertainty-Aware**: Monte Carlo win fractions drive robustness flags
- **Street-Level Maps**: Interactive Folium maps with cascading colors and pipe sizing
- **Conversational Interface**: Natural language query processing with multi-turn context, featuring a dedicated "Branitz Assistant" persona
- **Interactive Execution Trace**: Dynamic, full-width SVG branching diagrams showing the exact agent execution path for full transparency
- **Capability Guardrails**: Explicit system boundaries with graceful degradation

---

## System Architecture

### High-Level Overview

The system is an AI-powered decision support platform that compares **District Heating (DH)** vs. **Heat Pump (HP)** options at the street level. It uses a hierarchical multi-agent architecture with NLU-driven orchestration, domain-specific agents with cache-first execution, and a conversational interface.

### Complete System Diagram

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   BRANITZ HEAT DECISION AI SYSTEM                                    ║
║                              21 Agents · 5 Layers · 10 Intent Types                                 ║
╚═══════════════════════════════════════════════╤═════════════════════════════════════════════════════════╝
                                                │
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│                    USER INTERFACE                         │
│                 Intent Chat UI                            │
│             ui/app_intent_chat.py                         │
│                                                           │
│    (Two-Column + Trace: Chat ⟵ Left, Viz ⟵ Right          │
│                         SVG Trace ⟵ Bottom)               │
└────────────────────────────┬──────────────────────────────┘
                             │
                             │  user_query + cluster_id
                             ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 1: ORCHESTRATION            BranitzOrchestrator    (agents/orchestrator.py)      ║
║                                                                                         ║
║  route_request(user_query, cluster_id, context)                                        ║
║                                                                                         ║
║  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────────────┐    ║
║  │  AGENT 1     │───▶│  AGENT 2     │───▶│  AGENT 3     │───▶│  AGENT 4           │    ║
║  │  NLU Intent  │    │  Conversation│    │  Street      │    │  Capability        │    ║
║  │  Classifier  │    │  Manager     │    │  Resolver    │    │  Guardrail         │    ║
║  │              │    │              │    │              │    │                    │    ║
║  │ nlu/intent_  │    │ agents/      │    │ (logic in   │    │ agents/fallback.py │    ║
║  │ classifier.py│    │ conversation │    │  orchestrator│    │ CapabilityGuardrail│    ║
║  │              │    │ .py          │    │  .py)        │    │                    │    ║
║  │ Gemini LLM   │    │ Memory +     │    │ NLU hint →   │    │ Supported? → yes   │    ║
║  │ + keyword    │    │ follow-up    │    │ Memory →     │    │   → continue       │    ║
║  │   fallback   │    │ detection    │    │ UI default → │    │ Unsupported? → no  │    ║
║  │              │    │              │    │ Query extract │    │   → fallback +     │    ║
║  │ Output:      │    │ Output:      │    │              │    │     research note   │    ║
║  │ intent,      │    │ is_follow_up │    │ Output:      │    │     + alternatives  │    ║
║  │ confidence,  │    │ memory_street│    │ cluster_id   │    │                    │    ║
║  │ entities     │    │ cached_data  │    │ (ST###_...)  │    │ → FallbackLLM [21] │    ║
║  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └─────────┬──────────┘    ║
║         │                   │                   │                      │               ║
║         └───────────────────┴───────────────────┴──────────────────────┘               ║
║                                                                                        ║
║  ┌──────────────────────┐   Outputs returned to Orchestrator                           ║
║  │  AGENT 5             │◀─────────────────────────────────────────────────────────────┘
║  │  Execution Planner   │                                                              ║
║  │  intent_mapper.py +  │   CO2_COMPARISON     → ["cha","dha","economics"]             ║
║  │  executor._create_   │   LCOH_COMPARISON    → ["cha","dha","economics"]             ║
║  │  agent_plan()        │   VIOLATION_ANALYSIS → ["cha","dha"]                         ║
║  │                      │   NETWORK_DESIGN     → ["cha"]                               ║
║  │                      │   WHAT_IF_SCENARIO   → ["what_if"]                           ║
║  │                      │   DECISION           → ["cha","dha","economics","decision"]  ║
║  │                      │   EXPLAIN_DECISION   → ["cha","dha","economics","decision"]  ║
║  │                      │   FULL_REPORT        → ["cha","dha","economics","decision","uhdc"] ║
║  │                      │   DATA_PREPARATION   → ["data_prep"]                         ║
║  └──────────┬───────────┘                                                              ║
╚═════════════╪═══════════════════════════════════════════════════════════════════════════╝
              │  agent_plan = ["cha", "dha", "economics"]
              ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 2: DYNAMIC EXECUTOR         DynamicExecutor        (agents/executor.py)          ║
║                                                                                         ║
║  ┌──────────────────────────────────────────────────────────────────────────────────┐   ║
║  │  AGENT 6: Dynamic Executor                                                       │   ║
║  │                                                                                   │   ║
║  │  _ensure_agents()     → lazy init 8 domain agent instances (once)                │   ║
║  │  _create_agent_plan() → intent → ordered agent list                              │   ║
║  │  _run_agent_plan()    → for each agent: execute() → timed log                    │   ║
║  │  _integrate_results() → dispatch to _format_co2/_format_lcoh/etc.                │   ║
║  │                                                                                   │   ║
║  │  Execution Log:   "✓ Used cached CHA (0.002s)"                                   │   ║
║  │                   "✓ Used cached DHA (0.001s)"                                   │   ║
║  │                   "✓ Calculated ECONOMICS (2.3s)"                                │   ║
║  │                                                                                   │   ║
║  │  Output: { dh_tons_co2, hp_tons_co2, winner, execution_log, agent_results,       │   ║
║  │            total_execution_time }                                                 │   ║
║  └──────────┬───────────────────────────┬──────────────────────────┬────────────────┘   ║
╚═════════════╪═══════════════════════════╪══════════════════════════╪═════════════════════╝
              │                           │                          │
              ▼                           ▼                          ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 2.5: DOMAIN AGENTS                                 (agents/domain_agents.py)     ║
║                                                                                         ║
║  BaseDomainAgent(ABC): can_handle() + execute() + _check_cache()                       ║
║  Each agent: cache check → if miss → delegate to ADK Agent                             ║
║                                                                                         ║
║  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐                  ║
║  │  AGENT 7    │  │  AGENT 8    │  │  AGENT 9    │  │  AGENT 10    │                  ║
║  │  DataPrep   │  │  CHA        │  │  DHA        │  │  Economics   │                  ║
║  │  Agent      │  │  Agent      │  │  Agent      │  │  Agent       │                  ║
║  │             │  │             │  │             │  │              │                  ║
║  │ Cache:      │  │ Cache:      │  │ Cache:      │  │ Cache:       │                  ║
║  │ buildings   │  │ cha_kpis    │  │ dha_kpis    │  │ economics_   │                  ║
║  │ .parquet    │  │ .json +     │  │ .json       │  │ deterministic│                  ║
║  │ + cluster   │  │ network     │  │             │  │ .json        │                  ║
║  │   map +     │  │ .pickle     │  │             │  │              │                  ║
║  │   profiles  │  │             │  │             │  │ Prereqs:     │                  ║
║  │             │  │ Intents:    │  │ Intents:    │  │ CHA + DHA    │                  ║
║  │ Intents:    │  │ CHA, CO2,   │  │ DHA, HP,    │  │              │                  ║
║  │ DATA_PREP   │  │ LCOH, VIOL, │  │ LV_GRID,    │  │ Intents:     │                  ║
║  │             │  │ NETWORK,    │  │ CO2, LCOH   │  │ ECON, LCOH,  │                  ║
║  │             │  │ WHAT_IF     │  │             │  │ CO2, MC      │                  ║
║  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘                  ║
║         │                │                │                │                            ║
║  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐                  ║
║  │  AGENT 11   │  │  AGENT 12   │  │  AGENT 13   │  │  AGENT 14    │                  ║
║  │  Decision   │  │  Validation │  │  UHDC       │  │  WhatIf      │                  ║
║  │  Agent      │  │  Agent      │  │  Agent      │  │  Agent       │                  ║
║  │             │  │             │  │             │  │              │                  ║
║  │ Cache:      │  │ No cache    │  │ No cache    │  │ Uses CHA     │                  ║
║  │ decision_   │  │ (stateless) │  │ Prereq:     │  │ baseline     │                  ║
║  │ {id}.json   │  │             │  │ Decision    │  │ network      │                  ║
║  │             │  │ Stage 1:    │  │             │  │              │                  ║
║  │ Prereq:     │  │ ClaimExtrac │  │ Output:     │  │ 1. CHA cache │                  ║
║  │ Economics   │  │ tor (regex) │  │ HTML, MD,   │  │ 2. Clone net │                  ║
║  │             │  │             │  │ JSON reports│  │ 3. Disable   │                  ║
║  │ Intents:    │  │ Stage 2:    │  │             │  │    houses    │                  ║
║  │ DECISION,   │  │ TNLIModel   │  │ Intents:    │  │ 4. Re-run    │                  ║
║  │ EXPLAIN,    │  │ (rule-based │  │ UHDC,       │  │    pipeflow  │                  ║
║  │ RECOMMEND   │  │  + opt LLM) │  │ REPORT      │  │ 5. Compare   │                  ║
║  └──────┬──────┘  └─────────────┘  └──────┬──────┘  └──────┬───────┘                  ║
║         │                                  │                │                           ║
║  AGENT_REGISTRY = { "data_prep": DataPrepAgent, "cha": CHAAgent, "dha": DHAAgent,     ║
║    "economics": EconomicsAgent, "decision": DecisionAgent, "validation":              ║
║    ValidationAgent, "uhdc": UHDCAgent, "what_if": WhatIfAgent }                       ║
║  get_agent("cha", cache_dir="./cache") → CHAAgent instance                            ║
╚═══════╪═══════════════════════╪═══════════════════════════════╪═════════════════════════╝
        │                       │                               │
        ▼                       ▼                               ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 3: ADK AGENTS               BaseADKAgent              (adk/agent.py)             ║
║                                                                                         ║
║  Every tool call wrapped with:                                                         ║
║    ● enforce_guardrails()  → policy check (adk/policies.py)                            ║
║    ● AgentTrajectory       → full action audit trail                                    ║
║    ● time.perf_counter()   → duration_seconds on AgentAction                           ║
║                                                                                         ║
║  Critical policy: "LLM cannot decide" — decisions come from deterministic rules only   ║
║                                                                                         ║
║  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       ║
║  │ AGENT 15 │ │ AGENT 16 │ │ AGENT 17 │ │ AGENT 18 │ │ AGENT 19 │ │ AGENT 20 │       ║
║  │ ADK Data │ │ ADK CHA  │ │ ADK DHA  │ │ ADK Econ │ │ ADK Dec  │ │ ADK UHDC │       ║
║  │ Prep     │ │ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │       ║
║  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       ║
╚═══════╪════════════╪════════════╪════════════╪════════════╪════════════╪═══════════════╝
        │            │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 4: ADK TOOLS (raw functions)                        (adk/tools.py)               ║
║                                                                                         ║
║  prepare_    run_cha     run_dha     run_economics  run_decision  run_uhdc              ║
║  data_tool() _tool()     _tool()     _tool()        _tool()       _tool()              ║
║      │           │           │           │              │             │                  ║
║      ▼           ▼           ▼           ▼              ▼             ▼                  ║
║  00_prepare  01_run_cha  02_run_dha  03_run_econ   cli/decision  cli/uhdc               ║
║  _data.py    .py         .py         omics.py      .py           .py                    ║
╚══════╪═══════════╪═══════════╪═══════════╪══════════════╪════════════╪═══════════════════╝
       │           │           │           │              │            │
       ▼           ▼           ▼           ▼              ▼            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 5: SIMULATION ENGINES                                                            ║
║                                                                                         ║
║  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────────────┐      ║
║  │   CHA (cha/)       │  │   DHA (dha/)       │  │   Economics (economics/)     │      ║
║  │                    │  │                    │  │                              │      ║
║  │   pandapipes       │  │   pandapower       │  │   LCOH (Capital Recovery     │      ║
║  │   pipeflow         │  │   power flow       │  │     Factor method)           │      ║
║  │                    │  │                    │  │   CO2 (fuel-specific          │      ║
║  │   network_builder  │  │   grid_builder     │  │     emission factors)        │      ║
║  │   _trunk_spur.py   │  │   .py              │  │   Monte Carlo (default 500,  │      ║
║  │                    │  │                    │  │    configurable)              │      ║
║  │   convergence_     │  │   loadflow.py      │  │   Sensitivity (±5%)          │      ║
║  │   optimizer.py     │  │   hosting_         │  │   Stress tests               │      ║
║  │   kpi_extractor.py │  │   capacity.py      │  │                              │      ║
║  │   qgis_export.py   │  │   kpi_extractor.py │  │   params.py                  │      ║
║  │   (Folium maps)    │  │   smart_grid_      │  │   plant_context.py           │      ║
║  │                    │  │   strategies.py    │  │                              │      ║
║  │   EN 13941-1       │  │   VDE-AR-N 4100    │  │                              │      ║
║  └────────────────────┘  └────────────────────┘  └──────────────────────────────┘      ║
║                                                                                         ║
║  ┌────────────────────┐  ┌─────────────────────────────────────────────────────┐       ║
║  │   Decision         │  │   UHDC (uhdc/)                                      │       ║
║  │   (decision/)      │  │                                                     │       ║
║  │                    │  │   orchestrator.py  → artifact discovery              │       ║
║  │   rules.py →       │  │   explainer.py    → Gemini LLM explanation          │       ║
║  │     feasibility    │  │   safety_         → explanation safety check         │       ║
║  │     → cost domin.  │  │     validator.py                                    │       ║
║  │     → CO2 tiebreak │  │   report_         → HTML/Markdown/JSON output       │       ║
║  │     → robustness   │  │     builder.py                                      │       ║
║  │                    │  │                                                     │       ║
║  │   kpi_contract.py  │  │                                                     │       ║
║  │   schemas.py       │  │                                                     │       ║
║  └────────────────────┘  └─────────────────────────────────────────────────────┘       ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
       │           │           │           │              │            │
       ▼           ▼           ▼           ▼              ▼            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  VALIDATION LAYER                                                                       ║
║                                                                                         ║
║  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐             ║
║  │  ClaimExtractor                  │  │  TNLIModel / LightweightValidator│             ║
║  │  (validation/logic_auditor.py)   │  │  (validation/tnli_model.py)      │             ║
║  │                                  │  │                                  │             ║
║  │  13 regex patterns:              │  │  Rule-based entailment:          │             ║
║  │  CO2, LCOH, losses, pressure,    │  │  "DH is cheaper" + lcoh_dh <     │             ║
║  │  Monte Carlo metrics             │  │   lcoh_hp → ENTAILMENT          │             ║
║  │                                  │  │                                  │             ║
║  │  Cross-validate claims vs KPIs   │  │  Optional Gemini LLM backend    │             ║
║  │  Tolerance: ±10%                 │  │  for complex statements          │             ║
║  └──────────────────────────────────┘  └──────────────────────────────────┘             ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
       │
       ▼
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  DATA LAYER                                                                             ║
║                                                                                         ║
║  ┌────────────────────┐  ┌─────────────────────┐  ┌────────────────────────────┐       ║
║  │   data/raw/        │  │  data/processed/     │  │   results/{cluster_id}/    │       ║
║  │                    │  │                     │  │                            │       ║
║  │   GeoJSON          │  │  buildings.parquet   │  │   cha/                     │       ║
║  │   (buildings,      │  │  street_clusters     │  │     cha_kpis.json          │       ║
║  │    streets,        │  │    .parquet          │  │     network.pickle         │       ║
║  │    pipes)          │  │  building_cluster    │  │     interactive_map*.html  │       ║
║  │                    │  │    _map.parquet      │  │                            │       ║
║  │   JSON             │  │  hourly_heat_        │  │   dha/                     │       ║
║  │   (Wärmekataster,  │  │    profiles.parquet  │  │     dha_kpis.json          │       ║
║  │    demand)         │  │  cluster_design_     │  │     buses/lines.geojson    │       ║
║  │                    │  │    topn.json         │  │     hp_lv_map.html         │       ║
║  │   OSM data         │  │                     │  │                            │       ║
║  │   Stadtwerke       │  │                     │  │   economics/               │       ║
║  │   infrastructure   │  │                     │  │     economics_determ.json   │       ║
║  │                    │  │                     │  │     monte_carlo_*.json/pq   │       ║
║  │                    │  │  data/loader.py      │  │                            │       ║
║  │                    │  │  data/profiles.py    │  │   decision/                │       ║
║  │                    │  │  data/typology.py    │  │     decision_{id}.json     │       ║
║  │                    │  │  data/cluster.py     │  │     kpi_contract_{id}.json │       ║
║  │                    │  │                     │  │                            │       ║
║  │                    │  │                     │  │   uhdc/                     │       ║
║  │                    │  │                     │  │     uhdc_report_{id}.html   │       ║
║  │                    │  │                     │  │     uhdc_explanation_{id}.md│       ║
║  └────────────────────┘  └─────────────────────┘  └────────────────────────────┘       ║
║                                                                                         ║
║  config/__init__.py → DATA_RAW, DATA_PROCESSED, RESULTS_ROOT, resolve_cluster_path()   ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

### Layered Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Intent Chat UI                             │  │
│  │        (ui/app_intent_chat.py w/ SVG Trace)                   │  │
│  └──────────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────────┼───────────────────────────────────┘
          │                  │                        │
          ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LAYER 1: ORCHESTRATION (orchestrator.py)               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   BranitzOrchestrator                         │   │
│  │  route_request() → 6-Agent Pipeline with Full Trace          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────────┐  │
│  │    NLU     │ │Conversation│ │ Capability │ │   Execution     │  │
│  │  Intent    │ │  Manager   │ │ Guardrail  │ │   Planner       │  │
│  │ Classifier │ │  (Memory)  │ │ (Fallback) │ │                 │  │
│  └────────────┘ └────────────┘ └────────────┘ └─────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LAYER 2: DYNAMIC EXECUTOR (executor.py)                │
│                                                                     │
│  _create_agent_plan() → _run_agent_plan() → _integrate_results()   │
│  Lazy init · cache-first · timed execution logs · flat-dict output │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ delegates to
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│          LAYER 2.5: DOMAIN AGENTS (domain_agents.py)               │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐             │
│  │ DataPrep │ │   CHA    │ │   DHA    │ │ Economics │             │
│  │  Agent   │ │  Agent   │ │  Agent   │ │   Agent   │             │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐             │
│  │ Decision │ │Validation│ │   UHDC   │ │  WhatIf   │             │
│  │  Agent   │ │  Agent   │ │  Agent   │ │   Agent   │             │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘             │
│  Each agent: can_handle() → cache check → delegate to ADK agent    │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ delegates to
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LAYER 3: ADK AGENTS (adk/agent.py)                    │
│                                                                     │
│  BaseADKAgent → _execute_tool() with:                              │
│    · Policy enforcement (guardrails before every tool call)         │
│    · Trajectory tracking (AgentAction audit trail)                  │
│    · Per-action timing (duration_seconds via perf_counter)          │
│                                                                     │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐          │
│  │ADK CHA   │ │ADK DHA   │ │ADK Econ.  │ │ADK Decis. │          │
│  │Agent     │ │Agent     │ │Agent      │ │Agent      │          │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘          │
│  ┌───────────┐ ┌───────────┐                                       │
│  │ADK DataPr.│ │ADK UHDC  │                                       │
│  │Agent     │ │Agent     │                                       │
│  └───────────┘ └───────────┘                                       │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ calls
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LAYER 4: ADK TOOLS (adk/tools.py)                     │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐ │
│  │prepare_data  │ │  run_cha     │ │  run_dha     │ │run_econom.│ │
│  │   _tool()    │ │  _tool()     │ │  _tool()     │ │  _tool()  │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────┬─────┘ │
│  ┌──────────────┐ ┌──────────────┐                         │       │
│  │run_decision  │ │  run_uhdc    │                         │       │
│  │   _tool()    │ │  _tool()     │                         │       │
│  └──────┬───────┘ └──────┬───────┘                         │       │
└─────────┼────────────────┼─────────────────────────────────┼───────┘
          │                │                                 │
          ▼                ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LAYER 5: SIMULATION ENGINES                            │
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
| `ui/app_intent_chat.py` | Dedicated chat-first UI with a "Branitz Assistant" persona. Uses a two-column layout (chat on the left, visualizations on the right) and features a dynamic, full-width SVG bottom panel for the **Agent Execution Trace**, which provides full transparency into the Orchestrator → Executor → Domain Agent → Results flow. |
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

| Intent | Description | Agent Plan |
|--------|-------------|------------|
| `CO2_COMPARISON` | Compare CO2 emissions between DH and HP | CHA → DHA → Economics |
| `LCOH_COMPARISON` | Compare Levelized Cost of Heat | CHA → DHA → Economics |
| `VIOLATION_ANALYSIS` | Check network pressure/velocity & grid violations | CHA → DHA |
| `NETWORK_DESIGN` | Show network layout with interactive maps | CHA |
| `WHAT_IF_SCENARIO` | Modify network parameters and compare | WhatIf (delegates to CHA internally) |
| `EXPLAIN_DECISION` | Generate decision recommendation with explanation | CHA → DHA → Economics → Decision |
| `DECISION` | Full decision with all dependencies | CHA → DHA → Economics → Decision |
| `FULL_REPORT` | Complete UHDC report | CHA → DHA → Economics → Decision → UHDC |
| `DATA_PREPARATION` | Prepare raw data for pipeline | DataPrep |
| `CAPABILITY_QUERY` | Ask what the system can do | Guardrail (no executor) |

### Layer 3: Multi-Agent Orchestration

| File | Class | Role |
|------|-------|------|
| `agents/orchestrator.py` | `BranitzOrchestrator` | Central coordinator — routes requests through a 6-agent pipeline with full agent trace logging |
| `agents/executor.py` | `DynamicExecutor` | Lazy execution engine — creates agent plans, delegates to domain agents, integrates results into flat dicts |
| `agents/domain_agents.py` | 8 domain agents + `AGENT_REGISTRY` | Specialized domain agents with cache-first execution, each delegating to an ADK agent |
| `agents/conversation.py` | `ConversationManager` | Multi-turn state management — follow-up detection, anaphora resolution, metric switching, memory tracking |
| `agents/fallback.py` | `CapabilityGuardrail` | Defines explicit system boundaries — blocks unsupported requests with alternative suggestions and research context |
| `agents/__init__.py` | Package exports | Exports all agent classes, `AGENT_REGISTRY`, `get_agent()` factory |

### Layer 3.5: Domain Agents (Specialist Station Agents)

Each domain agent inherits from `BaseDomainAgent` and implements `can_handle()` + `execute()`. They check file-based caches before delegating to ADK agents.

| Agent | Class | Handles | Delegates To | Cache Files |
|-------|-------|---------|-------------|-------------|
| Data Prep | `DataPrepAgent` | DATA_PREPARATION | ADK DataPrepAgent | `buildings.parquet`, `building_cluster_map.parquet`, `hourly_profiles.parquet` |
| CHA | `CHAAgent` | CHA_SIMULATION, CO2/LCOH, VIOLATIONS, NETWORK_DESIGN, WHAT_IF | ADK CHAAgent | `cha_kpis.json`, `network.pickle` |
| DHA | `DHAAgent` | DHA_SIMULATION, HEAT_PUMP, LV_GRID, CO2/LCOH | ADK DHAAgent | `dha_kpis.json` |
| Economics | `EconomicsAgent` | ECONOMICS, LCOH/CO2_COMPARISON, MONTE_CARLO | ADK EconomicsAgent | `economics_deterministic.json` |
| Decision | `DecisionAgent` | DECISION, EXPLAIN_DECISION, RECOMMENDATION | ADK DecisionAgent | `decision_{cluster_id}.json` |
| Validation | `ValidationAgent` | VALIDATE, CHECK_CLAIMS, VERIFY_EXPLANATION | ClaimExtractor + TNLIModel (direct) | N/A (stateless) |
| UHDC | `UHDCAgent` | UHDC, REPORT, GENERATE_REPORT | ADK UHDCAgent | HTML, Markdown, JSON reports |
| WhatIf | `WhatIfAgent` | WHAT_IF_SCENARIO, SCENARIO_ANALYSIS | CHAAgent + pandapipes (direct) | `network.pickle` (baseline) |

### Layer 4: ADK Agents (Policy-Enforced Tool Wrappers)

| File | Role |
|------|------|
| `adk/agent.py` | `BaseADKAgent` and specialized ADK agents — wraps each tool call with policy enforcement, trajectory tracking (`AgentAction`), and per-action timing (`duration_seconds`) |
| `adk/tools.py` | Raw tool functions that launch simulation scripts as subprocesses |
| `adk/policies.py` | Policy registry with guardrails (e.g., "LLM cannot decide" — decisions must come from deterministic rules) |
| `adk/evals.py` | Agent evaluation framework |

**ADK Agent classes** (all in `adk/agent.py`):

| Class | Tool Function | Wraps Script |
|-------|--------------|-------------|
| `DataPrepAgent` | `prepare_data_tool()` | `00_prepare_data.py` |
| `CHAAgent` | `run_cha_tool()` | `01_run_cha.py` |
| `DHAAgent` | `run_dha_tool()` | `02_run_dha.py` |
| `EconomicsAgent` | `run_economics_tool()` | `03_run_economics.py` |
| `DecisionAgent` | `run_decision_tool()` | `cli/decision.py` |
| `UHDCAgent` | `run_uhdc_tool()` | `cli/uhdc.py` |

Each ADK agent produces an `AgentAction` dataclass containing:
- `name`, `phase`, `parameters`
- `result` (tool output dict)
- `status` (`"success"` / `"error"`)
- `timestamp`, `duration_seconds`
- `error` (if any)

### Layer 5: Simulation Engines

**CHA — Centralized Heating Analysis** (`cha/`)

| Module | Purpose |
|--------|---------|
| `network_builder.py` | Builds pandapipes networks from GIS building data |
| `network_builder_trunk_spur.py` | Trunk-spur topology construction |
| `convergence_optimizer.py` | Iterative optimization for numerical convergence |
| `convergence_optimizer_spur.py` | Spur-specific convergence optimization |
| `kpi_extractor.py` | Extracts EN 13941-1 compliance KPIs (velocity, pressure drop) |
| `qgis_export.py` | Generates interactive Folium maps (velocity, temperature, pressure layers) |
| `sizing.py` / `sizing_catalog.py` | Pipe sizing from manufacturer catalogs |
| `hydraulic_checks.py` | Hydraulic compliance checks |
| `thermal_checks.py` | Thermal compliance checks |
| `heat_loss.py` | Heat loss calculation |
| `geospatial_checks.py` | GIS geometry validation |
| `design_validator.py` | Design parameter validation |
| `robustness_checks.py` | Network robustness analysis |
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
| `base_loads.py` / `bdew_base_loads.py` | Base electrical load profiles |
| `mapping.py` | Grid visualization mapping |
| `export.py` | Result export utilities |
| `config.py` | DHA parameters (COP, power factor, simultaneity) |

**Economics** (`economics/`)

| Module | Purpose |
|--------|---------|
| `lcoh.py` | Levelized Cost of Heat calculation (Capital Recovery Factor method) |
| `co2.py` | CO2 emissions calculation (fuel-specific emission factors) |
| `monte_carlo.py` | Monte Carlo uncertainty propagation (default N=500, configurable) |
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
| `io.py` | File I/O utilities for report artifacts |

### Layer 6: Validation

| Module | Purpose |
|--------|---------|
| `validation/logic_auditor.py` | `ClaimExtractor` — regex-based quantitative claim extraction (13 patterns for CO2, LCOH, pressure, Monte Carlo, etc.) with cross-validation against reference KPIs |
| `validation/tnli_model.py` | `TNLIModel` / `LightweightValidator` — Tabular Natural Language Inference: rule-based entailment/contradiction detection with optional Gemini LLM backend |
| `validation/claims.py` | Structured claim extraction from LLM explanations |
| `validation/monitoring.py` | Validation monitoring and feedback loops |
| `validation/feedback_loop.py` | Validation feedback loop management |
| `validation/config.py` | Validation configuration |

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
| `config/__init__.py` | Centralized path resolution — `DATA_RAW`, `DATA_PROCESSED`, `RESULTS_ROOT`, `resolve_cluster_path()` |

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
│  Output: agent_plan = ["cha", "dha", "economics"]       │
│          (mapped via _create_agent_plan in executor)     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  AGENT 6: Dynamic Executor                              │
│  Duty: Delegate to domain agents in dependency order    │
│                                                          │
│  For each agent in plan:                                │
│    domain_agent.execute(street_id, context)             │
│      → Cache check (file-based: JSON, pickle)           │
│      → If miss: delegate to ADK Agent → Tool → Engine   │
│      → Timed log: "✓ Used cached CHA (0.002s)"         │
│                                                          │
│  _integrate_results() → flat dict for UI                │
│  Output: KPIs, execution_log, agent_results,            │
│          map_paths, total_execution_time                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  RESPONSE FORMATTER (in orchestrator)                   │
│  _format_executor_response() + _format_answer()         │
│  _create_viz() + _enrich_decision_data()                │
│  Produces: { type, answer, data, visualization,         │
│              execution_log, agent_trace, suggestions }   │
└─────────────────────────────────────────────────────────┘
```

### Delegation Chain (for a single agent, e.g., CHA)

```
DynamicExecutor._run_agent_plan()
  │
  ▼ delegates to
CHAAgent.execute()                         [domain_agents.py]
  │ 1. _check_cha_cache() → cha_kpis.json + network.pickle exist?
  │ 2. If cached: return AgentResult(cache_hit=True)
  │ 3. If miss:
  ▼ delegates to
ADKCHAAgent.run()                          [adk/agent.py]
  │ 1. enforce_guardrails() → policy check
  │ 2. start = time.perf_counter()
  ▼ calls
run_cha_tool(cluster_id, ...)              [adk/tools.py]
  │ 1. Launches 01_run_cha.py
  │ 2. pandapipes pipeflow simulation
  │ 3. KPI extraction, map generation
  ▼ returns
AgentAction(status, result, duration_seconds, timestamp)
  │
  ▼ wraps into
AgentResult(success, data, execution_time, cache_hit, metadata)
```

### Follow-Up Query Flow (Multi-Turn)

```
User: "Compare CO2 for Heinrich-Zille-Straße"
  → Full pipeline → Results for ST010

User: "What about LCOH?"              (follow-up detected)
  → Agent 1: intent=LCOH_COMPARISON
  → Agent 2: memory_street=ST010 (from previous turn)
  → Agent 3: Resolves to ST010 via conversation memory
  → Agent 4-6: Executes LCOH — CHA/DHA cached, only Economics runs
  → Execution log: "✓ Used cached CHA (0.002s)",
                   "✓ Used cached DHA (0.001s)",
                   "✓ Calculated ECONOMICS (2.3s)"

User: "What if we remove 2 houses?"   (follow-up detected)
  → Agent 1: intent=WHAT_IF_SCENARIO, modification="remove 2 houses"
  → Agent 6: Executor delegates to WhatIfAgent
  → WhatIfAgent: loads cached network.pickle, clones, removes 2
    heat consumers, re-runs pandapipes pipeflow, compares baseline
    vs scenario (pressure, heat, violations)
```

---

## Complete Agent Inventory

The system contains **21 agents** organized into four tiers: the main request pipeline, domain specialist agents, ADK policy-enforced agents, and specialized agents.

### Tier 1: Request Pipeline Agents (execute on every query)

These 6 agents run sequentially inside `BranitzOrchestrator.route_request()` for every user query. Each agent logs its duty and outcome to the **agent trace**, which is visible in the UI for full transparency.

#### Agent 1: NLU Intent Classifier

| | |
|---|---|
| **File** | `nlu/intent_classifier.py` |
| **Class/Function** | `classify_intent()` |
| **Duty** | Classify the user's natural language query into a structured intent and extract entities (street names, parameters) |
| **How it works** | Sends the query to Google Gemini LLM with a constrained system prompt that defines the supported intents. If the LLM is unavailable, falls back to keyword matching against known patterns. Street entities are extracted using fuzzy matching with German name normalization (handles `ss`/`ß`, `Straße`/`Strasse` variants). |
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
| **Output** | `{ resolved_cluster_id: "ST010_HEINRICH_ZILLE_STRASSE", method: "resolved from NLU entity" }` |

#### Agent 4: Capability Guardrail

| | |
|---|---|
| **File** | `agents/fallback.py` |
| **Class** | `CapabilityGuardrail` |
| **Duty** | Validate whether the system can handle the request before any execution begins. If not, return a structured fallback with alternatives and research context. |
| **How it works** | Checks the intent against an explicit registry of `UNSUPPORTED_INTENTS` (add_consumer, remove_pipe, real_time_scada, legal_compliance_check, multi_street_optimization). Also scans the query text for unsupported keywords. For `WHAT_IF_SCENARIO`, checks if the specific modification type is supported (removing houses = yes, changing pipe material = no). When blocking, generates a response with alternative suggestions, a research note explaining why this is a thesis boundary, and an escalation path. Uses `FallbackLLM` (Gemini) for context-aware explanations. |
| **Input** | Intent + entities + raw user query |
| **Output (if blocked)** | `{ can_handle: false, category: "unsupported", message: "...", alternative_suggestions: [...], research_note: "...", is_research_boundary: true }` |

#### Agent 5: Execution Planner

| | |
|---|---|
| **File** | `nlu/intent_mapper.py` + `agents/executor.py` (`_create_agent_plan`) |
| **Data** | `INTENT_TO_PLAN` dictionary + executor plan mapping |
| **Duty** | Determine which domain agents are required for the given intent |
| **How it works** | Maps each intent to a dependency-ordered list of domain agent keys. The executor's `_create_agent_plan()` defines the definitive plan: e.g., `CO2_COMPARISON → ["cha", "dha", "economics"]`. Unknown intents get the default plan `["cha", "dha", "economics"]`. An optional `needs_data_prep` context flag prepends `"data_prep"`. |
| **Input** | Intent + context |
| **Output** | `{ agent_plan: ["cha", "dha", "economics"] }` |

#### Agent 6: Dynamic Executor

| | |
|---|---|
| **File** | `agents/executor.py` |
| **Class** | `DynamicExecutor` |
| **Duty** | Delegate to domain agents in dependency order, integrate results into flat dicts for the UI |
| **How it works** | Lazily initializes 8 domain agent instances on first use. For each agent in the plan: calls `agent.execute(street_id, context)`. Each domain agent internally checks its file-based cache (JSON, pickle) and either returns cached data or delegates to its corresponding ADK agent. The executor collects all `AgentResult` objects, builds a timed execution log (e.g., `"✓ Used cached CHA (0.002s)"`), and calls `_integrate_results()` which dispatches to intent-specific format methods (`_format_co2`, `_format_lcoh`, `_format_violations`, `_format_decision`, `_format_what_if`, `_format_network_design`). Critical agent failures (CHA, DHA, Economics) stop the pipeline early. |
| **Input** | Intent + street_id + context (modification parameters) |
| **Output** | `{ dh_tons_co2: 45.2, hp_tons_co2: 67.3, winner: "DH", execution_log: ["✓ Used cached CHA (0.002s)", "✓ Calculated DHA (12.1s)"], agent_results: {...}, total_execution_time: 15.3 }` |

### Tier 2: Domain Agents (specialist station agents, called by executor)

These 8 agents are defined in `agents/domain_agents.py`. Each inherits from `BaseDomainAgent` and implements `can_handle()` + `execute()`. They are instantiated once per executor and reused across requests.

| # | Agent | Duty | Cache Check | Delegates To |
|---|-------|------|-------------|-------------|
| 7 | **DataPrepAgent** | Prepare raw GIS data into pipeline-ready Parquet | `buildings.parquet` + cluster map + profiles exist | ADK DataPrepAgent |
| 8 | **CHAAgent** | District heating hydraulic-thermal simulation | `cha_kpis.json` + `network.pickle` exist | ADK CHAAgent |
| 9 | **DHAAgent** | Heat pump LV grid power flow analysis | `dha_kpis.json` exists | ADK DHAAgent |
| 10 | **EconomicsAgent** | LCOH, CO2, Monte Carlo analysis | `economics_deterministic.json` exists; prerequisites: CHA + DHA | ADK EconomicsAgent |
| 11 | **DecisionAgent** | Deterministic decision evaluation + LLM explanation | `decision_{cluster_id}.json` exists; prerequisite: Economics | ADK DecisionAgent |
| 12 | **ValidationAgent** | Two-stage validation: ClaimExtractor (regex) + TNLIModel (semantic) | N/A (stateless) | Direct (no ADK agent) |
| 13 | **UHDCAgent** | Full HTML/Markdown/JSON report generation | N/A; prerequisite: Decision | ADK UHDCAgent |
| 14 | **WhatIfAgent** | Clone network, disable houses, re-run pipeflow, compare scenarios | N/A (uses CHA cache for baseline) | CHAAgent + pandapipes (direct) |

### Tier 3: ADK Agents (policy-enforced tool wrappers)

These 6 agents are defined in `adk/agent.py`. Each inherits from `BaseADKAgent` and wraps a single tool function with:
- **Policy enforcement** via `adk/policies.py` (e.g., "LLM cannot decide")
- **Trajectory tracking** via `AgentTrajectory` / `AgentAction` dataclasses
- **Per-action timing** via `time.perf_counter()` → `duration_seconds`

| # | ADK Agent | Tool Function | Script |
|---|-----------|--------------|--------|
| 15 | `DataPrepAgent` | `prepare_data_tool()` | `00_prepare_data.py` |
| 16 | `CHAAgent` | `run_cha_tool()` | `01_run_cha.py` |
| 17 | `DHAAgent` | `run_dha_tool()` | `02_run_dha.py` |
| 18 | `EconomicsAgent` | `run_economics_tool()` | `03_run_economics.py` |
| 19 | `DecisionAgent` | `run_decision_tool()` | `cli/decision.py` |
| 20 | `UHDCAgent` | `run_uhdc_tool()` | `cli/uhdc.py` |

### Tier 4: Specialized Agents

| # | Agent | File | How It Works |
|---|-------|------|-------------|
| 21 | **Fallback LLM** | `agents/fallback.py` (`FallbackLLM`) | Generates context-aware natural language explanations for unsupported requests. Uses Gemini to explain *why* a request cannot be fulfilled and suggests what the user can do instead. Falls back to templates if the API is unavailable. |

### Agent Communication Flow

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│           PIPELINE AGENTS (sequential)                        │
│                                                                │
│  [1] NLU ──► [2] Conversation ──► [3] Street Resolver         │
│                                          │                     │
│                                          ▼                     │
│  [4] Guardrail ──► [5] Planner ──► [6] Executor              │
│       │                                  │                     │
│       │ (if blocked)                     │ (delegates to)      │
│       ▼                                  ▼                     │
│  [21] Fallback LLM         [7-14] Domain Agents               │
│                                          │ (delegates to)      │
│                                          ▼                     │
│                              [15-20] ADK Agents               │
│                                          │ (calls)             │
│                                          ▼                     │
│                              ADK Tools → Simulation Engines    │
│                                          │                     │
│                                          ▼                     │
│                              [12] ValidationAgent (on demand)  │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
Structured Response
{ type, answer, data, agent_trace, execution_log, suggestions }
```

### Agent Trace Example

Every request produces a full agent trace representing the data flow logically, translated into a real-time branching SVG in the UI. Example for "Compare CO2 for Heinrich-Zille-Straße":

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
    "method": "resolved from NLU entity"
  },
  {
    "agent": "Capability Guardrail",
    "duty": "Validate request is within system boundaries",
    "can_handle": true
  },
  {
    "agent": "Execution Planner",
    "duty": "Determine required simulations for CO2_COMPARISON",
    "required_tools": ["cha", "dha", "economics"]
  },
  {
    "agent": "Dynamic Executor",
    "duty": "Execute CO2_COMPARISON for ST010 (agent-based, lazy)",
    "outcome": "success",
    "total_execution_time": 0.012,
    "execution_log": [
      "✓ Used cached CHA (0.002s)",
      "✓ Used cached DHA (0.001s)",
      "✓ Used cached ECONOMICS (0.003s)"
    ],
    "agents_invoked": {
      "cha": { "success": true, "cache_hit": true, "execution_time": 0.002 },
      "dha": { "success": true, "cache_hit": true, "execution_time": 0.001 },
      "economics": { "success": true, "cache_hit": true, "execution_time": 0.003 }
    }
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
                         ▼  [DataPrepAgent → 00_prepare_data.py]
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
│ CHAAgent     │ │ DHAAgent     │ │EconomicsAgent│
│ → ADK CHA   │ │ → ADK DHA   │ │ → ADK Econ.  │
│ → run_cha   │ │ → run_dha   │ │ → run_econom │
│   _tool()   │ │   _tool()   │ │   _tool()    │
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
              │  DecisionAgent   │
              │  → ADK Decision  │
              │  → rules.py      │
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
          ┌────────────┼────────────┐
          ▼                         ▼
┌──────────────────┐     ┌──────────────────┐
│  UHDCAgent       │     │ ValidationAgent  │
│  → ADK UHDC      │     │ ClaimExtractor   │
│  LLM explanation │     │ + TNLIModel      │
│  + report gen    │     │ (rule-based +    │
│                  │     │  optional LLM)   │
└────────┬─────────┘     └──────────────────┘
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
│   └── monte_carlo_samples.parquet     # Raw MC samples (N configurable; default 500)
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
| LLM / NLU | **Google Gemini API** (`google-genai`) | Intent classification, decision explanations |
| Explanation Validation | **TNLI** (`LightweightValidator` — rule-based + optional Gemini LLM) | Entailment/contradiction detection |
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
| **Phase 2** | Dynamic Executor + Domain Agents | Lazy simulation execution with agent delegation and file-based caching |
| **Phase 3** | Conversation Manager | Multi-turn context, follow-up detection, reference resolution |
| **Phase 4** | UHDC + Validation | LLM decision explanations with ClaimExtractor + TNLI safety validation |
| **Phase 5** | Capability Guardrail | Explicit boundaries, graceful "I don't know" fallback, research context |

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

3. **Install the package in editable mode** (recommended):

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
│   │   │   ├── __init__.py     #   Package exports (all agents + registry)
│   │   │   ├── orchestrator.py #   Layer 1: Central coordinator (6-agent pipeline)
│   │   │   ├── executor.py     #   Layer 2: Dynamic execution engine (agent delegation)
│   │   │   ├── domain_agents.py#   Layer 2.5: 8 domain agents + AGENT_REGISTRY
│   │   │   ├── conversation.py #   Conversation state manager
│   │   │   └── fallback.py     #   Capability guardrail + FallbackLLM
│   │   │
│   │   ├── adk/                # Agent Development Kit
│   │   │   ├── agent.py        #   Layer 3: ADK agents (policy + trajectory + timing)
│   │   │   ├── tools.py        #   Layer 4: Raw tool functions (subprocess launchers)
│   │   │   ├── policies.py     #   Policy registry + guardrails
│   │   │   └── evals.py        #   Agent evaluation framework
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
│   │   ├── validation/         # ClaimExtractor + TNLI validation
│   │   ├── data/               # Data loading and processing
│   │   ├── ui/                 # Streamlit UI components
│   │   ├── cli/                # CLI entry points (decision, economics, uhdc, validate)
│   │   └── config/             # Centralized configuration + path resolution
│   │
│   └── scripts/                # Pipeline entry points
│       ├── 00_prepare_data.py
│       ├── 01_run_cha.py
│       ├── 01_run_cha_trunk_spur.py
│       ├── 01_run_cha_with_validation.py
│       ├── 02_run_dha.py
│       ├── 03_run_economics.py
│       ├── generate_thesis_figures.py
│       ├── serve_maps.py
│       └── run_chat_ui.py
│
├── tests/                      # Test suite
│   ├── test_phase1_intent.py   #   Intent classification tests
│   ├── test_phase2_execution.py#   Execution pipeline tests
│   ├── test_capability_guardrail.py # Guardrail tests
│   └── test_consistency.py     #   Determinism / consistency tests
│
├── docs/                       # Documentation and checklists
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
PYTHONPATH=src pytest tests/test_phase1_intent.py -v
PYTHONPATH=src pytest tests/test_phase2_execution.py -v
PYTHONPATH=src pytest tests/test_capability_guardrail.py -v
PYTHONPATH=src pytest tests/test_consistency.py -v
```

---

## License

This project is part of a Master's thesis research at BTU Cottbus-Senftenberg. All rights reserved.
