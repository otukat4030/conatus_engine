"""Deterministic 48-affect rule engine."""

from __future__ import annotations

from dataclasses import dataclass

from conatus_engine.affect_catalog import (
    AffectDefinition,
    ClassificationKind,
    TemporalScope,
    load_affect_catalog,
)
from conatus_engine.diary_analyzer import EpisodeFeatureSchema


@dataclass(frozen=True)
class AffectEvaluation:
    affect_id: str
    japanese_name: str
    status: str
    reason: str
    evidence_text: str
    confidence: float


def _base_conf(features: EpisodeFeatureSchema, multiplier: float = 1.0) -> float:
    return round(max(0.0, min(features.confidence * multiplier, 1.0)), 2)


def _longitudinal_status(features: EpisodeFeatureSchema, domain: str | None = None) -> str:
    if not features.explicit_excess:
        return "candidate" if domain and features.excess_domain == domain else "insufficient_evidence"
    if domain is None or features.excess_domain == domain:
        return "matched"
    return "insufficient_evidence"


def evaluate_affect(definition: AffectDefinition, features: EpisodeFeatureSchema) -> AffectEvaluation:
    """Evaluate one affect definition against one episode feature set."""

    pid = definition.canonical_id
    direction = features.power_direction
    status = "insufficient_evidence"
    reason = "必要な意味特徴が不足しています。"
    confidence = _base_conf(features, 0.55)

    if pid == "P3-DA-01" and features.desire_present:
        status, reason, confidence = "matched", "欲望または行動への傾向が明示されています。", _base_conf(features)
    elif pid == "P3-DA-02" and direction == "increase":
        status, reason, confidence = "matched", "力能の増加として抽出されています。", _base_conf(features)
    elif pid == "P3-DA-03" and direction == "decrease":
        status, reason, confidence = "matched", "力能の減少として抽出されています。", _base_conf(features)
    elif pid == "P3-DA-04" and features.admiration:
        status, reason, confidence = "matched", "対象への驚き・注意の固着が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-05" and features.contempt:
        status, reason, confidence = "matched", "対象を軽く見る表現が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-06" and direction == "increase" and features.external_cause:
        status, reason, confidence = "matched", "喜びと外的原因の観念が同時にあります。", _base_conf(features)
    elif pid == "P3-DA-07" and direction == "decrease" and features.external_cause:
        status, reason, confidence = "matched", "悲しみと外的原因の観念が同時にあります。", _base_conf(features)
    elif pid == "P3-DA-08" and direction == "increase" and not features.external_cause and features.target_present:
        status, reason, confidence = "candidate", "対象への好ましい傾きがありますが外的原因の証拠は限定的です。", _base_conf(features, 0.75)
    elif pid == "P3-DA-09" and direction == "decrease" and not features.external_cause and features.target_present:
        status, reason, confidence = "candidate", "対象への反感がありますが外的原因の証拠は限定的です。", _base_conf(features, 0.75)
    elif pid == "P3-DA-10" and features.admiration and direction == "increase":
        status, reason, confidence = "matched", "驚異と喜びが結びついています。", _base_conf(features)
    elif pid == "P3-DA-11" and features.contempt and direction == "decrease":
        status, reason, confidence = "matched", "軽視と悲しみ/反発が結びついています。", _base_conf(features)
    elif pid == "P3-DA-12" and features.temporal_orientation == "future" and features.outcome_uncertain and direction != "decrease":
        status, reason, confidence = "matched", "未来の不確実な結果への喜び寄りの期待です。", _base_conf(features)
    elif pid == "P3-DA-13" and features.temporal_orientation == "future" and features.outcome_uncertain and direction == "decrease":
        status, reason, confidence = "matched", "未来の不確実な結果への悲しみ寄りの予期です。", _base_conf(features)
    elif pid == "P3-DA-14" and features.doubt_removed and direction == "increase":
        status, reason, confidence = "matched", "不確実性が解け、喜びが残っています。", _base_conf(features)
    elif pid == "P3-DA-15" and features.doubt_removed and direction == "decrease":
        status, reason, confidence = "matched", "不確実性が解け、悲しみが残っています。", _base_conf(features)
    elif pid == "P3-DA-16" and features.expectation_confirmed and direction == "increase":
        status, reason, confidence = "matched", "期待した結果による喜びです。", _base_conf(features)
    elif pid == "P3-DA-17" and (features.remorse or features.expectation_disconfirmed) and direction == "decrease":
        status, reason, confidence = "matched", "自分の行為または結果への後悔が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-18" and features.target_fortune == "bad" and features.reaction_to_target_fortune == "negative":
        status, reason, confidence = "matched", "他者の不幸に対する悲しみです。", _base_conf(features)
    elif pid == "P3-DA-19" and features.target_fortune == "good" and features.reaction_to_target_fortune == "positive":
        status, reason, confidence = "matched", "他者の幸福に対する喜びです。", _base_conf(features)
    elif pid == "P3-DA-20" and features.target_fortune == "good" and features.reaction_to_target_fortune == "negative":
        status, reason, confidence = "matched", "他者の幸福に対する否定的反応です。", _base_conf(features)
    elif pid == "P3-DA-21" and features.other_appraisal == "over":
        status, reason, confidence = "matched", "他者を正当以上に評価しています。", _base_conf(features)
    elif pid == "P3-DA-22" and features.other_appraisal == "under":
        status, reason, confidence = "matched", "他者を正当以下に評価しています。", _base_conf(features)
    elif pid == "P3-DA-23" and features.target_fortune == "good" and features.reaction_to_target_fortune == "negative":
        status, reason, confidence = "candidate", "嫉妬に近い反応ですが比較対象の証拠が限定的です。", _base_conf(features, 0.7)
    elif pid == "P3-DA-24" and features.kindness and features.target_fortune == "bad":
        status, reason, confidence = "matched", "不幸な他者を助けようとする傾向です。", _base_conf(features)
    elif pid == "P3-DA-25" and features.self_appraisal in ("fair", "over") and direction == "increase":
        status, reason, confidence = "candidate", "自己の力能への満足が読み取れます。", _base_conf(features, 0.75)
    elif pid == "P3-DA-26" and features.self_appraisal == "under" and direction == "decrease":
        status, reason, confidence = "matched", "自己を低く評価する悲しみです。", _base_conf(features)
    elif pid == "P3-DA-27" and features.self_appraisal == "over":
        status, reason, confidence = "matched", "自己を正当以上に評価しています。", _base_conf(features)
    elif pid == "P3-DA-28" and features.self_appraisal == "under":
        status, reason, confidence = "matched", "自己を正当以下に評価しています。", _base_conf(features)
    elif pid == "P3-DA-29" and features.imagined_social_judgment == "praise":
        status, reason, confidence = "matched", "称賛される想像が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-30" and (features.shame or features.imagined_social_judgment == "blame"):
        status, reason, confidence = "matched", "非難や恥の想像が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-31" and features.longing:
        status, reason, confidence = "matched", "過去のものへの恋しさが抽出されています。", _base_conf(features)
    elif pid == "P3-DA-32" and features.action_tendency in ("imitate", "challenge"):
        status, reason, confidence = "matched", "他者に倣う/競う行動傾向です。", _base_conf(features)
    elif pid == "P3-DA-33" and features.gratitude:
        status, reason, confidence = "matched", "感謝が明示されています。", _base_conf(features)
    elif pid == "P3-DA-34" and features.action_tendency == "help":
        status, reason, confidence = "matched", "他者を助けようとする行動傾向です。", _base_conf(features)
    elif pid == "P3-DA-35" and features.anger:
        status, reason, confidence = "matched", "怒りが明示されています。", _base_conf(features)
    elif pid == "P3-DA-36" and features.revenge:
        status, reason, confidence = "matched", "仕返し・復讐への傾向が明示されています。", _base_conf(features)
    elif pid == "P3-DA-37" and features.action_tendency == "restrain":
        status, reason, confidence = "matched", "害を与える行為を控える傾向です。", _base_conf(features)
    elif pid == "P3-DA-38" and features.danger_present and features.action_tendency == "avoid":
        status, reason, confidence = "matched", "危険を避ける小心が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-39" and features.danger_present and features.action_tendency == "dare":
        status, reason, confidence = "matched", "危険へ向かう大胆さが抽出されています。", _base_conf(features)
    elif pid == "P3-DA-40" and features.danger_present and features.action_tendency == "avoid":
        status, reason, confidence = "candidate", "臆病の候補ですが期間的反復の確認が必要です。", _base_conf(features, 0.65)
    elif pid == "P3-DA-41" and features.action_tendency == "freeze":
        status, reason, confidence = "matched", "行動不能に近い狼狽が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-42" and features.kindness:
        status, reason, confidence = "matched", "穏やかな親切・人間味が抽出されています。", _base_conf(features)
    elif pid == "P3-DA-43" and features.imagined_social_judgment == "praise":
        status, reason, confidence = "candidate", "名誉欲の候補ですが反復または欲望の明示が必要です。", _base_conf(features, 0.65)
    elif pid == "P3-DA-44":
        status = _longitudinal_status(features, "food")
        reason = "飲食に関する過度性を評価しました。"
    elif pid == "P3-DA-45":
        status = _longitudinal_status(features, "alcohol")
        reason = "飲酒に関する過度性を評価しました。"
    elif pid == "P3-DA-46":
        status = _longitudinal_status(features, "money")
        reason = "富への欲望の過度性を評価しました。"
    elif pid == "P3-DA-47":
        status = _longitudinal_status(features, "sex")
        reason = "性的欲望の過度性を評価しました。"
    elif pid == "P3-DA-48":
        status = _longitudinal_status(features, "other")
        reason = "その他の欲望の過度性を評価しました。"

    if definition.temporal_scope is TemporalScope.LONGITUDINAL and status == "matched":
        confidence = _base_conf(features, 0.9)
    return AffectEvaluation(
        affect_id=definition.canonical_id,
        japanese_name=definition.japanese_name,
        status=status,
        reason=reason,
        evidence_text=features.evidence_text,
        confidence=confidence,
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

    return AffectEvaluation(
        affect_id="UNCLASSIFIED",
        japanese_name="未分類",
        status="insufficient_evidence",
        reason="必要な意味情報が不足しているため、48情動の代表情動を決定できません。",
        evidence_text=features.evidence_text,
        confidence=_base_conf(features, 0.55),
    )


def _primary_score(result: AffectEvaluation, definition: AffectDefinition) -> tuple[int, int, float, int]:
    status_rank = {
        "matched": 3,
        "candidate": 2,
        "insufficient_evidence": 1,
    }.get(result.status, 0)
    specificity = max(_classification_specificity(kind) for kind in definition.classification)
    return (status_rank, specificity, result.confidence, -definition.number)


def _classification_specificity(kind: ClassificationKind) -> int:
    if kind is ClassificationKind.PRIMARY_AFFECT:
        return 0
    if kind is ClassificationKind.IMAGINATION_STATE:
        return 1
    if kind is ClassificationKind.COMPOSITE_AFFECT:
        return 2
    return 3


def validate_rule_engine() -> list[str]:
    """Validate that every catalog affect has an executable rule."""

    errors: list[str] = []
    neutral = EpisodeFeatureSchema(
        summary="validation",
        evidence_text="validation",
        power_direction="neutral",
        intensity=0,
        confidence=0.5,
    )
    results = evaluate_all_affects(neutral)
    if len(results) != 48:
        errors.append("rule engine must evaluate exactly 48 definitions")
    result_ids = {result.affect_id for result in results}
    catalog_ids = {item.canonical_id for item in load_affect_catalog()}
    if result_ids != catalog_ids:
        errors.append("rule engine IDs must match catalog IDs")
    return errors
