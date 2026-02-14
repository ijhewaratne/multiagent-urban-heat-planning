"""
Logic Auditor - validates LLM-generated rationales using TNLI.

Edit C: Fixed scoring semantics (verified/unverified/contradiction)
Edit D: Wired feedback loop for automatic regeneration
Edit E: ClaimExtractor for quantitative regex-based claim extraction
        Golden fixtures for deterministic regression testing

Checks if natural language explanations are consistent with KPI data tables.
"""

from __future__ import annotations

import logging
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Tuple

from .tnli_model import TNLIModel, LightweightResult as EntailmentResult, EntailmentLabel
from .config import ValidationConfig
from .claims import StructuredExplanation, ClaimValidator, ClaimResult

logger = logging.getLogger(__name__)


@dataclass
class Contradiction:
    """A detected contradiction between statement and table."""
    statement: str
    context: str  # Which KPI/metric it contradicts
    confidence: float
    evidence: Optional[Dict[str, Any]] = None


@dataclass
class ValidationReport:
    """
    Report of validation results.
    
    Edit C: Proper scoring semantics:
    - verified_rate: fraction of statements that are ENTAILED
    - unverified_rate: fraction that are NEUTRAL (not provable)
    - contradiction_rate: fraction that CONTRADICT the data
    """
    
    cluster_id: str
    timestamp: datetime
    validation_status: str  # "pass", "warning", "fail"
    overall_confidence: float
    
    statements_validated: int = 0
    contradictions: List[Contradiction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    feedback_iterations: int = 0
    
    entailment_results: List[EntailmentResult] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    # Edit C: Proper scoring metrics
    verified_count: int = 0
    unverified_count: int = 0
    contradiction_count: int = 0
    
    @property
    def has_contradictions(self) -> bool:
        """Check if any contradictions were found."""
        return len(self.contradictions) > 0
    
    @property
    def verified_rate(self) -> float:
        """Percentage of statements that were verified (ENTAILED)."""
        if self.statements_validated == 0:
            return 0.0
        return self.verified_count / self.statements_validated
    
    @property
    def unverified_rate(self) -> float:
        """Percentage of statements that could not be verified (NEUTRAL)."""
        if self.statements_validated == 0:
            return 0.0
        return self.unverified_count / self.statements_validated
    
    @property
    def contradiction_rate(self) -> float:
        """Percentage of statements that contradict the data."""
        if self.statements_validated == 0:
            return 0.0
        return self.contradiction_count / self.statements_validated
    
    @property
    def pass_rate(self) -> float:
        """Alias for verified_rate for backward compatibility."""
        return self.verified_rate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "cluster_id": self.cluster_id,
            "timestamp": self.timestamp.isoformat(),
            "validation_status": self.validation_status,
            "overall_confidence": self.overall_confidence,
            "statements_validated": self.statements_validated,
            # Include sentence-by-sentence results
            "sentence_results": [
                {
                    "statement": result.statement,
                    "status": "ENTAILMENT" if result.is_valid else 
                             "CONTRADICTION" if result.is_contradiction else 
                             "NEUTRAL",
                    "confidence": result.confidence,
                    "evidence": result.reason,
                    "label": result.label.value
                }
                for result in self.entailment_results
            ],
            "contradictions": [
                {
                    "statement": c.statement,
                    "context": c.context,
                    "confidence": c.confidence,
                    "evidence": c.evidence
                }
                for c in self.contradictions
            ],
            "warnings": self.warnings,
            "feedback_iterations": self.feedback_iterations,
            # Edit C: Include proper scoring
            "verified_count": self.verified_count,
            "unverified_count": self.unverified_count,
            "contradiction_count": self.contradiction_count,
            "verified_rate": self.verified_rate,
            "unverified_rate": self.unverified_rate,
            "contradiction_rate": self.contradiction_rate,
            "pass_rate": self.pass_rate,
            "evidence": self.evidence
        }


# ---------------------------------------------------------------------------
# Edit E: Quantitative Claim Extractor (regex-based)
# ---------------------------------------------------------------------------

