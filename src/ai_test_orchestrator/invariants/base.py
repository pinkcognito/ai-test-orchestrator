"""
Base protocol and utilities for invariant checks.

Every invariant check implements the InvariantCheck protocol:
- name: human-readable check name
- severity: CRITICAL / ERROR / WARNING
- check(): receives turn result, world state, and history; returns CheckResult
"""

from __future__ import annotations

from typing import Any, Protocol

from ..models import CheckResult, Severity, TurnResult


class InvariantCheck(Protocol):
    """Protocol that all invariant checks must implement."""

    @property
    def name(self) -> str:
        """Human-readable name for this check."""
        ...

    @property
    def severity(self) -> Severity:
        """Severity level: CRITICAL, ERROR, or WARNING."""
        ...

    @property
    def tags(self) -> tuple[str, ...]:
        """
        Tags that determine when this check should run.

        An empty tuple means the check runs on all turns. Otherwise, the
        check only runs on turns whose tags intersect this set.
        """
        ...

    def check(
        self,
        turn_result: TurnResult,
        world_state: dict[str, Any],
        history: list[TurnResult],
    ) -> CheckResult:
        """
        Run this invariant check against a single turn.

        Args:
            turn_result: The current turn's immutable result.
            world_state: The full world state snapshot after this turn.
            history: All previous TurnResults (not including current).

        Returns:
            CheckResult with pass/fail, message, and optional diff.
        """
        ...


class BaseInvariantCheck:
    """
    Convenience base class for invariant checks.

    Subclasses override `_check()` and set `_name` and `_severity`.
    """

    _name: str = "unnamed_check"
    _severity: Severity = Severity.ERROR
    _tags: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self._name

    @property
    def severity(self) -> Severity:
        return self._severity

    @property
    def tags(self) -> tuple[str, ...]:
        return self._tags

    def check(
        self,
        turn_result: TurnResult,
        world_state: dict[str, Any],
        history: list[TurnResult],
    ) -> CheckResult:
        return self._check(turn_result, world_state, history)

    def _check(
        self,
        turn_result: TurnResult,
        world_state: dict[str, Any],
        history: list[TurnResult],
    ) -> CheckResult:
        """Override this method in subclasses."""
        return CheckResult(
            check_name=self.name,
            passed=True,
            severity=self.severity,
            turn_number=turn_result.turn_number,
        )

    def _pass(self, turn: TurnResult, message: str = "") -> CheckResult:
        """Helper: create a passing CheckResult."""
        return CheckResult(
            check_name=self.name,
            passed=True,
            severity=self.severity,
            message=message,
            turn_number=turn.turn_number,
        )

    def _fail(self, turn: TurnResult, message: str, diff: dict[str, Any] | None = None) -> CheckResult:
        """Helper: create a failing CheckResult."""
        return CheckResult(
            check_name=self.name,
            passed=False,
            severity=self.severity,
            message=message,
            turn_number=turn.turn_number,
            diff=diff,
        )
