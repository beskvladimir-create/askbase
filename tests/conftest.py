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


@pytest.fixture(scope="session")
def frozen_holdout_2(tmp_path_factory):
    """Set 2, regenerated from its own recorded seed and date.

    A separate fixture rather than a parameter on the first one, because the
    two sets are two pre-registrations: set 1's failures have been read and
    every arm on it is a development number, while set 2 has never been run.
    Mixing them in one fixture is one refactor away from mixing them in one
    reported figure.

    Skipped where set 2 has no tasks. The public export empties the `TASKS_2`
    block of every domain module, because set 2 is live and publishing its
    wordings would hand them to the next model measured on it. Every set-2
    test depends on this fixture, so one skip here keeps the public CI green
    without weakening a single assertion in the private repository, where the
    tasks are present and the tests run in full. The skip is on the data being
    absent by design, never on an assertion failing.
    """
    import subprocess
    import sys
    from pathlib import Path

    from nl2sql_app.holdout import verify
    from nl2sql_app.holdout.generate import DOMAINS as _DOMAINS

    if not any(d.tasks_2 for d in _DOMAINS.values()):
        pytest.skip("набор 2 не публикуется: в этой копии его задач нет")

    root = Path(__file__).resolve().parent.parent
    out = tmp_path_factory.mktemp("holdout2")
    meta = verify.expected(2)
    for name in sorted(meta["domains"]):
        r = subprocess.run(
            [sys.executable, "-m", "nl2sql_app.holdout.generate",
             "--domain", name, "--seed", str(meta["seed"]),
             "--now", meta["now"], "--out", str(out), "--set", "2"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0, f"{name}: {r.stderr}"
    return out
