"""
Lightweight validation using LLM API or rule-based approach.

Edit B: Enhanced rule support for real decision claims
Edit C: Fixed scoring semantics (verified/unverified/contradiction)

No large model download required - uses Gemini API from .env.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EntailmentLabel(str, Enum):
    ENTAILMENT = "Entailment"
    NEUTRAL = "Neutral"
    CONTRADICTION = "Contradiction"


@dataclass
class LightweightResult:
    """Result from lightweight validation."""
    statement: str
    label: EntailmentLabel
    confidence: float
    reason: str = ""
    
    @property
    def is_valid(self) -> bool:
        return self.label == EntailmentLabel.ENTAILMENT
    
    @property
    def is_contradiction(self) -> bool:
        return self.label == EntailmentLabel.CONTRADICTION
    
    @property
    def is_neutral(self) -> bool:
        return self.label == EntailmentLabel.NEUTRAL


class LightweightValidator:
    """
    Lightweight validator that works without downloading large models.
    
    Options:
    1. Rule-based: Deterministic verification against KPIs
    2. LLM-based: Uses Gemini API for semantic validation
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize validator.
        
        Args:
            use_llm: If True, try to use Gemini API. If False or unavailable, use rules.
        """
        self.use_llm = use_llm
        self.llm_client = None
        
        if use_llm:
            self._init_llm()
    
    def _init_llm(self):
        """
        Try to initialize LLM client using API key from .env file.
        
        Issue B Fix: Model name configurable via GEMINI_MODEL env var.
        """
        try:
            import os
            
            # Load .env file using bootstrap utility
            try:
                from branitz_heat_decision.ui.env import bootstrap_env
                bootstrap_env()
            except ImportError:
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ImportError:
                    pass
            
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            
            # Issue B: Make model configurable
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            
            if api_key:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.llm_client = genai.GenerativeModel(model_name)
                logger.info(f"✅ LLM validation enabled (model: {model_name})")
            else:
                logger.warning("No GOOGLE_API_KEY found in .env, using rule-based validation only")
        except ImportError as e:
            logger.warning(f"Missing package: {e}, using rule-based validation")
        except Exception as e:
            logger.warning(f"Failed to init LLM: {e}, using rule-based validation")
    
    def validate_statement(
        self,
        kpis: Dict[str, Any],
        statement: str
    ) -> LightweightResult:
        """
        Validate a single statement against KPIs.
        
        First attempts rule-based validation.
        Falls back to LLM if rules don't apply.
        """
        # First try rule-based (deterministic)
        rule_result = self._validate_with_rules(kpis, statement)
        
        # If rules gave a definitive answer (not neutral), return it
        if rule_result.label != EntailmentLabel.NEUTRAL:
            return rule_result
        
        # If neutral and LLM available, try LLM
        if self.llm_client:
            return self._validate_with_llm(kpis, statement)
        
        return rule_result
    
    def _validate_with_llm(
        self,
        kpis: Dict[str, Any],
        statement: str
    ) -> LightweightResult:
        """
        Validate using LLM API.
        
        Issue B Fix: Disables client on exception to prevent repeated failures.
        """
        try:
            prompt = f"""You are a fact-checker for a district heating decision system.

Given the KPI data and a statement, determine if the statement is:
- ENTAILED: The statement is clearly supported by the data
- CONTRADICTION: The statement clearly contradicts the data
- NEUTRAL: Cannot determine from the data alone

KPI Data:
{self._format_kpis(kpis)}

Statement: "{statement}"

