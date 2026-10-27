"""The freeze, and the machinery that makes it more than a promise.

Three things can quietly undo a pre-registration, and there is a test here for
each. The recorded digests can stop matching what the generator produces. The
document and the machine-readable copy can drift apart, so that the file a
reader checks and the file the code checks say different things. And the
verifier can be lenient about exactly the cases it exists to catch.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nl2sql_app.holdout import verify
from nl2sql_app.holdout.generate import DOMAINS

ROOT = Path(__file__).resolve().parent.parent
DOC_EN = ROOT / "HOLDOUT.md"
DOC_RU = ROOT / "HOLDOUT.ru.md"


@pytest.fixture(scope="module")
def frozen(tmp_path_factory) -> Path:
    """Regenerate the whole set from the recorded seed and date."""
    out = tmp_path_factory.mktemp("holdout")
    meta = verify.expected()
    for name in sorted(meta["domains"]):
        r = subprocess.run(
            [sys.executable, "-m", "nl2sql_app.holdout.generate",
             "--domain", name, "--seed", str(meta["seed"]),
             "--now", meta["now"], "--out", str(out)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0, r.stderr
    return out


def test_the_recorded_command_reproduces_every_recorded_digest(frozen):
    # The whole freeze rests on this. If it ever fails, either the generator
    # changed or the digests did, and neither may happen silently.
    assert verify.check_set(frozen) == verify.expected()["domains"]


def test_the_document_and_the_machine_readable_copy_agree():
    # A digest a human checks in HOLDOUT.md and a digest the code checks in
    # DIGESTS.json have to be the same digest. Two sources of truth is one too
    # many, and the one that drifts is always the one nobody runs.
    digests = verify.expected()["domains"]
    for doc in (DOC_EN, DOC_RU):
        text = doc.read_text(encoding="utf-8")
        for name, digest in digests.items():
            assert digest in text, f"{doc.name}: нет хеша для {name}"
            assert name in text, f"{doc.name}: не упомянута область {name}"


def test_the_freeze_covers_every_domain_the_generator_knows():
    # A domain added to the generator and not to the freeze would be a domain
    # outside the pre-registration, available to be included after the fact.
    assert set(verify.expected()["domains"]) == set(DOMAINS)


def test_a_changed_set_is_refused(frozen, tmp_path):
    import shutil
    copy = tmp_path / "tampered"
    shutil.copytree(frozen, copy)
    target = copy / "hr" / "canonical.json"
    target.write_text(target.read_text(encoding="utf-8").replace("hr", "hr ", 1),
                      encoding="utf-8")
    with pytest.raises(verify.NotFrozen) as e:
        verify.check_set(copy)
    assert "hr" in str(e.value)


def test_a_missing_domain_is_refused_not_skipped(frozen, tmp_path):
    import shutil
    copy = tmp_path / "partial"
    shutil.copytree(frozen, copy)
    shutil.rmtree(copy / "medicine")
    # Running five of six and publishing the number is the quiet version of
    # choosing the sample after looking at it.
    with pytest.raises(verify.NotFrozen) as e:
        verify.check_set(copy)
    assert "medicine" in str(e.value)


def test_an_extra_domain_is_refused(frozen, tmp_path):
    import shutil
    copy = tmp_path / "extra"
    shutil.copytree(frozen, copy)
    (copy / "invented").mkdir()
    with pytest.raises(verify.NotFrozen) as e:
        verify.check_set(copy)
    assert "invented" in str(e.value)


def test_a_second_run_of_the_same_tool_needs_a_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    first = verify.record("xiyan-7b-q4", 1)
    assert first["repeat"] == 0

    with pytest.raises(verify.NotFrozen) as e:
        verify.record("xiyan-7b-q4", 1)
    assert "xiyan-7b-q4" in str(e.value)

    second = verify.record("xiyan-7b-q4", 1, reason="оценщик исправлен")
    assert second["repeat"] == 1
    assert second["reason"] == "оценщик исправлен"

    rows = [json.loads(ln) for ln in
            verify.JOURNAL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [r["repeat"] for r in rows] == [0, 1]
    # The reason stays in the journal: that is the only thing making a repeat
    # cost anything.
    assert rows[1]["reason"] == "оценщик исправлен"


def test_a_different_tool_on_the_same_set_is_not_a_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    verify.record("xiyan-7b-q4", 1)
    assert verify.record("arctic-7b-q4", 1)["repeat"] == 0


def test_every_run_records_the_commit_it_ran_from(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    row = verify.record("ours", 1)
    assert row["commit"] and row["commit"] != "unknown"
    assert row["at"].startswith("20")


def test_the_document_states_what_the_set_cannot_decide():
    # The power statement is load-bearing: without it a reader takes an
    # undetermined verdict for a weak result rather than for the expected one.
    en = DOC_EN.read_text(encoding="utf-8")
    ru = DOC_RU.read_text(encoding="utf-8")
    assert "undetermined" in en and "не определено" in ru
    assert "48" in en and "48" in ru
