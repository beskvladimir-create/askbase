"""The questions asked before, with the query each one produced.

Two promises rest on this file and neither had anything behind it.

docs/roles.md gives role 1, the analyst who does not write SQL, "a journal of
one's own questions with one-click repeat", on the grounds that monthly
reporting is the same question twelve times. docs/design.md section 3 says the
SQL and the row count are written to a journal, and section 4.5 offers to open
or clear it. `recent.py` is not that journal: it keeps up to five database
paths and nothing else, so reopening a file was the only thing a user could
repeat.

Design decisions, each with a reason:

  - A file, not QSettings. QSettings is for preferences and holds a handful of
    small values; a growing list of questions and queries does not belong in a
    plist that is rewritten whole on every change.
  - JSONL, one record per line, appended. A crash mid-write costs the last line
    and nothing else, and the file stays readable with `tail`.
  - Local only, and that is the point. Nothing here is sent anywhere, which is
    the same promise the rest of the application makes about the question and
    the data. The file lives under the user's own Application Support folder
    and can be deleted from the settings screen or from Finder.
  - Questions are kept with their answers' shape (row count, seconds) but never
    with the answers themselves. A journal that stored result rows would be a
    copy of the user's data in a second place, which is exactly what a product
    promising the data does not leave the machine must not do.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LIMIT = 200


@contextlib.contextmanager
def _locked(p: Path):
    """Hold an exclusive lock on the journal for the duration of a write.

    The window and the terminal command write the same file, and the trim
    rewrites it whole. Without a lock a measured run of two writers appending
    sixty entries each kept only 107 of the 120, with gaps in the middle of
    both sequences and no error anywhere: a reader built the kept list, a
    writer appended to the inode that was about to be replaced, and os.replace
    dropped it.

    A lock file beside the journal rather than the journal itself, because the
    trim replaces the journal and a lock held on a replaced inode protects
    nothing. Failing to lock is not fatal: losing a journal line must never
    cost somebody their answer.
    """
    lock = p.with_suffix(p.suffix + ".lock")
    handle = None
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        handle = lock.open("a+")
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except (OSError, ImportError):
        handle = None                       # Windows, or an unwritable folder
    try:
        yield
    finally:
        if handle is not None:
            with contextlib.suppress(OSError):
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            with contextlib.suppress(OSError):
                handle.close()


@dataclass(frozen=True)
class Entry:
    """One question and what came of it."""

    at: str                 # ISO 8601, UTC
    question: str
    sql: str
    rows: int
    seconds: float
    db_path: str
    truncated: bool = False
    ok: bool = True
    error: str = ""

    @property
    def db_name(self) -> str:
        return Path(self.db_path).name

    def when(self) -> str:
        """Local time, for showing. Stored in UTC, shown where the user lives."""
        try:
            return (datetime.fromisoformat(self.at)
                    .astimezone()
                    .strftime("%d.%m %H:%M"))
        except (ValueError, TypeError):
            # TypeError for a hand-edited line carrying a number or null: this
            # is read on the ask screen, and a journal must not be able to
            # stop the application that writes it.
            return ""


def path() -> Path:
    """Where the journal lives. Honours a test override."""
    override = os.environ.get("ASKBASE_JOURNAL")
    if override:
        # expanduser, as cli.py does for --db. Without it "~/x/journal.jsonl"
        # created a directory literally named "~" in the working directory.
        return Path(override).expanduser()
    base = Path.home() / "Library" / "Application Support" / "Askbase"
    return base / "journal.jsonl"


def append(entry: Entry) -> None:
    """Add one record. A journal that breaks the app it serves is worse than none."""
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    with _locked(p):
        _append_locked(p, entry)
    _trim()


def _append_locked(p: Path, entry: Entry) -> None:
    try:
        # A crash between a record and its newline leaves a file that does not
        # end in one. Appending then glued the two records into a single
        # unparsable line and lost both: the old one and the one being written.
        # Checked by reading the last byte, which costs nothing next to the
        # write itself.
        needs_newline = False
        try:
            if p.is_file() and p.stat().st_size:
                with p.open("rb") as probe:
                    probe.seek(-1, 2)
                    needs_newline = probe.read(1) != b"\n"
        except OSError:
            needs_newline = False
        with p.open("a", encoding="utf-8", errors="replace") as f:
            if needs_newline:
                f.write("\n")
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
    except (OSError, ValueError):
        # Deliberately silent. The user asked a question and got an answer; a
        # full disk or a read-only home directory must not turn that into an
        # error dialog about bookkeeping.
        return


def entries(limit: int = LIMIT) -> list[Entry]:
    """Most recent first. A damaged line is skipped, never fatal."""
    p = path()
    if not p.is_file():
        return []
    if limit <= 0:
        return []
    out: list[Entry] = []
    try:
        # errors="replace", not strict. A write killed mid-character leaves a
        # partial multi-byte sequence, which is exactly what a crash during a
        # Russian question produces, and UnicodeDecodeError is a ValueError,
        # not an OSError, so it went straight past the guard and poisoned the
        # file for every later read.
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue                            # a torn last line, or hand-editing
        try:
            out.append(Entry(**{k: v for k, v in data.items()
                                if k in Entry.__dataclass_fields__}))
        except TypeError:
            continue
        if len(out) >= limit:
            break
    return out


def clear() -> None:
    try:
        path().unlink(missing_ok=True)
    except OSError:
        return


def _trim() -> None:
    """Keep the newest LIMIT records, rewriting atomically, under the lock.

    Written to a temporary file in the same directory and moved into place, so
    an interrupted trim cannot leave the journal half-rewritten. A truncate in
    place would.
    """
    p = path()
    with _locked(p):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        if len(lines) <= LIMIT:
            return
        keep = lines[-LIMIT:]
        try:
            fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(keep) + "\n")
            os.replace(tmp, p)
        except OSError:
            return
