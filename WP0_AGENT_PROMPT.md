# Agent Prompt: WP0 — RNG Seeding & Framework Hardening

## Your Role

You are a senior Python engineer working on `ai-test-orchestrator`, a standalone reusable testing framework for AI/LLM applications. The repo is at `C:/Users/Dave/github/ai-test-orchestrator`. Read CLAUDE.md first, then the full source tree before writing any code.

Your job: implement WP0 (deterministic RNG seeding at the framework level) and fix every quality gap listed below. Ship production-grade code with full test coverage. No placeholders, no TODOs, no half-measures.

---

## WP0: Deterministic RNG Seeding

### Problem

The framework passes `ScenarioConfig.seed` to the SUT via `setup(config)`, but does **nothing** at the framework level to seed Python's own RNG. If any framework code (now or in the future) uses `random`, results won't be reproducible. The runner should own framework-level seeding.

### Requirements

1. **In `runner.py` → `ScenarioRunner.run()`**, before the main loop begins (after SUT setup), seed Python's `random` module if `self._scenario.seed` is not None:
   ```python
   import random
   if self._scenario.seed is not None:
       random.seed(self._scenario.seed)
   ```

2. **In `report.py` → `TestReport`**, add a `framework_version` field that captures `__version__` from the package. This aids reproducibility — you can tell which framework version produced a given report.

3. **In `report.py` → `write_transcript()`**, include `seed` and `framework_version` as a metadata header line (turn_number: 0) at the top of the JSONL file, so transcripts are self-describing:
   ```json
   {"turn_number": 0, "type": "metadata", "seed": 42, "framework_version": "0.1.0", "scenario": "tavern_brawl", "system": "gurps4e"}
   ```

4. **In `cli.py`**, log the seed value at INFO level when a scenario starts, so the user always sees which seed was used (or "none" if unseeded).

5. **Tests**: Add tests for all of the above — verify random.seed is called, verify transcript metadata line, verify framework_version in report.

---

## Quality Improvements

### A. Fix the encapsulation violation in `runner.py`

**Current bug (line 113):**
```python
tags = tuple(self._scenario.actions[self._agent._index - 1].tags) if self._agent._index > 0 else ()
```

This reaches into `PlayerAgent._index` (a private attribute) from outside the class. This is fragile and breaks encapsulation.

**Fix:** `PlayerAgent` already has a `current_step` property, but `next_action()` advances the index *before* returning, so by the time the runner reads `current_step` it's already pointing at the *next* step. Refactor so the runner can get the tags of the *just-executed* step cleanly:

- Add a `last_step` property to `PlayerAgent` that returns the step that was just executed (index - 1), or None if no step has been executed yet.
- In `runner.py`, replace the `_index` access with `self._agent.last_step`.
- The runner line becomes:
  ```python
  last = self._agent.last_step
  tags = tuple(last.tags) if last else ()
  ```

### B. Public API exports in `__init__.py`

The package's `__init__.py` only exports `__version__`. Any consumer has to know the internal module layout to import anything. Add proper public API exports:

```python
from .models import (
    SUTAdapter, TurnResult, CheckResult, ActionStep,
    ScenarioConfig, NarrativeScore, Severity, Verdict,
)
from .invariants.base import BaseInvariantCheck, InvariantCheck
from .invariant_checker import InvariantChecker
from .runner import ScenarioRunner, load_scenario
from .report import TestReport, write_transcript, console_summary
from .narrative_judge import NarrativeJudge
from .player_agent import PlayerAgent
```

Also add an `__all__` list so `from ai_test_orchestrator import *` is well-defined.

### C. Tag-based check filtering

**Current gap:** The `InvariantChecker` runs ALL registered checks on EVERY turn, regardless of tags. The PRD specifies that checks should be filterable by tags — e.g., combat-specific checks should only fire on turns tagged `[combat]`.

