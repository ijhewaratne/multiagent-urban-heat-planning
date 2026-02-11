# Branitz2: Explainable Multi-Physics Decision Intelligence
## For Climate-Neutral Urban Heat Planning

**Author:** Ishantha Hewaratne | Fraunhofer IEG  
**Meeting:** Thesis Committee Meeting #1 - The Vision  
**Duration:** 15 minutes (with Q&A buffer)

---

## SLIDE 1: Title & Hook (2 minutes)

### Visual Description
- Clean, professional title slide with Fraunhofer IEG branding
- Subtle background: abstract network visualization showing heat pipes (red) and electrical grid (blue) converging
- Small icons: thermometer, lightning bolt, shield (representing thermal, electrical, safety)

### Slide Content

**Title:** Branitz2: Explainable Multi-Physics Decision Intelligence for Climate-Neutral Urban Heat Planning

**Subtitle:** A Multi-Agent Framework Coupling Hydraulic-Thermal District Heating with Low-Voltage Electrical Grids

**Author:** Ishantha Hewaratne  
**Supervisor:** [Supervisor Name]  
**Institution:** Fraunhofer Institute for Energy Infrastructures and Geothermal (IEG)

**Key Innovation Tags (bottom of slide):**
- True Multi-Physics Coupling
- Uncertainty-Aware Decision Making
- LLM Safety via TNLI
- Standards-Compliant Automation

---

### Speaker Notes (2:00)

> *[0:00-0:15]* Good morning, everyone. Thank you for joining this first thesis committee meeting. My name is Ishantha Hewaratne, and today I'll present the vision and core innovations of my doctoral thesis: **Branitz2**.

> *[0:15-0:45]* The title is intentionally dense—let me unpack it. "Explainable Multi-Physics Decision Intelligence" captures our three core contributions: we combine **thermal** district heating simulation with **electrical** grid analysis, we make decisions under uncertainty using Monte Carlo methods, and we explain those decisions using constrained large language models with a novel safety mechanism.

> *[0:45-1:15]* Why "Branitz2"? The name pays homage to the historic Branitz district heating network in Cottbus, Germany—one of Europe's oldest DH systems. The "2" signifies our second-generation approach: moving from single-domain analysis to true multi-physics coupling.

> *[1:15-2:00]* The context is urgent: Germany's Building Energy Act (GEG 2024) mandates climate-neutral heating by 2045. Yet planners lack integrated tools that can simultaneously optimize heat networks AND ensure electrical grid compatibility. Branitz2 fills this gap. Today, I'll show you how.

---

## SLIDE 2: The Problem Gap (3 minutes)

### Visual Description
- Four-quadrant layout showing the gaps
- Each quadrant has an icon and brief description
- Central "gap" visualization showing disconnected puzzle pieces
- Color coding: Red = Problem, Green = Our Solution (subtle)

### Slide Content

**Title:** The Four Critical Gaps in Urban Heat Planning

| Gap | Current State | Impact |
|-----|---------------|--------|
| **1. Siloed Analysis** | DH tools (pandapipes) and LV tools (pandapower) operate independently | Suboptimal designs, missed constraints |
| **2. Black-Box AI** | Optimization results lack auditability | Regulatory rejection, planner distrust |
| **3. Manual Compliance** | EN 13941-1, VDE-AR-N 4100 checked by hand | Error-prone, time-consuming |
| **4. Deterministic Models** | LCOH calculations ignore price volatility | Fragile decisions, cost overruns |

**Central Insight:** *"Urban heat planning requires simultaneous optimization across thermal, hydraulic, and electrical domains—yet no existing tool does this."*

---

### Speaker Notes (3:00)

> *[0:00-0:45]* Let me walk you through the four critical gaps that motivated this work. First, **siloed analysis**. Current practice uses pandapipes for district heating and pandapower for electrical grids—but these are never coupled. A heat pump's impact on the LV grid? Manual guesswork. This leads to suboptimal designs and, worse, missed constraints that emerge only during operation.

