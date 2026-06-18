from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.models import SensorSample
from app.storage import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_persists_and_exports_complete_sample(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database_path = root / "samples.sqlite3"
            store = SessionStore(database_path)
            sample = SensorSample(
                timestamp=datetime(2026, 6, 18, 12, 0, 0),
                temperature=36.5,
                bioscore=50.0,
                status="NORMAL",
            )

            store.append(sample)
            reloaded = SessionStore(database_path)
            csv_path = reloaded.export_csv(root / "samples.csv")

            self.assertEqual(len(reloaded.samples), 1)
            self.assertEqual(reloaded.samples[0].temperature, 36.5)
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["bioscore"], "50.0")
            self.assertEqual(rows[0]["status"], "NORMAL")

    def test_ignores_corrupted_timestamp_row(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "samples.sqlite3"
            SessionStore(database_path)
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    "INSERT INTO samples (timestamp, status) VALUES (?, ?)",
                    ("not-a-timestamp", "NORMAL"),
                )
                connection.commit()
            finally:
                connection.close()

            reloaded = SessionStore(database_path)

            self.assertEqual(reloaded.samples, [])


if __name__ == "__main__":
    unittest.main()
