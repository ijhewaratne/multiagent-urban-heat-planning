import hashlib
import json
import logging
from pathlib import Path

from branitz_heat_decision.agents.domain_agents import EconomicsAgent, DecisionAgent

logging.basicConfig(level=logging.WARNING)

def test_consistency():
    street_id = "ST010_HEINRICH_ZILLE_STRASSE"
    runs = 10
    hashes = set()
    
    print(f"Executing deterministic validation runs for {runs} iterations...")
    
    for i in range(runs):
        context = {
            "force_recalc": True,  # Force native pipeline execution instead of hitting cache
            "n_samples": 500,
            "seed": 42,
            "llm_explanation": False,
        }
        
        # Run Economics explicitly 
        econ_agent = EconomicsAgent()
        econ_res = econ_agent.execute(street_id, context=context)
        if not econ_res.success:
            raise RuntimeError(f"Economics run {i+1} failed: {econ_res.errors}")
            
        # Run Decision
        dec_agent = DecisionAgent()
        dec_res = dec_agent.execute(street_id, context=context)
        if not dec_res.success:
            raise RuntimeError(f"Decision run {i+1} failed: {dec_res.errors}")
            
        # Obtain canonical JSON of decision data
        decision_data = dec_res.data.get("decision", {})
        canonical = json.dumps(decision_data, sort_keys=True)
        current_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        
        hashes.add(current_hash)
        print(f"Run {i+1} hash completed: {current_hash}")
        
    assert len(hashes) == 1, f"Determinism failed! Multiple distinct hashes generated: {hashes}"
    
    print(f"Validation successful. Computed hash: {list(hashes)[0]}. {runs} runs yielded identical outcomes.")
    
if __name__ == "__main__":
    test_consistency()
