"""Command-line interface for Conatus Engine.

CLIは入力と表示だけを担当し、哲学的概念の暫定モデルはmodels.pyへ分離します。
今後の精読でモデルを直しても、入出力層への影響を小さくするためです。
"""

from __future__ import annotations

from conatus_engine.models import Encounter, EncounterResult, Person, evaluate_encounter


def read_float(prompt: str) -> float:
    """floatとして読めるまで入力を促す."""

    while True:
        raw_value = input(prompt).strip()
        try:
            return float(raw_value)
        except ValueError:
            print("数値を入力してください。例: 10, -2.5, 0")


def read_yes_no(prompt: str) -> bool:
    """y/nとして読めるまで入力を促す."""

    while True:
        raw_value = input(prompt).strip().lower()
        if raw_value == "y":
            return True
        if raw_value == "n":
            return False
        print("y または n を入力してください。")


def format_result(result: EncounterResult) -> str:
    """評価結果をCLI表示用の文字列へ変換する."""

    return "\n".join(
        [
            "",
            "=== Conatus Engine Result ===",
            f"人物名: {result.person_name}",
            f"出来事: {result.event_description}",
            f"変化前の力能: {result.before_power}",
            f"変化後の力能: {result.after_power}",
            f"力能の変化量: {result.power_delta}",
            f"affect: {result.affect.value}",
            f"mode: {result.mode.value}",
            f"説明: {result.explanation}",
        ]
    )


def main() -> None:
    """Conatus EngineのCLIエントリーポイント."""

    print("Conatus Engine")
    print("『エチカ』第三部をPythonで読むための暫定モデルです。")
    print()

    name = input("人物名: ").strip()
    current_power = read_float("現在の力能: ")
    description = input("出会った出来事の説明: ").strip()
    power_delta = read_float("出会いによる力能の変化量: ")
    sufficient_cause = read_yes_no("その出来事の原因を十分に理解していますか？ (y/n): ")

    person = Person(name=name, power=current_power)
    encounter = Encounter(
        description=description,
        power_delta=power_delta,
        sufficient_cause=sufficient_cause,
    )

    result = evaluate_encounter(person, encounter)
    print(format_result(result))


if __name__ == "__main__":
    main()
