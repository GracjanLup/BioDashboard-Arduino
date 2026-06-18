from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


STATUS_RELAX = "RELAX"
STATUS_NORMAL = "NORMAL"
STATUS_AROUSED = "AROUSED"


@dataclass(slots=True)
class BaselineValues:
    temperature: float | None = None
    heart_rate: float | None = None
    gsr: float | None = None
    calibrated_at: datetime | None = None


@dataclass(slots=True)
class SensorSample:
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
    temperature: float | None = None
    heart_rate: float | None = None
    gsr: float | None = None
