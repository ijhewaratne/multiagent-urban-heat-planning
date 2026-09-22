"""Domain agent registry and factory."""

from typing import Dict, Type

from .base import BaseDomainAgent
from .data_prep import DataPrepAgent
from .cha import CHAAgent
from .dha import DHAAgent
from .economics import EconomicsAgent
from .decision import DecisionAgent
from .validation import ValidationAgent
from .uhdc import UHDCAgent
from .what_if import WhatIfAgent

# Agent Registry for easy access
AGENT_REGISTRY: Dict[str, Type[BaseDomainAgent]] = {
    "data_prep": DataPrepAgent,
    "cha": CHAAgent,
    "dha": DHAAgent,
    "economics": EconomicsAgent,
    "decision": DecisionAgent,
    "validation": ValidationAgent,
    "uhdc": UHDCAgent,
    "what_if": WhatIfAgent,
}


def get_agent(agent_name: str, **kwargs) -> BaseDomainAgent:
    """Factory function to get agent instance."""
    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(AGENT_REGISTRY.keys())}")
    return AGENT_REGISTRY[agent_name](**kwargs)
