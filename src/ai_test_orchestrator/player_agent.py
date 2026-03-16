"""
Player Agent — drives the SUT with scripted or template-based actions.

The Player Agent reads actions from a ScenarioConfig and feeds them
to the SUT one at a time. It supports two modes:

- Scripted: actions are read sequentially from the scenario file.
- Template: action strings contain {variable} placeholders substituted
  from the current world state (e.g. "I attack {nearest_enemy}").

A future Phase 3 mode (Autonomous) would use an LLM to generate
contextually appropriate actions.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .models import ActionStep, ScenarioConfig

logger = logging.getLogger(__name__)


class PlayerAgent:
    """
    Produces player actions from a scenario script.

    Iterates through ScenarioConfig.actions, optionally substituting
    template variables from the current world state.
    """

    def __init__(self, scenario: ScenarioConfig) -> None:
        self._scenario = scenario
        self._index = 0
        self._last_step: ActionStep | None = None

    @property
    def has_next(self) -> bool:
        """True if there are more actions to execute."""
        return self._index < len(self._scenario.actions)

    @property
    def current_step(self) -> ActionStep | None:
        """The current action step, or None if exhausted."""
        if self._index < len(self._scenario.actions):
            return self._scenario.actions[self._index]
        return None

    @property
    def last_step(self) -> ActionStep | None:
        """The most recently returned action step, or None if next_action() hasn't been called."""
        return self._last_step

    def next_action(self, world_state: dict[str, Any] | None = None) -> str | None:
        """
        Return the next action string, advancing the index.

        If the action contains {template} variables and world_state is
        provided, substitutes them. Unknown variables are left as-is.
        """
        if not self.has_next:
            return None
        step = self._scenario.actions[self._index]
        self._index += 1
        self._last_step = step
        action = step.input

        # Template substitution
        if world_state and "{" in action:
            action = self._substitute(action, world_state)

        logger.debug("PlayerAgent action %d: %s", self._index, action)
        return action

    def reset(self) -> None:
        """Reset to the beginning of the scenario."""
        self._index = 0

    @staticmethod
    def _substitute(template: str, state: dict[str, Any]) -> str:
        """Replace {key} placeholders with values from state dict. Nested keys use dot notation."""

        def _resolve(match: re.Match) -> str:
            key = match.group(1)
            parts = key.split(".")
            value: Any = state
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, match.group(0))
                else:
                    return match.group(0)
            return str(value)

        return re.sub(r"\{([^}]+)\}", _resolve, template)
