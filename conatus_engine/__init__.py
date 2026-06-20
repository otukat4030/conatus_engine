"""Conatus Engine.

『エチカ』第三部の概念をPythonで学ぶための実験用パッケージです。

このモデルは学習開始時点の暫定的な対応づけです。今後の精読に
よって、データ構造・関数名・判定規則は修正される前提です。
"""

from conatus_engine.models import Affect, Encounter, Mode, Person, evaluate_encounter

__all__ = [
    "Affect",
    "Encounter",
    "Mode",
    "Person",
    "evaluate_encounter",
]
