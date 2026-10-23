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
from datetime import date, datetime, timedelta
from pathlib import Path

from .domains import medicine
from .schema_spec import Domain

DOMAINS: dict[str, Domain] = {
    medicine.DOMAIN.name: medicine.DOMAIN,
}
LOOKUPS: dict[str, dict[str, list[tuple]]] = {
    medicine.DOMAIN.name: medicine.LOOKUPS,
}

# Name pools are held here rather than taken from Faker so that the output does
# not move when Faker's own data files are updated. A locale upgrade silently
# changing a set is the same class of bug as the shifting "today".
_FIRST = ("Anna", "Mark", "Elena", "Pavel", "Irina", "Victor", "Olga", "Daniel",
          "Sofia", "Timur", "Vera", "Igor", "Alina", "Boris", "Nina", "Artem")
_LAST = ("Kovach", "Reiner", "Almeida", "Bauer", "Novak", "Linde", "Marek",
         "Soto", "Hale", "Varga", "Petran", "Oduya", "Kristof", "Benali")
_CITY = ("Northport", "Eastvale", "Marden", "Lowick", "Thorne", "Avelin")
_DEPT = ("cardiology", "neurology", "oncology", "surgery", "endocrinology")
_DRUG = ("amoxicillin", "metformin", "atorvastatin", "omeprazole", "insulin",
         "ibuprofen", "warfarin", "salbutamol")
_DX = (
    ("E11", "type 2 diabetes mellitus", "endocrine"),
    ("I10", "essential hypertension", "circulatory"),
    ("J45", "asthma", "respiratory"),
    ("I21", "acute myocardial infarction", "circulatory"),
    ("C50", "malignant neoplasm of breast", "neoplasms"),
    ("K21", "gastro-oesophageal reflux", "digestive"),
    ("G40", "epilepsy", "nervous"),
    ("N18", "chronic kidney disease", "genitourinary"),
)


def _iso(d: date) -> str:
    return d.isoformat()


def build_rows(domain: Domain, seed: int, now: date) -> dict[str, list[tuple]]:
    """Generate every table's rows deterministically from (seed, now)."""
    rng = random.Random(seed)
    rows: dict[str, list[tuple]] = {}

    for name, content in LOOKUPS[domain.name].items():
        rows[name] = list(content)

    n_pat = domain.row_counts["pat"]
    rows["pat"] = [
        (
            i + 1,
            f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
            _iso(now - timedelta(days=rng.randint(6_000, 32_000))),
            rng.choice((1, 2)),
            rng.choice(_CITY) if rng.random() > 0.08 else None,   # some rows lack a city
        )
        for i in range(n_pat)
    ]

    n_doc = domain.row_counts["doc"]
    rows["doc"] = [
        (
            i + 1,
            f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
            rng.choice(_DEPT),
            _iso(now - timedelta(days=rng.randint(200, 7_000))),
        )
        for i in range(n_doc)
    ]

    rows["dx_ref"] = list(_DX)

    n_enc = domain.row_counts["enc"]
    encounters: list[tuple] = []
    for i in range(n_enc):
        adm = now - timedelta(days=rng.randint(0, 540))
        status = rng.choices((0, 1, 2, 3), weights=(8, 14, 70, 8))[0]
        disch = _iso(adm + timedelta(days=rng.randint(1, 21))) if status == 2 else None
        # The legacy split: rows older than a year kept the old column, newer
        # rows use the new one. Exactly one of the two is ever populated.
        old_row = (now - adm).days > 365
        encounters.append((
            i + 1,
            rng.randint(1, n_pat),
            rng.randint(1, n_doc),
            _iso(adm) if old_row else None,
            None if old_row else _iso(adm),
            disch,
            status,
        ))
    rows["enc"] = encounters

    rows["dx"] = [
        (
            i + 1,
            rng.randint(1, n_enc),
            rng.choice(_DX)[0],
            1 if rng.random() < 0.6 else 0,
        )
        for i in range(domain.row_counts["dx"])
    ]

    rows["rx"] = [
        (
            i + 1,
            rng.randint(1, n_enc),
            rng.choice(_DRUG),
            rng.choice((1, 2, 3, 4)),
            rng.randint(1, 30),
        )
        for i in range(domain.row_counts["rx"])
    ]
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
