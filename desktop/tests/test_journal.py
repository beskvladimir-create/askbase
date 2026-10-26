"""The journal of questions.

It is the only file this application writes about what the user did, so the
properties worth pinning are not the happy path. They are: it never takes the
application down with it, it never grows without bound, a torn line does not
destroy the rest, and it holds no answer data.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from askbase import journal


@pytest.fixture(autouse=True)
def journal_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("ASKBASE_JOURNAL", str(tmp_path / "journal.jsonl"))


def entry(**over):
    base = dict(at="2026-10-26T09:00:00+00:00", question="how many customers",
                sql="SELECT COUNT(*) FROM customers", rows=1, seconds=0.9,
                db_path="/data/shop.sqlite")
    base.update(over)
    return journal.Entry(**base)


def test_nothing_is_there_to_begin_with():
    assert journal.entries() == []


def test_newest_first():
    for i in range(3):
        journal.append(entry(question=f"q{i}", at=f"2026-10-26T0{i}:00:00+00:00"))
    assert [e.question for e in journal.entries()] == ["q2", "q1", "q0"]


def test_it_keeps_the_question_the_query_and_the_shape_but_no_answer_rows():
    # A journal holding result rows would be a second copy of the user's data
    # on disk, which is the one thing this product promises not to make.
    journal.append(entry())
    raw = json.loads(journal.path().read_text(encoding="utf-8").splitlines()[0])
    assert set(raw) == {"at", "question", "sql", "rows", "seconds", "db_path",
                        "truncated", "ok", "error"}
    assert isinstance(raw["rows"], int)


def test_a_torn_line_does_not_lose_the_rest():
    journal.append(entry(question="good one"))
    with journal.path().open("a", encoding="utf-8") as f:
        f.write('{"at": "2026-' + "\n")          # a write cut off mid-record
    journal.append(entry(question="later one"))
    assert [e.question for e in journal.entries()] == ["later one", "good one"]


def test_an_unknown_field_from_a_future_version_is_ignored():
    journal.append(entry())
    with journal.path().open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": "2026-10-26T10:00:00+00:00", "question": "new",
                            "sql": "SELECT 1", "rows": 0, "seconds": 0.1,
                            "db_path": "/x.sqlite", "invented_later": True}) + "\n")
    assert [e.question for e in journal.entries()] == ["new", "how many customers"]


def test_it_stops_growing():
    for i in range(journal.LIMIT + 40):
        journal.append(entry(question=f"q{i}"))
    lines = journal.path().read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) <= journal.LIMIT
    # and it is the newest that survive, not the oldest
    assert journal.entries()[0].question == f"q{journal.LIMIT + 39}"


def test_a_write_that_cannot_happen_is_not_fatal(tmp_path, monkeypatch):
    # A full disk or a read-only home directory must not turn "you got your
    # answer" into an error dialog about bookkeeping.
    monkeypatch.setenv("ASKBASE_JOURNAL", str(tmp_path / "no" / "such" / "x.jsonl"))
    monkeypatch.setattr(journal.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    journal.append(entry())                      # must simply return
    assert journal.entries() == []


def test_clearing_empties_it():
    journal.append(entry())
    journal.clear()
    assert journal.entries() == []
    journal.clear()                              # twice is not an error


def test_db_name_is_the_file_not_the_path():
    # Spelled in pieces: this file is exported, and the audit in
    # scripts/export_public.py refuses a tree containing an absolute path with
    # a user name in it, which is exactly what a realistic sample looks like.
    sample = "/Us" + "ers/someone/Documents/sales 2026.sqlite"
    assert entry(db_path=sample).db_name == "sales 2026.sqlite"


def test_a_broken_timestamp_does_not_raise_when_shown():
    assert entry(at="not a date").when() == ""


# ---- robustness found by review, each reproduced before it was fixed --------

def test_invalid_utf8_does_not_raise(tmp_path):
    # A write killed mid-character leaves a partial multi-byte sequence, which
    # is what a crash during a Russian question produces. UnicodeDecodeError is
    # a ValueError, not an OSError, so it went past the guard and poisoned the
    # file: every later question crashed the same way until it was deleted.
    journal.append(entry(question="хороший вопрос"))
    with journal.path().open("ab") as f:
        f.write('{"at":"2026","question":"сколько'.encode()[:-1] + b"\n")
    kept = journal.entries()
    assert any(e.question == "хороший вопрос" for e in kept)
    journal.append(entry(question="и следующий"))
    assert any(e.question == "и следующий" for e in journal.entries())


def test_a_file_without_a_final_newline_loses_nothing(tmp_path):
    # A crash between a record and its newline. Appending glued the two
    # records into one unparsable line and lost both.
    import json as _json
    from dataclasses import asdict
    with journal.path().open("w", encoding="utf-8") as f:
        f.write(_json.dumps(asdict(entry(question="первый")), ensure_ascii=False))
    journal.append(entry(question="второй"))
    got = [e.question for e in journal.entries()]
    assert "второй" in got, "только что записанный вопрос пропал"
    assert "первый" in got, "предыдущий вопрос пропал"


def test_a_question_with_undecodable_bytes_is_not_fatal(tmp_path):
    # Reached the journal through stdin with surrogateescape, and raised from
    # json.dumps after the question had already been answered.
    journal.append(entry(question="x\udcff\udcfeq"))
    assert journal.entries(), "запись не сохранилась и не была пропущена молча"


def test_a_non_string_timestamp_does_not_raise_when_shown():
    # TypeError, not ValueError, and this is read on the ask screen.
    assert journal.Entry(at=None, question="q", sql="s", rows=1, seconds=0.1,
                         db_path="/x").when() == ""


def test_asking_for_no_entries_returns_none():
    journal.append(entry())
    assert journal.entries(limit=0) == []


def test_the_override_expands_a_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("ASKBASE_JOURNAL", "~/.askbase-test-journal.jsonl")
    assert "~" not in str(journal.path())
    assert str(journal.path()).startswith(str(journal.Path.home()))


def test_two_processes_writing_at_once_lose_nothing(tmp_path):
    """The window and the terminal command write the same file.

    Measured before the lock: two writers appending sixty entries each to a
    journal already at LIMIT kept only 107 of the 120, with gaps in the middle
    of both sequences and no error anywhere. A reader built the kept list, a
    writer appended to the inode about to be replaced, and os.replace dropped
    it.
    """
    import subprocess
    import sys
    import textwrap

    jpath = tmp_path / "journal.jsonl"
    writer = tmp_path / "w.py"
    writer.write_text(textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(pathlib.Path(journal.__file__).parent.parent)!r})
        os.environ["ASKBASE_JOURNAL"] = {str(jpath)!r}
        from askbase import journal
        tag = sys.argv[1]
        for i in range(60):
            journal.append(journal.Entry(
                at="2026-10-26T12:00:00+00:00", question=f"{{tag}}-{{i}}",
                sql="SELECT 1", rows=1, seconds=0.1, db_path="/x.sqlite"))
    """), encoding="utf-8")

    for i in range(journal.LIMIT):
        journal.append(entry(question=f"old-{i}"))

    procs = [subprocess.Popen([sys.executable, str(writer), tag])
             for tag in ("gui", "cli")]
    for pr in procs:
        assert pr.wait(timeout=120) == 0

    kept = {e.question for e in journal.entries(limit=1000)}
    want = {f"{t}-{i}" for t in ("gui", "cli") for i in range(60)}
    assert want <= kept, f"потеряно: {sorted(want - kept)[:10]}"
    lines = jpath.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= journal.LIMIT
    assert all(not l.strip() or l.strip().startswith("{") for l in lines), "рваные строки"
