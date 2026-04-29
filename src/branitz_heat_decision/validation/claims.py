"""
Structured claims for deterministic validation.

Claims represent verifiable assertions that can be checked against KPI data.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, List, Any, Optional


class ClaimType(str, Enum):
    """Types of verifiable claims."""
    LCOH_COMPARE = "LCOH_COMPARE"      # Compare LCOH values
    CO2_COMPARE = "CO2_COMPARE"         # Compare CO2 emissions
    ROBUSTNESS = "ROBUSTNESS"           # Monte Carlo win fraction check
    FEASIBILITY = "FEASIBILITY"         # Feasibility flag check
    THRESHOLD = "THRESHOLD"             # Generic threshold comparison
    CHOICE_VALID = "CHOICE_VALID"       # Validate choice against data


class Operator(str, Enum):
    """Comparison operators."""
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "=="
    NE = "!="


@dataclass
class Claim:
    """A verifiable claim about KPI data."""
    claim_type: ClaimType
    lhs: str  # Left-hand side (KPI key or value)
    op: Operator
    rhs: str | float  # Right-hand side (KPI key or literal value)
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.claim_type.value,
            "lhs": self.lhs,
            "op": self.op.value,
            "rhs": self.rhs,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Claim":
        return cls(
            claim_type=ClaimType(data["type"]),
            lhs=data["lhs"],
            op=Operator(data["op"]),
            rhs=data["rhs"],
            description=data.get("description")
        )


@dataclass
class ClaimResult:
    """Result of validating a claim."""
    claim: Claim
    is_valid: bool
    actual_lhs: Optional[float] = None
    actual_rhs: Optional[float] = None
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "is_valid": self.is_valid,
            "actual_lhs": self.actual_lhs,
            "actual_rhs": self.actual_rhs,
            "reason": self.reason
        }


@dataclass
class StructuredExplanation:
    """
    Structured explanation format for deterministic validation.
    
    Instead of arbitrary text, explanations are structured claims.
    """
    choice: str  # "DH", "HP", or "UNDECIDED"
    claims: List[Claim]
    rationale_text: str  # Human-readable summary
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "choice": self.choice,
            "claims": [c.to_dict() for c in self.claims],
            "rationale_text": self.rationale_text
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredExplanation":
        return cls(
            choice=data["choice"],
            claims=[Claim.from_dict(c) for c in data.get("claims", [])],
            rationale_text=data.get("rationale_text", "")
        )
    
    @classmethod
    def from_decision_result(cls, decision_result: Dict[str, Any]) -> "StructuredExplanation":
        """
        Build structured explanation from decision result.
        
        Converts reason_codes and metrics to verifiable claims.
        """
        choice = decision_result.get("choice", "UNDECIDED")
        reason_codes = decision_result.get("reason_codes", [])
        metrics = decision_result.get("metrics_used", {})
        
        claims = []
        rationale_parts = []
        
        # Generate claims from reason codes
        for code in reason_codes:
            if code == "COST_DOMINANT_DH":
                claims.append(Claim(
                    claim_type=ClaimType.LCOH_COMPARE,
                    lhs="lcoh_dh_median",
                    op=Operator.LT,
                    rhs="lcoh_hp_median",
                    description="DH has lower LCOH than HP"
                ))
                rationale_parts.append("District heating has lower costs")
                
            elif code == "COST_DOMINANT_HP":
                claims.append(Claim(
                    claim_type=ClaimType.LCOH_COMPARE,
                    lhs="lcoh_hp_median",
                    op=Operator.LT,
                    rhs="lcoh_dh_median",
                    description="HP has lower LCOH than DH"
                ))
                rationale_parts.append("Heat pumps have lower costs")
                
            elif code == "CO2_TIEBREAKER_DH":
                claims.append(Claim(
                    claim_type=ClaimType.CO2_COMPARE,
                    lhs="co2_dh_median",
                    op=Operator.LT,
                    rhs="co2_hp_median",
                    description="DH has lower CO2 emissions"
                ))
                rationale_parts.append("District heating has lower CO2 emissions")
                
            elif code == "CO2_TIEBREAKER_HP":
                claims.append(Claim(
                    claim_type=ClaimType.CO2_COMPARE,
                    lhs="co2_hp_median",
                    op=Operator.LT,
                    rhs="co2_dh_median",
                    description="HP has lower CO2 emissions"
                ))
                rationale_parts.append("Heat pumps have lower CO2 emissions")
                
            elif code == "ROBUST_DECISION":
                if choice == "DH":
                    claims.append(Claim(
                        claim_type=ClaimType.ROBUSTNESS,
                        lhs="dh_wins_fraction",
                        op=Operator.GE,
                        rhs=0.7,
                        description="DH has robust win fraction (≥70%)"
                    ))
                else:
                    claims.append(Claim(
                        claim_type=ClaimType.ROBUSTNESS,
                        lhs="hp_wins_fraction",
                        op=Operator.GE,
                        rhs=0.7,
                        description="HP has robust win fraction (≥70%)"
                    ))
                rationale_parts.append("Decision is robust based on Monte Carlo analysis")
                
            elif code == "ONLY_DH_FEASIBLE":
                claims.append(Claim(
                    claim_type=ClaimType.FEASIBILITY,
                    lhs="dh_feasible",
                    op=Operator.EQ,
                    rhs=True,
                    description="Only DH is feasible"
                ))
                claims.append(Claim(
                    claim_type=ClaimType.FEASIBILITY,
                    lhs="hp_feasible",
                    op=Operator.EQ,
                    rhs=False,
                    description="HP is not feasible"
                ))
                rationale_parts.append("Only district heating is technically feasible")
                
            elif code == "ONLY_HP_FEASIBLE":
                claims.append(Claim(
                    claim_type=ClaimType.FEASIBILITY,
                    lhs="hp_feasible",
                    op=Operator.EQ,
                    rhs=True,
                    description="Only HP is feasible"
                ))
                claims.append(Claim(
                    claim_type=ClaimType.FEASIBILITY,
                    lhs="dh_feasible",
                    op=Operator.EQ,
                    rhs=False,
                    description="DH is not feasible"
                ))
                rationale_parts.append("Only heat pumps are technically feasible")
        
        # Add choice validation claim
        claims.append(Claim(
            claim_type=ClaimType.CHOICE_VALID,
            lhs="recommended_choice",
            op=Operator.EQ,
            rhs=choice,
            description=f"Recommended choice is {choice}"
        ))
        
        rationale_text = ". ".join(rationale_parts) if rationale_parts else f"Recommended: {choice}"
        
        return cls(
            choice=choice,
            claims=claims,
            rationale_text=rationale_text
        )


class ClaimValidator:
    """
    Validates structured claims against KPI data.

    In addition to simple KPI-to-KPI comparisons, claims may now reference
    arithmetic expressions such as:

        "(lcoh_hp_median - lcoh_dh_median) / lcoh_hp_median * 100"
        "pct_delta(co2_dh_median, co2_hp_median)"
        "delta(lcoh_hp_median, lcoh_dh_median)"

    Expressions are evaluated deterministically using a restricted AST.
    """
    
    # Key aliases to map claim keys to actual KPI keys
    KEY_ALIASES = {
        "dh_feasible": ["dh_feasible", "cha_feasible", "feasible_dh"],
        "hp_feasible": ["hp_feasible", "dha_feasible", "feasible_hp", "grid_feasible"],
        "recommended_choice": ["choice", "recommendation", "recommended_choice"],
        "dh_wins_fraction": ["dh_wins_fraction", "dh_win_fraction", "mc_dh_wins"],
        "hp_wins_fraction": ["hp_wins_fraction", "hp_win_fraction", "mc_hp_wins"],
        "lcoh_dh": ["lcoh_dh_median", "lcoh_dh"],
        "lcoh_hp": ["lcoh_hp_median", "lcoh_hp"],
        "co2_dh": ["co2_dh_median", "co2_dh"],
        "co2_hp": ["co2_hp_median", "co2_hp"],
    }

    NUMERIC_EQ_REL_TOL = 0.01
    NUMERIC_EQ_ABS_TOL = 0.1

    SAFE_FUNCTIONS = {
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "sum": lambda *args: sum(args),
        "avg": lambda *args: sum(args) / len(args) if args else 0.0,
        "delta": lambda a, b: float(a) - float(b),
        "ratio": lambda a, b: float(a) / float(b),
        "pct_delta": (
            lambda a, b: 0.0
            if float(b) == 0
            else ((float(a) - float(b)) / float(b)) * 100.0
        ),
    }
    
    def __init__(self):
        pass
    
    def validate_claim(self, claim: Claim, kpis: Dict[str, Any]) -> ClaimResult:
        """
        Validate a single claim against KPI data.
        
        Returns ClaimResult with is_valid and reasoning.
        """
        # Get LHS value using alias mapping
        lhs_val = self._get_value(claim.lhs, kpis)
        
        # Get RHS value - check if it's a literal or KPI reference
        # For CHOICE_VALID and FEASIBILITY, RHS is typically a literal value
        if isinstance(claim.rhs, (int, float, bool)):
            rhs_val = claim.rhs
        elif claim.claim_type in (ClaimType.CHOICE_VALID, ClaimType.FEASIBILITY):
            # These claim types use literal RHS values (e.g., "DH", True, False)
            rhs_val = claim.rhs
        else:
            # Try to resolve as literal, KPI reference, or arithmetic expression.
            looked_up = self._get_value(str(claim.rhs), kpis)
            # If not found and it looks like a literal string (short, no underscores), use as-is
            if looked_up is None and isinstance(claim.rhs, str) and len(claim.rhs) <= 10 and "_" not in claim.rhs:
                rhs_val = claim.rhs
            else:
                rhs_val = looked_up
        
        # Check if values are available
        if lhs_val is None:
            return ClaimResult(
                claim=claim,
                is_valid=False,
                reason=f"Missing LHS value: {claim.lhs}"
            )
        
        if rhs_val is None:
            return ClaimResult(
                claim=claim,
                is_valid=False,
                reason=f"Missing RHS value: {claim.rhs}"
            )
        
        # Perform comparison
        is_valid = self._compare(lhs_val, claim.op, rhs_val)
        
        reason = f"{claim.lhs}={lhs_val} {claim.op.value} {claim.rhs}={rhs_val}: {'✅ TRUE' if is_valid else '❌ FALSE'}"
        
        return ClaimResult(
            claim=claim,
            is_valid=is_valid,
            actual_lhs=lhs_val if isinstance(lhs_val, (int, float)) else None,
            actual_rhs=rhs_val if isinstance(rhs_val, (int, float)) else None,
            reason=reason
        )
    
    def validate_all(self, explanation: StructuredExplanation, kpis: Dict[str, Any]) -> List[ClaimResult]:
        """Validate all claims in a structured explanation."""
        return [self.validate_claim(claim, kpis) for claim in explanation.claims]

    def _lookup_kpi_name(self, key: str, kpis: Dict[str, Any]) -> Any:
        """Get value from KPIs, trying aliases and common key variations."""
        if key in kpis:
            return kpis[key]

        aliases = self.KEY_ALIASES.get(key, [])
        for alias in aliases:
            if alias in kpis:
                return kpis[alias]

        if key.endswith("_median"):
            base = key[:-7]
            if base in kpis:
                return kpis[base]
            for alias in self.KEY_ALIASES.get(base, []):
                if alias in kpis:
                    return kpis[alias]

        if f"{key}_median" in kpis:
            return kpis[f"{key}_median"]

        return None

    def _get_value(self, key: str, kpis: Dict[str, Any]) -> Any:
        """
        Resolve a claim operand.

        Resolution order:
        1. direct KPI lookup / alias lookup
        2. numeric literal parsing
        3. safe arithmetic expression evaluation
        """
        looked_up = self._lookup_kpi_name(key, kpis)
        if looked_up is not None:
            return looked_up

        numeric_literal = self._parse_numeric_literal(key)
        if numeric_literal is not None:
            return numeric_literal

        if self._looks_like_expression(key):
            try:
                return self._evaluate_expression(key, kpis)
            except Exception:
                return None

        return None

    @staticmethod
    def _parse_numeric_literal(value: Any) -> Optional[float]:
        """Parse strings like '42', '3.14', or '-7.5' into floats."""
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return None

        stripped = value.strip()
        try:
            return float(stripped)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _looks_like_expression(value: Any) -> bool:
        """Heuristic to detect arithmetic expressions instead of plain KPI keys."""
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        if not stripped:
            return False
        if any(ch in stripped for ch in "+-*/()%"):
            return True
        return "(" in stripped and ")" in stripped

    def _evaluate_expression(self, expr: str, kpis: Dict[str, Any]) -> float:
        """Safely evaluate a restricted arithmetic expression over KPI values."""
        node = ast.parse(expr, mode="eval")
        return float(self._eval_ast(node.body, kpis))

    def _eval_ast(self, node: ast.AST, kpis: Dict[str, Any]) -> float:
        """Recursive evaluator for restricted arithmetic AST nodes."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported literal in expression: {node.value!r}")

        if isinstance(node, ast.Num):  # pragma: no cover - py<3.8 compatibility
            return float(node.n)

        if isinstance(node, ast.Name):
            value = self._lookup_kpi_name(node.id, kpis)
            if value is None:
                raise ValueError(f"Unknown KPI reference in expression: {node.id}")
            if isinstance(value, bool):
                return float(value)
            return float(value)

        if isinstance(node, ast.BinOp):
            left = self._eval_ast(node.left, kpis)
            right = self._eval_ast(node.right, kpis)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
            if isinstance(node.op, ast.Mod):
                return left % right
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_ast(node.operand, kpis)
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name not in self.SAFE_FUNCTIONS:
                raise ValueError(f"Unsupported function in expression: {func_name}")
            args = [self._eval_ast(arg, kpis) for arg in node.args]
            return float(self.SAFE_FUNCTIONS[func_name](*args))

        raise ValueError(f"Unsupported expression node: {type(node).__name__}")
    
    def _compare(self, lhs: Any, op: Operator, rhs: Any) -> bool:
        """Perform comparison operation."""
        try:
            lhs_is_num = isinstance(lhs, (int, float)) and not isinstance(lhs, bool)
            rhs_is_num = isinstance(rhs, (int, float)) and not isinstance(rhs, bool)

            if op == Operator.LT:
                return float(lhs) < float(rhs)
            elif op == Operator.LE:
                return float(lhs) <= float(rhs)
            elif op == Operator.GT:
                return float(lhs) > float(rhs)
            elif op == Operator.GE:
                return float(lhs) >= float(rhs)
            elif op == Operator.EQ:
                if lhs_is_num and rhs_is_num:
                    return math.isclose(
                        float(lhs),
                        float(rhs),
                        rel_tol=self.NUMERIC_EQ_REL_TOL,
                        abs_tol=self.NUMERIC_EQ_ABS_TOL,
                    )
                return lhs == rhs or str(lhs) == str(rhs)
            elif op == Operator.NE:
                if lhs_is_num and rhs_is_num:
                    return not math.isclose(
                        float(lhs),
                        float(rhs),
                        rel_tol=self.NUMERIC_EQ_REL_TOL,
                        abs_tol=self.NUMERIC_EQ_ABS_TOL,
                    )
                return lhs != rhs
            else:
                return False
        except (ValueError, TypeError):
            return False
