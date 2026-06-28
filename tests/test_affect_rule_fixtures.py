import pytest

from conatus_engine.affect_catalog import load_affect_catalog
from conatus_engine.affect_rules import evaluate_affect, make_empty_feature
from conatus_engine.diary_analyzer import (
    ActionTendency,
    Appraisal,
    AttentionState,
    CausalLink,
    EntityRef,
    EntityStance,
    EpisodeFeatureSchema,
    EvidenceSpan,
    PowerComponents,
    SocialEvent,
    TemporalAppraisal,
)


EVIDENCE_TEXT = "fixture evidence"


def ev() -> list[EvidenceSpan]:
    return [EvidenceSpan(quote=EVIDENCE_TEXT, start_char=0, end_char=len(EVIDENCE_TEXT))]


def person(entity_id: str = "person-1") -> EntityRef:
    return EntityRef(entity_id=entity_id, kind="person", text=entity_id, evidence=ev())


def cause(effect: str, mode: str, entity_id: str | None) -> CausalLink:
    return CausalLink(effect=effect, mode=mode, cause_entity_id=entity_id, evidence=ev(), confidence=0.9)


def stance(entity_id: str, valence: str) -> EntityStance:
    return EntityStance(target_entity_id=entity_id, valence=valence, evidence=ev(), confidence=0.9)


def attention(mode: str, entity_id: str | None = "person-1") -> AttentionState:
    return AttentionState(target_entity_id=entity_id, mode=mode, evidence=ev(), confidence=0.9)


def social(
    effect: str,
    *,
    actor: str | None,
    recipient: str | None,
    similar: str = "unknown",
) -> SocialEvent:
    return SocialEvent(
        actor_entity_id=actor,
        recipient_entity_id=recipient,
        effect=effect,
        recipient_similar_to_self=similar,
        evidence=ev(),
        confidence=0.9,
    )


def appraisal(
    dimension: str,
    *,
    target: str | None,
    level: str = "unknown",
    bias: str = "unknown",
    judgment: str = "none",
) -> Appraisal:
    return Appraisal(
        target_entity_id=target,
        dimension=dimension,
        level=level,
        bias=bias,
        imagined_social_judgment=judgment,
        evidence=ev(),
        confidence=0.9,
    )


def action(
    goal: str,
    *,
    target: str | None = None,
    status: str = "intended",
    origin: str = "self_generated",
    model: str | None = None,
    blocker: str = "none",
    peer_norm: str = "not_applicable",
    domain: str = "none",
    excessiveness: str = "ordinary",
) -> ActionTendency:
    return ActionTendency(
        goal=goal,
        target_entity_id=target,
        status=status,
        origin=origin,
        model_entity_id=model,
        blocker=blocker,
        peer_norm=peer_norm,
        domain=domain,
        excessiveness=excessiveness,
        evidence=ev(),
        confidence=0.9,
    )


def temporal(
    *,
    orientation: str = "unknown",
    representation: str = "unknown",
    certainty: str = "unknown",
    outcome: str = "unknown",
    availability: str = "unknown",
) -> TemporalAppraisal:
    return TemporalAppraisal(
        orientation=orientation,
        representation=representation,
        certainty=certainty,
        outcome_vs_expectation=outcome,
        target_availability=availability,
        evidence=ev(),
        confidence=0.9,
    )


def feature(
    *,
    inc: int = 0,
    dec: int = 0,
    people: tuple[str, ...] = (),
    causes: list[CausalLink] | None = None,
    stances: list[EntityStance] | None = None,
    attentions: list[AttentionState] | None = None,
    temp: TemporalAppraisal | None = None,
    socials: list[SocialEvent] | None = None,
    appraisals: list[Appraisal] | None = None,
    actions: list[ActionTendency] | None = None,
) -> EpisodeFeatureSchema:
    entities = [EntityRef(entity_id="self", kind="self", text="self", evidence=[])]
    entities.extend(person(entity_id) for entity_id in people)
    return EpisodeFeatureSchema(
        episode_id="episode-1",
        start_char=0,
        end_char=len(EVIDENCE_TEXT),
        text=EVIDENCE_TEXT,
        summary=EVIDENCE_TEXT,
        entities=entities,
        power_components=PowerComponents(
            increase_intensity=inc,
            decrease_intensity=dec,
            increase_evidence=ev() if inc else [],
            decrease_evidence=ev() if dec else [],
        ),
        causal_links=causes or [],
        entity_stances=stances or [],
        attention_states=attentions or [],
        temporal_appraisal=temp or temporal(),
        social_events=socials or [],
        appraisals=appraisals or [],
        action_tendencies=actions or [],
        extraction_confidence=0.9,
    )


