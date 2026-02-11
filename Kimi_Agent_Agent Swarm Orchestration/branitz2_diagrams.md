# Branitz2: Multi-Agent Framework for Climate-Neutral Urban Heat Planning
## Publication-Quality Mermaid Diagrams

---

## 1. High-Level System Architecture

**Description:** Shows the complete data flow from raw GIS data through all agents to the final validated report. The LogicAuditor serves as a safety check on the UHDC Agent's LLM-generated explanations.

```mermaid
flowchart TB
    subgraph Input["📥 Input Layer"]
        GIS["GIS Data<br/>• Building footprints<br/>• Street network<br/>• Demographics"]
        Weather["Weather Data<br/>• 8760h temperature profiles<br/>• Solar irradiance"]
        Standards["Technical Standards<br/>• EN 13941-1 (DH)<br/>• VDE-AR-N 4100 (LV)"]
    end

    subgraph Agents["🤖 Agent Layer"]
        direction TB
        DataAgent["Data Agent<br/>• Heat demand profiles<br/>• Design hours"]
        CHA["CHA Agent<br/>• pandapipes simulation<br/>• Trunk-spur topology"]
        DHA["DHA Agent<br/>• pandapower LV grid<br/>• Heat pump analysis"]
        Econ["Economics Agent<br/>• Monte Carlo LCOH<br/>• CO₂ emissions"]
        Decision["Decision Agent<br/>• Rules engine<br/>• KPI evaluation"]
    end

    subgraph Coordination["🎯 Coordination Layer"]
        KPI["KPI Contract<br/>(Schema-Checked JSON)<br/>Single Source of Truth"]
        UHDC["UHDC Agent<br/>• Constrained LLM (Gemini)<br/>• Read-only coordinator"]
    end

    subgraph Validation["✅ Validation Layer"]
        LogicAuditor["LogicAuditor<br/>• TNLI-based validation<br/>• Claim extraction & verification"]
    end

    subgraph Output["📤 Output Layer"]
        Report["Validated Report<br/>• System recommendations<br/>• Uncertainty quantification<br/>• Explainable decisions"]
    end

    %% Data Flow
    GIS --> DataAgent
    Weather --> DataAgent
    Standards --> CHA
    Standards --> DHA

    DataAgent --> CHA
    DataAgent --> DHA
    CHA --> KPI
    DHA --> KPI
    KPI --> Econ
    Econ --> KPI
    KPI --> Decision
    Decision --> KPI

    KPI --> UHDC
    UHDC --> LogicAuditor
    LogicAuditor -->|"Safe / Unsafe"| UHDC
    UHDC --> Report

    %% Styling
    classDef inputStyle fill:#e8f4f8,stroke:#2c5f6f,stroke-width:2px
    classDef agentStyle fill:#f0f8e8,stroke:#4a6f2c,stroke-width:2px
    classDef coordStyle fill:#fff4e6,stroke:#8b5a00,stroke-width:2px
    classDef validStyle fill:#ffe8e8,stroke:#8b0000,stroke-width:2px
    classDef outputStyle fill:#f0e8f8,stroke:#5a2c6f,stroke-width:2px

    class GIS,Weather,Standards inputStyle
    class DataAgent,CHA,DHA,Econ,Decision agentStyle
    class KPI,UHDC coordStyle
    class LogicAuditor validStyle
    class Report outputStyle
```

---

## 2. Multi-Agent Interaction with KPI Contracts

**Description:** Illustrates how all agents communicate through the central KPI Contract, which acts as a schema-checked JSON hub ensuring data consistency and traceability across the multi-agent system.

```mermaid
flowchart LR
    subgraph Agents["Agent Nodes"]
        Data["📊 Data Agent"]
        CHA["🔥 CHA Agent"]
        DHA["⚡ DHA Agent"]
        Econ["💰 Economics Agent"]
        Decision["🎯 Decision Agent"]
        UHDC["🧠 UHDC Agent"]
    end

    subgraph Contract["KPI Contract Hub"]
        KPI["{
            'heat_demand_MWh': [...],
            'network_topology': {...},
            'grid_loading': {...},
            'lcoe_eur_mwh': {...},
            'co2_tons': {...},
            'win_fraction': {...},
            'recommendation': {...}
        }"]
    end

    subgraph Schema["JSON Schema Validation"]
        SchemaCheck["✓ Type checking<br/>✓ Range validation<br/>✓ Required fields<br/>✓ Cross-reference integrity"]
    end

    %% Bidirectional connections to KPI Contract
    Data <-->|"heat profiles<br/>design hours"| KPI
    CHA <-->|"pipe diameters<br/>pressure losses<br/>heat losses"| KPI
    DHA <-->|"voltage levels<br/>transformer loads<br/>HP consumption"| KPI
    Econ <-->|"LCOH distribution<br/>CO₂ emissions<br/>quantiles"| KPI
    Decision <-->|"rules evaluation<br/>win fraction<br/>ranking"| KPI
    UHDC <-->|"explanations<br/>recommendations"| KPI

    KPI --> SchemaCheck
    SchemaCheck -->|"Validation OK"| KPI

    %% Styling
    classDef agentStyle fill:#e8f4f8,stroke:#2c5f6f,stroke-width:2px
    classDef hubStyle fill:#fff4e6,stroke:#8b5a00,stroke-width:3px
    classDef schemaStyle fill:#e8f8e8,stroke:#2c6f4a,stroke-width:2px

    class Data,CHA,DHA,Econ,Decision,UHDC agentStyle
    class KPI hubStyle
    class SchemaCheck schemaStyle
```

