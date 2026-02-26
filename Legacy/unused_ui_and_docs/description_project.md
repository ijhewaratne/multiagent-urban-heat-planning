# Methodology: Multi-Agent Decision Support System for Climate-Neutral Urban Heat Planning

## 1. Introduction and Research Context

This chapter describes the design, architecture, and implementation of a multi-agent AI system developed to support climate-neutral heat supply planning at the street level in the Branitz district of Cottbus, Germany. The system addresses a fundamental urban energy planning question: for each street cluster, should heat be supplied via **District Heating (DH)** connected to the existing CHP plant, or via individual **Heat Pumps (HP)** drawing from the low-voltage electrical grid?

The system is designed around three guiding principles derived from stakeholder requirements:

1. **Determinism and auditability**: All decisions must originate from transparent, reproducible rules — never from a Large Language Model (LLM). The LLM is constrained to a read-only coordinator role: classifying user intent, generating explanations of pre-computed results, and formatting responses. It cannot alter simulation parameters, invent data, or override the deterministic decision engine.

2. **Lazy, cache-first execution**: Simulations are computationally expensive (hydraulic-thermal pipeflow, LV grid power flow, Monte Carlo sampling). The system runs only the simulations required for the user's specific query and reuses cached results across turns. A query about CO₂ emissions after a prior LCOH query should complete in milliseconds, not minutes.

3. **Graceful boundaries**: When a user requests an operation outside the system's capabilities (e.g., "add a new consumer to the network"), the system must explicitly state what it cannot do, explain why this is a research boundary, and suggest supported alternatives — rather than hallucinating a response or entering an error loop.

---

## 2. System Architecture

### 2.1 Hierarchical Agent Architecture

The system implements a five-layer hierarchical agent architecture with 21 agents organized across four tiers. Each layer has a distinct responsibility, and communication flows strictly downward through well-defined interfaces.

**Layer 1 — Orchestration** (`BranitzOrchestrator`): Routes each user query through a sequential six-agent pipeline: (1) NLU intent classification, (2) conversation context management, (3) street name resolution, (4) capability boundary validation, (5) execution planning, and (6) dynamic execution. Every agent logs its duty and outcome to a structured agent trace that is returned alongside the response for full transparency.

**Layer 2 — Dynamic Executor** (`DynamicExecutor`): Translates an intent (e.g., `CO2_COMPARISON`) into a dependency-ordered plan of domain agents (e.g., `["cha", "dha", "economics"]`), executes them sequentially, and integrates their outputs into the flat dictionary format the user interface expects. The executor lazily initializes agent instances on first use and produces a timed execution log (e.g., `"✓ Used cached CHA (0.002s)"`, `"✓ Calculated ECONOMICS (2.3s)"`).

**Layer 2.5 — Domain Agents** (8 specialist agents): Each domain agent encapsulates one simulation domain end-to-end. It first checks whether valid cached results exist on disk (file-based caching using JSON and pickle files). On a cache hit, it returns immediately. On a miss, it delegates to the corresponding ADK agent. Domain agents include: `DataPrepAgent`, `CHAAgent`, `DHAAgent`, `EconomicsAgent`, `DecisionAgent`, `ValidationAgent`, `UHDCAgent`, and `WhatIfAgent`.

**Layer 3 — ADK Agents** (6 policy-enforced wrappers): Each ADK agent wraps a single simulation tool function with three capabilities: (a) policy enforcement via a guardrail registry (e.g., the critical policy "LLM cannot decide" prevents any LLM from altering decision outcomes), (b) trajectory tracking via `AgentAction` dataclasses that record every tool invocation with parameters, results, timestamps, and errors, and (c) per-action wall-clock timing using `time.perf_counter()`.

**Layer 4 — ADK Tools** (raw functions): Thin wrapper functions that invoke the underlying simulation scripts. Each tool function calls a standalone Python script (e.g., `01_run_cha.py`) which performs the actual simulation using domain-specific libraries.

**Layer 5 — Simulation Engines**: The computational core — pandapipes for hydraulic-thermal simulation, pandapower for LV grid analysis, and custom economic models for LCOH and CO₂ calculations.

### 2.2 Design Rationale

