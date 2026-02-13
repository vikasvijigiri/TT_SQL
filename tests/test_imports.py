import sys
import os

# Add src to path
# Add src to path
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, '../src'))

try:
    from tt_sql.core.agent_base import BaseAgent
    from tt_sql.agents.critic_layer import CriticAgent
    from tt_sql.agents.generation_layer import MultiCandidateGeneratorAgent
    from tt_sql.agents.loop_layer import RefinementLoopAgent
    import json
    
    print("Imports successful.")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
