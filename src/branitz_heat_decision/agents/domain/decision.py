"""Decision domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

logger = logging.getLogger(__name__)


class DecisionAgent(BaseDomainAgent):
    """
    Expediter: Final Decision Specialist.
    Handles: KPI contracts, rule-based decision, explanation generation.
    """

    _CACHE_MODEL_VERSION = 3

    def can_handle(self, intent: str, context: Dict) -> bool:
        decision_intents = [
            "DECISION", "RECOMMENDATION", "EXPLAIN_DECISION",
            "FINAL_CHOICE", "WHAT_SHOULD_WE_DO", "GRID_REINFORCEMENT",
        ]
        return intent in decision_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}
        require_live_llm = bool(context.get("require_live_llm_explanation"))

        # Check prerequisites
        econ_ready = self._check_economics_exists(street_id)
        if not econ_ready:
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={"prerequisites_missing": {"economics": False}},
                errors=["Economics results required before decision"],
            )

        # Check cache — decision file on disk
        cache_hit, cached_data = self._check_decision_cache(street_id, context)
        if cache_hit and not context.get("force_recalc") and not require_live_llm:
            wants_explanation = bool(
                context.get("llm_explanation")
                or context.get("require_validated_explanation")
            )
            sidecars = (
                self._load_decision_sidecars(street_id)
                if wants_explanation
                else {"llm_explanation": None, "validation": None}
            )
            if context.get("require_validated_explanation") and (
                not sidecars["llm_explanation"] or not sidecars["validation"]
            ):
                logger.info(
                    "[%s] Cached decision for %s missing validated explanation; regenerating.",
                    self.agent_name,
                    street_id,
                )
            else:
                logger.info(f"[{self.agent_name}] Using cached decision for {street_id}")
                from branitz_heat_decision.config import resolve_cluster_path
                manifest = self._read_cache_manifest(
                    resolve_cluster_path(street_id, "decision") / "_cache_manifest.json"
                )
                return AgentResult(
                    success=True,
                    data={
                        "decision": cached_data,
                        "outputs": {},
                        "llm_explanation": sidecars["llm_explanation"],
                        "explanation_source": cached_data.get("explanation_source"),
                        "explanation_model": cached_data.get("explanation_model"),
                        "validation": sidecars["validation"],
                    },
                    execution_time=time.time() - start,
                    cache_hit=True,
                    agent_name=self.agent_name,
                    metadata={
                        "cache_source": "file_system",
                        "choice": cached_data.get("choice") or cached_data.get("recommendation"),
                        "robust": cached_data.get("robust"),
                        "validation_status": (
                            sidecars["validation"] or {}
                        ).get("validation_status"),
                        "explanation_source": cached_data.get("explanation_source"),
                        "explanation_model": cached_data.get("explanation_model"),
                        **self._cache_timing_metadata(manifest),
                    },
                )

        # Delegate to ADK DecisionAgent
        adk = base._get_adk_agents()
        adk_agent = adk["Decision"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            llm_explanation=context.get("llm_explanation", True),
            explanation_style=context.get("style", "executive"),
            no_fallback=context.get("no_fallback", False),
        )

        result = action.result or {}
        execution_time = time.time() - start

        # Load decision result
        decision_data = result.get("decision", {})
        llm_explanation = result.get("explanation")
        validation = result.get("validation")
        explanation_source = decision_data.get("explanation_source")
        explanation_model = decision_data.get("explanation_model")
        if action.status == "success" and decision_data:
            self._write_reinforcement_comparison(street_id, decision_data)
        validation_passed = bool(
            validation
            and str(validation.get("validation_status", "")).lower() == "pass"
            and int(validation.get("contradiction_count", 0) or 0) == 0
        )
        if llm_explanation and not validation_passed:
            logger.warning(
                "[%s] Explanation generated for %s without a passing validation; "
                "blocking long-form explanation while retaining the audit.",
                self.agent_name,
                street_id,
            )
            llm_explanation = None

        if require_live_llm and explanation_source != "gemini_api":
            return AgentResult(
                success=False,
                data={},
                execution_time=execution_time,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={"street_id": street_id, "explanation_source": explanation_source},
                errors=[
                    "A live Gemini explanation was required, but no verified Gemini response "
                    "was produced. Check the API connection and validation output."
                ],
            )

        from branitz_heat_decision.config import resolve_cluster_path
        manifest_path = resolve_cluster_path(street_id, "decision") / "_cache_manifest.json"
        self._write_cache_manifest(
            manifest_path,
            input_hash=self._decision_cache_key(street_id, context),
            calculation_duration_seconds=execution_time,
        )

        return AgentResult(
            success=action.status == "success",
            data={
                "tool_result": result,
                "decision": decision_data,
                "recommendation": decision_data.get("recommendation"),
                "robust": decision_data.get("robust", False),
                "outputs": result.get("outputs", {}),
                "llm_explanation": llm_explanation,
                "explanation_source": explanation_source,
                "explanation_model": explanation_model,
                "validation": validation,
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "choice": decision_data.get("recommendation"),
                "robust": decision_data.get("robust"),
                "winner": decision_data.get("winner"),
                "reason_code": decision_data.get("reason_code"),
                "validation_status": (validation or {}).get("validation_status"),
                "explanation_source": explanation_source,
                "explanation_model": explanation_model,
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _check_economics_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "economics") / "economics_deterministic.json").exists()

    def _check_decision_cache(self, street_id: str, context: Dict = None) -> tuple[bool, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        dec_file = resolve_cluster_path(street_id, "decision") / f"decision_{street_id}.json"
        manifest_file = resolve_cluster_path(street_id, "decision") / "_cache_manifest.json"
        
        if dec_file.exists() and manifest_file.exists():
            import json
            plan_path = resolve_cluster_path(street_id, "dha") / "dha_reinforcement.json"
            if plan_path.exists():
                try:
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    plan = {}
                if plan.get("is_sufficient") and not all(
                    (dec_file.parent / name).exists()
                    for name in (
                        f"kpi_contract_reinforced_{street_id}.json",
                        f"decision_reinforced_{street_id}.json",
                        "reinforcement_before_after.json",
                    )
                ):
                    return False, None
            manifest = self._read_cache_manifest(manifest_file)
            dependencies = self._decision_dependencies(street_id)
            expected_hash = self._decision_cache_key(street_id, context or {})
            if self._manifest_matches(
                manifest,
                expected_hash,
                manifest_file,
                dependencies,
            ):
                with open(dec_file) as f:
                    return True, json.load(f)
            else:
                logger.info(f"[{self.agent_name}] Cache hash mismatch. Recomputing.")
        return False, None

    def _decision_cache_key(self, street_id: str, context: Dict) -> str:
        cache_context = {
            **(context or {}),
            "decision_case_schema": self._CACHE_MODEL_VERSION,
        }
        return self._compute_cache_key(
            cache_context,
            self._decision_dependencies(street_id),
        )

    def _decision_dependencies(self, street_id: str):
        from branitz_heat_decision.config import resolve_cluster_path

        return [
            resolve_cluster_path(street_id, "cha") / "cha_kpis.json",
            resolve_cluster_path(street_id, "dha") / "dha_kpis.json",
            resolve_cluster_path(street_id, "economics") / "economics_monte_carlo.json",
            resolve_cluster_path(street_id, "dha") / "dha_reinforcement.json",
            resolve_cluster_path(street_id, "economics")
            / "reinforcement"
            / "economics_monte_carlo.json",
        ]

    def _load_decision_sidecars(self, street_id: str) -> Dict[str, Any]:
        from branitz_heat_decision.config import resolve_cluster_path
        import hashlib
        import json

        output_dir = resolve_cluster_path(street_id, "decision")
        explanation_text = None
        validation = None

        contract_path = output_dir / f"kpi_contract_{street_id}.json"
        provenance_path = output_dir / f"explanation_{street_id}_metadata.json"
        provenance_matches = False
        if contract_path.exists() and provenance_path.exists():
            try:
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                canonical_contract = json.dumps(
                    contract,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                provenance_matches = provenance.get("contract_sha256") == hashlib.sha256(
                    canonical_contract
                ).hexdigest()
            except (OSError, ValueError, TypeError):
                provenance_matches = False

        if not provenance_matches:
            return {"llm_explanation": None, "validation": None}

        explanation_path = output_dir / f"explanation_{street_id}.md"
        if explanation_path.exists():
            try:
                explanation_text = explanation_path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to load explanation for %s: %s",
                    self.agent_name,
                    street_id,
                    exc,
                )

        validation_path = output_dir / f"validation_{street_id}.json"
        if validation_path.exists():
            try:
                with open(validation_path, "r", encoding="utf-8") as f:
                    validation = json.load(f)
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to load validation for %s: %s",
                    self.agent_name,
                    street_id,
                    exc,
                )

        # Validation artifacts created before sentence-level prose auditing do
        # not prove that the cached Gemini text itself was checked. Refresh only
        # the fast decision/explanation stage once; CHA/DHA/economics stay cached.
        generated_audit = (
            ((validation or {}).get("evidence") or {}).get(
                "generated_explanation_audit"
            )
        )
        if explanation_text and not generated_audit:
            explanation_text = None
            validation = None

        if explanation_text and not validation:
            explanation_text = None

        return {
            "llm_explanation": explanation_text,
            "validation": validation,
        }

    def _write_reinforcement_comparison(
        self,
        street_id: str,
        baseline_decision: Dict[str, Any],
    ) -> None:
        """Persist a separate baseline vs verified-reinforcement audit."""
        import copy
        import csv
        import json
        from datetime import datetime, timezone

        from branitz_heat_decision.config import resolve_cluster_path
        from branitz_heat_decision.decision.kpi_contract import build_kpi_contract
        from branitz_heat_decision.decision.rules import decide_from_contract

        cha_dir = resolve_cluster_path(street_id, "cha")
        dha_dir = resolve_cluster_path(street_id, "dha")
        econ_dir = resolve_cluster_path(street_id, "economics")
        decision_dir = resolve_cluster_path(street_id, "decision")
        plan_path = dha_dir / "dha_reinforcement.json"
        cha_path = cha_dir / "cha_kpis.json"
        dha_path = dha_dir / "dha_kpis.json"
        reinforced_econ_dir = econ_dir / "reinforcement"
        reinforced_economics_path = reinforced_econ_dir / "economics_deterministic.json"
        reinforced_mc_path = reinforced_econ_dir / "economics_monte_carlo.json"
        required = (
            plan_path,
            cha_path,
            dha_path,
            reinforced_economics_path,
            reinforced_mc_path,
        )
        if not all(path.exists() for path in required):
            return

        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            cha_kpis = json.loads(cha_path.read_text(encoding="utf-8"))
            dha_kpis = json.loads(dha_path.read_text(encoding="utf-8"))
            reinforced_economics = json.loads(
                reinforced_economics_path.read_text(encoding="utf-8")
            )
            reinforced_mc = json.loads(reinforced_mc_path.read_text(encoding="utf-8"))
            if not plan.get("is_sufficient"):
                return

            # Build an explicitly named reinforced contract from the verified
            # post-load-flow KPIs. The canonical contract remains untouched.
            reinforced_dha = copy.deepcopy(dha_kpis)
            reinforced_kpis = reinforced_dha.get("kpis", reinforced_dha)
            reinforced_kpis.update(plan.get("after_kpis", {}))
            reinforced_kpis["feasible"] = True
            reinforced_kpis["reasons"] = ["HP_OK"]
            reinforced_kpis.pop("reinforcement", None)

            generated_at = datetime.now(timezone.utc).replace(microsecond=0)
            generated_at_utc = generated_at.isoformat().replace("+00:00", "Z")
            reinforced_contract = build_kpi_contract(
                street_id,
                cha_kpis,
                reinforced_dha,
                reinforced_mc,
                metadata={
                    "created_utc": generated_at_utc,
                    "inputs": {
                        "cha_kpis_path": str(cha_path.resolve()),
                        "dha_reinforcement_path": str(plan_path.resolve()),
                        "economics_summary_path": str(reinforced_mc_path.resolve()),
                    },
                    "analysis_case": "verified_reinforcement",
                    "notes": [
                        "Separate counterfactual; canonical current-grid results are unchanged."
                    ],
                },
            )
            reinforced_decision = decide_from_contract(reinforced_contract).to_dict()

            (decision_dir / f"kpi_contract_reinforced_{street_id}.json").write_text(
                json.dumps(reinforced_contract, indent=2),
                encoding="utf-8",
            )
            (decision_dir / f"decision_reinforced_{street_id}.json").write_text(
                json.dumps(reinforced_decision, indent=2),
                encoding="utf-8",
            )

            comparison = {
                "cluster_id": street_id,
                "generated_at_utc": generated_at_utc,
                "methodology": (
                    "canonical current-grid decision compared with a separately stored "
                    "verified post-reinforcement load-flow and economics scenario"
                ),
                "before_reinforcement": {
                    "grid_kpis": plan.get("before_kpis", {}),
                    "decision": baseline_decision,
                },
                "after_reinforcement": {
                    "grid_kpis": plan.get("after_kpis", {}),
                    "reinforcement_cost_eur": plan.get("total_cost_eur"),
                    "lcoh_dh_eur_per_mwh": reinforced_economics.get(
                        "lcoh_dh_eur_per_mwh"
                    ),
                    "lcoh_hp_eur_per_mwh": reinforced_economics.get(
                        "lcoh_hp_eur_per_mwh"
                    ),
                    "decision": reinforced_decision,
                },
                "decision_changes": (
                    (baseline_decision.get("choice") or baseline_decision.get("recommendation"))
                    != (
                        reinforced_decision.get("choice")
                        or reinforced_decision.get("recommendation")
                    )
                ),
            }
            json_path = decision_dir / "reinforcement_before_after.json"
            json_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")

            rows = [
                {
                    "metric": "HP feasible",
                    "before": plan.get("before_kpis", {}).get("feasible"),
                    "after": plan.get("after_kpis", {}).get("feasible"),
                },
                {
                    "metric": "Maximum feeder loading (%)",
                    "before": plan.get("before_kpis", {}).get("max_feeder_loading_pct"),
                    "after": plan.get("after_kpis", {}).get("max_feeder_loading_pct"),
                },
                {
                    "metric": "Line violations",
                    "before": plan.get("before_kpis", {}).get("line_violations_total"),
                    "after": plan.get("after_kpis", {}).get("line_violations_total"),
                },
                {
                    "metric": "Recommendation",
                    "before": baseline_decision.get("choice")
                    or baseline_decision.get("recommendation"),
                    "after": reinforced_decision.get("choice")
                    or reinforced_decision.get("recommendation"),
                },
                {
                    "metric": "HP LCOH after verified reinforcement (EUR/MWh)",
                    "before": "not technically feasible",
                    "after": reinforced_economics.get("lcoh_hp_eur_per_mwh"),
                },
            ]
            csv_path = decision_dir / "reinforcement_before_after.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["metric", "before", "after"])
                writer.writeheader()
                writer.writerows(rows)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning(
                "[%s] Could not write reinforcement comparison for %s: %s",
                self.agent_name,
                street_id,
                exc,
            )
