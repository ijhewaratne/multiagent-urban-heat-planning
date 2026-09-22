"""
ADK (Agent Development Kit) Module

Minimal-intrusion agent orchestration layer for Branitz Heat Decision pipeline.
Wraps existing modules without modifying them.
"""

from .agent import (
    BranitzADKAgent,
    BranitzADKTeam,
    BaseADKAgent,
    ADKDataPrepAgent,
    ADKCHAAgent,
    ADKDHAAgent,
    ADKEconomicsAgent,
    ADKDecisionAgent,
    ADKUHDCAgent,
)

# Deprecated aliases (pre-rename). The domain-level agents in
# branitz_heat_decision.agents.domain_agents use the un-prefixed names;
# ADK tool-level agents are now prefixed with "ADK" to avoid the clash.
DataPrepAgent = ADKDataPrepAgent
CHAAgent = ADKCHAAgent
DHAAgent = ADKDHAAgent
EconomicsAgent = ADKEconomicsAgent
DecisionAgent = ADKDecisionAgent
UHDCAgent = ADKUHDCAgent
from .tools import (
    prepare_data_tool,
    run_cha_tool,
    run_dha_tool,
    run_economics_tool,
    run_decision_tool,
    run_uhdc_tool,
    get_available_tools,
)
from .policies import (
    validate_agent_action,
    enforce_guardrails,
    PolicyViolation,
)
from .evals import (
    validate_trajectory,
    validate_artifacts,
    check_artifact_completeness,
)

__all__ = [
    "BranitzADKAgent",
    "BranitzADKTeam",
    "BaseADKAgent",
    "ADKDataPrepAgent",
    "ADKCHAAgent",
    "ADKDHAAgent",
    "ADKEconomicsAgent",
    "ADKDecisionAgent",
    "ADKUHDCAgent",
    # deprecated aliases
    "DataPrepAgent",
    "CHAAgent",
    "DHAAgent",
    "EconomicsAgent",
    "DecisionAgent",
    "UHDCAgent",
    "prepare_data_tool",
    "run_cha_tool",
    "run_dha_tool",
    "run_economics_tool",
    "run_decision_tool",
    "run_uhdc_tool",
    "get_available_tools",
    "validate_agent_action",
    "enforce_guardrails",
    "PolicyViolation",
    "validate_trajectory",
    "validate_artifacts",
    "check_artifact_completeness",
]
