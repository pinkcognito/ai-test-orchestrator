"""Tests for the PlayerAgent."""

from __future__ import annotations

from ai_test_orchestrator.models import ActionStep, ScenarioConfig
from ai_test_orchestrator.player_agent import PlayerAgent


class TestPlayerAgent:
    def _make_scenario(self, actions: list[str]) -> ScenarioConfig:
        return ScenarioConfig(
            name="test",
            actions=[ActionStep(input=a) for a in actions],
        )

    def test_has_next_and_exhaustion(self) -> None:
        agent = PlayerAgent(self._make_scenario(["a", "b"]))
        assert agent.has_next is True
        agent.next_action()
        agent.next_action()
        assert agent.has_next is False
        assert agent.next_action() is None

    def test_returns_actions_in_order(self) -> None:
        agent = PlayerAgent(self._make_scenario(["first", "second", "third"]))
        assert agent.next_action() == "first"
        assert agent.next_action() == "second"
        assert agent.next_action() == "third"

    def test_reset(self) -> None:
        agent = PlayerAgent(self._make_scenario(["a"]))
        agent.next_action()
        assert agent.has_next is False
        agent.reset()
        assert agent.has_next is True
        assert agent.next_action() == "a"

    def test_template_substitution(self) -> None:
        agent = PlayerAgent(self._make_scenario(["I go to {location}"]))
        result = agent.next_action(world_state={"location": "the tavern"})
        assert result == "I go to the tavern"

    def test_template_nested_keys(self) -> None:
        agent = PlayerAgent(self._make_scenario(["attack {pc.name}"]))
        result = agent.next_action(world_state={"pc": {"name": "Goblin"}})
        assert result == "attack Goblin"

    def test_template_unknown_key_left_intact(self) -> None:
        agent = PlayerAgent(self._make_scenario(["use {unknown_item}"]))
        result = agent.next_action(world_state={"location": "inn"})
        assert result == "use {unknown_item}"

    def test_empty_scenario(self) -> None:
        agent = PlayerAgent(self._make_scenario([]))
        assert agent.has_next is False
        assert agent.next_action() is None

    def test_last_step_none_before_first_action(self) -> None:
        agent = PlayerAgent(self._make_scenario(["a", "b"]))
        assert agent.last_step is None

    def test_last_step_tracks_executed_actions(self) -> None:
        agent = PlayerAgent(self._make_scenario(["first", "second"]))
        agent.next_action()
        assert agent.last_step is not None
        assert agent.last_step.input == "first"
        agent.next_action()
        assert agent.last_step.input == "second"

    def test_last_step_persists_after_exhaustion(self) -> None:
        agent = PlayerAgent(self._make_scenario(["only"]))
        agent.next_action()
        agent.next_action()  # returns None (exhausted)
        assert agent.last_step is not None
        assert agent.last_step.input == "only"
