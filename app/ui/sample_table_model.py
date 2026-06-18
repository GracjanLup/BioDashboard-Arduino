from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)

from app.measurements import gsr_assessment_label
from app.models import SensorSample


class SampleTableModel(QAbstractTableModel):
    HEADERS = [
        "Timestamp",
        "Temp \N{DEGREE SIGN}C",
        "BPM",
        "SpO2 %",
        "Pulse OK",
        "GSR",
        "GSR Assessment",
        "Status",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._samples: list[SensorSample] = []

    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        return 0 if parent.isValid() else len(self._samples)

    def columnCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),
    ) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ):
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.TextAlignmentRole,
        ):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        sample = self._samples[index.row()]
        values = (
            sample.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            _format_number(sample.temperature, 1),
            _format_number(sample.heart_rate, 0),
            _format_number(sample.spo2, 0),
            _format_bool(sample.pulse_valid),
            _format_number(sample.gsr, 0),
            gsr_assessment_label(sample.gsr),
            sample.status,
        )
        return values[index.column()]

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return self.HEADERS[section]

    def set_samples(self, samples: list[SensorSample]) -> None:
        self.beginResetModel()
        self._samples = samples
        self.endResetModel()


def _format_number(value: float | None, precision: int) -> str:
    if value is None:
        return "--"
    if precision <= 0:
        return str(int(round(value)))
    return f"{value:.{precision}f}"


def _format_bool(value: bool | None) -> str:
    if value is None:
        return "--"
    return "YES" if value else "NO"
