# Implementation Checklist: Hierarchical Agent Architecture

> **File**: `src/branitz_heat_decision/agents/domain_agents.py`
> **Verified**: 2026-01-25
> **Total Lines**: 987

---

## Architecture Overview

```
Layer 1: BranitzOrchestrator (orchestrator.py)
    ↓ route_request() → classify intent, resolve street, check guardrail
Layer 2: DynamicExecutor (executor.py)
    ↓ _run_agent_plan() → dependency-ordered agent execution
Layer 2.5: Domain Agents (domain_agents.py)    ← THIS FILE
    ↓ execute() → cache check → delegate to ADK agent
Layer 3: ADK Agents (adk/agent.py)
    ↓ _execute_tool() → policy enforcement + trajectory tracking
Layer 4: ADK Tools (adk/tools.py)
    - run_cha_tool(), run_dha_tool(), run_economics_tool(), etc.
```

---

## Phase 1: Core Infrastructure

### AgentResult Dataclass
- [x] Create `AgentResult` dataclass (line 46)
- [x] Field: `success: bool`
- [x] Field: `data: Dict[str, Any]`
- [x] Field: `execution_time: float`
- [x] Field: `cache_hit: bool`
- [x] Field: `agent_name: str`
- [x] Field: `metadata: Dict[str, Any]`
- [x] Field: `errors: list = None`
- [x] `__post_init__` initializes empty errors list (line 57)

### BaseDomainAgent Abstract Class
- [x] Create `BaseDomainAgent(ABC)` (line 62)
- [x] `__init__(self, cache_dir: str = "./cache")` — stores cache_dir and agent_name (lines 68-70)
- [x] Abstract method `can_handle(self, intent, context) -> bool` (line 72)
- [x] Abstract method `execute(self, street_id, context) -> AgentResult` (line 77)
- [x] Helper method `_check_cache(self, street_id) -> tuple[bool, Any]` (line 85)
- [x] Helper method `_update_cache(self, street_id, result)` (line 89)

### ADK Agent Delegation Layer
- [x] Lazy import function `_get_adk_agents()` (line 24)
- [x] Imports `ADKCHAAgent`, `ADKDHAAgent`, `ADKEconomicsAgent`, `ADKDecisionAgent`, `ADKUHDCAgent`, `ADKDataPrepAgent`, `AgentAction`
- [x] Uses import aliases to avoid name collision with domain agent classes

---

## Phase 2: Domain Agent Implementations

### 1. DataPrepAgent (line 99)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["DATA_PREPARATION", "PREPARE_DATA", "LOAD_DATA"]`
- [x] Cache check: `_is_data_prepared()` verifies `BUILDINGS_PATH`, `BUILDING_CLUSTER_MAP_PATH`, `HOURLY_PROFILES_PATH` exist
- [x] Delegates to: `ADKDataPrepAgent.run(buildings_path, streets_path)`
- [x] Returns `AgentResult` with `adk_timestamp`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | `adk.agent.DataPrepAgent` |
| ADK Tool | `prepare_data_tool` (adk/tools.py) |
| Script | `src/scripts/00_prepare_data.py` |
| Cache Files | `buildings.parquet`, `building_cluster_map.parquet`, `hourly_profiles.parquet` |
| Config Refs | `BUILDINGS_PATH`, `BUILDING_CLUSTER_MAP_PATH`, `HOURLY_PROFILES_PATH` |

---

### 2. CHAAgent — District Heating Specialist (line 162)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["CHA_SIMULATION", "DISTRICT_HEATING", "VIOLATION_ANALYSIS", "NETWORK_DESIGN", "CO2_COMPARISON", "LCOH_COMPARISON", "WHAT_IF_SCENARIO"]`
- [x] Cache check: `_check_cha_cache()` verifies `cha_kpis.json` + `network.pickle` exist (line 236)
- [x] On cache hit: loads and returns KPIs from JSON
- [x] On miss: delegates to `ADKCHAAgent.run(use_trunk_spur, plant_wgs84_lat, plant_wgs84_lon, optimize_convergence)`
- [x] Parses `cha_kpis.json` for structured KPI data after tool run
- [x] Returns `AgentResult` with `convergence_status`, `outputs_created`, `adk_timestamp`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | `adk.agent.CHAAgent` |
| ADK Tool | `run_cha_tool` (adk/tools.py) |
| Script | `src/scripts/01_run_cha.py` |
| Cache Files | `results/cha/{cluster_id}/cha_kpis.json`, `results/cha/{cluster_id}/network.pickle` |
| Output Maps | `interactive_map.html`, `interactive_map_temperature.html`, `interactive_map_pressure.html` |
| Engine | pandapipes pipeflow (DH hydraulic simulation) |
| Config | `resolve_cluster_path(street_id, "cha")` |

---

### 3. DHAAgent — Heat Pump Grid Specialist (line 252)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["DHA_SIMULATION", "HEAT_PUMP", "LV_GRID", "HOSTING_CAPACITY", "VOLTAGE_ANALYSIS", "CO2_COMPARISON", "LCOH_COMPARISON"]`
- [x] Cache check: `_check_dha_cache()` verifies `dha_kpis.json` exists (line 324)
- [x] Delegates to: `ADKDHAAgent.run(cop, hp_three_phase, grid_source)`
- [x] Parses `dha_kpis.json` for structured KPI data after tool run
- [x] Returns `AgentResult` with `voltage_violations`, `line_violations`, `adk_timestamp`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | `adk.agent.DHAAgent` |
| ADK Tool | `run_dha_tool` (adk/tools.py) |
| Script | `src/scripts/02_run_dha.py` |
| Cache Files | `results/dha/{cluster_id}/dha_kpis.json` |
| Engine | pandapower power flow (LV grid analysis) |
| Parameters | `cop=2.8`, `hp_three_phase=True`, `grid_source="legacy_json"` |
| Config | `resolve_cluster_path(street_id, "dha")` |

---

### 4. EconomicsAgent — Cost Analysis Specialist (line 335)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["ECONOMICS", "LCOH_COMPARISON", "CO2_COMPARISON", "COST_ANALYSIS", "MONTE_CARLO"]`
- [x] Prerequisites check: verifies CHA (`cha_kpis.json`) and DHA (`dha_kpis.json`) results exist first (lines 353-365)
- [x] Cache check: `_check_economics_cache()` verifies `economics_deterministic.json` exists (line 435)
- [x] Delegates to: `ADKEconomicsAgent.run(n_samples, seed)`
- [x] Loads `economics_deterministic.json` for structured data after tool run
- [x] Calculates winner (DH vs HP) by comparing LCOH and stores in metadata (lines 417-421)
- [x] Returns `AgentResult` with `lcoh_dh`, `lcoh_hp`, `co2_dh`, `co2_hp`, `winner`, `adk_timestamp`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | `adk.agent.EconomicsAgent` |
| ADK Tool | `run_economics_tool` (adk/tools.py) |
| Script | `src/scripts/03_run_economics.py` |
| Cache Files | `results/economics/{cluster_id}/economics_deterministic.json` |
| Prerequisites | CHA results (`cha_kpis.json`), DHA results (`dha_kpis.json`) |
| Parameters | `n_samples=500`, `seed=42` |
| Engine | LCOH calculation, CO2 emissions, Monte Carlo simulation |
| Config | `resolve_cluster_path(street_id, "economics")` |

---

