"""The holdout set is the main verdict, so its own generator gets checked hard.

A gold query that returns nothing, or that happens to return the same thing as
a wrong query would, is a broken task. CIDR 2026 measured annotation error rates
of 52.8% on BIRD Mini-Dev; the only defence is to check our own tasks by
machine where a machine can, and by hand where it cannot.
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from nl2sql_app.holdout.domains import medicine
from nl2sql_app.holdout.generate import build_rows, canonical_dump, tasks_payload, write_sqlite
from nl2sql_app.safety import check

SEED = 20261021
NOW = date(2026, 10, 21)
DOMAIN = medicine.DOMAIN


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    rows = build_rows(DOMAIN, SEED, NOW)
    path = tmp_path_factory.mktemp("holdout") / "medicine.sqlite"
    write_sqlite(DOMAIN, rows, path)
    con = sqlite3.connect(path)
    yield con
    con.close()


def test_same_seed_and_date_give_the_same_bytes():
    a = canonical_dump(build_rows(DOMAIN, SEED, NOW), tasks_payload(DOMAIN))
    b = canonical_dump(build_rows(DOMAIN, SEED, NOW), tasks_payload(DOMAIN))
    assert a == b


def test_a_different_frozen_date_changes_the_set():
    # Guards the pii-roundtrip failure mode: a set that silently moves because
    # it was regenerated on another day.
    a = canonical_dump(build_rows(DOMAIN, SEED, NOW), tasks_payload(DOMAIN))
    b = canonical_dump(build_rows(DOMAIN, SEED, date(2026, 10, 22)), tasks_payload(DOMAIN))
    assert a != b


def test_a_different_seed_changes_the_set():
    a = canonical_dump(build_rows(DOMAIN, SEED, NOW), tasks_payload(DOMAIN))
    b = canonical_dump(build_rows(DOMAIN, SEED + 1, NOW), tasks_payload(DOMAIN))
    assert a != b


@pytest.mark.parametrize("task", DOMAIN.tasks, ids=lambda t: t.tid)
def test_gold_sql_runs_and_returns_rows(db, task):
    rows = db.execute(task.gold_sql).fetchall()
    assert rows, f"{task.tid}: эталонный запрос вернул пусто, задача непригодна"


@pytest.mark.parametrize("task", DOMAIN.tasks, ids=lambda t: t.tid)
def test_gold_sql_passes_the_safety_check(db, task):
    # The gold queries must be things the product would actually be allowed to
    # run. A gold query our own guard rejects would mean the guard is wrong or
    # the task is.
    schema = {
        t.name: {r[1] for r in db.execute(f"PRAGMA table_info({t.name})")}
        for t in DOMAIN.tables
    }
    v = check(task.gold_sql, schema=schema)
    assert v.ok, f"{task.tid}: {v.reason}"


@pytest.mark.parametrize("task", DOMAIN.tasks, ids=lambda t: t.tid)
def test_every_task_has_four_wordings_in_two_languages(task):
    w = task.wordings()
    assert len(w) == 4
    assert sum(1 for lang, _, _ in w if lang == "en") == 2
    assert sum(1 for lang, _, _ in w if lang == "ru") == 2
    for _, _, text in w:
        assert text.strip()
    # Two wordings that differ only in punctuation would not measure paraphrase
    # robustness at all.
    assert task.en[0] != task.en[1]
    assert task.ru[0] != task.ru[1]


def test_russian_wordings_are_actually_russian():
    for task in DOMAIN.tasks:
        for text in task.ru:
            assert any("а" <= c.lower() <= "я" for c in text), task.tid


def test_task_ids_are_unique():
    ids = [t.tid for t in DOMAIN.tasks]
    assert len(ids) == len(set(ids))


def test_coded_columns_really_hold_codes(db):
    # The value-grounding feature is aimed at these columns; if the generator
    # ever starts writing words here, that feature becomes untestable.
    for table in DOMAIN.tables:
        for col in table.coded_columns:
            vals = [r[0] for r in db.execute(f"SELECT DISTINCT {col} FROM {table.name}")]
            assert vals, f"{table.name}.{col} пуст"
            assert all(isinstance(v, int) for v in vals), f"{table.name}.{col} не коды"


def test_legacy_column_pair_is_split_not_duplicated(db):
    # Exactly one of dt_adm / admitted_at is set per row. If both were filled,
    # the task that needs COALESCE would be solvable without noticing the trap.
    both, neither = db.execute(
        "SELECT SUM(dt_adm IS NOT NULL AND admitted_at IS NOT NULL),"
        "       SUM(dt_adm IS NULL AND admitted_at IS NULL) FROM enc"
    ).fetchone()
    assert both == 0
    assert neither == 0


def test_some_rows_have_a_missing_city(db):
    # Null handling is part of what the set is meant to probe.
    n = db.execute("SELECT COUNT(*) FROM pat WHERE city IS NULL").fetchone()[0]
    assert n > 0


# A trap that a naive query survives is decoration, not difficulty. Each case
# below is the query a model plausibly writes when it misses the trap; it must
# return something different from the gold, or the task does not discriminate.
NAIVE = {
    "med-001": "SELECT sex_cd, COUNT(*) FROM pat GROUP BY sex_cd ORDER BY 2 DESC",
    "med-003": "SELECT COUNT(*) FROM enc WHERE dt_adm >= '2026-01-01' AND dt_adm < '2026-04-01'",
    "med-004": "SELECT code, COUNT(*) FROM dx WHERE primary_flag = 1 GROUP BY code ORDER BY 2 DESC, 1 LIMIT 3",
    "med-005": "SELECT DISTINCT p.full_name FROM pat p JOIN enc e ON e.pat_id = p.id ORDER BY 1",
    "med-007": "SELECT d.dept, COUNT(*) FROM enc e JOIN doc d ON d.id = e.doc_id GROUP BY d.dept ORDER BY 2 DESC, 1",
    "med-008": "SELECT p.full_name, COUNT(*) FROM enc e JOIN pat p ON p.id = e.pat_id GROUP BY p.id, p.full_name ORDER BY 2 DESC, 1",
}


@pytest.mark.parametrize("tid,naive_sql", sorted(NAIVE.items()))
def test_the_trap_actually_bites(db, tid, naive_sql):
    task = next(t for t in DOMAIN.tasks if t.tid == tid)
    gold = db.execute(task.gold_sql).fetchall()
    naive = db.execute(naive_sql).fetchall()
    assert gold != naive, f"{tid}: наивный запрос даёт тот же ответ, ловушка не работает"
