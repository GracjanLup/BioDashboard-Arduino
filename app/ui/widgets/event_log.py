"""Event log widget."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit


class EventLog(QTextEdit):
    """Read-only log for connection, sensor, calibration, and user events."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EventLog")
        self.setReadOnly(True)
        self.setMinimumHeight(132)

    def append_event(self, message: str, category: str = "INFO") -> None:
        """Append a timestamped event line."""

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(f"[{timestamp}] {category.upper():<5} {message}\n")
        self.moveCursor(QTextCursor.End)