### 5. DecisionAgent — Recommendation Specialist (line 446)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["DECISION", "RECOMMENDATION", "EXPLAIN_DECISION", "FINAL_CHOICE", "WHAT_SHOULD_WE_DO"]`
- [x] Prerequisites check: economics must exist (line 464)
- [x] Cache check: `_check_decision_cache()` verifies `decision_{cluster_id}.json` exists (line 534)
- [x] Delegates to: `ADKDecisionAgent.run(llm_explanation, explanation_style, no_fallback)`
- [x] Extracts decision, robust status, reason code from result (lines 508-527)
- [x] Returns `AgentResult` with `choice`, `robust`, `winner`, `reason_code`, `adk_timestamp`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | `adk.agent.DecisionAgent` |
| ADK Tool | `run_decision_tool` (adk/tools.py) |
| Script | `cli/decision.py` |
| Cache Files | `results/decision/{cluster_id}/decision_{cluster_id}.json` |
| Prerequisites | Economics results (`economics_deterministic.json`) |
| Parameters | `llm_explanation=True`, `explanation_style="executive"`, `no_fallback=False` |
| Engine | Deterministic rules engine + LLM explanation generation |
| Config | `resolve_cluster_path(street_id, "decision")` |

---

### 6. ValidationAgent — QA/Logic Auditor Specialist (line 544)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["VALIDATE", "AUDIT", "CHECK_CLAIMS", "VERIFY_EXPLANATION"]`
- [x] **Stage 1: ClaimExtractor** — regex-based quantitative claim extraction (line 606)
  - [x] Cross-validates LCOH DH, LCOH HP, CO2 DH, CO2 HP against KPIs
  - [x] Tolerance: `abs(claim - expected) > 0.1` triggers mismatch
- [x] **Stage 2: TNLIModel** — Tabular NLI semantic validation (line 636)
  - [x] Splits explanation into sentences
  - [x] Validates each sentence against merged KPIs (economics + decision)
  - [x] Reports: `tnli_verified`, `tnli_contradictions`, per-sentence results
  - [x] Graceful fallback: if TNLI fails, logs warning and continues
- [x] Merges decision data (`choice`, `robust`, `reason_codes`, `dh_wins_fraction`, etc.) into KPIs for TNLI
- [x] Returns mismatch count and validation status in metadata
- [x] Returns `AgentResult` with `claims_extracted`, `mismatches`, `tnli_results`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | None (uses validation module directly) |
| Validation Module | `validation.logic_auditor.ClaimExtractor` |
| TNLI Module | `validation.tnli_model.TNLIModel` (LightweightValidator) |
| TNLI Backend | Rule-based + optional Gemini LLM (`GOOGLE_API_KEY`) |
| KPI Sources | `economics_deterministic.json`, `decision_{cluster_id}.json` |
| Validation Types | Quantitative (regex claims) + Qualitative (TNLI entailment) |
| Labels | `Entailment`, `Neutral`, `Contradiction` |
| Config | `resolve_cluster_path(street_id, "economics")`, `resolve_cluster_path(street_id, "decision")` |

---

### 7. UHDCAgent — Report Generation Specialist (line 687)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["UHDC", "REPORT", "GENERATE_REPORT", "FINAL_OUTPUT"]`
- [x] Prerequisites check: decision must exist (`decision_{cluster_id}.json`) (line 702)
- [x] Delegates to: `ADKUHDCAgent.run(llm, style, format)`
- [x] Returns report paths (HTML, Markdown, JSON)
- [x] Returns `AgentResult` with `formats_generated`, `all_outputs_exist`, `adk_timestamp`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | `adk.agent.UHDCAgent` |
| ADK Tool | `run_uhdc_tool` (adk/tools.py) |
| Script | `cli/uhdc.py` |
| Prerequisites | Decision results (`decision_{cluster_id}.json`) |
| Parameters | `llm=True`, `style="executive"`, `format="all"` |
| Output Formats | HTML, Markdown, JSON |
| Config | `resolve_cluster_path(street_id, "decision")` |

---

### 8. WhatIfAgent — Scenario Modification Specialist (line 753)
- [x] Inherits from `BaseDomainAgent`
- [x] `can_handle`: `["WHAT_IF_SCENARIO", "WHAT_IF", "SCENARIO_ANALYSIS"]`
- [x] Step 1: Ensures baseline CHA network exists via `CHAAgent` (line 790)
- [x] Step 2: Loads baseline `network.pickle` (line 818)
- [x] Step 3: Clones network with `pickle.loads(pickle.dumps(...))` (line 822)
- [x] Step 4: Applies modification — parses "remove N houses" via `_parse_house_count()` (line 824)
- [x] Step 5: Disables heat consumers via `_exclude_houses()` (line 828)
- [x] Step 6: Re-runs pipeflow `pp.pipeflow(scenario_net, ...)` (line 843)
- [x] Step 7: Compares baseline vs scenario via `_compare_scenarios()` (line 857)
- [x] Returns pressure change, heat delivered change, violation reduction
- [x] Returns `AgentResult` with `houses_removed`, `modification_log`, `cha_cache_hit`

**Tools & Environment:**
| Component | Detail |
|---|---|
| ADK Agent | None (uses pandapipes directly for network manipulation) |
| Internal Agent | `CHAAgent` (for baseline CHA) |
| Engine | pandapipes `pipeflow(mode="all", iter=100, tol_p=1e-4, tol_v=1e-4)` |
| Network Source | `results/cha/{cluster_id}/network.pickle` |
| Helpers | `_parse_house_count()`, `_exclude_houses()`, `_calculate_dh_co2()`, `_get_max_pressure()`, `_count_violations()`, `_compare_scenarios()` |
| Modification | Disables `heat_consumer.in_service=False`, `qext_w=0.0` |
| Comparison Metrics | `pressure_change_bar`, `heat_delivered_change_mw`, `violation_reduction` |
| Config | `resolve_cluster_path(street_id, "cha")` |

---

## Phase 3: Agent Registry & Factory

### AGENT_REGISTRY (line 970)
- [x] Key `"data_prep"` → `DataPrepAgent`
- [x] Key `"cha"` → `CHAAgent`
- [x] Key `"dha"` → `DHAAgent`
- [x] Key `"economics"` → `EconomicsAgent`
- [x] Key `"decision"` → `DecisionAgent`
- [x] Key `"validation"` → `ValidationAgent`
- [x] Key `"uhdc"` → `UHDCAgent`
- [x] Key `"what_if"` → `WhatIfAgent`
- [x] Values are **classes** (not instances)

### get_agent() Factory Function (line 982)
- [x] Looks up `agent_name` in `AGENT_REGISTRY`
- [x] Raises `ValueError` for unknown agents
- [x] Error message lists available agents: `list(AGENT_REGISTRY.keys())`
- [x] Passes `**kwargs` to agent constructor

---

## Phase 4: Executor Integration

### DynamicExecutor Agent Registry (executor.py, line 81)
- [x] Lazily initializes 8 agent **instances** via `_ensure_agents()`
- [x] `"data_prep"` → `DataPrepAgent(cache_dir)`
- [x] `"cha"` → `CHAAgent(cache_dir)`
- [x] `"dha"` → `DHAAgent(cache_dir)`
- [x] `"economics"` → `EconomicsAgent(cache_dir)`
- [x] `"decision"` → `DecisionAgent(cache_dir)`
- [x] `"validation"` → `ValidationAgent(cache_dir)`
- [x] `"uhdc"` → `UHDCAgent(cache_dir)`
- [x] `"what_if"` → `WhatIfAgent(cache_dir)`

