"""Application settings data model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def default_data_folder() -> Path:
    """Return the default folder for user-created recordings and reports."""

    return Path.home() / "Documents" / "BioMonitorDashboard"


@dataclass(slots=True)
class AppSettings:
    """User-configurable settings persisted between application sessions."""

    com_port: str = ""
    baud_rate: int = 115200
    sampling_interval_ms: int = 1000
    theme: str = "Medical Dark"
    chart_history_seconds: int = 300
    data_folder: Path = field(default_factory=default_data_folder)

    def to_json(self) -> dict[str, Any]:
        """Serialize settings to JSON-compatible values."""

        payload = asdict(self)
        payload["data_folder"] = str(self.data_folder)
        return payload

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "AppSettings":
        """Create settings from a JSON object, using defaults for missing keys."""

        defaults = cls()
        return cls(
            com_port=str(payload.get("com_port", defaults.com_port)),
            baud_rate=int(payload.get("baud_rate", defaults.baud_rate)),
            sampling_interval_ms=int(
                payload.get("sampling_interval_ms", defaults.sampling_interval_ms)
            ),
            theme=str(payload.get("theme", defaults.theme)),
            chart_history_seconds=int(
                payload.get("chart_history_seconds", defaults.chart_history_seconds)
            ),
            data_folder=Path(str(payload.get("data_folder", defaults.data_folder))),
        )
