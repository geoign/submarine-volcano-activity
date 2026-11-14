"""Writing files into a folder that a cloud drive synchronises.

While the drive's client holds a file, opening it for writing fails for a moment with OSError
(errno 22 on Windows). The tools write through these helpers, which try again for a few seconds.
"""

from __future__ import annotations

import csv
import io
import shutil
import time
from pathlib import Path

ATTEMPTS = 10
WAIT = 1.0


def _retry(action):
    for attempt in range(ATTEMPTS):
        try:
            return action()
        except OSError:
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(WAIT)


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with LF line ends."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _retry(lambda: path.write_text(text, encoding="utf-8", newline="\n"))


def write_csv(path: Path, columns: list[str], rows) -> int:
    """Write rows (dicts) as CSV; a missing or None value becomes an empty cell. Returns the row count."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    n = 0
    for r in rows:
        writer.writerow(["" if r.get(c) is None else r.get(c) for c in columns])
        n += 1
    write_text(path, buffer.getvalue())
    return n


def copy(src: Path, dst: Path) -> None:
    _retry(lambda: shutil.copy2(src, dst))
