"""Unit tests for QuestionAnalyzerAgent."""
import pytest


def test_agent_importable():
    from agent.app.agents.question_analyzer import QuestionAnalyzerAgent
    assert QuestionAnalyzerAgent is not None


def test_contract_instantiation():
    from agent.app.agents.question_analyzer.contract import QuestionAnalyzerOutput
    out = QuestionAnalyzerOutput(confidence=0.95)
    assert 0 <= out.confidence <= 1
