"""Export path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExportPaths:
    """Default export paths for one dashboard session."""

    csv: Path
    report: Path


def timestamped_path(folder: Path, prefix: str, suffix: str) -> Path:
    """Return a timestamped file path and ensure its folder exists."""

    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return folder / f"{prefix}_{stamp}{suffix}"