> *[0:45-1:30]* Second, **black-box AI**. Machine learning optimization is powerful, but when a planner asks "why this network topology?"—silence. This isn't just inconvenient; it's a regulatory barrier. German approval processes require auditable decision trails. Black-box models get rejected.

> *[1:30-2:15]* Third, **manual compliance**. Standards like EN 13941-1 for DH networks and VDE-AR-N 4100 for LV grids are checked by hand. For a complex urban quarter, this takes weeks. And humans make mistakes—especially with the thousands of constraints these standards encode.

> *[2:15-3:00]* Finally, **deterministic models**. Levelized Cost of Heat calculations use single-point estimates. But electricity prices? They vary by 300% between peak and off-peak. Gas prices? Volatile since 2022. Ignoring this uncertainty produces fragile decisions that fail under real-world conditions.

---

## SLIDE 3: The Innovation Architecture (5 minutes)

### Visual Description
- Large, central architecture diagram
- Five colored layers stacked vertically
- Data flow arrows showing information movement
- Agent icons (robot heads) at each layer
- Small insets showing: Monte Carlo distribution, TNLI validation flow, KPI Contract schema

### Slide Content

**Title:** The Branitz2 Architecture: Five Layers of Innovation

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5: EXPLANATION (LogicAuditor Agent)                  │
│  → Constrained Gemini LLM + TNLI Validation                 │
├─────────────────────────────────────────────────────────────┤
│  LAYER 4: DECISION (Arbiter Agent)                          │
│  → Monte Carlo Win Fractions → Robustness Classification    │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3: ECONOMICS (LCOH Agent)                            │
│  → N=500 samples, Uncertainty-aware cost analysis           │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: SIMULATION (CHA + DHA Agents)                     │
│  → pandapipes + pandapower coupling                         │
├─────────────────────────────────────────────────────────────┤
│  LAYER 1: DATA (Profile Agent)                              │
│  → KPI Contract (Schema-Validated Single Source of Truth)   │
└─────────────────────────────────────────────────────────────┘
```

**Five Innovations (with icons):**
1. 🔗 **True Multi-Physics**: First coupling of pandapipes + pandapower
2. 📋 **KPI Contract**: Canonical schema prevents "garbage in, garbage out"
3. 🛡️ **TNLI Safety**: Tabular NLI validates LLM explanations against data
4. 📊 **Uncertainty-Aware**: Monte Carlo win fractions drive decisions
5. ✅ **Standards Compliance**: Automated EN 13941-1 & VDE-AR-N 4100 validation

---

### Speaker Notes (5:00)

> *[0:00-0:45]* This is the heart of Branitz2—our five-layer architecture. Let me walk through each layer and its innovation.

> *[0:45-1:30]* **Layer 1: The KPI Contract.** This is our foundational innovation. Instead of ad-hoc data passing between agents, we enforce a canonical JSON schema that every agent must read and write. Think of it as a "single source of truth"—if it's not in the KPI Contract, it doesn't exist. This prevents the classic "garbage in, garbage out" problem of multi-agent systems.

> *[1:30-2:15]* **Layer 2: True Multi-Physics Simulation.** Here's where we break new ground. The CHA Agent—our Central Heating Agent—runs pandapipes for hydraulic-thermal district heating analysis. The DHA Agent—District Heating Agent—handles the electrical side with pandapower. But critically, they're coupled through the KPI Contract. When a heat pump's electrical load changes, the LV grid sees it. When voltage constraints bind, the heat network adapts. This is the **first** such coupling in the open-source energy modeling space.

> *[2:15-3:00]* **Layer 3: Uncertainty-Aware Economics.** Our LCOH Agent doesn't use single-point estimates. We run N=500 Monte Carlo samples across price scenarios, efficiency curves, and demand profiles. This gives us not just an expected cost—but a full distribution. We can answer: "What's the probability this design stays under budget?"

> *[3:00-3:45]* **Layer 4: Robust Decision Making.** Here's where uncertainty becomes actionable. We use "win fractions"—the probability that Design A outperforms Design B across scenarios. These win fractions feed into a robustness classification: "dominant," "trade-off," or "dominated." No more pretending we know the future—we quantify our uncertainty and decide accordingly.

> *[3:45-4:30]* **Layer 5: Safe Explanation.** Our LogicAuditor Agent uses Google's Gemini—but with critical constraints. It's read-only; it cannot issue control commands. And every explanation passes through TNLI—Tabular Natural Language Inference. We validate that what the LLM says actually matches the data in the KPI Contract. This is our safety innovation: explainability with verifiability.

> *[4:30-5:00]* Together, these five layers form a complete pipeline—from raw data to validated explanation. Every step is auditable, every decision is uncertainty-aware, and every output is standards-compliant.

---

## SLIDE 4: Zero-to-Hero Pipeline (5 minutes)

### Visual Description
- Horizontal flowchart with six stages
- Each stage has: icon, agent name, input/output visualization
- Animated-style arrows showing data flow
- Small "KPI Contract" badge at each stage indicating schema validation
- Bottom strip showing standards compliance checkpoints

### Slide Content

**Title:** The Zero-to-Hero Pipeline: From Raw Data to Validated Decision

```
RAW DATA    →   PROFILES    →   SIMULATION   →   ECONOMICS   →   DECISION   →   EXPLANATION
    │              │               │               │              │              │
    ▼              ▼               ▼               ▼              ▼              ▼
