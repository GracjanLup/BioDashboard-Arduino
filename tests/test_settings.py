from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.settings import AppSettings, SettingsManager


class SettingsTests(unittest.TestCase):
    def test_legacy_keys_are_ignored(self) -> None:
        settings = AppSettings.from_json(
            {
                "com_port": "COM4",
                "baud_rate": 9600,
                "sampling_interval_ms": 250,
                "chart_history_seconds": 30,
                "data_folder": "C:/BioMonitor",
            }
        )

        self.assertEqual(settings.com_port, "COM4")
        self.assertFalse(hasattr(settings, "baud_rate"))
        self.assertFalse(hasattr(settings, "sampling_interval_ms"))
        self.assertFalse(hasattr(settings, "chart_history_seconds"))

    def test_manager_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            manager = SettingsManager(path)
            expected = AppSettings(
                com_port="COM7",
                theme="High Contrast Dark",
                data_folder=Path(folder) / "data",
            )

            manager.save(expected)
            actual = manager.load()

            self.assertEqual(actual, expected)
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
