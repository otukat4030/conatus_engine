"""Command-line interface for Conatus Engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from conatus_engine.affect_catalog import (
    load_affect_catalog,
    validate_affect_catalog,
)
from conatus_engine.affect_rules import validate_rule_engine
from conatus_engine.engine import step
from conatus_engine.models import (
    AgentState,
    CausalAdequacy,
    IdeaAdequacy,
    Transition,
    WorldEvent,
)
from conatus_engine.pricing import (
    TokenUsage,
    estimate_cost,
    format_usd,
    load_pricing_catalog,
    resolve_pricing,
    validate_pricing_catalog,
)
from conatus_engine.usage_store import UsageRepository


def read_float(prompt: str) -> float:
    """Read a floating-point number from standard input."""

    while True:
        raw_value = input(prompt).strip()
        try:
            return float(raw_value)
        except ValueError:
            print("数値を入力してください。例: 10, -2.5, 0")


def read_non_empty(prompt: str) -> str:
    """Read a non-empty text value from standard input."""

    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("空ではない値を入力してください。")


def read_yes_no(prompt: str) -> bool:
    """Read y/n from standard input."""

    while True:
        raw_value = input(prompt).strip().lower()
        if raw_value == "y":
            return True
        if raw_value == "n":
            return False
        print("y または n を入力してください。")


def format_transition(transition: Transition) -> str:
    """Format a transition for CLI output."""

    lines = [
        "",
        "=== 状態遷移 ===",
        f"人物ID: {transition.before.agent_id}",
        f"人物名: {transition.before.name}",
        f"イベントID: {transition.event.event_id}",
        f"出来事: {transition.event.description}",
        f"更新前の力能: {transition.before.power}",
        f"更新後の力能: {transition.after.power}",
        f"力能の変化量: {transition.event.power_delta}",
        f"情動: {transition.affect.value}",
        f"能動／受動: {transition.mode.value}",
        f"因果的十分性: {transition.event.causal_adequacy.value}",
        f"観念の十分性: {transition.idea_adequacy.value}",
        "",
        "導出履歴:",
    ]
    for derivation in transition.derivations:
        lines.extend(
            [
                f"- {derivation.rule_id}",
                f"  premises: {', '.join(derivation.premises)}",
                f"  conclusion: {derivation.conclusion}",
                f"  explanation: {derivation.explanation}",
            ]
        )
    return "\n".join(lines)


def read_event() -> WorldEvent:
    """Read one world event from standard input."""

    event_id = read_non_empty("イベントID: ")
    description = read_non_empty("出来事の説明: ")
    power_delta = read_float("出来事による力能の変化量: ")
    causally_adequate = read_yes_no(
        "この結果は、その人物自身の本性・力から十分に説明できますか？ (y/n): "
    )
    idea_adequate = read_yes_no(
        "その人物は、出来事の原因を十分に理解していますか？ (y/n): "
    )

    return WorldEvent(
        event_id=event_id,
        description=description,
        power_delta=power_delta,
        causal_adequacy=(
            CausalAdequacy.ADEQUATE
            if causally_adequate
            else CausalAdequacy.PARTIAL
        ),
        idea_adequacy=IdeaAdequacy.ADEQUATE
        if idea_adequate
        else IdeaAdequacy.INADEQUATE,
    )


def run_interactive() -> None:
    """Run the original interactive Conatus Engine CLI."""

    print("Conatus Engine")
    print("スピノザ『エチカ』第三部を学ぶための暫定的な状態遷移モデルです。")
    print("初期状態を入力したあと、出来事を順に適用して状態遷移を体験できます。")
    print()

    name = read_non_empty("人物名: ")
    current_power = read_float("現在の力能: ")
    state = AgentState(agent_id=name, name=name, power=current_power)

    while True:
        print()
        print(f"--- 現在の状態: {state.name} / power={state.power} ---")
        if not read_yes_no("新しい出来事を入力しますか？ (y/n): "):
            break

        transition = step(state, read_event())
        print(format_transition(transition))
        state = transition.after

    print()
    print("=== 最終状態 ===")
    print(f"人物ID: {state.agent_id}")
    print(f"人物名: {state.name}")
    print(f"力能: {state.power}")


def _print_pricing_list() -> None:
    catalog = load_pricing_catalog()
    print("=== Pricing Catalog ===")
    print(f"Source: {catalog['source_name']}")
    print(f"Retrieved at: {catalog['retrieved_at']}")
    print("Prices are USD per 1M tokens and are local estimates only.")
    for entry in catalog["entries"]:
        print(
            f"- {entry['model_pattern']} [{entry['service_tier']}/{entry['context_band']}] "
            f"input={entry['input_price_per_1m_usd']} cached={entry['cached_input_price_per_1m_usd']} "
            f"output={entry['output_price_per_1m_usd']}"
        )


def _print_pricing_show(model: str) -> int:
    pricing, status, note = resolve_pricing(model)
    if pricing is None:
        print(f"Pricing unavailable: {status.value}")
        if note:
            print(f"Reason: {note}")
        return 1
    print(f"Model: {model}")
    print(f"Pricing model: {pricing.pricing_model}")
    print(f"Service tier: {pricing.service_tier}")
    print(f"Context band: {pricing.context_band}")
    print(f"Input / 1M: {pricing.input_price_per_1m_usd} USD")
    print(f"Cached input / 1M: {pricing.cached_input_price_per_1m_usd} USD")
    print(f"Output / 1M: {pricing.output_price_per_1m_usd} USD")
    print(f"Effective from: {pricing.effective_from}")
    print(f"Retrieved at: {pricing.pricing_retrieved_at}")
    print("This is a local estimate source, not a final billed amount.")
    return 0


def _print_pricing_validate() -> int:
    errors = validate_pricing_catalog()
    if errors:
        print("Pricing catalog validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Pricing catalog validation passed.")
    return 0


def _print_affect_list(all_items: bool) -> None:
    items = load_affect_catalog()
    for item in items if all_items else items[:10]:
        kinds = ",".join(kind.value for kind in item.classification)
        deps = ",".join(item.dependencies) or "-"
        print(
            f"{item.number:02d} {item.canonical_id} {item.latin_name} / "
            f"{item.english_name} / {item.japanese_name} "
            f"[{kinds}; {item.temporal_scope.value}; deps={deps}; {item.rule_id}]"
        )
    if not all_items:
        print("Use --all to show all 48 definitions.")


def _print_affect_show(affect_id: str) -> int:
    for item in load_affect_catalog():
        if item.canonical_id == affect_id:
            print(f"{item.canonical_id} Definition {item.number}")
            print(f"Latin: {item.latin_name}")
            print(f"English: {item.english_name}")
            print(f"Japanese: {item.japanese_name}")
            print(f"Source text: {item.public_domain_text}")
            print(f"Project Japanese translation: {item.japanese_translation}")
            print(f"Summary: {item.summary}")
            print(f"Source: {item.source}")
            print(f"Rights: {item.rights_status}")
            print(f"Rights evidence: {item.rights_evidence}")
            print(f"Rule: {item.rule_id}")
            print(f"Dependencies: {', '.join(item.dependencies) or '-'}")
            return 0
    print(f"Unknown affect ID: {affect_id}")
    return 1


def _print_affect_graph() -> None:
    for item in load_affect_catalog():
        deps = ", ".join(item.dependencies) or "root"
        print(f"{deps} -> {item.canonical_id} ({item.japanese_name})")


def _print_affect_validate() -> int:
    errors = validate_affect_catalog() + validate_rule_engine()
    if errors:
        print("Affect catalog validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Affect catalog and rule engine validation passed: 48 definitions, P3-DA-01..P3-DA-48.")
    return 0


def _print_usage_block(run) -> None:
    usage = run.usage
    print("=== OpenAI API Usage ===")
    print(f"Run ID: {run.id}")
    print(f"Created at: {run.created_at}")
    print(f"Model: {run.actual_model or run.requested_model or 'unknown'}")
    print(f"Service tier: {run.service_tier or 'unknown'}")
    print(f"Input tokens: {usage.input_tokens}")
    print(f"Cached input tokens: {usage.cached_input_tokens}")
    print(f"Uncached input tokens: {usage.uncached_input_tokens}")
    print(f"Output tokens: {usage.output_tokens}")
    print(f"Reasoning tokens: {usage.reasoning_tokens}")
    print(f"Total tokens: {usage.total_tokens}")
    print(f"Estimated total cost: {format_usd(run.estimated_total_cost_usd)}")
    print(f"Pricing status: {run.pricing_status.value}")
    print("This is a locally calculated estimate, not the final billed amount.")
    print("Reasoning tokens are included in output tokens and are not charged twice.")


def _usage_demo(args: argparse.Namespace) -> int:
    pricing, status, note = resolve_pricing(args.model)
    usage = TokenUsage(
        input_tokens=args.input_tokens,
        cached_input_tokens=args.cached_input_tokens,
        uncached_input_tokens=max(args.input_tokens - args.cached_input_tokens, 0),
        output_tokens=args.output_tokens,
        reasoning_tokens=args.reasoning_tokens,
        total_tokens=args.input_tokens + args.output_tokens,
    )
    estimate = estimate_cost(usage, pricing)
    if pricing is None:
        estimate = estimate.__class__(status, None, None, None, None, note)
    run_id = UsageRepository(args.db).save_usage(
        response_id="mock-response",
        requested_model=args.model,
        actual_model=args.model,
        service_tier="standard",
        usage=usage,
        pricing=pricing,
        estimate=estimate,
    )
    run = UsageRepository(args.db).get_usage(run_id)
    if run:
        _print_usage_block(run)
    return 0


def _usage_show(args: argparse.Namespace) -> int:
    run = UsageRepository(args.db).get_usage(args.analysis_run_id)
    if run is None:
        print(f"Usage run not found: {args.analysis_run_id}")
        return 1
    _print_usage_block(run)
    return 0


def _usage_report(args: argparse.Namespace) -> int:
    runs = UsageRepository(args.db).list_usage()
    estimated = [run for run in runs if run.estimated_total_cost_usd is not None]
    total = sum((run.estimated_total_cost_usd for run in estimated), start=0)
    print(f"=== OpenAI API usage report ({args.period}: {args.date}) ===")
    print(f"API analysis runs: {len(runs)}")
    print(f"Usage rows with estimates: {len(estimated)}")
    print(f"Rows without estimates: {len(runs) - len(estimated)}")
    print(f"Estimated total cost: {format_usd(total if estimated else None)}")
    print("This is based on saved token usage and local pricing data, not billing.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the subcommand parser."""

    parser = argparse.ArgumentParser(prog="conatus-engine")
    subparsers = parser.add_subparsers(dest="command")

    pricing = subparsers.add_parser("pricing")
    pricing_sub = pricing.add_subparsers(dest="pricing_command", required=True)
    pricing_sub.add_parser("list")
    pricing_show = pricing_sub.add_parser("show")
    pricing_show.add_argument("model")
    pricing_sub.add_parser("validate")

    usage = subparsers.add_parser("usage")
    usage_sub = usage.add_subparsers(dest="usage_command", required=True)
    usage_show = usage_sub.add_parser("show")
    usage_show.add_argument("analysis_run_id", type=int)
    usage_show.add_argument("--db", type=Path)
    usage_report = usage_sub.add_parser("report")
    usage_report.add_argument("--period", choices=("day", "month", "year"), required=True)
    usage_report.add_argument("--date", required=True)
    usage_report.add_argument("--db", type=Path)
    usage_demo = usage_sub.add_parser("demo")
    usage_demo.add_argument("--model", default="gpt-5.4-mini")
    usage_demo.add_argument("--input-tokens", type=int, default=2140)
    usage_demo.add_argument("--cached-input-tokens", type=int, default=860)
    usage_demo.add_argument("--output-tokens", type=int, default=720)
    usage_demo.add_argument("--reasoning-tokens", type=int, default=180)
    usage_demo.add_argument("--db", type=Path)

    affect = subparsers.add_parser("affect")
    affect_sub = affect.add_subparsers(dest="affect_command", required=True)
    affect_list = affect_sub.add_parser("list")
    affect_list.add_argument("--all", action="store_true")
    affect_show = affect_sub.add_parser("show")
    affect_show.add_argument("affect_id")
    affect_sub.add_parser("graph")
    affect_sub.add_parser("validate")
    return parser


