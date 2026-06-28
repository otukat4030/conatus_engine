"""Application services used by the desktop GUI."""

from __future__ import annotations

import os
import sqlite3
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from conatus_engine.affect_rules import classify_affect_roles
from conatus_engine.diary_analyzer import (
    AnalyzerResponse,
    MockDiaryAnalyzer,
    OpenAIDiaryAnalyzer,
)
from conatus_engine.pricing import (
    PricingStatus,
    TokenUsage,
    estimate_cost,
    format_usd,
    load_pricing_catalog,
    resolve_pricing,
    validate_pricing_catalog,
)
from conatus_engine.usage_store import UsageRepository, default_db_path


@dataclass(frozen=True)
class DiaryEntryRecord:
    id: int
    entry_date: str
    text: str


@dataclass(frozen=True)
class EpisodeRecord:
    id: int
    diary_entry_id: int
    episode_key: str
    start_char: int
    end_char: int
    text: str
    summary: str
    increase_intensity: int
    decrease_intensity: int
    conatus_delta: int
    extraction_confidence: float
    extractor: str
    features_json: str = "{}"


@dataclass(frozen=True)
class AffectRecord:
    episode_id: int
    affect_id: str
    japanese_name: str
    status: str
    role: str
    reason: str
    confidence: float
    rule_trace_json: str = "{}"


@dataclass(frozen=True)
class AnalysisResult:
    diary: DiaryEntryRecord
    episodes: list[EpisodeRecord]
    affects: list[AffectRecord]
    usage_run_id: int
    usage_text: str
    summary_text: str


@dataclass(frozen=True)
class LogRow:
    diary_id: int
    entry_date: str
    episode_count: int
    summary: str
    conatus_delta: int
    affects: str
    statuses: str
    api_cost: str


ROLE_LABELS = {
    "primary": "代表情動",
    "base": "基礎情動",
    "coexisting": "併存情動",
    "candidate": "確認候補",
    "unclassified": "未分類",
}


def _names_for_role(affects: list[AffectRecord], role: str) -> str:
    names = [affect.japanese_name for affect in affects if affect.role == role]
    return ", ".join(names) if names else "なし"


def format_episode_detail(
    episode: EpisodeRecord,
    affects: list[AffectRecord],
    *,
    entry_date: str | None = None,
) -> str:
    features = _load_features(episode.features_json)
    extractor_label = "Mock抽出結果" if episode.extractor == "mock" else "LLM抽出結果"
    feature_lines = [
        extractor_label,
        f"Episode ID: {episode.episode_key}",
        f"開始位置: {episode.start_char}",
        f"終了位置: {episode.end_char}",
        "Episode本文:",
        episode.text,
        f"summary: {episode.summary}",
        f"entities: {_compact_json(features.get('entities', []))}",
        f"power_components: {_compact_json(features.get('power_components', {}))}",
        f"causal_links: {_compact_json(features.get('causal_links', []))}",
        f"entity_stances: {_compact_json(features.get('entity_stances', []))}",
        f"attention_states: {_compact_json(features.get('attention_states', []))}",
        f"temporal_appraisal: {_compact_json(features.get('temporal_appraisal', {}))}",
        f"social_events: {_compact_json(features.get('social_events', []))}",
        f"appraisals: {_compact_json(features.get('appraisals', []))}",
        f"action_tendencies: {_compact_json(features.get('action_tendencies', []))}",
        f"extraction_confidence: {episode.extraction_confidence:.2f}",
    ]
    if entry_date:
        feature_lines.insert(1, f"日付: {entry_date}")

    sections = [
        *feature_lines,
        "",
        "Engine計算結果",
        f"increase_intensity: {episode.increase_intensity}",
        f"decrease_intensity: {episode.decrease_intensity}",
        f"conatus_delta: {episode.conatus_delta}",
        "",
        "情動判定結果",
        *_format_affect_sections(affects),
        "",
        "生JSON",
        _format_features_json(episode.features_json),
    ]
    return "\n".join(sections)


