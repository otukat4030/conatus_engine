# Conatus Engine

Python学習を兼ねて、スピノザ『エチカ』第三部の概念を小さなプログラムへ翻訳するための実験用プロジェクトです。

このプロジェクトは、第三部の完全な解釈を最初から実装するものではありません。現在のコードは、精読を始めるための暫定モデルです。今後の読解によって、データモデル、関数、判定規則、用語の対応関係を修正していく前提です。

## 現在の鋳型

- `Person`: 人物名と現在の力能
- `Encounter`: 出会った出来事、力能の変化量、原因理解の十分性
- `Affect`: `joy`, `sadness`, `neutral`
- `Mode`: `active`, `passive`
- `evaluate_encounter`: 出会いによる力能変化を評価するドメイン関数

CLIの入出力は `conatus_engine/cli.py`、概念モデルと判定規則は `conatus_engine/models.py` に分けています。将来WebアプリやGUIへ拡張する場合も、まずドメインロジックを再利用できます。

## 暫定的な判定規則

- 力能が増加した場合は `joy`
- 力能が減少した場合は `sadness`
- 力能が変化しない場合は `neutral`
- 原因が十分な場合は `active`
- 原因が不十分な場合は `passive`

## 実行方法

Python 3.12以降を使います。

```bash
python -m conatus_engine
```

インストールしてコマンドとして実行する場合:

```bash
pip install -e .
conatus-engine
```

## 実行例

```
PS E:\Documents\conatus_engine> uv run python -m conatus_engine
Conatus Engine
『エチカ』第三部をPythonで読むための暫定モデルです。

人物名: 岸本    
現在の力能: 0
出会った出来事の説明: ベッドから立ち上がってスマホを見ようとしたら首がピキっといった。
出会いによる力能の変化量: -100
その出来事の原因を十分に理解していますか？ (y/n): y

=== Conatus Engine Result ===
人物名: 岸本
出来事: ベッドから立ち上がってスマホを見ようとしたら首がピキっといった。
変化前の力能: 0.0
変化後の力能: -100.0
力能の変化量: -100.0
affect: sadness
mode: active
説明: 力能が減少したため、暫定的に悲しみと判定しました。原因を十分に理解しているため、能動としました。これは第三部の学習開始時点の仮モデルです。
```

## テスト

開発用依存関係として `pytest` を使います。

```bash
pip install -e ".[dev]"
pytest
```

## プロジェクト構成

```text
conatus_engine/
  __init__.py
  __main__.py
  cli.py
  models.py
tests/
  test_models.py
pyproject.toml
README.md
```