def run_args(argv: list[str]) -> int:
    """Run a subcommand."""

    args = build_parser().parse_args(argv)
    if args.command == "pricing":
        if args.pricing_command == "list":
            _print_pricing_list()
            return 0
        if args.pricing_command == "show":
            return _print_pricing_show(args.model)
        if args.pricing_command == "validate":
            return _print_pricing_validate()
    if args.command == "affect":
        if args.affect_command == "list":
            _print_affect_list(args.all)
            return 0
        if args.affect_command == "show":
            return _print_affect_show(args.affect_id)
        if args.affect_command == "graph":
            _print_affect_graph()
            return 0
        if args.affect_command == "validate":
            return _print_affect_validate()
    if args.command == "usage":
        if args.usage_command == "show":
            return _usage_show(args)
        if args.usage_command == "report":
            return _usage_report(args)
        if args.usage_command == "demo":
            return _usage_demo(args)
    return 1


def main(argv: list[str] | None = None) -> None:
    """Run the Conatus Engine CLI."""

    if argv is None:
        argv = [] if "pytest" in Path(sys.argv[0]).name else sys.argv[1:]
    if not argv:
        run_interactive()
        return
    raise SystemExit(run_args(argv))


if __name__ == "__main__":
    main(sys.argv[1:])


if __name__ == "__main__":
    main()
