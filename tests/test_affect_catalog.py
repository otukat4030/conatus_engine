from conatus_engine.affect_catalog import load_affect_catalog, validate_affect_catalog
from conatus_engine.affect_rules import (
    classify_affect_roles,
    evaluate_all_affects,
    make_empty_feature,
    select_primary_affect,
    validate_rule_engine,
)
from conatus_engine.diary_analyzer import MockDiaryAnalyzer


def _mock_feature(text: str):
    return MockDiaryAnalyzer().analyze(text).analysis.episodes[0]


def test_affect_catalog_contains_48_continuous_definitions() -> None:
    items = load_affect_catalog()

    assert len(items) == 48
    assert [item.number for item in items] == list(range(1, 49))
    assert items[0].canonical_id == "P3-DA-01"
    assert items[26].canonical_id == "P3-DA-27"
    assert items[26].latin_name == "Poenitentia"
    assert items[26].japanese_name == "後悔"
    assert items[-1].canonical_id == "P3-DA-48"
    assert items[-1].latin_name == "Libido"
    assert validate_affect_catalog(items) == []


def test_affect_catalog_has_source_rights_translation_alignment_and_rules() -> None:
    for item in load_affect_catalog():
        assert item.public_domain_text
        assert item.japanese_translation
        assert item.source
        assert item.rights_status
        assert item.rights_evidence
        assert item.rule_id
        assert item.source_alignment in {
            "canonical",
            "translation_variant",
            "project_extension",
            "needs_review",
        }


def test_rule_engine_evaluates_all_48_definitions() -> None:
    features = _mock_feature("明日の仕事が成功する希望があるが、まだ不安かもしれない。")

    results = evaluate_all_affects(features)

    assert len(results) == 48
    assert {result.affect_id for result in results} == {
        f"P3-DA-{number:02d}" for number in range(1, 49)
    }
    assert any(result.affect_id == "P3-DA-12" and result.status == "matched" for result in results)
    assert validate_rule_engine() == []


def test_rule_engine_selects_one_primary_affect_per_episode() -> None:
    features = _mock_feature("友人に助けてもらい感謝してうれしかった。")

    result = select_primary_affect(features)

    assert result.japanese_name == "感謝"
    assert result.status == "matched"
    assert "原典訳: 定義34" in result.reason
    assert result.trace.satisfied_conditions


def test_rule_engine_maps_repentance_to_definition_27() -> None:
    features = _mock_feature("昨日の自分の発言を後悔して申し訳なかった。")

    result = select_primary_affect(features)

    assert result.affect_id == "P3-DA-27"
    assert result.japanese_name == "後悔"
    assert "原典訳: 定義27" in result.reason


def test_rule_engine_does_not_fallback_to_desire_when_evidence_is_insufficient() -> None:
    result = select_primary_affect(make_empty_feature())

    assert result.affect_id == "UNCLASSIFIED"
    assert result.japanese_name == "未分類"
    assert result.status == "insufficient_evidence"


def test_affect_roles_split_gratitude_and_base_joy() -> None:
    features = _mock_feature("友人に助けてもらい感謝してうれしかった。")

    results = classify_affect_roles(features)

    assert _names_by_role(results, "primary") == ["感謝"]
    assert "喜び" in _names_by_role(results, "base")


def test_affect_roles_split_concrete_affect_and_base_sadness() -> None:
    features = _mock_feature("上司に理不尽に責められて、言い返したかったが我慢した。")

    results = classify_affect_roles(features)

    assert _names_by_role(results, "primary")
    assert "悲しみ" in _names_by_role(results, "base")
    assert {"怒り", "復讐"} & set(_names_by_role(results, "primary") + _names_by_role(results, "coexisting"))


def test_affect_roles_keep_coexisting_specific_affects() -> None:
    features = _mock_feature("友人に助けてもらい感謝してうれしかった。")

    results = classify_affect_roles(features)

    assert _names_by_role(results, "primary") == ["感謝"]
    assert "愛" in _names_by_role(results, "coexisting")


def test_affect_roles_mark_unclassified_when_nothing_matches() -> None:
    results = classify_affect_roles(make_empty_feature())

    assert len(results) == 1
    assert results[0].affect_id == "UNCLASSIFIED"
    assert results[0].role == "unclassified"


def _names_by_role(results, role: str) -> list[str]:
    return [result.japanese_name for result in results if result.role == role]