def _load_features(features_json: str) -> dict[str, object]:
    try:
        loaded = json.loads(features_json)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _format_features_json(features_json: str) -> str:
    try:
        return json.dumps(json.loads(features_json), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return features_json


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _format_affect_sections(affects: list[AffectRecord]) -> list[str]:
    lines: list[str] = []
    for role, label in ROLE_LABELS.items():
        role_affects = [affect for affect in affects if affect.role == role]
        lines.append(f"{label}:")
        if not role_affects:
            lines.append("- なし")
            continue
        for affect in role_affects:
            lines.append(
                f"- {affect.affect_id} {affect.japanese_name} "
                f"[{affect.status}] role={affect.role} confidence={affect.confidence:.2f}"
            )
            lines.append(f"  reason: {affect.reason}")
            trace = _load_features(affect.rule_trace_json)
            if trace:
                lines.append(f"  RuleTrace: {_compact_json(trace)}")
    return lines


class DiaryRepository:
    """SQLite repository for diaries, episodes, and affect assignments."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            self._ensure_compatible_schema(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS diary_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_date TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    diary_entry_id INTEGER NOT NULL,
                    episode_key TEXT NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    features_json TEXT NOT NULL,
                    increase_intensity INTEGER NOT NULL,
                    decrease_intensity INTEGER NOT NULL,
                    conatus_delta INTEGER NOT NULL,
                    extraction_confidence REAL NOT NULL,
                    extractor TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(diary_entry_id) REFERENCES diary_entries(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS affect_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL,
                    affect_id TEXT NOT NULL,
                    japanese_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'primary',
                    reason TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    rule_trace_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(episode_id, affect_id, status, role),
                    FOREIGN KEY(episode_id) REFERENCES episodes(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS diary_analysis_usage (
                    diary_entry_id INTEGER NOT NULL,
                    usage_run_id INTEGER NOT NULL,
                    PRIMARY KEY(diary_entry_id, usage_run_id)
                )
                """
            )

    @staticmethod
    def _ensure_compatible_schema(conn: sqlite3.Connection) -> None:
        expected_episode_columns = {
            "id",
            "diary_entry_id",
            "episode_key",
            "start_char",
            "end_char",
            "text",
            "summary",
            "features_json",
            "increase_intensity",
            "decrease_intensity",
            "conatus_delta",
            "extraction_confidence",
            "extractor",
            "created_at",
        }
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='episodes'"
        ).fetchone()
        if row is not None:
            columns = {
                item[1]
                for item in conn.execute("PRAGMA table_info(episodes)").fetchall()
            }
            if not expected_episode_columns.issubset(columns):
                raise RuntimeError(
                    "このデータベースは現在のバージョンと互換性がありません。"
                    "既存DBを削除するか、新しいDBパスを設定してください。"
                )
        affect_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='affect_assignments'"
        ).fetchone()
        if affect_row is not None:
            affect_columns = {
                item[1]
                for item in conn.execute("PRAGMA table_info(affect_assignments)").fetchall()
            }
            if not {"role", "rule_trace_json"}.issubset(affect_columns):
                raise RuntimeError(
                    "このデータベースは現在のバージョンと互換性がありません。"
                    "既存DBを削除するか、新しいDBパスを設定してください。"
                )

    def save_diary(self, entry_date: date, text: str) -> DiaryEntryRecord:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO diary_entries(entry_date, text, created_at) VALUES (?, ?, ?)",
                (entry_date.isoformat(), text, datetime.now().isoformat(timespec="seconds")),
            )
            entry_id = int(cursor.lastrowid)
        return DiaryEntryRecord(entry_id, entry_date.isoformat(), text)

    def save_episode(
        self,
        diary_id: int,
        episode_key: str,
        start_char: int,
        end_char: int,
        text: str,
        summary: str,
        increase_intensity: int,
        decrease_intensity: int,
        conatus_delta: int,
        extraction_confidence: float,
        extractor: str,
        features_json: str = "{}",
    ) -> EpisodeRecord:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO episodes(
                    diary_entry_id, episode_key, start_char, end_char, text,
                    summary, features_json, increase_intensity, decrease_intensity,
                    conatus_delta, extraction_confidence, extractor, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diary_id,
                    episode_key,
                    start_char,
                    end_char,
                    text,
                    summary,
                    features_json,
                    increase_intensity,
                    decrease_intensity,
                    conatus_delta,
                    extraction_confidence,
                    extractor,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            episode_id = int(cursor.lastrowid)
        return EpisodeRecord(
            episode_id,
            diary_id,
            episode_key,
            start_char,
            end_char,
            text,
            summary,
            increase_intensity,
            decrease_intensity,
            conatus_delta,
            extraction_confidence,
            extractor,
            features_json,
        )

    def save_affect(self, affect: AffectRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO affect_assignments(
                    episode_id, affect_id, japanese_name, status, role, reason, confidence,
                    rule_trace_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    affect.episode_id,
                    affect.affect_id,
                    affect.japanese_name,
                    affect.status,
                    affect.role,
                    affect.reason,
                    affect.confidence,
                    affect.rule_trace_json,
                ),
            )

    def link_usage(self, diary_id: int, usage_run_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO diary_analysis_usage(diary_entry_id, usage_run_id) VALUES (?, ?)",
                (diary_id, usage_run_id),
            )

    def list_diary_rows(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        affect_name: str | None = None,
    ) -> list[LogRow]:
        where, params = self._date_filter(start_date, end_date)
        params_list = list(params)
        if affect_name:
            where = self._add_where(
                where,
                """
                EXISTS (
                    SELECT 1
                    FROM affect_assignments af
                    WHERE af.episode_id = e.id AND af.japanese_name = ?
                )
                """,
            )
            params_list.append(affect_name)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT d.id, d.entry_date, COUNT(DISTINCT e.id),
                       GROUP_CONCAT(e.summary, ' / '),
                       COALESCE(SUM(e.conatus_delta), 0),
                       GROUP_CONCAT(DISTINCT a.japanese_name),
                       GROUP_CONCAT(DISTINCT a.status),
                       MAX(ar.estimated_total_cost_usd)
                FROM diary_entries d
                JOIN episodes e ON e.diary_entry_id = d.id
                {self._primary_affect_join("a")}
                LEFT JOIN diary_analysis_usage dau ON dau.diary_entry_id = d.id
                LEFT JOIN analysis_runs ar ON ar.id = dau.usage_run_id
                {where}
                GROUP BY d.id
                ORDER BY d.entry_date DESC, d.id DESC
                """,
                tuple(params_list),
            ).fetchall()
        return [
            LogRow(
                diary_id=int(row[0]),
                entry_date=str(row[1]),
                episode_count=int(row[2]),
                summary=str(row[3] or ""),
                conatus_delta=int(row[4]),
                affects=str(row[5] or "").replace(",", ", "),
                statuses=str(row[6] or "").replace(",", ", "),
                api_cost=format_usd(Decimal(str(row[7]))) if row[7] is not None else "",
            )
            for row in rows
        ]

    def list_affect_names(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> list[str]:
        where, params = self._date_filter(start_date, end_date)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT a.japanese_name
                FROM affect_assignments a
                JOIN episodes e ON e.id = a.episode_id
                JOIN diary_entries d ON d.id = e.diary_entry_id
                {where}
                {'AND' if where else 'WHERE'} a.japanese_name IS NOT NULL
                ORDER BY a.japanese_name
                """,
                params,
            ).fetchall()
        return [str(row[0]) for row in rows if row[0]]

    def get_diary_detail(self, diary_id: int, affect_name: str | None = None) -> str | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id AS diary_id, entry_date, text
                FROM diary_entries
                WHERE id = ?
                """,
                (diary_id,),
            ).fetchone()
            if row is None:
                return None
            episodes = conn.execute(
                """
                SELECT e.id, e.episode_key, e.start_char, e.end_char, e.text,
                       e.summary, e.increase_intensity, e.decrease_intensity,
                       e.conatus_delta, e.extraction_confidence, e.extractor,
                       e.features_json
                FROM episodes e
                WHERE e.diary_entry_id = ?
                ORDER BY e.id
                """,
                (diary_id,),
            ).fetchall()
            affects_by_episode: dict[int, list[sqlite3.Row]] = {int(episode["id"]): [] for episode in episodes}
            episode_ids = list(affects_by_episode)
            if episode_ids:
                placeholders = ", ".join("?" for _ in episode_ids)
                affect_rows = conn.execute(
                    f"""
                    SELECT episode_id, affect_id, japanese_name, status, role, reason,
                           confidence, rule_trace_json
                    FROM affect_assignments
                    WHERE episode_id IN ({placeholders})
                    ORDER BY
                        CASE role
                            WHEN 'primary' THEN 0
                            WHEN 'base' THEN 1
                            WHEN 'coexisting' THEN 2
                            WHEN 'candidate' THEN 3
                            WHEN 'unclassified' THEN 4
                            ELSE 5
                        END,
                        affect_id
                    """,
                    tuple(episode_ids),
                ).fetchall()
                for affect in affect_rows:
                    affects_by_episode[int(affect["episode_id"])].append(affect)
            usage = conn.execute(
                """
                SELECT ar.*
                FROM diary_analysis_usage dau
                JOIN analysis_runs ar ON ar.id = dau.usage_run_id
                WHERE dau.diary_entry_id = ?
                ORDER BY ar.id DESC
                LIMIT 1
                """,
                (row["diary_id"],),
            ).fetchone()
        episode_lines: list[str] = []
        for episode in episodes:
            record = EpisodeRecord(
                id=int(episode["id"]),
                diary_entry_id=diary_id,
                episode_key=str(episode["episode_key"]),
                start_char=int(episode["start_char"]),
                end_char=int(episode["end_char"]),
                text=str(episode["text"]),
                summary=str(episode["summary"]),
                increase_intensity=int(episode["increase_intensity"]),
                decrease_intensity=int(episode["decrease_intensity"]),
                conatus_delta=int(episode["conatus_delta"]),
                extraction_confidence=float(episode["extraction_confidence"]),
                extractor=str(episode["extractor"]),
                features_json=str(episode["features_json"]),
            )
            affect_records = [
                AffectRecord(
                    episode_id=int(affect["episode_id"]),
                    affect_id=str(affect["affect_id"]),
                    japanese_name=str(affect["japanese_name"]),
                    status=str(affect["status"]),
                    role=str(affect["role"]),
                    reason=str(affect["reason"]),
                    confidence=float(affect["confidence"]),
                    rule_trace_json=str(affect["rule_trace_json"]),
                )
                for affect in affects_by_episode.get(record.id, [])
            ]
            episode_lines.append(f"Episode {record.id}")
            episode_lines.append(format_episode_detail(record, affect_records, entry_date=str(row["entry_date"])))
        usage_lines = []
        if usage is not None:
            usage_lines = [
                "",
                "API使用量",
                f"モデル: {usage['actual_model'] or usage['requested_model']}",
                f"入力: {usage['input_tokens']}",
                f"キャッシュ入力: {usage['cached_input_tokens']}",
                f"出力: {usage['output_tokens']}",
                f"reasoning: {usage['reasoning_tokens']}",
                f"概算料金: {format_usd(Decimal(str(usage['estimated_total_cost_usd']))) if usage['estimated_total_cost_usd'] else 'unavailable'}",
                f"pricing status: {usage['pricing_status']}",
            ]
        return "\n".join(
            [
                f"日記ID: {row['diary_id']}",
                f"日付: {row['entry_date']}",
                "",
                "元の日記",
                row["text"],
                "",
                "Episode一覧" if not affect_name else f"Episode一覧（情動フィルタ: {affect_name} / 全Episode表示）",
                *(episode_lines or ["- なし"]),
                *usage_lines,
            ]
        )

    def delete_diary(self, diary_id: int) -> None:
        with self._connect() as conn:
            episode_ids = [
                int(row[0])
                for row in conn.execute(
                    "SELECT id FROM episodes WHERE diary_entry_id = ?", (diary_id,)
                ).fetchall()
            ]
            usage_ids = [
                int(row[0])
                for row in conn.execute(
                    "SELECT usage_run_id FROM diary_analysis_usage WHERE diary_entry_id = ?",
                    (diary_id,),
                ).fetchall()
            ]
            for episode_id in episode_ids:
                conn.execute("DELETE FROM affect_assignments WHERE episode_id = ?", (episode_id,))
            conn.execute("DELETE FROM episodes WHERE diary_entry_id = ?", (diary_id,))
            conn.execute("DELETE FROM diary_entries WHERE id = ?", (diary_id,))
            conn.execute("DELETE FROM diary_analysis_usage WHERE diary_entry_id = ?", (diary_id,))
            for usage_id in usage_ids:
                conn.execute("DELETE FROM analysis_runs WHERE id = ?", (usage_id,))

    def aggregate(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> dict[str, object]:
        where, params = self._date_filter(start_date, end_date)
        with self._connect() as conn:
            diary_count = conn.execute(
                f"""
                SELECT COUNT(DISTINCT d.id)
                FROM diary_entries d
                JOIN episodes e ON e.diary_entry_id = d.id
                {where}
                """,
                params,
            ).fetchone()[0]
            episode_count = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM episodes e
                JOIN diary_entries d ON d.id = e.diary_entry_id
                {where}
                """,
                params,
            ).fetchone()[0]
            conatus_sum = conn.execute(
                f"""
                SELECT COALESCE(SUM(e.conatus_delta), 0)
                FROM episodes e
                JOIN diary_entries d ON d.id = e.diary_entry_id
                {where}
                """,
                params,
            ).fetchone()[0]
            affect_rows = conn.execute(
                f"""
                SELECT a.japanese_name, COUNT(*)
                FROM affect_assignments a
                JOIN episodes e ON e.id = a.episode_id
                JOIN diary_entries d ON d.id = e.diary_entry_id
                {where}
                {'AND' if where else 'WHERE'} a.status IN ('matched', 'candidate')
                GROUP BY a.japanese_name
                ORDER BY COUNT(*) DESC, a.japanese_name
                """,
                params,
            ).fetchall()
            series_rows = conn.execute(
                f"""
                SELECT d.entry_date, COALESCE(SUM(e.conatus_delta), 0)
                FROM diary_entries d
                JOIN episodes e ON e.diary_entry_id = d.id
                {where}
                GROUP BY d.entry_date
                ORDER BY d.entry_date
                """,
                params,
            ).fetchall()
        return {
            "diary_count": int(diary_count),
            "episode_count": int(episode_count),
            "conatus_sum": int(conatus_sum),
            "affects": [(str(name), int(count)) for name, count in affect_rows],
            "series": [(str(day), int(delta)) for day, delta in series_rows],
        }

    @staticmethod
    def _date_filter(
        start_date: date | None, end_date: date | None
    ) -> tuple[str, tuple[str, ...]]:
        clauses: list[str] = []
        params: list[str] = []
        if start_date is not None:
            clauses.append("d.entry_date >= ?")
            params.append(start_date.isoformat())
        if end_date is not None:
            clauses.append("d.entry_date <= ?")
            params.append(end_date.isoformat())
        if not clauses:
            return "", ()
        return "WHERE " + " AND ".join(clauses), tuple(params)

    @staticmethod
    def _add_where(where: str, clause: str) -> str:
        if where:
            return f"{where} AND {clause}"
        return f"WHERE {clause}"

    @staticmethod
    def _primary_affect_join(alias: str) -> str:
        return f"""
        LEFT JOIN affect_assignments {alias} ON {alias}.id = (
            SELECT aa.id
            FROM affect_assignments aa
            WHERE aa.episode_id = e.id
            ORDER BY
                CASE aa.role
                    WHEN 'primary' THEN 0
                    WHEN 'unclassified' THEN 1
                    ELSE 2
                END,
                CASE aa.status
                    WHEN 'matched' THEN 0
                    WHEN 'candidate' THEN 1
                    ELSE 2
                END,
                CASE
                    WHEN aa.affect_id IN ('P3-DA-01', 'P3-DA-02', 'P3-DA-03') THEN 1
                    ELSE 0
                END,
                aa.confidence DESC,
                aa.id ASC
            LIMIT 1
        )
        """


