from conatus_engine.engine import step
from conatus_engine.models import (
    Affect,
    AgentState,
    CausalAdequacy,
    IdeaAdequacy,
    Mode,
    Transition,
    WorldEvent,
)
from conatus_engine.serialization import transition_from_json, to_dict, to_json


def test_transition_to_dict_preserves_required_information() -> None:
    state = AgentState(agent_id="agent-1", name="Spinoza", power=10.0)
    event = WorldEvent(
        event_id="event-1",
        description="a clear but externally caused event",
        power_delta=-2.0,
        causal_adequacy=CausalAdequacy.PARTIAL,
        idea_adequacy=IdeaAdequacy.ADEQUATE,
    )

    data = step(state, event).to_dict()

    assert data["before"]["power"] == 10.0
    assert data["after"]["power"] == 8.0
    assert data["event"]["causal_adequacy"] == "partial"
    assert data["idea_adequacy"] == "adequate"
    assert data["affect"] == "sadness"
    assert data["mode"] == "passive"
    assert len(data["derivations"]) >= 4


def test_transition_json_round_trips() -> None:
    state = AgentState(agent_id="agent-1", name="Spinoza", power=10.0)
    event = WorldEvent(
        event_id="event-1",
        description="a self-explained action with confused understanding",
        power_delta=2.0,
        causal_adequacy=CausalAdequacy.ADEQUATE,
        idea_adequacy=IdeaAdequacy.INADEQUATE,
    )
    transition = step(state, event)

    restored = Transition.from_json(transition.to_json())

    assert restored == transition
    assert restored.affect is Affect.JOY
    assert restored.mode is Mode.ACTIVE
    assert restored.idea_adequacy is IdeaAdequacy.INADEQUATE


def test_serialization_helpers_round_trip_transition() -> None:
    transition = step(
        AgentState(agent_id="agent-1", name="Spinoza", power=0.0),
        WorldEvent(
            event_id="event-1",
            description="neutral event",
            power_delta=0.0,
            causal_adequacy=CausalAdequacy.PARTIAL,
            idea_adequacy=IdeaAdequacy.ADEQUATE,
        ),
    )

    assert to_dict(transition) == transition.to_dict()
    assert transition_from_json(to_json(transition)) == transition