### Executor Agent Plans (executor.py, line 147)
- [x] `CO2_COMPARISON` → `["cha", "dha", "economics"]`
- [x] `LCOH_COMPARISON` → `["cha", "dha", "economics"]`
- [x] `VIOLATION_ANALYSIS` → `["cha", "dha"]`
- [x] `NETWORK_DESIGN` → `["cha"]`
- [x] `WHAT_IF_SCENARIO` → `["what_if"]`
- [x] `DECISION` → `["cha", "dha", "economics", "decision"]`
- [x] `EXPLAIN_DECISION` → `["cha", "dha", "economics", "decision"]`
- [x] `FULL_REPORT` → `["cha", "dha", "economics", "decision", "uhdc"]`
- [x] `DATA_PREPARATION` → `["data_prep"]`
- [x] Default fallback → `["cha", "dha", "economics"]`
- [x] Optional `needs_data_prep` context flag prepends `"data_prep"`

### Executor Has No Direct Tool Calls
- [x] Zero `from branitz_heat_decision.adk.tools import` in `executor.py`
- [x] Zero `from branitz_heat_decision.adk.tools import` in `agents/` directory
- [x] All tool execution goes through: Domain Agent → ADK Agent → ADK Tool

---

## Phase 5: Module Exports

### agents/__init__.py
- [x] Exports `BranitzOrchestrator`
- [x] Exports `DynamicExecutor`
- [x] Exports `AgentResult`
- [x] Exports `BaseDomainAgent`
- [x] Exports `DataPrepAgent`
- [x] Exports `CHAAgent`
- [x] Exports `DHAAgent`
- [x] Exports `EconomicsAgent`
- [x] Exports `DecisionAgent`
- [x] Exports `ValidationAgent`
- [x] Exports `UHDCAgent`
- [x] Exports `WhatIfAgent`
- [x] Exports `get_agent`
- [x] Exports conversation classes (`ConversationManager`, `ConversationMemory`, etc.)
- [x] Exports guardrail classes (`CapabilityGuardrail`, `CapabilityCategory`, etc.)

---

## Summary

| Checklist Item | Status |
|---|---|
| AgentResult dataclass (7 fields + __post_init__) | [x] |
| BaseDomainAgent abstract class (5 methods) | [x] |
| DataPrepAgent (cache + ADK delegation) | [x] |
| CHAAgent (cache + ADK delegation + KPI parsing) | [x] |
| DHAAgent (cache + ADK delegation + KPI parsing) | [x] |
| EconomicsAgent (prerequisites + cache + ADK + winner calc) | [x] |
| DecisionAgent (prerequisites + cache + ADK + decision extract) | [x] |
| ValidationAgent (ClaimExtractor + TNLI two-stage pipeline) | [x] |
| UHDCAgent (prerequisites + ADK delegation + report paths) | [x] |
| WhatIfAgent (CHA baseline + pandapipes clone/modify/compare) | [x] |
| AGENT_REGISTRY (8 entries, classes not instances) | [x] |
| get_agent() factory (ValueError with available list) | [x] |
| Executor agent registry (8 lazy instances) | [x] |
| Executor agent plans (9 intents + default + data_prep flag) | [x] |
| Zero direct tool calls in agents/ | [x] |
| Module exports in __init__.py | [x] |

**All 16 items implemented.** Architecture matches target hierarchy.

---
---

# Phase 2: Fix Module Exports

> **File**: `src/branitz_heat_decision/agents/__init__.py`
> **Verified**: 2026-01-25
> **Total Lines**: 55

---

## 2.1 Imports from domain_agents

**Implementation**: `src/branitz_heat_decision/agents/__init__.py` — lines 4-17

- [x] `AgentResult` imported from `.domain_agents`
- [x] `BaseDomainAgent` imported from `.domain_agents`
- [x] `DataPrepAgent` imported from `.domain_agents`
- [x] `CHAAgent` imported from `.domain_agents`
- [x] `DHAAgent` imported from `.domain_agents`
- [x] `EconomicsAgent` imported from `.domain_agents`
- [x] `DecisionAgent` imported from `.domain_agents`
- [x] `ValidationAgent` imported from `.domain_agents`
- [x] `UHDCAgent` imported from `.domain_agents`
- [x] `WhatIfAgent` imported from `.domain_agents`
- [x] `AGENT_REGISTRY` imported from `.domain_agents` *(was missing, added 2026-01-25)*
- [x] `get_agent` imported from `.domain_agents`

**`__all__` Exports** (lines 31-54):

- [x] `"AgentResult"` in `__all__`
- [x] `"BaseDomainAgent"` in `__all__`
- [x] `"DataPrepAgent"` in `__all__`
- [x] `"CHAAgent"` in `__all__`
- [x] `"DHAAgent"` in `__all__`
- [x] `"EconomicsAgent"` in `__all__`
- [x] `"DecisionAgent"` in `__all__`
- [x] `"ValidationAgent"` in `__all__`
- [x] `"UHDCAgent"` in `__all__`
- [x] `"WhatIfAgent"` in `__all__`
- [x] `"AGENT_REGISTRY"` in `__all__` *(was missing, added 2026-01-25)*
- [x] `"get_agent"` in `__all__`

---

## 2.2 Other Module Imports (sibling modules)

**Orchestrator** — `src/branitz_heat_decision/agents/__init__.py` line 2:

- [x] `BranitzOrchestrator` imported from `.orchestrator`
- [x] `"BranitzOrchestrator"` in `__all__`

**Executor** — `src/branitz_heat_decision/agents/__init__.py` line 3:

- [x] `DynamicExecutor` imported from `.executor`
- [x] `"DynamicExecutor"` in `__all__`

**Conversation** — `src/branitz_heat_decision/agents/__init__.py` lines 18-22:

- [x] `ConversationManager` imported from `.conversation`
- [x] `ConversationMemory` imported from `.conversation`
- [x] `ConversationState` imported from `.conversation`
- [x] `CalculationContext` imported from `.conversation`
- [x] All four in `__all__`

**Fallback / Guardrail** — `src/branitz_heat_decision/agents/__init__.py` lines 24-29:

- [x] `CapabilityGuardrail` imported from `.fallback`
- [x] `CapabilityCategory` imported from `.fallback`
- [x] `CapabilityResponse` imported from `.fallback`
- [x] `FallbackLLM` imported from `.fallback`
- [x] All four in `__all__`

---

## 2.3 Circular Import Verification

### Import Chain Analysis

The following table traces every import relationship between agents/ modules to verify no circular dependency exists:

| Source File | Imports From | Import Style | Circular Risk |
|---|---|---|---|
| `agents/__init__.py` | `.orchestrator` | **Top-level** | Low — orchestrator uses lazy imports internally |
| `agents/__init__.py` | `.executor` | **Top-level** | Low — executor uses lazy imports internally |
| `agents/__init__.py` | `.domain_agents` | **Top-level** | None — domain_agents imports only from `adk/`, `config`, `validation/` |
| `agents/__init__.py` | `.conversation` | **Top-level** | None — conversation is standalone |
| `agents/__init__.py` | `.fallback` | **Top-level** | None — fallback is standalone |
| `agents/orchestrator.py` | `agents.executor` | **Lazy** (`_get_executor()` at line 42) | None — deferred to runtime |
| `agents/orchestrator.py` | `agents.conversation` | **Lazy** (`_get_conversation()` at line 47) | None — deferred to runtime |
| `agents/orchestrator.py` | `agents.fallback` | **Lazy** (`_get_guardrail()` at line 52) | None — deferred to runtime |
| `agents/orchestrator.py` | `config` | **Top-level** (line 25) | None — config is leaf module |
| `agents/executor.py` | `agents.domain_agents` | **Lazy** (`_import_agents()` at line 25) | None — deferred to runtime |
| `agents/domain_agents.py` | `adk.agent` | **Lazy** (`_get_adk_agents()` at line 24) | None — adk is separate package layer |
| `agents/domain_agents.py` | `config` | **Lazy** (inside methods) | None — config is leaf module |
| `agents/domain_agents.py` | `validation.logic_auditor` | **Lazy** (inside `ValidationAgent.execute()`) | None — validation is leaf |
| `agents/domain_agents.py` | `validation.tnli_model` | **Lazy** (inside `ValidationAgent.execute()`) | None — validation is leaf |

