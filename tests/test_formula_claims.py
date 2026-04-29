from branitz_heat_decision.validation.claims import (
    Claim,
    ClaimType,
    ClaimValidator,
    Operator,
    StructuredExplanation,
)
from branitz_heat_decision.validation.logic_auditor import LogicAuditor


KPIS = {
    "lcoh_dh_median": 64.64,
    "lcoh_hp_median": 148.30,
    "co2_dh_median": 46.8,
    "co2_hp_median": 42.1,
    "dh_wins_fraction": 1.0,
}


def test_claim_validator_supports_arithmetic_expression_equality():
    validator = ClaimValidator()
    claim = Claim(
        claim_type=ClaimType.THRESHOLD,
        lhs="pct_delta(lcoh_hp_median, lcoh_dh_median)",
        op=Operator.EQ,
        rhs=129.4,
        description="HP LCOH is about 129.4% higher than DH",
    )

    result = validator.validate_claim(claim, KPIS)

    assert result.is_valid
    assert result.actual_lhs is not None
    assert abs(result.actual_lhs - 129.4) < 0.1


def test_claim_validator_supports_formula_comparison_between_expressions():
    validator = ClaimValidator()
    claim = Claim(
        claim_type=ClaimType.THRESHOLD,
        lhs="delta(lcoh_hp_median, lcoh_dh_median)",
        op=Operator.GT,
        rhs="delta(co2_dh_median, co2_hp_median)",
        description="Cost delta is larger than the CO2 delta",
    )

    result = validator.validate_claim(claim, KPIS)

    assert result.is_valid


def test_logic_auditor_validates_structured_formula_claims():
    auditor = LogicAuditor()
    explanation = StructuredExplanation(
        choice="DH",
        claims=[
            Claim(
                claim_type=ClaimType.ROBUSTNESS,
                lhs="dh_wins_fraction * 100",
                op=Operator.EQ,
                rhs=100.0,
                description="DH wins in 100% of Monte Carlo samples",
            ),
            Claim(
                claim_type=ClaimType.LCOH_COMPARE,
                lhs="lcoh_dh_median",
                op=Operator.LT,
                rhs="lcoh_hp_median",
                description="DH has lower LCOH than HP",
            ),
        ],
        rationale_text="DH wins all Monte Carlo samples and has lower LCOH.",
    )

    report = auditor.validate_structured_claims(KPIS, explanation, "ST010")

    assert report.validation_status == "pass"
    assert report.contradiction_count == 0
