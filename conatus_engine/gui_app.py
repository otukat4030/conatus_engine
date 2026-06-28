"""Desktop GUI entry point for Conatus Engine."""

from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> None:
    """Run the PySide6 desktop application."""

    argv = argv if argv is not None else sys.argv[1:]
    if "--demo" in argv or "--mock" in argv:
        os.environ.setdefault("CONATUS_GUI_MOCK", "1")
    from PySide6.QtWidgets import QApplication

    from conatus_engine.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow()
    window.show()
    if "--quit-after-start" in argv:
        app.processEvents()
        window.close()
        return
    raise SystemExit(app.exec())
