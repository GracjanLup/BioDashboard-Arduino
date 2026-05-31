"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme


def main(argv: list[str] | None = None) -> int:
    """Start the BioMonitor Dashboard desktop application."""

    app = QApplication(argv or sys.argv)
    app.setApplicationName("BioMonitor Dashboard")
    app.setOrganizationName("BioMonitor")
    apply_theme(app)

    window = MainWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
