"""BIRD benchmark smoke test (1 question)."""
import pytest


@pytest.mark.benchmark
def test_bird_smoke():
    pytest.skip('Benchmark requires live DB connection - run manually')
