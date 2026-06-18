from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def default_data_folder() -> Path:
    return Path.home() / "Documents" / "BioMonitorDashboard"


@dataclass(slots=True)
class AppSettings:
    com_port: str = ""
    theme: str = "Medical Dark"
    data_folder: Path = field(default_factory=default_data_folder)

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["data_folder"] = str(self.data_folder)
        return payload

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "AppSettings":
        defaults = cls()
        data_folder = str(payload.get("data_folder", defaults.data_folder)).strip()
        return cls(
            com_port=str(payload.get("com_port", defaults.com_port)).strip(),
            theme=str(payload.get("theme", defaults.theme)),
            data_folder=Path(data_folder) if data_folder else defaults.data_folder,
        )