┌────────┐    ┌────────┐      ┌────────┐      ┌────────┐    ┌────────┐    ┌────────┐
│ CSV    │    │ Profile│      │ CHA    │      │ LCOH   │    │Arbiter │    │ Logic  │
│ GIS    │───▶│ Agent  │─────▶│ Agent  │─────▶│ Agent  │───▶│ Agent  │───▶│Auditor │
│ Weather│    │        │      │ DHA    │      │        │    │        │    │        │
└────────┘    └────────┘      │ Agent  │      └────────┘    └────────┘    └────────┘
                              └────────┘
```

**Pipeline Stages:**

| Stage | Agent | Input | Output | Standards Check |
|-------|-------|-------|--------|-----------------|
| **1. Data Ingestion** | Profile Agent | CSV, GIS, Weather | Validated profiles | Schema check |
| **2. Simulation** | CHA + DHA | Profiles + Network | Hydraulic + Electrical results | EN 13941-1, VDE-AR-N 4100 |
| **3. Economics** | LCOH Agent | Simulation results | Cost distributions (N=500) | — |
| **4. Decision** | Arbiter Agent | Cost distributions | Win fractions + Ranking | — |
| **5. Explanation** | LogicAuditor | Decision + Data | Validated natural language | TNLI verification |

**Key Pipeline Features:**
- 🔄 Bidirectional feedback: DHA can trigger CHA re-simulation
- 📋 KPI Contract enforces schema at every handoff
- ⚡ Parallel execution: CHA and DHA run simultaneously where possible
- 🛡️ Immutable audit trail: Every agent decision logged

---

### Speaker Notes (5:00)

> *[0:00-0:45]* Now let me show you how data actually flows through Branitz2—from raw input to validated explanation. I call this the "Zero-to-Hero" pipeline because it transforms messy real-world data into actionable, auditable decisions.

> *[0:45-1:30]* **Stage 1: Data Ingestion.** The Profile Agent takes raw CSV files, GIS shapefiles, and weather data. But it doesn't just pass them through—it validates everything against our KPI Contract schema. Missing a required field? Pipeline stops. Wrong unit? Conversion or error. This is our first line of defense against garbage data.

> *[1:30-2:15]* **Stage 2: Simulation.** Here's where the magic happens. The CHA Agent runs pandapipes for district heating—pipe flows, temperatures, pressure drops. Simultaneously, the DHA Agent runs pandapower for the LV grid—voltages, currents, power flows. They're coupled through the KPI Contract: when CHA calculates a heat pump's electrical demand, DHA sees it immediately. This is true multi-physics—not sequential, but integrated.

> *[2:15-2:45]* And both agents enforce standards automatically. EN 13941-1 for DH networks? Checked. VDE-AR-N 4100 for LV grids? Validated. No manual spreadsheet checking required.

> *[2:45-3:30]* **Stage 3: Economics.** The LCOH Agent takes simulation results and runs Monte Carlo analysis. For each of N=500 samples, it draws from price distributions, efficiency curves, demand profiles. The output isn't a single number—it's a full probability distribution. We know not just the expected cost, but the variance, the tail risks, the confidence intervals.

> *[3:30-4:15]* **Stage 4: Decision.** The Arbiter Agent compares designs using win fractions. Design A vs Design B: what's the probability A has lower LCOH? If it's 95%, we call A "dominant." If it's 60%, we flag a "trade-off" for human review. This is uncertainty-aware decision making—we don't hide the ambiguity; we quantify it.

> *[4:15-5:00]* **Stage 5: Explanation.** Finally, the LogicAuditor generates natural language explanations. "Design A is preferred because..." But here's the critical part: every claim is validated via TNLI against the KPI Contract data. If the LLM hallucinates, TNLI catches it. This gives us explainability with verifiability—essential for regulatory approval and planner trust.

---

## SLIDE 5: CHA Agent Highlight (3 minutes)

### Visual Description
- Split screen: left side shows trunk-spur topology diagram, right side shows code snippet or pseudocode
- Topology diagram with color-coded pipes (red = supply, blue = return)
- Small inset showing 25% design margin calculation
- Badge: "EN 13941-1 Compliant"

### Slide Content

**Title:** CHA Agent: Central Heating with Context-Aware Validation

**Core Function:** Hydraulic-thermal simulation of district heating networks using pandapipes

**Key Innovation: Trunk-Spur Topology**

```
        [Heat Source]
             │
        ═════╧═════  ← TRUNK (main supply/return)
        ║         ║
     ┌──┴──┐   ┌──┴──┐
     │SPUR │   │SPUR │  ← SPURS (building connections)
     │  1  │   │  2  │
     └──┬──┘   └──┬──┘
     [Bldg A]  [Bldg B]
