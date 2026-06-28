"""Static catalog for Spinoza Part III Definitiones Affectuum."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


SourceAlignment = Literal[
    "canonical",
    "translation_variant",
    "project_extension",
    "needs_review",
]


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
    source_alignment: SourceAlignment


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
    ("Poenitentia", "Repentance", "後悔", (ClassificationKind.SELF_APPRAISAL,), TemporalScope.EPISODE),
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
    ("Crudelitas seu Saevitia", "Cruelty", "残虐", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Timor", "Timidity", "小心", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Audacia", "Daring", "大胆", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Pusillanimitas", "Cowardice", "臆病", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.PERIOD),
    ("Consternatio", "Consternation", "狼狽", (ClassificationKind.ACTION_TENDENCY,), TemporalScope.EPISODE),
    ("Humanitas seu Modestia", "Courtesy", "人間味", (ClassificationKind.SOCIAL_AFFECT,), TemporalScope.EPISODE),
    ("Ambitio", "Ambition", "名誉欲", (ClassificationKind.DESIRE_TENDENCY,), TemporalScope.PERIOD),
    ("Luxuria", "Luxury", "過度な飲食欲", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
    ("Ebrietas", "Drunkenness", "過度な飲酒欲", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
    ("Avaritia", "Avarice", "富への過度な欲望", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
    ("Libido", "Lust", "肉欲", (ClassificationKind.EXCESSIVE_DESIRE_PATTERN,), TemporalScope.LONGITUDINAL),
)


_JAPANESE_TRANSLATIONS: tuple[str, ...] = (
    "欲望とは、人間の本質そのものである。ただし、その本質が何らかの自己の変状によって、ある行為へ決定されていると考えられる限りにおいてである。",
    "喜びとは、人間がより小さい完全性から、より大きい完全性へ移ることである。",
    "悲しみとは、人間がより大きい完全性から、より小さい完全性へ移ることである。",
    "驚異とは、精神がある事物の表象にとどまることである。その表象が他の表象と結びつかないためである。",
    "軽視とは、ある事物の表象が精神にほとんど触れず、その事物の現前が、事物にあるものより、そこにないものを表象させることである。",
    "愛とは、外的原因の観念を伴う喜びである。",
    "憎しみとは、外的原因の観念を伴う悲しみである。",
    "好感とは、偶然に喜びの原因となる事物の観念を伴う喜びである。",
    "反感とは、偶然に悲しみの原因となる事物の観念を伴う悲しみである。",
    "心酔とは、私たちが驚異を抱く者への愛である。",
    "嘲笑とは、私たちが憎むものの中に、軽視する何かがあると表象することから生じる喜びである。",
    "希望とは、結果についていくらか疑っている未来または過去の事物の観念から生じる、不安定な喜びである。",
    "恐れとは、結果についていくらか疑っている未来または過去の事物の観念から生じる、不安定な悲しみである。",
    "安心とは、疑う原因が取り除かれた未来または過去の事物の観念から生じる喜びである。",
    "絶望とは、疑う原因が取り除かれた未来または過去の事物の観念から生じる悲しみである。",
    "予期した喜びとは、期待していたよりよく起こった過去の事物の観念を伴う喜びである。",
    "良心の呵責とは、期待していたより悪く起こった過去の事物の観念を伴う悲しみである。",
    "憐れみとは、私たちに似ていると表象する他者に起こった害悪の観念を伴う悲しみである。",
    "好意とは、他者に利益を与えた者への愛である。",
    "憤慨とは、他者に害悪を与えた者への憎しみである。",
    "買いかぶりとは、愛のために、ある者を正当以上に高く評価することである。",
    "見くびりとは、憎しみのために、ある者を正当以下に低く評価することである。",
    "嫉妬とは、他者の幸福を悲しませ、反対に他者の不幸を喜ばせる限りでの憎しみである。",
    "同情とは、私たちが憐れむ者に利益を与えようとする欲望である。",
    "自己満足とは、人間が自己自身とその行為能力を観想することから生じる喜びである。",
    "謙遜とは、人間が自己の無能力または弱さを観想することから生じる悲しみである。",
    "後悔とは、私たちが精神の自由な決定によって行ったと信じる行為の観念を伴う悲しみである。",
    "高慢とは、自己への愛のために、自分を正当以上に高く評価することである。",
    "自己卑下とは、悲しみのために、自分を正当以下に低く評価することである。",
    "名誉とは、他者から称賛されると表象する何らかの自己の行為の観念を伴う喜びである。",
    "恥とは、他者から非難されると表象する何らかの自己の行為の観念を伴う悲しみである。",
    "懐旧とは、ある事物を所有したいという欲望または衝動である。その事物の記憶によって養われるが、同時にそれを排除する他の事物の記憶によって抑えられる。",
    "競争心とは、他者がある事物への欲望を持つと表象することによって、私たちのうちに生じる同じ事物への欲望である。",
    "感謝とは、愛の感情によって、私たちに同じ愛の感情から利益を与えた者に利益を与えようと努める欲望または愛の熱意である。",
    "親切とは、私たちが憐れむ者に利益を与えようとする欲望である。",
    "怒りとは、憎しみによって、憎む者に害悪を加えようと駆り立てられる欲望である。",
    "復讐とは、相互の憎しみによって、同じ感情から私たちに損害を与えた者に害悪を加えようと駆り立てられる欲望である。",
    "残虐または残忍とは、私たちが愛する者または憐れむ者に害悪を加えようと駆り立てられる欲望である。",
    "小心とは、より大きな害悪を避けるために、より小さな害悪を欲することである。",
    "大胆とは、同等の人々が恐れて引き受けない危険なことを行うよう駆り立てる欲望である。",
    "臆病とは、同等の人々があえて引き受ける害悪への恐れによって、その者の欲望が抑えられることである。",
    "狼狽とは、避けようとする害悪への驚異によって、その害悪を避ける欲望が抑えられることである。",
    "人間味または慎みとは、人々を喜ばせることを行い、人々を不快にすることを避けようとする欲望である。",
    "名誉欲とは、名誉への過度な欲望である。",
    "過度な飲食欲とは、食事をともにすることへの過度な欲望または愛である。",
    "過度な飲酒欲とは、飲むことへの過度な欲望または愛である。",
    "富への過度な欲望とは、富への過度な欲望または愛である。",
    "肉欲とは、身体を結合させることへの欲望または愛である。",
)


def load_affect_catalog() -> list[AffectDefinition]:
    """Load the bundled 48-definition catalog."""

    source = "Benedict de Spinoza, Ethics Part III, Definitiones Affectuum; public-domain Latin and Elwes-era English editions consulted."
    rights = "public_domain_source_with_project_translation"
    evidence = "Spinoza's 17th-century Latin text is public domain; project Japanese text is original wording for this application."
    items: list[AffectDefinition] = []
    for index, (latin, english, japanese, kinds, scope) in enumerate(_NAMES, start=1):
        canonical_id = f"P3-DA-{index:02d}"
        dependencies: tuple[str, ...]
        if index in (1, 2, 3, 4, 5):
            dependencies = ()
        elif index in (6, 8, 10, 12, 14, 16, 19, 21, 25, 28, 30, 34, 35, 40, 43):
            dependencies = ("P3-DA-02",)
        elif index in (7, 9, 11, 13, 15, 17, 18, 20, 22, 23, 24, 26, 27, 29, 31, 36, 37, 38, 39, 41, 42):
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
                japanese_translation=f"定義{index}: {_JAPANESE_TRANSLATIONS[index - 1]}",
                summary=f"{japanese}を、Episode特徴または期間特徴から多ラベルで判定する。",
                source_alignment="canonical",
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
