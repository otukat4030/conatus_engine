"""Main desktop window for Conatus Engine."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, QSettings, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from matplotlib import font_manager, rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from conatus_engine.gui_services import (
    AnalysisResult,
    AnalysisService,
    DiaryService,
    ReportService,
    SettingsService,
    format_episode_detail,
)
from conatus_engine.usage_store import default_db_path


def configure_matplotlib_japanese_font() -> None:
    """Choose a Japanese-capable font when one is available."""

    available = {font.name for font in font_manager.fontManager.ttflist}
    candidates = [
        "Yu Gothic",
        "Yu Gothic UI",
        "Meiryo",
        "MS Gothic",
        "Noto Sans CJK JP",
        "IPAexGothic",
        "DejaVu Sans",
    ]
    selected = [font for font in candidates if font in available]
    rcParams["font.family"] = selected or candidates
    rcParams["axes.unicode_minus"] = False


configure_matplotlib_japanese_font()


class AnalysisThread(QThread):
    """Background thread for diary analysis."""

    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        entry_date,
        text: str,
        db_path: Path,
        model: str,
        analyzer_mode: str,
        api_key: str | None,
    ) -> None:
        super().__init__()
        self.entry_date = entry_date
        self.text = text
        self.db_path = db_path
        self.model = model
        self.analyzer_mode = analyzer_mode
        self.api_key = api_key

    def run(self) -> None:
        try:
            self.progress.emit("解析中...")
            result = AnalysisService(
                self.db_path,
                self.model,
                analyzer_mode=self.analyzer_mode,
                api_key=self.api_key,
            ).analyze(self.entry_date, self.text)
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(f"日記の解析に失敗しました: {exc}")


class ConnectionTestThread(QThread):
    """Background thread for OpenAI connection checks."""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, model: str, api_key: str | None) -> None:
        super().__init__()
        self.model = model
        self.api_key = api_key

    def run(self) -> None:
        try:
            result = SettingsService().test_openai_connection(
                model=self.model, api_key=self.api_key
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(f"接続確認に失敗しました: {type(exc).__name__}")


class TextDetailDialog(QDialog):
    """Resizable scrollable dialog for long diary details."""

    def __init__(self, title: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 700)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(view)
        layout.addWidget(buttons)
        self.setLayout(layout)


class DiaryTab(QWidget):
    """Diary input and result tab."""

    analysis_finished = Signal()
    status_message = Signal(str)

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self.settings = settings
        self.worker: AnalysisThread | None = None
        self.api_key_provider = lambda: None
        self._episode_detail_texts: dict[int, str] = {}

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(self.date_edit.date().currentDate())

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("今日あったことや、そのとき感じたことを書いてください。")
        self.text_edit.setMinimumHeight(180)
        self.char_count = QLabel("0 文字")
        self.save_button = QPushButton("日記を保存")
        self.analyze_button = QPushButton("保存して解析")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.usage_view = QTextEdit()
        self.usage_view.setReadOnly(True)
        self.episode_table = QTableWidget(0, 9)
        self.episode_table.setHorizontalHeaderLabels(
            ["episode_id", "要約", "increase", "decrease", "conatus", "代表情動", "基礎情動", "併存情動", "confidence"]
        )
        self.episode_table.setColumnHidden(0, True)
        self.episode_detail = QTextEdit()
        self.episode_detail.setReadOnly(True)

        form = QFormLayout()
        form.addRow("日付", self.date_edit)
        form.addRow("日記", self.text_edit)
        form.addRow("", self.char_count)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.analyze_button)
        buttons.addWidget(self.progress)
        form.addRow("", buttons)

        right = QVBoxLayout()
        right.addWidget(QLabel("解析結果"))
        right.addWidget(self.result_view, 2)
        right.addWidget(QLabel("API使用量と概算料金"))
        right.addWidget(self.usage_view, 1)
        right.addWidget(QLabel("Episode一覧"))
        right.addWidget(self.episode_table, 2)
        right.addWidget(QLabel("選択Episode詳細"))
        right.addWidget(self.episode_detail, 3)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(form)
        right_widget = QWidget()
        right_widget.setLayout(right)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        self.text_edit.textChanged.connect(self._update_char_count)
        self.save_button.clicked.connect(self.save_diary)
        self.analyze_button.clicked.connect(self.analyze_diary)
        self.episode_table.itemSelectionChanged.connect(self._episode_selected)

    def _db_path(self) -> Path:
        return Path(self.settings.value("db_path", str(default_db_path())))

    def _model(self) -> str:
        return str(self.settings.value("model", "gpt-5.4-mini"))

    def _analyzer_mode(self) -> str:
        return str(self.settings.value("analyzer_mode", "mock"))

    def _entry_date(self):
        return self.date_edit.date().toPython()

    def _update_char_count(self) -> None:
        self.char_count.setText(f"{len(self.text_edit.toPlainText())} 文字")

    def _validate_text(self) -> str | None:
        text = self.text_edit.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "入力エラー", "日記本文を入力してください。")
            return None
        return text

    def save_diary(self) -> None:
        text = self._validate_text()
        if text is None:
            return
        try:
            diary = DiaryService(self._db_path()).save_diary(self._entry_date(), text)
            self.status_message.emit(f"日記を保存しました: ID {diary.id}")
        except Exception as exc:
            QMessageBox.critical(self, "保存エラー", str(exc))
            self.status_message.emit("エラーが発生しました")

    def analyze_diary(self) -> None:
        text = self._validate_text()
        if text is None:
            return
        self.analyze_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.progress.show()
        self.status_message.emit("解析中")
        self.worker = AnalysisThread(
            self._entry_date(),
            text,
            self._db_path(),
            self._model(),
            self._analyzer_mode(),
            self.api_key_provider(),
        )
        self.worker.progress.connect(self.status_message.emit)
        self.worker.succeeded.connect(self._analysis_succeeded)
        self.worker.failed.connect(self._analysis_failed)
        self.worker.finished.connect(self._analysis_finished)
        self.worker.start()

    def _analysis_succeeded(self, result: AnalysisResult) -> None:
        self.result_view.setPlainText(result.summary_text)
        self.usage_view.setPlainText(result.usage_text)
        self.episode_table.setRowCount(0)
        self.episode_detail.clear()
        self._episode_detail_texts = {}
        primary_by_episode: dict[int, list[str]] = {}
        base_by_episode: dict[int, list[str]] = {}
        coexisting_by_episode: dict[int, list[str]] = {}
        affect_records_by_episode = {}
        for affect in result.affects:
            affect_records_by_episode.setdefault(affect.episode_id, []).append(affect)
            if affect.role in {"primary", "unclassified"}:
                primary_by_episode.setdefault(affect.episode_id, []).append(
                    f"{affect.japanese_name}({affect.status})"
                )
            elif affect.role == "base":
                base_by_episode.setdefault(affect.episode_id, []).append(affect.japanese_name)
            elif affect.role == "coexisting":
                coexisting_by_episode.setdefault(affect.episode_id, []).append(affect.japanese_name)
        for index, episode in enumerate(result.episodes, start=1):
            row = self.episode_table.rowCount()
            self.episode_table.insertRow(row)
            values = [
                episode.id,
                episode.summary or f"Episode {index}",
                str(episode.increase_intensity),
                str(episode.decrease_intensity),
                str(episode.conatus_delta),
                ", ".join(primary_by_episode.get(episode.id, [])),
                ", ".join(base_by_episode.get(episode.id, [])) or "なし",
                ", ".join(coexisting_by_episode.get(episode.id, [])) or "なし",
                f"{episode.extraction_confidence:.2f}",
            ]
            for col, value in enumerate(values):
                self.episode_table.setItem(row, col, QTableWidgetItem(str(value)))
            self._episode_detail_texts[episode.id] = format_episode_detail(
                episode, affect_records_by_episode.get(episode.id, [])
            )
        self.episode_table.resizeColumnsToContents()
        self.episode_table.setColumnHidden(0, True)
        if result.episodes:
            self.episode_table.selectRow(0)
        self.status_message.emit("解析が完了しました")
        self.analysis_finished.emit()

    def _episode_selected(self) -> None:
        items = self.episode_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        episode_id = int(self.episode_table.item(row, 0).text())
        self.episode_detail.setPlainText(self._episode_detail_texts.get(episode_id, ""))

    def _analysis_failed(self, message: str) -> None:
        QMessageBox.critical(self, "解析エラー", message)
        self.status_message.emit("エラーが発生しました")

    def _analysis_finished(self) -> None:
        self.analyze_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.progress.hide()
        self.worker = None


class ChartCanvas(FigureCanvas):
    """Small Matplotlib canvas for embedded charts."""

    def __init__(self) -> None:
        self.figure = Figure(figsize=(5, 3))
        super().__init__(self.figure)

    def plot_bars(self, title: str, data: list[tuple[str, int]]) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        labels = [name for name, _ in data] or ["データなし"]
        values = [value for _, value in data] or [0]
        ax.barh(labels[:10], values[:10])
        ax.set_title(title)
        self.figure.tight_layout()
        self.draw()

    def plot_series(self, title: str, data: list[tuple[str, int]]) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        labels = [day for day, _ in data]
        values = [value for _, value in data]
        ax.plot(labels, values, marker="o")
        ax.set_title(title)
        ax.tick_params(axis="x", labelrotation=30)
        self.figure.tight_layout()
        self.draw()


class LogTab(QWidget):
    """Emotion log and report tab."""

    status_message = Signal(str)

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self.settings = settings
        self.period = QComboBox()
        self.period.addItems(["今日", "過去7日", "今月", "過去30日", "今年", "カスタム"])
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        today = QDate.currentDate()
        self.start_date.setDate(today)
        self.end_date.setDate(today)
        self.affect_filter = QComboBox()
        self.affect_filter.addItem("すべて")
        self.refresh_button = QPushButton("更新")
        self.detail_button = QPushButton("詳細を開く")
        self.delete_button = QPushButton("選択した日記を削除")
        self.summary = QLabel("データを読み込んでください。")
        self.affect_chart = ChartCanvas()
        self.conatus_chart = ChartCanvas()
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["diary_id", "日付", "Episode数", "Episode概要", "conatus", "主要情動", "API概算料金"])
        self.table.setColumnHidden(0, True)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("期間"))
        controls.addWidget(self.period)
        controls.addWidget(QLabel("開始日"))
        controls.addWidget(self.start_date)
        controls.addWidget(QLabel("終了日"))
        controls.addWidget(self.end_date)
        controls.addWidget(QLabel("情動"))
        controls.addWidget(self.affect_filter)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.detail_button)
        controls.addWidget(self.delete_button)

        charts = QSplitter(Qt.Orientation.Horizontal)
        charts.addWidget(self.affect_chart)
        charts.addWidget(self.conatus_chart)

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.summary)
        layout.addWidget(charts, 2)
        layout.addWidget(self.table, 2)
        layout.addWidget(QLabel("詳細"))
        layout.addWidget(self.detail, 1)
        self.setLayout(layout)

        self.refresh_button.clicked.connect(self.reload)
        self.period.currentTextChanged.connect(self._apply_period_preset)
        self.affect_filter.currentTextChanged.connect(self.reload)
        self.detail_button.clicked.connect(self.open_detail)
        self.delete_button.clicked.connect(self.delete_selected_diary)
        self.table.itemSelectionChanged.connect(self._row_selected)
        self._apply_period_preset(self.period.currentText())

    def _db_path(self) -> Path:
        return Path(self.settings.value("db_path", str(default_db_path())))

    def reload(self, *_args) -> None:
        service = ReportService(self._db_path())
        current_affect = self.affect_filter.currentText() or "すべて"
        affect_name = None if current_affect == "すべて" else current_affect
        data = service.summary(
            self.start_date.date().toPython(),
            self.end_date.date().toPython(),
            affect_name,
        )
        affect_names = data["affect_names"]
        if affect_name and affect_name not in affect_names:
            current_affect = "すべて"
            affect_name = None
            data = service.summary(
                self.start_date.date().toPython(),
                self.end_date.date().toPython(),
                affect_name,
            )
            affect_names = data["affect_names"]
        self._set_affect_filter_options(affect_names, current_affect)
        filter_text = ""
        if affect_name:
            filter_text = f" / 情動フィルタ: {affect_name} / 表示日記数: {data['visible_diary_count']}"
        self.summary.setText(
            f"日記数: {data['diary_count']} / Episode数: {data['episode_count']} / "
            f"conatus合計: {data['conatus_sum']} / API解析回数: {data['api_runs']} / "
            f"API概算料金合計: {data['api_cost']} / 料金推定不能: {data['pricing_unavailable']}"
            f"{filter_text}"
        )
        self.affect_chart.plot_bars("情動別件数", data["affects"])
        self.conatus_chart.plot_series("コナトゥス時系列", data["series"])
        rows = data["rows"]
        self.table.setRowCount(0)
        self.detail.clear()
        for row_data in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                row_data.diary_id,
                row_data.entry_date,
                row_data.episode_count,
                row_data.summary,
                row_data.conatus_delta,
                row_data.affects,
                row_data.api_cost,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        self.table.setColumnHidden(0, True)
        if rows:
            self.table.selectRow(0)
        self.status_message.emit("情動ログを更新しました")

    def _set_affect_filter_options(self, affect_names: list[str], current: str) -> None:
        self.affect_filter.blockSignals(True)
        self.affect_filter.clear()
        self.affect_filter.addItem("すべて")
        self.affect_filter.addItems(affect_names)
        self.affect_filter.setCurrentText(current if current in affect_names else "すべて")
        self.affect_filter.blockSignals(False)

    def _apply_period_preset(self, value: str) -> None:
        today = QDate.currentDate()
        if value == "今日":
            start = today
        elif value == "過去7日":
            start = today.addDays(-6)
        elif value == "今月":
            start = QDate(today.year(), today.month(), 1)
        elif value == "過去30日":
            start = today.addDays(-29)
        elif value == "今年":
            start = QDate(today.year(), 1, 1)
        else:
            return
        self.start_date.setDate(start)
        self.end_date.setDate(today)

    def _row_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        diary_id = int(self.table.item(row, 0).text())
        current_affect = self.affect_filter.currentText() or "すべて"
        affect_name = None if current_affect == "すべて" else current_affect
        self.detail.setPlainText(ReportService(self._db_path()).detail(diary_id, affect_name))

    def open_detail(self) -> None:
        text = self.detail.toPlainText()
        if not text.strip():
            self._row_selected()
            text = self.detail.toPlainText()
        TextDetailDialog("日記ログ詳細", text or "行を選択してください。", self).exec()

    def delete_selected_diary(self) -> None:
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "削除", "削除する日記ログを選択してください。")
            return
        row = items[0].row()
        diary_id = int(self.table.item(row, 0).text())
        reply = QMessageBox.question(
            self,
            "削除確認",
            f"日記ID {diary_id} と関連するEpisode・情動・usageを削除しますか？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ReportService(self._db_path()).delete_diary(diary_id)
        self.detail.clear()
        self.reload()
        self.status_message.emit("日記ログを削除しました")


class SettingsTab(QWidget):
    """Settings tab."""

    status_message = Signal(str)

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self.settings = settings
        self.service = SettingsService()
        self.connection_worker: ConnectionTestThread | None = None
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_key = QCheckBox("表示")
        self.save_key = QCheckBox("OS keyringへ保存")
        self.delete_key = QPushButton("削除")
        self.key_status = QLabel("APIキーは画面やログへ表示しません。")
        self.analyzer_mode = QComboBox()
        self.analyzer_mode.addItems(["mock", "openai"])
        self.analyzer_mode.setCurrentText(str(settings.value("analyzer_mode", "mock")))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItems(self.service.available_models())
        current_model = str(settings.value("model", "gpt-5.4-mini"))
        if current_model not in self.service.available_models():
            self.model.addItem(current_model)
        self.model.setCurrentText(current_model)
        self.db_path = QLineEdit(str(settings.value("db_path", str(default_db_path()))))
        self.pick_db = QPushButton("選択")
        self.usd_jpy = QLineEdit(str(settings.value("usd_jpy_rate", "")))
        self.monthly_budget = QLineEdit(str(settings.value("monthly_budget_usd", "")))
        self.pricing_info = QTextEdit()
        self.pricing_info.setReadOnly(True)
        self.save_button = QPushButton("設定を保存")
        self.connection_button = QPushButton("接続確認")

        form = QFormLayout()
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key)
        key_row.addWidget(self.show_key)
        key_row.addWidget(self.save_key)
        key_row.addWidget(self.delete_key)
        form.addRow("OpenAI APIキー", key_row)
        form.addRow("", self.key_status)
        form.addRow("解析モード", self.analyzer_mode)
        form.addRow("使用モデル", self.model)
        db_row = QHBoxLayout()
        db_row.addWidget(self.db_path)
        db_row.addWidget(self.pick_db)
        form.addRow("データベースパス", db_row)
        form.addRow("USD/JPY換算レート", self.usd_jpy)
        form.addRow("月間API予算USD", self.monthly_budget)
        form.addRow("料金表情報", self.pricing_info)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.connection_button)
        form.addRow("", buttons)
        self.setLayout(form)

        self.show_key.toggled.connect(self._toggle_key)
        self.pick_db.clicked.connect(self._pick_db)
        self.save_button.clicked.connect(self.save_settings)
        self.connection_button.clicked.connect(self.connection_test)
        self.model.currentTextChanged.connect(self.reload_pricing)
        self.reload_pricing()

    def _toggle_key(self, checked: bool) -> None:
        self.api_key.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _pick_db(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "SQLiteデータベースを選択", self.db_path.text(), "SQLite (*.sqlite3 *.db);;All files (*)")
        if path:
            self.db_path.setText(path)

    def reload_pricing(self) -> None:
        self.pricing_info.setPlainText(self.service.pricing_info(self._model_text()))

    def save_settings(self) -> None:
        self.settings.setValue("model", self._model_text())
        self.settings.setValue("analyzer_mode", self.analyzer_mode.currentText())
        self.settings.setValue("db_path", self.db_path.text().strip())
        self.settings.setValue("usd_jpy_rate", self.usd_jpy.text().strip())
        self.settings.setValue("monthly_budget_usd", self.monthly_budget.text().strip())
        if self.save_key.isChecked() and self.api_key.text().strip():
            ok, message = self.service.save_api_key_to_keyring(self.api_key.text())
            self.key_status.setText(message)
            if not ok:
                QMessageBox.warning(self, "keyring保存", message)
        self.status_message.emit("設定を保存しました")
        self.reload_pricing()

    def current_api_key(self) -> str | None:
        return self.service.resolve_api_key(self.api_key.text())

    def connection_test(self) -> None:
        reply = QMessageBox.question(
            self,
            "接続確認",
            "OpenAI APIへ接続確認を行います。少額の利用料金が発生する場合があります。続行しますか？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.connection_button.setEnabled(False)
        self.status_message.emit("接続確認中")
        self.connection_worker = ConnectionTestThread(
            self._model_text(), self.current_api_key()
        )
        self.connection_worker.succeeded.connect(self._connection_succeeded)
        self.connection_worker.failed.connect(self._connection_failed)
        self.connection_worker.finished.connect(self._connection_finished)
        self.connection_worker.start()

    def _model_text(self) -> str:
        return self.model.currentText().strip() or "gpt-5.4-mini"

    def _connection_succeeded(self, message: str) -> None:
        QMessageBox.information(self, "接続確認", message)
        self.status_message.emit("準備完了")

    def _connection_failed(self, message: str) -> None:
        QMessageBox.critical(self, "接続確認", message)
        self.status_message.emit("エラーが発生しました")

    def _connection_finished(self) -> None:
        self.connection_button.setEnabled(True)
        self.connection_worker = None


class MainWindow(QMainWindow):
    """Main window containing diary, log, and settings tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "ConatusEngine",
            "ConatusEngine",
        )
        self.setWindowTitle("Conatus Engine")
        self.resize(1200, 800)
        self.tabs = QTabWidget()
        self.diary_tab = DiaryTab(self.settings)
        self.log_tab = LogTab(self.settings)
        self.settings_tab = SettingsTab(self.settings)
        self.diary_tab.api_key_provider = self.settings_tab.current_api_key
        self.tabs.addTab(self.diary_tab, "日記")
        self.tabs.addTab(self.log_tab, "情動ログ")
        self.tabs.addTab(self.settings_tab, "設定")
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("準備完了")

        self.diary_tab.status_message.connect(self.statusBar().showMessage)
        self.log_tab.status_message.connect(self.statusBar().showMessage)
        self.settings_tab.status_message.connect(self.statusBar().showMessage)
        self.diary_tab.analysis_finished.connect(self.log_tab.reload)

    def closeEvent(self, event) -> None:
        worker = self.diary_tab.worker
        if worker and worker.isRunning():
            worker.requestInterruption()
            worker.quit()
            worker.wait(2000)
        super().closeEvent(event)
