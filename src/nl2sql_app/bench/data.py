"""Load a benchmark set: BIRD dev, or our own frozen held-out set.

BIRD dev, under `data/bird/`:
    dev.json                 list of {question_id, db_id, question, evidence, SQL}
    dev_databases/<db_id>/<db_id>.sqlite
Download: https://bird-bench.github.io/  (dev set + databases).

The held-out set, under `data/holdout/`, as `nl2sql_app.holdout.generate`
writes it:
    <domain>/<domain>.sqlite
    <domain>/tasks.json      the tasks, each with four wordings
    <domain>/canonical.json  the bytes the published SHA-256 covers
See HOLDOUT.md. It is generated, never downloaded, and the digests are checked
before anything is read out of it.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Example:
    qid: int
    db_id: str
    question: str
    evidence: str          # BIRD "external knowledge" hint; empty on our set
    gold_sql: str
    db_path: str           # absolute path to the sqlite file

    # Held-out set only. BIRD has one question per gold query; ours has four
    # wordings of each, which are not independent observations. The task is the
    # resampling unit fixed in HOLDOUT.md before the run, and without it on the
    # record the interval would be computed over 96 wordings instead of 48
    # tasks and come out about a factor of √2 too narrow.
    task: str | None = None
    lang: str | None = None
    wording: int | None = None
    traps: tuple[str, ...] = field(default_factory=tuple)


def load_bird_dev(root: str) -> list[Example]:
    """Read dev.json and resolve each db's sqlite path. Fail loudly if missing."""
    dev_json = os.path.join(root, "dev.json")
    db_root = os.path.join(root, "dev_databases")
    if not os.path.isfile(dev_json):
        raise FileNotFoundError(
            f"{dev_json} not found. Download BIRD dev from https://bird-bench.github.io/"
        )
    with open(dev_json) as f:
        rows = json.load(f)

    out: list[Example] = []
    for r in rows:
        db_id = r["db_id"]
        db_path = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        out.append(
            Example(
                qid=r.get("question_id", len(out)),
                db_id=db_id,
                question=r["question"].strip(),
                evidence=(r.get("evidence") or "").strip(),
                gold_sql=r["SQL"].strip(),
                db_path=db_path,
            )
        )
    missing = [e.db_id for e in out if not os.path.isfile(e.db_path)]
    if missing:
        raise FileNotFoundError(
            f"{len(set(missing))} db files missing under {db_root}, e.g. {sorted(set(missing))[:3]}"
        )
    return out


def load_holdout(root: str, lang: str) -> list[Example]:
    """Read the frozen held-out set, one Example per wording in `lang`.

    The digests are checked here, not only in the verifier CLI. HOLDOUT.md puts
    `verify` first in the run plan, but a step that can be skipped is a step
    that will be, and a run against a set that is not the frozen one is a
    different experiment wearing the same name. Checking it at the point where
    the data is actually read is the version that cannot be forgotten.

    Only the domains named in the freeze are read, in sorted order, so a stray
    directory under `data/holdout/` cannot contribute tasks. `verify.check_set`
    refuses one outright, and this loop would ignore it either way.
    """
    from nl2sql_app.holdout.verify import check_set, expected

    base = Path(root)
    check_set(base)                      # raises NotFrozen on any difference

    out: list[Example] = []
    empty: list[str] = []
    for domain in sorted(expected()["domains"]):
        db_path = base / domain / f"{domain}.sqlite"
        if not db_path.is_file():
            raise FileNotFoundError(
                f"{db_path} нет. Сгенерируйте набор заново: см. HOLDOUT.md"
            )
        tasks = json.loads((base / domain / "tasks.json").read_text(encoding="utf-8"))
        for task in sorted(tasks, key=lambda t: t["tid"]):
            wordings = sorted((w for w in task["wordings"] if w["lang"] == lang),
                              key=lambda w: w["idx"])
            if not wordings:
                empty.append(f"{domain}/{task['tid']}")
                continue
            for w in wordings:
                out.append(Example(
                    # Sequential in a deterministic order, so the same wording
                    # carries the same qid in every run and per-question records
                    # line up across models.
                    qid=len(out),
                    db_id=domain,
                    question=w["text"].strip(),
                    evidence="",         # our set carries no external-knowledge hints
                    gold_sql=task["gold_sql"].strip(),
                    db_path=str(db_path),
                    task=f"{domain}/{task['tid']}",
                    lang=lang,
                    wording=w["idx"],
                    traps=tuple(task.get("traps", ())),
                ))
    if not out:
        raise ValueError(f"в наборе нет ни одной формулировки на языке {lang!r}")
    if empty:
        # Not a warning. A task silently contributing to one language and not
        # the other makes the two columns incomparable, which is the one thing
        # the four-wordings-per-task design exists to prevent.
        raise ValueError(
            f"нет формулировок на {lang!r} у задач: {', '.join(empty[:5])}"
            f"{' и ещё ' + str(len(empty) - 5) if len(empty) > 5 else ''}"
        )
    return out
