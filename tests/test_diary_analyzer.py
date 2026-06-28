import pytest

from conatus_engine.diary_analyzer import AnalyzerError, MockDiaryAnalyzer, OpenAIDiaryAnalyzer


def test_mock_diary_analyzer_returns_structured_features() -> None:
    response = MockDiaryAnalyzer().analyze("今日は成功してうれしかった。希望がある。")

    assert response.analysis.episodes
    assert response.usage is not None
    assert response.analysis.episodes[0].power_direction == "increase"


def test_mock_diary_analyzer_splits_multiple_episodes() -> None:
    response = MockDiaryAnalyzer().analyze("今日は成功してうれしかった。夕方は不安で悲しかった。")

    assert len(response.analysis.episodes) == 2
    assert response.analysis.episodes[0].power_direction == "increase"
    assert response.analysis.episodes[1].power_direction == "decrease"


def test_openai_analyzer_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AnalyzerError):
        OpenAIDiaryAnalyzer().analyze("test", model="gpt-5.4-mini")
