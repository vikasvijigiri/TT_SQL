"""Unit tests for ForensicReporter."""
import pytest
from pathlib import Path


def test_reporter_creates_run_dir(tmp_path, monkeypatch):
    import core.telemetry.forensic_reporter as fr
    monkeypatch.setattr(fr, 'ROOT_DATA', tmp_path)
    from core.telemetry.forensic_reporter import ForensicReporter
    reporter = ForensicReporter(run_id='run_test_001')
    reporter.write_all(blackboard=None, telemetry={}, result={}, final_sql='SELECT 1')
    assert (reporter.run_dir / 'forensic_report.md').exists()
    assert (reporter.run_dir / 'final.sql').exists()
    assert (reporter.run_dir / 'telemetry.json').exists()
