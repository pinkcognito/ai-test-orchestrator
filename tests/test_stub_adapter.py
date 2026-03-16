"""Tests for the built-in StubAdapter."""

from ai_test_orchestrator.models import SUTAdapter
from ai_test_orchestrator.stub_adapter import StubAdapter


class TestStubAdapter:
    def test_implements_sut_protocol(self):
        assert isinstance(StubAdapter(), SUTAdapter)

    def test_setup_stores_config(self):
        adapter = StubAdapter()
        adapter.setup({"system": "gurps4e", "pc": {"name": "Thorn"}})
        state = adapter.get_state()
        assert state["system"] == "gurps4e"
        assert state["pc"]["name"] == "Thorn"

    def test_process_turn_returns_required_keys(self):
        adapter = StubAdapter()
        adapter.setup({"pc": {"name": "Aldric"}})
        result = adapter.process_turn("I look around")
        assert "narrative" in result
        assert "state_update" in result
        assert isinstance(result["narrative"], str)
        assert len(result["narrative"]) > 0

    def test_narrative_includes_pc_name(self):
        adapter = StubAdapter()
        adapter.setup({"pc": {"name": "Dai Blackthorn"}})
        result = adapter.process_turn("I draw my sword")
        assert "Dai Blackthorn" in result["narrative"]

    def test_turn_counter_increments(self):
        adapter = StubAdapter()
        adapter.setup({})
        r1 = adapter.process_turn("action 1")
        r2 = adapter.process_turn("action 2")
        assert "Turn 1" in r1["narrative"]
        assert "Turn 2" in r2["narrative"]

    def test_teardown_clears_state(self):
        adapter = StubAdapter()
        adapter.setup({"system": "d20"})
        adapter.teardown()
        assert adapter.get_state() == {}
