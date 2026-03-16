"""Tests for the NarrativeJudge."""

from __future__ import annotations

import json

from ai_test_orchestrator.models import TurnResult
from ai_test_orchestrator.narrative_judge import NarrativeJudge


def _make_turn(narrative: str = "The goblin lunges.") -> TurnResult:
    return TurnResult(turn_number=1, action="attack", narrative=narrative)


class TestNarrativeJudge:
    def test_offline_returns_zero_scores(self) -> None:
        judge = NarrativeJudge(llm_callable=None)
        score = judge.score_turn(_make_turn(), {})
        assert score.overall == 0.0
        assert "offline" in score.rationale.lower() or "No LLM" in score.rationale

    def test_caching(self) -> None:
        call_count = 0

        def mock_llm(system: str, user: str) -> str:
            nonlocal call_count
            call_count += 1
            return json.dumps(
                {
                    "tone_consistency": 4,
                    "action_acknowledgment": 4,
                    "immersion": 4,
                    "mechanical_accuracy": 4,
                    "continuity": 4,
                    "rationale": "Good",
                }
            )

        judge = NarrativeJudge(llm_callable=mock_llm)
        t = _make_turn("The goblin attacks.")
        judge.score_turn(t, {})
        judge.score_turn(t, {})
        assert call_count == 1  # Second call should be cached

    def test_parses_llm_response(self) -> None:
        def mock_llm(system: str, user: str) -> str:
            return json.dumps(
                {
                    "tone_consistency": 5,
                    "action_acknowledgment": 4,
                    "immersion": 3,
                    "mechanical_accuracy": 4,
                    "continuity": 5,
                    "rationale": "Solid narrative",
                }
            )

        judge = NarrativeJudge(llm_callable=mock_llm)
        score = judge.score_turn(_make_turn(), {})
        assert score.tone_consistency == 5.0
        assert score.immersion == 3.0
        assert score.rationale == "Solid narrative"
        assert 3.0 < score.overall < 5.0

    def test_aggregate(self) -> None:
        from ai_test_orchestrator.models import NarrativeScore

        scores = [
            NarrativeScore(
                tone_consistency=4, action_acknowledgment=4, immersion=4, mechanical_accuracy=4, continuity=4
            ),
            NarrativeScore(
                tone_consistency=2, action_acknowledgment=2, immersion=2, mechanical_accuracy=2, continuity=2
            ),
        ]
        judge = NarrativeJudge()
        agg = judge.aggregate(scores)
        assert abs(agg["overall"] - 3.0) < 0.01

    def test_llm_error_handled(self) -> None:
        def broken_llm(system: str, user: str) -> str:
            raise RuntimeError("API down")

        judge = NarrativeJudge(llm_callable=broken_llm)
        score = judge.score_turn(_make_turn(), {})
        assert score.overall == 0.0
        assert "error" in score.rationale.lower()
