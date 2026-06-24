"""Prompt regression: verify prompts exist and haven't been accidentally cleared."""
import hashlib
from pathlib import Path

PROMPTS = Path(__file__).parents[2] / 'core' / 'prompts'

REQUIRED_PROMPTS = [
    'question_analyzer.yaml',
    'semantic_planner.yaml',
    'schema_linker.yaml',
    'join_planner.yaml',
    'sql_generator.yaml',
    'evidence_synthesizer.yaml',
    'final_answer.yaml',
]


def test_all_required_prompts_exist():
    missing = [p for p in REQUIRED_PROMPTS if not (PROMPTS / p).exists()]
    assert not missing, f'Missing prompts: {missing}'


def test_prompts_not_empty():
    for name in REQUIRED_PROMPTS:
        p = PROMPTS / name
        if p.exists():
            assert p.stat().st_size > 50, f'{name} looks empty'