---

## 3. TNLI Logic Auditor Sequence Diagram

**Description:** Shows the complete validation workflow: the UHDC Agent's LLM generates an explanation, the LogicAuditor extracts factual claims, validates them against the KPI Contract data, and returns a safe/unsafe verdict with justification.

```mermaid
sequenceDiagram
    autonumber
    participant UHDC as UHDC Agent<br/>(Gemini LLM)
    participant LLM as LLM Engine
    participant LA as LogicAuditor
    participant CE as Claim Extractor
    participant VE as Validation Engine
    participant KPI as KPI Contract
    participant User as User/Report

    Note over UHDC,KPI: TNLI-Based Explanation Validation Workflow

    UHDC->>+LLM: Generate explanation for<br/>recommendation decision
    LLM-->>-UHDC: Natural language explanation<br/>(e.g., "Centralized heating is 15% cheaper")

    UHDC->>+LA: Submit explanation for validation

    LA->>+CE: Extract factual claims
    CE->>CE: Parse sentences →<br/>identify numerical claims
    CE-->>-LA: Claim list:<br/>[C1: "15% cheaper", C2: "LCOH = 45€/MWh"]

    loop For each claim
        LA->>+VE: Validate claim Ci
        VE->>+KPI: Query relevant KPI data
        KPI-->>-VE: Return ground truth values
        VE->>VE: Apply TNLI model:<br/>entailment / contradiction / neutral
        VE-->>-LA: Validation result:<br/>{claim: Ci, status: pass/fail,<br/>confidence: 0.92}
    end

    LA->>LA: Aggregate results:<br/>All claims pass? → SAFE<br/>Any claim fail? → UNSAFE

    alt All Claims Valid
        LA-->>UHDC: ✅ VERDICT: SAFE<br/>Explanation approved
        UHDC->>User: Include in validated report
    else Any Claim Invalid
        LA-->>-UHDC: ❌ VERDICT: UNSAFE<br/>Failed claims: [C1, C3]<br/>Suggested correction: ...
        UHDC->>+LLM: Regenerate with constraints
        LLM-->>-UHDC: Revised explanation
        UHDC->>LA: Re-submit for validation
    end

    Note right of LA: TNLI = Textual Entailment<br/>for Natural Language Inference
```

---

## 4. Trunk-Spur Topology Example

**Description:** Visualizes a typical district heating network topology with a CHP plant feeding into trunk mains (high-capacity pipes) with extensions and buildings connected via spur pipes (lower-capacity connections).

