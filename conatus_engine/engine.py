"""Pure transition rules for Conatus Engine."""

from __future__ import annotations

from conatus_engine.models import (
    Affect,
    AgentState,
    CausalAdequacy,
    Derivation,
    Mode,
    Transition,
    WorldEvent,
)


def classify_affect(power_delta: float) -> Affect:
    """Classify joy, sadness, or neutrality from a power change."""

    if power_delta > 0:
        return Affect.JOY
    if power_delta < 0:
        return Affect.SADNESS
    return Affect.NEUTRAL


def classify_mode(causal_adequacy: CausalAdequacy) -> Mode:
    """Classify active or passive mode from causal adequacy alone."""

    if causal_adequacy is CausalAdequacy.ADEQUATE:
        return Mode.ACTIVE
    return Mode.PASSIVE


def _build_derivations(
    before: AgentState,
    after: AgentState,
    event: WorldEvent,
    affect: Affect,
    mode: Mode,
) -> tuple[Derivation, ...]:
    """Build the mechanical derivation trace for one transition."""

    return (
        Derivation(
            rule_id="power.update",
            premises=(
                f"before.power={before.power}",
                f"event.power_delta={event.power_delta}",
            ),
            conclusion=f"after.power={after.power}",
            explanation=(
                "現段階では、出来事に与えられた力能変化量を現在の力能に加算します。"
            ),
        ),
        Derivation(
            rule_id="affect.from_power_change",
            premises=(f"event.power_delta={event.power_delta}",),
            conclusion=f"affect={affect.value}",
            explanation="力能が増えれば喜び、減れば悲しみ、変化しなければ中立とします。",
        ),
        Derivation(
            rule_id="mode.from_causal_adequacy",
            premises=(f"event.causal_adequacy={event.causal_adequacy.value}",),
            conclusion=f"mode={mode.value}",
            explanation=(
                "能動／受動は、原因理解ではなく、結果が本人自身の本性・力から"
                "十分に説明できるかで判定します。"
            ),
        ),
        Derivation(
            rule_id="idea.record_adequacy",
            premises=(f"event.idea_adequacy={event.idea_adequacy.value}",),
            conclusion=f"idea_adequacy={event.idea_adequacy.value}",
            explanation="観念の十分性は、能動／受動とは独立した評価結果として記録します。",
        ),
    )


def step(state: AgentState, event: WorldEvent) -> Transition:
    """Apply one world event to an agent state and return a transition."""

    after = AgentState(
        agent_id=state.agent_id,
        name=state.name,
        power=state.power + event.power_delta,
    )
    affect = classify_affect(event.power_delta)
    mode = classify_mode(event.causal_adequacy)

    return Transition(
        before=state,
        after=after,
        event=event,
        affect=affect,
        mode=mode,
        idea_adequacy=event.idea_adequacy,
        derivations=_build_derivations(state, after, event, affect, mode),
    )


class ConatusEngine:
    """A small reusable engine wrapper around the pure step function."""

    def step(self, state: AgentState, event: WorldEvent) -> Transition:
        """Apply one world event to an agent state."""

        return step(state, event)
