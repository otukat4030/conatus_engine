# Conatus Engine

Conatus Engine is a small Python study project for experimenting with concepts
in Spinoza's *Ethics*, especially Part III. It is not a complete formalization
and should not be read as the only correct interpretation of Spinoza. The code
is a provisional learning and research model that makes its current assumptions
explicit.

Version `0.3.0` moves the project from a single encounter classifier to a small
state transition engine with a derivation trace.

## What Changed

The model now separates two ideas that were previously mixed together:

- `CausalAdequacy`: whether the result can be sufficiently explained from the
  agent's own nature and power.
- `IdeaAdequacy`: whether the agent sufficiently understands the causes of the
  event.

Active and passive modes are classified only from `CausalAdequacy`:

- `adequate` causal adequacy -> `active`
- `partial` causal adequacy -> `passive`

`IdeaAdequacy` is recorded independently. This means the engine can represent a
case where an agent understands the causes of an external event but is still not
the sufficient cause of that result.

## Core Models

- `AgentState`: the state of one agent at a point in time.
- `WorldEvent`: an event that changes the agent's power.
- `Transition`: the before/after result of applying one event to one state.
- `Derivation`: one recorded rule application explaining part of the result.

At this stage, `power_delta` is still provided as input. The engine does not yet
calculate a change in power from the event itself. Power is also represented as
an unrestricted finite real number, including negative values. Both choices are
temporary modeling decisions and will likely be revised later.

## Python API

```python
from conatus_engine import (
    AgentState,
    CausalAdequacy,
    IdeaAdequacy,
    WorldEvent,
    step,
)

state = AgentState(agent_id="agent-1", name="Spinoza", power=10.0)
event = WorldEvent(
    event_id="event-1",
    description="A clear but externally caused event",
    power_delta=-2.0,
    causal_adequacy=CausalAdequacy.PARTIAL,
    idea_adequacy=IdeaAdequacy.ADEQUATE,
)

transition = step(state, event)

assert transition.before == state
assert transition.after.power == 8.0
assert transition.affect.value == "sadness"
assert transition.mode.value == "passive"
assert transition.idea_adequacy.value == "adequate"
assert len(transition.derivations) >= 4
```

You can also use the small engine wrapper:

```python
from conatus_engine import ConatusEngine

transition = ConatusEngine().step(state, event)
```

## JSON

`AgentState`, `WorldEvent`, and `Transition` support JSON-compatible
dictionaries and JSON strings:

```python
data = transition.to_dict()
json_text = transition.to_json()
restored = transition.from_json(json_text)
assert restored == transition
```

Example transition JSON:

```json
{
  "before": {"agent_id": "agent-1", "name": "Spinoza", "power": 10.0},
  "after": {"agent_id": "agent-1", "name": "Spinoza", "power": 8.0},
  "event": {
    "event_id": "event-1",
    "description": "A clear but externally caused event",
    "power_delta": -2.0,
    "causal_adequacy": "partial",
    "idea_adequacy": "adequate"
  },
  "affect": "sadness",
  "mode": "passive",
  "idea_adequacy": "adequate",
  "derivations": [
    {
      "rule_id": "power.update",
      "premises": ["before.power=10.0", "event.power_delta=-2.0"],
      "conclusion": "after.power=8.0",
      "explanation": "現段階では、出来事に与えられた力能変化量を現在の力能に加算します。"
    }
  ]
}
```

## CLI

Run the CLI with:

```bash
python -m conatus_engine
```

or after installing the package:

```bash
pip install -e .
conatus-engine
```

The CLI first asks for an initial `AgentState` by requesting the agent's name
and current power. It uses the entered name as the internal `agent_id`, so you
only need to provide one identifier. It then enters an event loop: each
`WorldEvent` is applied to the current state, the transition is displayed, and
the resulting `after` state becomes the next current state. This makes the
state transition model visible from the command line.

For each event, the CLI asks separately whether the result is sufficiently
explained by the agent's own nature and power, and whether the agent sufficiently
understands the causes of the event.

Example:

```text
人物名: Spinoza
現在の力能: 10

--- 現在の状態: Spinoza / power=10.0 ---
新しい出来事を入力しますか？ (y/n): y
イベントID: event-1
出来事の説明: 外的な出来事の原因を正しく理解した
出来事による力能の変化量: -2
この結果は、その人物自身の本性・力から十分に説明できますか？ (y/n): n
その人物は、出来事の原因を十分に理解していますか？ (y/n): y
```

The output includes before/after power, affect, active/passive mode, causal
adequacy, idea adequacy, and the derivation history. When you continue, the next
event starts from the latest `after.power`.

## Validation

The models reject empty IDs and names. Power values and power deltas must be
finite numbers; `NaN`, positive infinity, and negative infinity raise
`ValueError`.

## Tests

Development dependencies are optional:

```bash
pip install -e ".[dev]"
pytest
```

## Current Limits

- The engine does not infer `power_delta`; it evaluates an already supplied
  change in power.
- Power has no upper or lower bound in this version.
- Only joy, sadness, and neutrality are modeled.
- Active/passive mode is based on the provisional causal adequacy rule above.
- The derivation rule IDs are stable placeholders, not guessed proposition
  numbers from the *Ethics*.

Future versions may calculate power changes from richer event descriptions and
may add love, hatred, hope, fear, imitation of affects, and other concepts.

## Project Structure

```text
conatus_engine/
  __init__.py
  __main__.py
  cli.py
  engine.py
  models.py
  serialization.py
tests/
  test_engine.py
  test_models.py
  test_serialization.py
pyproject.toml
README.md
```
