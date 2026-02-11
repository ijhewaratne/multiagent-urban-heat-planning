# Phase 1: Intent-Aware Architecture – Implementation Plan

**Goal**: Replace keyword-based routing with a semantic intent classification layer that sits before existing tools and decides **which simulations to run** based on user intent.

---

## Architecture Overview

```
User Query → Intent Classifier (NLU) → Intent + Entities
                    ↓
            Intent → Tool Plan Mapping
                    ↓
            Plan: [cha, dha, economics, decision, uhdc]
                    ↓
            LLMRouter / JobService (existing)
```

---

## Step 1: Create the Intent Classification Layer

### 1.1 Directory Structure

```
src/branitz_heat_decision/
├── nlu/
│   __init__.py
│   intent_classifier.py   # NEW: IntentClassifier + BranitzIntent
│   intent_mapper.py       # NEW: Intent → Tool plan
```

### 1.2 Intent Enum (Semantic Categories)

| Intent | Triggers | Description |
|--------|----------|-------------|
| `CO2_COMPARISON` | cha, dha, economics | User wants carbon emissions comparison |
| `LCOH_COMPARISON` | cha, dha, economics | User wants cost analysis |
| `VIOLATION_ANALYSIS` | cha | User asks about pressure/velocity/temperature violations |
| `NETWORK_DESIGN` | cha | User asks about pipe layout, DN, topology |
| `WHAT_IF_SCENARIO` | cha (or full chain) | Hypothetical: "what if we remove houses", "different temps" |
| `EXPLAIN_DECISION` | decision or uhdc | User wants KPI explanation, why a decision was made |
| `CAPABILITY_QUERY` | (none) | Meta: "what can you do?" |
| `UNKNOWN` | (none) | Outside capabilities; no simulation |

### 1.3 Implementation Options

**Option A: Use `google-genai` (existing dependency)**  
- No new packages; same SDK as UHDC explainer  
- Use `genai.Client` + `generate_content` for classification  
- Recommended for quickest integration  

**Option B: Use `google-adk`**  
- Add `pip install google-adk`  
- Use `LlmAgent` for structured agent-based classification  
- Better long-term if you plan to expand to multi-agent workflows  

---

## Step 2: Dynamic Orchestrator (Phase 1 Step 2)

### Purpose
Replace the linear pipeline with a state-aware router that:
1. Classifies intent (via Step 1)
2. Checks file-based cache (`results/{cha,dha,economics,decision}/{cluster_id}/`)
3. Runs only missing simulations in dependency order
4. Returns structured response with `answer`, `data`, `execution_plan`, `sources`
5. For UNKNOWN/CAPABILITY: Fallback agent explains limitations (Speaker B requirement)

### Implementation
- **Location**: `src/branitz_heat_decision/agents/orchestrator.py`
- **No google-adk**: Uses existing `adk/tools` (run_cha_tool, run_dha_tool, etc.) and `google-genai` for fallback
- **Cache**: File existence in `results/`; no in-memory cache (per-request stateless)
- **Handlers**: `_handle_co2_request`, `_handle_lcoh_request`, `_handle_violation_request`, `_handle_explain_request`, `_handle_fallback`

### Intent → Required Simulations
| Intent | Required (ordered) |
|--------|--------------------|
| CO2_COMPARISON, LCOH_COMPARISON | cha, dha, economics |
| VIOLATION_ANALYSIS, NETWORK_DESIGN, WHAT_IF_SCENARIO | cha |
| EXPLAIN_DECISION | cha, dha, economics, decision |
| UNKNOWN, CAPABILITY_QUERY | (none) |

---

## Step 3: Files to Create (NLU)

### File 1: `src/branitz_heat_decision/nlu/__init__.py`

```python
"""NLU (Natural Language Understanding) module for intent-aware routing."""
from .intent_classifier import BranitzIntent, IntentClassifier, classify_intent
from .intent_mapper import intent_to_plan
```

### File 2: `src/branitz_heat_decision/nlu/intent_classifier.py`

