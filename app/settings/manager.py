from __future__ import annotations

import json
import os
from pathlib import Path

from app.settings.model import AppSettings


class SettingsManager:
    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_path = settings_path or self._default_settings_path()

    def load(self) -> AppSettings:
        if not self.settings_path.exists():
            return AppSettings()

        try:
            with self.settings_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return AppSettings()
            return AppSettings.from_json(payload)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.settings_path.with_suffix(f"{self.settings_path.suffix}.tmp")
        try:
            with temporary_path.open("w", encoding="utf-8") as handle:
                json.dump(settings.to_json(), handle, indent=2)
                handle.write("\n")
            temporary_path.replace(self.settings_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _default_settings_path() -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "BioMonitorDashboard" / "settings.json"
        return Path.home() / ".biomonitor_dashboard" / "settings.json"