```mermaid
flowchart LR
    subgraph Source["Heat Source"]
        CHP["🏭 CHP Plant<br/>90°C supply<br/>60°C return"]
    end

    subgraph Trunk["Trunk Network (Primary)"]
        TM1["Trunk Main A<br/>DN 200<br/>L = 500m"]
        TM2["Trunk Main B<br/>DN 150<br/>L = 400m"]
        TE1["Trunk Ext. C<br/>DN 100<br/>L = 300m"]
        TE2["Trunk Ext. D<br/>DN 100<br/>L = 250m"]
    end

    subgraph Spurs["Spur Connections (Secondary)"]
        S1["Spur 1<br/>DN 50<br/>→ Building A"]
        S2["Spur 2<br/>DN 40<br/>→ Building B"]
        S3["Spur 3<br/>DN 50<br/>→ Building C"]
        S4["Spur 4<br/>DN 40<br/>→ Building D"]
        S5["Spur 5<br/>DN 32<br/>→ Building E"]
    end

    subgraph Buildings["Connected Buildings"]
        B1["🏢 Building A<br/>Q = 250 kW"]
        B2["🏠 Building B<br/>Q = 180 kW"]
        B3["🏢 Building C<br/>Q = 300 kW"]
        B4["🏠 Building D<br/>Q = 150 kW"]
        B5["🏠 Building E<br/>Q = 120 kW"]
    end

    %% Connections
    CHP -->|"Supply"| TM1
    TM1 --> TM2
    TM1 --> TE1
    TM2 --> TE2

    TM1 --> S1
    TE1 --> S2
    TE1 --> S3
    TE2 --> S4
    TE2 --> S5

    S1 --> B1
    S2 --> B2
    S3 --> B3
    S4 --> B4
    S5 --> B5

    %% Return lines (dashed)
    B1 -.->|"Return"| S1
    B2 -.->|"Return"| S2
    B3 -.->|"Return"| S3
    B4 -.->|"Return"| S4
    B5 -.->|"Return"| S5

    S1 -.-> TM1
    S2 -.-> TE1
    S3 -.-> TE1
    S4 -.-> TE2
    S5 -.-> TE2

    TE2 -.-> TM2
    TE1 -.-> TM1
    TM2 -.-> TM1
    TM1 -.-> CHP

    %% Styling
    classDef sourceStyle fill:#ff6b6b,stroke:#8b0000,stroke-width:3px,color:#fff
    classDef trunkStyle fill:#4ecdc4,stroke:#006b6b,stroke-width:3px
    classDef spurStyle fill:#95e1d3,stroke:#2c5f5f,stroke-width:2px
    classDef buildingStyle fill:#f7dc6f,stroke:#8b6914,stroke-width:2px

    class CHP sourceStyle
    class TM1,TM2,TE1,TE2 trunkStyle
    class S1,S2,S3,S4,S5 spurStyle
    class B1,B2,B3,B4,B5 buildingStyle
```

---

## 5. Monte Carlo Workflow

**Description:** Illustrates the uncertainty propagation workflow: input parameters are sampled from distributions, fed through the LCOH calculation model, and results are aggregated into quantiles (P10/P50/P90) and win fractions for decision-making.

```mermaid
flowchart TB
    subgraph Inputs["Input Parameter Distributions"]
        P1["Heat Demand<br/>μ = 1000 MWh<br/>σ = 100 MWh<br/>Normal"]
        P2["Gas Price<br/>λ = 0.05<br/>Scale = 4€/MWh<br/>Log-Normal"]
        P3["Electricity Price<br/>α = 3, β = 2<br/>Beta distribution"]
        P4["CAPEX<br/>Min = 500€/kW<br/>Max = 800€/kW<br/>Uniform"]
        P5["Interest Rate<br/>μ = 3%, σ = 0.5%<br/>Truncated Normal"]
    end

    subgraph Sampling["Monte Carlo Sampling"]
        MC["N = 500 Samples<br/>Latin Hypercube<br/>Sobol sequences"]
    end

    subgraph Model["LCOH Calculation Model"]
        LCOH["For each sample:<br/>LCOH = (CAPEX × CRF + OPEX) /<br/>Annual Heat Output"]
    end

    subgraph Output["Output Aggregation"]
        Q["Quantile Extraction"]
        P10["P10<br/>(Optimistic)"]
        P50["P50<br/>(Median)"]
        P90["P90<br/>(Conservative)"]
        WF["Win Fraction<br/>P(LCOH_A < LCOH_B)"]
    end

    subgraph Decision["Decision Support"]
        RES["Result:<br/>• LCOH distribution<br/>• Uncertainty bands<br/>• Confidence intervals"]
    end

    %% Flow
    P1 & P2 & P3 & P4 & P5 --> MC
    MC -->|"Sample vectors<br/>(500 × 5)"| LCOH
    LCOH -->|"500 LCOH values"| Q
    Q --> P10
    Q --> P50
    Q --> P90
    Q --> WF

    P10 & P50 & P90 & WF --> RES

    %% Styling
    classDef inputStyle fill:#e8f4f8,stroke:#2c5f6f,stroke-width:2px
    classDef sampleStyle fill:#fff4e6,stroke:#8b5a00,stroke-width:2px
    classDef modelStyle fill:#f0e8f8,stroke:#5a2c6f,stroke-width:2px
    classDef outputStyle fill:#e8f8e8,stroke:#2c6f4a,stroke-width:2px
    classDef decisionStyle fill:#ffe8e8,stroke:#8b0000,stroke-width:3px

    class P1,P2,P3,P4,P5 inputStyle
    class MC sampleStyle
    class LCOH modelStyle
    class Q,P10,P50,P90,WF outputStyle
    class RES decisionStyle
```

---

## 6. Zero-to-Hero Pipeline Flowchart

**Description:** The complete end-to-end pipeline showing sequential agent execution from raw data input through to the final validated report, with the LogicAuditor ensuring explanation quality at the final stage.