**Variant A – google-genai (recommended, no new deps):**

```python
# src/branitz_heat_decision/nlu/intent_classifier.py

from enum import Enum
from typing import Dict, Any, Optional, List
import json
import logging
import re

logger = logging.getLogger(__name__)

# Optional: use existing genai from explainer or ui
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    try:
        import google.generativeai as genai
        GENAI_AVAILABLE = True
    except ImportError:
        GENAI_AVAILABLE = False


class BranitzIntent(Enum):
    """Explicit intents that map to simulation strategies."""
    CO2_COMPARISON = "co2_comparison"
    LCOH_COMPARISON = "lcoh_comparison"
    VIOLATION_ANALYSIS = "violation_analysis"
    NETWORK_DESIGN = "network_design"
    WHAT_IF_SCENARIO = "what_if_scenario"
    EXPLAIN_DECISION = "explain_decision"
    CAPABILITY_QUERY = "capability_query"
    UNKNOWN = "unknown"


CLASSIFIER_SYSTEM_PROMPT = """
You are an intent classifier for a District Heating vs Heat Pump decision system (Branitz).
Analyze the user query and determine their intent.

Available intents (return ONLY one):
- CO2_COMPARISON: User wants carbon emissions comparison (needs DH + HP simulations)
- LCOH_COMPARISON: User wants cost/LCOH analysis (needs DH + HP simulations)
- VIOLATION_ANALYSIS: User asks about pressure/velocity/temperature violations (needs DH sim only)
- NETWORK_DESIGN: User asks about pipe layout, diameters, network topology (needs DH sim only)
- WHAT_IF_SCENARIO: User asks hypotheticals: "what if we remove houses", "different temperatures"
- EXPLAIN_DECISION: User asks why a decision was made or wants KPI explanation (needs cached results only)
- CAPABILITY_QUERY: User asks "what can you do?", "help", capabilities
- UNKNOWN: Outside capabilities (adding consumers, changing building geometry, legal advice, etc.)

Return STRICTLY this JSON (no other text):
{"intent": "ONE_OF_ABOVE", "confidence": 0.0_to_1.0, "entities": {"street_name": null_or_extracted, "metric": "co2|lcoh|pressure|velocity|etc", "modification": "what-if desc or null"}, "reasoning": "brief why"}

Examples:
"Compare CO2" -> {"intent": "CO2_COMPARISON", "confidence": 0.95, "entities": {"metric": "co2"}, "reasoning": "..."}
"What if we remove 2 houses?" -> {"intent": "WHAT_IF_SCENARIO", "entities": {"modification": "remove 2 houses"}, ...}
"Add a new consumer" -> {"intent": "UNKNOWN", "confidence": 0.9, "reasoning": "Cannot modify network topology"}
"""


def _call_genai_classify(user_query: str, conversation_history: Optional[List[str]] = None) -> str:
    """Call Gemini via google-genai. Returns raw model text."""
    import os
    key = os.getenv("GOOGLE_API_KEY")
    if not key or not key.strip():
        raise RuntimeError("GOOGLE_API_KEY not set")

    # Try new genai SDK first (from uhdc/explainer)
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=500)
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"User query: {user_query}",
            config=cfg,
        )
        return resp.text if hasattr(resp, "text") else str(resp)
    except ImportError:
        pass

    # Fallback: google.generativeai (ui/llm style)
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"{CLASSIFIER_SYSTEM_PROMPT}\n\nUser: {user_query}")
    return response.text


def _parse_json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON from model output (handles markdown code blocks)."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    text = text.strip()
    return json.loads(text)


def classify_intent(
    user_query: str,
    conversation_history: Optional[List[str]] = None,
    use_llm: bool = True,
    confidence_threshold: float = 0.7,
) -> Dict[str, Any]:
    """
    Classify user query into BranitzIntent.
    
    Returns:
        {
            "intent": "CO2_COMPARISON" | ...,
            "confidence": 0.0-1.0,
            "entities": {"street_name": ..., "metric": ..., "modification": ...},
            "reasoning": "..."
        }
    """
    if not user_query or not str(user_query).strip():
        return {"intent": "UNKNOWN", "confidence": 0.0, "entities": {}, "reasoning": "Empty query"}

    if use_llm and GENAI_AVAILABLE:
        try:
            text = _call_genai_classify(user_query, conversation_history)
            result = _parse_json_from_text(text)
            intent_raw = str(result.get("intent", "UNKNOWN")).upper().replace(" ", "_")
            result["intent"] = intent_raw if intent_raw in [e.value for e in BranitzIntent] else "UNKNOWN"
            if result.get("confidence", 0) < confidence_threshold:
                result["intent"] = "UNKNOWN"
                result["reasoning"] = (result.get("reasoning", "") or "") + " [Low confidence]"
            return result
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")
            return {"intent": "UNKNOWN", "confidence": 0.0, "entities": {}, "reasoning": str(e)}

    # Non-LLM fallback: simple keyword heuristics
    q = user_query.lower()
    if any(w in q for w in ["co2", "carbon", "emission", "emissions"]):
        return {"intent": "CO2_COMPARISON", "confidence": 0.6, "entities": {"metric": "co2"}, "reasoning": "Keyword fallback"}
    if any(w in q for w in ["cost", "lcoh", "price", "money", "expensive"]):
        return {"intent": "LCOH_COMPARISON", "confidence": 0.6, "entities": {"metric": "lcoh"}, "reasoning": "Keyword fallback"}
    if any(w in q for w in ["violation", "pressure", "velocity", "limit"]):
        return {"intent": "VIOLATION_ANALYSIS", "confidence": 0.6, "entities": {}, "reasoning": "Keyword fallback"}
    if any(w in q for w in ["network", "pipe", "layout", "topology", "diameter"]):
        return {"intent": "NETWORK_DESIGN", "confidence": 0.6, "entities": {}, "reasoning": "Keyword fallback"}
    if any(w in q for w in ["what if", "what if we", "hypothetical"]):
        return {"intent": "WHAT_IF_SCENARIO", "confidence": 0.6, "entities": {"modification": user_query[:80]}, "reasoning": "Keyword fallback"}
    if any(w in q for w in ["explain", "why", "decision", "recommend"]):
        return {"intent": "EXPLAIN_DECISION", "confidence": 0.6, "entities": {}, "reasoning": "Keyword fallback"}
    if any(w in q for w in ["help", "what can you", "capabilities"]):
        return {"intent": "CAPABILITY_QUERY", "confidence": 0.8, "entities": {}, "reasoning": "Keyword fallback"}

    return {"intent": "UNKNOWN", "confidence": 0.0, "entities": {}, "reasoning": "No match"}
```

