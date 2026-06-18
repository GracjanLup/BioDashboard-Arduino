from __future__ import annotations

from dataclasses import dataclass

from app.models import (
    STATUS_AROUSED,
    STATUS_NORMAL,
    STATUS_RELAX,
    BaselineValues,
    SensorDeltas,
    SensorSample,
)


@dataclass(slots=True)
class BioScoreWeights:
    temperature: float = 15.0
    heart_rate: float = 25.0
    gsr: float = 35.0


class BioScoreCalculator:
    def __init__(self, baseline: BaselineValues | None = None) -> None:
        self.baseline = baseline or BaselineValues()
        self.weights = BioScoreWeights()

    def set_baseline(self, baseline: BaselineValues) -> None:
        self.baseline = baseline

    def calculate_deltas(self, sample: SensorSample) -> SensorDeltas:
        return SensorDeltas(
            temperature=_delta(sample.temperature, self.baseline.temperature),
            heart_rate=_delta(sample.heart_rate, self.baseline.heart_rate),
            gsr=_delta(sample.gsr, self.baseline.gsr),
        )

    def calculate_score(self, sample: SensorSample) -> float:
        if not self.has_baseline:
            return 50.0

        deltas = self.calculate_deltas(sample)
        score = 50.0
        score += _normalized(deltas.temperature, scale=1.0) * self.weights.temperature
        score += _normalized(deltas.heart_rate, scale=35.0) * self.weights.heart_rate
        score += _normalized(deltas.gsr, scale=250.0) * self.weights.gsr
        return _clamp(score, 0.0, 100.0)

    @property
    def has_baseline(self) -> bool:
        return (
            self.baseline.temperature is not None
            or self.baseline.heart_rate is not None
            or self.baseline.gsr is not None
        )


def status_for_score(score: float) -> str:
    if score <= 35:
        return STATUS_RELAX
    if score <= 65:
        return STATUS_NORMAL
    return STATUS_AROUSED


def _delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None:
        return None
    return value - baseline


def _normalized(delta: float | None, scale: float) -> float:
    if delta is None:
        return 0.0
    return _clamp(delta / scale, -1.0, 1.0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))
