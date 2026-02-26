# Findings: Agent Cycle Analysis of the Branitz Heat Decision System

## Purpose

This note analyzes the project using the classical intelligent-agent cycle:

1. **Perceive** environment state
2. **Recognize/Interpret** the situation
3. **Plan** next action
4. **Act** through actuators
5. **Environment changes**, then cycle repeats

The question is: *Does the current system behave like an agentic cycle?*  
Short answer: **yes**, but as a **hierarchical, simulation-centric, partially closed-loop agent system** (not a physical real-time control agent).

---

## Diagram: Hierarchical Agent Cycle

```mermaid
flowchart TD
    U[User Query + Context] --> O1

    subgraph L1[Layer 1 - Orchestration Agents]
        O1[1. NLU Intent Classifier<br/>Perceive + Recognize]
        O2[2. Conversation Manager<br/>Perceive Memory + Recognize Follow-up]
        O3[3. Street Resolver<br/>Recognize/Disambiguate Street]
        O4[4. Capability Guardrail<br/>Policy Recognition]
        O5[5. Execution Planner<br/>Plan]
        O6[6. Dynamic Executor<br/>Meta-Plan + Delegate]
        O1 --> O2 --> O3 --> O4 --> O5 --> O6
    end

    O4 -->|Unsupported| F[Fallback Response<br/>I cannot... + alternatives]
    F --> E2[Environment Update:<br/>agent_trace + boundary metadata]

    O6 --> D1

    subgraph L25[Layer 2.5 - Domain Agents]
        D1[DataPrepAgent]
        D2[CHAAgent]
        D3[DHAAgent]
        D4[EconomicsAgent]
        D5[DecisionAgent]
        D6[ValidationAgent]
        D7[UHDCAgent]
        D8[WhatIfAgent]
    end

    O6 -->|intent-based plan| D2
    O6 -->|intent-based plan| D3
    O6 -->|intent-based plan| D4
    O6 -->|intent-based plan| D5
    O6 -->|intent-based plan| D8
    O6 -->|optional| D1
    O6 -->|optional| D6
    O6 -->|optional| D7

    D2 --> C[(Cache/Files<br/>results/cha/...)]
    D3 --> C2[(Cache/Files<br/>results/dha/...)]
    D4 --> C3[(Cache/Files<br/>results/economics/...)]
    D5 --> C4[(Cache/Files<br/>results/decision/...)]
    D8 --> C5[(Baseline network.pickle)]

    D2 -->|cache miss| A2
    D3 -->|cache miss| A3
    D4 -->|cache miss| A4
    D5 -->|cache miss| A5
    D7 -->|cache miss| A6
    D1 -->|cache miss| A1

    subgraph L3[Layer 3 - ADK Agents (Policy + Trajectory + Timing)]
        A1[ADK DataPrepAgent]
        A2[ADK CHAAgent]
        A3[ADK DHAAgent]
        A4[ADK EconomicsAgent]
        A5[ADK DecisionAgent]
        A6[ADK UHDCAgent]
    end

    A1 --> T1
    A2 --> T2
    A3 --> T3
    A4 --> T4
    A5 --> T5
    A6 --> T6

    subgraph L4[Layer 4 - Tools / Scripts / Engines]
        T1[prepare_data_tool -> 00_prepare_data.py]
        T2[run_cha_tool -> pandapipes]
        T3[run_dha_tool -> pandapower]
        T4[run_economics_tool -> LCOH/CO2/MC]
        T5[run_decision_tool -> deterministic rules]
        T6[run_uhdc_tool -> report generation]
    end

    T1 --> E[Environment Change:<br/>new/updated files + KPIs + reports]
    T2 --> E
    T3 --> E
    T4 --> E
    T5 --> E
    T6 --> E
    D8 --> E
    D6 --> E

    E --> O6
    O6 --> R[Integrated Result<br/>execution_log + agent_results]
    R --> UI[UI Response + Visualization + Suggestions]
    UI --> M[(Conversation Memory Update)]
    M --> O2

    E2 --> UI
```

---

## 1) What is the “environment” in this project?

The system has multiple environment layers:

- **User interaction environment**: user queries, follow-up context, requested streets/intents
- **Data environment**: raw/processed datasets and result files on disk
- **Simulation environment**: pandapipes/pandapower models and their numerical states
- **Policy environment**: guardrails and capability boundaries
- **Session memory environment**: conversation memory (`current_street`, cached data availability)

So this is not a robot-style physical environment; it is a **computational decision environment**.

---

## 2) Perceive → Recognize → Plan → Act mapping (system-level)

## Perceive

- Reads `user_query`, optional `cluster_id`, conversation history
- Reads available streets and cached result files
- Reads previous session memory (`ConversationMemory`)
- Reads policy constraints (`CapabilityGuardrail`)

## Recognize

- NLU classifies intent and entities
- Conversation manager detects follow-up and metric-switch patterns
- Street resolver maps free-text street mentions to valid cluster IDs
- Guardrail recognizes unsupported/partial requests

## Plan

- Execution planner maps intent to required tools/agents
- `DynamicExecutor._create_agent_plan()` builds dependency-ordered domain-agent plans
- Domain agents check prerequisites and cache availability
- ADK layer validates whether an action is policy-compliant

## Act

- Domain agents execute simulations (or load cache)
- ADK agents call tool functions and scripts
- Simulations produce files and metrics
- Orchestrator returns formatted answer, charts, execution log, agent trace, suggestions

