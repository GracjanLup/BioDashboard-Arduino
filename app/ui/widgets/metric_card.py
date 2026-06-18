from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.ui.theme import color_for_status
from app.ui.widgets.status_indicator import StatusIndicator


class MetricCard(QFrame):
    def __init__(self, title: str, unit: str = "", initial_value: str = "--") -> None:
        super().__init__()
        self.setObjectName("MetricCard")
        self.setMinimumHeight(132)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")

        self.value_label = QLabel(initial_value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setMinimumWidth(82)

        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("MetricUnit")
        self.delta_label = QLabel("Baseline: --")
        self.delta_label.setObjectName("MutedLabel")
        self.status = StatusIndicator("WAITING")

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(6)
        value_row.addWidget(self.value_label)
        value_row.addWidget(
            self.unit_label,
            alignment=Qt.AlignmentFlag.AlignBottom,
        )
        value_row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addLayout(value_row)
        layout.addWidget(self.delta_label)
        layout.addStretch()
        layout.addWidget(self.status)

    def set_value(self, value: float | None, precision: int = 1) -> None:
        if value is None:
            self.value_label.setText("--")
            return

        if precision <= 0:
            self.value_label.setText(str(int(round(value))))
        else:
            self.value_label.setText(f"{value:.{precision}f}")

    def set_delta(self, delta: float | None, precision: int = 1) -> None:
        if delta is None:
            self.delta_label.setText("Baseline: --")
            return

        sign = "+" if delta >= 0 else ""
        self.delta_label.setText(f"Delta: {sign}{delta:.{precision}f}")

    def set_status(self, text: str) -> None:
        self.status.set_status(text, color_for_status(text))
