"""Baseline calibration helpers."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from app.models import BaselineValues, SensorSample


class BaselineAccumulator:
    """Collect samples and calculate average baseline sensor values."""

    def __init__(self) -> None:
        self._samples: list[SensorSample] = []

    def reset(self) -> None:
        """Discard any previously collected calibration samples."""

        self._samples.clear()

    def add_sample(self, sample: SensorSample) -> None:
        """Add a sample to the calibration set."""

        self._samples.append(sample)

    @property
    def sample_count(self) -> int:
        """Return the number of collected calibration samples."""

        return len(self._samples)

    def calculate(self) -> BaselineValues:
        """Calculate baseline averages while ignoring missing values."""

        return BaselineValues(
            temperature=_nanmean([sample.temperature for sample in self._samples]),
            heart_rate=_nanmean([sample.heart_rate for sample in self._samples]),
            gsr=_nanmean([sample.gsr for sample in self._samples]),
            calibrated_at=datetime.now(),
        )


def _nanmean(values: list[float | None]) -> float | None:
    numeric = np.array([value for value in values if value is not None], dtype=float)
    if numeric.size == 0:
        return None
    return float(np.mean(numeric))

