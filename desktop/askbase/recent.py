"""The databases opened before.

A file dropped once is wanted again tomorrow, and finding the same .sqlite in
Finder every morning is the whole reason a tool starts to feel like work. Only
paths are kept, never anything read out of the file.
"""
from __future__ import annotations

from pathlib import Path

LIMIT = 5


def _settings():
    # Imported here, as in i18n: the module is plain data handling and the
    # tests that read it should not need a GUI toolkit installed.
    from PySide6.QtCore import QSettings

    return QSettings("Besk Tech", "Askbase")


def paths() -> list[str]:
    """Most recent first, and only the files that are still where they were."""
    saved = _settings().value("recent", []) or []
    if isinstance(saved, str):                  # a one-item list comes back as a bare string
        saved = [saved]
    return [p for p in saved if p and Path(p).is_file()][:LIMIT]


def remember(path: str) -> None:
    keep = [str(path)] + [p for p in paths() if p != str(path)]
    _settings().setValue("recent", keep[:LIMIT])


def forget(path: str) -> None:
    _settings().setValue("recent", [p for p in paths() if p != str(path)])