### Verification Results

- [x] `orchestrator.py` does **NOT** import from `agents/__init__.py` (uses `branitz_heat_decision.agents.executor` directly via lazy function)
- [x] `executor.py` does **NOT** import from `agents/__init__.py` (uses `branitz_heat_decision.agents.domain_agents` directly via lazy function)
- [x] `domain_agents.py` does **NOT** import from `agents/__init__.py`, `orchestrator.py`, or `executor.py`
- [x] All cross-module imports within `agents/` are **lazy** (deferred inside functions, not at module top-level)
- [x] Only `__init__.py` uses top-level imports — it is the leaf in the import DAG
- [x] No circular dependency detected

### Consumers of `agents/__init__.py`

These files import from the public `branitz_heat_decision.agents` package and work correctly:

| Consumer File | Import | Status |
|---|---|---|
| `src/branitz_heat_decision/ui/app_intent_chat.py` (line 321) | `from branitz_heat_decision.agents import BranitzOrchestrator` | [x] Works |
| `src/branitz_heat_decision/ui/app_conversational.py` (line 59) | `from branitz_heat_decision.agents import BranitzOrchestrator` | [x] Works |
| `src/branitz_heat_decision/ui/app.py` (line 169) | `from branitz_heat_decision.agents import BranitzOrchestrator` | [x] Works |
| `src/branitz_heat_decision/cli/decision.py` (line 189) | `from branitz_heat_decision.agents import BranitzOrchestrator` | [x] Works |
| `src/branitz_heat_decision/cli/validate_bundle.py` (line 218) | `from branitz_heat_decision.agents import BranitzOrchestrator` | [x] Works |

---

## 2.4 Fix Applied

`AGENT_REGISTRY` was defined in `domain_agents.py` (line 970) but was **not** imported or listed in `__init__.py`. This has been fixed:

**Before:**
```python
from .domain_agents import (
    AgentResult,
    BaseDomainAgent,
    DataPrepAgent, CHAAgent, DHAAgent, EconomicsAgent,
    DecisionAgent, ValidationAgent, UHDCAgent, WhatIfAgent,
    get_agent,
)
```

**After:**
```python
from .domain_agents import (
    AgentResult,
    BaseDomainAgent,
    DataPrepAgent, CHAAgent, DHAAgent, EconomicsAgent,
    DecisionAgent, ValidationAgent, UHDCAgent, WhatIfAgent,
    AGENT_REGISTRY,
    get_agent,
)
```

---

## Phase 2 Summary

| Checklist Item | Status | Notes |
|---|---|---|
| Import `AgentResult` | [x] | line 5 |
| Import `BaseDomainAgent` | [x] | line 6 |
| Import `DataPrepAgent` | [x] | line 7 |
| Import `CHAAgent` | [x] | line 8 |
| Import `DHAAgent` | [x] | line 9 |
| Import `EconomicsAgent` | [x] | line 10 |
| Import `DecisionAgent` | [x] | line 11 |
| Import `ValidationAgent` | [x] | line 12 |
| Import `UHDCAgent` | [x] | line 13 |
| Import `WhatIfAgent` | [x] | line 14 |
| Import `AGENT_REGISTRY` | [x] | line 15 — **fixed** (was missing) |
| Import `get_agent` | [x] | line 16 |
| All 12 symbols in `__all__` | [x] | lines 31-45 |
| `BranitzOrchestrator` exported | [x] | line 2, 32 |
| `DynamicExecutor` exported | [x] | line 3, 33 |
| Conversation classes exported (4) | [x] | lines 18-22, 46-49 |
| Guardrail classes exported (4) | [x] | lines 24-29, 50-53 |
| No circular imports | [x] | All cross-module imports are lazy |
| Consumer files work | [x] | 5 consumers verified |

**All 19 items implemented.** One fix applied (`AGENT_REGISTRY` added to import + `__all__`).

---
---

# Phase 3: Refactor DynamicExecutor

> **File**: `src/branitz_heat_decision/agents/executor.py`
> **Verified**: 2026-01-25
> **Total Lines**: 399

---

## 3.1 Update Imports

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 1-19

### Top-Level Imports (lines 12-17)

- [x] `from __future__ import annotations`
- [x] `import logging`
- [x] `import time` — used for `time.perf_counter()` timing
- [x] `from pathlib import Path` — used for `self.cache_dir`
- [x] `from typing import Any, Dict, List, Optional, Tuple`

### Domain Agent Imports — Lazy (lines 25-47)

- [x] Imports deferred inside `_import_agents()` function (not top-level)
- [x] `AgentResult` imported from `branitz_heat_decision.agents.domain_agents`
- [x] `DataPrepAgent` imported
- [x] `CHAAgent` imported
- [x] `DHAAgent` imported
- [x] `EconomicsAgent` imported
- [x] `DecisionAgent` imported
- [x] `ValidationAgent` imported
- [x] `UHDCAgent` imported
- [x] `WhatIfAgent` imported
- [x] All 9 symbols returned as dict for lazy access (lines 37-47)

### Removed Imports (verified absent)

- [x] Zero `from branitz_heat_decision.adk.tools import` — no direct tool imports
- [x] Zero `import pandapipes` — no inline simulation engine
- [x] Zero `import pickle` — no inline network manipulation
- [x] Zero `from branitz_heat_decision.cha` / `from branitz_heat_decision.dha` — no direct simulation module imports
- [x] No `SimulationType` or `SimulationCache` classes (removed in previous refactor)

**Tools & Environment:**
| Component | Detail |
|---|---|
| Import Style | Lazy via `_import_agents()` — zero cost until first `execute()` |
| Import Source | `branitz_heat_decision.agents.domain_agents` |
| Why Lazy | Avoids circular deps; executor.py can load even if domain agents have heavy deps |

---

## 3.2 Update DynamicExecutor.__init__

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 50-90

### Class Docstring (lines 51-65)

- [x] Documents the 4-step delegation pattern: plan → delegate → integrate → return
- [x] Documents Speaker B requirements: lazy execution, cache-first, timed logs, what-if

### __init__ Method (lines 67-72)

- [x] Signature: `__init__(self, cache_dir: str = "./cache")`
- [x] `self.cache_dir = Path(cache_dir)` — converts to Path object
- [x] `self._agents: Optional[Dict[str, Any]] = None` — lazy placeholder
- [x] `self._agent_classes: Optional[Dict[str, Any]] = None` — lazy placeholder
- [x] No agent instances created at construction time (lazy pattern)

### _ensure_agents — Lazy Initialization (lines 75-90)

- [x] Guard clause: `if self._agents is not None: return` — only runs once
- [x] Calls `_import_agents()` to get class references
- [x] Stores class refs in `self._agent_classes`
- [x] Initializes 8 agent **instances** with `cache_dir`:

| Registry Key | Agent Class | Line |
|---|---|---|
| `"data_prep"` | `DataPrepAgent(cache)` | 82 |
| `"cha"` | `CHAAgent(cache)` | 83 |
| `"dha"` | `DHAAgent(cache)` | 84 |
| `"economics"` | `EconomicsAgent(cache)` | 85 |
| `"decision"` | `DecisionAgent(cache)` | 86 |
| `"validation"` | `ValidationAgent(cache)` | 87 |
| `"uhdc"` | `UHDCAgent(cache)` | 88 |
| `"what_if"` | `WhatIfAgent(cache)` | 89 |

**Tools & Environment:**
| Component | Detail |
|---|---|
| Pattern | Lazy singleton — agents instantiated once on first `execute()` call |
| Cache Dir | Passed as string to each domain agent's `BaseDomainAgent.__init__` |
| Instance Scope | Agents persist across multiple `execute()` calls within same executor |

---

## 3.3 Refactor execute Method

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 95-140

### Method Signature (line 95)

- [x] `execute(self, intent: str, street_id: str, context: Optional[Dict] = None) -> Dict[str, Any]`
- [x] Backward-compatible — same signature as pre-refactor version
- [x] Docstring documents return keys: `execution_log`, `error`, plus intent-specific data

### Execution Flow

- [x] `context = context or {}` — default empty dict (line 109)
- [x] `self._ensure_agents()` — lazy agent init on first call (line 110)
- [x] `start = time.perf_counter()` — high-resolution execution timing (line 112)
- [x] Logs receipt: `[DynamicExecutor] Received order: {intent} for {street_id}` (line 113)
- [x] Calls `self._create_agent_plan(intent, context)` to determine agent sequence (line 116)
- [x] Logs plan: `[DynamicExecutor] Agent plan: {plan}` (line 117)
- [x] Calls `self._run_agent_plan(plan, intent, street_id, context)` — returns `(agent_results, execution_log)` (line 119)
- [x] Calls `self._integrate_results(agent_results, intent, street_id)` — returns flat dict (line 124)
- [x] Attaches `execution_log` to integrated result (line 125)
- [x] Computes `total_execution_time = time.perf_counter() - start` (line 127)
- [x] Attaches `agent_results` metadata dict (success, execution_time, cache_hit, metadata per agent) (lines 128-136)
- [x] Attaches `total_execution_time` (line 137)
- [x] Logs completion: `[DynamicExecutor] Order completed in {total:.2f}s` (line 139)

### Return Value Keys (line 140)

- [x] All intent-specific data keys (from `_integrate_results`)
- [x] `execution_log: List[str]` — timed log of what ran
- [x] `agent_results: Dict` — per-agent metadata (success, time, cache_hit)
- [x] `total_execution_time: float`
- [x] `error: str` — set only on failure (from `_integrate_results`)

> **Note**: The checklist originally listed `type`, `data`, and `all_agents_success` as return keys. The current implementation does **not** wrap results in a `type`/`data` envelope — the integrated data keys are returned at the top level alongside `execution_log` and `agent_results`. This is intentional for backward compatibility with the orchestrator/UI. `all_agents_success` is also not present as a top-level key; the orchestrator derives this from `agent_results`.

**Tools & Environment:**
| Component | Detail |
|---|---|
| Timer | `time.perf_counter()` — monotonic, sub-microsecond resolution |
| Logging | Python `logging` module, `[DynamicExecutor]` prefix |
| Error Handling | Exceptions caught in `_run_agent_plan`; critical agent failures stop pipeline |

---

## 3.4 Create _create_agent_plan Method

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 145-163

- [x] Signature: `_create_agent_plan(self, intent: str, context: Dict) -> List[str]`
- [x] Returns dependency-ordered list of agent registry keys

### Intent → Agent Plan Mapping (lines 147-157)

| Intent | Agent Plan | Line |
|---|---|---|
| `"CO2_COMPARISON"` | `["cha", "dha", "economics"]` | 148 |
| `"LCOH_COMPARISON"` | `["cha", "dha", "economics"]` | 149 |
| `"VIOLATION_ANALYSIS"` | `["cha", "dha"]` | 150 |
| `"NETWORK_DESIGN"` | `["cha"]` | 151 |
| `"WHAT_IF_SCENARIO"` | `["what_if"]` | 152 |
| `"DECISION"` | `["cha", "dha", "economics", "decision"]` | 153 |
| `"EXPLAIN_DECISION"` | `["cha", "dha", "economics", "decision"]` | 154 |
| `"FULL_REPORT"` | `["cha", "dha", "economics", "decision", "uhdc"]` | 155 |
| `"DATA_PREPARATION"` | `["data_prep"]` | 156 |

### Additional Logic

- [x] Default fallback for unknown intents: `["cha", "dha", "economics"]` (line 158)
- [x] `needs_data_prep` context flag prepends `"data_prep"` to any plan (lines 160-161)

> **Note vs. Checklist**: The user's checklist listed `EXPLAIN_DECISION → ["cha", "dha", "economics", "decision", "validation"]`. The current implementation maps it to `["cha", "dha", "economics", "decision"]` **without** `"validation"`. Validation is triggered separately by the orchestrator when explanation text is available, not as part of the executor plan. This is by design — ValidationAgent requires `explanation_text` in context which is only available after decision generation.

---

## 3.5 Create _run_agent_plan Method (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 168-226

This method was **not listed** in the user's original checklist but is the core execution loop. It replaces the inline `for agent_name in agent_plan:` loop described in the checklist.

- [x] Signature: `_run_agent_plan(self, plan, intent, street_id, context) -> Tuple[Dict[str, Any], List[str]]`
- [x] Returns `(results_dict, execution_log_list)`
- [x] Retrieves `AgentResult` class from `self._agent_classes` for error construction (line 176)

### Agent Loop (lines 180-226)

- [x] Iterates through `plan` in dependency order
- [x] Looks up agent from `self._agents.get(agent_name)` (line 181)
- [x] Skips if agent is `None` (line 182-183)
- [x] Records `agent_start = time.perf_counter()` per agent (line 185)
- [x] Calls `agent.execute(street_id, context)` (line 187)
- [x] Catches exceptions and creates failure `AgentResult` with error message (lines 188-198)
- [x] Stores result in `results[agent_name]` (line 200)

### Timed Log Line (lines 203-211)

- [x] Status: `"✓"` on success, `"✗"` on failure
- [x] Cache tag: `"Used cached"` or `"Calculated"`
- [x] Label: agent name uppercased with underscores replaced (e.g., `"WHAT IF"`)
- [x] Duration format: cache hits use `:.3f` (millisecond precision), calculations use `:.1f` (line 208-210)
- [x] Example output: `"✓ Used cached CHA (0.002s)"` or `"✓ Calculated ECONOMICS (3.2s)"`

### Sub-Log Entries (lines 213-215)

- [x] Appends agent-specific metadata from `result.metadata.get("modification_log", [])` (e.g., WhatIfAgent logs)
- [x] Prefixed with `"  → "` for visual nesting

### Early Stop on Critical Failure (lines 217-224)

- [x] If agent failed (`not result.success`): logs error
- [x] If failed agent is in `("cha", "dha", "economics")`: stops pipeline with message `"Pipeline stopped: {agent_name} is a prerequisite"`
- [x] Non-critical agents (decision, validation, uhdc, what_if) fail gracefully without stopping

