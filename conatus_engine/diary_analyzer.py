"""Diary analyzers for structured episode feature extraction."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from conatus_engine.pricing import TokenUsage, extract_token_usage


PowerDirection = Literal["increase", "decrease", "neutral", "unknown"]
ReactionValence = Literal["positive", "negative", "neutral", "unknown"]
Appraisal = Literal["over", "under", "fair", "unknown"]


class EpisodeFeatureSchema(BaseModel):
    """Structured features extracted before deterministic affect evaluation."""

    summary: str
    evidence_text: str
    power_direction: PowerDirection
    intensity: int = Field(ge=0, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    desire_present: bool = False
    external_cause: bool = False
    target_present: bool = False
    target_fortune: Literal["good", "bad", "neutral", "unknown"] = "unknown"
    reaction_to_target_fortune: ReactionValence = "unknown"
    temporal_orientation: Literal["past", "present", "future", "unknown"] = "unknown"
    outcome_uncertain: bool = False
    doubt_removed: bool = False
    expectation_confirmed: bool = False
    expectation_disconfirmed: bool = False
    self_appraisal: Appraisal = "unknown"
    other_appraisal: Appraisal = "unknown"
    imagined_social_judgment: Literal["praise", "blame", "unknown"] = "unknown"
    action_tendency: Literal[
        "help",
        "harm",
        "avoid",
        "imitate",
        "challenge",
        "dare",
        "freeze",
        "restrain",
        "none",
        "unknown",
    ] = "unknown"
    danger_present: bool = False
    explicit_excess: bool = False
    excess_domain: Literal["food", "alcohol", "money", "sex", "honor", "other", "unknown"] = "unknown"
    admiration: bool = False
    contempt: bool = False
    gratitude: bool = False
    anger: bool = False
    revenge: bool = False
    kindness: bool = False
    shame: bool = False
    remorse: bool = False
    longing: bool = False
    confidence_note: str = ""


class DiaryAnalysisSchema(BaseModel):
    """Top-level structured diary analysis returned by an analyzer."""

    episodes: list[EpisodeFeatureSchema]


@dataclass(frozen=True)
class AnalyzerResponse:
    """Analyzer output plus API metadata."""

    analysis: DiaryAnalysisSchema
    response_id: str | None
    requested_model: str
    actual_model: str
    service_tier: str | None
    usage: TokenUsage | None


class AnalyzerError(RuntimeError):
    """Raised when diary analysis cannot be completed safely."""


def _contains(text: str, *words: str) -> bool:
    return any(word in text for word in words)


def _split_episode_text(text: str) -> list[str]:
    chunks: list[str] = []
    for line in text.replace("\r\n", "\n").splitlines():
        for match in re.finditer(r"[^。！？!?]+[。！？!?]?", line):
            chunk = match.group(0).strip()
            if chunk:
                chunks.append(chunk)
    return chunks or [text.strip()]


class MockDiaryAnalyzer:
    """Deterministic offline analyzer for tests and demos."""

    provider = "mock"

    def analyze(self, text: str, *, model: str = "mock") -> AnalyzerResponse:
        episodes = [self._episode_from_text(chunk) for chunk in _split_episode_text(text)]
        return AnalyzerResponse(
            analysis=DiaryAnalysisSchema(episodes=episodes),
            response_id="mock-response",
            requested_model=model,
            actual_model=model,
            service_tier="standard",
            usage=TokenUsage(2140, 860, 1280, 720, 180, 2860),
        )

    def _episode_from_text(self, text: str) -> EpisodeFeatureSchema:
        positive = _contains(text, "うれ", "嬉", "成功", "でき", "希望", "感謝", "助け")
        negative = _contains(text, "悲", "否定", "不安", "恐", "失敗", "腹", "怒")
        if positive and not negative:
            direction: PowerDirection = "increase"
            intensity = 3
        elif negative and not positive:
            direction = "decrease"
            intensity = 2
        elif positive and negative:
            direction = "increase"
            intensity = 1
        else:
            direction = "neutral"
            intensity = 0
        summary = text if len(text) <= 40 else f"{text[:39]}..."
        return EpisodeFeatureSchema(
            summary=summary,
            evidence_text=text[:200],
            power_direction=direction,
            intensity=intensity,
            confidence=0.82,
            desire_present=_contains(text, "したい", "欲しい", "望"),
            external_cause=_contains(text, "同僚", "友人", "相手", "会議", "会社"),
            target_present=_contains(text, "同僚", "友人", "相手", "誰か"),
            temporal_orientation="future" if _contains(text, "明日", "将来", "希望") else "present",
            outcome_uncertain=_contains(text, "かもしれない", "不安", "まだ分から"),
            doubt_removed=_contains(text, "安心", "分かった", "解決"),
            expectation_confirmed=_contains(text, "予想通り", "期待通り"),
            self_appraisal="over" if _contains(text, "自分はすごい", "自慢") else "fair",
            other_appraisal="under" if _contains(text, "見下", "軽蔑") else "unknown",
            imagined_social_judgment="praise" if _contains(text, "褒め", "評価") else "unknown",
            action_tendency="help" if _contains(text, "助け", "手伝") else "unknown",
            danger_present=_contains(text, "危険", "怖"),
            explicit_excess=_contains(text, "やめられない", "過度", "飲み過ぎ", "食べ過ぎ"),
            excess_domain="alcohol" if _contains(text, "酒", "飲み過ぎ") else "food" if _contains(text, "食べ過ぎ") else "unknown",
            admiration=_contains(text, "驚", "すごい"),
            contempt=_contains(text, "軽視", "見下"),
            gratitude=_contains(text, "感謝", "ありがとう"),
            anger=_contains(text, "怒", "腹が立"),
            revenge=_contains(text, "仕返", "復讐"),
            kindness=_contains(text, "親切", "助け"),
            shame=_contains(text, "恥"),
            remorse=_contains(text, "後悔", "申し訳"),
            longing=_contains(text, "懐か", "恋しい"),
            confidence_note="MockDiaryAnalyzerによる語彙ベース抽出",
        )


class OpenAIDiaryAnalyzer:
    """OpenAI Responses API analyzer using Pydantic structured output."""

    provider = "openai"
    prompt_version = "diary-features-v1"

    def analyze(self, text: str, *, model: str, api_key: str | None = None) -> AnalyzerResponse:
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AnalyzerError("OpenAI APIキーが設定されていません。")
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - dependency is installed in app env
            raise AnalyzerError("openai パッケージがインストールされていません。") from exc

        client = OpenAI(api_key=api_key)
        system_prompt = (
            "あなたは日記から観察可能なEpisode特徴だけを抽出します。"
            "日記に複数の出来事・場面・感情の単位があれば、episodes に複数要素として分けてください。"
            "一つのEpisodeは、あとで一つの情動へ分類できる最小のまとまりにしてください。"
            "医学的・心理学的診断をせず、人格を断定せず、日記にない事実を推測しません。"
            "最終的なスピノザ情動名は決めず、指定スキーマだけを返してください。"
        )
        try:
            response = client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                text_format=DiaryAnalysisSchema,
            )
        except Exception as exc:
            raise AnalyzerError(self._friendly_openai_error(exc)) from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise AnalyzerError("OpenAI応答から構造化解析結果を取得できませんでした。")
        if not parsed.episodes:
            raise AnalyzerError("Episodeが抽出されませんでした。")
        return AnalyzerResponse(
            analysis=parsed,
            response_id=getattr(response, "id", None),
            requested_model=model,
            actual_model=getattr(response, "model", model),
            service_tier=getattr(response, "service_tier", "standard"),
            usage=extract_token_usage(response),
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
