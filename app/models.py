"""Shared data models used by the BioMonitor Dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


STATUS_RELAX = "RELAX"
STATUS_NORMAL = "NORMAL"
STATUS_AROUSED = "AROUSED"


@dataclass(slots=True)
class BaselineValues:
    """Average resting values used as the reference for deltas and BioScore."""

    temperature: float | None = None
    heart_rate: float | None = None
    gsr: float | None = None
    calibrated_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        """Return true when every supported sensor has a baseline value."""

        return self.temperature is not None and self.heart_rate is not None and self.gsr is not None


@dataclass(slots=True)
class SensorSample:
    """Single timestamped physiological sample stored for the current session."""

    timestamp: datetime
    temperature: float | None = None
    heart_rate: float | None = None
    spo2: float | None = None
    pulse_valid: bool | None = None
    pulse_temperature: float | None = None
    gsr: float | None = None
    bioscore: float | None = None
    status: str = STATUS_NORMAL

    def to_record(self) -> dict[str, Any]:
        """Convert the sample to a flat dictionary suitable for pandas export."""

        return {
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "temperature": self.temperature,
            "heart_rate": self.heart_rate,
            "spo2": self.spo2,
            "pulse_valid": self.pulse_valid,
            "pulse_temperature": self.pulse_temperature,
            "gsr": self.gsr,
            "bioscore": round(self.bioscore, 2) if self.bioscore is not None else None,
            "status": self.status,
        }


@dataclass(slots=True)
class SensorDeltas:
    """Differences between the current sample and calibrated baseline values."""

    temperature: float | None = None
    heart_rate: float | None = None
    gsr: float | None = None
