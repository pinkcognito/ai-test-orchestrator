"""
Scenario Runner — orchestrates the test loop.

Loads a scenario config, creates a PlayerAgent, drives the SUT,
runs invariant checks per turn, optionally scores narrative quality,
and produces a TestReport.
"""

from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path
from typing import Any

import yaml

from ._version import __version__ as _framework_version
from .invariant_checker import InvariantChecker
from .models import ActionStep, CriticalFailureError, ScenarioConfig, SUTAdapter, TurnResult
from .narrative_judge import NarrativeJudge
from .player_agent import PlayerAgent
from .report import TestReport, write_transcript

logger = logging.getLogger(__name__)


def load_scenario(path: str | Path) -> ScenarioConfig:
    """Load and validate a scenario from a YAML file."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Scenario file must contain a YAML mapping, got {type(data).__name__}")

    name = data.get("name", Path(path).stem)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Scenario 'name' must be a non-empty string.")

    system = data.get("system", "gurps4e")
    if not isinstance(system, str) or not system.strip():
        raise ValueError("Scenario 'system' must be a non-empty string.")

    max_turns = data.get("max_turns", 50)
    if not isinstance(max_turns, int) or max_turns <= 0:
        raise ValueError("Scenario 'max_turns' must be a positive integer.")

    actions_raw = data.get("actions", [])
    if not isinstance(actions_raw, list):
        raise ValueError("Scenario 'actions' must be a list.")

    actions: list[ActionStep] = []
    for idx, a in enumerate(actions_raw, start=1):
        if not isinstance(a, dict):
            raise ValueError(f"Action at index {idx} must be a mapping.")
        action_input = a.get("input")
        if not isinstance(action_input, str) or not action_input.strip():
            raise ValueError(f"Action at index {idx} must have non-empty 'input' string.")
        actions.append(
            ActionStep(
                input=action_input,
                tags=a.get("tags", []),
                expect=a.get("expect", {}),
            )
        )

    return ScenarioConfig(
        name=name,
        system=system,
        pc=data.get("pc", {}),
        seed=data.get("seed"),
        max_turns=max_turns,
        actions=actions,
        fail_fast=data.get("fail_fast", False),
        enable_narrative_judge=data.get("enable_narrative_judge", False),
        extra=data.get("extra", {}),
    )


class ScenarioRunner:
    """
    Orchestrates a single scenario execution.

    Drives the SUT through a PlayerAgent, runs InvariantChecker per turn,
    optionally runs NarrativeJudge, and produces a TestReport.
    """

    def __init__(
        self,
        sut: SUTAdapter,
        scenario: ScenarioConfig,
        checker: InvariantChecker | None = None,
        judge: NarrativeJudge | None = None,
        transcript_dir: str | Path = "test_results",
    ) -> None:
        self._sut = sut
        self._scenario = scenario
        self._agent = PlayerAgent(scenario)
        self._checker = checker or InvariantChecker(fail_fast=scenario.fail_fast)
        self._judge = judge
        self._transcript_dir = Path(transcript_dir)
        self._turns: list[TurnResult] = []
        self._world_states: list[dict[str, Any]] = []

    @property
    def turns(self) -> list[TurnResult]:
        return list(self._turns)

    @property
    def check_results(self) -> list[Any]:
        """All invariant check results collected during the run."""
        return self._checker.results

    def run(self) -> TestReport:
        """
        Execute the full scenario and return a TestReport.

        Steps:
        1. Set up the SUT with scenario config.
        2. Loop: PlayerAgent produces action -> SUT processes -> collect TurnResult -> run invariants.
        3. Optionally score narrative quality.
        4. Produce report.
        """
        start = time.monotonic()

        # Setup SUT
        setup_config = {
            "system": self._scenario.system,
            "seed": self._scenario.seed,
            **self._scenario.pc,
            **self._scenario.extra,
        }
        self._sut.setup(setup_config)

        if self._scenario.seed is not None:
            random.seed(self._scenario.seed)

        # Main loop
        turn_num = 0
        try:
            while self._agent.has_next and turn_num < self._scenario.max_turns:
                world_state = self._sut.get_state()
                action = self._agent.next_action(world_state)
                if action is None:
                    break

                turn_num += 1
                raw_result = self._sut.process_turn(action)

                last_step = self._agent.last_step
                tags = tuple(last_step.tags) if last_step else ()

                turn = TurnResult(
                    turn_number=turn_num,
                    action=action,
                    narrative=raw_result.get("narrative", ""),
                    state_update=raw_result.get("state_update", {}),
                    world_state_snapshot=self._sut.get_state(),
                    raw_response=raw_result.get("raw_response", ""),
                    tags=tags,
                    extra=raw_result.get("extra", {}),
                )

                # Run invariant checks
                self._checker.check_turn(turn, turn.world_state_snapshot, self._turns)

                self._turns.append(turn)
                self._world_states.append(turn.world_state_snapshot)

        except CriticalFailureError as e:
            logger.warning("Scenario halted by fail-fast: %s", e)

        finally:
            self._sut.teardown()

        duration = time.monotonic() - start

        # Sanitize scenario name to prevent path traversal
        safe_name = re.sub(r"[^\w\-]", "_", self._scenario.name).strip("._")
        transcript_name = f"{safe_name}_{self._scenario.seed or 'noseed'}.jsonl"
        transcript_path = self._transcript_dir / transcript_name
        write_transcript(
            self._turns,
            transcript_path,
            seed=self._scenario.seed,
            framework_version=_framework_version,
            scenario=self._scenario.name,
            system=self._scenario.system,
        )

        # Invariant summary
        inv_summary = self._checker.summary()

        # Narrative scoring (optional)
        narrative_scores = None
        if self._judge and self._scenario.enable_narrative_judge and self._turns:
            scores = self._judge.score_transcript(self._turns, self._world_states)
            narrative_scores = self._judge.aggregate(scores)

        verdict = TestReport.compute_verdict(inv_summary)

        report = TestReport(
            scenario=self._scenario.name,
            system=self._scenario.system,
            seed=self._scenario.seed,
            turns_executed=len(self._turns),
            duration_seconds=round(duration, 2),
            invariant_results=inv_summary,
            narrative_scores=narrative_scores,
            verdict=verdict,
            transcript_path=str(transcript_path),
        )

        return report
