from __future__ import annotations

from dataclasses import dataclass

from app.models import STATUS_AROUSED, STATUS_NORMAL, STATUS_RELAX
from app.serial.parser import ParsedMessage
from app.serial.protocol import ArduinoCommand


GSR_BASELINE_TOLERANCE = 100.0
GSR_RAW_LOW_THRESHOLD = 300.0
GSR_RAW_HIGH_THRESHOLD = 700.0


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    command: str
    page_title: str
    test_title: str
    duration_seconds: int
    expected_serial: str
    instructions: str


MEASUREMENT_SPECS = {
    ArduinoCommand.TEMP.value: MeasurementSpec(
        command=ArduinoCommand.TEMP.value,
        page_title="Temperature Monitor",
        test_title="Temperature Test",
        duration_seconds=60,
        expected_serial="TEMP:36.2",
        instructions=(
            "1. Connect Arduino and make sure the connection status is CONNECTED.\n"
            "2. For best results, place the thermometer under the armpit, close to the skin.\n"
            "3. Press your arm against your torso and keep the sensor still for the whole test.\n"
            "4. Click Start Test.\n"
            "5. Wait 60 seconds until the progress bar completes."
        ),
    ),
    ArduinoCommand.BPM.value: MeasurementSpec(
        command=ArduinoCommand.BPM.value,
        page_title="Heart Rate Monitor",
        test_title="Heart Rate Test",
        duration_seconds=30,
        expected_serial="BPM:74,SPO2:97,PULSE_VALID:1,PULSE_TEMP:31.50",
        instructions=(
            "1. Place your fingertip on the heart-rate sensor.\n"
            "2. Do not press your finger too hard.\n"
            "3. Do not move your finger during the measurement.\n"
            "4. Breathe calmly and do not talk during the test.\n"
            "5. Click Start Test and wait 30 seconds."
        ),
    ),
    ArduinoCommand.GSR.value: MeasurementSpec(
        command=ArduinoCommand.GSR.value,
        page_title="GSR Monitor",
        test_title="GSR Test",
        duration_seconds=30,
        expected_serial="GSR:542",
        instructions=(
            "1. Place the electrodes on the same fingers before each measurement.\n"
            "2. Do not squeeze the electrodes too hard.\n"
            "3. Sit calmly and limit hand movement.\n"
            "4. Click Start Test.\n"
            "5. Keep your hand in the same position for 30 seconds until the progress bar completes."
        ),
    ),
}


def measurement_spec(command: str) -> MeasurementSpec | None:
    return MEASUREMENT_SPECS.get(command)


def is_measurement_command(command: str) -> bool:
    return command in MEASUREMENT_SPECS


def value_for_command(parsed: ParsedMessage, command: str) -> float | None:
    if command == ArduinoCommand.TEMP.value:
        return parsed.temperature
    if command == ArduinoCommand.GSR.value:
        return parsed.gsr
    if command == ArduinoCommand.BPM.value:
        return parsed.heart_rate
    return None


def final_test_value(values: list[float]) -> float:
    if not values:
        raise ValueError("At least one measurement value is required.")
    stable_values = values[-10:]
    return sum(stable_values) / len(stable_values)


def format_test_value(command: str, value: float) -> str:
    if command == ArduinoCommand.TEMP.value:
        return f"{value:.1f} \N{DEGREE SIGN}C"
    if command == ArduinoCommand.GSR.value:
        return format_gsr_result(value)
    if command == ArduinoCommand.BPM.value:
        return f"{value:.0f} BPM"
    return f"{value:.2f}"


def numeric_value_from_raw_line(line: str, command: str) -> float | None:
    cleaned = line.strip().replace(",", ".")
    if ":" in cleaned:
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if command == ArduinoCommand.TEMP.value and -50.0 <= value <= 150.0:
        return value
    if command == ArduinoCommand.GSR.value and 0.0 <= value <= 1023.0:
        return value
    return None


def line_matches_command(line: str, command: str) -> bool:
    normalized = line.strip().upper()
    if command == ArduinoCommand.TEMP.value:
        return normalized.startswith("TEMP:")
    if command == ArduinoCommand.GSR.value:
        return normalized.startswith("GSR:")
    if command == ArduinoCommand.BPM.value:
        return normalized.startswith("BPM:")
    return False


def measurement_name(command: str) -> str:
    spec = measurement_spec(command)
    if spec is None:
        return "Measurement"
    if command == ArduinoCommand.BPM.value:
        return "Heart rate / SpO2 test"
    return spec.test_title


def invalid_measurement_reason(parsed: ParsedMessage, command: str) -> str | None:
    if command == ArduinoCommand.TEMP.value:
        if parsed.temperature is not None and parsed.temperature <= -100.0:
            return (
                "the DS18B20 returned its disconnected-sensor value. Check the sensor wiring "
                "and skin contact, then repeat the measurement."
            )
        return None

    if command != ArduinoCommand.BPM.value:
        return None

    if parsed.pulse_valid is False:
        return (
            "the MAX30102 reported insufficient pulse signal (PULSE_VALID:0). Keep the "
            "fingertip still, avoid excessive pressure, and fully cover the sensor."
        )
    if parsed.pulse_valid is True and parsed.heart_rate is None:
        return (
            "the pulse signal was marked valid, but no plausible heart-rate value was "
            "received. Reposition the fingertip and repeat the measurement."
        )
    if parsed.pulse_valid is True and parsed.spo2 is None:
        return (
            "the pulse signal was detected, but no plausible SpO2 value was received. "
            "Keep the fingertip still and repeat the measurement."
        )
    return None


def format_gsr_result(value: float | None) -> str:
    value_text = "--" if value is None else str(int(round(value)))
    return f"{value_text} ADC, assessment: {gsr_assessment_text(value)}"


def gsr_assessment_label(value: float | None, delta: float | None = None) -> str:
    if value is None:
        return "NO DATA"
    if delta is not None:
        if delta < -GSR_BASELINE_TOLERANCE:
            return "LOW"
        if delta <= GSR_BASELINE_TOLERANCE:
            return "IN RANGE"
        return "ELEVATED"
    if value < GSR_RAW_LOW_THRESHOLD:
        return "LOW"
    if value <= GSR_RAW_HIGH_THRESHOLD:
        return "IN RANGE"
    return "ELEVATED"


def gsr_assessment_text(value: float | None, delta: float | None = None) -> str:
    return gsr_assessment_label(value, delta).lower()


def gsr_assessment_detail(value: float | None, delta: float | None = None) -> str:
    label = gsr_assessment_text(value, delta)
    if value is None:
        return "Assessment: no data"
    if delta is None:
        return f"Assessment: {label}"
    sign = "+" if delta >= 0 else ""
    return f"Assessment: {label} ({sign}{delta:.0f} vs baseline)"


def temperature_status(value: float | None) -> str:
    if value is None:
        return "WAITING"
    if value <= -100.0:
        return "INVALID"
    if 35.5 <= value <= 37.5:
        return STATUS_NORMAL
    if value < 35.5:
        return STATUS_RELAX
    return STATUS_AROUSED


def heart_status(value: float | None) -> str:
    if value is None:
        return "WAITING"
    if value < 55:
        return STATUS_RELAX
    if value <= 100:
        return STATUS_NORMAL
    return STATUS_AROUSED


def spo2_status(value: float | None, pulse_valid: bool | None) -> str:
    if pulse_valid is False:
        return "INVALID"
    if value is None:
        return "WAITING"
    if value >= 95:
        return STATUS_NORMAL
    if value >= 90:
        return STATUS_RELAX
    return STATUS_AROUSED