The hierarchical delegation pattern (Orchestrator → Executor → Domain Agent → ADK Agent → Tool) was chosen to achieve separation of concerns at each level:

- The **orchestrator** knows about user interaction (NLU, conversation state, UI formatting) but nothing about simulation internals.
- The **executor** knows about agent dependencies and result integration but does not call any simulation function directly.
- **Domain agents** know about caching and prerequisites (e.g., economics requires CHA and DHA results) but delegate the actual tool invocation to ADK agents.
- **ADK agents** enforce system-wide policies and record audit trails but are agnostic to caching or result formatting.
- **Tools** are pure functions with no state, policy awareness, or caching logic.

This separation ensures that adding a new simulation type (e.g., a geothermal agent) requires only: (1) a new domain agent with `can_handle()` and `execute()`, (2) a corresponding ADK agent class, (3) a tool function, and (4) an entry in the agent registry and executor plan mapping. No changes to the orchestrator or UI are needed.

### 2.3 Agent-Cycle Interpretation (Perceive -> Recognize -> Plan -> Act)

The implemented architecture can be interpreted as a hierarchical perceive-recognize-plan-act loop:

- **Perceive**: user query, conversation history, available streets, cached artifacts, and capability policies.
- **Recognize**: intent classification, follow-up detection, street disambiguation, and unsupported-operation detection.
- **Plan**: intent-to-agent plan creation in the executor, dependency ordering, and cache/prerequisite checks in each domain agent.
- **Act**: ADK-agent-mediated tool execution, simulation runs, result integration, and response generation.
- **Environment update**: result files and conversation memory are updated, influencing subsequent turns.

This makes the system a software-based closed-loop decision agent (across chat turns), rather than a physical control agent.

---

## 3. Natural Language Understanding

### 3.1 Intent Classification

User queries are classified into a set of structured intents using a two-stage approach. In day-to-day chat, the classifier primarily targets the core user intents (`CO2_COMPARISON`, `LCOH_COMPARISON`, `VIOLATION_ANALYSIS`, `NETWORK_DESIGN`, `WHAT_IF_SCENARIO`, `EXPLAIN_DECISION`, `CAPABILITY_QUERY`, `UNKNOWN`), while the full execution stack also supports system-level intents such as `DECISION`, `FULL_REPORT`, and `DATA_PREPARATION`.

**Primary method — LLM classification**: The query is sent to Google Gemini (temperature=0.0 for determinism) with a constrained system prompt that defines exactly eight supported intents (`CO2_COMPARISON`, `LCOH_COMPARISON`, `VIOLATION_ANALYSIS`, `NETWORK_DESIGN`, `WHAT_IF_SCENARIO`, `EXPLAIN_DECISION`, `CAPABILITY_QUERY`, `UNKNOWN`). The LLM returns a structured JSON object containing the classified intent, a confidence score (0.0–1.0), extracted entities (street name, metric type, modification description), and a brief reasoning string.

**Fallback method — keyword matching**: If the Gemini API is unavailable (no API key, network failure, rate limiting), the system falls back to deterministic keyword pattern matching against known phrases for each intent. This ensures the system remains functional without cloud connectivity.

### 3.2 Entity Extraction

Street entities are extracted using fuzzy matching with German name normalization. The matcher handles common orthographic variants: `ß` ↔ `ss`, `Straße` ↔ `Strasse`, and partial street name mentions. Scoring is based on distinguishing word parts, with generic suffixes (strasse, platz, allee, weg) excluded from the match score to avoid false positives between streets that differ only in their suffix.

### 3.3 Multi-Turn Conversation Management

The `ConversationManager` maintains a `ConversationMemory` object across turns, tracking:
- `current_street`: the street being discussed
- `last_calculation`: the most recent intent and its results
- `available_data`: which simulation results are cached per street

Follow-up queries are detected using linguistic patterns ("what about", "how about", "also show", short queries without street mentions). When a follow-up is detected, the system enriches the new intent with the current street from memory, enabling natural conversation chains: "Compare CO₂ for Heinrich-Zille-Straße" → "What about LCOH?" → "What if we remove 2 houses?" — all three queries operate on the same street without the user repeating it.

---

## 4. Simulation Models

### 4.1 Centralized Heating Analysis (CHA)