class ClaimExtractor:
    """
    Extract quantitative claims from free-text LLM explanations.

    Bridges the gap between unstructured explanation text and structured
    validation: regex patterns pull out numbers that can be cross-checked
    against the canonical KPI dictionary.
    """

    PATTERNS: Dict[str, str] = {
        # ---- CO2 variants ----
        "co2_dh_median": (
            r"(?:DH|District\s+Heating).{0,40}?"
            r"(\d+\.?\d*)\s*(?:tCO2|tons?|t)\s*/\s*(?:year|yr|a)"
        ),
        "co2_hp_median": (
            r"(?:HP|Heat\s+Pump).{0,40}?"
            r"(\d+\.?\d*)\s*(?:tCO2|tons?|t)\s*/\s*(?:year|yr|a)"
        ),
        "co2_delta": (
            r"(?:less|more|lower|higher).{0,30}?"
            r"(\d+\.?\d*)\s*%\s*.{0,20}?"
            r"(?:CO2|emissions?)"
        ),

        # ---- LCOH variants ----
        # Handles both "DH is 85.4 €/MWh" and "85.4 €/MWh for DH"
        "lcoh_dh_median": (
            r"(?:"
            r"(?:DH|District\s+Heating).{0,40}?(\d+\.?\d*)\s*\u20ac/MWh"
            r"|"
            r"(\d+\.?\d*)\s*\u20ac/MWh\s+(?:for\s+)?(?:DH|District\s+Heating)"
            r")"
        ),
        "lcoh_hp_median": (
            r"(?:"
            r"(?:HP|Heat\s+Pump).{0,40}?(\d+\.?\d*)\s*\u20ac/MWh"
            r"|"
            r"(\d+\.?\d*)\s*\u20ac/MWh\s+(?:for\s+)?(?:HP|Heat\s+Pump)"
            r")"
        ),
        "lcoh_delta_pct": (
            r"(?:cheaper|expensive|more\s+costly).{0,30}?"
            r"(\d+\.?\d*)\s*%"
        ),

        # ---- Network / losses ----
        "loss_share_pct": r"(?:loss|losses).{0,30}?(\d+\.?\d*)\s*%",
        "pump_power_kw": r"(?:pump|pumping).{0,30}?(\d+\.?\d*)\s*kW",

        # ---- Pressure ----
        "dp_per_100m_max": (
            r"(?:pressure\s+drop|\u0394p|dp).{0,40}?"
            r"(\d+\.?\d*)\s*(?:bar|mbar)"
        ),
        "en_threshold": (
            r"(?:EN\s*13941|threshold).{0,40}?"
            r"(\d+\.?\d*)"
        ),

        # ---- Monte Carlo ----
        "mc_win_fraction": (
            r"(?:win|probability|wins\s+in).{0,30}?"
            r"(\d+\.?\d*)\s*%"
        ),
        "mc_n_samples": (
            r"(?:Monte\s+Carlo|simulations?).{0,40}?"
            r"(\d+)\s*(?:samples?|runs?|iterations?)"
        ),
        "robustness": (
            r"(?:robust|sensitive).{0,30}?"
            r"(\d+\.?\d*)\s*%"
        ),
    }

    # Maps extractor keys → canonical KPI dict keys for cross-validation.
    KPI_KEY_MAP: Dict[str, List[str]] = {
        "co2_dh_median": ["co2_dh_t_per_a", "co2_dh_median"],
        "co2_hp_median": ["co2_hp_t_per_a", "co2_hp_median"],
        "lcoh_dh_median": ["lcoh_dh_eur_per_mwh", "lcoh_dh_median", "lcoh_dh"],
        "lcoh_hp_median": ["lcoh_hp_eur_per_mwh", "lcoh_hp_median", "lcoh_hp"],
        "loss_share_pct": ["loss_share_pct", "heat_loss_pct"],
        "pump_power_kw": ["pump_power_kw", "pump_kw"],
        "dp_per_100m_max": ["dp_per_100m_max", "dp_max_bar_per_100m"],
        "mc_win_fraction": ["dh_win_fraction", "dh_wins_fraction", "mc_win_fraction"],
        "mc_n_samples": ["mc_n_samples", "n_samples"],
    }

    # Relative tolerance for numeric comparison (10 % by default).
    DEFAULT_TOLERANCE = 0.10

    @classmethod
    def extract_all(cls, text: str) -> Dict[str, List[float]]:
        """
        Extract all quantitative claims from explanation text.

        Returns a dict mapping claim key → list of extracted float values.
        Handles alternation patterns that produce tuple groups by picking
        the first non-empty group from each match.
        """
        claims: Dict[str, List[float]] = {}
        for key, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                values: List[float] = []
                for m in matches:
                    if isinstance(m, tuple):
                        # Alternation pattern — pick first non-empty group
                        val = next((g for g in m if g), None)
                    else:
                        val = m
                    if val:
                        values.append(float(val))
                if values:
                    claims[key] = values
        return claims

    @classmethod
    def cross_validate(
        cls,
        extracted: Dict[str, List[float]],
        kpis: Dict[str, Any],
        tolerance: float | None = None,
    ) -> List[Tuple[str, float, float, bool, str]]:
        """
        Cross-validate extracted claims against canonical KPIs.

        Returns list of (claim_key, extracted_val, kpi_val, is_match, reason).
        """
        tol = tolerance if tolerance is not None else cls.DEFAULT_TOLERANCE
        results: List[Tuple[str, float, float, bool, str]] = []

        for claim_key, values in extracted.items():
            kpi_candidates = cls.KPI_KEY_MAP.get(claim_key, [claim_key])
            kpi_val: Optional[float] = None
            for cand in kpi_candidates:
                if cand in kpis and kpis[cand] is not None:
                    try:
                        kpi_val = float(kpis[cand])
                    except (ValueError, TypeError):
                        continue
                    break

            if kpi_val is None:
                # No reference KPI available — skip (can't validate)
                continue

            # mc_win_fraction is often stated as % in text but stored as fraction
            if claim_key == "mc_win_fraction" and kpi_val < 1.0:
                kpi_val = kpi_val * 100.0  # normalise to %

            for val in values:
                if kpi_val == 0:
                    is_match = val == 0
                else:
                    is_match = math.isclose(val, kpi_val, rel_tol=tol)

                reason = (
                    f"{claim_key}: text says {val}, KPI says {kpi_val} "
                    f"-> {'MATCH' if is_match else 'MISMATCH'} "
                    f"(tol={tol*100:.0f}%)"
                )
                results.append((claim_key, val, kpi_val, is_match, reason))

        return results


