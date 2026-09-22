"""
Domain-Specific Assistant Agents (Layer 2.5) — one module per agent.

Public API is identical to the former monolithic ``agents/domain_agents.py``.
"""

from .base import AgentResult, BaseDomainAgent, _get_adk_agents
from .data_prep import DataPrepAgent
from .cha import CHAAgent
from .dha import DHAAgent
from .economics import EconomicsAgent
from .decision import DecisionAgent
from .validation import ValidationAgent
from .uhdc import UHDCAgent
from .what_if import WhatIfAgent
from .registry import AGENT_REGISTRY, get_agent

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
