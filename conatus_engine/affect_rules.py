"""Deterministic 48-affect rule engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from pydantic import BaseModel

from conatus_engine.affect_catalog import (
    AffectDefinition,
    ClassificationKind,
    TemporalScope,
    load_affect_catalog,
)
from conatus_engine.diary_analyzer import (
    ActionTendency,
    Appraisal,
    AttentionState,
    CausalLink,
    EntityStance,
    EpisodeFeatureSchema,
    EvidenceSpan,
    SocialEvent,
)


BASE_AFFECT_IDS = {
    "P3-DA-01",
    "P3-DA-02",
    "P3-DA-03",
}
LONGITUDINAL_CANDIDATE_IDS = {
    "P3-DA-41",
    "P3-DA-44",
    "P3-DA-45",
    "P3-DA-46",
    "P3-DA-47",
    "P3-DA-48",
}
PRIMARY_PRIORITY = {
    "P3-DA-27": 30,
    "P3-DA-34": 30,
    "P3-DA-36": 25,
    "P3-DA-37": 28,
    "P3-DA-25": 12,
    "P3-DA-02": 0,
    "P3-DA-03": 0,
    "P3-DA-01": 0,
}

AffectStatus = Literal["matched", "candidate", "insufficient_evidence", "contradicted"]
AffectRole = Literal["primary", "base", "coexisting", "candidate", "unclassified"]


class RuleTrace(BaseModel):
    """Trace of which atomic conditions were used for one affect judgment."""

    affect_id: str
    status: AffectStatus
    satisfied_conditions: list[str]
    missing_conditions: list[str]
    contradicted_conditions: list[str]
    evidence: list[EvidenceSpan]


@dataclass(frozen=True)
class HistoryMetrics:
    """Aggregated history metrics for period/longitudinal affects."""

    domain: str
    occurrence_count: int
    window_days: int
    repeated: bool
    persistent: bool
    restrained_repeatedly: bool


@dataclass(frozen=True)
class LongitudinalAffectPolicy:
    """Policy threshold for promoting period candidates to matched."""

    min_occurrences: int = 3
    window_days: int = 30


@dataclass(frozen=True)
class AffectEvaluation:
    affect_id: str
    japanese_name: str
    status: str
    reason: str
    evidence_text: str
    confidence: float
    trace: RuleTrace


@dataclass(frozen=True)
class AffectRoleEvaluation:
    affect_id: str
    japanese_name: str
    status: str
    role: AffectRole
    reason: str
    evidence_text: str
    confidence: float
    trace: RuleTrace


class AffectRuleContext:
    """Search helpers over an EpisodeFeatureSchema."""

    def __init__(self, feature: EpisodeFeatureSchema) -> None:
        self.feature = feature

    @property
    def increase(self) -> int:
        return self.feature.power_components.increase_intensity

    @property
    def decrease(self) -> int:
        return self.feature.power_components.decrease_intensity

    @property
    def conatus_delta(self) -> int:
        return self.increase - self.decrease

    @property
    def confidence(self) -> float:
        return self.feature.extraction_confidence

    def has_increase(self) -> bool:
        return self.increase > 0

    def has_decrease(self) -> bool:
        return self.decrease > 0

    def causes(
        self,
        *,
        effect: str | None = None,
        mode: str | None = None,
        cause: str | None = None,
    ) -> list[CausalLink]:
        return [
            link
            for link in self.feature.causal_links
            if (effect is None or link.effect == effect)
            and (mode is None or link.mode == mode)
            and (cause is None or link.cause_entity_id == cause)
        ]

    def stances(
        self,
        *,
        valence: str | None = None,
        target: str | None = None,
    ) -> list[EntityStance]:
        return [
            stance
            for stance in self.feature.entity_stances
            if (valence is None or stance.valence == valence)
            and (target is None or stance.target_entity_id == target)
        ]

    def attention(
        self,
        *,
        mode: str | None = None,
        target: str | None = None,
    ) -> list[AttentionState]:
        return [
            state
            for state in self.feature.attention_states
            if (mode is None or state.mode == mode)
            and (target is None or state.target_entity_id == target)
        ]

    def social_events(
        self,
        *,
        effect: str | Iterable[str] | None = None,
        actor: str | None = None,
        recipient: str | None = None,
    ) -> list[SocialEvent]:
        effects = {effect} if isinstance(effect, str) else set(effect or [])
        return [
            event
            for event in self.feature.social_events
            if (not effects or event.effect in effects)
            and (actor is None or event.actor_entity_id == actor)
            and (recipient is None or event.recipient_entity_id == recipient)
        ]

    def appraisals(
        self,
        *,
        dimension: str | None = None,
        level: str | None = None,
        bias: str | None = None,
        judgment: str | None = None,
        target: str | None = None,
    ) -> list[Appraisal]:
        return [
            appraisal
            for appraisal in self.feature.appraisals
            if (dimension is None or appraisal.dimension == dimension)
            and (level is None or appraisal.level == level)
            and (bias is None or appraisal.bias == bias)
            and (judgment is None or appraisal.imagined_social_judgment == judgment)
            and (target is None or appraisal.target_entity_id == target)
        ]

    def actions(
        self,
        *,
        goal: str | Iterable[str] | None = None,
        status: str | Iterable[str] | None = None,
        target: str | None = None,
        domain: str | None = None,
        excessiveness: str | None = None,
        origin: str | None = None,
        blocker: str | Iterable[str] | None = None,
        peer_norm: str | None = None,
    ) -> list[ActionTendency]:
        goals = {goal} if isinstance(goal, str) else set(goal or [])
        statuses = {status} if isinstance(status, str) else set(status or [])
        blockers = {blocker} if isinstance(blocker, str) else set(blocker or [])
        return [
            action
            for action in self.feature.action_tendencies
            if (not goals or action.goal in goals)
            and (not statuses or action.status in statuses)
            and (target is None or action.target_entity_id == target)
            and (domain is None or action.domain == domain)
            and (excessiveness is None or action.excessiveness == excessiveness)
            and (origin is None or action.origin == origin)
            and (not blockers or action.blocker in blockers)
            and (peer_norm is None or action.peer_norm == peer_norm)
        ]

    def any_desire_action(self) -> bool:
        return any(
            action.goal not in {"none", "unknown"}
            for action in self.feature.action_tendencies
        )

    def evidence_from(self, *objects: object) -> list[EvidenceSpan]:
        evidence: list[EvidenceSpan] = []
        for obj in objects:
            if obj is None:
                continue
            value = getattr(obj, "evidence", None)
            if isinstance(value, list):
                evidence.extend(span for span in value if isinstance(span, EvidenceSpan))
        return _dedupe_evidence(evidence)

    def evidence_for_power(self, effect: str) -> list[EvidenceSpan]:
        if effect == "increase":
            return self.feature.power_components.increase_evidence
        if effect == "decrease":
            return self.feature.power_components.decrease_evidence
        return []

    def entity_ids(self) -> set[str]:
        return {entity.entity_id for entity in self.feature.entities}


def evaluate_affect(definition: AffectDefinition, features: EpisodeFeatureSchema) -> AffectEvaluation:
    """Evaluate one affect definition against one episode feature set."""

    ctx = AffectRuleContext(features)
    trace = _evaluate_trace(definition.canonical_id, ctx)
    confidence = _confidence(ctx, trace)
    reason = _reason(definition, trace)
    return AffectEvaluation(
        affect_id=definition.canonical_id,
        japanese_name=definition.japanese_name,
        status=trace.status,
        reason=reason,
        evidence_text=_trace_evidence_text(trace) or features.text,
        confidence=confidence,
        trace=trace,
    )


def evaluate_all_affects(features: EpisodeFeatureSchema) -> list[AffectEvaluation]:
    """Evaluate all 48 affect definitions."""

    return [evaluate_affect(definition, features) for definition in load_affect_catalog()]


def select_primary_affect(features: EpisodeFeatureSchema) -> AffectEvaluation:
    """Select one representative affect for one extracted episode."""

    definitions = load_affect_catalog()
    by_id = {definition.canonical_id: definition for definition in definitions}
    results = [evaluate_affect(definition, features) for definition in definitions]
    selectable = [result for result in results if result.status in {"matched", "candidate"}]
    if selectable:
        return max(selectable, key=lambda result: _primary_score(result, by_id[result.affect_id]))

    trace = RuleTrace(
        affect_id="UNCLASSIFIED",
        status="insufficient_evidence",
        satisfied_conditions=[],
        missing_conditions=["48情動を代表するだけの原子的特徴が不足"],
        contradicted_conditions=[],
        evidence=[],
    )
    return AffectEvaluation(
        affect_id="UNCLASSIFIED",
        japanese_name="未分類",
        status="insufficient_evidence",
        reason="必要な意味情報が不足しているため、48情動の代表情動を決定できません。",
        evidence_text=features.text,
        confidence=_base_conf(features, 0.55),
        trace=trace,
    )


def classify_affect_roles(features: EpisodeFeatureSchema) -> list[AffectRoleEvaluation]:
    """Evaluate one episode and assign display/storage roles to all relevant affects."""

    evaluations = evaluate_all_affects(features)
    primary = select_primary_affect(features)
    if primary.affect_id == "UNCLASSIFIED":
        return [_with_role(primary, "unclassified")]

    results: list[AffectRoleEvaluation] = []
    primary_saved = False
    for evaluation in evaluations:
        if evaluation.affect_id == primary.affect_id:
            results.append(_with_role(evaluation, "primary"))
            primary_saved = True
        elif evaluation.status == "matched" and evaluation.affect_id in BASE_AFFECT_IDS:
            results.append(_with_role(evaluation, "base"))
        elif evaluation.status == "matched":
            results.append(_with_role(evaluation, "coexisting"))
        elif evaluation.status == "candidate":
            results.append(_with_role(evaluation, "candidate"))

    if not primary_saved:
        results.insert(0, _with_role(primary, "primary"))
    return results


def _evaluate_trace(pid: str, ctx: AffectRuleContext) -> RuleTrace:
    if pid == "P3-DA-01":
        return _trace(pid, _cond(ctx.any_desire_action(), "goalがnone/unknown以外のActionTendencyがある"))
    if pid == "P3-DA-02":
        return _trace(pid, _cond(ctx.has_increase(), "increase_intensity > 0"), ctx.evidence_for_power("increase"))
    if pid == "P3-DA-03":
        return _trace(pid, _cond(ctx.has_decrease(), "decrease_intensity > 0"), ctx.evidence_for_power("decrease"))
    if pid == "P3-DA-04":
        attention = ctx.attention(mode="novel_fixation")
        return _trace(pid, _cond(bool(attention), "attention.mode == novel_fixation"), ctx.evidence_from(*attention))
    if pid == "P3-DA-05":
        attention = ctx.attention(mode="low_salience")
        return _trace(pid, _cond(bool(attention), "attention.mode == low_salience"), ctx.evidence_from(*attention))
    if pid == "P3-DA-06":
        causes = ctx.causes(effect="increase", mode="direct_external")
        return _trace(
            pid,
            _cond(ctx.has_increase(), "increase_intensity > 0"),
            _cond(bool(causes), "increaseにdirect_externalの原因がある"),
            ctx.evidence_for_power("increase") + ctx.evidence_from(*causes),
        )
    if pid == "P3-DA-07":
        causes = ctx.causes(effect="decrease", mode="direct_external")
        return _trace(
            pid,
            _cond(ctx.has_decrease(), "decrease_intensity > 0"),
            _cond(bool(causes), "decreaseにdirect_externalの原因がある"),
            ctx.evidence_for_power("decrease") + ctx.evidence_from(*causes),
        )
    if pid == "P3-DA-08":
        causes = ctx.causes(effect="increase", mode="accidental_external")
        return _trace(
            pid,
            _cond(ctx.has_increase(), "increase_intensity > 0"),
            _cond(bool(causes), "increaseにaccidental_externalの原因がある"),
            ctx.evidence_for_power("increase") + ctx.evidence_from(*causes),
        )
    if pid == "P3-DA-09":
        causes = ctx.causes(effect="decrease", mode="accidental_external")
        return _trace(
            pid,
            _cond(ctx.has_decrease(), "decrease_intensity > 0"),
            _cond(bool(causes), "decreaseにaccidental_externalの原因がある"),
            ctx.evidence_for_power("decrease") + ctx.evidence_from(*causes),
        )
    if pid == "P3-DA-10":
        love_causes = ctx.causes(effect="increase", mode="direct_external")
        matched = [
            cause
            for cause in love_causes
            if cause.cause_entity_id and ctx.attention(mode="novel_fixation", target=cause.cause_entity_id)
        ]
        return _trace(
            pid,
            _cond(bool(love_causes), "愛の条件となるdirect_externalのincrease原因がある"),
            _cond(bool(matched), "愛の原因とnovel_fixationの対象が同じentity_id"),
            ctx.evidence_from(*love_causes, *ctx.attention(mode="novel_fixation")),
        )
    if pid == "P3-DA-11":
        targets = {
            state.target_entity_id
            for state in ctx.attention(mode="low_salience")
            if state.target_entity_id is not None
        }
        matched = [target for target in targets if ctx.stances(valence="negative", target=target)]
        return _trace(
            pid,
            _cond(ctx.has_increase(), "increase_intensity > 0"),
            _cond(bool(matched), "同じ対象へのnegative stanceとlow_salienceがある"),
            ctx.evidence_for_power("increase") + ctx.evidence_from(*ctx.attention(mode="low_salience")),
        )
    if pid in {"P3-DA-12", "P3-DA-13", "P3-DA-14", "P3-DA-15"}:
        return _temporal_trace(pid, ctx)
    if pid == "P3-DA-16":
        return _trace(
            pid,
            _cond(ctx.has_increase(), "increase_intensity > 0"),
            _cond(ctx.feature.temporal_appraisal.orientation == "past", "orientation == past"),
            _cond(ctx.feature.temporal_appraisal.outcome_vs_expectation == "better", "outcome_vs_expectation == better"),
            ctx.evidence_for_power("increase") + ctx.feature.temporal_appraisal.evidence,
        )
    if pid == "P3-DA-17":
        return _trace(
            pid,
            _cond(ctx.has_decrease(), "decrease_intensity > 0"),
            _cond(ctx.feature.temporal_appraisal.orientation == "past", "orientation == past"),
            _cond(ctx.feature.temporal_appraisal.outcome_vs_expectation == "worse", "outcome_vs_expectation == worse"),
            ctx.evidence_for_power("decrease") + ctx.feature.temporal_appraisal.evidence,
        )
    if pid == "P3-DA-18":
        events = [
            event
            for event in ctx.social_events(effect={"harm", "bad_fortune"})
            if event.recipient_entity_id != "self" and event.recipient_similar_to_self == "present"
        ]
        return _trace(
            pid,
            _cond(ctx.has_decrease(), "decrease_intensity > 0"),
            _cond(bool(events), "自分に似た他者にharmまたはbad_fortuneがある"),
            ctx.evidence_for_power("decrease") + ctx.evidence_from(*events),
        )
    if pid == "P3-DA-19":
        events = ctx.social_events(effect="benefit")
        matched = [
            event
            for event in events
            if event.actor_entity_id and ctx.causes(effect="increase", cause=event.actor_entity_id)
        ]
        return _trace(
            pid,
            _cond(bool(events), "人物Aが人物Bへbenefit"),
            _cond(bool(matched), "人物Aを原因とするincreaseがある"),
            ctx.evidence_from(*events, *ctx.causes(effect="increase")),
        )
    if pid == "P3-DA-20":
        events = ctx.social_events(effect="harm")
        matched = [
            event
            for event in events
            if event.actor_entity_id and ctx.causes(effect="decrease", cause=event.actor_entity_id)
        ]
        return _trace(
            pid,
            _cond(bool(events), "人物Aが人物Bへharm"),
            _cond(bool(matched), "人物Aを原因とするdecreaseがある"),
            ctx.evidence_from(*events, *ctx.causes(effect="decrease")),
        )
    if pid in {"P3-DA-21", "P3-DA-22"}:
        return _stance_appraisal_trace(pid, ctx)
    if pid in {"P3-DA-23", "P3-DA-24"}:
        return _fortune_stance_trace(pid, ctx)
    if pid == "P3-DA-25":
        appraisals = ctx.appraisals(dimension="self_power", level="high")
        return _trace(pid, _cond(ctx.has_increase(), "increase_intensity > 0"), _cond(bool(appraisals), "self_power appraisal.level == high"), ctx.evidence_for_power("increase") + ctx.evidence_from(*appraisals))
    if pid == "P3-DA-26":
        appraisals = ctx.appraisals(dimension="self_power", level="low")
        return _trace(pid, _cond(ctx.has_decrease(), "decrease_intensity > 0"), _cond(bool(appraisals), "self_power appraisal.level == low"), ctx.evidence_for_power("decrease") + ctx.evidence_from(*appraisals))
    if pid == "P3-DA-27":
        appraisals = ctx.appraisals(dimension="self_action", level="low")
        return _trace(pid, _cond(ctx.has_decrease(), "decrease_intensity > 0"), _cond(bool(appraisals), "自分の行為への低い評価がある"), ctx.evidence_for_power("decrease") + ctx.evidence_from(*appraisals))
    if pid == "P3-DA-28":
        return _trace(
            pid,
            _cond(bool(ctx.stances(valence="positive", target="self")), "selfへのpositive stance"),
            _cond(bool(ctx.appraisals(dimension="self_person", bias="over")), "self_person appraisal.bias == over"),
            ctx.evidence_from(*ctx.stances(target="self"), *ctx.appraisals(dimension="self_person")),
        )
    if pid == "P3-DA-29":
        return _trace(
            pid,
            _cond(ctx.has_decrease(), "decrease_intensity > 0"),
            _cond(bool(ctx.appraisals(dimension="self_person", bias="under")), "self_person appraisal.bias == under"),
            ctx.evidence_for_power("decrease") + ctx.evidence_from(*ctx.appraisals(dimension="self_person")),
        )
    if pid == "P3-DA-30":
        appraisals = ctx.appraisals(dimension="self_action", judgment="praise")
        return _trace(pid, _cond(ctx.has_increase(), "increase_intensity > 0"), _cond(bool(appraisals), "self_action appraisal.imagined_social_judgment == praise"), ctx.evidence_for_power("increase") + ctx.evidence_from(*appraisals))
    if pid == "P3-DA-31":
        appraisals = ctx.appraisals(dimension="self_action", judgment="blame")
        return _trace(pid, _cond(ctx.has_decrease(), "decrease_intensity > 0"), _cond(bool(appraisals), "self_action appraisal.imagined_social_judgment == blame"), ctx.evidence_for_power("decrease") + ctx.evidence_from(*appraisals))
    if pid == "P3-DA-32":
        actions = ctx.actions(goal="possess", status="blocked", blocker="target_absent")
        temporal = ctx.feature.temporal_appraisal
        return _trace(
            pid,
            _cond(bool(actions), "goal == possess / status == blocked / blocker == target_absent"),
            _cond(temporal.representation == "memory", "representation == memory"),
            _cond(temporal.target_availability in {"absent", "excluded"}, "target_availabilityがabsentまたはexcluded"),
            ctx.evidence_from(*actions) + temporal.evidence,
        )
    if pid == "P3-DA-33":
        actions = [
            action
            for action in ctx.actions(origin="imitated")
            if action.model_entity_id is not None
        ]
        return _trace(pid, _cond(bool(actions), "origin == imitated かつ model_entity_idが存在"), ctx.evidence_from(*actions))
    if pid == "P3-DA-34":
        events = ctx.social_events(effect="benefit", recipient="self")
        matched_targets = [
            event.actor_entity_id
            for event in events
            if event.actor_entity_id
            and ctx.stances(valence="positive", target=event.actor_entity_id)
            and ctx.actions(goal="benefit", target=event.actor_entity_id)
        ]
        return _trace(
            pid,
            _cond(bool(events), "対象がselfへbenefit"),
            _cond(bool(matched_targets), "同じ対象へのpositive stanceとbenefit行為傾向がある"),
            ctx.evidence_from(*events, *ctx.stances(valence="positive"), *ctx.actions(goal="benefit")),
        )
    if pid == "P3-DA-35":
        events = ctx.social_events(effect={"harm", "bad_fortune"})
        matched = [
            event
            for event in events
            if event.recipient_entity_id and ctx.actions(goal="benefit", target=event.recipient_entity_id)
        ]
        return _trace(pid, _cond(bool(events), "他者にharmまたはbad_fortuneがある"), _cond(bool(matched), "その対象をbenefitしようとするActionTendencyがある"), ctx.evidence_from(*events, *ctx.actions(goal="benefit")))
    if pid == "P3-DA-36":
        return _same_target_action_stance_trace(pid, ctx, action_goal="harm", stance_valence="negative")
    if pid == "P3-DA-37":
        events = ctx.social_events(effect="harm", recipient="self")
        matched = [
            event
            for event in events
            if event.actor_entity_id
            and ctx.stances(valence="negative", target=event.actor_entity_id)
            and ctx.actions(goal="harm", target=event.actor_entity_id)
        ]
        return _trace(pid, _cond(bool(events), "対象がselfへharm"), _cond(bool(matched), "同じ対象へのnegative stanceとharm行為傾向がある"), ctx.evidence_from(*events, *ctx.stances(valence="negative"), *ctx.actions(goal="harm")))
    if pid == "P3-DA-38":
        actions = ctx.actions(goal="harm")
        matched = [
            action
            for action in actions
            if action.target_entity_id and ctx.stances(valence="positive", target=action.target_entity_id)
        ]
        return _trace(pid, _cond(bool(actions), "対象をharmしようとするActionTendencyがある"), _cond(bool(matched), "同じ対象へのpositive stanceがある"), ctx.evidence_from(*actions, *ctx.stances(valence="positive")))
    if pid == "P3-DA-39":
        actions = ctx.actions(goal="avoid", blocker="lesser_evil_tradeoff")
        return _trace(pid, _cond(bool(actions), "大きな害を避けるためのavoid傾向 / blocker == lesser_evil_tradeoff"), ctx.evidence_from(*actions))
    if pid == "P3-DA-40":
        actions = ctx.actions(goal="perform", status={"intended", "performed"}, peer_norm="peers_fear")
        return _trace(pid, _cond(bool(actions), "危険な行為をperformしようとし、peer_norm == peers_fear"), ctx.evidence_from(*actions))
    if pid == "P3-DA-41":
        actions = ctx.actions(status="blocked", blocker="fear", peer_norm="peers_dare")
        return _trace(pid, _cond(bool(actions), "行為への欲望がfearによりblocked / peer_norm == peers_dare"), ctx.evidence_from(*actions), force_candidate=True)
    if pid == "P3-DA-42":
        actions = ctx.actions(goal="avoid", status="blocked", blocker={"wonder", "competing_evil"})
        return _trace(pid, _cond(bool(actions), "害をavoidしようとする行為傾向がwonderまたはcompeting_evilでblocked"), ctx.evidence_from(*actions))
    if pid == "P3-DA-43":
        actions = ctx.actions(goal={"please", "avoid_displeasing"})
        return _trace(pid, _cond(bool(actions), "goal == please または avoid_displeasing"), ctx.evidence_from(*actions))
    if pid == "P3-DA-44":
        actions = ctx.actions(goal="seek_esteem", excessiveness="excessive")
        return _trace(pid, _cond(bool(actions), "goal == seek_esteem / excessiveness == excessive"), ctx.evidence_from(*actions), force_candidate=True)
    if pid == "P3-DA-45":
        return _excess_trace(pid, ctx, "food")
    if pid == "P3-DA-46":
        return _excess_trace(pid, ctx, "alcohol")
    if pid == "P3-DA-47":
        return _excess_trace(pid, ctx, "wealth")
    if pid == "P3-DA-48":
        return _excess_trace(pid, ctx, "sex")

    return _trace(pid, _cond(False, "未実装のルール"))


def _temporal_trace(pid: str, ctx: AffectRuleContext) -> RuleTrace:
    temporal = ctx.feature.temporal_appraisal
    is_increase = pid in {"P3-DA-12", "P3-DA-14"}
    is_uncertain = pid in {"P3-DA-12", "P3-DA-13"}
    return _trace(
        pid,
        _cond(ctx.has_increase() if is_increase else ctx.has_decrease(), "increase_intensity > 0" if is_increase else "decrease_intensity > 0"),
        _cond(temporal.orientation in {"past", "future"}, "orientationがpastまたはfuture"),
        _cond(temporal.certainty == ("uncertain" if is_uncertain else "resolved"), f"certainty == {'uncertain' if is_uncertain else 'resolved'}"),
        (ctx.evidence_for_power("increase" if is_increase else "decrease") + temporal.evidence),
    )


def _stance_appraisal_trace(pid: str, ctx: AffectRuleContext) -> RuleTrace:
    positive = pid == "P3-DA-21"
    stances = ctx.stances(valence="positive" if positive else "negative")
    appraisals = ctx.appraisals(dimension="other_person", bias="over" if positive else "under")
    matched = [
        stance.target_entity_id
        for stance in stances
        if any(appraisal.target_entity_id == stance.target_entity_id for appraisal in appraisals)
    ]
    return _trace(
        pid,
        _cond(bool(stances), f"対象への{'positive' if positive else 'negative'} stance"),
        _cond(bool(appraisals), f"other_person appraisal.bias == {'over' if positive else 'under'}"),
        _cond(bool(matched), "stanceとappraisalの対象IDが同じ"),
        ctx.evidence_from(*stances, *appraisals),
    )


def _fortune_stance_trace(pid: str, ctx: AffectRuleContext) -> RuleTrace:
    envy = pid == "P3-DA-23"
    stances = ctx.stances(valence="negative" if envy else "positive")
    good = ctx.social_events(effect="good_fortune")
    bad = ctx.social_events(effect="bad_fortune")
    if envy:
        fortune_match = (ctx.has_decrease() and bool(good)) or (ctx.has_increase() and bool(bad))
        condition = "他者のgood_fortuneに対するdecrease、またはbad_fortuneに対するincrease"
    else:
        fortune_match = (ctx.has_increase() and bool(good)) or (ctx.has_decrease() and bool(bad))
        condition = "他者のgood_fortuneに対するincrease、またはbad_fortuneに対するdecrease"
    return _trace(
        pid,
        _cond(bool(stances), f"対象への{'negative' if envy else 'positive'} stance"),
        _cond(fortune_match, condition),
        ctx.evidence_from(*stances, *good, *bad) + ctx.evidence_for_power("increase") + ctx.evidence_for_power("decrease"),
    )


def _same_target_action_stance_trace(
    pid: str,
    ctx: AffectRuleContext,
    *,
    action_goal: str,
    stance_valence: str,
) -> RuleTrace:
    actions = ctx.actions(goal=action_goal)
    matched = [
        action
        for action in actions
        if action.target_entity_id and ctx.stances(valence=stance_valence, target=action.target_entity_id)
    ]
    return _trace(
        pid,
        _cond(bool(actions), f"goal == {action_goal} のActionTendencyがある"),
        _cond(bool(matched), f"同じ対象への{stance_valence} stanceがある"),
        ctx.evidence_from(*actions, *ctx.stances(valence=stance_valence)),
    )


def _excess_trace(pid: str, ctx: AffectRuleContext, domain: str) -> RuleTrace:
    actions = ctx.actions(domain=domain, excessiveness="excessive")
    return _trace(
        pid,
        _cond(bool(actions), f"domain == {domain} / excessiveness == excessive"),
        ctx.evidence_from(*actions),
        force_candidate=True,
    )


def _cond(value: bool, text: str) -> tuple[bool, str]:
    return value, text


def _trace(
    affect_id: str,
    *conditions_or_evidence,
    force_candidate: bool = False,
) -> RuleTrace:
    satisfied: list[str] = []
    missing: list[str] = []
    evidence: list[EvidenceSpan] = []
    for item in conditions_or_evidence:
        if isinstance(item, tuple):
            ok, text = item
            if ok:
                satisfied.append(text)
            else:
                missing.append(text)
        elif isinstance(item, list):
            evidence.extend(span for span in item if isinstance(span, EvidenceSpan))
    if missing:
        status: AffectStatus = "insufficient_evidence"
    elif force_candidate or affect_id in LONGITUDINAL_CANDIDATE_IDS:
        status = "candidate"
        missing.append("期間・履歴集約による反復確認")
    else:
        status = "matched"
    return RuleTrace(
        affect_id=affect_id,
        status=status,
        satisfied_conditions=satisfied,
        missing_conditions=missing,
        contradicted_conditions=[],
        evidence=_dedupe_evidence(evidence),
    )


def _dedupe_evidence(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    seen: set[tuple[int, int, str]] = set()
    result: list[EvidenceSpan] = []
    for span in spans:
        key = (span.start_char, span.end_char, span.quote)
        if key not in seen:
            seen.add(key)
            result.append(span)
    return result


def _base_conf(features: EpisodeFeatureSchema, multiplier: float = 1.0) -> float:
    return round(max(0.0, min(features.extraction_confidence * multiplier, 1.0)), 2)


def _confidence(ctx: AffectRuleContext, trace: RuleTrace) -> float:
    if trace.status == "matched":
        multiplier = 1.0
    elif trace.status == "candidate":
        multiplier = 0.75
    else:
        multiplier = 0.55
    evidence_bonus = min(len(trace.evidence), 4) * 0.02
    return round(max(0.0, min(ctx.confidence * multiplier + evidence_bonus, 1.0)), 2)


def _reason(definition: AffectDefinition, trace: RuleTrace) -> str:
    if trace.status not in {"matched", "candidate"}:
        return "必要な意味特徴が不足しています。"
    satisfied = "、".join(trace.satisfied_conditions) if trace.satisfied_conditions else "なし"
    missing = "、".join(trace.missing_conditions) if trace.missing_conditions else "なし"
    return (
        f"原典訳: {definition.japanese_translation} "
        f"判定: satisfied=[{satisfied}] missing=[{missing}]"
    )


def _trace_evidence_text(trace: RuleTrace) -> str:
    return " / ".join(span.quote for span in trace.evidence)


def _with_role(evaluation: AffectEvaluation, role: AffectRole) -> AffectRoleEvaluation:
    return AffectRoleEvaluation(
        affect_id=evaluation.affect_id,
        japanese_name=evaluation.japanese_name,
        status=evaluation.status,
        role=role,
        reason=evaluation.reason,
        evidence_text=evaluation.evidence_text,
        confidence=evaluation.confidence,
        trace=evaluation.trace,
    )


def _primary_score(result: AffectEvaluation, definition: AffectDefinition) -> tuple[int, int, int, int, float, int]:
    status_rank = {
        "matched": 3,
        "candidate": 2,
        "insufficient_evidence": 1,
        "contradicted": 0,
    }.get(result.status, 0)
    specificity = max(_classification_specificity(kind) for kind in definition.classification)
    episode_scope_rank = 0 if definition.temporal_scope in {TemporalScope.PERIOD, TemporalScope.LONGITUDINAL} else 1
    evidence_count = len(result.trace.evidence)
    priority = PRIMARY_PRIORITY.get(result.affect_id, 10)
    return (
        status_rank,
        specificity,
        episode_scope_rank,
        priority,
        result.confidence + evidence_count / 100,
        -definition.number,
    )


def _classification_specificity(kind: ClassificationKind) -> int:
    if kind is ClassificationKind.PRIMARY_AFFECT:
        return 0
    if kind is ClassificationKind.IMAGINATION_STATE:
        return 1
    if kind is ClassificationKind.COMPOSITE_AFFECT:
        return 2
    return 3


def make_empty_feature() -> EpisodeFeatureSchema:
    """Return a valid neutral feature for validation and tests."""

    from conatus_engine.diary_analyzer import (
        EntityRef,
        PowerComponents,
        TemporalAppraisal,
    )

    return EpisodeFeatureSchema(
        episode_id="episode-1",
        start_char=0,
        end_char=10,
        text="validation",
        summary="validation",
        entities=[EntityRef(entity_id="self", kind="self", text="書き手", evidence=[])],
        power_components=PowerComponents(
            increase_intensity=0,
            decrease_intensity=0,
            increase_evidence=[],
            decrease_evidence=[],
        ),
        causal_links=[],
        entity_stances=[],
        attention_states=[],
        temporal_appraisal=TemporalAppraisal(
            orientation="unknown",
            representation="unknown",
            certainty="unknown",
            outcome_vs_expectation="unknown",
            target_availability="unknown",
            evidence=[],
            confidence=0.5,
        ),
        social_events=[],
        appraisals=[],
        action_tendencies=[],
        extraction_confidence=0.5,
    )


def validate_rule_engine() -> list[str]:
    """Validate that every catalog affect has an executable rule."""

    errors: list[str] = []
    results = evaluate_all_affects(make_empty_feature())
    if len(results) != 48:
        errors.append("rule engine must evaluate exactly 48 definitions")
    result_ids = {result.affect_id for result in results}
    catalog_ids = {item.canonical_id for item in load_affect_catalog()}
    if result_ids != catalog_ids:
        errors.append("rule engine IDs must match catalog IDs")
    return errors
