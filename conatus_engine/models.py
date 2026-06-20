"""Domain models for Conatus Engine.

このモジュールはCLIの入出力から独立したドメインロジックです。
『エチカ』第三部の精読が進むにつれて、ここにある概念対応と判定規則は
より精密なものへ修正していく想定です。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Affect(str, Enum):
    """力能の増減から暫定的に判定する感情の種類."""

    JOY = "joy"
    SADNESS = "sadness"
    NEUTRAL = "neutral"


class Mode(str, Enum):
    """原因理解の十分性から暫定的に判定する能動・受動の様態."""

    ACTIVE = "active"
    PASSIVE = "passive"


@dataclass(frozen=True)
class Person:
    """人物と、その時点での身体の活動能力・力能."""

    name: str
    power: float


@dataclass(frozen=True)
class Encounter:
    """人物が出会った出来事と、その出来事が力能に与える変化.

    sufficient_cause は「出来事の原因を十分に理解しているか」を表します。
    ここでの対応づけは学習用の暫定モデルであり、第三部の完全な解釈では
    ありません。
    """

    description: str
    power_delta: float
    sufficient_cause: bool


@dataclass(frozen=True)
class EncounterResult:
    """出会いを評価した結果.

    CLIや将来のWeb/GUIは、この結果を表示形式に変換するだけにします。
    """

    person_name: str
    event_description: str
    before_power: float
    after_power: float
    power_delta: float
    affect: Affect
    mode: Mode
    explanation: str


def classify_affect(power_delta: float) -> Affect:
    """力能の変化量から、喜び・悲しみ・中立を暫定的に判定する."""

    if power_delta > 0:
        return Affect.JOY
    if power_delta < 0:
        return Affect.SADNESS
    return Affect.NEUTRAL


def classify_mode(sufficient_cause: bool) -> Mode:
    """原因理解の十分性から、能動・受動を暫定的に判定する."""

    if sufficient_cause:
        return Mode.ACTIVE
    return Mode.PASSIVE


def build_explanation(affect: Affect, mode: Mode) -> str:
    """暫定判定についての短い日本語説明を作る."""

    affect_text = {
        Affect.JOY: "力能が増加したため、暫定的に喜びと判定しました。",
        Affect.SADNESS: "力能が減少したため、暫定的に悲しみと判定しました。",
        Affect.NEUTRAL: "力能が変化しないため、暫定的に中立と判定しました。",
    }[affect]

    mode_text = {
        Mode.ACTIVE: "原因を十分に理解しているため、能動としました。",
        Mode.PASSIVE: "原因の理解が不十分なため、受動としました。",
    }[mode]

    return f"{affect_text}{mode_text}これは第三部の学習開始時点の仮モデルです。"


def evaluate_encounter(person: Person, encounter: Encounter) -> EncounterResult:
    """人物と出会いから、力能変化・感情・能動/受動を評価する."""

    affect = classify_affect(encounter.power_delta)
    mode = classify_mode(encounter.sufficient_cause)
    after_power = person.power + encounter.power_delta

    return EncounterResult(
        person_name=person.name,
        event_description=encounter.description,
        before_power=person.power,
        after_power=after_power,
        power_delta=encounter.power_delta,
        affect=affect,
        mode=mode,
        explanation=build_explanation(affect, mode),
    )
