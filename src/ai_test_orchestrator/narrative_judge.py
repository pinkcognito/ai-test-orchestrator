"""
LLM Narrative Judge — rubric-based narrative quality scoring.

Sends narrative segments to an LLM with a structured rubric and parses
back 1-5 scores per criterion. The rubric and LLM backend are configurable.

This module is optional: it requires the 'llm' extra dependency (anthropic).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .models import NarrativeScore, TurnResult

logger = logging.getLogger(__name__)

DEFAULT_RUBRIC = """You are evaluating the narrative quality of an AI Game Master's response.

Score each criterion from 1 (poor) to 5 (excellent):

1. **Tone Consistency** (25%): Does the narrative tone match the scene mood and character dispositions?
2. **Action Acknowledgment** (25%): Does the narrative address what the player actually did?
3. **Immersion** (20%): Is the prose engaging, vivid, and free of meta-game language?
4. **Mechanical Accuracy** (20%): Do narrative descriptions align with the mechanical outcomes provided?
5. **Continuity** (10%): Does the narrative reference prior events correctly?

Context provided:
- Player action: {action}
- Mechanical results: {state_update}
- World state summary: {world_state_summary}

Narrative to evaluate:
{narrative}

Respond with ONLY a JSON object:
{{"tone_consistency": N, "action_acknowledgment": N, "immersion": N, "mechanical_accuracy": N, "continuity": N, "rationale": "brief explanation"}}
"""


def _safe_substitute(template: str, values: dict[str, str]) -> str:
    """Substitute {key} placeholders without using str.format(), avoiding brace injection."""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    return re.sub(r"\{([a-z_]+)\}", _replace, template)


class NarrativeJudge:
    """
    Scores narrative quality using an LLM with a configurable rubric.

    Requires an LLM callable: (system_prompt: str, user_message: str) -> str.
    """

    def __init__(
        self,
        llm_callable: Any | None = None,
        rubric_template: str = DEFAULT_RUBRIC,
    ) -> None:
        """
        Args:
            llm_callable: A callable(system: str, user: str) -> str that calls an LLM.
                          If None, judge returns zero scores (offline mode).
            rubric_template: Template with {action}, {state_update}, {world_state_summary},
                             {narrative} placeholders.
        """
        self._llm = llm_callable
        self._rubric = rubric_template
        self._cache: dict[str, NarrativeScore] = {}
        self._approx_word_count: int = 0

    @property
    def approx_word_count(self) -> int:
        """Approximate word count across all judge calls (not a token count)."""
        return self._approx_word_count

    def score_turn(
        self,
        turn_result: TurnResult,
        world_state: dict[str, Any],
    ) -> NarrativeScore:
        """
        Score a single turn's narrative.

        Returns cached result if the same narrative was already scored.
        Returns zero scores if no LLM callable is configured.
        """
        cache_key = turn_result.narrative.strip()
        if cache_key in self._cache:
            logger.debug("NarrativeJudge: cache hit for turn %d", turn_result.turn_number)
            return self._cache[cache_key]

        if self._llm is None:
            return NarrativeScore(rationale="No LLM configured; offline mode")

        prompt = _safe_substitute(
            self._rubric,
            {
                "action": turn_result.action,
                "state_update": json.dumps(turn_result.state_update, indent=2),
                "world_state_summary": json.dumps(
                    {k: v for k, v in world_state.items() if k in ("location", "pc_name", "pc_hp", "turn")},
                    indent=2,
                ),
                "narrative": turn_result.narrative,
            },
        )

        try:
            response = self._llm("You are a narrative quality evaluator.", prompt)
            self._approx_word_count += len(prompt.split()) + len(response.split())
            score = self._parse_response(response)
        except Exception as e:
            logger.error("NarrativeJudge LLM call failed: %s", e)
            score = NarrativeScore(rationale=f"LLM error: {e}")

        self._cache[cache_key] = score
        return score

    def score_transcript(self, turns: list[TurnResult], world_states: list[dict[str, Any]]) -> list[NarrativeScore]:
        """Score all turns in a transcript. Returns list parallel to turns."""
        return [self.score_turn(t, ws) for t, ws in zip(turns, world_states)]

    def aggregate(self, scores: list[NarrativeScore]) -> dict[str, float]:
        """Average scores across all turns."""
        if not scores:
            return {"overall": 0.0}
        n = len(scores)
        return {
            "tone_consistency": sum(s.tone_consistency for s in scores) / n,
            "action_acknowledgment": sum(s.action_acknowledgment for s in scores) / n,
            "immersion": sum(s.immersion for s in scores) / n,
            "mechanical_accuracy": sum(s.mechanical_accuracy for s in scores) / n,
            "continuity": sum(s.continuity for s in scores) / n,
            "overall": sum(s.overall for s in scores) / n,
        }

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 5.0) -> float:
        """Clamp a value to [lo, hi] range."""
        return max(lo, min(hi, value))

    @staticmethod
    def _parse_response(response: str) -> NarrativeScore:
        """Parse LLM JSON response into NarrativeScore."""
        # Strip markdown fences if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]

        data = json.loads(text)
        clamp = NarrativeJudge._clamp
        return NarrativeScore(
            tone_consistency=clamp(float(data.get("tone_consistency", 0))),
            action_acknowledgment=clamp(float(data.get("action_acknowledgment", 0))),
            immersion=clamp(float(data.get("immersion", 0))),
            mechanical_accuracy=clamp(float(data.get("mechanical_accuracy", 0))),
            continuity=clamp(float(data.get("continuity", 0))),
            rationale=str(data.get("rationale", "")),
        )
