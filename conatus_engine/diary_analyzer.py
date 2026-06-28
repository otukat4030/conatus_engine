"""Diary analyzers for structured episode feature extraction."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from conatus_engine.pricing import TokenUsage, extract_token_usage


EntityKind = Literal[
    "self",
    "person",
    "group",
    "object",
    "event",
    "abstract",
    "unknown",
]
CauseMode = Literal["self", "direct_external", "accidental_external", "none", "unknown"]
PowerEffect = Literal["increase", "decrease", "desire"]
StanceValence = Literal["positive", "negative", "ambivalent", "neutral", "unknown"]
AttentionMode = Literal["novel_fixation", "low_salience", "ordinary", "unknown"]
TemporalOrientation = Literal["past", "present", "future", "mixed", "unknown"]
TemporalRepresentation = Literal["perception", "memory", "anticipation", "unknown"]
TemporalCertainty = Literal["uncertain", "resolved", "not_applicable", "unknown"]
OutcomeVsExpectation = Literal["better", "as_expected", "worse", "not_observed", "unknown"]
TargetAvailability = Literal["present", "absent", "excluded", "unknown"]
SocialEffect = Literal[
    "benefit",
    "harm",
    "good_fortune",
    "bad_fortune",
    "none",
    "unknown",
]
SimilarityToSelf = Literal["present", "absent", "unknown"]
AppraisalDimension = Literal[
    "self_power",
    "self_person",
    "self_action",
    "other_person",
    "unknown",
]
AppraisalLevel = Literal["high", "low", "neutral", "unknown"]
AppraisalBias = Literal["over", "under", "fair", "unknown"]
SocialJudgment = Literal["praise", "blame", "none", "unknown"]
ActionGoal = Literal[
    "approach",
    "possess",
    "avoid",
    "benefit",
    "harm",
    "restrain_harm",
    "please",
    "avoid_displeasing",
    "perform",
    "seek_esteem",
    "none",
    "unknown",
]
ActionStatus = Literal["intended", "performed", "blocked", "restrained", "unknown"]
ActionOrigin = Literal["self_generated", "imitated", "unknown"]
ActionBlocker = Literal[
    "none",
    "target_absent",
    "fear",
    "wonder",
    "competing_evil",
    "lesser_evil_tradeoff",
    "social_displeasure",
    "unknown",
]
PeerNorm = Literal["peers_fear", "peers_dare", "not_applicable", "unknown"]
ActionDomain = Literal["food", "alcohol", "wealth", "sex", "esteem", "other", "none", "unknown"]
Excessiveness = Literal["ordinary", "excessive", "unknown"]


class EvidenceSpan(BaseModel):
    """Direct quote backing one extracted judgment."""

    quote: str = Field(
        description="日記本文からそのまま抜き出した文字列。言い換えや要約をしない。"
    )
    start_char: int = Field(ge=0, description="根拠引用の開始文字位置。")
    end_char: int = Field(ge=0, description="根拠引用の終了文字位置。")


class EntityRef(BaseModel):
    """Entity reference shared across episode features."""

    entity_id: str = Field(
        description=(
            "Episode内で一意な参照ID。日記の書き手は必ずselfとし、他の人物・対象は"
            "person-1、object-1、event-1等とする。"
        )
    )
    kind: EntityKind = Field(
        description=(
            "対象の種類。本文から種類が判断できない場合はunknown。selfは日記の書き手だけに使う。"
        )
    )
    text: str = Field(
        description=(
            "日記本文に実際に現れる対象の表記。selfが暗黙の場合のみ、書き手を示す短い表記を許す。"
        )
    )
    evidence: list[EvidenceSpan] = Field(
        description="このentity参照を支える本文中の直接引用。暗黙のselfでは空配列を許す。"
    )


class PowerComponents(BaseModel):
    """Separate increase/decrease components of conatus power."""

    increase_intensity: int = Field(
        ge=0,
        le=5,
        description=(
            "主体の活動能力・行為能力の増大の強さ。0=根拠なし、1=ごく弱い、2=弱いが明示的、"
            "3=明確、4=強い、5=Episodeの中心となる非常に強い変化。"
        ),
    )
    decrease_intensity: int = Field(
        ge=0,
        le=5,
        description=(
            "主体の活動能力・行為能力の減少の強さ。0=根拠なし、1=ごく弱い、2=弱いが明示的、"
            "3=明確、4=強い、5=Episodeの中心となる非常に強い変化。"
        ),
    )
    increase_evidence: list[EvidenceSpan] = Field(
        description="increase_intensityを直接支える本文中の引用。根拠なしなら空配列。"
    )
    decrease_evidence: list[EvidenceSpan] = Field(
        description="decrease_intensityを直接支える本文中の引用。根拠なしなら空配列。"
    )


class CausalLink(BaseModel):
    """Causal relation between an entity and power/desire effect."""

    effect: PowerEffect = Field(
        description="原因が作用する結果。increase、decrease、desireのいずれか。"
    )
    cause_entity_id: str | None = Field(
        description="原因entityのID。原因なし・判断不能ならnull。"
    )
    mode: CauseMode = Field(
        description=(
            "self=自分または自分の行為が原因、direct_external=外部の人物・対象・出来事が直接原因、"
            "accidental_external=連想や間接的結び付きによる外部原因、none=原因なし、unknown=判断不能。"
        )
    )
    evidence: list[EvidenceSpan] = Field(description="因果判断を支える直接引用。")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="因果関係の抽出が本文から直接支持される確信度。",
    )


class EntityStance(BaseModel):
    """Non-affect stance toward an entity."""

    target_entity_id: str = Field(description="姿勢が向く対象entity ID。")
    valence: StanceValence = Field(
        description=(
            "positive=接近・保持・支援したい方向、negative=避ける・排除する・害したい方向、"
            "ambivalent=肯定と否定が両方明示、neutral=中立が明確、unknown=判断不能。"
        )
    )
    evidence: list[EvidenceSpan] = Field(description="姿勢判断を支える直接引用。")
    confidence: float = Field(ge=0.0, le=1.0, description="姿勢抽出の確信度。")


class AttentionState(BaseModel):
    """Attention state toward an entity."""

    target_entity_id: str | None = Field(description="注意が向く対象entity ID。判断不能ならnull。")
    mode: AttentionMode = Field(
        description=(
            "novel_fixation=新奇性や理解不能性により注意が固定、low_salience=欠如や取るに足らなさへ注意、"
            "ordinary=通常の注目、unknown=判断不能。"
        )
    )
    evidence: list[EvidenceSpan] = Field(description="注意状態を支える直接引用。")
    confidence: float = Field(ge=0.0, le=1.0, description="注意状態抽出の確信度。")


class TemporalAppraisal(BaseModel):
    """Time and certainty appraisal for the episode."""

    orientation: TemporalOrientation = Field(
        description="past/present/future/mixed/unknown。複数方向が明示される場合のみmixed。"
    )
    representation: TemporalRepresentation = Field(
        description="perception=知覚、memory=記憶、anticipation=予期、unknown=判断不能。"
    )
    certainty: TemporalCertainty = Field(
        description=(
            "uncertain=結果に疑いが残る、resolved=書き手にとって疑いが解消、"
            "not_applicable=確実性評価が不要、unknown=判断不能。"
        )
    )
    outcome_vs_expectation: OutcomeVsExpectation = Field(
        description=(
            "better=期待より良い、as_expected=期待通り、worse=期待より悪い、"
            "not_observed=期待との比較なし、unknown=判断不能。"
        )
    )
    target_availability: TargetAvailability = Field(
        description="対象がpresent/absent/excluded/unknownのどれか。懐旧ではabsentまたはexcludedが重要。"
    )
    evidence: list[EvidenceSpan] = Field(description="時間・確実性判断を支える直接引用。")
    confidence: float = Field(ge=0.0, le=1.0, description="時間評価抽出の確信度。")


class SocialEvent(BaseModel):
    """Structured social relation or fortune event."""

    actor_entity_id: str | None = Field(description="行為者entity ID。判断不能ならnull。")
    recipient_entity_id: str | None = Field(description="受け手entity ID。判断不能ならnull。")
    effect: SocialEffect = Field(
        description="benefit/harm/good_fortune/bad_fortune/none/unknown。"
    )
    recipient_similar_to_self: SimilarityToSelf = Field(
        description="受け手が自分に似ていると表象される根拠の有無。present/absent/unknown。"
    )
    evidence: list[EvidenceSpan] = Field(description="社会的出来事を支える直接引用。")
    confidence: float = Field(ge=0.0, le=1.0, description="社会的出来事抽出の確信度。")


class Appraisal(BaseModel):
    """Non-affect appraisal of self, action, or other."""

    target_entity_id: str | None = Field(description="評価対象entity ID。判断不能ならnull。")
    dimension: AppraisalDimension = Field(
        description="self_power/self_person/self_action/other_person/unknown。"
    )
    level: AppraisalLevel = Field(
        description="high=高い評価、low=低い評価、neutral=中立が明確、unknown=判断不能。"
    )
    bias: AppraisalBias = Field(
        description="over=正当以上、under=正当以下、fair=妥当、unknown=客観的正当性を判断不能。"
    )
    imagined_social_judgment: SocialJudgment = Field(
        description="praise=称賛される表象、blame=非難される表象、none=なしが明確、unknown=判断不能。"
    )
    evidence: list[EvidenceSpan] = Field(description="評価判断を支える直接引用。")
    confidence: float = Field(ge=0.0, le=1.0, description="評価抽出の確信度。")


class ActionTendency(BaseModel):
    """Observed action tendency without naming an affect."""

    goal: ActionGoal = Field(
        description=(
            "行為傾向の目標。approach/possess/avoid/benefit/harm/restrain_harm/please/"
            "avoid_displeasing/perform/seek_esteem/none/unknown。"
        )
    )
    target_entity_id: str | None = Field(description="行為対象entity ID。判断不能ならnull。")
    status: ActionStatus = Field(
        description="intended=意図、performed=実行、blocked=妨げられた、restrained=自制、unknown=判断不能。"
    )
    origin: ActionOrigin = Field(
        description="self_generated=自発、imitated=他者の欲望の模倣、unknown=判断不能。"
    )
    model_entity_id: str | None = Field(
        description="origin=imitatedの場合の模倣元entity ID。それ以外や判断不能ならnull。"
    )
    blocker: ActionBlocker = Field(
        description=(
            "none/target_absent/fear/wonder/competing_evil/lesser_evil_tradeoff/"
            "social_displeasure/unknown。"
        )
    )
    peer_norm: PeerNorm = Field(
        description="peers_fear=同等者が恐れる、peers_dare=同等者があえて行う、not_applicable/unknown。"
    )
    domain: ActionDomain = Field(
        description="food/alcohol/wealth/sex/esteem/other/none/unknown。過度な欲望判定に使う。"
    )
    excessiveness: Excessiveness = Field(
        description="ordinary=通常、excessive=過度・反復・やめにくい、unknown=判断不能。"
    )
    desired_object_entity_id: str | None = Field(
        default=None,
        description="競争心などで共有される欲望対象entity ID。判断不能ならnull。",
    )
    evidence: list[EvidenceSpan] = Field(description="行為傾向を支える直接引用。")
    confidence: float = Field(ge=0.0, le=1.0, description="行為傾向抽出の確信度。")


class EpisodeFeatureSchema(BaseModel):
    """Atomic episode features extracted before deterministic affect evaluation."""

    episode_id: str = Field(description="日記内で一意なEpisode ID。例: episode-1。")
    start_char: int = Field(ge=0, description="日記本文におけるEpisode開始文字位置。")
    end_char: int = Field(ge=0, description="日記本文におけるEpisode終了文字位置。")
    text: str = Field(description="日記本文からそのまま抜き出したEpisode本文。")
    summary: str = Field(
        description=(
            "表示用の短い要約。情動名を直接書かず、出来事・対象・行為・時間・関係をまとめる。"
        )
    )
    entities: list[EntityRef] = Field(description="Episode内の人物・対象・出来事参照。")
    power_components: PowerComponents = Field(description="力能増大・減少の2成分。")
    causal_links: list[CausalLink] = Field(description="力能変化や欲望に対する原因リンク。")
    entity_stances: list[EntityStance] = Field(description="対象への接近・回避などの姿勢。")
    attention_states: list[AttentionState] = Field(description="対象への注意状態。")
    temporal_appraisal: TemporalAppraisal = Field(description="時間方向・確実性・期待との関係。")
    social_events: list[SocialEvent] = Field(description="人物間の利益・害・幸不幸。")
    appraisals: list[Appraisal] = Field(description="自己・行為・他者に対する評価。")
    action_tendencies: list[ActionTendency] = Field(description="本文から観察できる行為傾向。")
    extraction_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Episode分割と特徴抽出が本文から直接支持される確信度。",
    )


class DiaryAnalysisSchema(BaseModel):
    """Top-level structured diary analysis returned by an analyzer."""

    episodes: list[EpisodeFeatureSchema]


class EpisodeSpan(BaseModel):
    """Episode boundary returned by the segmentation step."""

    episode_id: str = Field(description="日記内で一意なEpisode ID。例: episode-1。")
    start_char: int = Field(ge=0, description="日記本文における開始文字位置。")
    end_char: int = Field(ge=0, description="日記本文における終了文字位置。")
    text: str = Field(description="日記本文からそのまま抜き出したEpisode本文。")


class DiarySegmentationSchema(BaseModel):
    """Structured output for the first OpenAI segmentation step."""

    episodes: list[EpisodeSpan]


@dataclass(frozen=True)
class AnalyzerResponse:
    """Analyzer output plus API metadata."""

    analysis: DiaryAnalysisSchema
    response_id: str | None
    requested_model: str
    actual_model: str
    service_tier: str | None
    usage: TokenUsage | None
    provider: Literal["mock", "openai"] = "openai"
    prompt_version: str = "diary-features-v2"
    segmentation_json: str | None = None


class AnalyzerError(RuntimeError):
    """Raised when diary analysis cannot be completed safely."""


def normalize_episode_span(span: EpisodeSpan, source_text: str) -> EpisodeSpan:
    """Return a span whose boundaries exactly match source text when safely recoverable."""

    if span.end_char < span.start_char:
        raise AnalyzerError("Episodeの終了位置が開始位置より前です。")
    if source_text[span.start_char : span.end_char] != span.text:
        corrected = _locate_text_span(span.text, source_text, hint_start=span.start_char)
        if corrected is None and span.text.strip() != span.text:
            corrected = _locate_text_span(
                span.text.strip(), source_text, hint_start=span.start_char
            )
        if corrected is None:
            raise AnalyzerError(
                "Episode境界を補正できません。日記本文に存在しないEpisode本文が返されました。"
            )
        start, end = corrected
        return span.model_copy(
            update={
                "start_char": start,
                "end_char": end,
                "text": source_text[start:end],
            }
        )
    return span


def validate_episode_span(span: EpisodeSpan, source_text: str) -> None:
    """Reject segmentation spans that cannot be matched to the source text."""

    normalize_episode_span(span, source_text)


def normalize_episode_feature(
    feature: EpisodeFeatureSchema,
    source_text: str,
    expected_span: EpisodeSpan | None = None,
) -> EpisodeFeatureSchema:
    """Normalize recoverable boundary/evidence offsets, then validate semantics."""

    if expected_span is not None:
        expected_span = normalize_episode_span(expected_span, source_text)
        feature_span = _feature_span(feature)
        if feature.text != expected_span.text:
            if feature.text.strip() != expected_span.text.strip():
                feature_span = normalize_episode_span(feature_span, source_text)
                if (
                    feature_span.start_char != expected_span.start_char
                    or feature_span.end_char != expected_span.end_char
                ):
                    raise AnalyzerError("Episode特徴の本文が確定済みEpisode境界と一致しません。")
        normalized = feature.model_copy(
            deep=True,
            update={
                "episode_id": expected_span.episode_id,
                "start_char": expected_span.start_char,
                "end_char": expected_span.end_char,
                "text": expected_span.text,
            },
        )
    else:
        span = normalize_episode_span(_feature_span(feature), source_text)
        normalized = feature.model_copy(
            deep=True,
            update={
                "start_char": span.start_char,
                "end_char": span.end_char,
                "text": span.text,
            },
        )

    _normalize_feature_evidence(normalized)
    _validate_episode_feature_semantics(normalized)
    return normalized


def validate_episode_feature(feature: EpisodeFeatureSchema, source_text: str) -> None:
    """Validate textual spans and semantic references in one feature object."""

    normalize_episode_feature(feature, source_text)


def _validate_episode_feature_semantics(feature: EpisodeFeatureSchema) -> None:
    if feature.end_char < feature.start_char:
        raise AnalyzerError("Episode特徴の終了位置が開始位置より前です。")

    entity_ids = [entity.entity_id for entity in feature.entities]
    entity_id_set = set(entity_ids)
    if len(entity_ids) != len(entity_id_set):
        raise AnalyzerError("同じentity_idが重複しています。")
    if not any(entity.entity_id == "self" and entity.kind == "self" for entity in feature.entities):
        raise AnalyzerError("entity_id=self の書き手entityがありません。")

    for span in _all_evidence_spans(feature):
        _validate_evidence_span(span, feature.text)

    for link in feature.causal_links:
        _validate_ref(link.cause_entity_id, entity_id_set, "causal_links.cause_entity_id")
    for stance in feature.entity_stances:
        _validate_ref(stance.target_entity_id, entity_id_set, "entity_stances.target_entity_id")
    for attention in feature.attention_states:
        _validate_ref(attention.target_entity_id, entity_id_set, "attention_states.target_entity_id")
    for event in feature.social_events:
        _validate_ref(event.actor_entity_id, entity_id_set, "social_events.actor_entity_id")
        _validate_ref(event.recipient_entity_id, entity_id_set, "social_events.recipient_entity_id")
        if event.effect in {"benefit", "harm"} and (
            event.actor_entity_id is None or event.recipient_entity_id is None
        ):
            raise AnalyzerError("benefit/harm のSocialEventにはactorとrecipientが必要です。")
        if event.effect in {"good_fortune", "bad_fortune"} and event.recipient_entity_id is None:
            raise AnalyzerError("good_fortune/bad_fortune のSocialEventにはrecipientが必要です。")
    for appraisal in feature.appraisals:
        _validate_ref(appraisal.target_entity_id, entity_id_set, "appraisals.target_entity_id")
    for action in feature.action_tendencies:
        _validate_ref(action.target_entity_id, entity_id_set, "action_tendencies.target_entity_id")
        _validate_ref(action.model_entity_id, entity_id_set, "action_tendencies.model_entity_id")
        _validate_ref(
            action.desired_object_entity_id,
            entity_id_set,
            "action_tendencies.desired_object_entity_id",
        )
        if action.origin == "imitated" and action.model_entity_id is None:
            raise AnalyzerError("origin=imitated のActionTendencyにはmodel_entity_idが必要です。")
    if (
        any(action.blocker == "target_absent" for action in feature.action_tendencies)
        and feature.temporal_appraisal.target_availability == "present"
    ):
        raise AnalyzerError("target_absent と target_availability=present が矛盾しています。")


def _feature_span(feature: EpisodeFeatureSchema) -> EpisodeSpan:
    return EpisodeSpan(
        episode_id=feature.episode_id,
        start_char=feature.start_char,
        end_char=feature.end_char,
        text=feature.text,
    )


def _locate_text_span(
    text: str,
    source_text: str,
    *,
    hint_start: int = 0,
) -> tuple[int, int] | None:
    if not text:
        return None
    starts: list[int] = []
    start = source_text.find(text)
    while start >= 0:
        starts.append(start)
        start = source_text.find(text, start + 1)
    if not starts:
        return None
    selected = min(starts, key=lambda value: abs(value - hint_start))
    return selected, selected + len(text)


def _normalize_feature_evidence(feature: EpisodeFeatureSchema) -> None:
    feature.power_components.increase_evidence = _normalize_evidence_list(
        feature.power_components.increase_evidence, feature.text
    )
    feature.power_components.decrease_evidence = _normalize_evidence_list(
        feature.power_components.decrease_evidence, feature.text
    )
    for entity in feature.entities:
        entity.evidence = _normalize_evidence_list(entity.evidence, feature.text)
    for link in feature.causal_links:
        link.evidence = _normalize_evidence_list(link.evidence, feature.text)
    for stance in feature.entity_stances:
        stance.evidence = _normalize_evidence_list(stance.evidence, feature.text)
    for attention in feature.attention_states:
        attention.evidence = _normalize_evidence_list(attention.evidence, feature.text)
    feature.temporal_appraisal.evidence = _normalize_evidence_list(
        feature.temporal_appraisal.evidence, feature.text
    )
    for event in feature.social_events:
        event.evidence = _normalize_evidence_list(event.evidence, feature.text)
    for appraisal in feature.appraisals:
        appraisal.evidence = _normalize_evidence_list(appraisal.evidence, feature.text)
    for action in feature.action_tendencies:
        action.evidence = _normalize_evidence_list(action.evidence, feature.text)


def _normalize_evidence_list(
    spans: list[EvidenceSpan],
    source_text: str,
) -> list[EvidenceSpan]:
    return [_normalize_evidence_span(span, source_text) for span in spans]


def _normalize_evidence_span(span: EvidenceSpan, source_text: str) -> EvidenceSpan:
    if span.end_char >= span.start_char and source_text[span.start_char : span.end_char] == span.quote:
        return span
    corrected = _locate_text_span(span.quote, source_text, hint_start=span.start_char)
    if corrected is None and span.quote.strip() != span.quote:
        corrected = _locate_text_span(
            span.quote.strip(), source_text, hint_start=span.start_char
        )
    if corrected is None:
        raise AnalyzerError("EvidenceSpanの引用が本文と一致しません。")
    start, end = corrected
    return span.model_copy(
        update={
            "quote": source_text[start:end],
            "start_char": start,
            "end_char": end,
        }
    )


def _validate_ref(value: str | None, entity_ids: set[str], label: str) -> None:
    if value is not None and value not in entity_ids:
        raise AnalyzerError(f"存在しないentity_idを参照しています: {label}")


def _validate_evidence_span(span: EvidenceSpan, source_text: str) -> None:
    if span.end_char < span.start_char:
        raise AnalyzerError("EvidenceSpanの終了位置が開始位置より前です。")
    if source_text[span.start_char : span.end_char] != span.quote:
        raise AnalyzerError("EvidenceSpanの引用が本文と一致しません。")


def _all_evidence_spans(feature: EpisodeFeatureSchema) -> list[EvidenceSpan]:
    spans: list[EvidenceSpan] = []
    spans.extend(feature.power_components.increase_evidence)
    spans.extend(feature.power_components.decrease_evidence)
    for entity in feature.entities:
        spans.extend(entity.evidence)
    for link in feature.causal_links:
        spans.extend(link.evidence)
    for stance in feature.entity_stances:
        spans.extend(stance.evidence)
    for attention in feature.attention_states:
        spans.extend(attention.evidence)
    spans.extend(feature.temporal_appraisal.evidence)
    for event in feature.social_events:
        spans.extend(event.evidence)
    for appraisal in feature.appraisals:
        spans.extend(appraisal.evidence)
    for action in feature.action_tendencies:
        spans.extend(action.evidence)
    return spans


def combine_token_usage(usages: list[TokenUsage | None]) -> TokenUsage | None:
    """Add usage from multiple Responses API calls without guessing missing values."""

    present = [usage for usage in usages if usage is not None]
    if not present:
        return None

    def summed(attr: str) -> int | None:
        values = [getattr(usage, attr) for usage in present]
        if all(value is None for value in values):
            return None
        return sum(int(value or 0) for value in values)

    input_tokens = summed("input_tokens")
    cached_input_tokens = summed("cached_input_tokens")
    uncached_input_tokens = summed("uncached_input_tokens")
    output_tokens = summed("output_tokens")
    reasoning_tokens = summed("reasoning_tokens")
    total_tokens = summed("total_tokens")
    if uncached_input_tokens is None and input_tokens is not None and cached_input_tokens is not None:
        uncached_input_tokens = max(input_tokens - cached_input_tokens, 0)
    return TokenUsage(
        input_tokens,
        cached_input_tokens,
        uncached_input_tokens,
        output_tokens,
        reasoning_tokens,
        total_tokens,
    )


def _contains(text: str, *words: str) -> bool:
    return any(word in text for word in words)


def _split_episode_spans(text: str) -> list[EpisodeSpan]:
    spans: list[EpisodeSpan] = []
    normalized = text.replace("\r\n", "\n")
    for match in re.finditer(r"[^。！？!?\n]+[。！？!?]?", normalized):
        chunk = match.group(0).strip()
        if not chunk:
            continue
        leading = len(match.group(0)) - len(match.group(0).lstrip())
        start = match.start() + leading
        end = start + len(chunk)
        spans.append(
            EpisodeSpan(
                episode_id=f"episode-{len(spans) + 1}",
                start_char=start,
                end_char=end,
                text=normalized[start:end],
            )
        )
    if spans:
        return spans
    stripped = normalized.strip()
    if not stripped:
        return []
    start = normalized.index(stripped)
    return [EpisodeSpan(episode_id="episode-1", start_char=start, end_char=start + len(stripped), text=stripped)]


def _evidence(text: str, *needles: str) -> list[EvidenceSpan]:
    for needle in needles:
        if not needle:
            continue
        index = text.find(needle)
        if index >= 0:
            return [EvidenceSpan(quote=needle, start_char=index, end_char=index + len(needle))]
    if not text:
        return []
    quote = text[: min(len(text), 40)]
    return [EvidenceSpan(quote=quote, start_char=0, end_char=len(quote))]


def _first_keyword(text: str, words: tuple[str, ...]) -> str | None:
    positions = [(text.find(word), word) for word in words if text.find(word) >= 0]
    if not positions:
        return None
    return min(positions, key=lambda item: item[0])[1]


def _summary(text: str) -> str:
    return text if len(text) <= 44 else f"{text[:43]}..."


class MockDiaryAnalyzer:
    """Deterministic offline analyzer for tests and demos."""

    provider = "mock"
    prompt_version = "mock-diary-features-v2"

    def analyze(self, text: str, *, model: str = "mock") -> AnalyzerResponse:
        spans = _split_episode_spans(text)
        episodes = [self._feature_from_span(span, text) for span in spans]
        return AnalyzerResponse(
            analysis=DiaryAnalysisSchema(episodes=episodes),
            response_id="mock-response",
            requested_model=model,
            actual_model=model,
            service_tier=None,
            usage=None,
            provider="mock",
            prompt_version=self.prompt_version,
            segmentation_json=DiarySegmentationSchema(episodes=spans).model_dump_json(
                ensure_ascii=False
            ),
        )

    def _feature_from_span(self, span: EpisodeSpan, diary_text: str) -> EpisodeFeatureSchema:
        text = span.text
        person_word = _first_keyword(
            text,
            (
                "同僚",
                "友人",
                "上司",
                "相手",
                "先生",
                "母",
                "父",
                "家族",
                "チーム",
            ),
        )
        entities = [EntityRef(entity_id="self", kind="self", text="書き手", evidence=[])]
        person_id = None
        if person_word is not None:
            person_id = "person-1"
            entities.append(
                EntityRef(
                    entity_id=person_id,
                    kind="group" if person_word in {"家族", "チーム"} else "person",
                    text=person_word,
                    evidence=_evidence(text, person_word),
                )
            )

        increase_words = (
            "うれ",
            "嬉",
            "成功",
            "でき",
            "希望",
            "感謝",
            "ありがた",
            "ありがとう",
            "助け",
            "褒め",
            "安心",
        )
        decrease_words = (
            "悲",
            "不安",
            "恐",
            "怖",
            "失敗",
            "否定",
            "責め",
            "理不尽",
            "怒",
            "腹が立",
            "後悔",
            "申し訳",
            "恥",
        )
        positive = _contains(text, *increase_words)
        negative = _contains(text, *decrease_words)
        increase = 3 if positive else 0
        decrease = 2 if negative else 0
        if positive and negative:
            increase, decrease = 3, 2

        causal_links = self._causal_links(text, person_id)
        social_events = self._social_events(text, person_id)
        stances = self._stances(text, person_id)
        actions = self._actions(text, person_id)
        feature = EpisodeFeatureSchema(
            episode_id=span.episode_id,
            start_char=span.start_char,
            end_char=span.end_char,
            text=text,
            summary=_summary(text),
            entities=entities,
            power_components=PowerComponents(
                increase_intensity=increase,
                decrease_intensity=decrease,
                increase_evidence=_evidence(text, *_matching_words(text, increase_words)) if increase else [],
                decrease_evidence=_evidence(text, *_matching_words(text, decrease_words)) if decrease else [],
            ),
            causal_links=causal_links,
            entity_stances=stances,
            attention_states=self._attention_states(text, person_id),
            temporal_appraisal=self._temporal_appraisal(text, person_id is not None),
            social_events=social_events,
            appraisals=self._appraisals(text, person_id),
            action_tendencies=actions,
            extraction_confidence=0.82,
        )
        validate_episode_feature(feature, diary_text)
        return feature

    def _causal_links(self, text: str, person_id: str | None) -> list[CausalLink]:
        links: list[CausalLink] = []
        if person_id and _contains(text, "助け", "褒め", "ありがた", "ありがとう", "感謝"):
            links.append(
                CausalLink(
                    effect="increase",
                    cause_entity_id=person_id,
                    mode="direct_external",
                    evidence=_evidence(text, "助け", "褒め", "ありがた", "ありがとう", "感謝"),
                    confidence=0.84,
                )
            )
        if person_id and _contains(text, "責め", "否定", "理不尽"):
            links.append(
                CausalLink(
                    effect="decrease",
                    cause_entity_id=person_id,
                    mode="direct_external",
                    evidence=_evidence(text, "責め", "否定", "理不尽"),
                    confidence=0.84,
                )
            )
        if _contains(text, "成功", "できた"):
            links.append(
                CausalLink(
                    effect="increase",
                    cause_entity_id="self",
                    mode="self",
                    evidence=_evidence(text, "成功", "できた"),
                    confidence=0.78,
                )
            )
        if _contains(text, "後悔", "申し訳"):
            links.append(
                CausalLink(
                    effect="decrease",
                    cause_entity_id="self",
                    mode="self",
                    evidence=_evidence(text, "後悔", "申し訳"),
                    confidence=0.78,
                )
            )
        if _contains(text, "したい", "欲しい", "望", "言い返したかった"):
            links.append(
                CausalLink(
                    effect="desire",
                    cause_entity_id="self",
                    mode="self",
                    evidence=_evidence(text, "したい", "欲しい", "望", "言い返したかった"),
                    confidence=0.72,
                )
            )
        return links

    def _stances(self, text: str, person_id: str | None) -> list[EntityStance]:
        stances: list[EntityStance] = []
        if person_id and _contains(text, "感謝", "ありがた", "ありがとう", "助け"):
            stances.append(
                EntityStance(
                    target_entity_id=person_id,
                    valence="positive",
                    evidence=_evidence(text, "感謝", "ありがた", "ありがとう", "助け"),
                    confidence=0.82,
                )
            )
        if person_id and _contains(text, "責め", "理不尽", "怒", "腹が立", "嫌"):
            stances.append(
                EntityStance(
                    target_entity_id=person_id,
                    valence="negative",
                    evidence=_evidence(text, "責め", "理不尽", "怒", "腹が立", "嫌"),
                    confidence=0.82,
                )
            )
        if _contains(text, "自分はすごい", "自慢"):
            stances.append(
                EntityStance(
                    target_entity_id="self",
                    valence="positive",
                    evidence=_evidence(text, "自分はすごい", "自慢"),
                    confidence=0.78,
                )
            )
        if _contains(text, "後悔", "申し訳", "恥"):
            stances.append(
                EntityStance(
                    target_entity_id="self",
                    valence="negative",
                    evidence=_evidence(text, "後悔", "申し訳", "恥"),
                    confidence=0.78,
                )
            )
        return stances

    def _attention_states(self, text: str, person_id: str | None) -> list[AttentionState]:
        target = person_id
        if _contains(text, "驚", "すごい", "信じられない"):
            return [
                AttentionState(
                    target_entity_id=target,
                    mode="novel_fixation",
                    evidence=_evidence(text, "驚", "すごい", "信じられない"),
                    confidence=0.76,
                )
            ]
        if _contains(text, "見下", "軽視", "取るに足りない"):
            return [
                AttentionState(
                    target_entity_id=target,
                    mode="low_salience",
                    evidence=_evidence(text, "見下", "軽視", "取るに足りない"),
                    confidence=0.76,
                )
            ]
        return [
            AttentionState(
                target_entity_id=target,
                mode="ordinary" if target else "unknown",
                evidence=_evidence(text, target or text[:1]) if target else [],
                confidence=0.45,
            )
        ]

    def _temporal_appraisal(self, text: str, has_target: bool) -> TemporalAppraisal:
        future = _contains(text, "明日", "将来", "これから", "希望", "かもしれない")
        memory = _contains(text, "昔", "以前", "懐か", "恋しい")
        past = memory or _contains(text, "昨日", "後悔", "期待外れ", "予想外")
        uncertain = _contains(text, "かもしれない", "不安", "まだ分から")
        resolved = _contains(text, "安心", "解決", "分かった")
        absent = _contains(text, "懐か", "恋しい", "失った", "いない")
        return TemporalAppraisal(
            orientation="future" if future else "past" if past else "present",
            representation="memory" if memory else "anticipation" if future else "perception",
            certainty="uncertain" if uncertain else "resolved" if resolved else "not_applicable",
            outcome_vs_expectation=(
                "better"
                if _contains(text, "予想以上", "期待以上")
                else "as_expected"
                if _contains(text, "予想通り", "期待通り")
                else "worse"
                if _contains(text, "期待外れ", "予想外", "後悔", "失敗")
                else "not_observed"
            ),
            target_availability="absent" if absent else "present" if has_target else "unknown",
            evidence=_evidence(text, "明日", "将来", "希望", "不安", "安心", "懐か", "後悔"),
            confidence=0.72,
        )

    def _social_events(self, text: str, person_id: str | None) -> list[SocialEvent]:
        if not person_id:
            return []
        events: list[SocialEvent] = []
        if _contains(text, "助け", "手伝", "ありがた", "ありがとう", "感謝"):
            events.append(
                SocialEvent(
                    actor_entity_id=person_id,
                    recipient_entity_id="self",
                    effect="benefit",
                    recipient_similar_to_self="unknown",
                    evidence=_evidence(text, "助け", "手伝", "ありがた", "ありがとう", "感謝"),
                    confidence=0.86,
                )
            )
        if _contains(text, "責め", "否定", "理不尽"):
            events.append(
                SocialEvent(
                    actor_entity_id=person_id,
                    recipient_entity_id="self",
                    effect="harm",
                    recipient_similar_to_self="unknown",
                    evidence=_evidence(text, "責め", "否定", "理不尽"),
                    confidence=0.86,
                )
            )
        if _contains(text, "成功した", "うまくいった"):
            events.append(
                SocialEvent(
                    actor_entity_id=None,
                    recipient_entity_id=person_id,
                    effect="good_fortune",
                    recipient_similar_to_self="present" if _contains(text, "似ている", "同じ") else "unknown",
                    evidence=_evidence(text, "成功した", "うまくいった"),
                    confidence=0.66,
                )
            )
        if _contains(text, "失敗した", "つらそう", "困って"):
            events.append(
                SocialEvent(
                    actor_entity_id=None,
                    recipient_entity_id=person_id,
                    effect="bad_fortune",
                    recipient_similar_to_self="present" if _contains(text, "似ている", "同じ") else "unknown",
                    evidence=_evidence(text, "失敗した", "つらそう", "困って"),
                    confidence=0.66,
                )
            )
        return events

    def _appraisals(self, text: str, person_id: str | None) -> list[Appraisal]:
        appraisals: list[Appraisal] = []
        if _contains(text, "成功", "できた"):
            appraisals.append(
                Appraisal(
                    target_entity_id="self",
                    dimension="self_power",
                    level="high",
                    bias="unknown",
                    imagined_social_judgment="none",
                    evidence=_evidence(text, "成功", "できた"),
                    confidence=0.76,
                )
            )
        if _contains(text, "失敗", "無力"):
            appraisals.append(
                Appraisal(
                    target_entity_id="self",
                    dimension="self_power",
                    level="low",
                    bias="unknown",
                    imagined_social_judgment="none",
                    evidence=_evidence(text, "失敗", "無力"),
                    confidence=0.76,
                )
            )
        if _contains(text, "後悔", "申し訳"):
            appraisals.append(
                Appraisal(
                    target_entity_id="self",
                    dimension="self_action",
                    level="low",
                    bias="unknown",
                    imagined_social_judgment="none",
                    evidence=_evidence(text, "後悔", "申し訳"),
                    confidence=0.78,
                )
            )
        if _contains(text, "褒め", "評価された"):
            appraisals.append(
                Appraisal(
                    target_entity_id="self",
                    dimension="self_action",
                    level="high",
                    bias="unknown",
                    imagined_social_judgment="praise",
                    evidence=_evidence(text, "褒め", "評価された"),
                    confidence=0.78,
                )
            )
        if _contains(text, "恥", "非難"):
            appraisals.append(
                Appraisal(
                    target_entity_id="self",
                    dimension="self_action",
                    level="low",
                    bias="unknown",
                    imagined_social_judgment="blame",
                    evidence=_evidence(text, "恥", "非難"),
                    confidence=0.78,
                )
            )
        if _contains(text, "自分はすごい", "自慢"):
            appraisals.append(
                Appraisal(
                    target_entity_id="self",
                    dimension="self_person",
                    level="high",
                    bias="over",
                    imagined_social_judgment="none",
                    evidence=_evidence(text, "自分はすごい", "自慢"),
                    confidence=0.76,
                )
            )
        if _contains(text, "自分なんて", "だめな人間"):
            appraisals.append(
                Appraisal(
                    target_entity_id="self",
                    dimension="self_person",
                    level="low",
                    bias="under",
                    imagined_social_judgment="none",
                    evidence=_evidence(text, "自分なんて", "だめな人間"),
                    confidence=0.76,
                )
            )
        if person_id and _contains(text, "見下", "軽蔑", "軽視"):
            appraisals.append(
                Appraisal(
                    target_entity_id=person_id,
                    dimension="other_person",
                    level="low",
                    bias="under",
                    imagined_social_judgment="none",
                    evidence=_evidence(text, "見下", "軽蔑", "軽視"),
                    confidence=0.76,
                )
            )
        if person_id and _contains(text, "尊敬", "すごい"):
            appraisals.append(
                Appraisal(
                    target_entity_id=person_id,
                    dimension="other_person",
                    level="high",
                    bias="over" if _contains(text, "過大") else "unknown",
                    imagined_social_judgment="none",
                    evidence=_evidence(text, "尊敬", "すごい"),
                    confidence=0.68,
                )
            )
        return appraisals

    def _actions(self, text: str, person_id: str | None) -> list[ActionTendency]:
        actions: list[ActionTendency] = []
        if person_id and _contains(text, "恩返し", "助けたい", "手伝いたい", "ありがた", "感謝"):
            actions.append(
                ActionTendency(
                    goal="benefit",
                    target_entity_id=person_id,
                    status="intended",
                    origin="self_generated",
                    model_entity_id=None,
                    blocker="none",
                    peer_norm="not_applicable",
                    domain="none",
                    excessiveness="ordinary",
                    evidence=_evidence(text, "恩返し", "助けたい", "手伝いたい", "ありがた", "感謝"),
                    confidence=0.78,
                )
            )
        if person_id and _contains(text, "言い返したかった", "仕返", "復讐", "やり返"):
            actions.append(
                ActionTendency(
                    goal="harm",
                    target_entity_id=person_id,
                    status="restrained" if _contains(text, "我慢", "こらえ") else "intended",
                    origin="self_generated",
                    model_entity_id=None,
                    blocker="social_displeasure" if _contains(text, "我慢", "こらえ") else "none",
                    peer_norm="not_applicable",
                    domain="none",
                    excessiveness="ordinary",
                    evidence=_evidence(text, "言い返したかった", "仕返", "復讐", "やり返"),
                    confidence=0.82,
                )
            )
        if _contains(text, "我慢", "こらえ"):
            actions.append(
                ActionTendency(
                    goal="restrain_harm",
                    target_entity_id=person_id,
                    status="performed",
                    origin="self_generated",
                    model_entity_id=None,
                    blocker="none",
                    peer_norm="not_applicable",
                    domain="none",
                    excessiveness="ordinary",
                    evidence=_evidence(text, "我慢", "こらえ"),
                    confidence=0.76,
                )
            )
        if _contains(text, "欲しい", "手に入れたい"):
            actions.append(
                ActionTendency(
                    goal="possess",
                    target_entity_id=None,
                    status="intended",
                    origin="self_generated",
                    model_entity_id=None,
                    blocker="none",
                    peer_norm="not_applicable",
                    domain="other",
                    excessiveness="ordinary",
                    evidence=_evidence(text, "欲しい", "手に入れたい"),
                    confidence=0.7,
                )
            )
        if _contains(text, "避けたい", "逃げたい"):
            actions.append(
                ActionTendency(
                    goal="avoid",
                    target_entity_id=person_id,
                    status="intended",
                    origin="self_generated",
                    model_entity_id=None,
                    blocker="fear" if _contains(text, "怖", "恐") else "none",
                    peer_norm="not_applicable",
                    domain="none",
                    excessiveness="ordinary",
                    evidence=_evidence(text, "避けたい", "逃げたい"),
                    confidence=0.7,
                )
            )
        if _contains(text, "褒められたい", "名誉"):
            actions.append(
                ActionTendency(
                    goal="seek_esteem",
                    target_entity_id=None,
                    status="intended",
                    origin="self_generated",
                    model_entity_id=None,
                    blocker="none",
                    peer_norm="not_applicable",
                    domain="esteem",
                    excessiveness="excessive" if _contains(text, "過度", "やめられない") else "ordinary",
                    evidence=_evidence(text, "褒められたい", "名誉"),
                    confidence=0.72,
                )
            )
        domain = (
            "alcohol"
            if _contains(text, "酒", "飲み過ぎ")
            else "food"
            if _contains(text, "食べ過ぎ")
            else "wealth"
            if _contains(text, "金", "富")
            else "sex"
            if _contains(text, "性的", "性")
            else None
        )
        if domain:
            actions.append(
                ActionTendency(
                    goal="possess",
                    target_entity_id=None,
                    status="performed" if _contains(text, "過ぎ") else "intended",
                    origin="self_generated",
                    model_entity_id=None,
                    blocker="none",
                    peer_norm="not_applicable",
                    domain=domain,
                    excessiveness="excessive" if _contains(text, "やめられない", "過度", "過ぎ") else "ordinary",
                    evidence=_evidence(text, "酒", "飲み過ぎ", "食べ過ぎ", "金", "富", "性的", "性"),
                    confidence=0.72,
                )
            )
        return actions


def _matching_words(text: str, words: tuple[str, ...]) -> tuple[str, ...]:
    found = tuple(word for word in words if word in text)
    return found or (text[: min(len(text), 12)],)


class OpenAIDiaryAnalyzer:
    """OpenAI Responses API analyzer using two-stage Pydantic structured output."""

    provider = "openai"
    prompt_version = "diary-features-v2"

    def analyze(self, text: str, *, model: str, api_key: str | None = None) -> AnalyzerResponse:
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AnalyzerError("OpenAI APIキーが設定されていません。")

        client = self._create_client(api_key)
        responses = []
        try:
            segmentation_response = self._parse_segmentation(client, model, text)
            responses.append(segmentation_response)
            segmentation = getattr(segmentation_response, "output_parsed", None)
            if segmentation is None:
                raise AnalyzerError("OpenAI応答からEpisode分割結果を取得できませんでした。")
            if not segmentation.episodes:
                raise AnalyzerError("Episodeが抽出されませんでした。")
            segmentation = DiarySegmentationSchema(
                episodes=[
                    normalize_episode_span(span, text)
                    for span in segmentation.episodes
                ]
            )

            features: list[EpisodeFeatureSchema] = []
            actual_model = getattr(segmentation_response, "model", model)
            for span in segmentation.episodes:
                feature_response, feature = self._extract_feature_with_one_repair(
                    client, model, text, span
                )
                responses.append(feature_response)
                actual_model = getattr(feature_response, "model", actual_model)
                features.append(feature)
        except AnalyzerError:
            raise
        except Exception as exc:
            raise AnalyzerError(self._friendly_openai_error(exc)) from exc

        response_ids = [getattr(response, "id", None) for response in responses if getattr(response, "id", None)]
        return AnalyzerResponse(
            analysis=DiaryAnalysisSchema(episodes=features),
            response_id=",".join(response_ids) if response_ids else None,
            requested_model=model,
            actual_model=actual_model,
            service_tier=getattr(segmentation_response, "service_tier", "standard"),
            usage=combine_token_usage([extract_token_usage(response) for response in responses]),
            provider="openai",
            prompt_version=self.prompt_version,
            segmentation_json=segmentation.model_dump_json(ensure_ascii=False),
        )

    def _create_client(self, api_key: str):
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - dependency is installed in app env
            raise AnalyzerError("openai パッケージがインストールされていません。") from exc
        return OpenAI(api_key=api_key)

    def _parse_segmentation(self, client, model: str, text: str):
        return client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": self._segmentation_prompt()},
                {"role": "user", "content": text},
            ],
            text_format=DiarySegmentationSchema,
            store=False,
        )

    def _parse_feature(self, client, model: str, diary_text: str, span: EpisodeSpan, repair_note: str | None = None):
        user_text = (
            f"日記全体:\n{diary_text}\n\n"
            f"確定済みEpisode境界:\n"
            f"episode_id={span.episode_id}\n"
            f"start_char={span.start_char}\n"
            f"end_char={span.end_char}\n"
            f"text={span.text}"
        )
        if repair_note:
            user_text = f"{user_text}\n\n前回の不整合: {repair_note}\nこの不整合だけを修正してください。"
        return client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": self._feature_prompt()},
                {"role": "user", "content": user_text},
            ],
            text_format=EpisodeFeatureSchema,
            store=False,
        )

    def _extract_feature_with_one_repair(
        self,
        client,
        model: str,
        diary_text: str,
        span: EpisodeSpan,
    ) -> tuple[object, EpisodeFeatureSchema]:
        first = self._parse_feature(client, model, diary_text, span)
        feature = getattr(first, "output_parsed", None)
        if feature is None:
            raise AnalyzerError("OpenAI応答からEpisode特徴を取得できませんでした。")
        try:
            return first, normalize_episode_feature(feature, diary_text, span)
        except AnalyzerError as exc:
            repair = self._parse_feature(client, model, diary_text, span, str(exc))
            repaired_feature = getattr(repair, "output_parsed", None)
            if repaired_feature is None:
                raise AnalyzerError("OpenAI応答から修正後Episode特徴を取得できませんでした。") from exc
            return repair, normalize_episode_feature(repaired_feature, diary_text, span)

    @staticmethod
    def _segmentation_prompt() -> str:
        return (
            "あなたは日記をEpisodeへ分割します。情動名を返さず、診断や人格断定をしません。"
            "主な出来事、主な対象、主な原因、時間方向が共通するまとまりを1つのEpisodeとします。"
            "複数情動が成立するという理由だけでEpisodeを分割しません。"
            "start_char/end_char/textは日記本文の文字位置と完全一致させ、textを言い換えません。"
        )

    @staticmethod
    def _feature_prompt() -> str:
        return (
            "あなたは確定済みEpisode本文から、人物・原因・対象・行為・時間・関係だけを抽出します。"
            "情動名を返さず、最終的なスピノザ情動名はPython側が決めます。"
            "医学的・心理学的診断をせず、人格を断定せず、日記にない事実を推測しません。"
            "判断できない場合はunknownを選び、unknownと否定を区別してください。"
            "同じ人物・対象は同じentity_idで参照し、日記の書き手はselfにしてください。"
            "各判断には本文の直接引用EvidenceSpanを付け、引用を言い換えないでください。"
            "同一Episode内に増大と減少、複数の行為傾向が共存してよいです。"
            "Episode境界を変更せず、start_char/end_char/textを指定値と完全一致させてください。"
        )

    @staticmethod
    def _friendly_openai_error(exc: Exception) -> str:
        name = type(exc).__name__
        if name == "RateLimitError":
            return (
                "OpenAI APIのレート制限または利用上限に達しました。"
                "少し時間を置くか、設定タブで別モデルを選択してください。"
            )
        if name == "AuthenticationError":
            return "OpenAI APIキーを確認できませんでした。設定タブでAPIキーを確認してください。"
        if name == "PermissionDeniedError":
            return "このAPIキーでは選択したモデルを利用できません。設定タブで別モデルを選択してください。"
        return f"OpenAI API解析に失敗しました: {name}"
