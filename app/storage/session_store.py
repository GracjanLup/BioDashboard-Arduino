"""Persistent session storage backed by SQLite and pandas exports."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.models import SensorSample


class SessionStore:
    """Store sensor samples and keep them available across application restarts."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
        self._samples = self._load_samples()

    @property
    def samples(self) -> list[SensorSample]:
        """Return a copy of the current session samples."""

        return list(self._samples)

    def append(self, sample: SensorSample) -> None:
        """Add a sample to memory and persist it on disk."""

        self._samples.append(sample)
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

    def clear(self) -> None:
        """Remove all stored session samples from memory and disk."""

        self._samples.clear()
        with self._connect() as connection:
            connection.execute("DELETE FROM samples")

    def to_dataframe(self) -> pd.DataFrame:
        """Return all samples as a pandas data frame with stable column order."""

        columns = [
            "timestamp",
            "temperature",
            "heart_rate",
            "spo2",
            "pulse_valid",
            "pulse_temperature",
            "gsr",
            "status",
        ]
        return pd.DataFrame([sample.to_record() for sample in self._samples], columns=columns)

    def export_csv(self, path: Path) -> Path:
        """Write the session to CSV and return the output path."""

        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe().to_csv(path, index=False)
        return path

    def export_report(self, path: Path) -> Path:
        """Write a compact HTML report for the session."""

        path.parent.mkdir(parents=True, exist_ok=True)
        frame = self.to_dataframe()
        numeric_columns = [
            "temperature",
            "heart_rate",
            "spo2",
            "pulse_temperature",
            "gsr",
        ]
        numeric = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
        summary = numeric.describe().round(2) if not frame.empty else pd.DataFrame()

        html = [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<title>BioMonitor Session Report</title>",
            _report_css(),
            "</head>",
            "<body>",
            "<main>",
            "<h1>BioMonitor Session Report</h1>",
            f"<p class=\"muted\">Samples recorded: {len(frame)}</p>",
            "<h2>Summary</h2>",
            summary.to_html(classes="data", border=0) if not summary.empty else "<p>No data.</p>",
            "<h2>Recent Samples</h2>",
            frame.tail(200).to_html(classes="data", border=0, index=False),
            "</main>",
            "</body>",
            "</html>",
        ]
        path.write_text("\n".join(html), encoding="utf-8")
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

        return [
            SensorSample(
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
            for row in rows
        ]

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


def _report_css() -> str:
    return """
<style>
body {
  background: #10151b;
  color: #d8e2ec;
  font-family: Inter, Segoe UI, Arial, sans-serif;
  margin: 0;
}
main {
  margin: 32px auto;
  max-width: 1120px;
  padding: 0 24px;
}
h1, h2 {
  color: #f2f7fb;
  font-weight: 650;
}
.muted {
  color: #8ea2b5;
}
.data {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0 32px;
}
.data th, .data td {
  border-bottom: 1px solid #263341;
  padding: 8px 10px;
  text-align: right;
}
.data th {
  color: #93c5fd;
  font-weight: 600;
}
</style>
"""
