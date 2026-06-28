import os
import sqlite3
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
    assert "Mock抽出結果" in window.diary_tab.episode_detail.toPlainText()
    assert "Engine計算結果" in window.diary_tab.episode_detail.toPlainText()
    assert "情動判定結果" in window.diary_tab.episode_detail.toPlainText()
    assert "生JSON" in window.diary_tab.episode_detail.toPlainText()
    assert '"summary": "今日は仕事で成功してうれしかった。"' in window.diary_tab.episode_detail.toPlainText()
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


def test_report_graph_data_counts_multiple_affect_roles_and_rows_per_diary(tmp_path) -> None:
    db_path = tmp_path / "primary.sqlite3"
    AnalysisService(db_path).analyze_with_mock(
        date(2026, 6, 28),
        "成功してうれしかった。夕方は不安で悲しかった。",
    )

    data = ReportService(db_path).summary()

    assert ("喜び", 1) in data["affects"]
    assert ("悲しみ", 1) in data["affects"]
    assert ("自己満足", 1) in data["affects"]
    assert len(data["rows"]) == 1
    assert data["rows"][0].episode_count == 2


def test_analysis_saves_multiple_affects_with_roles(tmp_path) -> None:
    db_path = tmp_path / "roles.sqlite3"
    result = AnalysisService(db_path).analyze_with_mock(
        date(2026, 6, 28),
        "友人に助けてもらい感謝してうれしかった。",
    )

    roles = {(affect.japanese_name, affect.role) for affect in result.affects}

    assert ("感謝", "primary") in roles
    assert ("喜び", "base") in roles
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT japanese_name, role FROM affect_assignments ORDER BY role, japanese_name"
        ).fetchall()
    assert ("感謝", "primary") in rows
    assert ("喜び", "base") in rows


def test_old_affect_assignment_schema_is_rejected(tmp_path) -> None:
    db_path = tmp_path / "old.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE affect_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER NOT NULL,
                affect_id TEXT NOT NULL,
                japanese_name TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                confidence REAL NOT NULL,
                UNIQUE(episode_id, affect_id, status)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO affect_assignments(
                episode_id, affect_id, japanese_name, status, reason, confidence
            ) VALUES (1, 'P3-DA-02', '喜び', 'matched', 'old', 0.8)
            """
        )

    with pytest.raises(RuntimeError, match="互換性がありません"):
        AnalysisService(db_path)


def test_report_detail_includes_all_affects_and_features_json(tmp_path) -> None:
    db_path = tmp_path / "detail.sqlite3"
    result = AnalysisService(db_path).analyze_with_mock(
        date(2026, 6, 28),
        "友人に助けてもらい感謝してうれしかった。",
    )

    detail = ReportService(db_path).detail(result.diary.id)

    assert "Mock抽出結果" in detail
    assert "Engine計算結果" in detail
    assert "情動判定結果" in detail
    assert "代表情動:" in detail
    assert "基礎情動:" in detail
    assert "role=primary" in detail
    assert "role=base" in detail
    assert "生JSON" in detail
    assert '"summary": "友人に助けてもらい感謝してうれしかった。"' in detail


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
    assert "成功してうれしかった" in episode_detail


def test_diary_episode_detail_distinguishes_roles_and_raw_json(qtbot, tmp_path) -> None:
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)
    window.settings.setValue("db_path", str(tmp_path / "detail-gui.sqlite3"))
    window.diary_tab.text_edit.setPlainText("友人に助けてもらい感謝してうれしかった。")

    window.diary_tab.analyze_diary()
    qtbot.waitUntil(lambda: window.diary_tab.worker is None, timeout=5000)

    detail = window.diary_tab.episode_detail.toPlainText()

    assert "Mock抽出結果" in detail
    assert "Engine計算結果" in detail
    assert "情動判定結果" in detail
    assert "代表情動:" in detail
    assert "基礎情動:" in detail
    assert "併存情動:" in detail
    assert "確認候補:" in detail
    assert "role=primary" in detail
    assert "role=base" in detail
    assert "role=coexisting" in detail
    assert "RuleTrace" in detail
    assert "生JSON" in detail
    assert '"summary": "友人に助けてもらい感謝してうれしかった。"' in detail


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
