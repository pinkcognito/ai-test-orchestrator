"""Tests for TestReport and report utilities."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ai_test_orchestrator.models import TurnResult, Verdict
from ai_test_orchestrator.report import TestReport, console_summary, write_transcript


class TestTestReport:
    def test_compute_verdict_pass(self) -> None:
        summary = {
            "critical": {"passed": 5, "failed": 0},
            "error": {"passed": 10, "failed": 0},
            "warning": {"passed": 3, "failed": 0},
        }
        assert TestReport.compute_verdict(summary) == Verdict.PASS

    def test_compute_verdict_warnings(self) -> None:
        summary = {
            "critical": {"passed": 5, "failed": 0},
            "error": {"passed": 10, "failed": 0},
            "warning": {"passed": 3, "failed": 2},
        }
        assert TestReport.compute_verdict(summary) == Verdict.PASS_WITH_WARNINGS

    def test_compute_verdict_fail_error(self) -> None:
        summary = {
            "critical": {"passed": 5, "failed": 0},
            "error": {"passed": 8, "failed": 2},
            "warning": {"passed": 3, "failed": 0},
        }
        assert TestReport.compute_verdict(summary) == Verdict.FAIL

    def test_compute_verdict_fail_critical(self) -> None:
        summary = {
            "critical": {"passed": 4, "failed": 1},
            "error": {"passed": 10, "failed": 0},
            "warning": {"passed": 3, "failed": 0},
        }
        assert TestReport.compute_verdict(summary) == Verdict.FAIL

    def test_to_json(self) -> None:
        r = TestReport(scenario="test", system="gurps4e", seed=42, turns_executed=5, duration_seconds=1.5)
        j = json.loads(r.to_json())
        assert j["scenario"] == "test"
        assert j["verdict"] == "pass"

    def test_save_and_load(self) -> None:
        r = TestReport(scenario="test", system="d20", seed=None, turns_executed=3, duration_seconds=0.5)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            r.save(path)
            data = json.loads(Path(path).read_text())
            assert data["system"] == "d20"
        finally:
            Path(path).unlink(missing_ok=True)


class TestWriteTranscript:
    def test_writes_jsonl(self) -> None:
        turns = [
            TurnResult(turn_number=1, action="look", narrative="A room."),
            TurnResult(turn_number=2, action="go north", narrative="A hallway."),
        ]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "transcript.jsonl"
            write_transcript(turns, path)
            lines = path.read_text().strip().split("\n")
            assert len(lines) == 2
            assert json.loads(lines[0])["action"] == "look"
            assert json.loads(lines[1])["turn_number"] == 2


class TestConsoleSummary:
    def test_contains_scenario_info(self) -> None:
        r = TestReport(
            scenario="tavern",
            system="gurps4e",
            seed=42,
            turns_executed=10,
            duration_seconds=2.5,
            invariant_results={
                "critical": {"passed": 10, "failed": 0, "failures": []},
                "error": {
                    "passed": 20,
                    "failed": 1,
                    "failures": [{"check": "no_raw_numbers", "turn": 7, "message": "Found '14'"}],
                },
                "warning": {"passed": 5, "failed": 0, "failures": []},
            },
            verdict=Verdict.FAIL,
        )
        summary = console_summary(r)
        assert "tavern" in summary
        assert "gurps4e" in summary
        assert "42" in summary
        assert "FAIL" in summary
        assert "Found '14'" in summary