# ---------------------------------------------------------------------------
# Edit E: Golden Fixtures for deterministic regression testing
# ---------------------------------------------------------------------------

GOLDEN_FIXTURES: List[Dict[str, Any]] = [
    {
        "name": "ST010_CO2_correct",
        "explanation": (
            "District Heating emits 45.2 tCO2/year vs "
            "Heat Pumps 67.3 tCO2/year. DH has 33% lower emissions."
        ),
        "expected_claims": {
            "co2_dh_median": [45.2],
            "co2_hp_median": [67.3],
        },
        "should_pass": True,
    },
    {
        "name": "ST010_LCOH_correct",
        "explanation": (
            "LCOH for DH is 85.4 \u20ac/MWh compared to "
            "92.1 \u20ac/MWh for HP. DH is 7.3% cheaper."
        ),
        "expected_claims": {
            "lcoh_dh_median": [85.4],
            "lcoh_hp_median": [92.1],
        },
        "should_pass": True,
    },
    {
        "name": "ST010_wrong_numbers",
        "explanation": "District Heating emits 30 tCO2/year.",
        "expected_claims": {
            "co2_dh_median": [30.0],
        },
        "should_pass": False,  # Should be caught as contradiction against actual 45.2
    },
    {
        "name": "ST010_loss_share",
        "explanation": (
            "Network heat losses are 8.5% of total heat delivered. "
            "Pump power is 12.3 kW."
        ),
        "expected_claims": {
            "loss_share_pct": [8.5],
            "pump_power_kw": [12.3],
        },
        "should_pass": True,
    },
    {
        "name": "ST010_mc_robust",
        "explanation": (
            "Monte Carlo analysis with 1000 samples shows DH wins "
            "in 78% of scenarios, making this a robust decision."
        ),
        "expected_claims": {
            "mc_n_samples": [1000],
            "mc_win_fraction": [78.0],
        },
        "should_pass": True,
    },
]

