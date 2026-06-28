# Conatus Engine

Conatus Engine は、スピノザ『エチカ』第三部の概念を Python のデータモデル、デスクトップGUI、コマンドライン操作で扱うためのエンジンです。

バージョン `0.4.0` では、既存の状態遷移エンジンに加えて、次の機能を追加しています。

- 『エチカ』第三部末尾の `Definitiones Affectuum` にある番号付き情動定義 48 件のカタログ
- OpenAI API の usage 情報にもとづくトークン数と概算料金の記録・表示
- PySide6 によるデスクトップGUI

API料金機能は、OpenAI API のレスポンスに含まれる usage 情報と、ローカルの料金表を使って概算額を計算します。請求書や最終請求額を取得するものではありません。

## 日記解析の流れ

`openai` モードでは、GUIの「保存して解析」で入力した日記本文を OpenAI Responses API に送信します。APIには情動名を直接決めさせず、日記から観察できるEpisode特徴だけを Structured Outputs として返させます。返ってきた特徴を `conatus_engine` の48情動ルールエンジンが判定し、Episodeごとに代表情動を1件だけ保存・表示します。

```mermaid
flowchart TD
    A[日記本文] --> B[OpenAI Responses API<br/>Structured Outputs]
    B --> C[DiaryAnalysisSchema<br/>episodes[]]
    C --> D[Episode特徴<br/>要約・根拠・力能方向・強度・観察フラグ]
    D --> E[conatus_delta計算<br/>increase=+intensity / decrease=-intensity]
    D --> F[48情動ルールを全評価]
    F --> G[Episodeごとに代表情動を1件選択]
    E --> H[GUI/SQLite出力]
    G --> H
    B --> I[usage情報<br/>トークン数]
    I --> J[概算料金計算]
    J --> H
```

APIから受け取る主な出力は、`DiaryAnalysisSchema` の `episodes` 配列です。1つの日記から複数のEpisodeが抽出されることがあります。各Episodeには、次のような特徴が入ります。

- `summary`: Episodeの短い要約
- `evidence_text`: 日記本文中の根拠
- `power_direction`: コナトゥスが増加したか、減少したか、中立か
- `intensity`: 0から5の強度
- `confidence`: 抽出の確信度
- `desire_present`, `external_cause`, `target_present`, `gratitude`, `anger`, `remorse` など、48情動ルールが参照する観察フラグ

`conatus_engine` はこのAPI出力から `conatus_delta` を計算します。`increase` は `+intensity`、`decrease` は `-intensity`、`neutral` と `unknown` は `0` です。そのうえで48情動定義をすべて決定論的に評価し、`matched` を優先、次に `candidate` を優先して、1つのEpisodeに1つの代表情動を割り当てます。必要な意味情報が不足している場合は、無理に「欲望」などへ分類せず、`未分類` として扱います。

最終的な出力は、日記タブの解析サマリー、Episode一覧、情動ログ、情動別グラフ、コナトゥス時系列、SQLite保存データ、OpenAI APIのトークン数と概算料金です。情動ログの一覧は日記単位で表示します。期間と情動名で絞り込み、選択した日記の本文、該当Episode、日付、判定理由を確認できます。

## 変更点

以前は混ざっていた次の二つの概念を分離しています。

- `CausalAdequacy`: 結果が、その主体自身の本性と力から十分に説明できるか
- `IdeaAdequacy`: 主体が、その出来事の原因を十分に理解しているか

能動・受動の判定は `CausalAdequacy` だけから行います。

- `adequate` な因果的十分性 -> `active`
- `partial` な因果的十分性 -> `passive`

`IdeaAdequacy` は独立した情報として記録されます。これにより、外的な出来事の原因を理解していても、その結果の十分な原因が本人ではない、というケースを表現できます。

## 中核モデル

- `AgentState`: ある時点における主体の状態
- `WorldEvent`: 主体の力能を変化させる出来事
- `Transition`: ひとつの出来事を状態へ適用した前後の結果
- `Derivation`: 結果を説明する規則適用の履歴

`power_delta` は入力値として与えます。エンジンはその値をもとに状態遷移、情動、能動・受動、導出履歴を計算します。力能は有限の実数として扱います。

## Python API

```python
from conatus_engine import (
    AgentState,
    CausalAdequacy,
    IdeaAdequacy,
    WorldEvent,
    step,
)

state = AgentState(agent_id="agent-1", name="Spinoza", power=10.0)
event = WorldEvent(
    event_id="event-1",
    description="A clear but externally caused event",
    power_delta=-2.0,
    causal_adequacy=CausalAdequacy.PARTIAL,
    idea_adequacy=IdeaAdequacy.ADEQUATE,
)

transition = step(state, event)

assert transition.before == state
assert transition.after.power == 8.0
assert transition.affect.value == "sadness"
assert transition.mode.value == "passive"
assert transition.idea_adequacy.value == "adequate"
assert len(transition.derivations) >= 4
```

