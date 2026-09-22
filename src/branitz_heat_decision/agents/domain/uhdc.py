"""UHDC (report) domain agent (Layer 2.5).

Split out of the former monolithic ``agents/domain_agents.py``.
"""

import time
import logging
from typing import Dict, Any, Optional

from . import base
from .base import AgentResult, BaseDomainAgent

logger = logging.getLogger(__name__)


class UHDCAgent(BaseDomainAgent):
    """
    Plating Chef: Report Generation Specialist.
    Handles: Final report assembly, HTML/Markdown/JSON output.
    """

    def can_handle(self, intent: str, context: Dict) -> bool:
        uhdc_intents = ["UHDC", "REPORT", "GENERATE_REPORT", "FINAL_OUTPUT"]
        return intent in uhdc_intents

    def execute(self, street_id: str, context: Dict = None) -> AgentResult:
        start = time.time()
        context = context or {}

        # Check prerequisites
        decision_ready = self._check_decision_exists(street_id)
        if not decision_ready:
            return AgentResult(
                success=False,
                data={},
                execution_time=0,
                cache_hit=False,
                agent_name=self.agent_name,
                metadata={},
                errors=["Decision results required before UHDC report"],
            )

        # Delegate to ADK UHDCAgent
        adk = base._get_adk_agents()
        adk_agent = adk["UHDC"](cluster_id=street_id, verbose=True)
        action = adk_agent.run(
            llm=context.get("llm", True),
            style=context.get("style", "executive"),
            format=context.get("format", "all"),
        )

        result = action.result or {}
        execution_time = time.time() - start

        return AgentResult(
            success=action.status == "success",
            data={
                "tool_result": result,
                "outputs": result.get("outputs", {}),
                "report_paths": {
                    "html": result.get("outputs", {}).get("html"),
                    "markdown": result.get("outputs", {}).get("markdown"),
                    "json": result.get("outputs", {}).get("json"),
                },
            },
            execution_time=execution_time,
            cache_hit=False,
            agent_name=self.agent_name,
            metadata={
                "formats_generated": list(result.get("outputs", {}).keys()),
                "all_outputs_exist": all(result.get("outputs", {}).values()),
                "adk_timestamp": action.timestamp,
            },
            errors=[action.error] if action.error else [],
        )

    def _check_decision_exists(self, street_id: str) -> bool:
        from branitz_heat_decision.config import resolve_cluster_path
        return (resolve_cluster_path(street_id, "decision") / f"decision_{street_id}.json").exists()
