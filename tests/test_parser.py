from __future__ import annotations

import unittest

from app.serial.parser import parse_serial_message, validation_error_for_line


class ParserTests(unittest.TestCase):
    def test_parses_temperature(self) -> None:
        parsed = parse_serial_message("TEMP:36.25")

        assert parsed is not None
        self.assertEqual(parsed.temperature, 36.25)

    def test_invalid_pulse_flag_discards_heart_rate(self) -> None:
        parsed = parse_serial_message("BPM:0,SPO2:-1,PULSE_VALID:0,PULSE_TEMP:31.5")

        assert parsed is not None
        self.assertIsNone(parsed.heart_rate)
        self.assertIsNone(parsed.spo2)
        self.assertFalse(parsed.pulse_valid)

    def test_reports_disconnected_temperature_sensor(self) -> None:
        reason = validation_error_for_line("TEMP:-127.0")

        assert reason is not None
        self.assertIn("disconnected-sensor", reason)

    def test_reports_gsr_outside_adc_range(self) -> None:
        reason = validation_error_for_line("GSR:1500")

        self.assertEqual(reason, "GSR is outside the Arduino ADC range (0 to 1023).")


if __name__ == "__main__":
    unittest.main()
