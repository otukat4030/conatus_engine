from decimal import Decimal
from types import SimpleNamespace

from conatus_engine.pricing import (
    PricingStatus,
    TokenUsage,
    estimate_cost,
    extract_token_usage,
    resolve_pricing,
    validate_pricing_catalog,
)


def test_extract_token_usage_with_cached_and_reasoning_tokens() -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=2140,
            input_tokens_details=SimpleNamespace(cached_tokens=860),
            output_tokens=720,
            output_tokens_details=SimpleNamespace(reasoning_tokens=180),
            total_tokens=2860,
        )
    )

    usage = extract_token_usage(response)

    assert usage is not None
    assert usage.cached_input_tokens == 860
    assert usage.uncached_input_tokens == 1280
    assert usage.reasoning_tokens == 180


def test_extract_token_usage_returns_none_when_usage_missing() -> None:
    assert extract_token_usage(SimpleNamespace()) is None


def test_cached_tokens_larger_than_input_is_clamped() -> None:
    response = {"usage": {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 20}}}

    usage = extract_token_usage(response)

    assert usage is not None
    assert usage.uncached_input_tokens == 0


def test_estimate_cost_does_not_double_count_reasoning_tokens() -> None:
    pricing, status, _ = resolve_pricing("gpt-5.4-mini")
    assert status is PricingStatus.ESTIMATED
    usage = TokenUsage(
        input_tokens=1000,
        cached_input_tokens=400,
        uncached_input_tokens=600,
        output_tokens=200,
        reasoning_tokens=150,
        total_tokens=1200,
    )

    estimate = estimate_cost(usage, pricing)

    assert estimate.status is PricingStatus.ESTIMATED
    assert estimate.estimated_total_cost_usd == Decimal("0.0013800")


def test_unknown_model_is_not_guessed_from_mini_substring() -> None:
    pricing, status, _ = resolve_pricing("my-mini-experiment")

    assert pricing is None
    assert status is PricingStatus.UNKNOWN_MODEL


def test_pricing_catalog_validates() -> None:
    assert validate_pricing_catalog() == []
