from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.ui.theme import color_for_status


class StatusIndicator(QWidget):
    def __init__(self, text: str = "OFFLINE", color: str | None = None) -> None:
        super().__init__()
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        self.label = QLabel(text)
        self.label.setObjectName("MutedLabel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        self.set_status(text, color or color_for_status(text))

    def set_status(self, text: str, color: str | None = None) -> None:
        resolved_color = color or color_for_status(text)
        self.label.setText(text)
        self.dot.setStyleSheet(
            f"background: {resolved_color}; border-radius: 5px; "
            "border: 1px solid rgba(255,255,255,0.18);"
        )