## Environment Change

- New result files are written or reused
- Conversation memory updates (`current_street`, `available_data`, `last_calculation`)
- Subsequent user turns are interpreted against this updated state

This creates a practical closed loop across chat turns.

---

## 3) Agent taxonomy in your architecture

Your agents are best described as a **hybrid of model-based, goal-based, and rule-based agents**.

### A) Orchestration agents (Layer 1)

- **NLU Intent Classifier**: interpretive agent (semantic perception)
- **Conversation Manager**: memory/state agent (context persistence)
- **Street Resolver**: state disambiguation agent
- **Capability Guardrail**: safety/supervisory rule-based agent
- **Execution Planner**: plan synthesis agent
- **Dynamic Executor**: workflow control agent coordinating specialists

### B) Domain specialist agents (Layer 2.5)

- `CHAAgent`, `DHAAgent`, `EconomicsAgent`, `DecisionAgent`, `UHDCAgent`, `WhatIfAgent`, etc.
- Each has local state logic: cache checks, prerequisite checks, result interpretation
- These are **goal-directed specialist agents** for one domain function

### C) ADK agents (Layer 3)

- Tool-execution agents with policy enforcement and trajectory tracking
- These are **rule-governed execution agents** with explicit action logs (`AgentAction`)

### D) Validation agent type

- `ValidationAgent` is a **critic/auditor agent** (checks consistency of generated explanations)
- Uses ClaimExtractor + TNLI for factual and semantic verification

---

## 4) Sensor / Actuator view (thesis-friendly framing)

## Sensors (Perception channels)

- User text input and history
- Intent classifier output (intent, entities, confidence)
- Conversation memory
- Filesystem cache and result artifacts
- Policy registries and unsupported keyword detectors
- Simulation output files (JSON, pickle, geojson, html)

## Internal world model

- Intent-to-plan mappings
- Dependency graph among domain computations
- Capability model (`SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, `FUTURE`)
- KPI contract (for decision and explanation validation)

## Actuators (Action channels)

- Tool invocations (`run_cha_tool`, `run_dha_tool`, `run_economics_tool`, etc.)
- Script executions that trigger numerical simulation
- Response generation (answer text, visualization metadata, suggestions)
- Memory updates and state transitions

---

## 5) How “agentic” is it? (assessment)

### Strong agentic properties (present)

- **Hierarchical delegation** (meta-agent -> specialist agents)
- **Stateful behavior** via conversation memory and file-based world state
- **Deliberation/planning** via intent-to-agent plans and prerequisites
- **Adaptive behavior** (cache hit vs. recomputation, follow-up reuse)
- **Safety supervision** via guardrails and policy enforcement
- **Self-explanation hooks** through execution logs and agent traces

### Not fully autonomous in the RL sense

- No continuous online learning from feedback
- No reward optimization loop updating policy parameters
- Mostly deterministic planning templates, not open-ended planning search
- Environment changes are primarily computational artifacts, not physical control actions

Conclusion: this is a **deterministic, auditable, hierarchical cognitive workflow agent system**, ideal for decision support and research reproducibility.

---

## 6) Per-agent cycle examples

### Example 1: `EconomicsAgent`

1. **Perceive**: checks if CHA/DHA outputs exist + whether economics cache exists
2. **Recognize**: identifies if prerequisites are missing / cache hit / cache miss
3. **Plan**: choose cached-return path or ADK execution path
4. **Act**: either load `economics_deterministic.json` or run ADK economics tool
5. **Environment change**: economics result files generated/updated

### Example 2: `WhatIfAgent`

1. **Perceive**: reads modification request + baseline network file
2. **Recognize**: parses number of houses to remove; validates feasible modification
3. **Plan**: baseline load -> clone -> modify -> rerun pipeflow -> compare
4. **Act**: applies network modification and executes pandapipes
5. **Environment change**: scenario output and comparison metrics returned; follow-up can build on this

### Example 3: `CapabilityGuardrail`

1. **Perceive**: intent + entities + query text
2. **Recognize**: unsupported intent/keyword or partial capability
3. **Plan**: block, clarify, or allow
4. **Act**: return structured fallback with alternatives or permit execution
5. **Environment change**: route changes to fallback path instead of simulation path

---

## 7) Proposed thesis wording (ready to reuse)

"The Branitz system implements a hierarchical multi-agent architecture in which each request is processed through an explicit perceive-recognize-plan-act cycle. Perception combines natural-language input, conversation memory, cached simulation artifacts, and capability constraints. Recognition is performed by intent classification, follow-up resolution, street disambiguation, and guardrail validation. Planning occurs at two levels: global intent-to-agent sequencing in the Dynamic Executor, and local cache/prerequisite planning within each domain agent. Actions are executed through policy-constrained ADK agents that invoke deterministic simulation tools (CHA, DHA, economics, decision, UHDC). Environment updates occur through persisted result artifacts and updated conversation state, enabling closed-loop multi-turn behavior with transparent execution logs and full agent traces." 

---

## 8) Final finding

Your project **does satisfy the agent-cycle concept**, but in a software decision-support form:

- It is not a single monolithic agent.
- It is a **multi-agent, hierarchical cycle system** with explicit safety boundaries.
- It is particularly strong for thesis use because it is deterministic, auditable, explainable, and reproducible.
