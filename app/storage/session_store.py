from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.models import SensorSample


CSV_COLUMNS = [
    "timestamp",
    "temperature",
    "heart_rate",
    "spo2",
    "pulse_valid",
    "pulse_temperature",
    "gsr",
    "bioscore",
    "status",
]


class SessionStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
        self._samples = self._load_samples()

    @property
    def samples(self) -> list[SensorSample]:
        return list(self._samples)

    def append(self, sample: SensorSample) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO samples (
                    timestamp,
                    temperature,
                    heart_rate,
                    spo2,
                    pulse_valid,
                    pulse_temperature,
                    gsr,
                    bioscore,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample.timestamp.isoformat(timespec="milliseconds"),
                    sample.temperature,
                    sample.heart_rate,
                    sample.spo2,
                    _bool_to_int(sample.pulse_valid),
                    sample.pulse_temperature,
                    sample.gsr,
                    sample.bioscore,
                    sample.status,
                ),
            )
        self._samples.append(sample)

    def export_csv(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(sample.to_record() for sample in self._samples)
        return path

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    temperature REAL,
                    heart_rate REAL,
                    spo2 REAL,
                    pulse_valid INTEGER,
                    pulse_temperature REAL,
                    gsr REAL,
                    bioscore REAL,
                    status TEXT NOT NULL
                )
                """
            )

    def _load_samples(self) -> list[SensorSample]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    timestamp,
                    temperature,
                    heart_rate,
                    spo2,
                    pulse_valid,
                    pulse_temperature,
                    gsr,
                    bioscore,
                    status
                FROM samples
                ORDER BY id
                """
            ).fetchall()

        samples = []
        for row in rows:
            try:
                sample = SensorSample(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    temperature=row["temperature"],
                    heart_rate=row["heart_rate"],
                    spo2=row["spo2"],
                    pulse_valid=_int_to_bool(row["pulse_valid"]),
                    pulse_temperature=row["pulse_temperature"],
                    gsr=row["gsr"],
                    bioscore=row["bioscore"],
                    status=row["status"],
                )
            except (TypeError, ValueError):
                continue
            samples.append(sample)
        return samples

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _int_to_bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)
