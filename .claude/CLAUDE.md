# CLAUDE.md — AI Test Orchestrator Project Guide

## What This Project Is

A reusable, framework-agnostic testing orchestration system for AI-driven applications. It automates end-to-end scenario testing through a three-agent architecture: a **Player Agent** drives scripted actions into a **System Under Test** (SUT), and a **Judge Agent** validates invariants and optionally scores narrative quality via an LLM.

The framework is designed to be consumed as a dependency by application repos (e.g. AI-dungeonmaster). Application-specific invariants and SUT adapters live in the consuming repo, not here.

## Project Structure

```
src/ai_test_orchestrator/
  __init__.py
  __main__.py                 # python -m ai_test_orchestrator
  models.py                   # Core data models: SUTAdapter protocol, TurnResult, CheckResult, ScenarioConfig, NarrativeScore, Severity, Verdict
  player_agent.py             # Scripted/template action driver
  invariant_checker.py        # Framework: run checks, collect results, fail-fast or collect-all
  invariants/
    __init__.py               # Plugin registry: register(), get_all_checks(), clear_registry()
    base.py                   # InvariantCheck protocol + BaseInvariantCheck convenience class
  narrative_judge.py          # LLM rubric-based narrative scorer (optional, needs 'llm' extra)
  runner.py                   # ScenarioRunner: orchestrates full scenario execution
  report.py                   # TestReport, JSONL transcript writer, console summary
  cli.py                      # CLI entry point

tests/
  test_models.py
  test_player_agent.py
  test_invariant_checker.py
  test_narrative_judge.py
  test_report.py
  test_runner.py

data/scenarios/               # Example scenario YAML files (for reference/testing)
test_results/                 # Generated reports and transcripts (.gitignored except .gitkeep)
```

## Key Design Decisions

### 1. SUTAdapter Protocol
The framework talks to any system through the `SUTAdapter` protocol:
```python
class SUTAdapter(Protocol):
    def setup(self, config: dict) -> None: ...
    def process_turn(self, action: str) -> dict[str, Any]: ...
    def get_state(self) -> dict[str, Any]: ...
    def teardown(self) -> None: ...
```
Application repos implement this once to wrap their game session / app loop.

### 2. Invariants Are Pluggable
Invariant checks are registered via `invariants.register()` or passed directly to `InvariantChecker`. Each check implements the `InvariantCheck` protocol (name, severity, check method). The framework provides `BaseInvariantCheck` with `_pass()` and `_fail()` helpers.

### 3. TurnResult Is Immutable
`TurnResult` is a frozen dataclass. Each turn creates a new instance. No mutation of previous results. History is a list of prior TurnResults.

### 4. Narrative Judge Is Optional
The LLM judge requires the `[llm]` extra. Without it, `NarrativeJudge` runs in offline mode (zero scores). The judge accepts any callable `(system_prompt, user_message) -> str` — not tied to Anthropic.

### 5. Severity Drives CI
- **CRITICAL**: test suite fails, fail-fast halts execution
- **ERROR**: test marked as failed, suite continues
- **WARNING**: logged only, does not fail

## How to Install

```bash
# As a dependency in another project
pip install ai-test-orchestrator
# or from git:
pip install git+https://github.com/pinkcognito/ai-test-orchestrator.git

# With LLM judge support
pip install ai-test-orchestrator[llm]

# For development
pip install -e ".[dev]"
```

## How to Run

```bash
# Run a scenario against a SUT adapter
python -m ai_test_orchestrator \
    --scenario data/scenarios/example.yaml \
    --adapter myapp.testing.adapter:MySUTAdapter

# With custom invariants
python -m ai_test_orchestrator \
    --scenario data/scenarios/example.yaml \
    --adapter myapp.testing.adapter:MySUTAdapter \
    --invariants myapp.testing.invariants

# Fail-fast mode
python -m ai_test_orchestrator \
    --scenario data/scenarios/example.yaml \
    --adapter myapp.testing.adapter:MySUTAdapter \
    --fail-fast
```

## How to Test

```bash
pip install -e ".[dev]"
python -m pytest -v

# With coverage
python -m pytest --cov=ai_test_orchestrator --cov-report=term-missing
```

## Scenario File Format (YAML)

```yaml
name: Tavern Social Interaction
system: gurps4e
seed: 42
max_turns: 15
fail_fast: false
enable_narrative_judge: false
pc:
  name: Dai Blackthorn
  location: The Broken Anvil Inn
actions:
  - input: "I look around the room"
    tags: [perception, exploration]
  - input: "I approach the innkeeper"
    tags: [social]
    expect:
      disposition_change: Mira Ashvale
  - input: "I attack {nearest_enemy}"
    tags: [combat]
```

Template variables (`{key}` or `{nested.key}`) are substituted from the current world state.

## Writing Custom Invariants (for consuming projects)

```python
from ai_test_orchestrator.invariants.base import BaseInvariantCheck
from ai_test_orchestrator.models import Severity

class NoRawNumbersInNarrative(BaseInvariantCheck):
    _name = "no_raw_numbers"
    _severity = Severity.ERROR

    def _check(self, turn_result, world_state, history):
        # Check for HP/FP values leaked into narrative
        hp = world_state.get("pc_hp", "")
        if isinstance(hp, str) and "/" in hp:
            raw = hp.split("/")[0]
            if raw in turn_result.narrative:
                return self._fail(turn_result, f"Found raw HP '{raw}' in narrative")
        return self._pass(turn_result)
```

Register in your project's invariants module:
```python
def get_checks():
    return [NoRawNumbersInNarrative(), ...]
```

## Writing a SUT Adapter (for consuming projects)

```python
from ai_test_orchestrator.models import SUTAdapter
from myapp.main import GameSession

class MyGameAdapter:
    def __init__(self):
        self._session = None

    def setup(self, config):
        self._session = GameSession(
            rules_system=config.get("system", "gurps4e"),
            offline=True,
        )
        self._session.setup(
            pc_name=config.get("name", "Test Hero"),
            location=config.get("location", "Test Location"),
        )

    def process_turn(self, action):
        narrative = self._session.process_turn(action)
        return {
            "narrative": narrative,
            "state_update": {},  # parse from GM response if available
        }

    def get_state(self):
        return self._session.world.get_state()

    def teardown(self):
        pass
```

## Common Tasks

### Adding a new invariant check
1. Subclass `BaseInvariantCheck` in your project
2. Set `_name` and `_severity`
3. Override `_check()` returning `self._pass(turn)` or `self._fail(turn, msg)`
4. Add to your `get_checks()` function

### Adding a new scenario
Create a YAML file following the format above. Place it in your project's `data/scenarios/` directory.

### Running in CI
```yaml
# .github/workflows/e2e-tests.yml
- name: Run E2E tests
  run: |
    python -m ai_test_orchestrator \
      --scenario data/scenarios/*.yaml \
      --adapter src.testing.adapter:GameAdapter \
      --invariants src.testing.invariants \
      --json-report test_results/report.json
```