ラッパークラスも使えます。

```python
from conatus_engine import ConatusEngine

transition = ConatusEngine().step(state, event)
```

## JSON

`AgentState`, `WorldEvent`, `Transition` は、JSON互換の辞書とJSON文字列へ変換できます。

```python
data = transition.to_dict()
json_text = transition.to_json()
restored = transition.from_json(json_text)
assert restored == transition
```

状態遷移JSONの例:

```json
{
  "before": {"agent_id": "agent-1", "name": "Spinoza", "power": 10.0},
  "after": {"agent_id": "agent-1", "name": "Spinoza", "power": 8.0},
  "event": {
    "event_id": "event-1",
    "description": "A clear but externally caused event",
    "power_delta": -2.0,
    "causal_adequacy": "partial",
    "idea_adequacy": "adequate"
  },
  "affect": "sadness",
  "mode": "passive",
  "idea_adequacy": "adequate",
  "derivations": [
    {
      "rule_id": "power.update",
      "premises": ["before.power=10.0", "event.power_delta=-2.0"],
      "conclusion": "after.power=8.0",
      "explanation": "出来事に与えられた力能変化量を現在の力能に加算します。"
    }
  ]
}
```

## GUI

次のコマンドでデスクトップGUIを起動できます。

```bash
python -m conatus_engine
```

インストール後は、次のコマンドも使えます。

```bash
pip install -e .
conatus-engine
```

GUIには3つのタブがあります。

- `日記`: 日付と日記本文を入力し、保存または解析を実行します。解析結果、Episode一覧、API usage、概算料金を表示します。
- `情動ログ`: 保存済み日記を期間と情動名で絞り込み、日記単位の行として表示します。行選択で元の日記・該当Episode・代表情動・API使用量の詳細を表示します。選択した日記ログの削除もできます。情動別件数とコナトゥス時系列はMatplotlibグラフで表示します。
- `設定`: 解析モード、使用モデル、SQLiteデータベースパス、料金表情報、USD/JPY換算レート、月間API予算、APIキー入力、OpenAI接続確認を扱います。

APIキー入力欄は伏せ字表示です。保存を選んだ場合はOSのkeyringへ保存します。QSettings、SQLite、README、ログへAPIキーを平文保存しません。keyringが利用できない場合、平文ファイルへのフォールバック保存は行いません。

解析モードは `mock` と `openai` を選択できます。`mock` はネットワークを使わないデモ・テスト用です。`openai` はOpenAI Responses APIのStructured Outputsを使い、日記本文からEpisode特徴を抽出します。抽出された特徴はPython側の48情動ルールエンジンへ渡され、Episodeごとに代表情動が1件選ばれます。使用モデルは設定タブのコンボボックスから選択できます。

設定タブの `接続確認` は実際にOpenAI APIへ短いリクエストを送信します。少額の利用料金が発生する場合があります。レート制限や利用上限に達した場合は、時間を置くか、別モデルを選択してください。

日記をOpenAI APIで解析する場合、日記本文はAPIへ送信されます。SQLiteには日記本文が平文で保存されます。このアプリは医療・心理診断を目的としません。

GUIを起動してすぐ閉じる確認には、次を使えます。

```bash
python -m conatus_engine --quit-after-start
```

## CLI

既存のCLIは別エントリーポイントとして残しています。

```bash
python -m conatus_engine.cli --help
conatus-engine-cli --help
```

引数なしで起動すると、CLIは最初に `AgentState` の初期値として人物名と現在の力能を尋ねます。入力された人物名は内部の `agent_id` としても使われます。その後、出来事を順に入力するループに入り、各 `WorldEvent` が現在状態へ適用され、結果の `after` 状態が次の現在状態になります。

各出来事について、CLIは次の二点を個別に尋ねます。

- その結果が、人物自身の本性・力から十分に説明できるか
- その人物が、出来事の原因を十分に理解しているか

実行例:

```text
人物名: Spinoza
現在の力能: 10

--- 現在の状態: Spinoza / power=10.0 ---
新しい出来事を入力しますか？ (y/n): y
イベントID: event-1
出来事の説明: 外的な出来事の原因を正しく理解した
出来事による力能の変化量: -2
この結果は、その人物自身の本性・力から十分に説明できますか？ (y/n): n
その人物は、出来事の原因を十分に理解していますか？ (y/n): y
```

出力には、更新前後の力能、情動、能動・受動、因果的十分性、観念の十分性、導出履歴が含まれます。