**Tools & Environment:**
| Component | Detail |
|---|---|
| Timer | `time.perf_counter()` per agent |
| Error Recovery | Exceptions caught → `AgentResult(success=False)` |
| Pipeline Stop | Critical agents (cha, dha, economics) halt further execution on failure |
| Log Format | `{status} {cache_tag} {LABEL} ({duration}s)` |

---

## 3.6 Create _integrate_results Method

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 231-267

- [x] Signature: `_integrate_results(self, results, intent, street_id) -> Dict[str, Any]`
- [x] Accepts `results: Dict[str, AgentResult]` and `intent: str`

### Critical Failure Checks (lines 239-248)

- [x] Checks CHA, DHA, Economics for failure → returns `{"error": "..."}` (lines 240-243)
- [x] Checks WhatIfAgent for failure → returns `{"error": "..."}` (lines 246-248)

### Intent-Based Dispatch (lines 250-267)

| Intent | Formatter Method | Line |
|---|---|---|
| `"CO2_COMPARISON"` | `_format_co2(results, street_id)` | 252 |
| `"LCOH_COMPARISON"` | `_format_lcoh(results, street_id)` | 254 |
| `"VIOLATION_ANALYSIS"` | `_format_violations(results, street_id)` | 256 |
| `"NETWORK_DESIGN"` | `_format_network_design(results, street_id)` | 258 |
| `"DECISION"` / `"EXPLAIN_DECISION"` | `_format_decision(results, street_id)` | 260 |
| `"WHAT_IF_SCENARIO"` | `_format_what_if(results, street_id)` | 262 |
| Other (fallback) | Raw agent data: `{name: r.data for ...}` | 265-267 |

> **Additional vs. Checklist**: The checklist did not list `_format_network_design` or `_format_what_if`, but both are implemented. Also, `_integrate_results` takes `street_id` as an additional parameter (not in original checklist).

---

## 3.7 Create Format Methods

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 270-374

### _format_co2 (lines 270-279)

- [x] Extracts economics via `_extract_economics(results)` helper
- [x] Returns dict with keys:
  - `dh_tons_co2: float`
  - `hp_tons_co2: float`
  - `difference: float` (DH − HP)
  - `winner: str` ("DH" or "HP")

### _format_lcoh (lines 282-291)

- [x] Extracts economics via `_extract_economics(results)` helper
- [x] Returns dict with keys:
  - `lcoh_dh_eur_per_mwh: float`
  - `lcoh_hp_eur_per_mwh: float`
  - `difference: float` (HP − DH)
  - `winner: str` ("DH" or "HP")

### _format_violations (lines 294-318)

- [x] Extracts CHA KPIs via `_extract_cha_kpis(results)` helper
- [x] Extracts DHA KPIs via `_extract_dha_kpis(results)` helper
- [x] Returns dict with keys:
  - `cha.converged: bool`
  - `cha.pressure_bar_max: float`
  - `cha.velocity_ms_max: float`
  - `dha.voltage_violations: int`
  - `dha.line_violations: int`
  - `v_share_within_limits: float`
  - `dp_max_bar_per_100m: float`

### _format_network_design (lines 321-346) — *not in original checklist*

- [x] Extracts CHA KPIs, topology, pipes, heat_consumers
- [x] Resolves interactive map file paths (velocity, temperature, pressure)
- [x] Returns dict with keys: `topology`, `pipes`, `heat_consumers`, `map_paths`

### _format_decision (lines 349-360)

- [x] Extracts decision data from `results["decision"].data`
- [x] Returns dict with keys:
  - `choice: str`
  - `recommendation: str`
  - `robust: bool`
  - `reason: str`
  - `reason_codes: list`
  - `metrics_used: dict`

### _format_what_if (lines 363-374) — *not in original checklist*

- [x] Static method
- [x] Extracts WhatIfAgent result data
- [x] Returns dict with keys:
  - `baseline: dict` (co2_tons, max_pressure_bar)
  - `scenario: dict` (co2_tons, max_pressure_bar)
  - `comparison: dict` (pressure_change_bar, heat_delivered_change_mw, violation_reduction)
  - `modification_applied: str`

---

## 3.8 Helper Extraction Methods (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — lines 377-398

These static helper methods reduce duplication across formatters:

### _extract_economics (lines 378-383)

- [x] Static method
- [x] Checks `results["economics"].success`
- [x] Returns `data.get("economics", data)` — handles both nested and flat formats

### _extract_cha_kpis (lines 386-390)

- [x] Static method
- [x] Checks `results["cha"].success`
- [x] Returns `data.get("kpis", data)` — handles both nested and flat formats

### _extract_dha_kpis (lines 393-398)

- [x] Static method
- [x] Checks `results["dha"].success`
- [x] Returns `data.get("kpis", data)` with double-unwrap for nested KPI structures

**Tools & Environment:**
| Component | Detail |
|---|---|
| Pattern | Static helper methods for safe data extraction with fallbacks |
| Safety | All check `result.success` before accessing `.data` |
| Flexibility | Handle both `{"kpis": {...}}` and flat `{...}` formats from different cache states |

---

## 3.9 Return Value Structure

**Implementation**: `src/branitz_heat_decision/agents/executor.py` — `execute()` return at line 140

The return dict contains these keys:

| Key | Type | Source | Line |
|---|---|---|---|
| *(intent-specific keys)* | `Dict` | `_integrate_results()` | 124 |
| `execution_log` | `List[str]` | `_run_agent_plan()` | 125 |
| `agent_results` | `Dict[str, Dict]` | built from `AgentResult` objects | 128-136 |
| `total_execution_time` | `float` | `time.perf_counter()` delta | 137 |
| `error` | `str` (optional) | set by `_integrate_results` on failure | 243/248 |

### agent_results sub-dict per agent (lines 129-134):

- [x] `success: bool`
- [x] `execution_time: float`
- [x] `cache_hit: bool`
- [x] `metadata: Dict`

> **Difference from Checklist**: The checklist listed `type: intent string`, `data: integrated/formatted data`, and `all_agents_success: bool` as top-level return keys. The actual implementation **flattens** the integrated data directly into the return dict (no `type`/`data` envelope), and does **not** include `all_agents_success` — the orchestrator can derive it from `agent_results`. This flat structure maintains backward compatibility with the UI renderers.

---

## Phase 3 Summary