The CHA module simulates the district heating network using pandapipes, an open-source tool for multi-energy network simulation based on the STANET methodology.

**Network construction**: The `network_builder_trunk_spur.py` module constructs a pandapipes network from GIS building data. Buildings are connected to a trunk-spur topology where a main trunk line runs along the street with spur connections to individual buildings. Pipe diameters are selected from a manufacturer catalog (`sizing_catalog.py`) based on target flow velocities: trunk lines are sized for a maximum velocity of 1.5 m/s and service lines for 1.5 m/s, both compliant with EN 13941-1 noise and erosion limits.

**Operating parameters**: The network operates at a supply temperature of 90°C (363.15 K) and a return temperature of 50°C (323.15 K), with a system pressure of 8.0 bar and a pump differential of 3.0 bar. The working fluid is water.

**Thermal losses**: Heat losses are calculated using a linear method calibrated to manufacturer data (Aquatherm typical values: 30 W/m for trunk lines, 25 W/m for service lines). A TwinPipe correction factor of 0.9 accounts for supply-return thermal interaction per EN 13941-1.

**Convergence**: The `convergence_optimizer.py` module implements iterative pipeflow solving with automatic pressure adjustment. If the solver produces negative absolute pressures (common for long networks), the system automatically increases the plant pressure and pump lift and retries.

**KPI extraction**: After convergence, the `kpi_extractor.py` module extracts EN 13941-1 compliance KPIs including maximum velocity, velocity compliance share, maximum pressure drop per 100m, and network topology statistics (trunk edges, spur connections, buildings connected).

**Visualization**: Three interactive Folium maps are generated: velocity layer (with cascading color scale), temperature distribution, and pressure drop layer. These are stored as HTML files and served directly in the Streamlit UI.

### 4.2 Decentralized Heating Analysis (DHA)

The DHA module simulates the impact of distributed heat pumps on the low-voltage electrical grid using pandapower.

**Grid construction**: The `grid_builder.py` module constructs a pandapower LV grid from geodata. Each building is modeled as a load node with a heat pump drawing electrical power based on its thermal demand and a coefficient of performance (COP) of 2.8 (default). Heat pumps are modeled as balanced three-phase loads.

**Power flow analysis**: The `loadflow.py` module runs a Newton-Raphson power flow analysis to identify voltage violations (exceeding ±10% of nominal voltage per VDE-AR-N 4100) and line overloading (exceeding 100% thermal rating).

**Hosting capacity**: The `hosting_capacity.py` module performs Monte Carlo analysis to determine the maximum number of heat pumps the grid can accommodate before violations occur, considering simultaneity factors and load diversity.

**Smart grid strategies**: The `smart_grid_strategies.py` module evaluates mitigation options (demand response, battery storage, grid reinforcement) and the `reinforcement_optimizer.py` estimates grid upgrade costs.

### 4.3 Economic Analysis

The economics module computes the Levelized Cost of Heat (LCOH) and CO₂ emissions for both DH and HP options, enabling a like-for-like comparison at the street level.

**LCOH calculation**: The LCOH is computed using the Capital Recovery Factor (CRF) method over a 20-year lifetime at a 4% discount rate:

$$\text{CRF} = \frac{r(1+r)^n}{(1+r)^n - 1}$$

where $r$ is the discount rate and $n$ is the project lifetime in years.

For district heating, the LCOH includes:
- **CAPEX**: Pipe installation costs (from manufacturer catalog, €50–500/m depending on diameter DN20–DN200), plant cost allocation (using the marginal cost principle — only the incremental capacity expansion cost is allocated to each street, not the sunk cost of the existing CHP plant, at €150/kW marginal), and pump costs (€500/kW).
- **OPEX**: Annual operation and maintenance at 2% of CAPEX, plus fuel costs based on the Cottbus CHP plant's natural gas consumption at €55/MWh with 90% generation efficiency.

For heat pumps, the LCOH includes:
- **CAPEX**: Heat pump installation at €900/kW_th per building, plus any LV grid reinforcement costs (€200/kW_el for feeder upgrades triggered when loading exceeds the 80% planning limit).
- **OPEX**: Annual O&M at 2% of CAPEX, plus electricity consumption at €250/MWh divided by the COP.