### File 3: `src/branitz_heat_decision/nlu/intent_mapper.py`

```python
# src/branitz_heat_decision/nlu/intent_mapper.py

from typing import Dict, Any, List
from .intent_classifier import BranitzIntent


# Intent → Tool plan (registry keys: cha, dha, economics, decision, uhdc)
INTENT_TO_PLAN: Dict[str, List[str]] = {
    "CO2_COMPARISON": ["cha", "dha", "economics"],
    "LCOH_COMPARISON": ["cha", "dha", "economics"],
    "VIOLATION_ANALYSIS": ["cha"],
    "NETWORK_DESIGN": ["cha"],
    "WHAT_IF_SCENARIO": ["cha"],  # May extend to [cha, dha, economics] when what-if engine exists
    "EXPLAIN_DECISION": ["decision"],  # Or ["uhdc"] if report needed; decision reads cached
    "CAPABILITY_QUERY": [],
    "UNKNOWN": [],
}


def intent_to_plan(intent_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert classifier output to tool plan compatible with LLMRouter.
    
    Returns:
        [{"tool": "cha", "reason": "..."}, {"tool": "dha", "reason": "..."}, ...]
    """
    intent = str(intent_result.get("intent", "UNKNOWN")).upper().replace(" ", "_")
    reasoning = intent_result.get("reasoning", "")
    
    tool_ids = INTENT_TO_PLAN.get(intent, INTENT_TO_PLAN["UNKNOWN"])
    
    plan = []
    for t in tool_ids:
        plan.append({"tool": t, "reason": reasoning or f"Intent {intent} requires {t}"})
    
    return plan
```