# Reference KPIs used for golden fixture validation.
GOLDEN_REFERENCE_KPIS: Dict[str, Any] = {
    "co2_dh_t_per_a": 45.2,
    "co2_hp_t_per_a": 67.3,
    "lcoh_dh_eur_per_mwh": 85.4,
    "lcoh_hp_eur_per_mwh": 92.1,
    "loss_share_pct": 8.5,
    "pump_power_kw": 12.3,
    "mc_n_samples": 1000,
    "dh_win_fraction": 0.78,
}


def test_golden_fixtures() -> List[Dict[str, Any]]:
    """
    Run all golden fixtures through ClaimExtractor + cross-validation.

    Can be invoked as a standalone self-test:
        python -m branitz_heat_decision.validation.logic_auditor
    """
    results: List[Dict[str, Any]] = []

    for fixture in GOLDEN_FIXTURES:
        # Step 1: Extract claims from explanation text
        extracted = ClaimExtractor.extract_all(fixture["explanation"])

        # Step 2: Verify expected claims were found
        extraction_ok = True
        for key, expected_vals in fixture["expected_claims"].items():
            if key not in extracted:
                extraction_ok = False
                break
            for ev in expected_vals:
                if not any(math.isclose(ev, av, rel_tol=0.01) for av in extracted[key]):
                    extraction_ok = False
                    break

        # Step 3: Cross-validate against reference KPIs
        xval = ClaimExtractor.cross_validate(extracted, GOLDEN_REFERENCE_KPIS)
        all_match = all(ok for (_, _, _, ok, _) in xval) if xval else True
        passed = all_match  # True → no mismatches with reference KPIs

        expected = fixture["should_pass"]
        correct = passed == expected

        results.append({
            "name": fixture["name"],
            "correct": correct,  # True if result matches expectation
            "expected_pass": expected,
            "actual_pass": passed,
            "extraction_ok": extraction_ok,
            "extracted_claims": extracted,
            "cross_validation": [
                {"key": k, "text": tv, "kpi": kv, "match": m, "reason": r}
                for k, tv, kv, m, r in xval
            ],
        })

    return results


# ---------------------------------------------------------------------------
# LogicAuditor
# ---------------------------------------------------------------------------

