"""Qt serial worker for Arduino communication."""

from __future__ import annotations

from threading import Lock

from PySide6.QtCore import QThread, Signal

from app.serial.parser import has_supported_field, parse_serial_message
from app.serial.protocol import SUPPORTED_COMMANDS

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - exercised only without pyserial installed.
    serial = None  # type: ignore[assignment]
    list_ports = None  # type: ignore[assignment]


def available_ports() -> list[str]:
    """Return currently visible serial ports."""

    if list_ports is None:
        return []
    return [port.device for port in list_ports.comports()]


class ArduinoSerialWorker(QThread):
    """Background serial reader that emits parsed Arduino samples."""

    connected = Signal(str)
    disconnected = Signal()
    raw_received = Signal(str)
    sample_received = Signal(object, str)
    error = Signal(str)

    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 1.0) -> None:
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._serial = None
        self._running = False
        self._lock = Lock()

    def run(self) -> None:
        """Open the serial port and continuously read line-based messages."""

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
            try:
                raw_bytes = self._serial.readline()
            except serial.SerialException as exc:
                self.error.emit(f"Serial read error: {exc}")
                break

            if not raw_bytes:
                continue

            line = raw_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            self.raw_received.emit(line)
            parsed = parse_serial_message(line)
            if parsed is not None:
                self.sample_received.emit(parsed, line)
            elif has_supported_field(line):
                self.error.emit(f"Ignored malformed serial message: {line}")

        self._close_serial()
        self.disconnected.emit()

    def stop(self) -> None:
        """Ask the serial loop to stop and close the port."""

        self._running = False
        self._close_serial()

    def send_command(self, command: str) -> bool:
        """Send an Arduino command. Returns false when sending is not possible."""

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