---

## Step 3: Integration with LLMRouter

**Modify `src/branitz_heat_decision/ui/llm.py`:**

1. Add optional intent-first path:
   - If `UHDC_USE_INTENT_CLASSIFIER=true` (env): call `classify_intent()` → `intent_to_plan()` before falling back to `_query_llm`.
2. Keep existing `_query_llm` as fallback when intent classifier returns `UNKNOWN` or empty plan.
3. Preserve keyword fallback when LLM/key unavailable.

**Pseudocode for `route_intent()`:**

```python
def route_intent(self, prompt: str, cluster_id: str) -> Dict[str, Any]:
    if not cluster_id:
        return {"plan": [], "message": "Please select a street cluster first."}

    # NEW: Intent-first path (optional)
    if os.getenv("UHDC_USE_INTENT_CLASSIFIER", "false").lower() == "true":
        from branitz_heat_decision.nlu import classify_intent, intent_to_plan
        result = classify_intent(prompt, use_llm=True)
        plan = intent_to_plan(result)
        if plan or result["intent"] == "CAPABILITY_QUERY":
            msg = _capability_message() if result["intent"] == "CAPABILITY_QUERY" else \
                  f"Intent: {result['intent']}. Shall we run these simulations?"
            return {"plan": plan, "message": msg, "intent": result}
        # Else fall through to existing LLM/keyword logic
```

---

## Step 4: Google ADK Variant (Optional)

If you prefer `google-adk`:

1. Add to `requirements.txt`: `google-adk>=0.1.0`
2. Create `intent_classifier_adk.py`:

```python
# Intent classifier using Google ADK (optional)

from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.genai import types

class IntentClassifierADK:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.agent = LlmAgent(
            name="intent_classifier",
            model=model_name,
            instruction=CLASSIFIER_SYSTEM_PROMPT,
        )
        self.session_service = InMemorySessionService()

    def classify(self, user_query: str, conversation_history: list = None) -> dict:
        session = self.session_service.create_session(user_id="intent_cls")
        response = self.agent.run(
            user_content=user_query,
            session=session,
        )
        # ADK returns Message; extract text and parse JSON
        text = response.messages[-1].content.parts[0].text if response.messages else ""
        return _parse_and_validate(text)
```