```

**Context-Aware Validation:**
- Validates pipe diameters against EN 13941-1 velocity constraints
- Checks pressure losses against available pump head
- **25% Design Margin**: All capacities sized for 125% of peak demand
- Temperature cascading: Supply/return temps validated per building type

**Standards Compliance:**
- ✅ EN 13941-1: Temperature, velocity, pressure drop limits
- ✅ VDI 2077: Heat demand calculation methods
- ✅ DIN 18599: Building energy reference

---

### Speaker Notes (3:00)

> *[0:00-0:45]* Let me zoom into one of our key agents: the CHA Agent, or Central Heating Agent. This handles the district heating side of our multi-physics simulation.

> *[0:45-1:30]* The CHA Agent uses a **trunk-spur topology**—a proven design pattern for urban district heating. The trunk is the main supply and return line, sized for the aggregate flow. Spurs branch off to individual buildings. This isn't just a modeling choice; it's how real DH networks are built, which makes our simulations more transferable to practice.

> *[1:30-2:15]* But here's the innovation: **context-aware validation**. The CHA Agent doesn't just simulate—it validates against standards in real-time. When a pipe diameter is proposed, it checks EN 13941-1 velocity constraints. Too fast? Rejection. Pressure loss exceeding pump capacity? Flagged. And we apply a **25% design margin**—all capacities sized for 125% of calculated peak demand. This accounts for future growth, estimation errors, and extreme weather events.

> *[2:15-3:00]* The temperature cascading is also validated. Different building types have different supply temperature requirements. A hospital needs higher temps than a residential building. The CHA Agent tracks this and validates that the network can deliver the required temperatures at each spur point. Every check is logged—full audit trail for regulatory review.

---

## SLIDE 6: DHA Agent Highlight (3 minutes)

### Visual Description
- Electrical single-line diagram showing MV/LV boundary
- Highlighted: ext_grid at MV level, transformer, LV network with heat pumps
- Small inset showing "Option 2" vs "Option 1" comparison
- Voltage profile graph showing acceptable range

### Slide Content

**Title:** DHA Agent: Electrical Grid Integration at the MV/LV Boundary

**Core Function:** Low-voltage electrical grid analysis using pandapower

**The MV/LV Challenge:**
- Urban heat planning focuses on the LV level (400V)
- But heat pumps, EVs, and PV create bidirectional power flows
- Traditional approach: Model LV in isolation → misses upstream constraints

**Our Solution: "Option 2" Modeling**

```
[Transmission Grid] ──▶ [MV Grid] ──▶ [Transformer] ──▶ [LV Grid]
                              ▲                              │
                              │                              │
                         [ext_grid]                    [Heat Pumps]
                                                         [PV Systems]
                                                         [EV Charging]
