from conatus_engine.affect_catalog import load_affect_catalog, validate_affect_catalog
from conatus_engine.affect_rules import (
    evaluate_all_affects,
    select_primary_affect,
    validate_rule_engine,
)
from conatus_engine.diary_analyzer import EpisodeFeatureSchema


def test_affect_catalog_contains_48_continuous_definitions() -> None:
    items = load_affect_catalog()

    assert len(items) == 48
    assert [item.number for item in items] == list(range(1, 49))
    assert items[0].canonical_id == "P3-DA-01"
    assert items[-1].canonical_id == "P3-DA-48"
    assert validate_affect_catalog(items) == []


def test_affect_catalog_has_source_rights_translation_and_rules() -> None:
    for item in load_affect_catalog():
        assert item.public_domain_text
        assert item.japanese_translation
        assert item.source
        assert item.rights_status
        assert item.rights_evidence
        assert item.rule_id


def test_rule_engine_evaluates_all_48_definitions() -> None:
    features = EpisodeFeatureSchema(
        summary="hopeful success",
        evidence_text="仕事が成功して希望がある",
        power_direction="increase",
        intensity=3,
        confidence=0.9,
        desire_present=True,
        temporal_orientation="future",
        outcome_uncertain=True,
    )

    results = evaluate_all_affects(features)

    assert len(results) == 48
    assert {result.affect_id for result in results} == {
        f"P3-DA-{number:02d}" for number in range(1, 49)
    }
    assert any(result.affect_id == "P3-DA-12" and result.status == "matched" for result in results)
    assert validate_rule_engine() == []


def test_rule_engine_selects_one_primary_affect_per_episode() -> None:
    features = EpisodeFeatureSchema(
        summary="感謝",
        evidence_text="友人に助けてもらい感謝した",
        power_direction="increase",
        intensity=3,
        confidence=0.9,
        gratitude=True,
    )

    result = select_primary_affect(features)

    assert result.japanese_name == "感謝"
    assert result.status == "matched"


def test_rule_engine_does_not_fallback_to_desire_when_evidence_is_insufficient() -> None:
    features = EpisodeFeatureSchema(
        summary="neutral",
        evidence_text="今日は机の上に本があった",
        power_direction="neutral",
        intensity=0,
        confidence=0.6,
    )

    result = select_primary_affect(features)

    assert result.affect_id == "UNCLASSIFIED"
    assert result.japanese_name == "未分類"
    assert result.status == "insufficient_evidence"