## サブコマンド

情動カタログ:

```bash
python -m conatus_engine.cli affect validate
python -m conatus_engine.cli affect list --all
python -m conatus_engine.cli affect show P3-DA-22
python -m conatus_engine.cli affect graph
```

OpenAI API料金表:

```bash
python -m conatus_engine.cli pricing validate
python -m conatus_engine.cli pricing list
python -m conatus_engine.cli pricing show gpt-5.4-mini
```

OpenAI API usage:

```bash
python -m conatus_engine.cli usage demo --db ./usage-demo.sqlite3
python -m conatus_engine.cli usage show 1 --db ./usage-demo.sqlite3
python -m conatus_engine.cli usage report --period month --date 2026-06-01 --db ./usage-demo.sqlite3
```

`usage demo` は固定されたローカルのモック値を使います。OpenAI APIは呼び出しません。

## 入力値の検証

モデルは空のIDや名前を拒否します。力能と力能変化量は有限の数値である必要があります。`NaN`、正の無限大、負の無限大は `ValueError` になります。

## 情動定義カタログ

`affect` コマンドは、`P3-DA-01` から `P3-DA-48` までの 48 件の番号付き情動定義を扱います。

情動名は表示用メタデータであり、安定した識別子ではありません。正規IDには『エチカ』第三部と定義番号にもとづく `P3-DA-XX` 形式を使います。

各行には次の情報が含まれます。

- ラテン語名
- 英語表示名
- 日本語表示名
- 分類種別
- 時間スコープ
- 依存関係
- ルールID
- 出典情報
- 権利情報
- 日本語訳

長期的な傾向を表す情動は `longitudinal` スコープとして区別します。単一の出来事から人物の固定的な性格を断定するための分類ではありません。

日本語の文言は、このプロジェクトで作成した訳文です。現代日本語訳からの転載ではありません。

48情動ルールエンジンは、OpenAIまたはMock解析器が返した観察特徴を入力として、全48定義を決定論的に評価します。保存と通常表示では、1つのEpisodeに対して代表情動を1件だけ選びます。根拠が足りないEpisodeは `未分類` として残し、48情動のどれかへ強制的には割り当てません。`affect validate` はカタログだけでなく、この48件すべてのルールが実行可能であることも検証します。

## OpenAI API usage と概算料金

OpenAI APIの利用料金は、ChatGPTのサブスクリプションとは別に扱われます。このプロジェクトでは、APIレスポンスの usage 情報から次を保存・表示できます。

- 入力トークン
- キャッシュ入力トークン
- 非キャッシュ入力トークン
- 出力トークン
- reasoning tokens
- 合計トークン

料金は `Decimal` を使って次の式で計算します。

```text
uncached_input_tokens / 1_000_000 * input_price_per_1m_usd
+ cached_input_tokens / 1_000_000 * cached_input_price_per_1m_usd
+ output_tokens / 1_000_000 * output_price_per_1m_usd
```

reasoning tokens は通常、出力トークンの内訳として扱われます。そのため、出力トークンへ追加して二重計上しません。

料金表ファイル:

```text
conatus_engine/data/model_pricing.json
```

料金表では、単価を10進文字列として保存します。あわせて、参照元、取得日、service tier、context band を保持します。未知のモデル名には似た名前の料金を推測適用せず、`unknown_model` として扱います。

usage の保存にはSQLiteを使います。保存先は `CONATUS_DB_PATH` または `--db` で指定できます。データベースはローカルに保存されます。

実際の請求額は OpenAI の請求画面または利用状況画面で確認してください。トークン以外の追加料金は、明示的にモデル化されていない限り、この概算には含まれません。

## インストール

Python `3.12` 以上が必要です。

```bash
uv sync --extra dev
```

## テスト

開発用依存関係を入れてテストを実行します。

```bash
pip install -e ".[dev]"
pytest
```

`uv` を使う場合:

```bash
uv run pytest
```

ヘッドレス環境でGUIテストを実行する場合:

```bash
set QT_QPA_PLATFORM=offscreen
uv run pytest
```

スクリーンショットを保存する場合は `screenshots/` 配下を使ってください。一時出力は `screenshots/tmp/` に置く想定です。

## プロジェクト構成

```text
conatus_engine/
  __init__.py
  __main__.py
  affect_catalog.py
  cli.py
  engine.py
  gui_app.py
  gui_services.py
  models.py
  pricing.py
  serialization.py
  usage_store.py
  ui/
    main_window.py
  data/
    model_pricing.json
tests/
  test_affect_catalog.py
  test_engine.py
  test_models.py
  test_pricing.py
  test_serialization.py
  test_usage_store.py
pyproject.toml
README.md
```
