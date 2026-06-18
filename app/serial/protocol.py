from __future__ import annotations

from enum import StrEnum


SERIAL_BAUD_RATE = 115200


class ArduinoCommand(StrEnum):
    TEMP = "TEMP"
    GSR = "GSR"
    BPM = "BPM"
    STOP = "STOP"


SUPPORTED_COMMANDS = frozenset(command.value for command in ArduinoCommand)