```mermaid
flowchart TB
    subgraph Start["🚀 Initialization"]
        Input["Raw Input Data:<br/>• GIS building data<br/>• Weather profiles<br/>• Economic parameters<br/>• Technical standards"]
    end

    subgraph Pipeline["Sequential Agent Pipeline"]
        direction TB
        Step1["1️⃣ Data Agent<br/>Generate 8760h heat profiles<br/>Identify design hours<br/>Calculate heat demand density"]

        Step2["2️⃣ CHA Agent<br/>pandapipes simulation<br/>Design trunk-spur topology<br/>Size pipes & pumps<br/>Calculate heat losses"]

        Step3["3️⃣ DHA Agent<br/>pandapower LV grid analysis<br/>Heat pump electrical load<br/>Voltage drop check<br/>Transformer sizing"]

        Step4["4️⃣ Economics Agent<br/>Monte Carlo simulation (N=500)<br/>LCOH calculation<br/>CO₂ emissions analysis<br/>Uncertainty quantification"]

        Step5["5️⃣ Decision Agent<br/>Apply decision rules<br/>Calculate win fraction<br/>Rank alternatives<br/>Generate recommendation"]

        Step6["6️⃣ UHDC Agent<br/>Constrained LLM (Gemini)<br/>Generate explanations<br/>Synthesize findings<br/>Draft report"]
    end

    subgraph Validation["🔍 Safety Check"]
        Step7["7️⃣ LogicAuditor<br/>TNLI-based validation<br/>Extract & verify claims<br/>Safe/Unsafe verdict"]
    end

    subgraph End["📋 Output"]
        Output["Validated Final Report:<br/>• System recommendation<br/>• Uncertainty bounds (P10/P50/P90)<br/>• Explainable justification<br/>• Technical documentation"]
    end

    %% Flow
    Input --> Step1
    Step1 -->|"Heat profiles<br/>Design hours"| Step2
    Step2 -->|"Network design<br/>Hydraulic results"| Step3
    Step3 -->|"Grid loading<br/>HP consumption"| Step4
    Step4 -->|"LCOH distribution<br/>CO₂ results"| Step5
    Step5 -->|"Recommendation<br/>Win fraction"| Step6
    Step6 -->|"Explanation draft"| Step7

    Step7 -->|"✅ SAFE"| Output
    Step7 -.->|"❌ UNSAFE<br/>Regenerate"| Step6

    %% KPI Contract connections (dashed)
    Step1 -.->|"Updates"| KPI["KPI Contract"]
    Step2 -.->|"Updates"| KPI
    Step3 -.->|"Updates"| KPI
    Step4 -.->|"Updates"| KPI
    Step5 -.->|"Updates"| KPI
    Step6 -.->|"Reads"| KPI
    Step7 -.->|"Validates against"| KPI

    %% Styling
    classDef startStyle fill:#e8f4f8,stroke:#2c5f6f,stroke-width:2px
    classDef pipelineStyle fill:#f0f8e8,stroke:#4a6f2c,stroke-width:2px
    classDef validationStyle fill:#ffe8e8,stroke:#8b0000,stroke-width:3px
    classDef endStyle fill:#f0e8f8,stroke:#5a2c6f,stroke-width:3px
    classDef kpiStyle fill:#fff4e6,stroke:#8b5a00,stroke-width:2px,stroke-dasharray: 5 5

    class Input startStyle
    class Step1,Step2,Step3,Step4,Step5,Step6 pipelineStyle
    class Step7 validationStyle
    class Output endStyle
    class KPI kpiStyle
```

---

## Summary

This document contains six publication-quality Mermaid diagrams for the Branitz2 thesis presentation:

| # | Diagram | Purpose |
|---|---------|---------|
| 1 | **High-Level System Architecture** | Overview of data flow from inputs to validated output |
| 2 | **Multi-Agent Interaction with KPI Contracts** | Central hub architecture showing agent communication |
| 3 | **TNLI Logic Auditor Sequence Diagram** | Step-by-step validation workflow |
| 4 | **Trunk-Spur Topology Example** | Visual network topology with color-coded pipes |
| 5 | **Monte Carlo Workflow** | Uncertainty propagation from distributions to quantiles |
| 6 | **Zero-to-Hero Pipeline Flowchart** | Complete sequential pipeline with feedback loop |

### Design Principles Applied

- **Academic styling**: Subdued, professional color palettes
- **Clear hierarchy**: Visual distinction between layers and components
- **Consistent notation**: Standardized symbols and labels
- **Information density**: Appropriate detail for publication quality
- **Standards compliance**: References to EN 13941-1 and VDE-AR-N 4100
