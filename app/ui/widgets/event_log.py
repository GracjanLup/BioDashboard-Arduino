from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit


class EventLog(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EventLog")
        self.setReadOnly(True)
        self.setMinimumHeight(132)
        self.document().setMaximumBlockCount(1000)

    def append_event(self, message: str, category: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.insertPlainText(f"[{timestamp}] {category.upper():<5} {message}\n")
        self.moveCursor(QTextCursor.MoveOperation.End)