Respond in this exact format:
VERDICT: [ENTAILED/CONTRADICTION/NEUTRAL]
REASON: [Brief explanation why]"""

            response = self.llm_client.generate_content(prompt)
            text = response.text.strip()
            
            # Parse response
            verdict = "NEUTRAL"
            reason = ""
            
            for line in text.split("\n"):
                if line.startswith("VERDICT:"):
                    verdict = line.split(":", 1)[1].strip().upper()
                elif line.startswith("REASON:"):
                    reason = line.split(":", 1)[1].strip()
            
            if "ENTAILED" in verdict or "ENTAIL" in verdict:
                return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.85, reason)
            elif "CONTRADICTION" in verdict or "CONTRADICT" in verdict:
                return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.85, reason)
            else:
                return LightweightResult(statement, EntailmentLabel.NEUTRAL, 0.5, reason or "LLM uncertain")
                
        except Exception as e:
            # Issue B Fix: Disable client on exception to prevent repeated failures
            logger.warning(f"LLM validation failed: {e}. Disabling LLM for remaining validations.")
            self.llm_client = None  # Fail closed - use rules for rest of run
            return LightweightResult(statement, EntailmentLabel.NEUTRAL, 0.5, 
                "LLM unavailable, falling back to rules")
    
    def _validate_with_rules(
        self,
        kpis: Dict[str, Any],
        statement: str
    ) -> LightweightResult:
        """
        Enhanced rule-based validation (Edit B + Edit F).
        
        Covers broad natural-language phrasings for:
        - LCOH / cost comparisons and superiority claims
        - CO2 / emissions comparisons
        - Recommendation / choice / preference assertions
        - Feasibility claims
        - Robustness / Monte Carlo claims
        - Dominance / winner / optimal assertions
        - Specific numerical value matching
        """
        statement_lower = statement.lower()
        
        # Get KPI values with fallbacks
        lcoh_dh = self._get_kpi(kpis, ["lcoh_dh_median", "lcoh_dh", "lcoh_dh_eur_per_mwh"])
        lcoh_hp = self._get_kpi(kpis, ["lcoh_hp_median", "lcoh_hp", "lcoh_hp_eur_per_mwh"])
        co2_dh = self._get_kpi(kpis, ["co2_dh_median", "co2_dh", "co2_dh_t_per_a"])
        co2_hp = self._get_kpi(kpis, ["co2_hp_median", "co2_hp", "co2_hp_t_per_a"])
        dh_wins = self._get_kpi(kpis, ["dh_wins_fraction", "dh_win_fraction"])
        hp_wins = self._get_kpi(kpis, ["hp_wins_fraction", "hp_win_fraction"])
        dh_feasible = self._get_kpi(kpis, ["dh_feasible", "cha_feasible"])
        hp_feasible = self._get_kpi(kpis, ["hp_feasible", "dha_feasible"])
        choice = str(kpis.get("choice", kpis.get("recommendation", ""))).upper()
        
        # Subject detection helpers
        is_dh_ref = bool(re.search(r'\bdistrict\b|\bdh\b', statement_lower))
        is_hp_ref = bool(re.search(r'\bheat\s*pump\b|\bhp\b', statement_lower))
        
        # ── 1. RECOMMENDATION / CHOICE / PREFERENCE ASSERTIONS ──────
        # Broadened: catches "recommended choice", "recommended", "should be selected",
        # "is the preferred", "the recommendation is", "recommends", etc.
        recommend_patterns = [
            r'recommend', r'should be selected', r'preferred',
            r'the choice is', r'the heating (?:solution|recommendation)',
            r'analysis (?:supports|favors|recommends)',
            r'model (?:supports|prefers|recommends)',
        ]
        is_recommendation_claim = any(re.search(p, statement_lower) for p in recommend_patterns)
        
        if is_recommendation_claim and choice:
            claims_dh = is_dh_ref and not is_hp_ref
            claims_hp = is_hp_ref and not is_dh_ref
            # Also catch phrases like "recommends DH" without explicit subject
            if not claims_dh and not claims_hp:
                claims_dh = bool(re.search(r'recommend\w*\s+(?:dh|district)', statement_lower))
                claims_hp = bool(re.search(r'recommend\w*\s+(?:hp|heat\s*pump)', statement_lower))
            
            # Handle compound sentences with both DH and HP referenced
            if not claims_dh and not claims_hp and is_dh_ref and is_hp_ref:
                # Check for concessive structures: "but HP is recommended", "despite X, HP should be selected"
                # The system AFTER "but"/"however"/"despite" is the one being recommended
                concessive = re.search(r'(?:but|however|despite|yet|although|while)\b(.+)', statement_lower)
                if concessive:
                    tail = concessive.group(1)
                    if re.search(r'\bhp\b|heat\s*pump', tail) and any(re.search(p, tail) for p in recommend_patterns):
                        claims_hp = True
                    elif re.search(r'\bdh\b|district', tail) and any(re.search(p, tail) for p in recommend_patterns):
                        claims_dh = True
                
                # Check which system is nearest to recommend-verb
                if not claims_dh and not claims_hp:
                    for p in recommend_patterns:
                        m = re.search(p, statement_lower)
                        if m:
                            keyword_pos = m.start()
                            dh_pos = min((m.start() for m in re.finditer(r'\bdh\b|\bdistrict\b', statement_lower)), default=999)
                            hp_pos = min((m.start() for m in re.finditer(r'\bhp\b|heat\s*pump', statement_lower)), default=999)
                            # The system closest to the keyword (on either side) is the subject
                            if abs(keyword_pos - hp_pos) < abs(keyword_pos - dh_pos):
                                claims_hp = True
                            else:
                                claims_dh = True
                            break
            
            if claims_dh:
                if choice == "DH":
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.95,
                        f"Recommendation is DH (verified)")
                else:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.95,
                        f"Recommendation is {choice}, not DH")
            elif claims_hp:
                if choice == "HP":
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.95,
                        f"Recommendation is HP (verified)")
                else:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.95,
                        f"Recommendation is {choice}, not HP")
        
        # ── 2. FEASIBILITY CLAIMS ────────────────────────────────────
        if "only_dh_feasible" in statement_lower or "only dh feasible" in statement_lower or \
           ("only" in statement_lower and "district" in statement_lower and "feasible" in statement_lower):
            if dh_feasible is True and hp_feasible is False:
                return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.95,
                    "DH feasible=True, HP feasible=False")
            elif dh_feasible is not None and hp_feasible is not None:
                return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.95,
                    f"DH feasible={dh_feasible}, HP feasible={hp_feasible}")
        
        if "only_hp_feasible" in statement_lower or "only hp feasible" in statement_lower or \
           ("only" in statement_lower and "heat pump" in statement_lower and "feasible" in statement_lower):
            if hp_feasible is True and dh_feasible is False:
                return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.95,
                    "HP feasible=True, DH feasible=False")
            elif dh_feasible is not None and hp_feasible is not None:
                return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.95,
                    f"DH feasible={dh_feasible}, HP feasible={hp_feasible}")
        
        # General feasibility assertions (e.g. "DH is feasible", "both are feasible")
        if "feasible" in statement_lower or "technically viable" in statement_lower or \
           "compatible" in statement_lower:
            both_ref = is_dh_ref and is_hp_ref or "both" in statement_lower
            neither_ref = "neither" in statement_lower or "not feasible" in statement_lower
            
            if neither_ref:
                if dh_feasible or hp_feasible:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        f"DH feasible={dh_feasible}, HP feasible={hp_feasible}")
            elif both_ref:
                if dh_feasible and hp_feasible:
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                        "Both DH and HP are feasible")
                else:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        f"DH feasible={dh_feasible}, HP feasible={hp_feasible}")
            elif is_dh_ref and not is_hp_ref:
                if "not" in statement_lower or "infeasible" in statement_lower:
                    if dh_feasible is False:
                        return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                            "DH is not feasible (verified)")
                    elif dh_feasible is True:
                        return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                            "DH is feasible, not infeasible")
                elif dh_feasible is True:
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                        "DH feasibility confirmed")
                elif dh_feasible is False:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        "DH is not feasible")
            elif is_hp_ref and not is_dh_ref:
                if "not" in statement_lower or "infeasible" in statement_lower:
                    if hp_feasible is False:
                        return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                            "HP is not feasible (verified)")
                    elif hp_feasible is True:
                        return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                            "HP is feasible, not infeasible")
                elif hp_feasible is True:
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                        "HP feasibility confirmed")
                elif hp_feasible is False:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        "HP is not feasible")
        
        # ── 3. ROBUSTNESS / MONTE CARLO CLAIMS ──────────────────────
        if "robust" in statement_lower or "monte carlo" in statement_lower or \
           "probabilistic" in statement_lower or "win fraction" in statement_lower or \
           "majority" in statement_lower:
            if dh_wins is not None and dh_wins >= 0.7 and (is_dh_ref or choice == "DH"):
                return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                    f"DH win fraction = {dh_wins:.1%} ≥ 70%")
            elif hp_wins is not None and hp_wins >= 0.7 and (is_hp_ref or choice == "HP"):
                return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                    f"HP win fraction = {hp_wins:.1%} ≥ 70%")
            elif dh_wins is not None and hp_wins is not None:
                winner_fraction = dh_wins if choice == "DH" else hp_wins
                if winner_fraction < 0.7:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.85,
                        f"Win fraction = {winner_fraction:.1%} < 70% (not robust)")
        
        # ── 4. LCOH / COST COMPARISONS (broadened vocabulary) ────────
        cost_superiority_patterns = [
            r'cheaper', r'lower cost', r'lower lcoh', r'cost.?dominant',
            r'more expensive', r'higher cost', r'higher lcoh',
            r'cost.?effective', r'cost.?advantage', r'cost.?optimal',
            r'better value', r'better economics', r'economically\s+(?:prefer|optimal)',
            r'outperform', r'cost\s+comparison',
        ]
        is_cost_claim = any(re.search(p, statement_lower) for p in cost_superiority_patterns)
        
        # Also detect "X is the winner/dominant" which implies cost superiority
        winner_patterns = [
            r'(?:wins|dominat|superior)', r'favors?\b',
            r'the (?:clear |cost.?)?(?:winner|dominant)',
        ]
        is_winner_claim = any(re.search(p, statement_lower) for p in winner_patterns)
        
        if (is_cost_claim or is_winner_claim) and lcoh_dh is not None and lcoh_hp is not None:
            # Determine which system is being claimed as superior
            dh_claimed_superior = False
            hp_claimed_superior = False
            
            # Negative claims: "X is more expensive" → the OTHER is superior
            is_negative_cost = bool(re.search(r'more expensive|higher cost|higher lcoh|exceed', statement_lower))
            
            if is_negative_cost:
                # "HP is more expensive" → DH is cheaper
                if is_hp_ref and not is_dh_ref:
                    dh_claimed_superior = True
                elif is_dh_ref and not is_hp_ref:
                    hp_claimed_superior = True
                elif is_dh_ref and is_hp_ref:
                    # Both mentioned — figure out subject by word order
                    dh_pos = statement_lower.find("dh") if "dh" in statement_lower else statement_lower.find("district")
                    hp_pos = statement_lower.find("hp") if "hp" in statement_lower else statement_lower.find("heat pump")
                    if dh_pos < hp_pos:
                        hp_claimed_superior = True  # "DH is more expensive than HP"
                    else:
                        dh_claimed_superior = True
            else:
                # Positive claims: "DH is cheaper" → DH is superior
                if is_dh_ref and not is_hp_ref:
                    dh_claimed_superior = True
                elif is_hp_ref and not is_dh_ref:
                    hp_claimed_superior = True
                elif is_dh_ref and is_hp_ref:
                    # Handle concessive: "While DH costs less, ... favors HP"
                    concessive = re.search(r'(?:but|however|despite|yet|although|while)\b(.+)', statement_lower)
                    if concessive:
                        tail = concessive.group(1)
                        tail_has_hp = bool(re.search(r'\bhp\b|heat\s*pump', tail))
                        tail_has_dh = bool(re.search(r'\bdh\b|\bdistrict\b', tail))
                        tail_cost = any(re.search(p, tail) for p in cost_superiority_patterns)
                        tail_winner = any(re.search(p, tail) for p in winner_patterns)
                        if tail_has_hp and (tail_cost or tail_winner):
                            hp_claimed_superior = True
                        elif tail_has_dh and (tail_cost or tail_winner):
                            dh_claimed_superior = True
                    
                    if not dh_claimed_superior and not hp_claimed_superior:
                        # Fallback: proximity to positive keyword
                        dh_pos = statement_lower.find("dh") if "dh" in statement_lower else statement_lower.find("district")
                        hp_pos = statement_lower.find("hp") if "hp" in statement_lower else statement_lower.find("heat pump")
                        if dh_pos < hp_pos:
                            dh_claimed_superior = True
                        else:
                            hp_claimed_superior = True
            
            if dh_claimed_superior:
                if lcoh_dh < lcoh_hp:
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                        f"DH LCOH ({lcoh_dh:.1f}) < HP LCOH ({lcoh_hp:.1f})")
                else:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        f"DH LCOH ({lcoh_dh:.1f}) ≥ HP LCOH ({lcoh_hp:.1f})")
            elif hp_claimed_superior:
                if lcoh_hp < lcoh_dh:
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                        f"HP LCOH ({lcoh_hp:.1f}) < DH LCOH ({lcoh_dh:.1f})")
                else:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        f"HP LCOH ({lcoh_hp:.1f}) ≥ DH LCOH ({lcoh_dh:.1f})")
        
        # ── 5. CO2 COMPARISONS ───────────────────────────────────────
        co2_patterns = [
            r'lower co2', r'lower emission', r'co2 tiebreaker',
            r'less co2', r'fewer emission', r'higher emission',
            r'more emission', r'higher co2',
        ]
        is_co2_claim = any(re.search(p, statement_lower) for p in co2_patterns)
        
        if is_co2_claim and co2_dh is not None and co2_hp is not None:
            is_negative_co2 = bool(re.search(r'higher emission|higher co2|more emission', statement_lower))
            
            if is_negative_co2:
                if is_hp_ref and not is_dh_ref:
                    # "HP has higher emissions" → DH has lower
                    if co2_dh < co2_hp:
                        return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                            f"DH CO2 ({co2_dh:.1f}) < HP CO2 ({co2_hp:.1f})")
                    else:
                        return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                            f"DH CO2 ({co2_dh:.1f}) ≥ HP CO2 ({co2_hp:.1f})")
            else:
                if is_dh_ref and co2_dh < co2_hp:
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                        f"DH CO2 ({co2_dh:.1f}) < HP CO2 ({co2_hp:.1f})")
                elif is_dh_ref and co2_dh >= co2_hp:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        f"DH CO2 ({co2_dh:.1f}) ≥ HP CO2 ({co2_hp:.1f})")
                elif is_hp_ref and co2_hp < co2_dh:
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.9,
                        f"HP CO2 ({co2_hp:.1f}) < DH CO2 ({co2_dh:.1f})")
                elif is_hp_ref:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.9,
                        f"HP CO2 ({co2_hp:.1f}) ≥ DH CO2 ({co2_dh:.1f})")
        
        # ── 6. GENERIC COMPARISON / CONCLUSION ASSERTIONS ────────────
        # Catches: "the analysis confirms DH", "DH is the winner",
        # "economic model supports DH", etc.
        conclusion_patterns = [
            r'(?:analysis|model|assessment|evaluation|comparison)\s+(?:confirms?|shows?|supports?|indicates?)',
            r'clearly\s+(?:favors?|supports?|shows?)',
            r'the\s+(?:winner|optimal|best|dominant)\s+(?:choice|option|solution)',
        ]
        is_conclusion = any(re.search(p, statement_lower) for p in conclusion_patterns)
        
        if is_conclusion and choice and lcoh_dh is not None and lcoh_hp is not None:
            if is_dh_ref and not is_hp_ref:
                if choice == "DH":
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.85,
                        f"Analysis confirms DH (choice={choice})")
                else:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.85,
                        f"Analysis confirms {choice}, not DH")
            elif is_hp_ref and not is_dh_ref:
                if choice == "HP":
                    return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.85,
                        f"Analysis confirms HP (choice={choice})")
                else:
                    return LightweightResult(statement, EntailmentLabel.CONTRADICTION, 0.85,
                        f"Analysis confirms {choice}, not HP")
        
        # ── 7. Specific numerical values mentioned ───────────────────
        numbers_in_statement = re.findall(r'\d+\.?\d*', statement)
        for num_str in numbers_in_statement:
            try:
                num = float(num_str)
                for kpi_name, kpi_val in kpis.items():
                    if isinstance(kpi_val, (int, float)):
                        if abs(num - kpi_val) < 1.0:  # Match within 1.0 tolerance
                            return LightweightResult(statement, EntailmentLabel.ENTAILMENT, 0.85,
                                f"Value {num} matches {kpi_name}={kpi_val:.2f}")
            except ValueError:
                continue
        
        # Default: neutral (not verifiable with rules)
        return LightweightResult(statement, EntailmentLabel.NEUTRAL, 0.5, 
            "Could not verify against KPIs with rules")
    
    def _get_kpi(self, kpis: Dict[str, Any], keys: List[str]) -> Any:
        """Get first available KPI value from list of possible keys."""
        for key in keys:
            if key in kpis and kpis[key] is not None:
                return kpis[key]
        return None
    
    def _format_kpis(self, kpis: Dict[str, Any]) -> str:
        """Format KPIs for LLM prompt."""
        lines = []
        for k, v in kpis.items():
            if v is not None:
                lines.append(f"- {k}: {v}")
        return "\n".join(lines)
    
    def batch_validate(
        self,
        kpis: Dict[str, Any],
        statements: List[str]
    ) -> List[LightweightResult]:
        """Validate multiple statements."""
        return [self.validate_statement(kpis, s) for s in statements]


# Make it compatible with TNLIModel interface
class TNLIModel:
    """
    Wrapper that uses lightweight validation (no model download).
    """
    
    def __init__(self, config=None):
        self.validator = LightweightValidator(use_llm=True)
        logger.info("Using lightweight TNLI (no model download required)")
    
    def validate_statement(self, table_data: Dict[str, Any], statement: str):
        return self.validator.validate_statement(table_data, statement)
    
    def batch_validate(self, table_data: Dict[str, Any], statements: List[str]):
        return self.validator.batch_validate(table_data, statements)
