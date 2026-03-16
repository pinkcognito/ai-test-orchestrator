"""
Stub SUTAdapter for testing and CI.

Returns canned responses so the full framework pipeline can be exercised
without a real application backend or API key.
"""

from __future__ import annotations

from typing import Any


class StubAdapter:
    """A no-op SUT adapter that returns fixed narrative responses.

    Useful for:
    - CI pipeline smoke tests
    - Framework development and debugging
    - Example scenario validation
    """

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self._turn = 0

    def setup(self, config: dict[str, Any]) -> None:
        self._state = {
            "pc": config.get("pc", {"name": "Test Hero"}),
            "system": config.get("system", "gurps4e"),
            "location": config.get("pc", {}).get("location", "Test Location"),
            "npcs": {},
            "flags": {},
        }
        self._turn = 0

    def process_turn(self, action: str) -> dict[str, Any]:
        self._turn += 1
        pc_name = self._state.get("pc", {}).get("name", "the adventurer")
        return {
            "narrative": (
                f"{pc_name} considers the situation carefully. "
                f"The room is quiet, save for the crackle of the hearth fire. "
                f"(Turn {self._turn}: responding to '{action[:50]}')"
            ),
            "state_update": {
                "flags": {},
                "disposition_changes": {},
            },
        }

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def teardown(self) -> None:
        self._state.clear()
        self._turn = 0
