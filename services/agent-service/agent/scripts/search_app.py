import sys
import json
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.services.llm import LLMClient

llm = LLMClient()

title = "The Rundown"
desc_cleaned = "4 Miami at N.C. State 7:45 p.m., ESPN Think the Wolfpack is kicking itself for that loss two weeks ago at North Carolina? You bet. Had N.C. State (4-2, 3-1 ACC) won that one, this would be for sole possession of first place in the ACC. As it is, this is a chance for the Wolfpack to show it belongs in the upper echelon of the restructured league -- which, for now, is Miami, Florida State, and a cesspool of also-rans. The Wolfpack's defense is the best in the nation against the pass (97.5 yards per game) and overall (203.7). It will have to shut down a rejuvenated Brock Berlin, who threw for 308 yards last week against Louisville, his most in 13 games. Key for N.C. State: Will perpetually banged-up tailback T.A. McLendon -- a game-time decision because of a bad hamstring -- be able to run effectively?"

items = [{"id": 39, "text": {"title": title, "description": desc_cleaned}}]

user_prompt_template = """Allowed categories: sports, non-sports

Classification instruction: Classify each article as sports or non-sports based on its title and description.

Items to classify:
{items_json}"""

# System prompt with strict constraint
sys_strict = """You are a precise text classifier.

For each item in the list below, assign exactly one category from the allowed list.
Base your decision solely on the text content provided -- no assumptions, no external knowledge.

Respond ONLY with a JSON array of objects, one per input item, in the same order:
[
  {"id": <row_id>, "category": "<chosen category>"},
  ...
]"""

# System prompt with general knowledge allowed
sys_knowledge = """You are a precise text classifier.

For each item in the list below, assign exactly one category from the allowed list.
Use your general knowledge of categories and entities to classify the items accurately.

Respond ONLY with a JSON array of objects, one per input item, in the same order:
[
  {"id": <row_id>, "category": "<chosen category>"},
  ...
]"""

res_strict = llm.generate(
    system_prompt=sys_strict,
    user_prompt=user_prompt_template.format(items_json=json.dumps(items)),
)
print("--- Strict Prompt Output ---")
print(res_strict.strip())

res_knowledge = llm.generate(
    system_prompt=sys_knowledge,
    user_prompt=user_prompt_template.format(items_json=json.dumps(items)),
)
print("\n--- General Knowledge Prompt Output ---")
print(res_knowledge.strip())
