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


@pytest.fixture(scope="session")
def frozen_holdout(tmp_path_factory):
    """The held-out set, regenerated from the recorded seed and date.

    Session-scoped and shared by the freeze tests and the stage tests, which
    both need the real set and neither of which may depend on `data/holdout`
    existing. It does not exist in the public export, so a test that reads it
    off disk passes here and skips on GitHub, and a check that only runs on one
    machine is the kind that stops being true without anyone noticing.

    Generating it is also the stronger test: it proves the published digests
    still come out of the committed generator.
    """
    import subprocess
    import sys
    from pathlib import Path

    from nl2sql_app.holdout import verify

    root = Path(__file__).resolve().parent.parent
    out = tmp_path_factory.mktemp("holdout")
    meta = verify.expected()
    for name in sorted(meta["domains"]):
        r = subprocess.run(
            [sys.executable, "-m", "nl2sql_app.holdout.generate",
             "--domain", name, "--seed", str(meta["seed"]),
             "--now", meta["now"], "--out", str(out)],
            cwd=root, capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0, f"{name}: {r.stderr}"
    return out
