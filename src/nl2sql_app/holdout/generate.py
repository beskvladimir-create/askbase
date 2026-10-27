"""Build a holdout domain into a SQLite file plus its task list, reproducibly.

    python -m nl2sql_app.holdout.generate --domain medicine --now 2026-10-21 \
        --seed 20261021 --out data/holdout

Byte-for-byte reproducibility is the whole point: HOLDOUT.md records a SHA-256
per file, and `verify.py` refuses to run a tool whose set does not match. Three
things would break it and are therefore pinned here.

  - the random seed, passed in and recorded
  - "today", because Faker derives dates from the current day. pii-roundtrip hit
    exactly this: regenerating a set on a different day moved one value out of
    a hundred documents. The date is an argument, never `date.today()`.
  - SQLite's own file layout, which carries timestamps and free-page noise. We
    write the database deterministically and emit the tasks as JSON, and the
    hash of record is over the JSON dump of the data, not over the .sqlite blob.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .domains import (
    banking,
    hr,
    logistics,
    manufacturing,
    medicine,
    public_services,
)
from .schema_spec import Domain

# A domain owns its own tables, its own lookups and its own row builder. The
# generator used to reach into medicine's table names directly, which meant a
# second domain could not exist without either renaming its tables to match or
# forking this file. Adding a domain is now adding a module to this tuple.
MODULES = (medicine, banking, logistics, public_services, manufacturing, hr)
DOMAINS: dict[str, Domain] = {m.DOMAIN.name: m.DOMAIN for m in MODULES}
_BY_NAME = {m.DOMAIN.name: m for m in MODULES}


def build_rows(domain: Domain, seed: int, now: date) -> dict[str, list[tuple]]:
    """Generate every table's rows deterministically from (seed, now).

    Lookup tables come first and verbatim: their contents are part of the
    schema's meaning rather than sample data, and a model is expected to reach
    them through a join. Everything after that is the domain's own business,
    built from one shared rng so that a domain cannot perturb another's bytes.
    """
    module = _BY_NAME[domain.name]
    rng = random.Random(seed)
    rows: dict[str, list[tuple]] = {n: list(v) for n, v in module.LOOKUPS.items()}
    rows.update(module.build_rows(rng, now, domain.row_counts))
    return rows


def write_sqlite(domain: Domain, rows: dict[str, list[tuple]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        con.executescript(domain.ddl())
        for table, data in rows.items():
            if not data:
                continue
            placeholders = ",".join("?" * len(data[0]))
            con.executemany(f"INSERT INTO {table} VALUES ({placeholders})", data)
        con.commit()
    finally:
        con.close()


def tasks_payload(domain: Domain) -> list[dict]:
    """The task list as it is frozen and hashed."""
    return [
        {
            "tid": t.tid,
            "domain": domain.name,
            "gold_sql": " ".join(t.gold_sql.split()),
            "wordings": [
                {"lang": lang, "idx": idx, "text": text}
                for lang, idx, text in t.wordings()
            ],
            "traps": list(t.traps),
        }
        for t in domain.tasks
    ]


def canonical_dump(rows: dict[str, list[tuple]], tasks: list[dict]) -> str:
    """Stable text form of the whole set, and the thing the SHA-256 covers.

    Hashing this instead of the .sqlite file keeps the digest meaningful: two
    SQLite files holding identical data can differ byte for byte, so a hash of
    the blob would fail for reasons that have nothing to do with the data.
    """
    payload = {
        "tables": {name: [list(r) for r in data] for name, data in sorted(rows.items())},
        "tasks": tasks,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, choices=sorted(DOMAINS))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--now", required=True,
                    help="frozen 'today' as YYYY-MM-DD; never the real current date")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    domain = DOMAINS[args.domain]
    now = datetime.strptime(args.now, "%Y-%m-%d").date()
    out = Path(args.out) / domain.name

    rows = build_rows(domain, args.seed, now)
    tasks = tasks_payload(domain)
    write_sqlite(domain, rows, out / f"{domain.name}.sqlite")
    (out / "tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    dump = canonical_dump(rows, tasks)
    (out / "canonical.json").write_text(dump, encoding="utf-8")
    digest = hashlib.sha256(dump.encode()).hexdigest()
    (out / "SHA256").write_text(digest + "\n", encoding="utf-8")

    print(f"домен      {domain.name}")
    print(f"зерно      {args.seed}, дата {args.now}")
    print(f"таблиц     {len(domain.tables)}")
    print(f"строк      {sum(len(v) for v in rows.values())}")
    print(f"задач      {len(tasks)}, формулировок {sum(len(t['wordings']) for t in tasks)}")
    print(f"каталог    {out}")
    print(f"SHA-256    {digest}")


if __name__ == "__main__":
    main()
