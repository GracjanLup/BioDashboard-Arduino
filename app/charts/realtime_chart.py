"""Real-time pyqtgraph chart widget."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QFrame, QVBoxLayout

from app.ui.theme import COLOR_ACCENT, COLOR_BORDER, COLOR_MUTED, COLOR_PANEL, COLOR_TEXT

pg.setConfigOptions(antialias=True)


class RealtimeChartWidget(QFrame):
    """Scrolling line chart that keeps a configurable recent history window."""

    def __init__(
        self,
        title: str,
        unit: str,
        color: str = COLOR_ACCENT,
        history_seconds: int = 300,
        y_range: tuple[float, float] | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("PanelCard")
        self.title = title
        self.unit = unit
        self.history_seconds = history_seconds
        self.y_range = y_range
        self._x_values: list[float] = []
        self._y_values: list[float] = []

        axis = pg.DateAxisItem(orientation="bottom")
        self.plot_widget = pg.PlotWidget(axisItems={"bottom": axis})
        self.plot_widget.setBackground(COLOR_PANEL)
        self.plot_widget.setTitle(title, color=COLOR_TEXT, size="11pt")
        self.plot_widget.setLabel("left", unit, color=COLOR_MUTED)
        self.plot_widget.setLabel("bottom", "Time", color=COLOR_MUTED)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.22)
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.PanMode)
        self.plot_widget.getPlotItem().getAxis("left").setPen(COLOR_BORDER)
        self.plot_widget.getPlotItem().getAxis("bottom").setPen(COLOR_BORDER)
        self.plot_widget.getPlotItem().getAxis("left").setTextPen(COLOR_MUTED)
        self.plot_widget.getPlotItem().getAxis("bottom").setTextPen(COLOR_MUTED)

        pen = pg.mkPen(color=color, width=2)
        self.curve = self.plot_widget.plot([], [], pen=pen)
        if self.y_range is not None:
            self.plot_widget.setYRange(self.y_range[0], self.y_range[1], padding=0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.plot_widget)

    def set_history_seconds(self, seconds: int) -> None:
        """Update the visible history length."""

        self.history_seconds = max(30, int(seconds))
        self._trim_history()
        self._redraw()

    def add_sample(self, timestamp: datetime, value: float | None) -> None:
        """Append a value and refresh the chart."""

        if value is None:
            return

        self._x_values.append(timestamp.timestamp())
        self._y_values.append(float(value))
        self._trim_history()
        self._redraw()

    def clear(self) -> None:
        """Remove all plotted data."""

        self._x_values.clear()
        self._y_values.clear()
        self.curve.setData([], [])
        if self.y_range is not None:
            self.plot_widget.setYRange(self.y_range[0], self.y_range[1], padding=0)

    def _trim_history(self) -> None:
        if not self._x_values:
            return

        cutoff = self._x_values[-1] - self.history_seconds
        first_index = 0
        for index, value in enumerate(self._x_values):
            if value >= cutoff:
                first_index = index
                break
        else:
            first_index = len(self._x_values)

        if first_index:
            del self._x_values[:first_index]
            del self._y_values[:first_index]

    def _redraw(self) -> None:
        self.curve.setData(self._x_values, self._y_values)
        if not self._x_values:
            return

        latest = self._x_values[-1]
        self.plot_widget.setXRange(latest - self.history_seconds, latest, padding=0.01)
        if self.y_range is None:
            self.plot_widget.getViewBox().enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        else:
            self.plot_widget.setYRange(self.y_range[0], self.y_range[1], padding=0)
