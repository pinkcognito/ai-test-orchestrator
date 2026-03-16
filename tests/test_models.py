"""Tests for core data models."""

from __future__ import annotations

from ai_test_orchestrator.models import (
    ActionStep,
    CheckResult,
    NarrativeScore,
    ScenarioConfig,
    Severity,
    TurnResult,
    Verdict,
)


class TestSeverity:
    def test_values(self) -> None:
        assert Severity.CRITICAL == "critical"
        assert Severity.ERROR == "error"
        assert Severity.WARNING == "warning"


class TestVerdict:
    def test_values(self) -> None:
        assert Verdict.PASS == "pass"
        assert Verdict.PASS_WITH_WARNINGS == "pass_with_warnings"
        assert Verdict.FAIL == "fail"


class TestTurnResult:
    def test_frozen(self) -> None:
        t = TurnResult(turn_number=1, action="look", narrative="You see a room.")
        assert t.turn_number == 1
        assert t.narrative == "You see a room."

    def test_defaults(self) -> None:
        t = TurnResult(turn_number=1, action="x", narrative="y")
        assert t.state_update == {}
        assert t.world_state_snapshot == {}
        assert t.tags == ()
        assert t.extra == {}

    def test_tags_are_tuple(self) -> None:
        t = TurnResult(turn_number=1, action="x", narrative="y", tags=("a", "b"))
        assert isinstance(t.tags, tuple)


class TestCheckResult:
    def test_pass(self) -> None:
        r = CheckResult(check_name="test", passed=True, severity=Severity.ERROR, turn_number=3)
        assert r.passed is True
        assert r.turn_number == 3

    def test_fail_with_message(self) -> None:
        r = CheckResult(
            check_name="hp_bounds", passed=False, severity=Severity.CRITICAL, message="HP > max", turn_number=2
        )
        assert r.passed is False
        assert "HP" in r.message


class TestNarrativeScore:
    def test_overall_weighted(self) -> None:
        s = NarrativeScore(
            tone_consistency=4.0,
            action_acknowledgment=4.0,
            immersion=4.0,
            mechanical_accuracy=4.0,
            continuity=4.0,
        )
        assert abs(s.overall - 4.0) < 0.01

    def test_zero_defaults(self) -> None:
        s = NarrativeScore()
        assert s.overall == 0.0


class TestScenarioConfig:
    def test_defaults(self) -> None:
        s = ScenarioConfig(name="test")
        assert s.system == "gurps4e"
        assert s.max_turns == 50
        assert s.actions == []
        assert s.fail_fast is False

    def test_with_actions(self) -> None:
        s = ScenarioConfig(
            name="combat",
            actions=[ActionStep(input="attack goblin", tags=["combat"])],
        )
        assert len(s.actions) == 1
        assert s.actions[0].tags == ["combat"]
