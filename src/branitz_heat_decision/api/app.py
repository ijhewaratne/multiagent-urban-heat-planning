"""
FastAPI service for the Branitz Heat Decision engine.

Implements the integration paths described in HANDOFF.md:

Deterministic ("Option B"):
    POST /clusters/{cluster_id}/run        — run pipeline phases (cha/dha/economics/decision)
    GET  /clusters/{cluster_id}/decision   — read the decision JSON
    GET  /clusters/{cluster_id}/kpis       — read CHA/DHA/economics KPIs

Agentic ("Option A"):
    POST /query                            — natural-language query via BranitzOrchestrator

Plus:
    GET  /health, GET /clusters, GET /scenarios

Notes:
  - Heavy imports (pandas/geopandas/pandapipes) happen lazily inside the
    pipeline subprocesses, so the API process itself stays light.
  - Simulation runs are synchronous by default; pass {"background": true}
    to POST /clusters/{id}/run to get a job id and poll GET /jobs/{job_id}.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

VALID_PHASES = ("data_prep", "cha", "dha", "economics", "decision", "uhdc")
DEFAULT_PHASES = ["cha", "dha", "economics", "decision"]

app = FastAPI(
    title="Branitz Heat Decision API",
    description="District Heating vs. Heat Pump decision engine (Branitz / Wärmeplanung)",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# In-memory job store (single-process; swap for Redis/DB in production)
# ---------------------------------------------------------------------------
_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    phases: List[str] = Field(
        default_factory=lambda: list(DEFAULT_PHASES),
        description=f"Pipeline phases to run, in order. Valid: {VALID_PHASES}",
    )
    scenario: Optional[str] = Field(
        default=None,
        description="Economic scenario name (e.g. 2030_optimistic) or YAML path. "
        "Applies to economics + decision phases.",
    )
    n_samples: int = Field(default=500, description="Monte Carlo samples for economics")
    background: bool = Field(
        default=False, description="Run asynchronously and return a job id"
    )


class QueryRequest(BaseModel):
    query: str = Field(description="Natural-language question")
    cluster_id: Optional[str] = Field(
        default=None, description="Cluster ID (e.g. ST010_HEINRICH_ZILLE_STRASSE); "
        "extracted from the query if omitted"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _results_path(cluster_id: str, phase: str, scenario: Optional[str] = None) -> Path:
    from branitz_heat_decision.config import resolve_cluster_path

    p = resolve_cluster_path(cluster_id, phase)
    if scenario and phase in ("economics", "decision"):
        from branitz_heat_decision.economics.scenarios import scenario_name

        p = p / "scenarios" / scenario_name(scenario)
    return p


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {path.name}. Run the pipeline first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _execute_phases(cluster_id: str, req: RunRequest) -> Dict[str, Any]:
    """Run the requested phases sequentially via the ADK tool wrappers."""
    from branitz_heat_decision.adk.tools import (
        prepare_data_tool,
        run_cha_tool,
        run_dha_tool,
        run_economics_tool,
        run_decision_tool,
        run_uhdc_tool,
    )

    runners = {
        "data_prep": lambda: prepare_data_tool(),
        "cha": lambda: run_cha_tool(cluster_id=cluster_id),
        "dha": lambda: run_dha_tool(cluster_id=cluster_id),
        "economics": lambda: run_economics_tool(
            cluster_id=cluster_id, n_samples=req.n_samples, scenario=req.scenario
        ),
        "decision": lambda: run_decision_tool(cluster_id=cluster_id, scenario=req.scenario),
        "uhdc": lambda: run_uhdc_tool(cluster_id=cluster_id),
    }

    phase_results: Dict[str, Any] = {}
    status = "success"
    for phase in req.phases:
        logger.info("[API] %s: running phase %s", cluster_id, phase)
        result = runners[phase]()
        phase_results[phase] = {
            "status": result.get("status"),
            "outputs": result.get("outputs"),
            "error": result.get("error") or (result.get("stderr") or "")[-2000:] or None,
        }
        if result.get("status") != "success":
            status = "error"
            logger.error("[API] %s: phase %s failed — aborting chain", cluster_id, phase)
            break

    return {
        "cluster_id": cluster_id,
        "scenario": req.scenario,
        "status": status,
        "phases": phase_results,
    }


def _run_job(job_id: str, cluster_id: str, req: RunRequest) -> None:
    try:
        result = _execute_phases(cluster_id, req)
        with _JOBS_LOCK:
            _JOBS[job_id].update(status=result["status"], result=result)
    except Exception as e:  # pragma: no cover
        logger.exception("Job %s failed", job_id)
        with _JOBS_LOCK:
            _JOBS[job_id].update(status="error", result={"error": str(e)})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/clusters")
def list_clusters() -> Dict[str, Any]:
    """Available cluster IDs from the processed cluster index."""
    try:
        from branitz_heat_decision.ui.services import ClusterService

        idx = ClusterService().get_cluster_index()
        if not idx.empty:
            col = "cluster_id" if "cluster_id" in idx.columns else idx.columns[0]
            return {"clusters": idx[col].astype(str).tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cluster index unavailable: {e}")
    return {"clusters": []}


@app.get("/scenarios")
def list_scenarios_endpoint() -> Dict[str, Any]:
    from branitz_heat_decision.economics.scenarios import list_scenarios

    return {"scenarios": list_scenarios()}


@app.post("/clusters/{cluster_id}/run")
def run_cluster(
    cluster_id: str, req: RunRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Run pipeline phases for a cluster (deterministic Option B path)."""
    invalid = [p for p in req.phases if p not in VALID_PHASES]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Invalid phases: {invalid}. Valid: {VALID_PHASES}")
    if req.scenario:
        from branitz_heat_decision.economics.scenarios import resolve_scenario_path

        try:
            resolve_scenario_path(req.scenario)
        except FileNotFoundError as e:
            raise HTTPException(status_code=422, detail=str(e))

    if req.background:
        job_id = uuid.uuid4().hex[:12]
        with _JOBS_LOCK:
            _JOBS[job_id] = {
                "job_id": job_id,
                "cluster_id": cluster_id,
                "status": "running",
                "result": None,
            }
        background_tasks.add_task(_run_job, job_id, cluster_id, req)
        return {"job_id": job_id, "status": "running", "poll": f"/jobs/{job_id}"}

    return _execute_phases(cluster_id, req)


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id")
    return job