```

**Key Features:**
- **ext_grid at MV level**: Models realistic upstream impedance
- **Transformer modeling**: Includes tap changer, losses, impedance
- **Bidirectional power flow**: PV export, heat pump demand simultaneously
- **Voltage constraints**: VDE-AR-N 4100 compliance (±10% of nominal)

**Coupling with CHA:**
- CHA calculates heat pump electrical demand → passes to DHA
- DHA checks voltage constraints → signals CHA if violations occur
- Bidirectional feedback loop for integrated optimization

---

### Speaker Notes (3:00)

> *[0:00-0:45]* Now the DHA Agent—our District Heating Agent for the electrical side. This is where Branitz2 really differentiates itself.

> *[0:45-1:30]* The challenge is the **MV/LV boundary**. Urban heat planning naturally focuses on the low-voltage level—400V distribution to buildings. But heat pumps, electric vehicles, and rooftop PV create bidirectional power flows that affect the medium-voltage grid upstream. Model LV in isolation, and you miss critical constraints.

> *[1:30-2:15]* Our solution is what we call **"Option 2" modeling**—we place the external grid reference point at the MV level, not the LV level. This means we model the realistic upstream impedance: the MV grid, the transformer with its tap changer and losses, and then the LV distribution. When a heat pump starts up, we see the voltage dip propagate through the entire chain. This is how real grids behave.

> *[2:15-3:00]* And here's the coupling magic: the DHA Agent doesn't work in isolation. When CHA calculates a heat pump's electrical demand, it passes to DHA. DHA runs the power flow and checks VDE-AR-N 4100 voltage constraints. Violation? It signals back to CHA, which can then explore alternatives—maybe a different heat pump sizing, or network reinforcement. This bidirectional feedback is what makes Branitz2 truly multi-physics, not just multi-tool.

---

## SLIDE 7: The Safety Innovation - LogicAuditor (4 minutes)

### Visual Description
- Three-panel layout showing the TNLI workflow
- Left: LLM generating explanation
- Center: TNLI validation with entailment/contradiction/neutral
- Right: Pass/Fail decision with confidence scores
- Bottom: Example of caught hallucination

### Slide Content

**Title:** LogicAuditor: Safe LLM Explanations via Tabular NLI

**The Problem:**
- LLMs hallucinate—generate plausible but false statements
- In critical infrastructure planning, this is unacceptable
- Need: Explainability + Verifiability

**Our Solution: TNLI (Tabular Natural Language Inference)**

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  LLM Generates  │     │  TNLI Validates │     │  Output Decision│
│   Explanation   │────▶│ Against KPI Data│────▶│  Pass / Fail    │
│                 │     │                 │     │  (with score)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        ▼                       ▼
   "Design A has          Entailment: 0.92
    lower LCOH            Contradiction: 0.05
    than Design B"        Neutral: 0.03
```

**TNLI Three-Way Classification:**
| Label | Meaning | Action |
|-------|---------|--------|
| **Entailment** | Statement supported by data | ✅ Pass |
| **Contradiction** | Statement conflicts with data | ❌ Reject + Regenerate |
| **Neutral** | Statement not verifiable from data | ⚠️ Flag for review |

