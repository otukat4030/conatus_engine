from types import SimpleNamespace

import pytest

from conatus_engine.diary_analyzer import (
    AnalyzerError,
    DiarySegmentationSchema,
    EpisodeFeatureSchema,
    EpisodeSpan,
    EvidenceSpan,
    MockDiaryAnalyzer,
    OpenAIDiaryAnalyzer,
    normalize_episode_feature,
    normalize_episode_span,
    validate_episode_feature,
)


def test_mock_diary_analyzer_returns_structured_features() -> None:
    response = MockDiaryAnalyzer().analyze("今日は成功してうれしかった。希望がある。")

    assert response.analysis.episodes
    assert response.usage is None
    episode = response.analysis.episodes[0]
    assert episode.power_components.increase_intensity > 0
    assert episode.power_components.decrease_intensity == 0


def test_mock_diary_analyzer_splits_multiple_episodes() -> None:
    response = MockDiaryAnalyzer().analyze("今日は成功してうれしかった。夕方は不安で悲しかった。")

    assert len(response.analysis.episodes) == 2
    assert response.analysis.episodes[0].power_components.increase_intensity > 0
    assert response.analysis.episodes[1].power_components.decrease_intensity > 0


def test_mock_diary_analyzer_is_deterministic_and_evidence_matches() -> None:
    text = "同僚が作業を助けてくれて、ありがたかった。"

    first = MockDiaryAnalyzer().analyze(text).analysis.episodes[0]
    second = MockDiaryAnalyzer().analyze(text).analysis.episodes[0]

    assert first == second
    validate_episode_feature(first, text)
    assert first.social_events[0].effect == "benefit"
    assert first.social_events[0].actor_entity_id == "person-1"
    assert first.social_events[0].recipient_entity_id == "self"
    assert first.entity_stances[0].valence == "positive"
    assert first.action_tendencies[0].goal == "benefit"


def test_mock_handles_restrained_harm_tendency() -> None:
    text = "上司に理不尽に責められて、言い返したかったが我慢した。"

    feature = MockDiaryAnalyzer().analyze(text).analysis.episodes[0]

    validate_episode_feature(feature, text)
    assert any(event.effect == "harm" for event in feature.social_events)
    assert any(stance.valence == "negative" for stance in feature.entity_stances)
    assert any(
        action.goal == "harm" and action.status == "restrained"
        for action in feature.action_tendencies
    )
    assert any(action.goal == "restrain_harm" for action in feature.action_tendencies)


def test_openai_analyzer_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AnalyzerError):
        OpenAIDiaryAnalyzer().analyze("test", model="gpt-5.4-mini")


def test_episode_feature_schema_exposes_new_blocks_and_excludes_old_fields() -> None:
    schema = EpisodeFeatureSchema.model_json_schema()
    properties = schema["properties"]

    for old_field in [
        "gratitude",
        "anger",
        "revenge",
        "remorse",
        "power_direction",
        "external_cause",
        "target_fortune",
        "intensity",
    ]:
        assert old_field not in properties

    for field in [
        "entities",
        "power_components",
        "causal_links",
        "entity_stances",
        "attention_states",
        "temporal_appraisal",
        "social_events",
        "appraisals",
        "action_tendencies",
    ]:
        assert properties[field]["description"]

    power_schema = schema["$defs"]["PowerComponents"]["properties"]
    assert power_schema["increase_intensity"]["minimum"] == 0
    assert power_schema["increase_intensity"]["maximum"] == 5
    assert power_schema["decrease_intensity"]["minimum"] == 0
    assert power_schema["decrease_intensity"]["maximum"] == 5
    assert schema["properties"]["extraction_confidence"]["minimum"] == 0
    assert schema["properties"]["extraction_confidence"]["maximum"] == 1


def test_validate_episode_feature_rejects_bad_evidence_span() -> None:
    text = "今日は成功してうれしかった。"
    feature = MockDiaryAnalyzer().analyze(text).analysis.episodes[0].model_copy(deep=True)
    feature.power_components.increase_evidence = [
        EvidenceSpan(quote="存在しない引用", start_char=0, end_char=7)
    ]

    with pytest.raises(AnalyzerError):
        validate_episode_feature(feature, text)


def test_normalize_episode_span_corrects_offsets_when_text_exists() -> None:
    text = "朝は眠かった。今日は成功してうれしかった。"
    span = EpisodeSpan(
        episode_id="episode-1",
        start_char=0,
        end_char=10,
        text="今日は成功してうれしかった。",
    )

    normalized = normalize_episode_span(span, text)

    assert normalized.start_char == text.index("今日は")
    assert normalized.end_char == len(text)
    assert text[normalized.start_char : normalized.end_char] == normalized.text


