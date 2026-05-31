"""Arduino protocol constants."""

from __future__ import annotations

from enum import StrEnum


class ArduinoCommand(StrEnum):
    """Commands supported by the Arduino firmware."""

    TEMP = "TEMP"
    GSR = "GSR"
    BPM = "BPM"
    ALL = "ALL"
    STOP = "STOP"


SUPPORTED_COMMANDS = {command.value for command in ArduinoCommand}