**CO₂ emissions**: Annual CO₂ emissions are calculated using fuel-specific emission factors:
- District heating (natural gas CHP): 202 kg CO₂/MWh_fuel (UBA reference) ÷ 0.90 boiler efficiency = 224.4 kg CO₂/MWh_th
- Heat pumps (grid electricity): 350 kg CO₂/MWh_el (German grid mix reference) ÷ COP 2.8 = 125.0 kg CO₂/MWh_th

**Monte Carlo uncertainty propagation**: To assess the robustness of the economic comparison, the system performs a Monte Carlo simulation with a configurable sample size (`n_samples`). In the current agent runtime path, the default is 500 samples (seeded with 42 for reproducibility), but the pipeline supports higher sample counts (e.g., 1,000) when required. Key uncertain parameters (energy prices, CAPEX costs, COP, emission factors) are sampled from their probability distributions. For each sample, the LCOH is recalculated for both options, and the "winner" is recorded. The resulting **win fraction** (e.g., "DH wins in 73% of samples") is used as a robustness metric.

**Sensitivity analysis**: A ±5% perturbation of each input parameter identifies which factors have the greatest influence on the LCOH comparison result.

---

## 5. Decision Engine

The decision engine is a purely deterministic, rule-based system that produces an auditable recommendation. No LLM is involved in the decision itself. The decision follows a four-step cascade:

**Step 1 — Feasibility gate**: If only one option is technically feasible (e.g., heat pumps cause unacceptable grid violations), that option is immediately excluded and the other is recommended. If neither is feasible, the result is `UNDECIDED`.

**Step 2 — Cost dominance**: If both options are feasible, the system compares their LCOH values. If the relative difference exceeds 5% (or the absolute difference exceeds €5/MWh), the cheaper option is recommended as cost-dominant.

**Step 3 — CO₂ tiebreaker**: If costs are within the 5% threshold (i.e., economically equivalent), the option with lower annual CO₂ emissions is preferred. In the edge case of equal CO₂, district heating is chosen as the deterministic default.

**Step 4 — Robustness check**: The Monte Carlo win fraction is evaluated against two thresholds:
- **Robust** (≥70% win fraction): The recommendation is confirmed with high confidence.
- **Sensitive** (≥55% but <70%): The recommendation holds but is flagged as sensitive to parameter uncertainty.
- **Below 55%**: The recommendation is flagged as not robust.

The output is a `DecisionResult` dataclass containing: `choice` ("DH", "HP", or "UNDECIDED"), `robust` (boolean), `reason_codes` (list of step identifiers, e.g., `["COST_DOMINANT_DH", "ROBUST_DECISION"]`), and `metrics_used` (the numerical values that drove the decision).

---

## 6. Explanation Generation and Validation

### 6.1 LLM-Based Explanation Generation

Once a deterministic decision is produced, the UHDC (Unified Heat Decision Context) module generates a human-readable explanation using Google Gemini (temperature=0.0 for reproducibility). The LLM receives the full KPI contract — including LCOH values, CO₂ values, win fractions, feasibility flags, and the deterministic decision result — and is instructed to explain the pre-computed result, not to make its own judgment.

If the LLM API is unavailable, the system falls back to a template-based explanation that inserts the numerical values into predefined sentence structures.

### 6.2 Two-Stage Explanation Validation

The system includes a two-stage validation pipeline for explanations, implemented by the `ValidationAgent`:

**Stage 1 — ClaimExtractor** (quantitative validation): A regex-based extractor identifies 13 types of quantitative claims in the explanation text (LCOH values, CO₂ figures, pressure metrics, Monte Carlo statistics, etc.). Each extracted number is cross-validated against the reference KPI data with a configurable tolerance (default ±10%). Claims that deviate beyond tolerance are flagged as mismatches — potential hallucinations.

**Stage 2 — TNLIModel** (semantic validation): A Tabular Natural Language Inference (TNLI) engine validates qualitative and comparative statements. The explanation is split into individual sentences, and each is evaluated for entailment, neutrality, or contradiction against the KPI table. For example, the statement "District heating is the cheaper option" is checked against the actual LCOH values to confirm entailment. The TNLI engine uses a lightweight rule-based approach with optional Gemini LLM backend for complex statements that rules cannot resolve.