def test_normalize_episode_feature_corrects_diary_relative_evidence_offsets() -> None:
    text = "朝は眠かった。今日は成功してうれしかった。"
    span = EpisodeSpan(
        episode_id="episode-1",
        start_char=text.index("今日は"),
        end_char=len(text),
        text="今日は成功してうれしかった。",
    )
    feature = MockDiaryAnalyzer().analyze(span.text).analysis.episodes[0].model_copy(deep=True)
    feature.start_char = 0
    feature.end_char = 1
    feature.power_components.increase_evidence = [
        EvidenceSpan(
            quote="成功",
            start_char=text.index("成功"),
            end_char=text.index("成功") + len("成功"),
        )
    ]

    normalized = normalize_episode_feature(feature, text, span)

    assert normalized.start_char == span.start_char
    assert normalized.end_char == span.end_char
    assert normalized.power_components.increase_evidence[0].start_char == span.text.index("成功")


def test_validate_episode_feature_rejects_unknown_entity_reference() -> None:
    text = "同僚が作業を助けてくれて、ありがたかった。"
    feature = MockDiaryAnalyzer().analyze(text).analysis.episodes[0].model_copy(deep=True)
    feature.entity_stances[0].target_entity_id = "person-999"

    with pytest.raises(AnalyzerError):
        validate_episode_feature(feature, text)


def test_validate_episode_feature_rejects_imitated_action_without_model() -> None:
    text = "友人と同じものが欲しい。"
    feature = MockDiaryAnalyzer().analyze(text).analysis.episodes[0].model_copy(deep=True)
    action = feature.action_tendencies[0].model_copy(update={"origin": "imitated", "model_entity_id": None})
    feature.action_tendencies[0] = action

    with pytest.raises(AnalyzerError):
        validate_episode_feature(feature, text)


class _FakeResponses:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.responses = _FakeResponses(responses)


def test_openai_analyzer_sends_segmentation_then_feature_requests(monkeypatch) -> None:
    diary_text = "今日は成功してうれしかった。"
    feature = MockDiaryAnalyzer().analyze(diary_text).analysis.episodes[0]
    segmentation = DiarySegmentationSchema(
        episodes=[
            EpisodeSpan(
                episode_id="episode-1",
                start_char=0,
                end_char=len(diary_text),
                text=diary_text,
            )
        ]
    )
    fake_client = _FakeClient(
        [
            SimpleNamespace(
                id="seg",
                model="gpt-test",
                service_tier="standard",
                output_parsed=segmentation,
                usage=None,
            ),
            SimpleNamespace(id="feat", model="gpt-test", output_parsed=feature, usage=None),
        ]
    )
    monkeypatch.setattr(OpenAIDiaryAnalyzer, "_create_client", lambda self, api_key: fake_client)

    response = OpenAIDiaryAnalyzer().analyze(diary_text, model="gpt-test", api_key="sk-test")

    assert len(fake_client.responses.calls) == 2
    assert fake_client.responses.calls[0]["text_format"] is DiarySegmentationSchema
    assert fake_client.responses.calls[1]["text_format"] is EpisodeFeatureSchema
    assert fake_client.responses.calls[0]["store"] is False
    assert fake_client.responses.calls[1]["store"] is False
    assert response.response_id == "seg,feat"
    assert response.actual_model == "gpt-test"


def test_openai_analyzer_repairs_semantic_inconsistency_once(monkeypatch) -> None:
    diary_text = "今日は成功してうれしかった。"
    feature = MockDiaryAnalyzer().analyze(diary_text).analysis.episodes[0]
    bad_feature = feature.model_copy(deep=True)
    bad_feature.power_components.increase_evidence = [
        EvidenceSpan(quote="存在しない引用", start_char=0, end_char=7)
    ]
    segmentation = DiarySegmentationSchema(
        episodes=[EpisodeSpan(episode_id="episode-1", start_char=0, end_char=len(diary_text), text=diary_text)]
    )
    fake_client = _FakeClient(
        [
            SimpleNamespace(id="seg", model="gpt-test", output_parsed=segmentation, usage=None),
            SimpleNamespace(id="bad", model="gpt-test", output_parsed=bad_feature, usage=None),
            SimpleNamespace(id="fixed", model="gpt-test", output_parsed=feature, usage=None),
        ]
    )
    monkeypatch.setattr(OpenAIDiaryAnalyzer, "_create_client", lambda self, api_key: fake_client)

    response = OpenAIDiaryAnalyzer().analyze(diary_text, model="gpt-test", api_key="sk-test")

    assert len(fake_client.responses.calls) == 3
    assert response.response_id == "seg,fixed"
