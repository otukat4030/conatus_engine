import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QSettings, Qt
from PySide6.QtWidgets import QLineEdit, QMessageBox

from conatus_engine.gui_services import AnalysisService, ReportService
from conatus_engine.ui.main_window import MainWindow


def test_main_window_has_three_tabs_and_diary_first(qtbot, tmp_path) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Conatus Engine"
    assert window.tabs.count() == 3
    assert window.tabs.tabText(0) == "日記"
    assert window.tabs.tabText(1) == "情動ログ"
    assert window.tabs.tabText(2) == "設定"
    assert window.tabs.currentIndex() == 0


def test_diary_empty_text_cannot_start_analysis(qtbot, tmp_path, monkeypatch) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "conatus_engine.ui.main_window.QMessageBox.warning",
        lambda *args, **kwargs: None,
    )

    window.diary_tab.analyze_diary()

    assert window.diary_tab.worker is None
    assert window.diary_tab.analyze_button.isEnabled()


def test_mock_analysis_updates_results_and_log(qtbot, tmp_path) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)
    window.settings.setValue("db_path", str(tmp_path / "gui.sqlite3"))
    window.diary_tab.text_edit.setPlainText("今日は仕事で成功してうれしかった。希望もある。")

    window.diary_tab.analyze_diary()
    qtbot.waitUntil(lambda: window.diary_tab.worker is None, timeout=5000)

    assert "今日のコナトゥス変化" in window.diary_tab.result_view.toPlainText()
    assert "API使用量" in window.diary_tab.usage_view.toPlainText()
    assert window.diary_tab.episode_table.rowCount() == 2
    assert "日記数:" in window.log_tab.summary.text()
    assert window.log_tab.table.rowCount() == 1
    window.log_tab.table.selectRow(0)
    assert "元の日記" in window.log_tab.detail.toPlainText()
    assert "Episode一覧" in window.log_tab.detail.toPlainText()


def test_log_delete_removes_selected_diary(qtbot, tmp_path, monkeypatch) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)
    window.settings.setValue("db_path", str(tmp_path / "delete.sqlite3"))
    window.diary_tab.text_edit.setPlainText("今日は成功してうれしかった。")
    window.diary_tab.analyze_diary()
    qtbot.waitUntil(lambda: window.diary_tab.worker is None, timeout=5000)
    window.log_tab.table.selectRow(0)
    monkeypatch.setattr(
        "conatus_engine.ui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window.log_tab.delete_selected_diary()

    assert window.log_tab.table.rowCount() == 0
    assert "日記数: 0" in window.log_tab.summary.text()


def test_log_date_filter_limits_rows_and_counts(qtbot, tmp_path) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    db_path = tmp_path / "dates.sqlite3"
    AnalysisService(db_path).analyze_with_mock(date(2026, 6, 1), "成功してうれしかった")
    AnalysisService(db_path).analyze_with_mock(date(2026, 6, 28), "成功してうれしかった")
    window = MainWindow()
    qtbot.addWidget(window)
    window.settings.setValue("db_path", str(db_path))
    window.log_tab.period.setCurrentText("カスタム")
    window.log_tab.start_date.setDate(QDate(2026, 6, 28))
    window.log_tab.end_date.setDate(QDate(2026, 6, 28))

    window.log_tab.reload()

    assert window.log_tab.table.rowCount() == 1
    assert "日記数: 1" in window.log_tab.summary.text()


def test_report_graph_data_counts_one_affect_per_episode_and_rows_per_diary(tmp_path) -> None:
    db_path = tmp_path / "primary.sqlite3"
    AnalysisService(db_path).analyze_with_mock(
        date(2026, 6, 28),
        "成功してうれしかった。夕方は不安で悲しかった。",
    )

    data = ReportService(db_path).summary()

    assert ("喜び", 1) in data["affects"]
    assert ("悲しみ", 1) in data["affects"]
    assert ("自己満足", 1) not in data["affects"]
    assert len(data["rows"]) == 1
    assert data["rows"][0].episode_count == 2


def test_log_affect_filter_shows_matching_episodes_and_dates(qtbot, tmp_path) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    db_path = tmp_path / "affect-filter.sqlite3"
    AnalysisService(db_path).analyze_with_mock(
        date(2026, 6, 28),
        "成功してうれしかった。夕方は不安で悲しかった。",
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window.settings.setValue("db_path", str(db_path))
    window.log_tab.period.setCurrentText("カスタム")
    window.log_tab.start_date.setDate(QDate(2026, 6, 28))
    window.log_tab.end_date.setDate(QDate(2026, 6, 28))

    window.log_tab.reload()
    window.log_tab.affect_filter.setCurrentText("悲しみ")

    assert window.log_tab.table.rowCount() == 1
    assert window.log_tab.table.item(0, 1).text() == "2026-06-28"
    assert window.log_tab.table.item(0, 4).text() == "-2"
    assert window.log_tab.table.item(0, 5).text() == "悲しみ"
    detail = window.log_tab.detail.toPlainText()
    episode_detail = detail.split("Episode一覧", maxsplit=1)[1]
    assert "夕方は不安で悲しかった" in episode_detail
    assert "成功してうれしかった" not in episode_detail


def test_settings_api_key_is_password_by_default_and_not_qsettings(qtbot, tmp_path) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.settings_tab.api_key.echoMode() == QLineEdit.EchoMode.Password
    window.settings_tab.api_key.setText("sk-secret")
    window.settings_tab.save_key.setChecked(False)
    qtbot.mouseClick(window.settings_tab.save_button, Qt.MouseButton.LeftButton)

    assert window.settings.value("openai_api_key") is None


def test_settings_model_is_combo_selection(qtbot, tmp_path) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.settings_tab.model.findText("gpt-5.4-mini") >= 0
    window.settings_tab.model.setCurrentText("gpt-5.4-nano")
    qtbot.mouseClick(window.settings_tab.save_button, Qt.MouseButton.LeftButton)

    assert window.settings.value("model") == "gpt-5.4-nano"