| Checklist Item | Status | Location (line) |
|---|---|---|
| **Imports** | | |
| Lazy domain agent imports (`_import_agents`) | [x] | 25-47 |
| Zero direct tool imports | [x] | verified via grep |
| Zero inline simulation imports (pandapipes, pickle) | [x] | verified via grep |
| Standard library imports (logging, time, Path, typing) | [x] | 12-17 |
| **__init__** | | |
| `cache_dir` stored as `Path` | [x] | 68 |
| Lazy agent placeholders (`_agents`, `_agent_classes`) | [x] | 71-72 |
| `_ensure_agents()` guard clause | [x] | 76 |
| 8 agent instances registered | [x] | 81-90 |
| **execute()** | | |
| Signature preserved: `(intent, street_id, context)` | [x] | 95-99 |
| `time.perf_counter()` start timing | [x] | 112 |
| Calls `_create_agent_plan` | [x] | 116 |
| Calls `_run_agent_plan` | [x] | 119 |
| Calls `_integrate_results` | [x] | 124 |
| Attaches `execution_log` | [x] | 125 |
| Attaches `agent_results` metadata | [x] | 128-136 |
| Attaches `total_execution_time` | [x] | 137 |
| **_create_agent_plan()** | | |
| 9 intent → plan mappings | [x] | 147-157 |
| Default fallback plan | [x] | 158 |
| `needs_data_prep` context flag | [x] | 160-161 |
| **_run_agent_plan()** | | |
| Dependency-ordered agent loop | [x] | 180-226 |
| Per-agent timing | [x] | 185, 201 |
| Exception catching → failure AgentResult | [x] | 188-198 |
| Timed log: `✓/✗ Used cached/Calculated LABEL (Xs)` | [x] | 204-211 |
| Sub-log for agent metadata (modification_log) | [x] | 213-215 |
| Critical agent failure stops pipeline | [x] | 220-224 |
| **_integrate_results()** | | |
| Critical failure checks (cha, dha, economics, what_if) | [x] | 239-248 |
| Intent-based dispatch to 6 formatters | [x] | 250-262 |
| Generic fallback for unknown intents | [x] | 265-267 |
| **Format methods** | | |
| `_format_co2` — CO2 comparison dict | [x] | 270-279 |
| `_format_lcoh` — LCOH comparison dict | [x] | 282-291 |
| `_format_violations` — violations dict | [x] | 294-318 |
| `_format_network_design` — network + maps dict | [x] | 321-346 |
| `_format_decision` — recommendation dict | [x] | 349-360 |
| `_format_what_if` — baseline vs scenario dict | [x] | 363-374 |
| **Helper methods** | | |
| `_extract_economics` — safe economics extraction | [x] | 378-383 |
| `_extract_cha_kpis` — safe CHA KPI extraction | [x] | 386-390 |
| `_extract_dha_kpis` — safe DHA KPI extraction | [x] | 393-398 |

**All 34 items implemented.** Three design notes recorded where implementation differs from checklist (flat return instead of `type`/`data` envelope; `all_agents_success` derived by orchestrator; `EXPLAIN_DECISION` excludes validation from plan).

---
---

# Phase 4: Update Orchestrator

> **File**: `src/branitz_heat_decision/agents/orchestrator.py`
> **Verified**: 2026-01-25
> **Total Lines**: 939

---

## 4.1 Naming Bug Check (line ~643-644)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 642-644

The user flagged a potential naming bug: `results.get("cha_tons_co2", 0)` being used for Heat Pump data. **Verified: this bug does NOT exist** in the current code.

Current code (correct):

```python
# orchestrator.py lines 642-644
if intent == "CO2_COMPARISON":
    data["co2_dh_t_per_a"] = results.get("dh_tons_co2", 0)
    data["co2_hp_t_per_a"] = results.get("hp_tons_co2", 0)
```

Key alignment verified:

| Orchestrator Reads | Executor Returns (`_format_co2`, line 274-278) | Correct? |
|---|---|---|
| `results.get("dh_tons_co2", 0)` | `"dh_tons_co2": float(co2_dh)` | [x] Yes |
| `results.get("hp_tons_co2", 0)` | `"hp_tons_co2": float(co2_hp)` | [x] Yes |
| `results.get("winner", "")` | `"winner": "DH" if co2_dh < co2_hp else "HP"` | [x] Yes |

- [x] No `cha_tons_co2` key exists anywhere in the codebase
- [x] DH data mapped to `co2_dh_t_per_a` (not HP)
- [x] HP data mapped to `co2_hp_t_per_a` (not DH)
- [x] No naming confusion between DH/HP/CHA

### Same check for LCOH keys (lines 645-647):

| Orchestrator Reads | Executor Returns (`_format_lcoh`, line 287-290) | Correct? |
|---|---|---|
| `results.get("lcoh_dh_eur_per_mwh", 0)` | `"lcoh_dh_eur_per_mwh": float(dh)` | [x] Yes |
| `results.get("lcoh_hp_eur_per_mwh", 0)` | `"lcoh_hp_eur_per_mwh": float(hp)` | [x] Yes |

- [x] LCOH keys match between executor and orchestrator

---

## 4.2 Verify Executor Initialization

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 42-44, 215

### Lazy Import (line 42-44)

- [x] `_get_executor()` imports `DynamicExecutor` from `branitz_heat_decision.agents.executor`
- [x] Returns the refactored class (agent-based, not tool-based)
- [x] Lazy import pattern — no circular dependency risk

### Instantiation in __init__ (line 215)

- [x] `self.executor = _get_executor()(cache_dir=cache_dir)`
- [x] `cache_dir` parameter passed through from orchestrator constructor
- [x] Signature compatible: `DynamicExecutor(cache_dir: str = "./cache")`
- [x] No changes needed — constructor signature unchanged by refactor

### Executor Usage in route_request (lines 512-520)

- [x] Calls `self.executor.execute(intent=intent, street_id=cluster_id, context={...})`
- [x] Context includes: `modification`, `history`, `run_missing`
- [x] Signature match: `execute(self, intent: str, street_id: str, context: Optional[Dict] = None)`
- [x] No breaking changes from refactor

---

## 4.3 Update Response Formatting — agent_results & execution_log

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 522-555, 610-665

### Agent Trace Enrichment (lines 522-538)

- [x] Extracts `results.get("agent_results", {})` — per-agent metadata from executor
- [x] Builds rich agent trace entry for "Dynamic Executor" with:
  - `outcome`: `"error"` or `"success"`
  - `execution_log`: full timed log from executor
  - `total_execution_time`: end-to-end duration
  - `agents_invoked`: per-agent dict with `success`, `cache_hit`, `execution_time`
- [x] Agent trace appended to `agent_trace` list visible to UI

### _format_executor_response (lines 610-665)

- [x] Passes `result["execution_log"]` to UI as:
  - `"execution_plan"` key (line 655) — for backward compatibility
  - `"execution_log"` key (line 660) — explicit log
  - `"sources"` list (line 658) — includes `["DynamicExecutor"] + execution_log`
- [x] Passes `result["agent_results"]` to UI as `"agent_results"` (line 663)
- [x] Passes `result["total_execution_time"]` to UI as `"total_execution_time"` (line 664)

### Error Path (lines 624-635)

- [x] On error: still passes `execution_log` through to UI (lines 628, 633)
- [x] Sets `can_proceed: False` and `visualization: None`

---

## 4.4 _format_answer — Human-Readable Responses (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 667-726

- [x] `CO2_COMPARISON` (line 669): Reads `dh_tons_co2`, `hp_tons_co2`, `winner` → "District Heating: X tCO₂/year vs Heat Pumps: Y tCO₂/year. {winner} has lower emissions."
- [x] `LCOH_COMPARISON` (line 677): Reads `lcoh_dh_eur_per_mwh`, `lcoh_hp_eur_per_mwh`, `winner` → "LCOH DH: X €/MWh vs HP: Y €/MWh. {winner} has lower cost."
- [x] `VIOLATION_ANALYSIS` (line 685): Reads CHA/DHA nested dicts → velocity, pressure, voltage/line violations
- [x] `NETWORK_DESIGN` (line 696): Reads topology, pipes, map_paths → building count, pipe count, trunk info, available maps
- [x] `WHAT_IF_SCENARIO` (line 715): Reads modification_applied, comparison → pressure/heat change
- [x] `EXPLAIN_DECISION` (line 724): Delegates to `_format_decision_answer()`
- [x] Fallback: `str(results)` for unrecognized intents (line 726)

---

## 4.5 _format_decision_answer — Rich Decision Explanation (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 728-767

