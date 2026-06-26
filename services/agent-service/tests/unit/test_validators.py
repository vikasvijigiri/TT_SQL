"""Unit tests for deterministic validators."""
import pytest


def test_validators_importable():
    from agent.app.core.validators.deterministic_validators import DeterministicValidators
    assert DeterministicValidators is not None
