"""
Invariant Checker — runs all registered checks against turn results.

Supports two modes:
- fail_fast: halt on first CRITICAL failure
- collect_all: run all checks, collect all results

Checks are pulled from the invariants registry.
"""

from __future__ import annotations

import logging
from typing import Any

from .invariants import get_all_checks
from .invariants.base import InvariantCheck
from .models import CheckResult, CriticalFailureError, Severity, TurnResult

logger = logging.getLogger(__name__)


class InvariantChecker:
    """
    Runs registered invariant checks against turn results.

    Can operate in fail-fast mode (halt on first CRITICAL) or
    collect-all mode (run everything, report at end).
    """

    def __init__(
        self,
        checks: list[InvariantCheck] | None = None,
        fail_fast: bool = False,
    ) -> None:
        self._checks = checks if checks is not None else get_all_checks()
        self._fail_fast = fail_fast
        self._results: list[CheckResult] = []

    @property
    def results(self) -> list[CheckResult]:
        """All check results collected so far."""
        return list(self._results)

    @property
    def has_failures(self) -> bool:
        """True if any check has failed."""
        return any(not r.passed for r in self._results)

    @property
    def has_critical_failure(self) -> bool:
        """True if any CRITICAL check has failed."""
        return any(not r.passed and r.severity == Severity.CRITICAL for r in self._results)

    def check_turn(
        self,
        turn_result: TurnResult,
        world_state: dict[str, Any],
        history: list[TurnResult],
    ) -> list[CheckResult]:
        """
        Run all invariant checks against a single turn.

        Returns the list of CheckResults for this turn. Results are
        also accumulated in self.results.

        Raises CriticalFailureError if fail_fast is True and a CRITICAL check fails.
        """
        turn_results: list[CheckResult] = []

        for check in self._checks:
            try:
                result = check.check(turn_result, world_state, history)
            except Exception as e:
                logger.error("Check %s raised exception: %s", check.name, e)
                result = CheckResult(
                    check_name=check.name,
                    passed=False,
                    severity=Severity.CRITICAL,
                    message=f"Check raised exception: {e}",
                    turn_number=turn_result.turn_number,
                )

            turn_results.append(result)
            self._results.append(result)

            if not result.passed:
                logger.warning(
                    "FAIL [%s] %s (turn %d): %s",
                    result.severity.value,
                    result.check_name,
                    result.turn_number,
                    result.message,
                )

            if self._fail_fast and not result.passed and result.severity == Severity.CRITICAL:
                raise CriticalFailureError(f"Critical failure in {check.name}: {result.message}")

        return turn_results

    def summary(self) -> dict[str, dict[str, int | list[dict]]]:
        """
        Summarise all results by severity.

        Returns dict with keys 'critical', 'error', 'warning', each containing
        'passed', 'failed' counts and 'failures' list.
        """
        summary: dict[str, dict[str, Any]] = {}
        for severity in Severity:
            sev_results = [r for r in self._results if r.severity == severity]
            passed = sum(1 for r in sev_results if r.passed)
            failed_results = [r for r in sev_results if not r.passed]
            summary[severity.value] = {
                "passed": passed,
                "failed": len(failed_results),
                "failures": [
                    {
                        "check": r.check_name,
                        "turn": r.turn_number,
                        "message": r.message,
                    }
                    for r in failed_results
                ],
            }
        return summary

    def reset(self) -> None:
        """Clear all accumulated results."""
        self._results.clear()