- [x] Extracts `choice`/`recommendation`, `reason_codes`, `robust`, `metrics_used`
- [x] Formats DH/HP-specific recommendation sentences
- [x] Appends LCOH detail if `metrics_used` contains `lcoh_dh_median` and `lcoh_hp_median`
- [x] Adds robustness warning if `robust=False`

---

## 4.6 _enrich_decision_data — Full Decision JSON from Disk (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 769-804

- [x] Loads `decision_{cluster_id}.json` from `resolve_cluster_path(cluster_id, "decision")`
- [x] Normalizes keys: `choice` → `recommendation`, builds `reason` from `reason_codes`
- [x] Merges into `data` dict using `data.setdefault(key, val)` — executor fields take priority
- [x] Called only for `EXPLAIN_DECISION` intent (line 650)

---

## 4.7 _create_viz — Visualization Hints for UI (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 806-849

- [x] `CO2_COMPARISON` → bar chart (`dh_tons_co2` vs `hp_tons_co2`, y_label: `tCO₂/year`)
- [x] `LCOH_COMPARISON` → bar chart (`lcoh_dh_eur_per_mwh` vs `lcoh_hp_eur_per_mwh`, y_label: `€/MWh`)
- [x] `WHAT_IF_SCENARIO` → comparison chart (baseline vs scenario)
- [x] `EXPLAIN_DECISION` → decision chart (recommendation, robust, reason_codes, LCOH/CO2 metrics)
- [x] Returns `None` for intents without visualization

---

## 4.8 Conversation Memory Update (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 547-554

- [x] On success (`"error" not in results`): calls `self.conversation.update_memory(intent, street_id, results, execution_log)`
- [x] Adds contextual suggestion chips via `self.conversation.get_suggestions()`
- [x] Enables "What about LCOH?" follow-ups without re-running simulations

---

## 4.9 Error Handling (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 558-591

- [x] `ValueError` (line 558): returns `type: "fallback"`, logs to agent trace
- [x] General `Exception` (line 574): returns `type: "ERROR"`, logs full traceback, suggests retry
- [x] Both paths include full `agent_trace` in response

---

## 4.10 Capability Guardrail Integration (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 402-428, 851-904

- [x] Validates request via `self.capability_guardrail.validate_request(intent, entities, user_query)`
- [x] On rejection: calls `_handle_capability_fallback()`
- [x] Fallback returns `type: "guardrail_blocked"`, `is_research_boundary: True`
- [x] Includes `alternative_suggestions`, `research_note`, `escalation_path`

---

## 4.11 _EXECUTOR_INTENTS Set (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 31-34

- [x] `frozenset` containing 6 intents routed to DynamicExecutor:
  - `CO2_COMPARISON`
  - `LCOH_COMPARISON`
  - `VIOLATION_ANALYSIS`
  - `WHAT_IF_SCENARIO`
  - `NETWORK_DESIGN`
  - `EXPLAIN_DECISION`
- [x] `EXPLAIN_DECISION` included (previously had its own handler, now goes through executor)

---

## 4.12 Agent Trace — Full 6-Agent Pipeline (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — `route_request()`

The orchestrator produces a complete agent trace for every request:

| # | Agent | Duty | Location (line) |
|---|---|---|---|
| 1 | NLU Intent Classifier | Classify intent, extract entities | 268-275 |
| 2 | Conversation Manager | Resolve references, detect follow-ups | 285-292 |
| 3 | Street Resolver | Map display name → cluster_id | 351-358 |
| 4 | Capability Guardrail | Validate within system boundaries | 410-417 |
| 5 | Execution Planner | Determine required simulations | 499-504 |
| 6 | Dynamic Executor | Execute via domain agents | 524-538 |

- [x] All 6 agents logged in `agent_trace`
- [x] `agent_trace` attached to every response (success, error, clarification, fallback)

---

## 4.13 Helper Functions — Standalone Utilities (not in original checklist)

**Implementation**: `src/branitz_heat_decision/agents/orchestrator.py` — lines 57-138

| Function | Purpose | Line |
|---|---|---|
| `_get_available_streets()` | Load cluster IDs from index or parquet | 57-81 |
| `_get_building_count(cluster_id)` | Count buildings from CHA topology (spurs) | 84-102 |
| `_has_cha_results(cluster_id)` | Check if `cha_kpis.json` exists | 105-108 |
| `_has_dha_results(cluster_id)` | Check if `dha_kpis.json` exists | 111-114 |
| `_has_economics_results(cluster_id)` | Check if `economics_deterministic.json` exists | 117-120 |
| `_has_decision_results(cluster_id)` | Check if `decision_{cluster_id}.json` exists | 123-126 |
| `_load_json(path)` | Safe JSON file loader | 129-138 |
| `_call_fallback_llm(query, intent_data)` | LLM-based fallback explanation | 141-188 |
| `_fallback_template(query, intent_data)` | Template fallback when LLM unavailable | 191-197 |

- [x] All helpers use lazy imports where needed
- [x] None import from `adk.tools` or call simulation tools directly

---

## Phase 4 Summary

| Checklist Item | Status | Location (line) |
|---|---|---|
| **Naming Bug Check** | | |
| No `cha_tons_co2` key exists | [x] | verified via grep |
| `dh_tons_co2` maps correctly to DH | [x] | 643, 670, 812 |
| `hp_tons_co2` maps correctly to HP | [x] | 644, 671, 813 |
| LCOH keys align between executor & orchestrator | [x] | 646-647 vs 287-288 |
| **Executor Initialization** | | |
| `_get_executor()` returns refactored DynamicExecutor | [x] | 42-44 |
| `self.executor` instantiated with `cache_dir` | [x] | 215 |
| `execute()` signature compatible | [x] | 512-520 |
| No breaking changes from refactor | [x] | verified |
| **Response Formatting** | | |
| `agent_results` extracted and passed to agent trace | [x] | 523, 530-537 |
| `execution_log` passed to UI (3 locations) | [x] | 655, 658, 660 |
| `agent_results` passed to UI response | [x] | 663 |
| `total_execution_time` passed to UI response | [x] | 664 |
| Error path preserves execution_log | [x] | 628, 633 |
| **Answer Formatting** | | |
| `_format_answer` covers 6 intents + fallback | [x] | 667-726 |
| `_format_decision_answer` with LCOH detail + robustness | [x] | 728-767 |
| **Data Enrichment** | | |
| `_enrich_decision_data` loads full decision JSON | [x] | 769-804 |
| Merges with executor fields (executor wins on conflict) | [x] | 803-804 |
| **Visualization** | | |
| `_create_viz` covers CO2, LCOH, What-If, Decision | [x] | 806-849 |
| **Conversation Memory** | | |
| Memory updated on success | [x] | 548-553 |
| Suggestion chips generated | [x] | 554 |
| **Error Handling** | | |
| ValueError caught | [x] | 558-573 |
| General Exception caught with traceback | [x] | 574-591 |
| **Guardrail** | | |
| Capability check before execution | [x] | 405-417 |
| Fallback with `is_research_boundary: True` | [x] | 903 |
| **Agent Trace** | | |
| 6-agent trace pipeline | [x] | 268-538 |
| Trace attached to all response paths | [x] | 381, 399, 427, 493, 555, 572, 590, 607 |
| **No Direct Tool Calls** | | |
| Zero `from branitz_heat_decision.adk.tools import` | [x] | verified via grep |

**All 30 items verified.** No naming bug found — `dh_tons_co2`/`hp_tons_co2` keys are correctly used throughout. The orchestrator fully integrates with the refactored executor, passing `agent_results`, `execution_log`, and `total_execution_time` to the UI.
