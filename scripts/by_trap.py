#!/usr/bin/env python3
"""Accuracy split by what kind of trap a task carries, written into the summary.

    python scripts/by_trap.py            # recompute and write
    python scripts/by_trap.py --check    # print, write nothing

The ranking page says that a question hiding nothing in the schema does far
better than the headline figure, and that is the single most important
sentence on it for a reader deciding whether to install anything. It was typed
by hand, and the builder's own docstring forbids exactly that: a number typed
into a page is correct on the day it is typed and silently wrong after the
next run.

It was also wrong. The figures first published were 90% and 39%, which are
the relaxed measure, printed beside a headline figure that is the strict one.
Two different measures in one sentence is the thing this project exists not to
do. The strict figures are 68.8% and 31.6%, and they are what the page now
quotes, resolved from the summary files like every other number on the site.

The classification of a trap is the hand-audited one from the review of set 1,
reproduced here rather than imported so that it is committed where it is used.
A task counts in `no_schema` when none of its traps is a schema-semantics one,
and in `only_schema` when all of them are.
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

SKILL = ("anti-join", "having", "two aliases", "joined twice",
         "a range, not on equality", "two joins to reach it",
         "inner join is correct here", "a single join answers")
CLARIFY = ("distinct customer", "distinct person", "distinct carrier",
           "distinct patient", "distinct applicant", "distinct part",
           "people reapply", "destination end", "deadline is inclusive",
           "unpaid leave", "avg over days, not sum", "sum over days",
           "cannot be late yet", "the two disagree")


def classify(trap: str) -> str:
    t = trap.lower()
    if any(k in t for k in SKILL):
        return "skill"
    if any(k in t for k in CLARIFY):
        return "clarify"
    return "schema"


def trap_classes() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for f in sorted(glob.glob(str(ROOT / "data/holdout/*/tasks.json"))):
        d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        for t in (d if isinstance(d, list) else d["tasks"]):
            out[t["tid"]] = {classify(x) for x in (t.get("traps") or [])}
    return out


def split(path: pathlib.Path, classes: dict[str, set[str]]) -> dict[str, float]:
    """Per-task accuracy averaged inside each bucket, on the strict measure."""
    acc: dict[str, list[bool]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            acc.setdefault(r["task"].split("/")[-1], []).append(bool(r["correct"]))
    score = {t: sum(v) / len(v) for t, v in acc.items()}
    buckets = {
        "no_schema": [t for t in score if "schema" not in classes.get(t, set())],
        "only_schema": [t for t in score if classes.get(t) == {"schema"}],
        "only_skill": [t for t in score if classes.get(t) == {"skill"}],
        "only_clarify": [t for t in score if classes.get(t) == {"clarify"}],
    }
    return {name: sum(score[t] for t in ts) / len(ts)
            for name, ts in buckets.items() if ts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)

    classes = trap_classes()
    if not classes:
        print("нет data/holdout, задачи не прочитаны")
        return 1
    touched = 0
    for jsonl in sorted((ROOT / "results").glob("*.holdout-??.jsonl")):
        summary = jsonl.with_name(jsonl.name[:-len(".jsonl")] + ".summary.json")
        if not summary.is_file():
            continue
        by_trap = split(jsonl, classes)
        print(f"{summary.name}")
        for k, v in by_trap.items():
            print(f"    {k:14s} {v:6.1%}")
        if not a.check:
            d = json.loads(summary.read_text(encoding="utf-8"))
            d["by_trap"] = by_trap
            summary.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
            touched += 1
    if touched:
        print(f"\nзаписано сводок: {touched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
