"""Keep a test run out of the real user's settings and journal.

Both are genuine files in the user's own Library folder, and the Qt suite
constructs Window about twenty times and calls _open on throwaway databases. A
review found the consequence in the author's own preferences: three pytest
temp-directory paths in the recent list and a timeout of infinity, left behind
by tests. The journal already had ASKBASE_JOURNAL; the settings store had
nothing, so it got ASKBASE_SETTINGS to match.

autouse and session-wide on purpose. An opt-in fixture is one a new test
forgets, and the cost of forgetting is somebody's real preferences.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_user_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ASKBASE_SETTINGS", str(tmp_path / "askbase-prefs.ini"))
    monkeypatch.setenv("ASKBASE_JOURNAL", str(tmp_path / "askbase-journal.jsonl"))
