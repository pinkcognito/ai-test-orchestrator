"""
Core data models for the AI Test Orchestrator.

Defines the Protocol interfaces that any System Under Test must implement,
plus the immutable data structures for turn results, check results, and
scenario configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Severity levels for invariant checks
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    """Invariant check severity. CRITICAL fails the suite; ERROR fails the test; WARNING is logged only."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


class CriticalFailureError(Exception):
    """Raised when a CRITICAL invariant check fails in fail-fast mode."""


class Verdict(StrEnum):
    """Overall test scenario verdict."""

    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    FAIL = "fail"


# ---------------------------------------------------------------------------
# SUT adapter protocol — what the framework needs from any system under test
# ---------------------------------------------------------------------------


@runtime_checkable
class SUTAdapter(Protocol):
    """
    Protocol that any System Under Test must implement.

    The framework drives the SUT through this interface. Implementations
    wrap the actual game/application session.
    """

    def setup(self, config: dict[str, Any]) -> None:
        """Initialise the SUT with scenario configuration (PC name, location, system, etc.)."""
        ...

    def process_turn(self, action: str) -> dict[str, Any]:
        """
        Submit a player/user action and return the turn result.

        The returned dict must include at minimum:
        - "narrative": str — the generated text response
        - "state_update": dict — any structured state changes (JSON block from GM, etc.)

        Additional keys are passed through to invariant checkers.
        """
        ...

    def get_state(self) -> dict[str, Any]:
        """Return the current full state snapshot of the SUT."""
        ...

    def teardown(self) -> None:
        """Clean up resources. Called after scenario completes."""
        ...


# ---------------------------------------------------------------------------
# Turn result — immutable record of one turn
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnResult:
    """Immutable record of a single turn in a scenario execution."""

    turn_number: int
    action: str
    narrative: str
    state_update: dict[str, Any] = field(default_factory=dict)
    world_state_snapshot: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    tags: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Check result — output of an invariant check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    """Result of a single invariant check against a turn."""

    check_name: str
    passed: bool
    severity: Severity
    message: str = ""
    turn_number: int = 0
    diff: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Scenario configuration
# ---------------------------------------------------------------------------


@dataclass
class ActionStep:
    """One action in a scenario script."""

    input: str
    tags: list[str] = field(default_factory=list)
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioConfig:
    """Parsed scenario file configuration."""

    name: str
    system: str = "gurps4e"
    pc: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    max_turns: int = 50
    actions: list[ActionStep] = field(default_factory=list)
    fail_fast: bool = False
    enable_narrative_judge: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Narrative score
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NarrativeScore:
    """LLM judge score for one turn's narrative."""

    tone_consistency: float = 0.0
    action_acknowledgment: float = 0.0
    immersion: float = 0.0
    mechanical_accuracy: float = 0.0
    continuity: float = 0.0
    rationale: str = ""

    @property
    def overall(self) -> float:
        """Weighted average: tone 25%, acknowledgment 25%, immersion 20%, accuracy 20%, continuity 10%."""
        return (
            self.tone_consistency * 0.25
            + self.action_acknowledgment * 0.25
            + self.immersion * 0.20
            + self.mechanical_accuracy * 0.20
            + self.continuity * 0.10
        )