Validation results include: number of claims extracted, number of mismatches, number of TNLI-verified statements, number of contradictions, and an overall pass/fail status.

Note: validation is architecturally available as a dedicated domain agent and can be triggered on-demand with explanation text context. In the current default `EXPLAIN_DECISION` execution plan, validation is not automatically inserted as a mandatory step inside the executor plan.

---

## 7. Capability Guardrails

The system implements explicit capability boundaries to prevent the "crazy agent" failure mode — where an AI system attempts to fulfill an impossible request by hallucinating or looping.

The `CapabilityGuardrail` maintains a registry of unsupported operations (e.g., adding/removing network consumers, connecting to real-time SCADA, legal compliance assessment, multi-street optimization). When a user request matches an unsupported pattern, the system:

1. Immediately stops processing (no simulation is attempted).
2. Returns a structured response explaining what cannot be done and why.
3. Suggests supported alternatives (e.g., "I cannot add a consumer, but I can show you a what-if scenario with fewer houses").
4. Includes a `research_note` explaining that this limitation represents a research boundary, not a bug.
5. Sets `is_research_boundary: true` in the response metadata for thesis documentation purposes.

For `WHAT_IF_SCENARIO` requests, the guardrail applies a finer-grained check: removing houses from the network is supported (the `WhatIfAgent` can clone the pandapipes network, disable heat consumers, and re-run pipeflow), but changing pipe materials or adding new consumers is not.

---

## 8. What-If Scenario Analysis

The `WhatIfAgent` enables counterfactual analysis by modifying the baseline CHA network and comparing results:

1. **Baseline retrieval**: The agent ensures a baseline CHA network exists (delegating to `CHAAgent` if not cached). The serialized pandapipes network (`network.pickle`) is loaded from disk.

2. **Network cloning**: The baseline network is deep-copied using Python's `pickle.loads(pickle.dumps(...))` to create an independent scenario network.

3. **Modification**: The user's modification is parsed (e.g., "remove 2 houses" → `n_houses=2`). The last `n` active heat consumers in the network are disabled by setting `in_service=False` and `qext_w=0.0`.

4. **Scenario simulation**: pandapipes `pipeflow()` is re-run on the modified network with the same solver parameters (mode=all, iter=100, tol_p=1e-4, tol_v=1e-4).

5. **Comparison**: The baseline and scenario networks are compared on three metrics: maximum pressure change (bar), total heat delivered change (MW), and number of pressure violations reduced.

---

## 9. User Interface

The system provides three Streamlit-based interfaces:

**Intent Chat UI** (`app_intent_chat.py`): A split-panel layout with the chat interface occupying 2/5 of the screen and visualizations (bar charts, interactive maps, agent traces) occupying 3/5. This is the primary interface for the conversational workflow. The street is extracted from the natural language query — no dropdown selection is required before chatting.

**Multi-Tab Dashboard** (`app.py`): A traditional tab-based interface with dedicated views for Overview, Feasibility, Economics, Compare & Decide, Intent Chat, Portfolio, and Jobs.

**Conversational UI** (`app_conversational.py`): A minimal chat-first interface with automatic context detection.

All interfaces consume the same `BranitzOrchestrator.route_request()` API, ensuring consistent behavior regardless of the UI variant.

### 9.1 Execution Transparency

Every response includes:
- An **execution log** showing which agents ran and their timing (e.g., `"✓ Used cached CHA (0.002s)"`, `"✓ Calculated ECONOMICS (2.3s)"`).
- An **agent trace** documenting the duty and outcome of each of the six pipeline agents.
- **Suggestion chips** for contextually relevant follow-up queries.
- An expandable **"What was calculated"** panel that visually confirms cache reuse.

This transparency is critical for the thesis demonstration: it provides empirical evidence that the system runs only the required simulations, reuses cached results, and produces deterministic outcomes.

---

## 10. Caching and Performance

The system uses file-based caching exclusively (no in-memory caches that would be lost on restart). Each simulation produces deterministic output files in a structured directory hierarchy:

