from __future__ import annotations

import unittest

from app.measurements import (
    final_test_value,
    gsr_assessment_label,
    invalid_measurement_reason,
    measurement_spec,
    numeric_value_from_raw_line,
    spo2_status,
)
from app.serial.parser import ParsedMessage
from app.serial.protocol import ArduinoCommand


class MeasurementTests(unittest.TestCase):
    def test_protocol_durations(self) -> None:
        temperature = measurement_spec(ArduinoCommand.TEMP.value)
        gsr = measurement_spec(ArduinoCommand.GSR.value)
        bpm = measurement_spec(ArduinoCommand.BPM.value)
        assert temperature is not None
        assert gsr is not None
        assert bpm is not None

        self.assertEqual(temperature.duration_seconds, 60)
        self.assertEqual(gsr.duration_seconds, 30)
        self.assertEqual(bpm.duration_seconds, 30)

    def test_final_value_uses_last_ten_samples(self) -> None:
        values = [0.0, 100.0, *[10.0] * 10]

        self.assertEqual(final_test_value(values), 10.0)

    def test_final_value_rejects_empty_input(self) -> None:
        with self.assertRaises(ValueError):
            final_test_value([])

    def test_numeric_fallback_does_not_accept_unvalidated_bpm(self) -> None:
        self.assertIsNone(numeric_value_from_raw_line("72", ArduinoCommand.BPM.value))

    def test_invalid_pulse_reason_is_actionable(self) -> None:
        parsed = ParsedMessage(pulse_valid=False)

        reason = invalid_measurement_reason(parsed, ArduinoCommand.BPM.value)

        assert reason is not None
        self.assertIn("fingertip", reason)

    def test_gsr_and_spo2_statuses(self) -> None:
        self.assertEqual(gsr_assessment_label(200), "LOW")
        self.assertEqual(gsr_assessment_label(500), "IN RANGE")
        self.assertEqual(gsr_assessment_label(800), "ELEVATED")
        self.assertEqual(spo2_status(98, False), "INVALID")


if __name__ == "__main__":
    unittest.main()
