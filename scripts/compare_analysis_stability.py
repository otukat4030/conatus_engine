"""Manual OpenAI diary-analysis stability check.

This script calls the OpenAI analyzer and intentionally is not used by pytest.
It prints aggregate metrics only; it does not print the diary text or API key.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from statistics import mean
from typing import Any

from conatus_engine.affect_rules import classify_affect_roles
from conatus_engine.diary_analyzer import (
    AnalyzerError,
    DiaryAnalysisSchema,
    OpenAIDiaryAnalyzer,
    validate_episode_feature,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare repeated OpenAI diary analyses.")
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    if args.runs < 2:
        parser.error("--runs must be 2 or greater")

    diary_text = args.input_file.read_text(encoding="utf-8")
    analyses: list[DiaryAnalysisSchema] = []
    validation_failures = 0

    analyzer = OpenAIDiaryAnalyzer()
    for _ in range(args.runs):
        try:
            response = analyzer.analyze(diary_text, model=args.model)
            for episode in response.analysis.episodes:
                validate_episode_feature(episode, diary_text)
            analyses.append(response.analysis)
        except AnalyzerError:
            validation_failures += 1

    metrics = compare_analyses(analyses)
    metrics["requested_runs"] = args.runs
    metrics["successful_runs"] = len(analyses)
    metrics["semantic_validation_violation_rate"] = validation_failures / args.runs
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if analyses else 1


def compare_analyses(analyses: list[DiaryAnalysisSchema]) -> dict[str, float]:
    if len(analyses) < 2:
        return {
            "episode_count_match_rate": 0.0,
            "episode_boundary_jaccard": 0.0,
            "entity_id_jaccard": 0.0,
            "enum_field_match_rate": 0.0,
            "unknown_rate": 0.0,
            "evidence_span_valid_rate": 0.0,
            "affect_set_jaccard": 0.0,
            "primary_affect_match_rate": 0.0,
        }

    baseline = analyses[0]
    comparisons = analyses[1:]
    baseline_count = len(baseline.episodes)
    baseline_boundaries = _boundaries(baseline)
    baseline_entities = _entity_ids(baseline)
    baseline_enums = _enum_values(baseline)
    baseline_affects = _affect_ids(baseline)
    baseline_primary = _primary_ids(baseline)

    return {
        "episode_count_match_rate": mean(
            1.0 if len(analysis.episodes) == baseline_count else 0.0
            for analysis in comparisons
        ),
        "episode_boundary_jaccard": mean(
            _jaccard(baseline_boundaries, _boundaries(analysis))
            for analysis in comparisons
        ),
        "entity_id_jaccard": mean(
            _jaccard(baseline_entities, _entity_ids(analysis))
            for analysis in comparisons
        ),
        "enum_field_match_rate": mean(
            _enum_match_rate(baseline_enums, _enum_values(analysis))
            for analysis in comparisons
        ),
        "unknown_rate": mean(_unknown_rate(analysis) for analysis in analyses),
        "evidence_span_valid_rate": mean(_evidence_span_valid_rate(analysis) for analysis in analyses),
        "affect_set_jaccard": mean(
            _jaccard(baseline_affects, _affect_ids(analysis))
            for analysis in comparisons
        ),
        "primary_affect_match_rate": mean(
            1.0 if _primary_ids(analysis) == baseline_primary else 0.0
            for analysis in comparisons
        ),
    }


def _boundaries(analysis: DiaryAnalysisSchema) -> set[tuple[int, int]]:
    return {(episode.start_char, episode.end_char) for episode in analysis.episodes}


def _entity_ids(analysis: DiaryAnalysisSchema) -> set[str]:
    return {
        entity.entity_id
        for episode in analysis.episodes
        for entity in episode.entities
    }


def _enum_values(analysis: DiaryAnalysisSchema) -> dict[str, str]:
    values: dict[str, str] = {}
    for episode_index, episode in enumerate(analysis.episodes):
        data = episode.model_dump()
        for path, value in _walk(data):
            if isinstance(value, str) and path.endswith(
                (
                    ".kind",
                    ".effect",
                    ".mode",
                    ".valence",
                    ".orientation",
                    ".representation",
                    ".certainty",
                    ".outcome_vs_expectation",
                    ".target_availability",
                    ".recipient_similar_to_self",
                    ".dimension",
                    ".level",
                    ".bias",
                    ".imagined_social_judgment",
                    ".goal",
                    ".status",
                    ".origin",
                    ".blocker",
                    ".peer_norm",
                    ".domain",
                    ".excessiveness",
                )
            ):
                values[f"{episode_index}{path}"] = value
    return values


def _walk(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _enum_match_rate(left: dict[str, str], right: dict[str, str]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 1.0
    return sum(1 for key in keys if left.get(key) == right.get(key)) / len(keys)


def _unknown_rate(analysis: DiaryAnalysisSchema) -> float:
    values = list(_enum_values(analysis).values())
    if not values:
        return 0.0
    return sum(1 for value in values if value == "unknown") / len(values)


def _evidence_span_valid_rate(analysis: DiaryAnalysisSchema) -> float:
    spans = []
    for episode in analysis.episodes:
        for span in _span_dicts(episode.model_dump()):
            spans.append((episode.text, span))
    if not spans:
        return 0.0
    valid = 0
    for source, span in spans:
        if source[span["start_char"] : span["end_char"]] == span["quote"]:
            valid += 1
    return valid / len(spans)


def _span_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if {"quote", "start_char", "end_char"}.issubset(value):
            yield value
        for child in value.values():
            yield from _span_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _span_dicts(child)


def _affect_ids(analysis: DiaryAnalysisSchema) -> set[str]:
    return {
        affect.affect_id
        for episode in analysis.episodes
        for affect in classify_affect_roles(episode)
        if affect.status in {"matched", "candidate"}
    }


def _primary_ids(analysis: DiaryAnalysisSchema) -> tuple[str, ...]:
    primary: list[str] = []
    for episode in analysis.episodes:
        for affect in classify_affect_roles(episode):
            if affect.role in {"primary", "unclassified"}:
                primary.append(affect.affect_id)
                break
    return tuple(primary)


def _jaccard(left: set[Any], right: set[Any]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


if __name__ == "__main__":
    raise SystemExit(main())