class DiaryService:
    """Application service for saving diaries."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.repository = DiaryRepository(db_path)

    def save_diary(self, entry_date: date, text: str) -> DiaryEntryRecord:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("日記本文を入力してください。")
        return self.repository.save_diary(entry_date, cleaned)


class AnalysisService:
    """Diary analysis service used by the GUI."""

    def __init__(
        self,
        db_path: Path | None = None,
        model: str | None = None,
        *,
        analyzer_mode: str = "mock",
        api_key: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.repository = DiaryRepository(db_path)
        self.usage_repository = UsageRepository(db_path)
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-5.4-mini"
        self.analyzer_mode = analyzer_mode
        self.api_key = api_key

    def analyze(self, entry_date: date, text: str) -> AnalysisResult:
        diary = DiaryService(self.db_path).save_diary(entry_date, text)
        analyzer_response = self._run_analyzer(text)
        episodes: list[EpisodeRecord] = []
        affects: list[AffectRecord] = []
        for feature in analyzer_response.analysis.episodes:
            conatus_delta = (
                feature.power_components.increase_intensity
                - feature.power_components.decrease_intensity
            )
            episode = self.repository.save_episode(
                diary.id,
                feature.episode_id,
                feature.start_char,
                feature.end_char,
                feature.text,
                feature.summary,
                feature.power_components.increase_intensity,
                feature.power_components.decrease_intensity,
                conatus_delta,
                feature.extraction_confidence,
                analyzer_response.provider,
                feature.model_dump_json(ensure_ascii=False),
            )
            episodes.append(episode)
            for evaluation in classify_affect_roles(feature):
                affect = AffectRecord(
                    episode_id=episode.id,
                    affect_id=evaluation.affect_id,
                    japanese_name=evaluation.japanese_name,
                    status=evaluation.status,
                    role=evaluation.role,
                    reason=evaluation.reason,
                    confidence=evaluation.confidence,
                    rule_trace_json=evaluation.trace.model_dump_json(ensure_ascii=False),
                )
                affects.append(affect)
                self.repository.save_affect(affect)

        pricing, pricing_status, note = resolve_pricing(self.model)
        usage = analyzer_response.usage
        estimate = estimate_cost(usage, pricing)
        if usage is None:
            usage = TokenUsage(None, None, None, None, None, None)
        if pricing is None and estimate.status is not PricingStatus.USAGE_UNAVAILABLE:
            estimate = estimate.__class__(pricing_status, None, None, None, None, note)
        usage_run_id = self.usage_repository.save_usage(
            response_id=analyzer_response.response_id,
            requested_model=analyzer_response.requested_model,
            actual_model=analyzer_response.actual_model,
            service_tier=analyzer_response.service_tier or "standard",
            usage=usage,
            pricing=pricing,
            estimate=estimate,
            provider=analyzer_response.provider,
            prompt_version=analyzer_response.prompt_version,
            schema_version="episode-feature-v2",
            segmentation_json=analyzer_response.segmentation_json,
            status="succeeded",
        )
        self.repository.link_usage(diary.id, usage_run_id)
        usage_text = (
            "API使用量\n"
            f"モデル: {analyzer_response.actual_model}\n"
            f"response ID: {analyzer_response.response_id or 'n/a'}\n"
            f"入力: {self._fmt_tokens(usage.input_tokens)} tokens\n"
            f"キャッシュ入力: {self._fmt_tokens(usage.cached_input_tokens)} tokens\n"
            f"出力: {self._fmt_tokens(usage.output_tokens)} tokens\n"
            f"reasoning: {self._fmt_tokens(usage.reasoning_tokens)} tokens\n"
            f"合計: {self._fmt_tokens(usage.total_tokens)} tokens\n"
            f"概算料金: {format_usd(estimate.estimated_total_cost_usd)}\n"
            f"pricing status: {estimate.status.value}\n"
            f"料金表取得日: {pricing.pricing_retrieved_at if pricing else 'n/a'}\n"
            "この金額は保存されたトークン数と料金表から計算した概算です。"
        )
        conatus_total = sum(episode.conatus_delta for episode in episodes)
        affect_summary = self._affect_summary_by_episode(episodes, affects)
        summary = (
            f"日記ID: {diary.id}\n"
            f"日付: {diary.entry_date}\n"
            f"Episode数: {len(episodes)}\n"
            f"今日のコナトゥス変化: {conatus_total:+d}\n"
            f"{affect_summary}\n"
            f"API概算料金: {format_usd(estimate.estimated_total_cost_usd)}"
        )
        return AnalysisResult(diary, episodes, affects, usage_run_id, usage_text, summary)

    def analyze_with_mock(self, entry_date: date, text: str) -> AnalysisResult:
        return AnalysisService(
            self.db_path,
            self.model,
            analyzer_mode="mock",
            api_key=self.api_key,
        ).analyze(entry_date, text)

    def _run_analyzer(self, text: str) -> AnalyzerResponse:
        if self.analyzer_mode == "openai":
            return OpenAIDiaryAnalyzer().analyze(text, model=self.model, api_key=self.api_key)
        return MockDiaryAnalyzer().analyze(text, model=self.model)

    @staticmethod
    def _fmt_tokens(value: int | None) -> str:
        return "unavailable" if value is None else f"{value:,}"

    @staticmethod
    def _affect_summary_by_episode(
        episodes: list[EpisodeRecord], affects: list[AffectRecord]
    ) -> str:
        by_episode: dict[int, list[AffectRecord]] = {}
        for affect in affects:
            by_episode.setdefault(affect.episode_id, []).append(affect)
        lines = ["情動判定:"]
        for index, episode in enumerate(episodes, start=1):
            episode_affects = by_episode.get(episode.id, [])
            lines.append(
                f"- Episode {index}: "
                f"代表情動: {_names_for_role(episode_affects, 'primary')}; "
                f"基礎情動: {_names_for_role(episode_affects, 'base')}; "
                f"併存情動: {_names_for_role(episode_affects, 'coexisting')}; "
                f"確認候補: {_names_for_role(episode_affects, 'candidate')}; "
                f"未分類: {_names_for_role(episode_affects, 'unclassified')}"
            )
        return "\n".join(lines)


class ReportService:
    """Application service for emotion-log summaries."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.repository = DiaryRepository(db_path)
        self.usage_repository = UsageRepository(db_path)

    def summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        affect_name: str | None = None,
    ) -> dict[str, object]:
        data = self.repository.aggregate(start_date, end_date)
        runs = self.usage_repository.list_usage()
        estimated = [
            run.estimated_total_cost_usd
            for run in runs
            if run.estimated_total_cost_usd is not None
        ]
        total = sum(estimated, start=Decimal("0"))
        data["api_runs"] = len(runs)
        data["api_cost"] = format_usd(total if estimated else None)
        data["pricing_unavailable"] = len(runs) - len(estimated)
        data["affect_names"] = self.repository.list_affect_names(start_date, end_date)
        data["rows"] = self.repository.list_diary_rows(start_date, end_date, affect_name)
        data["visible_diary_count"] = len(data["rows"])
        data["affect_filter"] = affect_name
        return data

    def detail(self, diary_id: int, affect_name: str | None = None) -> str:
        return self.repository.get_diary_detail(diary_id, affect_name) or "詳細が見つかりません。"

    def delete_diary(self, diary_id: int) -> None:
        self.repository.delete_diary(diary_id)


