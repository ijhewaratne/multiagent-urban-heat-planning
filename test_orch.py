import sys
import os

sys.path.insert(0, "src")
from branitz_heat_decision.ui.env import bootstrap_env
bootstrap_env()

try:
    from branitz_heat_decision.agents import BranitzOrchestrator
    # We may need an API key if not in env
    api_key = os.getenv("GOOGLE_API_KEY", "")
    orch = BranitzOrchestrator(api_key=api_key)
    print("Orchestrator initialized successfully.")
    
    print("Testing route_request...")
    res = orch.route_request("Compare CO2 emissions", "ST001_AN_DEN_WEINBERGEN", {"available_streets": ["ST001_AN_DEN_WEINBERGEN"]})
    print("SUCCESS")
    print(res)
except Exception as e:
    import traceback
    traceback.print_exc()
