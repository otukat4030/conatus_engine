"""Command-line interface for Conatus Engine."""

from __future__ import annotations

from conatus_engine.engine import step
from conatus_engine.models import (
    AgentState,
    CausalAdequacy,
    IdeaAdequacy,
    Transition,
    WorldEvent,
)


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


def main() -> None:
    """Run the Conatus Engine CLI."""

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


if __name__ == "__main__":
    main()
