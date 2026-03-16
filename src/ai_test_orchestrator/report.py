"""
Test Report — structured output from a scenario execution.

Generates JSON reports with invariant results, optional narrative scores,
a verdict, and a JSONL transcript path. Also provides console summary output.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ._version import __version__ as _framework_version
from .models import TurnResult, Verdict

logger = logging.getLogger(__name__)


@dataclass
class TestReport:
    """Structured report from a single scenario execution."""

    scenario: str
    system: str
    seed: int | None
    turns_executed: int
    duration_seconds: float
    invariant_results: dict[str, Any] = field(default_factory=dict)
    narrative_scores: dict[str, float] | None = None
    verdict: Verdict = Verdict.PASS
    transcript_path: str = ""
    framework_version: str = _framework_version

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str | Path) -> None:
        """Write report JSON to file."""
        Path(path).write_text(self.to_json(), encoding="utf-8")
        logger.info("Report saved to %s", path)

    @staticmethod
    def compute_verdict(invariant_summary: dict[str, Any]) -> Verdict:
        """
        Determine verdict from invariant summary.

        FAIL: any CRITICAL or ERROR failures.
        PASS_WITH_WARNINGS: only WARNING failures.
        PASS: no failures at all.
        """
        critical = invariant_summary.get("critical", {})
        error = invariant_summary.get("error", {})
        warning = invariant_summary.get("warning", {})

        if critical.get("failed", 0) > 0 or error.get("failed", 0) > 0:
            return Verdict.FAIL
        if warning.get("failed", 0) > 0:
            return Verdict.PASS_WITH_WARNINGS
        return Verdict.PASS


def write_transcript(
    turns: list[TurnResult],
    path: str | Path,
    *,
    seed: int | None,
    framework_version: str,
    scenario: str,
    system: str,
) -> None:
    """Write turn results as JSONL (metadata header + one JSON object per turn)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        metadata = {
            "turn_number": 0,
            "type": "metadata",
            "seed": seed,
            "framework_version": framework_version,
            "scenario": scenario,
            "system": system,
        }
        f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
        for turn in turns:
            # Convert frozen dataclass to dict for serialisation
            d = {
                "turn_number": turn.turn_number,
                "action": turn.action,
                "narrative": turn.narrative,
                "state_update": turn.state_update,
                "world_state_snapshot": turn.world_state_snapshot,
                "tags": list(turn.tags),
                "timestamp": turn.timestamp,
                "extra": turn.extra,
            }
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    logger.info("Transcript written to %s (%d turns)", path, len(turns))


def console_summary(report: TestReport) -> str:
    """Format a human-readable console summary with pass/fail counts."""
    lines = [
        f"\n{'=' * 60}",
        f"  Scenario: {report.scenario}",
        f"  System:   {report.system}",
        f"  Seed:     {report.seed or 'none'}",
        f"  Turns:    {report.turns_executed}",
        f"  Duration: {report.duration_seconds:.1f}s",
        f"{'─' * 60}",
    ]

    for severity in ["critical", "error", "warning"]:
        data = report.invariant_results.get(severity, {})
        passed = data.get("passed", 0)
        failed = data.get("failed", 0)
        total = passed + failed
        status = "PASS" if failed == 0 else "FAIL"
        label = severity.upper().ljust(10)
        lines.append(f"  {label} {passed}/{total} passed  [{status}]")
        for failure in data.get("failures", []):
            lines.append(f"           └─ turn {failure['turn']}: {failure['message']}")

    if report.narrative_scores:
        lines.append(f"{'─' * 60}")
        lines.append("  Narrative scores:")
        for key, val in report.narrative_scores.items():
            lines.append(f"    {key}: {val:.2f}")

    verdict_str = report.verdict.value.upper().replace("_", " ")
    lines.extend(
        [
            f"{'─' * 60}",
            f"  VERDICT: {verdict_str}",
            f"{'=' * 60}",
        ]
    )

    return "\n".join(lines)
