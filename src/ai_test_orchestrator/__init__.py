"""AI Test Orchestrator — reusable AI-driven end-to-end testing framework."""

from __future__ import annotations

from ._version import __version__
from .invariant_checker import InvariantChecker
from .invariants.base import BaseInvariantCheck, InvariantCheck
from .models import (
    ActionStep,
    CheckResult,
    CriticalFailureError,
    NarrativeScore,
    ScenarioConfig,
    Severity,
    SUTAdapter,
    TurnResult,
    Verdict,
)
from .narrative_judge import NarrativeJudge
from .player_agent import PlayerAgent
from .report import TestReport, console_summary, write_transcript
from .runner import ScenarioRunner, load_scenario

__all__ = [
    "__version__",
    "ActionStep",
    "BaseInvariantCheck",
    "CheckResult",
    "CriticalFailureError",
    "InvariantCheck",
    "InvariantChecker",
    "NarrativeJudge",
    "NarrativeScore",
    "PlayerAgent",
    "ScenarioConfig",
    "ScenarioRunner",
    "Severity",
    "SUTAdapter",
    "TestReport",
    "TurnResult",
    "Verdict",
    "console_summary",
    "load_scenario",
    "write_transcript",
]
