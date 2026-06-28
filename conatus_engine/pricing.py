"""OpenAI usage extraction and local cost estimation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from importlib import resources
from typing import Any


class PricingStatus(str, Enum):
    """Status of a local API cost estimate."""

    ESTIMATED = "estimated"
    USAGE_UNAVAILABLE = "usage_unavailable"
    UNKNOWN_MODEL = "unknown_model"
    UNSUPPORTED_SERVICE_TIER = "unsupported_service_tier"
    UNSUPPORTED_CONTEXT_BAND = "unsupported_context_band"
    PRICING_DATA_MISSING = "pricing_data_missing"
    INCOMPLETE_ESTIMATE = "incomplete_estimate"


@dataclass(frozen=True)
class TokenUsage:
    """Token usage returned by an OpenAI API response."""

    input_tokens: int | None
    cached_input_tokens: int | None
    uncached_input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class PricingSnapshot:
    """The exact pricing row applied to one estimate."""

    pricing_model: str
    service_tier: str | None
    context_band: str | None
    input_price_per_1m_usd: Decimal
    cached_input_price_per_1m_usd: Decimal
    output_price_per_1m_usd: Decimal
    effective_from: date
    pricing_source: str
    pricing_retrieved_at: date
    pricing_catalog_version: str


@dataclass(frozen=True)
class CostEstimate:
    """A locally calculated token-cost estimate."""

    status: PricingStatus
    uncached_input_cost_usd: Decimal | None
    cached_input_cost_usd: Decimal | None
    output_cost_usd: Decimal | None
    estimated_total_cost_usd: Decimal | None
    note: str | None


def _get_attr_or_key(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def extract_token_usage(response: Any) -> TokenUsage | None:
    """Extract token usage from a Responses API-like object without guessing."""

    usage = _get_attr_or_key(response, "usage")
    if usage is None:
        return None

    input_tokens = _get_attr_or_key(usage, "input_tokens")
    output_tokens = _get_attr_or_key(usage, "output_tokens")
    total_tokens = _get_attr_or_key(usage, "total_tokens")

    input_details = _get_attr_or_key(usage, "input_tokens_details")
    output_details = _get_attr_or_key(usage, "output_tokens_details")
    cached_input_tokens = _get_attr_or_key(input_details, "cached_tokens")
    reasoning_tokens = _get_attr_or_key(output_details, "reasoning_tokens")

    uncached = None
    if input_tokens is not None and cached_input_tokens is not None:
        uncached = max(int(input_tokens) - int(cached_input_tokens), 0)

    return TokenUsage(
        input_tokens=None if input_tokens is None else int(input_tokens),
        cached_input_tokens=(
            None if cached_input_tokens is None else int(cached_input_tokens)
        ),
        uncached_input_tokens=uncached,
        output_tokens=None if output_tokens is None else int(output_tokens),
        reasoning_tokens=None if reasoning_tokens is None else int(reasoning_tokens),
        total_tokens=None if total_tokens is None else int(total_tokens),
    )


def estimate_cost(usage: TokenUsage | None, pricing: PricingSnapshot | None) -> CostEstimate:
    """Estimate token cost using Decimal arithmetic.

    Reasoning tokens are treated as part of output tokens and are not added again.
    """

    if usage is None:
        return CostEstimate(
            PricingStatus.USAGE_UNAVAILABLE, None, None, None, None, "usage is absent"
        )
    if pricing is None:
        return CostEstimate(
            PricingStatus.PRICING_DATA_MISSING,
            None,
            None,
            None,
            None,
            "pricing data is unavailable",
        )
    required = (usage.input_tokens, usage.output_tokens, usage.cached_input_tokens)
    if any(value is None for value in required):
        return CostEstimate(
            PricingStatus.INCOMPLETE_ESTIMATE,
            None,
            None,
            None,
            None,
            "required token fields are incomplete",
        )

    uncached_tokens = usage.uncached_input_tokens
    if uncached_tokens is None:
        uncached_tokens = max(usage.input_tokens - usage.cached_input_tokens, 0)

    scale = Decimal("1000000")
    uncached_cost = (
        Decimal(uncached_tokens) / scale * pricing.input_price_per_1m_usd
    )
    cached_cost = (
        Decimal(usage.cached_input_tokens)
        / scale
        * pricing.cached_input_price_per_1m_usd
    )
    output_cost = Decimal(usage.output_tokens) / scale * pricing.output_price_per_1m_usd
    total = uncached_cost + cached_cost + output_cost
    return CostEstimate(
        PricingStatus.ESTIMATED,
        uncached_cost,
        cached_cost,
        output_cost,
        total,
        "locally calculated estimate; not a final billed amount",
    )


def load_pricing_catalog() -> dict[str, Any]:
    """Load the bundled pricing catalog."""

    text = resources.files("conatus_engine.data").joinpath(
        "model_pricing.json"
    ).read_text(encoding="utf-8")
    return json.loads(text)


def _entry_to_snapshot(entry: dict[str, Any], catalog: dict[str, Any]) -> PricingSnapshot:
    return PricingSnapshot(
        pricing_model=str(entry["model_pattern"]),
        service_tier=entry.get("service_tier"),
        context_band=entry.get("context_band"),
        input_price_per_1m_usd=Decimal(str(entry["input_price_per_1m_usd"])),
        cached_input_price_per_1m_usd=Decimal(
            str(entry["cached_input_price_per_1m_usd"])
        ),
        output_price_per_1m_usd=Decimal(str(entry["output_price_per_1m_usd"])),
        effective_from=date.fromisoformat(str(entry["effective_from"])),
        pricing_source=str(catalog["source_name"]),
        pricing_retrieved_at=date.fromisoformat(str(catalog["retrieved_at"])),
        pricing_catalog_version=str(catalog["schema_version"]),
    )


def resolve_pricing(
    model: str,
    *,
    service_tier: str | None = "standard",
    context_band: str | None = "short",
    catalog: dict[str, Any] | None = None,
) -> tuple[PricingSnapshot | None, PricingStatus, str | None]:
    """Resolve a model to a pricing row without fuzzy substring guesses."""

    catalog = catalog or load_pricing_catalog()
    entries = catalog.get("entries", [])
    aliases = catalog.get("snapshot_aliases", {})
    candidates = [model]
    if model in aliases:
        candidates.append(str(aliases[model]))
    for entry in entries:
        if str(entry["model_pattern"]) not in candidates:
            continue
        if entry.get("service_tier") != service_tier:
            return None, PricingStatus.UNSUPPORTED_SERVICE_TIER, "unsupported service tier"
        if entry.get("context_band") != context_band:
            return None, PricingStatus.UNSUPPORTED_CONTEXT_BAND, "unsupported context band"
        return _entry_to_snapshot(entry, catalog), PricingStatus.ESTIMATED, None

    for entry in entries:
        pattern = entry.get("safe_regex")
        if pattern and re.fullmatch(str(pattern), model):
            if entry.get("service_tier") != service_tier:
                return None, PricingStatus.UNSUPPORTED_SERVICE_TIER, "unsupported service tier"
            if entry.get("context_band") != context_band:
                return None, PricingStatus.UNSUPPORTED_CONTEXT_BAND, "unsupported context band"
            return _entry_to_snapshot(entry, catalog), PricingStatus.ESTIMATED, None
    return None, PricingStatus.UNKNOWN_MODEL, "unknown model"


def validate_pricing_catalog(catalog: dict[str, Any] | None = None) -> list[str]:
    """Return validation errors for the pricing catalog."""

    catalog = catalog or load_pricing_catalog()
    errors: list[str] = []
    if catalog.get("currency") != "USD":
        errors.append("currency must be USD")
    if not catalog.get("source_name") or not catalog.get("retrieved_at"):
        errors.append("source_name and retrieved_at are required")
    try:
        date.fromisoformat(str(catalog.get("retrieved_at")))
    except ValueError:
        errors.append("retrieved_at must be an ISO date")

    seen: set[tuple[str, str | None, str | None, str]] = set()
    for index, entry in enumerate(catalog.get("entries", []), start=1):
        key = (
            str(entry.get("model_pattern")),
            entry.get("service_tier"),
            entry.get("context_band"),
            str(entry.get("effective_from")),
        )
        if key in seen:
            errors.append(f"entry {index}: duplicate pricing key")
        seen.add(key)
        for field in (
            "input_price_per_1m_usd",
            "cached_input_price_per_1m_usd",
            "output_price_per_1m_usd",
        ):
            try:
                if Decimal(str(entry[field])) < 0:
                    errors.append(f"entry {index}: {field} must not be negative")
            except Exception:
                errors.append(f"entry {index}: {field} must be Decimal text")
        try:
            date.fromisoformat(str(entry["effective_from"]))
        except Exception:
            errors.append(f"entry {index}: effective_from must be an ISO date")
    return errors


def format_usd(value: Decimal | None) -> str:
    """Format USD without hiding small costs as $0.00."""

    if value is None:
        return "unavailable"
    return f"${value.quantize(Decimal('0.000001'))}"
