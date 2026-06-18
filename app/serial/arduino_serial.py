from __future__ import annotations

from threading import Lock

from PySide6.QtCore import QObject, QThread, Signal

from app.serial.parser import (
    has_supported_field,
    parse_serial_message,
    validation_error_for_line,
)
from app.serial.protocol import SERIAL_BAUD_RATE, SUPPORTED_COMMANDS

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - exercised only without pyserial installed.
    serial = None  # type: ignore[assignment]
    list_ports = None  # type: ignore[assignment]


def available_ports() -> list[str]:
    if list_ports is None:
        return []
    return [port.device for port in list_ports.comports()]


class ArduinoSerialWorker(QThread):
    connected = Signal(str)
    disconnected = Signal()
    raw_received = Signal(str)
    sample_received = Signal(object, str)
    error = Signal(str)

    def __init__(
        self,
        port: str,
        baud_rate: int = SERIAL_BAUD_RATE,
        timeout: float = 1.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._serial = None
        self._running = False
        self._lock = Lock()
        self._last_validation_error: str | None = None

    def run(self) -> None:
        if serial is None:
            self.error.emit("pyserial is not installed.")
            self.disconnected.emit()
            return

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=1.0,
            )
        except serial.SerialException as exc:
            message = str(exc)
            if "PermissionError" in message or "Access is denied" in message:
                self.error.emit(
                    f"Could not open {self.port}: access denied. Close Arduino Serial Monitor, "
                    "other terminal programs, and any other BioMonitor window using this port."
                )
            else:
                self.error.emit(f"Could not open {self.port}: {exc}")
            self.disconnected.emit()
            return

        self._running = True
        self.connected.emit(self.port)

        while self._running:
            serial_port = self._serial
            if serial_port is None:
                break
            try:
                raw_bytes = serial_port.readline()
            except serial.SerialException as exc:
                if self._running:
                    self.error.emit(f"Serial read error: {exc}")
                break

            if not raw_bytes:
                continue

            line = raw_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            self.raw_received.emit(line)
            validation_error = validation_error_for_line(line)
            if validation_error is not None:
                if validation_error != self._last_validation_error:
                    self.error.emit(
                        f"Ignored invalid measurement field: {validation_error} Raw data: {line}"
                    )
                    self._last_validation_error = validation_error

            parsed = parse_serial_message(line)
            if parsed is not None:
                if validation_error is None:
                    self._last_validation_error = None
                self.sample_received.emit(parsed, line)
            elif has_supported_field(line) and validation_error is None:
                reason = "supported fields are malformed."
                if reason != self._last_validation_error:
                    self.error.emit(f"Ignored invalid measurement: {reason} Raw data: {line}")
                    self._last_validation_error = reason

        self._running = False
        self._close_serial()
        self.disconnected.emit()

    def stop(self) -> None:
        self._running = False
        self._close_serial()

    def send_command(self, command: str) -> bool:
        normalized = command.strip().upper()
        if normalized not in SUPPORTED_COMMANDS:
            self.error.emit(f"Unsupported Arduino command: {command}")
            return False

        with self._lock:
            if self._serial is None or not self._serial.is_open:
                self.error.emit("Serial port is not connected.")
                return False

            try:
                self._serial.write(f"{normalized}\n".encode("ascii"))
                self._serial.flush()
            except serial.SerialException as exc:
                self.error.emit(f"Serial write error: {exc}")
                return False
        return True

    def _close_serial(self) -> None:
        with self._lock:
            if self._serial is not None and self._serial.is_open:
                try:
                    self._serial.close()
                except serial.SerialException as exc:
                    self.error.emit(f"Serial close error: {exc}")
