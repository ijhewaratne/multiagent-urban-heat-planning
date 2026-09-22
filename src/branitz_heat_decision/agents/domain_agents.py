"""
Backward-compatibility shim.

The domain agents were split into one module per agent under
``branitz_heat_decision.agents.domain``.  Import from there going forward:

    from branitz_heat_decision.agents.domain import CHAAgent

This module re-exports the full public API so existing imports keep working.
"""

from branitz_heat_decision.agents.domain import (  # noqa: F401
    AGENT_REGISTRY,
    AgentResult,
    BaseDomainAgent,
    CHAAgent,
    DHAAgent,
    DataPrepAgent,
    DecisionAgent,
    EconomicsAgent,
    UHDCAgent,
    ValidationAgent,
    WhatIfAgent,
    _get_adk_agents,
    get_agent,
)

__all__ = [
    "AgentResult",
    "BaseDomainAgent",
    "DataPrepAgent",
    "CHAAgent",
    "DHAAgent",
    "EconomicsAgent",
    "DecisionAgent",
    "ValidationAgent",
    "UHDCAgent",
    "WhatIfAgent",
    "AGENT_REGISTRY",
    "get_agent",
]