class LogicAuditor:
    """
    Validates LLM-generated decision rationales against KPI tables.
    
    Edit D: Includes optional feedback loop for automatic regeneration.
    Edit E: Integrates ClaimExtractor for quantitative cross-validation.
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        """Initialize Logic Auditor with TNLI model."""
        self.config = config or ValidationConfig()
        self.model = TNLIModel(self.config)
        self.claim_validator = ClaimValidator()
        logger.info("LogicAuditor initialized")
    
    def validate_rationale(
        self,
        kpis: Dict[str, Any],
        rationale: str,
        cluster_id: str = "unknown",
        regenerate_fn: Optional[Callable[[Dict[str, Any], str], str]] = None
    ) -> ValidationReport:
        """
        Validate a decision rationale against KPI table.
        
        Edit D: If regenerate_fn is provided and feedback is enabled,
        will attempt to regenerate on contradictions.
        
        Args:
            kpis: Dictionary of KPIs (metrics and values)
            rationale: Natural language explanation to validate
            cluster_id: Identifier for the cluster
            regenerate_fn: Optional function to regenerate rationale
            
        Returns:
            ValidationReport with validation results
        """
        current_rationale = rationale
        iteration = 0
        
        while iteration < self.config.max_iterations:
            iteration += 1
            
            # Perform validation
            report = self._validate_once(kpis, current_rationale, cluster_id)
            report.feedback_iterations = iteration
            
            # Check if we should stop
            if not report.has_contradictions:
                logger.info(f"Validation passed on iteration {iteration}")
                return report
            
            # Edit D: Attempt regeneration if enabled and function provided
            if not self.config.enable_feedback or regenerate_fn is None:
                return report
            
            if iteration >= self.config.max_iterations:
                logger.warning(f"Max iterations ({self.config.max_iterations}) reached")
                return report
            
            # Build enriched context for regeneration
            context = self._build_feedback_context(kpis, report.contradictions)
            
            logger.info(f"Regenerating rationale (iteration {iteration})")
            try:
                new_rationale = regenerate_fn(kpis, context)
                
                if new_rationale.strip() == current_rationale.strip():
                    logger.warning("Regenerated rationale unchanged, stopping")
                    return report
                
                current_rationale = new_rationale
            except Exception as e:
                logger.error(f"Regeneration failed: {e}")
                return report
        
        return report
    
    # ------------------------------------------------------------------
    # Edit E: Standalone free-text validation with ClaimExtractor
    # ------------------------------------------------------------------

    def validate_explanation(
        self,
        explanation: str,
        kpis: Dict[str, Any],
        cluster_id: str = "unknown",
        tolerance: float | None = None,
    ) -> ValidationReport:
        """
        Validate a free-text explanation against reference KPIs.

        Combines:
        1. **ClaimExtractor** — regex-based quantitative cross-validation
        2. **TNLI** — semantic entailment for non-numeric statements

        This is the primary entry point for validating LLM-generated
        explanations where no structured claims are available.

        Args:
            explanation: Free-text explanation to validate.
            kpis: Reference KPI dictionary.
            cluster_id: Cluster identifier for the report.
            tolerance: Relative tolerance for numeric comparison (default 10 %).

        Returns:
            ValidationReport with combined results.
        """
        # --- Phase 1: Quantitative claim extraction + cross-validation ---
        extracted = ClaimExtractor.extract_all(explanation)
        xval_results = ClaimExtractor.cross_validate(extracted, kpis, tolerance)

        quant_contradictions: List[Contradiction] = []
        quant_verified = 0
        quant_total = len(xval_results)

        for claim_key, text_val, kpi_val, is_match, reason in xval_results:
            if is_match:
                quant_verified += 1
            else:
                quant_contradictions.append(Contradiction(
                    statement=f"{claim_key}: text says {text_val}",
                    context=f"KPI {claim_key} = {kpi_val}",
                    confidence=1.0,  # Deterministic check
                    evidence={
                        "claim_key": claim_key,
                        "text_value": text_val,
                        "kpi_value": kpi_val,
                        "reason": reason,
                    },
                ))

        # --- Phase 2: TNLI semantic validation on full sentences ---
        tnli_report = self._validate_once(kpis, explanation, cluster_id)

        # --- Merge results ---
        # Quantitative mismatches always count as contradictions
        all_contradictions = quant_contradictions + tnli_report.contradictions
        total_verified = quant_verified + tnli_report.verified_count
        total_unverified = tnli_report.unverified_count
        total_contradiction = len(all_contradictions)
        total_statements = quant_total + tnli_report.statements_validated

        if all_contradictions:
            status = "fail"
        elif total_unverified > total_statements * 0.5:
            status = "warning"
        elif tnli_report.warnings:
            status = "warning"
        else:
            status = "pass"

        avg_conf = (
            tnli_report.overall_confidence
            if tnli_report.statements_validated
            else 1.0
        )

        return ValidationReport(
            cluster_id=cluster_id,
            timestamp=datetime.now(),
            validation_status=status,
            overall_confidence=avg_conf,
            statements_validated=total_statements,
            contradictions=all_contradictions,
            warnings=tnli_report.warnings,
            entailment_results=tnli_report.entailment_results,
            verified_count=total_verified,
            unverified_count=total_unverified,
            contradiction_count=total_contradiction,
            evidence={
                "kpis": {k: str(v) for k, v in kpis.items()},
                "quantitative_extraction": {
                    k: v for k, v in extracted.items()
                },
                "cross_validation": [
                    {"key": k, "text": tv, "kpi": kv, "match": m, "reason": r}
                    for k, tv, kv, m, r in xval_results
                ],
            },
        )

    # ------------------------------------------------------------------
    # Internal: single TNLI validation pass
    # ------------------------------------------------------------------

    def _validate_once(
        self,
        kpis: Dict[str, Any],
        rationale: str,
        cluster_id: str
    ) -> ValidationReport:
        """Single validation pass (no feedback loop)."""
        # Parse rationale into individual statements
        statements = self._parse_statements(rationale)
        
        logger.info(f"Validating {len(statements)} statements for cluster {cluster_id}")
        
        # Validate each statement
        results = self.model.batch_validate(kpis, statements)
        
        # Edit C: Proper scoring semantics
        contradictions = []
        warnings = []
        verified_count = 0
        unverified_count = 0
        contradiction_count = 0
        total_confidence = 0.0
        
        for result in results:
            total_confidence += result.confidence
            
            if result.is_valid:  # ENTAILED
                verified_count += 1
            elif result.is_contradiction:  # CONTRADICTION
                contradiction_count += 1
                context = self._identify_contradiction_context(result.statement, kpis)
                contradictions.append(Contradiction(
                    statement=result.statement,
                    context=context,
                    confidence=result.confidence,
                    evidence={
                        "kpis_checked": list(kpis.keys()),
                        "reason": result.reason
                    }
                ))
            else:  # NEUTRAL
                unverified_count += 1
                if result.confidence < self.config.min_confidence:
                    warnings.append(f"Could not verify: {result.statement[:100]}")
        
        # Edit C: Proper status determination
        # FAIL only if contradictions exist
        # WARNING if too many unverified (neutral) or low confidence
        # PASS if verified is high and contradictions are zero
        if contradictions:
            status = "fail"
        elif unverified_count > len(statements) * 0.5:  # >50% unverified
            status = "warning"
        elif warnings:
            status = "warning"
        else:
            status = "pass"
        
        avg_confidence = total_confidence / len(results) if results else 0.0
        
        report = ValidationReport(
            cluster_id=cluster_id,
            timestamp=datetime.now(),
            validation_status=status,
            overall_confidence=avg_confidence,
            statements_validated=len(statements),
            contradictions=contradictions,
            warnings=warnings,
            entailment_results=results,
            verified_count=verified_count,
            unverified_count=unverified_count,
            contradiction_count=contradiction_count,
            evidence={"kpis": {k: str(v) for k, v in kpis.items()}}
        )
        
        logger.info(
            f"Validation: {status} | Verified: {verified_count}, "
            f"Unverified: {unverified_count}, Contradictions: {contradiction_count}"
        )
        
        return report
    
    def validate_structured_claims(
        self,
        kpis: Dict[str, Any],
        explanation: StructuredExplanation,
        cluster_id: str = "unknown"
    ) -> ValidationReport:
        """
        Validate structured claims (Edit A format).
        
        Deterministic validation - no LLM needed.
        """
        results = self.claim_validator.validate_all(explanation, kpis)
        
        contradictions = []
        verified_count = 0
        
        for result in results:
            if result.is_valid:
                verified_count += 1
            else:
                contradictions.append(Contradiction(
                    statement=result.claim.description or str(result.claim.lhs),
                    context=result.reason,
                    confidence=1.0,  # Deterministic
                    evidence={
                        "lhs": result.actual_lhs,
                        "rhs": result.actual_rhs,
                        "operator": result.claim.op.value
                    }
                ))
        
        status = "fail" if contradictions else "pass"
        
        # Convert ClaimResults to EntailmentResults for UI display
        entailment_results = []
        for result in results:
            label = EntailmentLabel.ENTAILMENT if result.is_valid else EntailmentLabel.CONTRADICTION
            statement = result.claim.description or f"{result.claim.lhs} {result.claim.op} {result.claim.rhs}"
            
            entailment_results.append(EntailmentResult(
                statement=statement,
                label=label,
                confidence=1.0,
                reason=result.reason
            ))

        return ValidationReport(
            cluster_id=cluster_id,
            timestamp=datetime.now(),
            validation_status=status,
            overall_confidence=1.0,  # Deterministic
            statements_validated=len(results),
            contradictions=contradictions,
            verified_count=verified_count,
            unverified_count=0,
            contradiction_count=len(contradictions),
            evidence={"kpis": {k: str(v) for k, v in kpis.items()}},
            entailment_results=entailment_results
        )
    
    def validate_decision_explanation(
        self,
        decision_data: Dict[str, Any]
    ) -> ValidationReport:
        """
        Validate a complete decision explanation.
        
        Issue A Fix: Injects choice/reason_codes into KPIs for deterministic validation.
        Correctness Fix: Uses structured claims for reason_codes to validate each individually.
        """
        kpis = decision_data.get("kpis", decision_data.get("metrics_used", {})).copy()
        cluster_id = decision_data.get("cluster_id", "unknown")
        reason_codes = decision_data.get("reason_codes", [])
        
        # Issue A: Inject decision fields into KPIs for rule-based validation
        if "choice" in decision_data:
            kpis["choice"] = decision_data["choice"]
        if "recommendation" in decision_data:
            kpis["recommendation"] = decision_data["recommendation"]
        if "robust" in decision_data:
            kpis["robust"] = decision_data["robust"]
        if reason_codes:
            kpis["reason_codes"] = reason_codes
            
            # Infer feasibility from reason_codes if not already set
            if "ONLY_DH_FEASIBLE" in reason_codes:
                if "dh_feasible" not in kpis and "cha_feasible" not in kpis:
                    kpis["dh_feasible"] = True
                if "hp_feasible" not in kpis and "dha_feasible" not in kpis:
                    kpis["hp_feasible"] = False
            elif "ONLY_HP_FEASIBLE" in reason_codes:
                if "hp_feasible" not in kpis and "dha_feasible" not in kpis:
                    kpis["hp_feasible"] = True
                if "dh_feasible" not in kpis and "cha_feasible" not in kpis:
                    kpis["dh_feasible"] = False
                    
            # Infer robustness from ROBUST_DECISION reason code
            if "ROBUST_DECISION" in reason_codes and "robust" not in kpis:
                kpis["robust"] = True
        
        # Check for structured claims first (best path - fully deterministic)
        if "claims" in decision_data:
            explanation = StructuredExplanation.from_dict(decision_data)
            return self.validate_structured_claims(kpis, explanation, cluster_id)
        
        # Correctness Fix: If reason_codes exist, use structured claims path
        # This ensures each reason code is validated individually
        if reason_codes:
            structured = StructuredExplanation.from_decision_result(decision_data)

            return self.validate_structured_claims(kpis, structured, cluster_id)
        
        # Fall back to free-text validation only if no structured data available
        explanation = decision_data.get("explanation", "")
        return self.validate_rationale(kpis, explanation, cluster_id)
    
    def _parse_statements(self, rationale: str) -> List[str]:
        """Parse rationale into individual statements for validation."""
        import re
        
        # Split on sentence boundaries
        sentences = re.split(r'[.!?]+', rationale)
        
        # Clean and filter
        statements = []
        for sentence in sentences:
            cleaned = sentence.strip()
            if len(cleaned) > 15 and any(char.isalpha() for char in cleaned):
                statements.append(cleaned)
        
        return statements
    
    def _identify_contradiction_context(self, statement: str, kpis: Dict[str, Any]) -> str:
        """Identify which KPI(s) a contradictory statement relates to."""
        statement_lower = statement.lower()
        
        relevant_kpis = []
        for key in kpis.keys():
            if key.lower().replace("_", " ") in statement_lower:
                relevant_kpis.append(key)
        
        if relevant_kpis:
            return f"KPIs: {', '.join(relevant_kpis)}"
        else:
            return "Unknown KPI context"
    
    def _build_feedback_context(
        self,
        kpis: Dict[str, Any],
        contradictions: List[Contradiction]
    ) -> str:
        """Build enriched context for LLM regeneration."""
        context_parts = [
            "IMPORTANT: Previous explanation contained contradictions.",
            "",
            "**Verified KPI Values:**"
        ]
        
        for key, value in kpis.items():
            context_parts.append(f"- {key}: {value}")
        
        context_parts.append("")
        context_parts.append("**Detected Contradictions:**")
        
        for i, contra in enumerate(contradictions, 1):
            context_parts.append(f"{i}. \"{contra.statement}\"")
            context_parts.append(f"   Problem: {contra.context}")
        
        context_parts.extend([
            "",
            "**Guidelines:**",
            "- Only make statements verifiable from KPIs",
            "- Use exact values from the table",
            "- Avoid speculation"
        ])
        
        return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# Self-test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json

    print("Running golden fixture self-test...\n")
    fixture_results = test_golden_fixtures()

    all_correct = True
    for r in fixture_results:
        icon = "PASS" if r["correct"] else "FAIL"
        all_correct = all_correct and r["correct"]
        print(f"  [{icon}] {r['name']}")
        if not r["correct"]:
            print(f"         expected_pass={r['expected_pass']}, actual_pass={r['actual_pass']}")
        for xv in r["cross_validation"]:
            m_icon = "ok" if xv["match"] else "MISMATCH"
            print(f"         {m_icon}: {xv['reason']}")

    print(f"\n{'All golden fixtures passed!' if all_correct else 'Some fixtures FAILED.'}")
    sys.exit(0 if all_correct else 1)
