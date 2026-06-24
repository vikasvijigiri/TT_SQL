# Meta Learner Agent

## Single Responsibility
Analyzes cross-run history. Generates permanent rules. Evolves agent prompts.

## Files

| File | Role |
|:---|:---|
| `agent.py` | Core agent logic |
| `contract.py` | Pydantic input/output contracts |
| `prompt.yaml` | Agent-specific LLM system prompt |
| `validator.py` | Output validation gate |
| `README.md` | This file |

## Validator Strategy
**No gate (pure retrieval/formatting)**

## Input Contract
`MetaLearnerAgentInput` -- see `contract.py`

## Output Contract
`MetaLearnerOutput` -- see `contract.py`

## Architectural Rules
- This agent has **exactly one** responsibility.
- It reads from and writes to the **Blackboard**.
- Its output is **always validated** before the next agent runs.
- It contains **no benchmark-specific logic**.
- It contains **no hardcoded schemas or answers**.