**Safety Constraints:**
- 🔒 **Read-only**: LLM cannot issue control commands
- 📋 **Schema-bound**: Only references KPI Contract fields
- 🎯 **Temperature=0**: Deterministic output, no creativity
- 📝 **Audit log**: Every explanation stored with TNLI scores

---

### Speaker Notes (4:00)

> *[0:00-0:45]* Now I want to highlight what I consider our most important innovation from a safety perspective: the LogicAuditor and its TNLI validation mechanism.

> *[0:45-1:30]* Here's the problem: Large language models are powerful explainers, but they **hallucinate**. They generate confident, plausible-sounding statements that are factually wrong. In most applications, this is annoying. In critical infrastructure planning, it's dangerous. If an LLM claims "Design A meets all voltage constraints" when it doesn't, and a planner acts on that, we have a problem.

> *[1:30-2:15]* Our solution is **TNLI—Tabular Natural Language Inference**. Here's how it works. The LLM generates an explanation: "Design A has lower LCOH than Design B because of higher heat pump efficiency." That statement is then passed to a TNLI model, which classifies the relationship between the statement and the actual data in the KPI Contract. Is the statement entailed by the data? Does it contradict the data? Or is it neutral—neither confirmed nor denied?

> *[2:15-3:00]* The TNLI outputs three probabilities: entailment, contradiction, and neutral. If entailment is high—say above 0.85—the explanation passes. If contradiction is high, we reject and regenerate. If neutral is high, we flag for human review. This gives us a verifiable explanation pipeline.

> *[3:00-3:45]* But we don't stop there. The LLM is **read-only**—it can query the KPI Contract, but it cannot issue control commands. No "set pump speed to X" or "close valve Y." It's strictly an explainer, not an actor. We also set temperature to zero for deterministic outputs—no creativity, no variation. And every explanation is logged with its TNLI scores, creating an immutable audit trail.

> *[3:45-4:00]* This is what I mean by "safe AI for critical infrastructure." We're not avoiding LLMs—they're too useful for explanation. But we're constraining them, validating them, and logging everything. Explainability with verifiability.

---

## SLIDE 8: Validation Strategy (3 minutes)

### Visual Description
- Five-layer pyramid showing validation hierarchy
- Each layer labeled with validation type and methods
- Color gradient from green (bottom) to gold (top)
- Small icons representing each validation approach

### Slide Content

**Title:** Five-Layer Validation: From Physics to Empirical Reality

```
                    ╱╲
                   ╱  ╲
                  ╱ 5  ╲    EMPIRICAL
                 ╱────────╲   Real-world case study
                ╱    4     ╲  SEMANTIC
               ╱────────────╲ Expert review, TNLI scores
              ╱      3       ╲ LOGICAL
             ╱────────────────╲ Standards compliance, constraint checks
            ╱        2         ╲ ECONOMIC
           ╱────────────────────╲ LCOH benchmarking, sensitivity analysis
          ╱          1           ╲ PHYSICS
         ╱────────────────────────╲ pandapipes/pandapower validation
```

**Validation Layers:**

| Layer | Type | Methods | Status |
|-------|------|---------|--------|
| **1** | Physics | pandapipes validation against analytical solutions; pandapower IEEE test cases | ✅ Complete |
| **2** | Economic | LCOH benchmarking against VDI 2067; sensitivity analysis | ✅ Complete |
| **3** | Logical | EN 13941-1 constraint verification; VDE-AR-N 4100 compliance | ✅ Complete |
| **4** | Semantic | Expert review of explanations; TNLI score distributions | ✅ Complete |
| **5** | Empirical | Real-world case study: Cottbus urban quarter | 🔄 In Progress |

**Validation Metrics:**
- Physics: <1% deviation from reference solutions
- Economic: Within 5% of VDI 2067 benchmark
- Logical: 100% standards compliance rate
- Semantic: >90% expert approval rate

