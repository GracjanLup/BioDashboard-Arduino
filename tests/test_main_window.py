from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.serial.parser import parse_serial_message
from app.serial.arduino_serial import ArduinoSerialWorker
from app.serial.protocol import ArduinoCommand
from app.settings import AppSettings, SettingsManager
from app.ui.main_window import BIOMONITOR_VIEW, MainWindow


class FakeSerialWorker:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def isRunning(self) -> bool:
        return True

    def send_command(self, command: str) -> bool:
        self.commands.append(command)
        return True


class MainWindowTests(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        instance = QApplication.instance()
        cls.app = instance if isinstance(instance, QApplication) else QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        manager = SettingsManager(root / "settings.json")
        manager.save(AppSettings(data_folder=root / "data"))
        self.window = MainWindow(settings_manager=manager)

    def tearDown(self) -> None:
        self.window.close()
        self.temp_dir.cleanup()

    def test_biomonitor_hides_test_controls(self) -> None:
        self.window._select_live_mode(BIOMONITOR_VIEW)

        self.assertTrue(self.window.controls_panel.isHidden())
        self.assertTrue(self.window.test_guide_panel.isHidden())
        self.assertEqual(self.window.metrics_title.text(), "Latest Results")

    def test_measurement_view_shows_complete_protocol(self) -> None:
        self.window._select_live_mode(ArduinoCommand.TEMP.value)

        self.assertFalse(self.window.controls_panel.isHidden())
        self.assertFalse(self.window.test_guide_panel.isHidden())
        self.assertIsNotNone(self.window.expected_serial_label.parent())
        self.assertIsNotNone(self.window.last_serial_label.parent())
        self.assertFalse(self.window.stop_button.isEnabled())
        self.assertEqual(self.window.metrics_grid.columnStretch(0), 1)
        for column in range(1, 5):
            self.assertEqual(self.window.metrics_grid.columnStretch(column), 0)

    def test_temperature_test_saves_one_final_result(self) -> None:
        worker = FakeSerialWorker()
        self.window.serial_worker = cast(ArduinoSerialWorker, worker)
        self.window._select_live_mode(ArduinoCommand.TEMP.value)

        self.window._start_measurement()
        first = parse_serial_message("TEMP:36.4")
        second = parse_serial_message("TEMP:36.6")
        assert first is not None
        assert second is not None
        self.window._on_sample_received(first, "TEMP:36.4")
        self.window._on_sample_received(second, "TEMP:36.6")
        self.window._finish_individual_test(stopped_by_user=False)
        self.window.serial_worker = None

        samples = self.window.session_store.samples
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].temperature, 36.5)
        self.assertEqual(worker.commands, ["TEMP", "STOP"])


if __name__ == "__main__":
    unittest.main()
