"""Validation (TNLI) domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

logger = logging.getLogger(__name__)


class ValidationAgent(BaseDomainAgent):
    """
    QA Chef: Logic Auditor & Validation Specialist.

    Two-stage validation pipeline:
      1. **ClaimExtractor** — regex-based extraction of quantitative claims
         from explanation text (LCOH, CO2, etc.) + cross-check vs KPIs.
      2. **TNLIModel** (LightweightValidator) — Tabular Natural Language
         Inference: rule-based + optional LLM verification of qualitative
         statements (comparisons, feasibility, robustness claims).

    No ADK agent equivalent — uses validation module directly.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        validation_intents = [
            "VALIDATE", "AUDIT", "CHECK_CLAIMS", "VERIFY_EXPLANATION",
        ]
        return intent in validation_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        explanation_text = context.get("explanation_text")
        if not explanation_text:
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={},
                errors=["No explanation text provided for validation"],
            )

        # ------------------------------------------------------------------
        # Load KPIs (economics + decision) for both stages
        # ------------------------------------------------------------------
        from branitz_heat_decision.config import resolve_cluster_path
        import json

        kpis: Dict[str, Any] = {}
        econ_path = resolve_cluster_path(street_id, "economics") / "economics_deterministic.json"
        if econ_path.exists():
            with open(econ_path) as f:
                kpis = json.load(f)

        # Merge decision data so TNLI can validate choice / robustness claims
        dec_path = resolve_cluster_path(street_id, "decision") / f"decision_{street_id}.json"
        if dec_path.exists():
            with open(dec_path) as f:
                dec = json.load(f)
            for key in ("choice", "recommendation", "robust", "reason_codes",
                        "dh_wins_fraction", "hp_wins_fraction",
                        "dh_feasible", "hp_feasible"):
                if key in dec and key not in kpis:
                    kpis[key] = dec[key]

        # ------------------------------------------------------------------
        # Stage 1: ClaimExtractor — quantitative claim extraction + check
        # ------------------------------------------------------------------
        from branitz_heat_decision.validation.logic_auditor import ClaimExtractor

        extractor = ClaimExtractor()
        claims = extractor.extract_all(explanation_text)

        mismatches = []
        for claim_type, values in claims.items():
            if claim_type == "lcoh_dh_median":
                expected = kpis.get("lcoh_dh_eur_per_mwh")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"LCOH DH: claim {values[0]} vs actual {expected}")
            elif claim_type == "lcoh_hp_median":
                expected = kpis.get("lcoh_hp_eur_per_mwh")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"LCOH HP: claim {values[0]} vs actual {expected}")
            elif claim_type == "co2_dh_median":
                expected = kpis.get("co2_dh_t_per_a")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"CO2 DH: claim {values[0]} vs actual {expected}")
            elif claim_type == "co2_hp_median":
                expected = kpis.get("co2_hp_t_per_a")
                if expected and abs(values[0] - expected) > 0.1:
                    mismatches.append(f"CO2 HP: claim {values[0]} vs actual {expected}")

        # ------------------------------------------------------------------
        # Stage 2: TNLI — semantic / qualitative statement validation
        # ------------------------------------------------------------------
        tnli_results = []
        tnli_contradictions = 0
        tnli_verified = 0
        try:
            from branitz_heat_decision.validation.tnli_model import TNLIModel

            tnli = TNLIModel()
            # Split explanation into individual sentences for validation
            sentences = [
                s.strip() for s in explanation_text.replace("\n", ". ").split(".")
                if len(s.strip()) > 10
            ]
            for sentence in sentences:
                result = tnli.validate_statement(kpis, sentence)
                tnli_results.append({
                    "statement": result.statement,
                    "label": result.label.value,
                    "confidence": result.confidence,
                    "reason": result.reason,
                })
                if result.is_contradiction:
                    tnli_contradictions += 1
                    mismatches.append(f"TNLI contradiction: '{sentence[:80]}…' — {result.reason}")
                elif result.is_valid:
                    tnli_verified += 1
        except Exception as exc:
            logger.warning(f"[{self.agent_name}] TNLI stage skipped: {exc}")

        execution_time = time.time() - start
        all_passed = len(mismatches) == 0

        return AgentResult(
            success=all_passed,
            data={
                "claims_extracted": claims,
                "mismatches": mismatches,
                "tnli_results": tnli_results,
                "explanation_text": explanation_text[:200] + "...",
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "claims_found": len(claims),
                "mismatches": len(mismatches),
                "tnli_verified": tnli_verified,
                "tnli_contradictions": tnli_contradictions,
                "tnli_total": len(tnli_results),
                "validation_passed": all_passed,
            },
            errors=mismatches if mismatches else [],
        )