POSITIVE_CASES = {
    "P3-DA-01": (feature(actions=[action("possess")]), "matched"),
    "P3-DA-02": (feature(inc=3), "matched"),
    "P3-DA-03": (feature(dec=3), "matched"),
    "P3-DA-04": (feature(people=("person-1",), attentions=[attention("novel_fixation")]), "matched"),
    "P3-DA-05": (feature(people=("person-1",), attentions=[attention("low_salience")]), "matched"),
    "P3-DA-06": (feature(inc=3, people=("person-1",), causes=[cause("increase", "direct_external", "person-1")]), "matched"),
    "P3-DA-07": (feature(dec=3, people=("person-1",), causes=[cause("decrease", "direct_external", "person-1")]), "matched"),
    "P3-DA-08": (feature(inc=3, people=("person-1",), causes=[cause("increase", "accidental_external", "person-1")]), "matched"),
    "P3-DA-09": (feature(dec=3, people=("person-1",), causes=[cause("decrease", "accidental_external", "person-1")]), "matched"),
    "P3-DA-10": (feature(inc=3, people=("person-1",), causes=[cause("increase", "direct_external", "person-1")], attentions=[attention("novel_fixation", "person-1")]), "matched"),
    "P3-DA-11": (feature(inc=3, people=("person-1",), stances=[stance("person-1", "negative")], attentions=[attention("low_salience", "person-1")]), "matched"),
    "P3-DA-12": (feature(inc=3, temp=temporal(orientation="future", certainty="uncertain")), "matched"),
    "P3-DA-13": (feature(dec=3, temp=temporal(orientation="future", certainty="uncertain")), "matched"),
    "P3-DA-14": (feature(inc=3, temp=temporal(orientation="past", certainty="resolved")), "matched"),
    "P3-DA-15": (feature(dec=3, temp=temporal(orientation="past", certainty="resolved")), "matched"),
    "P3-DA-16": (feature(inc=3, temp=temporal(orientation="past", outcome="better")), "matched"),
    "P3-DA-17": (feature(dec=3, temp=temporal(orientation="past", outcome="worse")), "matched"),
    "P3-DA-18": (feature(dec=3, people=("person-1", "person-2"), socials=[social("harm", actor="person-2", recipient="person-1", similar="present")]), "matched"),
    "P3-DA-19": (feature(inc=3, people=("person-1", "person-2"), causes=[cause("increase", "direct_external", "person-1")], socials=[social("benefit", actor="person-1", recipient="person-2")]), "matched"),
    "P3-DA-20": (feature(dec=3, people=("person-1", "person-2"), causes=[cause("decrease", "direct_external", "person-1")], socials=[social("harm", actor="person-1", recipient="person-2")]), "matched"),
    "P3-DA-21": (feature(people=("person-1",), stances=[stance("person-1", "positive")], appraisals=[appraisal("other_person", target="person-1", bias="over")]), "matched"),
    "P3-DA-22": (feature(people=("person-1",), stances=[stance("person-1", "negative")], appraisals=[appraisal("other_person", target="person-1", bias="under")]), "matched"),
    "P3-DA-23": (feature(dec=3, people=("person-1",), stances=[stance("person-1", "negative")], socials=[social("good_fortune", actor=None, recipient="person-1")]), "matched"),
    "P3-DA-24": (feature(dec=3, people=("person-1",), stances=[stance("person-1", "positive")], socials=[social("bad_fortune", actor=None, recipient="person-1")]), "matched"),
    "P3-DA-25": (feature(inc=3, appraisals=[appraisal("self_power", target="self", level="high")]), "matched"),
    "P3-DA-26": (feature(dec=3, appraisals=[appraisal("self_power", target="self", level="low")]), "matched"),
    "P3-DA-27": (feature(dec=3, appraisals=[appraisal("self_action", target="self", level="low")]), "matched"),
    "P3-DA-28": (feature(stances=[stance("self", "positive")], appraisals=[appraisal("self_person", target="self", bias="over")]), "matched"),
    "P3-DA-29": (feature(dec=3, appraisals=[appraisal("self_person", target="self", bias="under")]), "matched"),
    "P3-DA-30": (feature(inc=3, appraisals=[appraisal("self_action", target="self", judgment="praise")]), "matched"),
    "P3-DA-31": (feature(dec=3, appraisals=[appraisal("self_action", target="self", judgment="blame")]), "matched"),
    "P3-DA-32": (feature(actions=[action("possess", status="blocked", blocker="target_absent")], temp=temporal(representation="memory", availability="absent")), "matched"),
    "P3-DA-33": (feature(people=("person-1",), actions=[action("possess", origin="imitated", model="person-1")]), "matched"),
    "P3-DA-34": (feature(people=("person-1",), socials=[social("benefit", actor="person-1", recipient="self")], stances=[stance("person-1", "positive")], actions=[action("benefit", target="person-1")]), "matched"),
    "P3-DA-35": (feature(people=("person-1", "person-2"), socials=[social("harm", actor="person-2", recipient="person-1")], actions=[action("benefit", target="person-1")]), "matched"),
    "P3-DA-36": (feature(people=("person-1",), stances=[stance("person-1", "negative")], actions=[action("harm", target="person-1")]), "matched"),
    "P3-DA-37": (feature(people=("person-1",), socials=[social("harm", actor="person-1", recipient="self")], stances=[stance("person-1", "negative")], actions=[action("harm", target="person-1")]), "matched"),
    "P3-DA-38": (feature(people=("person-1",), stances=[stance("person-1", "positive")], actions=[action("harm", target="person-1")]), "matched"),
    "P3-DA-39": (feature(actions=[action("avoid", blocker="lesser_evil_tradeoff")]), "matched"),
    "P3-DA-40": (feature(actions=[action("perform", peer_norm="peers_fear")]), "matched"),
    "P3-DA-41": (feature(actions=[action("perform", status="blocked", blocker="fear", peer_norm="peers_dare")]), "candidate"),
    "P3-DA-42": (feature(actions=[action("avoid", status="blocked", blocker="wonder")]), "matched"),
    "P3-DA-43": (feature(actions=[action("please")]), "matched"),
    "P3-DA-44": (feature(actions=[action("seek_esteem", domain="esteem", excessiveness="excessive")]), "candidate"),
    "P3-DA-45": (feature(actions=[action("possess", domain="food", excessiveness="excessive")]), "candidate"),
    "P3-DA-46": (feature(actions=[action("possess", domain="alcohol", excessiveness="excessive")]), "candidate"),
    "P3-DA-47": (feature(actions=[action("possess", domain="wealth", excessiveness="excessive")]), "candidate"),
    "P3-DA-48": (feature(actions=[action("possess", domain="sex", excessiveness="excessive")]), "candidate"),
}


@pytest.mark.parametrize("definition", load_affect_catalog(), ids=lambda item: item.canonical_id)
def test_each_affect_has_positive_fixture(definition) -> None:
    fixture, expected = POSITIVE_CASES[definition.canonical_id]

    result = evaluate_affect(definition, fixture)

    assert result.status == expected
    assert result.trace.satisfied_conditions


@pytest.mark.parametrize("definition", load_affect_catalog(), ids=lambda item: item.canonical_id)
def test_each_affect_has_boundary_negative_fixture(definition) -> None:
    result = evaluate_affect(definition, make_empty_feature())

    assert result.status == "insufficient_evidence"
