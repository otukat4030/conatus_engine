from conatus_engine.pricing import TokenUsage, estimate_cost, resolve_pricing
from conatus_engine.usage_store import UsageRepository


def test_usage_repository_saves_estimate_without_recomputing(tmp_path) -> None:
    pricing, _, _ = resolve_pricing("gpt-5.4-mini")
    usage = TokenUsage(1000, 400, 600, 200, 150, 1200)
    estimate = estimate_cost(usage, pricing)
    repo = UsageRepository(tmp_path / "usage.sqlite3")

    run_id = repo.save_usage(
        response_id="resp_1",
        requested_model="gpt-5.4-mini",
        actual_model="gpt-5.4-mini",
        service_tier="standard",
        usage=usage,
        pricing=pricing,
        estimate=estimate,
    )
    restored = repo.get_usage(run_id)

    assert restored is not None
    assert restored.usage.input_tokens == 1000
    assert restored.estimated_total_cost_usd == estimate.estimated_total_cost_usd