---

### Speaker Notes (3:00)

> *[0:00-0:45]* A critical question for any thesis: how do you validate that your system actually works? We've implemented a five-layer validation strategy, from foundational physics to real-world empirical testing.

> *[0:45-1:15]* **Layer 1: Physics Validation.** We validate our simulation engines against known solutions. Pandapipes is checked against analytical solutions for simple pipe networks. Pandapower is validated against IEEE test cases. Our target: less than 1% deviation from reference solutions. This ensures our multi-physics coupling is built on solid foundations.

> *[1:15-1:45]* **Layer 2: Economic Validation.** The LCOH Agent is benchmarked against VDI 2067, the German standard for economic analysis of building systems. We also run extensive sensitivity analysis—how much do results change when inputs vary? This gives us confidence in our uncertainty quantification.

> *[1:45-2:15]* **Layer 3: Logical Validation.** Every constraint check is verified. EN 13941-1 temperature limits? We test with values above, at, and below limits. VDE-AR-N 4100 voltage constraints? Same approach. We achieve 100% standards compliance rate in our test suite—every rule is correctly implemented.

> *[2:15-2:45]* **Layer 4: Semantic Validation.** This is where experts review LLM explanations. Do they make sense? Are they useful? We also track TNLI score distributions—are we seeing high entailment rates? Our target is >90% expert approval, and we're achieving that.

> *[2:45-3:00]* **Layer 5: Empirical Validation.** The ultimate test: does it work on a real urban quarter? We're conducting a case study in Cottbus, working with actual network data, real building stock, and measured consumption profiles. This is currently in progress and will form a key part of the thesis conclusion.

---

## SLIDE 9: Roadmap & Status (2 minutes)

### Visual Description
- Timeline showing project phases
- Completed phases in green, current in yellow, future in gray
- Small status indicators for each phase
- Bottom: Key deliverables and timeline

### Slide Content

**Title:** Project Roadmap: From Concept to Completion

```
2023 Q1-Q2    2023 Q3-Q4    2024 Q1-Q2    2024 Q3-Q4    2025 Q1-Q2
    │             │             │             │             │
    ▼             ▼             ▼             ▼             ▼
┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
│PHASE 1 │   │PHASE 2 │   │PHASE 3 │   │PHASE 4 │   │PHASE 5 │
│Research│   │ Design │   │  Impl  │   │  Test  │   │ Thesis │
│  & Lit │   │ & Arch │   │        │   │ & Val  │   │ Writing│
└────────┘   └────────┘   └────────┘   └────────┘   └────────┘
   [DONE]      [DONE]       [DONE]       [DONE]      [IN PROG]
     🟢          🟢            🟢            🟢           🟡
```

**Phase Summary:**

| Phase | Description | Status |
|-------|-------------|--------|
| **1. Research** | Literature review, tool selection, standards analysis | ✅ DONE |
| **2. Design** | Architecture design, KPI Contract specification | ✅ DONE |
| **3. Implementation** | Agent development, multi-physics coupling | ✅ DONE |
| **4. Testing** | Unit tests, integration tests, validation | ✅ DONE |
| **5. Thesis** | Documentation, case study, submission | 🔄 IN PROGRESS |

**Key Deliverables:**
- ✅ Working Branitz2 framework (GitHub repository)
- ✅ Full test suite with 95%+ coverage
- ✅ Validation report (5-layer approach)
- 🔄 Empirical case study (Cottbus quarter)
- 🔄 Doctoral thesis (submission target: Q2 2025)

**Next Steps:**
1. Complete Cottbus case study (by Feb 2025)
2. Finalize thesis chapters (by Mar 2025)
3. Committee review and defense (by May 2025)

---

### Speaker Notes (2:00)

> *[0:00-0:45]* Let me conclude with our project status and roadmap. Branitz2 has been developed over approximately 18 months, following a structured five-phase approach.

