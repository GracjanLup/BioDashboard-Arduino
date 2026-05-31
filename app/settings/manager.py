"""JSON-backed settings manager."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.settings.model import AppSettings


class SettingsManager:
    """Load and save dashboard settings in the user's profile."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_path = settings_path or self._default_settings_path()

    def load(self) -> AppSettings:
        """Load settings from disk. Invalid files fall back to defaults."""

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
        """Persist settings to disk."""

        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        with self.settings_path.open("w", encoding="utf-8") as handle:
            json.dump(settings.to_json(), handle, indent=2)

    @staticmethod
    def _default_settings_path() -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "BioMonitorDashboard" / "settings.json"
        return Path.home() / ".biomonitor_dashboard" / "settings.json"
