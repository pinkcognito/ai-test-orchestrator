# AI Test Orchestrator

Reusable AI-driven end-to-end testing framework for applications with non-deterministic (LLM) outputs.

## Three-Agent Architecture

```
Player Agent          System Under Test        Judge Agent
(Scenario Script) ──► (Your App/Game)     ──► (Invariant Checks)
                                                    │
                                              TestReport (JSON)
                                              pass / fail / warn
```

- **Player Agent**: Drives scripted or template-based actions into the SUT
- **System Under Test**: Your application, wrapped in a simple `SUTAdapter` protocol
- **Judge Agent**: Validates structural, mechanical, and narrative invariants per turn; optionally scores narrative quality via LLM

## Install

```bash
pip install ai-test-orchestrator          # core framework
pip install ai-test-orchestrator[llm]     # with LLM narrative judge
pip install -e ".[dev]"                   # for development
```

## Quick Start

```bash
# Run a scenario
python -m ai_test_orchestrator \
    --scenario data/scenarios/example.yaml \
    --adapter myapp.testing.adapter:MySUTAdapter \
    --invariants myapp.testing.invariants
```

## SUT Adapter Protocol

Implement this in your application repo:

```python
class SUTAdapter(Protocol):
    def setup(self, config: dict) -> None: ...
    def process_turn(self, action: str) -> dict[str, Any]: ...
    def get_state(self) -> dict[str, Any]: ...
    def teardown(self) -> None: ...
```

`process_turn()` must return `{"narrative": str, "state_update": dict}`.

## Scenario Files (YAML)

```yaml
name: My Test Scenario
system: gurps4e
seed: 42
max_turns: 15
actions:
  - input: "I look around"
    tags: [exploration]
  - input: "I attack {nearest_enemy}"
    tags: [combat]
```

## Writing Invariant Checks

```python
from ai_test_orchestrator.invariants.base import BaseInvariantCheck
from ai_test_orchestrator.models import Severity

class MyCheck(BaseInvariantCheck):
    _name = "my_check"
    _severity = Severity.ERROR

    def _check(self, turn_result, world_state, history):
        if something_wrong:
            return self._fail(turn_result, "Description of failure")
        return self._pass(turn_result)
```

## Severity Levels

| Level | Behavior |
|-------|----------|
| CRITICAL | Test suite fails; fail-fast halts execution |
| ERROR | Test marked failed; suite continues |
| WARNING | Logged only; does not fail |

## Development

```bash
git clone https://github.com/pinkcognito/ai-test-orchestrator.git
cd ai-test-orchestrator
pip install -e ".[dev]"
git config core.hooksPath .githooks
python -m pytest -v
```

## License

MIT
