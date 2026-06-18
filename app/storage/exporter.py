from __future__ import annotations

from datetime import datetime
from pathlib import Path


def timestamped_path(folder: Path, prefix: str, suffix: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return folder / f"{prefix}_{stamp}{suffix}"