Note: Google ADK API may differ by version; adjust `run()` and response structure per [ADK docs](https://google.github.io/adk-docs/).

---

## Step 5: Wiring Summary

| Component | Change |
|----------|--------|
| **New** | `nlu/intent_classifier.py` – classify_intent(), BranitzIntent |
| **New** | `nlu/intent_mapper.py` – intent_to_plan() |
| **Modify** | `ui/llm.py` – add intent-first path behind `UHDC_USE_INTENT_CLASSIFIER` |
| **Modify** | `adk/agent.py` – optionally call classifier before choosing tools (Phase 2) |
| **Unchanged** | `ui/registry.py`, `adk/tools.py`, JobService – no changes for Phase 1 |

---

## Step 6: Testing Checklist

- [ ] `classify_intent("Compare CO2 emissions")` → CO2_COMPARISON, plan = [cha, dha, economics]
- [ ] `classify_intent("What if we remove 2 houses?")` → WHAT_IF_SCENARIO, plan = [cha]
- [ ] `classify_intent("Add a new consumer")` → UNKNOWN, plan = []
- [ ] `classify_intent("Why was DH recommended?")` → EXPLAIN_DECISION, plan = [decision]
- [ ] `classify_intent("")` or no GOOGLE_API_KEY → keyword fallback or UNKNOWN
- [ ] UI: Enable `UHDC_USE_INTENT_CLASSIFIER=true`, chat "compare costs" → plan includes economics

---

## Dependencies

- **Phase 1 (Option A)**: No new deps; uses existing `google-genai` or `google-generativeai`
- **Phase 1 (Option B)**: `pip install google-adk`

---

## Implementation Status

**Completed (Phase 1 Step 1)**:
- `src/branitz_heat_decision/nlu/intent_classifier.py` – `BranitzIntent`, `classify_intent()` (google-genai + keyword fallback)
- `src/branitz_heat_decision/nlu/intent_mapper.py` – `intent_to_plan()`
- `src/branitz_heat_decision/nlu/__init__.py` – module exports
- `ui/llm.py` – intent-first path behind `UHDC_USE_INTENT_CLASSIFIER=true`

**Completed (Phase 1 Step 2)**:
- `src/branitz_heat_decision/agents/orchestrator.py` – `BranitzOrchestrator` with `route_request()`
- File-based cache (checks `results/{cha,dha,economics,decision}/{cluster_id}/`)
- Intent handlers: CO2, LCOH, violation, network, what-if, explain
- Fallback agent: LLM explains limitations (Speaker B "I don't know")
- Dynamic execution plan: runs only missing simulations in dependency order

**Enable intent classifier**: `export UHDC_USE_INTENT_CLASSIFIER=true` before starting the UI.

**Use orchestrator** (sync, blocks until done):
```python
from branitz_heat_decision.agents import BranitzOrchestrator
orch = BranitzOrchestrator()
result = orch.route_request("Compare CO2 emissions", "ST010_HEINRICH_ZILLE_STRASSE")
# result: {type, intent_data, execution_plan, data, answer, sources, can_proceed}
```

**Completed (Phase 1 Step 3 – Streamlit integration)**:
- **Intent Chat tab**: New tab in the main UI (between Compare & Decide and Portfolio)
- **Chat left, viz right**: `st.columns([1, 2])` layout
- **Orchestrator**: Lazy-init via `_get_orchestrator()`, uses `GOOGLE_API_KEY` from env or `st.secrets`
- **Dynamic viz**: CO₂ bar chart, LCOH bar chart, violation metrics + CHA map iframe, decision explanation
- **Fallback handling**: `st.warning` + `st.info` with suggestion (Speaker B requirement)
- **Per-cluster chat history**: `st.session_state[f"intent_chat_messages_{cluster_id}"]`
- **Execution plan expander**: "What I calculated" for transparency

---

## Step 4: Testing the Intent Classifier

**File**: `tests/test_phase1_intent.py`

Run:
```bash
PYTHONPATH=src pytest tests/test_phase1_intent.py -v -k "not integration"
```

Or as script:
```bash
PYTHONPATH=src python tests/test_phase1_intent.py
```

Tests:
- `test_intent_keyword_fallback`: Validates expected intents without LLM
- `test_intent_structure`: Result has intent, confidence, entities, reasoning
- `test_empty_query`: Empty query → UNKNOWN
- `test_intent_with_llm`: Integration test (skipped unless GOOGLE_API_KEY set)

---

## Step 5: Migration Strategy (CLI)

**Don't break existing code** – orchestrator is optional.

Added to `cli/decision.py`:
- `--intent-chat`: Use orchestrator instead of legacy pipeline
- `--query`: Natural language query (required with --intent-chat)

**Usage**:
```bash
# OLD: Legacy pipeline (unchanged)
python -m branitz_heat_decision.cli.decision --cluster-id ST010_HEINRICH_ZILLE_STRASSE

# NEW: Intent-aware orchestrator
python -m branitz_heat_decision.cli.decision --cluster-id ST010_HEINRICH_ZILLE_STRASSE \
  --intent-chat --query "Compare CO2 emissions"
```

When `--intent-chat` and `--query` are set, the CLI calls `BranitzOrchestrator.route_request()` and prints the answer; otherwise the existing pipeline runs as before.