class SettingsService:
    """Non-UI helpers for pricing and API-key related settings."""

    keyring_service = "conatus-engine"
    keyring_user = "openai-api-key"

    def pricing_info(self, model: str) -> str:
        catalog = load_pricing_catalog()
        errors = validate_pricing_catalog(catalog)
        pricing, status, note = resolve_pricing(model, catalog=catalog)
        lines = [
            f"料金表取得日: {catalog.get('retrieved_at')}",
            f"schema version: {catalog.get('schema_version')}",
            f"登録モデル数: {len(catalog.get('entries', []))}",
            f"pricing validate: {'OK' if not errors else 'NG'}",
            f"現在モデル: {model}",
            f"解決状態: {status.value}",
        ]
        if pricing:
            lines.append(f"入力単価: {pricing.input_price_per_1m_usd} USD / 1M tokens")
            lines.append(f"出力単価: {pricing.output_price_per_1m_usd} USD / 1M tokens")
        if note:
            lines.append(f"理由: {note}")
        return "\n".join(lines)

    def available_models(self) -> list[str]:
        catalog = load_pricing_catalog()
        return [str(entry["model_pattern"]) for entry in catalog.get("entries", [])]

    def test_openai_connection(self, *, model: str, api_key: str | None) -> str:
        api_key = self.resolve_api_key(api_key)
        if not api_key:
            return "OpenAI APIキーが設定されていません。"
        try:
            from openai import OpenAI
        except Exception as exc:
            return f"openai パッケージを読み込めません: {type(exc).__name__}"
        try:
            response = OpenAI(api_key=api_key).responses.create(
                model=model,
                input="接続確認です。ok とだけ返してください。",
                max_output_tokens=16,
            )
        except Exception as exc:
            return self._friendly_openai_error(exc)

        usage = getattr(response, "usage", None)
        usage_text = "usage: unavailable"
        if usage is not None:
            usage_text = (
                f"input={getattr(usage, 'input_tokens', None)}, "
                f"output={getattr(usage, 'output_tokens', None)}, "
                f"total={getattr(usage, 'total_tokens', None)}"
            )
        return (
            "接続成功\n"
            f"モデル: {getattr(response, 'model', model)}\n"
            f"response ID: {getattr(response, 'id', 'n/a')}\n"
            f"{usage_text}\n"
            "この接続確認はOpenAI APIを呼び出すため、利用料金が発生する場合があります。"
        )

    def save_api_key_to_keyring(self, api_key: str) -> tuple[bool, str]:
        if not api_key.strip():
            return False, "APIキーが空です。"
        try:
            import keyring

            keyring.set_password(self.keyring_service, self.keyring_user, api_key)
            return True, "APIキーをOS keyringへ保存しました。"
        except Exception as exc:  # pragma: no cover - depends on OS keyring
            return False, f"keyringへ保存できませんでした: {type(exc).__name__}"

    def get_api_key_from_keyring(self) -> str | None:
        try:
            import keyring

            return keyring.get_password(self.keyring_service, self.keyring_user)
        except Exception:
            return None

    def resolve_api_key(self, current_value: str | None = None) -> str | None:
        return (
            (current_value or "").strip()
            or self.get_api_key_from_keyring()
            or os.getenv("OPENAI_API_KEY")
            or None
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
            return "このAPIキーでは選択したモデルを利用できません。別のモデルを選択してください。"
        return f"OpenAI APIへの接続に失敗しました: {name}"
