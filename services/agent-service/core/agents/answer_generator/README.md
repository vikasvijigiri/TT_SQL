# Answer Generator Agent

## Single Responsibility
Formats the final answer. No SQL. No retrieval. Purely formats evidence into answer.

## Files

| File | Role |
|:---|:---|
| `agent.py` | Core agent logic |
| `contract.py` | Pydantic input/output contracts |
| `prompt.yaml` | Agent-specific LLM system prompt |
| `validator.py` | Output validation gate |
| `README.md` | This file |

## Validator Strategy
**Deterministic (Python / SQLGlot / Pydantic)**

## Input Contract
`FinalAnswerAgentInput` -- see `contract.py`

## Output Contract
`FinalAnswerOutput` -- see `contract.py`

## Architectural Rules
- This agent has **exactly one** responsibility.
- It reads from and writes to the **Blackboard**.
- Its output is **always validated** before the next agent runs.
- It contains **no benchmark-specific logic**.
- It contains **no hardcoded schemas or answers**.
