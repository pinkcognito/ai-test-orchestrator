"""Tests for the InvariantChecker framework."""

from __future__ import annotations

import pytest

from ai_test_orchestrator.invariant_checker import InvariantChecker
from ai_test_orchestrator.invariants.base import BaseInvariantCheck
from ai_test_orchestrator.models import CriticalFailureError, Severity, TurnResult


class AlwaysPassCheck(BaseInvariantCheck):
    _name = "always_pass"
    _severity = Severity.ERROR

    def _check(self, turn_result, world_state, history):
        return self._pass(turn_result)


class AlwaysFailCheck(BaseInvariantCheck):
    _name = "always_fail"
    _severity = Severity.ERROR

    def _check(self, turn_result, world_state, history):
        return self._fail(turn_result, "Always fails")


class CriticalFailCheck(BaseInvariantCheck):
    _name = "critical_fail"
    _severity = Severity.CRITICAL

    def _check(self, turn_result, world_state, history):
        return self._fail(turn_result, "Critical failure")


class WarningCheck(BaseInvariantCheck):
    _name = "warning_check"
    _severity = Severity.WARNING

    def _check(self, turn_result, world_state, history):
        return self._fail(turn_result, "Just a warning")


def _make_turn(n: int = 1) -> TurnResult:
    return TurnResult(turn_number=n, action="test", narrative="test narrative")


class TestInvariantChecker:
    def test_all_pass(self) -> None:
        checker = InvariantChecker(checks=[AlwaysPassCheck()])
        results = checker.check_turn(_make_turn(), {}, [])
        assert len(results) == 1
        assert results[0].passed is True
        assert not checker.has_failures

    def test_error_failure_collected(self) -> None:
        checker = InvariantChecker(checks=[AlwaysPassCheck(), AlwaysFailCheck()])
        checker.check_turn(_make_turn(), {}, [])
        assert checker.has_failures is True
        assert not checker.has_critical_failure

    def test_critical_failure_detected(self) -> None:
        checker = InvariantChecker(checks=[CriticalFailCheck()])
        checker.check_turn(_make_turn(), {}, [])
        assert checker.has_critical_failure is True

    def test_fail_fast_raises_critical_failure(self) -> None:
        checker = InvariantChecker(checks=[CriticalFailCheck()], fail_fast=True)
        with pytest.raises(CriticalFailureError, match="Critical failure"):
            checker.check_turn(_make_turn(), {}, [])

    def test_fail_fast_does_not_trigger_on_error(self) -> None:
        checker = InvariantChecker(checks=[AlwaysFailCheck()], fail_fast=True)
        # Should not raise — fail_fast only triggers on CRITICAL
        checker.check_turn(_make_turn(), {}, [])
        assert checker.has_failures

    def test_summary_structure(self) -> None:
        checker = InvariantChecker(checks=[AlwaysPassCheck(), AlwaysFailCheck(), WarningCheck()])
        checker.check_turn(_make_turn(1), {}, [])
        checker.check_turn(_make_turn(2), {}, [])
        summary = checker.summary()
        assert "critical" in summary
        assert "error" in summary
        assert "warning" in summary
        assert summary["error"]["passed"] == 2
        assert summary["error"]["failed"] == 2
        assert summary["warning"]["failed"] == 2

    def test_reset_clears_results(self) -> None:
        checker = InvariantChecker(checks=[AlwaysFailCheck()])
        checker.check_turn(_make_turn(), {}, [])
        assert checker.has_failures
        checker.reset()
        assert not checker.has_failures
        assert checker.results == []

    def test_accumulates_across_turns(self) -> None:
        checker = InvariantChecker(checks=[AlwaysPassCheck()])
        checker.check_turn(_make_turn(1), {}, [])
        checker.check_turn(_make_turn(2), {}, [])
        checker.check_turn(_make_turn(3), {}, [])
        assert len(checker.results) == 3

    def test_check_exception_produces_critical_failure(self) -> None:
        class BrokenCheck(BaseInvariantCheck):
            _name = "broken"
            _severity = Severity.WARNING

            def _check(self, turn_result, world_state, history):
                raise ValueError("boom")

        checker = InvariantChecker(checks=[BrokenCheck()])
        results = checker.check_turn(_make_turn(), {}, [])
        assert not results[0].passed
        assert results[0].severity == Severity.CRITICAL
        assert "exception" in results[0].message
