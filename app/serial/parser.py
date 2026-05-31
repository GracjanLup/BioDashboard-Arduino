"""Robust parser for Arduino sensor messages."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ParsedMessage:
    """Parsed values from a serial line.

    Any field can be ``None`` when the Arduino line did not include that sensor.
    """

    temperature: float | None = None
    heart_rate: float | None = None
    spo2: float | None = None
    pulse_valid: bool | None = None
    pulse_temperature: float | None = None
    gsr: float | None = None

    @property
    def has_values(self) -> bool:
        """Return true when at least one supported value was parsed."""

        return (
            self.temperature is not None
            or self.heart_rate is not None
            or self.spo2 is not None
            or self.pulse_valid is not None
            or self.pulse_temperature is not None
            or self.gsr is not None
        )


FIELD_MAP = {
    "TEMP": "temperature",
    "TEMPERATURE": "temperature",
    "BPM": "heart_rate",
    "HR": "heart_rate",
    "HEART_RATE": "heart_rate",
    "SPO2": "spo2",
    "PULSE_VALID": "pulse_valid",
    "PULSE_TEMP": "pulse_temperature",
    "GSR": "gsr",
}


def has_supported_field(line: str) -> bool:
    """Return true when a line contains at least one known sensor field name."""

    for token in line.strip().split(","):
        key, separator, _value = token.partition(":")
        if separator and key.strip().upper() in FIELD_MAP:
            return True
    return False


def parse_serial_message(line: str) -> ParsedMessage | None:
    """Parse Arduino messages such as ``TEMP:36.2`` or combined sample lines.

    Malformed tokens are ignored. The function returns ``None`` when the line has
    no valid supported fields.
    """

    cleaned = line.strip()
    if not cleaned:
        return None

    values: dict[str, float | bool] = {}
    for token in cleaned.split(","):
        key, separator, value = token.partition(":")
        if not separator:
            continue

        field_name = FIELD_MAP.get(key.strip().upper())
        if field_name is None:
            continue

        if field_name == "pulse_valid":
            parsed_value = _to_bool(value)
            if parsed_value is None:
                continue
            values[field_name] = parsed_value
            continue

        number = _to_float(value)
        if number is not None and _is_plausible(field_name, number):
            values[field_name] = number

    pulse_valid = _as_bool(values.get("pulse_valid"))
    heart_rate = _as_float(values.get("heart_rate"))
    if pulse_valid is False:
        heart_rate = None

    parsed = ParsedMessage(
        temperature=_as_float(values.get("temperature")),
        heart_rate=heart_rate,
        spo2=_as_float(values.get("spo2")),
        pulse_valid=pulse_valid,
        pulse_temperature=_as_float(values.get("pulse_temperature")),
        gsr=_as_float(values.get("gsr")),
    )
    return parsed if parsed.has_values else None


def _to_float(value: str) -> float | None:
    try:
        number = float(value.strip())
    except ValueError:
        return None

    if not isfinite(number):
        return None
    return number


def _to_bool(value: str) -> bool | None:
    normalized = value.strip().upper()
    if normalized in {"1", "TRUE", "YES", "VALID"}:
        return True
    if normalized in {"0", "FALSE", "NO", "INVALID"}:
        return False
    return None


def _is_plausible(field_name: str, value: float) -> bool:
    if field_name == "temperature":
        return -50.0 <= value <= 150.0
    if field_name == "heart_rate":
        return 20.0 <= value <= 240.0
    if field_name == "spo2":
        return 0.0 <= value <= 100.0
    if field_name == "gsr":
        return 0.0 <= value <= 1023.0
    return True


def _as_float(value: float | bool | None) -> float | None:
    return value if isinstance(value, float) else None


def _as_bool(value: float | bool | None) -> bool | None:
    return value if isinstance(value, bool) else None
