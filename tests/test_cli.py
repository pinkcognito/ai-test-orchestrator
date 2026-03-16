"""Tests for the CLI entry point."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from ai_test_orchestrator.cli import _import_adapter, _import_invariants, main


class StubSUT:
    """Minimal SUT adapter for CLI testing."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = {"location": "test", "turn": 0}

    def setup(self, config: dict[str, Any]) -> None:
        self._state["system"] = config.get("system", "test")

    def process_turn(self, action: str) -> dict[str, Any]:
        self._state["turn"] = self._state.get("turn", 0) + 1
        return {
            "narrative": f"You said: {action}",
            "state_update": {"action_processed": action},
        }

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def teardown(self) -> None:
        pass


class TestImportAdapter:
    def test_valid_spec(self) -> None:
        cls = _import_adapter("tests.test_cli:StubSUT")
        assert cls is StubSUT

    def test_missing_colon_raises(self) -> None:
        with pytest.raises(ValueError, match="must be"):
            _import_adapter("tests.test_cli.StubSUT")

    def test_bad_module_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            _import_adapter("nonexistent.module:Foo")


class TestImportInvariants:
    def test_module_without_get_checks(self) -> None:
        checks = _import_invariants("tests.test_cli")
        assert checks == []


class TestMainCLI:
    def _make_scenario(self, actions: list[str], **kwargs: Any) -> str:
        data = {
            "name": "cli_test",
            "system": "test",
            "seed": 1,
            "actions": [{"input": a} for a in actions],
            **kwargs,
        }
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(data, f)
        f.close()
        return f.name

    def test_basic_run_pass(self) -> None:
        path = self._make_scenario(["look", "go north"])
        try:
            with tempfile.TemporaryDirectory() as d:
                exit_code = main(
                    [
                        "--scenario",
                        path,
                        "--adapter",
                        "tests.test_cli:StubSUT",
                        "--output-dir",
                        d,
                    ]
                )
            assert exit_code == 0
        finally:
            Path(path).unlink(missing_ok=True)

    def test_json_report_written(self) -> None:
        path = self._make_scenario(["look"])
        try:
            with tempfile.TemporaryDirectory() as d:
                report_path = str(Path(d) / "report.json")
                exit_code = main(
                    [
                        "--scenario",
                        path,
                        "--adapter",
                        "tests.test_cli:StubSUT",
                        "--output-dir",
                        d,
                        "--json-report",
                        report_path,
                    ]
                )
                assert exit_code == 0
                data = json.loads(Path(report_path).read_text())
                assert isinstance(data, list)
                assert data[0]["scenario"] == "cli_test"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_multiple_scenarios(self) -> None:
        path1 = self._make_scenario(["a"])
        path2 = self._make_scenario(["b"])
        try:
            with tempfile.TemporaryDirectory() as d:
                report_path = str(Path(d) / "report.json")
                exit_code = main(
                    [
                        "--scenario",
                        path1,
                        path2,
                        "--adapter",
                        "tests.test_cli:StubSUT",
                        "--output-dir",
                        d,
                        "--json-report",
                        report_path,
                    ]
                )
                assert exit_code == 0
                data = json.loads(Path(report_path).read_text())
                assert len(data) == 2
        finally:
            Path(path1).unlink(missing_ok=True)
            Path(path2).unlink(missing_ok=True)

    def test_seed_override(self) -> None:
        path = self._make_scenario(["a"])
        try:
            with tempfile.TemporaryDirectory() as d:
                report_path = str(Path(d) / "report.json")
                exit_code = main(
                    [
                        "--scenario",
                        path,
                        "--adapter",
                        "tests.test_cli:StubSUT",
                        "--output-dir",
                        d,
                        "--seed",
                        "999",
                        "--json-report",
                        report_path,
                    ]
                )
                assert exit_code == 0
                data = json.loads(Path(report_path).read_text())
                assert data[0]["seed"] == 999
        finally:
            Path(path).unlink(missing_ok=True)

    def test_verbose_flag(self) -> None:
        path = self._make_scenario(["a"])
        try:
            with tempfile.TemporaryDirectory() as d:
                exit_code = main(
                    [
                        "--scenario",
                        path,
                        "--adapter",
                        "tests.test_cli:StubSUT",
                        "--output-dir",
                        d,
                        "-v",
                    ]
                )
                assert exit_code == 0
        finally:
            Path(path).unlink(missing_ok=True)

    def test_fail_fast_flag(self) -> None:
        path = self._make_scenario(["a"])
        try:
            with tempfile.TemporaryDirectory() as d:
                exit_code = main(
                    [
                        "--scenario",
                        path,
                        "--adapter",
                        "tests.test_cli:StubSUT",
                        "--output-dir",
                        d,
                        "--fail-fast",
                    ]
                )
                assert exit_code == 0
        finally:
            Path(path).unlink(missing_ok=True)
