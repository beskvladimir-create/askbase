"""Refuse to run on a held-out set that is not the frozen one.

    python -m nl2sql_app.holdout.verify --data data/holdout
    python -m nl2sql_app.holdout.verify --data data/holdout \
        --record "xiyan-7b-q4" --reason "первый прогон"

A digest written in a document and never checked is decoration. This is the
part that makes the freeze real, and it refuses rather than warns: a run on a
set that does not match is not a weaker result, it is a different experiment
wearing the same name.

Three checks, each for a failure that has actually happened to somebody.

**The set matches.** Every domain's canonical.json is hashed and compared with
DIGESTS.json. A missing domain is a failure too: running five of six and
reporting the number as the held-out result is the quiet version of choosing
the sample after seeing it.

**The code is committed.** pii-roundtrip's rule, and the reason is the same:
"which code produced this" has to be answerable later, and a dirty tree makes
it unanswerable. Uncommitted changes to anything but the data refuse the run.

**The run is written down.** Every run appends to results/holdout_runs.jsonl:
the tool, the set, the commit, the time. A second run of the same tool on the
same set is refused unless a reason is given, and the reason stays in the
journal. This is what stops a held-out set from quietly becoming a set you
tried until it agreed with you.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
DIGESTS = HERE / "DIGESTS.json"
JOURNAL = ROOT / "results" / "holdout_runs.jsonl"


class NotFrozen(Exception):
    """The set on disk is not the set that was frozen."""


def expected() -> dict:
    return json.loads(DIGESTS.read_text(encoding="utf-8"))


def digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_set(data: Path) -> dict[str, str]:
    """Hash every domain on disk and compare. Raises on the first difference."""
    want = expected()["domains"]
    problems: list[str] = []
    got: dict[str, str] = {}
    for name, digest in sorted(want.items()):
        canonical = data / name / "canonical.json"
        if not canonical.exists():
            problems.append(f"{name}: нет файла {canonical}")
            continue
        actual = digest_of(canonical)
        got[name] = actual
        if actual != digest:
            problems.append(f"{name}: SHA-256 {actual}, а заморожен {digest}")
    extra = sorted(p.name for p in data.iterdir()
                   if p.is_dir() and p.name not in want) if data.exists() else []
    if extra:
        problems.append(f"лишние домены, которых нет в заморозке: {', '.join(extra)}")
    if problems:
        raise NotFrozen("набор не совпадает с замороженным:\n  " + "\n  ".join(problems))
    return got


def head_commit() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True, check=False)
    return r.stdout.strip() or "unknown"


def dirty_paths() -> list[str]:
    """Uncommitted changes, ignoring the generated data itself."""
    r = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                       capture_output=True, text=True, check=False)
    out = []
    for line in r.stdout.splitlines():
        path = line[3:].strip()
        if path.startswith(("data/", "results/")):
            continue
        out.append(path)
    return out


def previous_runs(tool: str, set_no: int) -> list[dict]:
    if not JOURNAL.exists():
        return []
    rows = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("tool") == tool and row.get("set") == set_no:
            rows.append(row)
    return rows


def record(tool: str, set_no: int, reason: str = "") -> dict:
    earlier = previous_runs(tool, set_no)
    if earlier and not reason:
        raise NotFrozen(
            f"{tool} уже прогонялся на наборе {set_no} "
            f"({earlier[-1].get('at')}). Повтор только с --reason, "
            f"и причина останется в журнале."
        )
    row = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": tool,
        "set": set_no,
        "commit": head_commit(),
        "repeat": len(earlier),
        "reason": reason,
    }
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/holdout")
    ap.add_argument("--record", metavar="TOOL",
                    help="записать прогон этого инструмента в журнал")
    ap.add_argument("--reason", default="",
                    help="причина повторного прогона; без неё повтор отклоняется")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="только для отладки: прогон с незакоммиченного кода")
    args = ap.parse_args(argv)

    meta = expected()
    data = Path(args.data)
    try:
        got = check_set(data)
    except NotFrozen as e:
        print(f"ОТКАЗ: {e}", file=sys.stderr)
        return 1

    print(f"набор {meta['set']}, зерно {meta['seed']}, дата {meta['now']}")
    for name, digest in sorted(got.items()):
        print(f"  {name:<18} {digest}")
    print(f"совпало доменов: {len(got)} из {len(meta['domains'])}")

    if args.record:
        dirty = dirty_paths()
        if dirty and not args.allow_dirty:
            print("ОТКАЗ: незакоммиченные изменения, прогон не записан:",
                  file=sys.stderr)
            for p in dirty[:10]:
                print(f"  {p}", file=sys.stderr)
            return 1
        try:
            row = record(args.record, meta["set"], args.reason)
        except NotFrozen as e:
            print(f"ОТКАЗ: {e}", file=sys.stderr)
            return 1
        print(f"записан прогон: {row['tool']}, коммит {row['commit'][:10]}, "
              f"повтор {row['repeat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
