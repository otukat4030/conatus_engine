"""Small sqlite repository for saved OpenAI API usage estimates."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from conatus_engine.pricing import CostEstimate, PricingSnapshot, PricingStatus, TokenUsage


@dataclass(frozen=True)
class UsageRun:
    """A saved analysis-run usage row."""

    id: int
    created_at: str
    response_id: str | None
    requested_model: str | None
    actual_model: str | None
    service_tier: str | None
    usage: TokenUsage
    pricing_status: PricingStatus
    estimated_total_cost_usd: Decimal | None
    cost_estimation_note: str | None
    provider: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    segmentation_json: str | None = None
    status: str | None = None
    error_type: str | None = None


def default_db_path() -> Path:
    """Return the configured local database path."""

    configured = os.getenv("CONATUS_DB_PATH")
    if configured:
        return Path(configured)
    return Path.home() / ".conatus_engine" / "conatus.sqlite3"


class UsageRepository:
    """SQLite repository for usage rows."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    provider TEXT,
                    prompt_version TEXT,
                    schema_version TEXT,
                    segmentation_json TEXT,
                    status TEXT,
                    error_type TEXT,
                    response_id TEXT,
                    requested_model TEXT,
                    actual_model TEXT,
                    service_tier TEXT,
                    input_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    uncached_input_tokens INTEGER,
                    output_tokens INTEGER,
                    reasoning_tokens INTEGER,
                    total_tokens INTEGER,
                    pricing_status TEXT NOT NULL,
                    pricing_model TEXT,
                    pricing_catalog_version TEXT,
                    pricing_effective_from TEXT,
                    pricing_retrieved_at TEXT,
                    pricing_source TEXT,
                    input_price_per_1m_usd TEXT,
                    cached_input_price_per_1m_usd TEXT,
                    output_price_per_1m_usd TEXT,
                    uncached_input_cost_usd TEXT,
                    cached_input_cost_usd TEXT,
                    output_cost_usd TEXT,
                    estimated_total_cost_usd TEXT,
                    cost_estimation_note TEXT
                )
                """
            )
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(analysis_runs)").fetchall()
            }
            for column, definition in {
                "provider": "TEXT",
                "prompt_version": "TEXT",
                "schema_version": "TEXT",
                "segmentation_json": "TEXT",
                "status": "TEXT",
                "error_type": "TEXT",
            }.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE analysis_runs ADD COLUMN {column} {definition}")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_metadata(key, value) VALUES (?, ?)",
                ("schema_version", "1"),
            )

    def save_usage(
        self,
        *,
        response_id: str | None,
        requested_model: str | None,
        actual_model: str | None,
        service_tier: str | None,
        usage: TokenUsage,
        pricing: PricingSnapshot | None,
        estimate: CostEstimate,
        created_at: datetime | None = None,
        provider: str | None = None,
        prompt_version: str | None = None,
        schema_version: str | None = None,
        segmentation_json: str | None = None,
        status: str | None = "succeeded",
        error_type: str | None = None,
    ) -> int:
        """Save one usage and pricing estimate row."""

        created_at = created_at or datetime.now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_runs (
                    created_at, provider, prompt_version, schema_version, segmentation_json,
                    status, error_type, response_id, requested_model, actual_model, service_tier,
                    input_tokens, cached_input_tokens, uncached_input_tokens, output_tokens,
                    reasoning_tokens, total_tokens, pricing_status, pricing_model,
                    pricing_catalog_version, pricing_effective_from, pricing_retrieved_at,
                    pricing_source, input_price_per_1m_usd, cached_input_price_per_1m_usd,
                    output_price_per_1m_usd, uncached_input_cost_usd,
                    cached_input_cost_usd, output_cost_usd, estimated_total_cost_usd,
                    cost_estimation_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at.isoformat(timespec="seconds"),
                    provider,
                    prompt_version,
                    schema_version,
                    segmentation_json,
                    status,
                    error_type,
                    response_id,
                    requested_model,
                    actual_model,
                    service_tier,
                    usage.input_tokens,
                    usage.cached_input_tokens,
                    usage.uncached_input_tokens,
                    usage.output_tokens,
                    usage.reasoning_tokens,
                    usage.total_tokens,
                    estimate.status.value,
                    pricing.pricing_model if pricing else None,
                    pricing.pricing_catalog_version if pricing else None,
                    pricing.effective_from.isoformat() if pricing else None,
                    pricing.pricing_retrieved_at.isoformat() if pricing else None,
                    pricing.pricing_source if pricing else None,
                    str(pricing.input_price_per_1m_usd) if pricing else None,
                    str(pricing.cached_input_price_per_1m_usd) if pricing else None,
                    str(pricing.output_price_per_1m_usd) if pricing else None,
                    str(estimate.uncached_input_cost_usd)
                    if estimate.uncached_input_cost_usd is not None
                    else None,
                    str(estimate.cached_input_cost_usd)
                    if estimate.cached_input_cost_usd is not None
                    else None,
                    str(estimate.output_cost_usd)
                    if estimate.output_cost_usd is not None
                    else None,
                    str(estimate.estimated_total_cost_usd)
                    if estimate.estimated_total_cost_usd is not None
                    else None,
                    estimate.note,
                ),
            )
            return int(cursor.lastrowid)

    def get_usage(self, run_id: int) -> UsageRun | None:
        """Load one usage row."""

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM analysis_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return UsageRun(
            id=int(row["id"]),
            created_at=str(row["created_at"]),
            response_id=row["response_id"],
            requested_model=row["requested_model"],
            actual_model=row["actual_model"],
            service_tier=row["service_tier"],
            usage=TokenUsage(
                row["input_tokens"],
                row["cached_input_tokens"],
                row["uncached_input_tokens"],
                row["output_tokens"],
                row["reasoning_tokens"],
                row["total_tokens"],
            ),
            pricing_status=PricingStatus(row["pricing_status"]),
            estimated_total_cost_usd=(
                None
                if row["estimated_total_cost_usd"] is None
                else Decimal(str(row["estimated_total_cost_usd"]))
            ),
            cost_estimation_note=row["cost_estimation_note"],
            provider=row["provider"] if "provider" in row.keys() else None,
            prompt_version=row["prompt_version"] if "prompt_version" in row.keys() else None,
            schema_version=row["schema_version"] if "schema_version" in row.keys() else None,
            segmentation_json=row["segmentation_json"] if "segmentation_json" in row.keys() else None,
            status=row["status"] if "status" in row.keys() else None,
            error_type=row["error_type"] if "error_type" in row.keys() else None,
        )

    def list_usage(self) -> list[UsageRun]:
        """Return all saved usage rows."""

        with self._connect() as conn:
            ids = [
                int(row[0])
                for row in conn.execute("SELECT id FROM analysis_runs ORDER BY id")
            ]
        return [run for run_id in ids if (run := self.get_usage(run_id)) is not None]
