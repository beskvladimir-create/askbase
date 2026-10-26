"""The databases opened before.

A file dropped once is wanted again tomorrow, and finding the same .sqlite in
Finder every morning is the whole reason a tool starts to feel like work. Only
paths are kept, never anything read out of the file.
"""
from __future__ import annotations

import os
from pathlib import Path

LIMIT = 5


def _settings():
    # Imported here, as in i18n: the module is plain data handling and the
    # tests that read it should not need a GUI toolkit installed.
    from PySide6.QtCore import QSettings

    # ASKBASE_SETTINGS redirects the store, the way ASKBASE_JOURNAL redirects
    # the journal. Without it the Qt suite wrote to the real preferences of
    # whoever ran it: a review found three pytest temp paths and a stray
    # timeout in the author's own plist, left there by tests that construct
    # Window about twenty times and call _open on throwaway files.
    override = os.environ.get("ASKBASE_SETTINGS")
    if override:
        return QSettings(override, QSettings.Format.IniFormat)
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