@app.get("/clusters/{cluster_id}/decision")
def get_decision(cluster_id: str, scenario: Optional[str] = None) -> Dict[str, Any]:
    """Decision JSON (winner, reason codes, metrics, robustness)."""
    d = _results_path(cluster_id, "decision", scenario)
    decision = _read_json(d / f"decision_{cluster_id}.json")
    out: Dict[str, Any] = {"cluster_id": cluster_id, "scenario": scenario, "decision": decision}
    contract = d / f"kpi_contract_{cluster_id}.json"
    if contract.exists():
        out["kpi_contract"] = json.loads(contract.read_text(encoding="utf-8"))
    explanation = d / f"explanation_{cluster_id}.md"
    if explanation.exists():
        out["explanation_md"] = explanation.read_text(encoding="utf-8")
    return out


@app.get("/clusters/{cluster_id}/kpis")
def get_kpis(cluster_id: str, scenario: Optional[str] = None) -> Dict[str, Any]:
    """Raw KPIs from all completed phases (missing phases are null)."""
    out: Dict[str, Any] = {"cluster_id": cluster_id, "scenario": scenario}
    cha = _results_path(cluster_id, "cha") / "cha_kpis.json"
    dha = _results_path(cluster_id, "dha") / "dha_kpis.json"
    econ_dir = _results_path(cluster_id, "economics", scenario)
    econ = econ_dir / "economics_monte_carlo.json"
    if not econ.exists():
        econ = econ_dir / "monte_carlo_summary.json"
    det = econ_dir / "economics_deterministic.json"
    out["cha"] = json.loads(cha.read_text(encoding="utf-8")) if cha.exists() else None
    out["dha"] = json.loads(dha.read_text(encoding="utf-8")) if dha.exists() else None
    out["economics_monte_carlo"] = json.loads(econ.read_text(encoding="utf-8")) if econ.exists() else None
    out["economics_deterministic"] = json.loads(det.read_text(encoding="utf-8")) if det.exists() else None
    if all(out[k] is None for k in ("cha", "dha", "economics_monte_carlo", "economics_deterministic")):
        raise HTTPException(status_code=404, detail=f"No results for {cluster_id}. Run the pipeline first.")
    return out


@app.post("/query")
def query(req: QueryRequest) -> Dict[str, Any]:
    """Natural-language query via the agentic orchestrator (Option A path)."""
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    from branitz_heat_decision.agents import BranitzOrchestrator

    # One orchestrator per process (keeps conversation memory across calls)
    global _ORCHESTRATOR
    try:
        _ORCHESTRATOR
    except NameError:
        _ORCHESTRATOR = BranitzOrchestrator()

    result = _ORCHESTRATOR.route_request(
        user_query=req.query,
        cluster_id=req.cluster_id,
        context={},
        run_missing=True,
    )
    return {
        "answer": result.get("answer"),
        "type": result.get("type"),
        "can_proceed": result.get("can_proceed"),
        "data": result.get("data"),
        "execution_log": result.get("execution_log"),
        "agent_trace": result.get("agent_trace"),
        "intent_data": result.get("intent_data"),
    }
