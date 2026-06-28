"""Application services used by the desktop GUI."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from conatus_engine.affect_rules import select_primary_affect
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
    summary: str
    evidence_text: str
    conatus_delta: int
    power_direction: str
    intensity: int
    confidence: float
    features_json: str = "{}"


@dataclass(frozen=True)
class AffectRecord:
    episode_id: int
    affect_id: str
    japanese_name: str
    status: str
    reason: str
    confidence: float


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
                    summary TEXT NOT NULL,
                    evidence_text TEXT NOT NULL,
                    conatus_delta INTEGER NOT NULL,
                    power_direction TEXT NOT NULL,
                    intensity INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    features_json TEXT NOT NULL DEFAULT '{}',
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
                    reason TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    UNIQUE(episode_id, affect_id, status),
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
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(episodes)").fetchall()
            }
            if "features_json" not in columns:
                conn.execute(
                    "ALTER TABLE episodes ADD COLUMN features_json TEXT NOT NULL DEFAULT '{}'"
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
        summary: str,
        evidence_text: str,
        conatus_delta: int,
        power_direction: str,
        intensity: int,
        confidence: float,
        features_json: str = "{}",
    ) -> EpisodeRecord:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO episodes(
                    diary_entry_id, summary, evidence_text, conatus_delta,
                    power_direction, intensity, confidence, features_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diary_id,
                    summary,
                    evidence_text,
                    conatus_delta,
                    power_direction,
                    intensity,
                    confidence,
                    features_json,
                ),
            )
            episode_id = int(cursor.lastrowid)
        return EpisodeRecord(
            episode_id,
            diary_id,
            summary,
            evidence_text,
            conatus_delta,
            power_direction,
            intensity,
            confidence,
            features_json,
        )

    def save_affect(self, affect: AffectRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO affect_assignments(
                    episode_id, affect_id, japanese_name, status, reason, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    affect.episode_id,
                    affect.affect_id,
                    affect.japanese_name,
                    affect.status,
                    affect.reason,
                    affect.confidence,
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
            where = self._add_where(where, "a.japanese_name = ?")
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
                FROM episodes e
                JOIN diary_entries d ON d.id = e.diary_entry_id
                {self._primary_affect_join("a")}
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
            params: list[object] = [diary_id]
            affect_filter_sql = ""
            if affect_name:
                affect_filter_sql = "AND a.japanese_name = ?"
                params.append(affect_name)
            episodes = conn.execute(
                f"""
                SELECT e.id, e.summary, e.evidence_text, e.conatus_delta,
                       e.power_direction, e.intensity, e.confidence,
                       a.affect_id, a.japanese_name, a.status, a.reason,
                       a.confidence AS affect_confidence
                FROM episodes e
                {self._primary_affect_join("a")}
                WHERE e.diary_entry_id = ?
                {affect_filter_sql}
                ORDER BY e.id
                """,
                tuple(params),
            ).fetchall()
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
            episode_lines.extend(
                [
                    f"- Episode {episode['id']}: {episode['summary']}",
                    f"  日付: {row['entry_date']}",
                    f"  根拠: {episode['evidence_text']}",
                    f"  conatus_delta: {episode['conatus_delta']}",
                    f"  方向: {episode['power_direction']} / 強度: {episode['intensity']} / confidence: {episode['confidence']}",
                    (
                        "  代表情動: "
                        f"{episode['affect_id'] or 'n/a'} {episode['japanese_name'] or 'なし'} "
                        f"[{episode['status'] or 'なし'}] "
                        f"confidence={episode['affect_confidence'] if episode['affect_confidence'] is not None else 'n/a'}"
                    ),
                    f"  判定理由: {episode['reason'] or 'なし'}",
                ]
            )
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
                "Episode一覧" if not affect_name else f"Episode一覧（情動フィルタ: {affect_name}）",
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
                FROM episodes e
                JOIN diary_entries d ON d.id = e.diary_entry_id
                {self._primary_affect_join("a")}
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
            conatus_delta = self._conatus_delta(feature.power_direction, feature.intensity)
            episode = self.repository.save_episode(
                diary.id,
                feature.summary,
                feature.evidence_text,
                conatus_delta,
                feature.power_direction,
                feature.intensity,
                feature.confidence,
                feature.model_dump_json(ensure_ascii=False),
            )
            episodes.append(episode)
            evaluation = select_primary_affect(feature)
            affect = AffectRecord(
                episode.id,
                evaluation.affect_id,
                evaluation.japanese_name,
                evaluation.status,
                evaluation.reason,
                evaluation.confidence,
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
        names = ", ".join(affect.japanese_name for affect in affects if affect.status == "matched")
        candidates = ", ".join(affect.japanese_name for affect in affects if affect.status == "candidate") or "なし"
        summary = (
            f"日記ID: {diary.id}\n"
            f"日付: {diary.entry_date}\n"
            f"Episode数: {len(episodes)}\n"
            f"今日のコナトゥス変化: {conatus_total:+d}\n"
            f"主な情動: {names or 'なし'}\n"
            f"確認候補: {candidates}\n"
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
    def _conatus_delta(direction: str, intensity: int) -> int:
        if direction == "increase":
            return intensity
        if direction == "decrease":
            return -intensity
        return 0

    @staticmethod
    def _fmt_tokens(value: int | None) -> str:
        return "unavailable" if value is None else f"{value:,}"


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
