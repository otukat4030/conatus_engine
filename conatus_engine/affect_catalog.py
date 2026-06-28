"""Static catalog for Spinoza Part III Definitiones Affectuum."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClassificationKind(str, Enum):
    PRIMARY_AFFECT = "primary_affect"
    IMAGINATION_STATE = "imagination_state"
    COMPOSITE_AFFECT = "composite_affect"
    SELF_APPRAISAL = "self_appraisal"
    SOCIAL_AFFECT = "social_affect"
    DESIRE_TENDENCY = "desire_tendency"
    ACTION_TENDENCY = "action_tendency"
    EXCESSIVE_DESIRE_PATTERN = "excessive_desire_pattern"


class TemporalScope(str, Enum):
    EPISODE = "episode"
    DIARY_ENTRY = "diary_entry"
    PERIOD = "period"
    LONGITUDINAL = "longitudinal"


@dataclass(frozen=True)
class AffectDefinition:
    canonical_id: str
    number: int
    latin_name: str
    english_name: str
    japanese_name: str
    classification: tuple[ClassificationKind, ...]
    temporal_scope: TemporalScope
    dependencies: tuple[str, ...]
    rule_id: str
    source: str
    rights_status: str
    rights_evidence: str
    public_domain_text: str
    japanese_translation: str
    summary: str


_NAMES: tuple[tuple[str, str, str, tuple[ClassificationKind, ...], TemporalScope], ...] = (
    ("Cupiditas", "Desire", "欲望", (ClassificationKind.PRIMARY_AFFECT,), TemporalScope.EPISODE),
    ("Laetitia", "Joy", "喜び", (ClassificationKind.PRIMARY_AFFECT,), TemporalScope.EPISODE),
    ("Tristitia", "Sadness", "悲しみ", (ClassificationKind.PRIMARY_AFFECT,), TemporalScope.EPISODE),
    ("Admiratio", "Wonder", "驚異", (ClassificationKind.IMAGINATION_STATE,), TemporalScope.EPISODE),
    ("Contemptus", "Contempt", "軽視", (ClassificationKind.IMAGINATION_STATE,), TemporalScope.EPISODE),
    ("Amor", "Love", "愛", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Odium", "Hatred", "憎しみ", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Propensio", "Inclination", "好感", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Aversio", "Aversion", "反感", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Devotio", "Devotion", "心酔", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Irrisio", "Derision", "嘲笑", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Spes", "Hope", "希望", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Metus", "Fear", "恐れ", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Securitas", "Confidence", "安心", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Desperatio", "Despair", "絶望", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Gaudium", "Gladness", "予期した喜び", (ClassificationKind.COMPOSITE_AFFECT,), TemporalScope.EPISODE),
    ("Conscientiae morsus", "Remorse", "良心の呵責", (ClassificationKind.SELF_APPRAISAL,), TemporalScope.EPISODE),
    ("Commiseratio", "Pity", "憐れみ", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Favor", "Approval", "好意", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Indignatio", "Indignation", "憤慨", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Existimatio", "Overestimation", "買いかぶり", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Despectus", "Disparagement", "見くびり", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Invidia", "Envy", "嫉妬", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Misericordia", "Mercy", "同情", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Acquiescentia in se ipso", "Self-contentment", "自己満足", (ClassificationKind.SELF_APPRAISAL,), TemporalScope.EPISODE),
    ("Humilitas", "Humility", "謙遜", (ClassificationKind.SELF_APPRAISAL,), TemporalScope.EPISODE),
    ("Superbia", "Pride", "高慢", (ClassificationKind.SELF_APPRAISAL,), TemporalScope.EPISODE),
    ("Abjectio", "Self-abasement", "自己卑下", (ClassificationKind.SELF_APPRAISAL,), TemporalScope.EPISODE),
    ("Gloria", "Honor", "名誉", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Pudor", "Shame", "恥", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Desiderium", "Longing", "懐旧", (ClassificationKind.DESIRE_TENDENCY,), TemporalScope.DIARY_ENTRY),
    ("Aemulatio", "Emulation", "競争心", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Gratia", "Thankfulness", "感謝", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Benevolentia", "Benevolence", "親切", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Ira", "Anger", "怒り", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Vindicta", "Revenge", "復讐", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Clementia", "Clemency", "寛容", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Timor", "Timidity", "小心", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Audacia", "Daring", "大胆", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Pusillanimitas", "Cowardice", "臆病", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.PERIOD),
    ("Consternatio", "Consternation", "狼狽", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Humanitas", "Courtesy", "人間味", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Ambitio", "Ambition", "名誉欲", (ClassificationKind.DESIRE_TENDENCY,), TemporalScope.PERIOD),
    ("Luxuria", "Luxury", "過度な飲食欲", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
    ("Ebrietas", "Drunkenness", "過度な飲酒欲", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
    ("Avaritia", "Avarice", "富への過度な欲望", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
    ("Libido", "Lust", "過度な性的欲望", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
    ("Desiderium immoderatum", "Immoderate desire", "その他の過度な欲望", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
)


def load_affect_catalog() -> list[AffectDefinition]:
    """Load the bundled 48-definition catalog."""

    source = "Benedict de Spinoza, Ethics Part III, Definitiones Affectuum; public-domain Latin and Elwes-era English editions consulted."
    rights = "public_domain_source_with_project_translation"
    evidence = "Spinoza's 17th-century Latin text is public domain; project Japanese text is original provisional wording."
    items: list[AffectDefinition] = []
    for index, (latin, english, japanese, kinds, scope) in enumerate(_NAMES, start=1):
        canonical_id = f"P3-DA-{index:02d}"
        dependencies: tuple[str, ...]
        if index in (1, 2, 3, 4, 5):
            dependencies = ()
        elif index in (6, 8, 10, 12, 14, 16, 19, 21, 25, 27, 29, 33, 34, 37, 39, 42, 43):
            dependencies = ("P3-DA-02",)
        elif index in (7, 9, 11, 13, 15, 17, 18, 20, 22, 23, 24, 26, 28, 30, 35, 36, 38, 40, 41):
            dependencies = ("P3-DA-03",)
        else:
            dependencies = ("P3-DA-01",)
        items.append(
            AffectDefinition(
                canonical_id=canonical_id,
                number=index,
                latin_name=latin,
                english_name=english,
                japanese_name=japanese,
                classification=kinds,
                temporal_scope=scope,
                dependencies=dependencies,
                rule_id=f"affect.{canonical_id.lower()}",
                source=source,
                rights_status=rights,
                rights_evidence=evidence,
                public_domain_text=(
                    f"Definition {index}: {english} as represented in public-domain editions of Spinoza's Part III affect definitions."
                ),
                japanese_translation=(
                    f"定義{index}: {japanese}。これは原典読解のためのプロジェクト独自の暫定訳です。"
                ),
                summary=f"{japanese}を、Episode特徴または期間特徴から多ラベルで判定する。",
            )
        )
    return items


def validate_affect_catalog(items: list[AffectDefinition] | None = None) -> list[str]:
    """Return catalog completeness errors."""

    items = items or load_affect_catalog()
    errors: list[str] = []
    if len(items) != 48:
        errors.append("catalog must contain exactly 48 numbered definitions")
    numbers = [item.number for item in items]
    if numbers != list(range(1, 49)):
        errors.append("definition numbers must be continuous from 1 to 48")
    ids = [item.canonical_id for item in items]
    if len(set(ids)) != len(ids):
        errors.append("canonical IDs must be unique")
    for item in items:
        expected = f"P3-DA-{item.number:02d}"
        if item.canonical_id != expected:
            errors.append(f"{item.canonical_id}: expected {expected}")
        for field_name in (
            "latin_name",
            "english_name",
            "japanese_name",
            "source",
            "rights_status",
            "rights_evidence",
            "public_domain_text",
            "japanese_translation",
            "summary",
            "rule_id",
        ):
            if not getattr(item, field_name):
                errors.append(f"{item.canonical_id}: {field_name} is required")
        for dependency in item.dependencies:
            if dependency not in ids:
                errors.append(f"{item.canonical_id}: missing dependency {dependency}")
    return errors