```
results/{simulation_type}/{cluster_id}/
  ├── cha_kpis.json           # CHA KPIs + topology
  ├── network.pickle          # Serialized pandapipes network
  ├── dha_kpis.json           # DHA grid KPIs
  ├── economics_deterministic.json  # LCOH + CO₂
  ├── monte_carlo_summary.json     # MC statistics
  └── decision_{cluster_id}.json   # Final recommendation
```

Each domain agent checks for the existence of its required output files before running. A full cold-start pipeline (CHA + DHA + Economics + Decision) for one street takes approximately 30–120 seconds depending on network complexity. Subsequent queries for the same street complete in under 100 milliseconds (cache hits only).

---

## 11. Technology Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Hydraulic-thermal simulation | pandapipes | Open-source, EN 13941-1 compatible, Python-native |
| LV grid simulation | pandapower | Open-source, IEC 60909 / VDE-AR-N 4100 compatible |
| LLM / NLU | Google Gemini API | Structured JSON output, temperature=0.0 for determinism, multilingual |
| Explanation validation | Custom TNLI (rule-based + optional LLM) | Lightweight, no GPU required, extensible rules |
| User interface | Streamlit | Rapid prototyping, native Python, interactive widgets |
| Map visualization | Folium | Leaflet.js-based, GeoJSON support, embeddable in Streamlit |
| Charts | Altair | Declarative, Vega-Lite based, responsive |
| Uncertainty analysis | NumPy / SciPy | Standard scientific computing, Monte Carlo sampling |
| Network topology | NetworkX | Graph algorithms for trunk-spur construction |
| Data processing | pandas / geopandas | GIS-aware DataFrame operations, Parquet I/O |

---

## 12. Standards Compliance

| Standard | Application | Implementation |
|----------|------------|----------------|
| EN 13941-1 | District heating pipe design | Velocity limits, pressure drop limits, thermal loss calculation, pipe sizing catalog |
| VDE-AR-N 4100 | LV grid connection rules | Voltage band compliance (±10%), line loading limits, hosting capacity assessment |
| BDEW | Heat demand profiles | Standard load profiles for residential heating demand estimation |
| UBA emission factors | CO₂ calculation | German-specific emission factors: 202 kg CO₂/MWh for natural gas, 350 kg CO₂/MWh for grid electricity |

---

## 13. Reproducibility and Determinism

The system is designed for full reproducibility:

1. **No stochastic decisions**: The decision engine is purely rule-based. Running the same KPI contract through `decide_from_contract()` always produces the same `DecisionResult`.

2. **LLM determinism**: All LLM calls use temperature=0.0. While this does not guarantee identical token sequences across API versions, the downstream validation pipeline catches any semantic deviations.

3. **Monte Carlo seeding**: The Monte Carlo simulation accepts a seed parameter (default=42) for reproducible sampling.

4. **File-based state**: All intermediate results are persisted as JSON or Parquet files. The system can be restarted and will produce identical responses from cached data.

5. **Validation as a contract**: The ClaimExtractor + TNLI pipeline serves as an automated consistency check. If the LLM produces a different explanation on a second run, the validation pipeline will catch any factual deviations from the reference KPIs.

---

## 14. Limitations and Research Boundaries

The following limitations are explicitly encoded in the system's capability guardrail and documented as research boundaries:

| Limitation | Category | Research Note |
|-----------|----------|---------------|
| Cannot add/remove consumers from the network | Topology modification | Requires pandapipes network builder extension; planned for future work |
| Cannot change pipe materials or diameters post-simulation | Design parameter modification | Would require re-running the full CHA pipeline with modified catalog |
| No real-time SCADA integration | Data source | System uses static design-day analysis, not real-time operational data |
| Single-street analysis only | Scope | Multi-street portfolio optimization is architecturally supported but not implemented |
| No legal compliance assessment | Domain | Legal assessment requires domain expertise beyond the simulation scope |
| Heat pump COP is static (2.8) | Model simplification | Dynamic COP based on outdoor temperature profiles is a planned enhancement |
| German grid mix emission factor is static | Model simplification | Time-varying marginal emission factors would improve accuracy |

Each limitation, when triggered by a user query, produces a structured response with the `is_research_boundary: true` flag, an explanation of why it is out of scope, and a list of supported alternatives.
