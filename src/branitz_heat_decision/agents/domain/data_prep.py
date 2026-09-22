"""DataPrep domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

logger = logging.getLogger(__name__)


class DataPrepAgent(BaseDomainAgent):
    """
    Prep Chef: Prepares raw data, creates clusters, generates profiles.
    Handles: Data loading, OSM extraction, building clustering.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        return intent in ["DATA_PREPARATION", "PREPARE_DATA", "LOAD_DATA"]

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check if data already prepared
        if self._is_data_prepared(street_id):
            logger.info(f"[{self.agent_name}] Data already prepared for {street_id}")
            return AgentResult(
                success=True,
                data={"status": "already_prepared", "street_id": street_id},
                execution_time=time.time() - start,
                cache_hit=True,
                agent_name=self.agent_name,
                metadata={"preparation_status": "cached"},
            )

        # Delegate to ADK DataPrepAgent
        adk = base._get_adk_agents()
        adk_agent = adk["DataPrep"](verbose=True)
        action = adk_agent.run(
            buildings_path=context.get("buildings_path"),
            streets_path=context.get("streets_path"),
        )

        result = action.result or {}
        execution_time = time.time() - start

        return AgentResult(
            success=action.status == "success",
            data=result,
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "outputs_created": result.get("outputs", {}),
                "preparation_status": "completed",
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _is_data_prepared(self, street_id: str) -> bool:
        from branitz_heat_decision.config import (
            BUILDINGS_PATH,
            BUILDING_CLUSTER_MAP_PATH,
            HOURLY_PROFILES_PATH,
        )
        return all([
            BUILDINGS_PATH.exists(),
            BUILDING_CLUSTER_MAP_PATH.exists(),
            HOURLY_PROFILES_PATH.exists(),
        ])
