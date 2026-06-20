import math

import pytest

from conatus_engine.models import (
    AgentState,
    CausalAdequacy,
    Derivation,
    IdeaAdequacy,
    WorldEvent,
)


def test_causal_and_idea_adequacy_can_differ() -> None:
    event = WorldEvent(
        event_id="event-1",
        description="原因は理解しているが本人だけでは十分に説明できない出来事",
        power_delta=-1.0,
        causal_adequacy=CausalAdequacy.PARTIAL,
        idea_adequacy=IdeaAdequacy.ADEQUATE,
    )

    assert event.causal_adequacy is CausalAdequacy.PARTIAL
    assert event.idea_adequacy is IdeaAdequacy.ADEQUATE


@pytest.mark.parametrize("power", [math.nan, math.inf, -math.inf])
def test_agent_state_rejects_non_finite_power(power: float) -> None:
    with pytest.raises(ValueError):
        AgentState(agent_id="agent-1", name="Spinoza", power=power)


@pytest.mark.parametrize("power_delta", [math.nan, math.inf, -math.inf])
def test_world_event_rejects_non_finite_power_delta(power_delta: float) -> None:
    with pytest.raises(ValueError):
        WorldEvent(
            event_id="event-1",
            description="invalid power delta",
            power_delta=power_delta,
            causal_adequacy=CausalAdequacy.ADEQUATE,
            idea_adequacy=IdeaAdequacy.ADEQUATE,
        )


@pytest.mark.parametrize(
    ("agent_id", "name"),
    [("", "Spinoza"), ("agent-1", "")],
)
def test_agent_state_rejects_empty_id_or_name(agent_id: str, name: str) -> None:
    with pytest.raises(ValueError):
        AgentState(agent_id=agent_id, name=name, power=1.0)


@pytest.mark.parametrize(
    ("event_id", "description"),
    [("", "dialogue"), ("event-1", "")],
)
def test_world_event_rejects_empty_id_or_description(
    event_id: str, description: str
) -> None:
    with pytest.raises(ValueError):
        WorldEvent(
            event_id=event_id,
            description=description,
            power_delta=1.0,
            causal_adequacy=CausalAdequacy.ADEQUATE,
            idea_adequacy=IdeaAdequacy.ADEQUATE,
        )


def test_derivation_rejects_empty_core_fields() -> None:
    with pytest.raises(ValueError):
        Derivation(rule_id="", premises=(), conclusion="x", explanation="x")