> *[0:45-1:15]* Phases 1 through 4 are **complete**. We've done the research, designed the architecture, implemented all agents, and validated the system. The framework is fully functional, with a comprehensive test suite and validation report. You can see the code on our GitHub repository.

> *[1:15-1:45]* We're now in **Phase 5: Thesis Writing**. This includes completing the empirical case study in Cottbus and documenting everything in the doctoral thesis. My target is submission by Q2 2025, with committee review and defense shortly after.

> *[1:45-2:00]* I'm confident in the technical contributions: true multi-physics coupling, the KPI Contract schema, TNLI safety validation, and uncertainty-aware decision making. These represent genuine advances in the field of urban energy planning. I look forward to your questions and feedback.

---

## APPENDIX: Key Literature Citations

### Standards & Guidelines
- **EN 13941-1:2021** - Design and installation of district heating networks
- **VDE-AR-N 4100:2023** - Technical requirements for connection of customer installations to the low-voltage distribution network
- **VDI 2067:2012** - Economic efficiency of building installations
- **VDI 2077:2015** - Calculation of heat demand

### Software & Tools
- **pandapipes**: Lohmeier et al. (2020) - Open-source pipe flow simulation
- **pandapower**: Thurner et al. (2018) - Open-source power system modeling
- **Gemini**: Google DeepMind (2023) - Large language model family

### Methods & Theory
- **Monte Carlo in Energy**: Dubey et al. (2022) - Uncertainty quantification in building energy
- **TNLI/NLI**: Williams et al. (2018) - Broad-coverage natural language inference
- **Multi-Agent Systems**: Wooldridge (2009) - Introduction to multi-agent systems
- **Explainable AI**: Gunning et al. (2019) - DARPA's XAI program

### Domain Context
- **GEG 2024**: German Building Energy Act - Climate-neutral heating mandate
- **EU Green Deal**: 2050 climate neutrality target
- **Heat Planning**: German National Heat Strategy (2023)

---

## TIMING SUMMARY

| Slide | Title | Duration | Cumulative |
|-------|-------|----------|------------|
| 1 | Title & Hook | 2:00 | 2:00 |
| 2 | The Problem Gap | 3:00 | 5:00 |
| 3 | The Innovation Architecture | 5:00 | 10:00 |
| 4 | Zero-to-Hero Pipeline | 5:00 | 15:00 |
| 5 | CHA Agent Highlight | 3:00 | 18:00 |
| 6 | DHA Agent Highlight | 3:00 | 21:00 |
| 7 | The Safety Innovation | 4:00 | 25:00 |
| 8 | Validation Strategy | 3:00 | 28:00 |
| 9 | Roadmap & Status | 2:00 | 30:00 |

**Note:** This script provides 30 minutes of content for a 15-minute slot. Select slides based on audience interest and time constraints. Recommended core: Slides 1-4 (15 minutes).

---

## SPEAKER TIPS

### For Technical Audiences
- Emphasize the multi-physics coupling (pandapipes + pandapower)
- Discuss Monte Carlo implementation details
- Explain TNLI architecture and training data

### For Policy/Standards Audiences
- Lead with standards compliance (EN 13941-1, VDE-AR-N 4100)
- Emphasize auditability and explainability
- Connect to GEG 2024 and climate neutrality targets

### For Industry/Practitioner Audiences
- Focus on the zero-to-hero pipeline
- Highlight time savings from automated compliance
- Show real-world applicability (Cottbus case study)

### Q&A Preparation
**Expected Questions:**
1. "How does TNLI handle ambiguous statements?" → Neutral classification + human review
2. "What's the computational cost of N=500 Monte Carlo?" → Parallelizable, ~10x single-run cost
3. "Can this scale to city-wide networks?" → Modular design, agents can be distributed
4. "How do you handle model uncertainty (not just parameter uncertainty)?" → Future work, structural sensitivity analysis

---

*Document generated for Branitz2 Thesis Committee Meeting #1*  
*Version: 1.0 | Date: 2024*  
*Author: Ishantha Hewaratne, Fraunhofer IEG*
