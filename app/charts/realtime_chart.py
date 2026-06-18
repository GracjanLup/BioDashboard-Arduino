from __future__ import annotations

from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout

from app.ui.theme import COLOR_ACCENT, theme_palette

pg.setConfigOptions(antialias=True)


class RealtimeChartWidget(QFrame):
    def __init__(
        self,
        title: str,
        unit: str,
        color: str = COLOR_ACCENT,
        y_range: tuple[float, float] | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("PanelCard")
        self.title = title
        self.unit = unit
        self.y_range = y_range
        self._x_values: list[float] = []
        self._y_values: list[float] = []
        self._interaction_unlocked = False

        axis = pg.DateAxisItem(orientation="bottom")
        self.plot_widget = pg.PlotWidget(axisItems={"bottom": axis})
        self.plot_item = self.plot_widget.getPlotItem()
        self.view_box = self.plot_item.getViewBox()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.22)
        self.view_box.setMouseMode(pg.ViewBox.PanMode)

        pen = pg.mkPen(color=color, width=2)
        self.curve = self.plot_widget.plot([], [], pen=pen)
        if self.y_range is not None:
            self.plot_widget.setYRange(self.y_range[0], self.y_range[1], padding=0)

        self.curve.setZValue(1)
        self.points = pg.ScatterPlotItem(
            [],
            [],
            size=10,
            pen=pg.mkPen(color=theme_palette().text, width=1.2),
            brush=pg.mkBrush(color),
            pxMode=True,
        )
        self.points.setZValue(2)
        self.plot_item.addItem(self.points)

        self.lock_button = QToolButton(self.plot_widget)
        self.lock_button.setObjectName("ChartLockButton")
        self.lock_button.setAutoRaise(True)
        self.lock_button.setCheckable(True)
        self.lock_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_button.setFixedSize(30, 30)
        self.lock_button.setIconSize(QSize(17, 17))
        self.lock_button.clicked.connect(self._set_interaction_unlocked)
        self.apply_theme()
        self.plot_widget.installEventFilter(self)
        self._set_interaction_unlocked(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.plot_widget)
        QTimer.singleShot(0, self._position_lock_button)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        if watched is self.plot_widget and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            QTimer.singleShot(0, self._position_lock_button)
        return super().eventFilter(watched, event)

    def add_sample(self, timestamp: datetime, value: float | None) -> None:
        if value is None:
            return

        self._x_values.append(timestamp.timestamp())
        self._y_values.append(float(value))
        self._redraw()

    def clear(self) -> None:
        self._x_values.clear()
        self._y_values.clear()
        self.curve.setData([], [])
        self.points.setData([], [])
        if self.y_range is not None and not self._interaction_unlocked:
            self.plot_widget.setYRange(self.y_range[0], self.y_range[1], padding=0)

    def apply_theme(self) -> None:
        palette = theme_palette()
        self.plot_widget.setBackground(palette.panel)
        self.plot_widget.setTitle(self.title, color=palette.text, size="11pt")
        self.plot_widget.setLabel("left", self.unit, color=palette.muted)
        self.plot_widget.setLabel("bottom", "Time", color=palette.muted)
        self.plot_item.getAxis("left").setPen(palette.border)
        self.plot_item.getAxis("bottom").setPen(palette.border)
        self.plot_item.getAxis("left").setTextPen(palette.muted)
        self.plot_item.getAxis("bottom").setTextPen(palette.muted)
        self.points.setPen(pg.mkPen(color=palette.text, width=1.2))
        self._locked_icon = _lock_icon(
            locked=True,
            text_color=palette.text,
            muted_color=palette.muted,
        )
        self._unlocked_icon = _lock_icon(
            locked=False,
            text_color=palette.text,
            muted_color=palette.muted,
        )
        self._apply_lock_button_style()
        icon = self._unlocked_icon if self._interaction_unlocked else self._locked_icon
        self.lock_button.setIcon(icon)

    def _set_interaction_unlocked(self, unlocked: bool) -> None:
        self._interaction_unlocked = unlocked
        self.lock_button.setChecked(unlocked)
        self.lock_button.setIcon(self._unlocked_icon if unlocked else self._locked_icon)
        self.lock_button.setToolTip("Lock chart" if unlocked else "Unlock chart")
        self.lock_button.setAccessibleName("Chart unlocked" if unlocked else "Chart locked")

        self.plot_widget.setMouseEnabled(x=unlocked, y=unlocked)
        self.view_box.setMouseEnabled(x=unlocked, y=unlocked)
        self.view_box.setMenuEnabled(unlocked)
        self.plot_item.setMenuEnabled(unlocked)

        if unlocked:
            self.view_box.disableAutoRange(axis=pg.ViewBox.XAxis)
            self.view_box.disableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self._redraw()

        self._position_lock_button()

    def _apply_lock_button_style(self) -> None:
        palette = theme_palette()
        self.lock_button.setStyleSheet(
            f"""
            QToolButton#ChartLockButton {{
                background: {palette.input_background};
                border: 1px solid {palette.border};
                border-radius: 7px;
                padding: 4px;
            }}
            QToolButton#ChartLockButton:hover {{
                background: {palette.hover};
                border-color: {palette.hover_border};
            }}
            QToolButton#ChartLockButton:checked {{
                background: {palette.primary};
                border-color: {palette.primary_border};
            }}
            """
        )

    def _position_lock_button(self) -> None:
        margin = 10
        x = max(margin, self.plot_widget.width() - self.lock_button.width() - margin)
        self.lock_button.move(x, margin)
        self.lock_button.raise_()

    def _redraw(self) -> None:
        self.curve.setData(self._x_values, self._y_values)
        self.points.setData(self._x_values, self._y_values)
        if not self._x_values:
            return

        latest = self._x_values[-1]
        if self._interaction_unlocked:
            return

        first = self._x_values[0]
        if first == latest:
            half_window = 30.0
            self.plot_widget.setXRange(first - half_window, latest + half_window, padding=0)
        else:
            self.plot_widget.setXRange(first, latest, padding=0.04)

        minimum = min(self._y_values)
        maximum = max(self._y_values)
        if self.y_range is not None:
            minimum = min(minimum, self.y_range[0])
            maximum = max(maximum, self.y_range[1])

        if minimum == maximum:
            spread = max(1.0, abs(minimum) * 0.05)
            self.plot_widget.setYRange(minimum - spread, maximum + spread, padding=0)
        else:
            self.plot_widget.setYRange(minimum, maximum, padding=0.12)


def _lock_icon(*, locked: bool, text_color: str, muted_color: str) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    stroke = QColor(text_color if locked else muted_color)
    painter.setPen(
        QPen(
            stroke,
            1.8,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(stroke)
    painter.drawRoundedRect(4, 8, 10, 7, 1.8, 1.8)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    if locked:
        painter.drawArc(5, 2, 8, 10, 0, 180 * 16)
    else:
        painter.drawArc(8, 2, 8, 10, 20 * 16, 210 * 16)
        painter.drawLine(8, 7, 6, 7)

    painter.end()
    return QIcon(pixmap)