**Implement:**
1. Add an optional `tags` attribute to `BaseInvariantCheck` (default: empty tuple = runs on all turns).
2. In `InvariantChecker.check_turn()`, skip checks whose `tags` don't intersect with the turn's `tags`. A check with empty tags always runs (universal check). A check with `tags=("combat",)` only runs on turns where `TurnResult.tags` contains `"combat"`.
3. Add the `tags` property to the `InvariantCheck` protocol (with a default so existing implementations don't break).

### D. Scenario validation

**Current gap:** `load_scenario()` does zero validation. A YAML file missing `actions` silently produces a scenario with no actions. A YAML file with `max_turns: "banana"` passes through unchecked.

**Implement:**
1. After loading, validate: `actions` must be a list (can be empty). `max_turns` must be a positive integer. `name` must be a non-empty string. `system` must be a non-empty string.
2. Raise a clear `ValueError` with a descriptive message for each violation.
3. Validate each `ActionStep`: `input` must be a non-empty string.

### E. Transcript includes world_state_snapshot

**Current gap:** `write_transcript()` omits `world_state_snapshot` from the JSONL output. This is the most valuable field for debugging invariant failures — you need to see what the world looked like when something went wrong.

**Fix:** Add `world_state_snapshot` to the dict written per turn. Also add `extra` if non-empty.

### F. ScenarioRunner should expose the checker

**Current gap:** After `run()` returns, there's no way to get the raw `CheckResult` objects — only the summary dict in the report. Consumers may want to programmatically inspect individual failures.

**Fix:** Add a `@property check_results` to `ScenarioRunner` that returns `self._checker.results`.

---

## Constraints

- **Python 3.11+**, type hints everywhere, `from __future__ import annotations` at the top of every module.
- **Ruff clean**: `ruff check src/ tests/` and `ruff format --check src/ tests/` must pass with zero errors. Config is in `pyproject.toml` (line-length 120, py311, rules E/F/I/N/W/UP).
- **All existing tests must continue to pass.** Do not break any existing test. Run `python -m pytest -v` and confirm 46+ tests pass before and after your changes.
- **Frozen dataclasses stay frozen.** Do not unfreeze `TurnResult`, `CheckResult`, or `NarrativeScore`.
- **No new dependencies.** Everything uses stdlib + pyyaml (already in deps).
- **Docstrings** on every public class, method, and function. Follow existing style (imperative mood, one-line summary, then details if needed).
- **Test naming**: `test_<what>_<expected_behavior>`. One assert per test where practical.
- **Commit messages**: conventional commits (`feat:`, `fix:`, `test:`, `refactor:`).

## Files You Will Modify

| File | Changes |
|------|---------|
| `src/ai_test_orchestrator/__init__.py` | Public API exports + `__all__` |
| `src/ai_test_orchestrator/player_agent.py` | Add `last_step` property |
| `src/ai_test_orchestrator/runner.py` | RNG seeding, fix `_index` access, expose `check_results` |
| `src/ai_test_orchestrator/report.py` | `framework_version` field, transcript metadata line, include world_state_snapshot |
| `src/ai_test_orchestrator/invariant_checker.py` | Tag-based check filtering |
| `src/ai_test_orchestrator/invariants/base.py` | Add `tags` to protocol and base class |
| `src/ai_test_orchestrator/cli.py` | Log seed at INFO |
| `tests/test_runner.py` | Tests for RNG seeding, metadata line, check_results exposure |
| `tests/test_player_agent.py` | Test for `last_step` property |
| `tests/test_invariant_checker.py` | Tests for tag filtering |
| `tests/test_report.py` | Tests for framework_version, world_state in transcript |
| `tests/test_models.py` | (verify no breakage) |

## Files You Must NOT Modify

- `pyproject.toml` (no new deps, no config changes)
- `.claude/CLAUDE.md` (do not update project docs — that's a separate step)
- `.cursor/rules/cursorrules.mdc`

## Definition of Done

1. `python -m pytest -v` — all tests pass (original 46 + your new ones)
2. `ruff check src/ tests/` — zero errors
3. `ruff format --check src/ tests/` — zero reformatting needed
4. Every improvement listed above is implemented with tests
5. No `# TODO`, no `# FIXME`, no `pass` stubs
6. A single commit with message: `feat: WP0 deterministic seeding + framework hardening`

## Execution Order

1. Read all source files and all test files first. Understand the patterns.
2. Implement changes in dependency order: models → player_agent → invariants/base → invariant_checker → report → runner → cli → __init__.py
3. Write tests alongside each change.
4. Run `ruff check --fix src/ tests/` then `ruff format src/ tests/` then `python -m pytest -v`.
5. Fix any failures. Repeat until green.
6. Commit.
