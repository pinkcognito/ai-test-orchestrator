"""Tests for the ScenarioRunner."""

from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from ai_test_orchestrator.invariant_checker import InvariantChecker
from ai_test_orchestrator.invariants.base import BaseInvariantCheck
from ai_test_orchestrator.models import Severity, Verdict
from ai_test_orchestrator.runner import ScenarioRunner, load_scenario


class StubSUT:
    """Minimal SUT adapter for testing."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = {"location": "test", "turn": 0}
        self._setup_called = False
        self._teardown_called = False

    def setup(self, config: dict[str, Any]) -> None:
        self._setup_called = True
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
        self._teardown_called = True


class TestLoadScenario:
    def test_loads_yaml(self) -> None:
        data = {
            "name": "Test Scenario",
            "system": "gurps4e",
            "seed": 42,
            "max_turns": 10,
            "actions": [
                {"input": "look around", "tags": ["exploration"]},
                {"input": "attack goblin", "tags": ["combat"]},
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            path = f.name
        try:
            scenario = load_scenario(path)
            assert scenario.name == "Test Scenario"
            assert scenario.system == "gurps4e"
            assert scenario.seed == 42
            assert len(scenario.actions) == 2
            assert scenario.actions[0].tags == ["exploration"]
        finally:
            Path(path).unlink(missing_ok=True)


class TestLoadScenarioValidation:
    def test_non_dict_yaml_raises(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("- just\n- a\n- list\n")
            path = f.name
        try:
            with pytest.raises(ValueError, match="YAML mapping"):
                load_scenario(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_action_missing_input_raises(self) -> None:
        data = {"name": "bad", "actions": [{"tags": ["oops"]}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="non-empty 'input'"):
                load_scenario(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_invalid_max_turns_raises(self) -> None:
        data = {"name": "bad", "max_turns": -5, "actions": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="positive integer"):
                load_scenario(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_empty_name_raises(self) -> None:
        data = {"name": "", "actions": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="non-empty string"):
                load_scenario(path)
        finally:
            Path(path).unlink(missing_ok=True)


class TestScenarioRunner:
    def _make_scenario_file(self, actions: list[str], **kwargs: Any) -> str:
        data = {
            "name": "integration_test",
            "system": "test",
            "seed": 1,
            "actions": [{"input": a} for a in actions],
            **kwargs,
        }
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(data, f)
        f.close()
        return f.name

    def test_runs_all_actions(self) -> None:
        path = self._make_scenario_file(["a", "b", "c"])
        try:
            scenario = load_scenario(path)
            sut = StubSUT()
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, transcript_dir=d)
                report = runner.run()
            assert report.turns_executed == 3
            assert report.scenario == "integration_test"
            assert sut._setup_called
            assert sut._teardown_called
        finally:
            Path(path).unlink(missing_ok=True)

    def test_verdict_pass_when_no_checks(self) -> None:
        path = self._make_scenario_file(["look"])
        try:
            scenario = load_scenario(path)
            sut = StubSUT()
            checker = InvariantChecker(checks=[])
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, checker=checker, transcript_dir=d)
                report = runner.run()
            assert report.verdict == Verdict.PASS
        finally:
            Path(path).unlink(missing_ok=True)

    def test_verdict_fail_on_error_check(self) -> None:
        class FailCheck(BaseInvariantCheck):
            _name = "always_fail"
            _severity = Severity.ERROR

            def _check(self, tr, ws, h):
                return self._fail(tr, "nope")

        path = self._make_scenario_file(["a"])
        try:
            scenario = load_scenario(path)
            sut = StubSUT()
            checker = InvariantChecker(checks=[FailCheck()])
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, checker=checker, transcript_dir=d)
                report = runner.run()
            assert report.verdict == Verdict.FAIL
        finally:
            Path(path).unlink(missing_ok=True)

    def test_transcript_has_metadata_and_turns(self) -> None:
        path = self._make_scenario_file(["x", "y"])
        try:
            scenario = load_scenario(path)
            sut = StubSUT()
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, transcript_dir=d)
                report = runner.run()
                assert Path(report.transcript_path).exists()
                lines = Path(report.transcript_path).read_text().strip().split("\n")
                assert len(lines) == 3  # 1 metadata + 2 turns
                meta = json.loads(lines[0])
                assert meta["type"] == "metadata"
                assert meta["seed"] == 1
        finally:
            Path(path).unlink(missing_ok=True)

    def test_max_turns_respected(self) -> None:
        data = {
            "name": "long",
            "max_turns": 2,
            "actions": [{"input": a} for a in ["a", "b", "c", "d", "e"]],
        }
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(data, f)
        f.close()
        try:
            scenario = load_scenario(f.name)
            sut = StubSUT()
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, transcript_dir=d)
                report = runner.run()
            assert report.turns_executed == 2
        finally:
            Path(f.name).unlink(missing_ok=True)

    def test_rng_seeded_deterministically(self) -> None:
        path = self._make_scenario_file(["a"], seed=42)
        try:
            scenario = load_scenario(path)
            sut = StubSUT()
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, transcript_dir=d)
                runner.run()
                val1 = random.random()

            # Run again with same seed — should produce same random value
            scenario2 = load_scenario(path)
            sut2 = StubSUT()
            with tempfile.TemporaryDirectory() as d:
                runner2 = ScenarioRunner(sut=sut2, scenario=scenario2, transcript_dir=d)
                runner2.run()
                val2 = random.random()

            assert val1 == val2
        finally:
            Path(path).unlink(missing_ok=True)

    def test_check_results_exposed(self) -> None:
        class PassCheck(BaseInvariantCheck):
            _name = "pass_check"
            _severity = Severity.ERROR

            def _check(self, tr, ws, h):
                return self._pass(tr)

        path = self._make_scenario_file(["a", "b"])
        try:
            scenario = load_scenario(path)
            sut = StubSUT()
            checker = InvariantChecker(checks=[PassCheck()])
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, checker=checker, transcript_dir=d)
                runner.run()
                assert len(runner.check_results) == 2
                assert all(r.passed for r in runner.check_results)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_framework_version_in_report(self) -> None:
        path = self._make_scenario_file(["a"])
        try:
            scenario = load_scenario(path)
            sut = StubSUT()
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, transcript_dir=d)
                report = runner.run()
                assert report.framework_version == "0.1.0"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_path_traversal_sanitized(self) -> None:
        data = {
            "name": "../../etc/evil",
            "system": "test",
            "seed": 1,
            "actions": [{"input": "a"}],
        }
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(data, f)
        f.close()
        try:
            scenario = load_scenario(f.name)
            sut = StubSUT()
            with tempfile.TemporaryDirectory() as d:
                runner = ScenarioRunner(sut=sut, scenario=scenario, transcript_dir=d)
                report = runner.run()
                # Transcript should be inside the transcript dir, not escaped
                assert Path(report.transcript_path).parent == Path(d)
                assert ".." not in Path(report.transcript_path).name
        finally:
            Path(f.name).unlink(missing_ok=True)
