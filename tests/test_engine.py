from conatus_engine import ConatusEngine
from conatus_engine.engine import step
from conatus_engine.models import (
    Affect,
    AgentState,
    CausalAdequacy,
    IdeaAdequacy,
    Mode,
    WorldEvent,
)


def make_state(power: float = 10.0) -> AgentState:
    return AgentState(agent_id="agent-1", name="Spinoza", power=power)


def make_event(
    *,
    power_delta: float,
    causal_adequacy: CausalAdequacy,
    idea_adequacy: IdeaAdequacy,
) -> WorldEvent:
    return WorldEvent(
        event_id="event-1",
        description="a studied encounter",
        power_delta=power_delta,
        causal_adequacy=causal_adequacy,
        idea_adequacy=idea_adequacy,
    )


def test_power_increase_adequate_cause_adequate_idea_is_joy_active() -> None:
    state = make_state()
    event = make_event(
        power_delta=2.5,
        causal_adequacy=CausalAdequacy.ADEQUATE,
        idea_adequacy=IdeaAdequacy.ADEQUATE,
    )

    transition = step(state, event)

    assert transition.before == state
    assert transition.after.power == state.power + event.power_delta
    assert transition.affect is Affect.JOY
    assert transition.mode is Mode.ACTIVE
    assert transition.idea_adequacy is IdeaAdequacy.ADEQUATE


def test_power_decrease_partial_cause_adequate_idea_is_sadness_passive() -> None:
    state = make_state()
    event = make_event(
        power_delta=-3.0,
        causal_adequacy=CausalAdequacy.PARTIAL,
        idea_adequacy=IdeaAdequacy.ADEQUATE,
    )

    transition = step(state, event)

    assert transition.affect is Affect.SADNESS
    assert transition.mode is Mode.PASSIVE
    assert transition.idea_adequacy is IdeaAdequacy.ADEQUATE


def test_power_increase_adequate_cause_inadequate_idea_is_active() -> None:
    state = make_state()
    event = make_event(
        power_delta=1.0,
        causal_adequacy=CausalAdequacy.ADEQUATE,
        idea_adequacy=IdeaAdequacy.INADEQUATE,
    )

    transition = step(state, event)

    assert transition.affect is Affect.JOY
    assert transition.mode is Mode.ACTIVE
    assert transition.idea_adequacy is IdeaAdequacy.INADEQUATE


def test_no_power_change_is_neutral() -> None:
    state = make_state()
    event = make_event(
        power_delta=0.0,
        causal_adequacy=CausalAdequacy.PARTIAL,
        idea_adequacy=IdeaAdequacy.INADEQUATE,
    )

    transition = step(state, event)

    assert transition.after.power == state.power
    assert transition.affect is Affect.NEUTRAL


def test_step_does_not_mutate_input_state() -> None:
    state = make_state(power=4.0)
    event = make_event(
        power_delta=5.0,
        causal_adequacy=CausalAdequacy.ADEQUATE,
        idea_adequacy=IdeaAdequacy.ADEQUATE,
    )

    transition = step(state, event)

    assert state.power == 4.0
    assert transition.before == state
    assert transition.after != state


def test_step_is_deterministic_for_same_inputs() -> None:
    state = make_state()
    event = make_event(
        power_delta=2.0,
        causal_adequacy=CausalAdequacy.ADEQUATE,
        idea_adequacy=IdeaAdequacy.ADEQUATE,
    )

    assert step(state, event) == step(state, event)


def test_derivations_contain_required_rule_ids() -> None:
    transition = step(
        make_state(),
        make_event(
            power_delta=2.0,
            causal_adequacy=CausalAdequacy.ADEQUATE,
            idea_adequacy=IdeaAdequacy.ADEQUATE,
        ),
    )

    rule_ids = {derivation.rule_id for derivation in transition.derivations}

    assert len(transition.derivations) >= 4
    assert {
        "power.update",
        "affect.from_power_change",
        "mode.from_causal_adequacy",
        "idea.record_adequacy",
    } <= rule_ids


def test_engine_class_delegates_to_step() -> None:
    state = make_state()
    event = make_event(
        power_delta=1.0,
        causal_adequacy=CausalAdequacy.ADEQUATE,
        idea_adequacy=IdeaAdequacy.ADEQUATE,
    )

    assert ConatusEngine().step(state, event) == step(state, event)
