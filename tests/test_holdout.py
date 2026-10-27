"""The holdout set is the main verdict, so its own generator gets checked hard.

A gold query that returns nothing, or that happens to return the same thing as
a wrong query would, is a broken task. CIDR 2026 measured annotation error rates
of 52.8% on BIRD Mini-Dev; the only defence is to check our own tasks by
machine where a machine can, and by hand where it cannot.

Every check here runs against every domain. A test that only knew about
medicine would have passed while a second domain shipped broken, which is the
failure this file exists to prevent.
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from nl2sql_app.holdout.generate import (
    DOMAINS,
    build_rows,
    canonical_dump,
    tasks_payload,
    write_sqlite,
)
from nl2sql_app.safety import check

SEED = 20261021
NOW = date(2026, 10, 21)
ALL = sorted(DOMAINS.values(), key=lambda d: d.name)
TASKS = [(d, t) for d in ALL for t in d.tasks]


def _tid(param) -> str:
    return param.name if hasattr(param, "name") else str(param)


@pytest.fixture(scope="module")
def dbs(tmp_path_factory):
    """One connection per domain, built once."""
    root = tmp_path_factory.mktemp("holdout")
    out = {}
    for domain in ALL:
        path = root / f"{domain.name}.sqlite"
        write_sqlite(domain, build_rows(domain, SEED, NOW), path)
        out[domain.name] = sqlite3.connect(path)
    yield out
    for con in out.values():
        con.close()


@pytest.mark.parametrize("domain", ALL, ids=_tid)
def test_same_seed_and_date_give_the_same_bytes(domain):
    a = canonical_dump(build_rows(domain, SEED, NOW), tasks_payload(domain))
    b = canonical_dump(build_rows(domain, SEED, NOW), tasks_payload(domain))
    assert a == b


@pytest.mark.parametrize("domain", ALL, ids=_tid)
def test_a_different_frozen_date_changes_the_set(domain):
    # Guards the pii-roundtrip failure mode: a set that silently moves because
    # it was regenerated on another day.
    a = canonical_dump(build_rows(domain, SEED, NOW), tasks_payload(domain))
    b = canonical_dump(build_rows(domain, SEED, date(2026, 10, 22)), tasks_payload(domain))
    assert a != b


@pytest.mark.parametrize("domain", ALL, ids=_tid)
def test_a_different_seed_changes_the_set(domain):
    a = canonical_dump(build_rows(domain, SEED, NOW), tasks_payload(domain))
    b = canonical_dump(build_rows(domain, SEED + 1, NOW), tasks_payload(domain))
    assert a != b


def test_domains_do_not_share_a_digest():
    # Two domains that generated the same bytes would mean one of them is not
    # wired up, and the set would be a third smaller than it claims.
    dumps = {d.name: canonical_dump(build_rows(d, SEED, NOW), tasks_payload(d)) for d in ALL}
    assert len(set(dumps.values())) == len(dumps)


@pytest.mark.parametrize("domain,task", TASKS, ids=lambda p: getattr(p, "tid", _tid(p)))
def test_gold_sql_runs_and_returns_rows(dbs, domain, task):
    rows = dbs[domain.name].execute(task.gold_sql).fetchall()
    assert rows, f"{task.tid}: эталонный запрос вернул пусто, задача непригодна"


@pytest.mark.parametrize("domain,task", TASKS, ids=lambda p: getattr(p, "tid", _tid(p)))
def test_gold_sql_passes_the_safety_check(dbs, domain, task):
    # The gold queries must be things the product would actually be allowed to
    # run. A gold query our own guard rejects would mean the guard is wrong or
    # the task is.
    db = dbs[domain.name]
    schema = {
        t.name: {r[1] for r in db.execute(f"PRAGMA table_info({t.name})")}
        for t in domain.tables
    }
    v = check(task.gold_sql, schema=schema)
    assert v.ok, f"{task.tid}: {v.reason}"


@pytest.mark.parametrize("domain,task", TASKS, ids=lambda p: getattr(p, "tid", _tid(p)))
def test_every_task_has_four_wordings_in_two_languages(domain, task):
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


@pytest.mark.parametrize("domain,task", TASKS, ids=lambda p: getattr(p, "tid", _tid(p)))
def test_russian_wordings_are_actually_russian(domain, task):
    for text in task.ru:
        assert any("а" <= c.lower() <= "я" for c in text), task.tid


@pytest.mark.parametrize("domain,task", TASKS, ids=lambda p: getattr(p, "tid", _tid(p)))
def test_every_task_names_its_traps(domain, task):
    # A task with no trap recorded cannot be classified in the error analysis,
    # and the report needs that split to mean anything.
    assert task.traps, f"{task.tid}: ловушки не описаны"


def test_task_ids_are_unique_across_every_domain():
    ids = [t.tid for _, t in TASKS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("domain", ALL, ids=_tid)
def test_coded_columns_really_hold_codes(dbs, domain):
    # The value-grounding feature is aimed at these columns; if the generator
    # ever starts writing words here, that feature becomes untestable.
    db = dbs[domain.name]
    for table in domain.tables:
        for col in table.coded_columns:
            vals = [r[0] for r in db.execute(
                f"SELECT DISTINCT {col} FROM {table.name} WHERE {col} IS NOT NULL")]
            assert vals, f"{table.name}.{col} пуст"
            # NULL is allowed and is not a code: public_services.stage.result_cd
            # is NULL while a stage is open, and telling a missing value apart
            # from a value meaning "unknown" is the whole of gov-006.
            assert all(isinstance(v, int) for v in vals), f"{table.name}.{col} не коды"


# Exactly one of each legacy pair is set per row. If both were filled, the task
# that needs COALESCE would be solvable without noticing the trap; if neither
# were, the column would just be empty and the trap would be a different one.
LEGACY_PAIRS = [
    ("medicine", "enc", "dt_adm", "admitted_at"),
    ("banking", "txn", "dt_op", "posted_at"),
    ("logistics", "shp", "dt_disp", "dispatched_at"),
    ("public_services", "case_rec", "dt_sub", "submitted_at"),
    ("manufacturing", "mov", "dt_op", "recorded_at"),
]


@pytest.mark.parametrize("domain,table,old,new", LEGACY_PAIRS, ids=lambda p: str(p))
def test_legacy_column_pair_is_split_not_duplicated(dbs, domain, table, old, new):
    both, neither = dbs[domain].execute(
        f"SELECT SUM({old} IS NOT NULL AND {new} IS NOT NULL),"
        f"       SUM({old} IS NULL AND {new} IS NULL) FROM {table}"
    ).fetchone()
    assert both == 0
    assert neither == 0


# Null handling is part of what the set is meant to probe.
NULLABLE = [("medicine", "pat", "city"), ("banking", "cust", "city"),
            ("logistics", "cust", "city"), ("public_services", "applicant", "city"),
            ("hr", "emp", "left_at"), ("public_services", "stage", "result_cd")]


@pytest.mark.parametrize("domain,table,col", NULLABLE, ids=lambda p: str(p))
def test_some_rows_have_a_missing_value(dbs, domain, table, col):
    n = dbs[domain].execute(
        f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]
    assert n > 0


def test_status_and_date_disagree_in_medicine(dbs):
    # med-002 rests on this: a cancelled encounter can carry a discharge date,
    # so "discharged" by status and "discharged" by date are different answers.
    n = dbs["medicine"].execute(
        "SELECT COUNT(*) FROM enc WHERE status_cd != 2 AND discharged IS NOT NULL"
    ).fetchone()[0]
    assert n > 0


def test_status_and_date_disagree_in_logistics(dbs):
    # log-006 rests on this: a lost shipment can carry a delivery attempt date,
    # so "delivered" by status and "delivered" by date are different answers.
    n = dbs["logistics"].execute(
        "SELECT COUNT(*) FROM shp WHERE status_cd != 2 AND delivered_at IS NOT NULL"
    ).fetchone()[0]
    assert n > 0


def test_one_lookup_is_joined_twice_in_logistics(dbs):
    # log-002 is only hard if origin and destination genuinely differ.
    n = dbs["logistics"].execute(
        "SELECT COUNT(*) FROM shp WHERE org_cd = dst_cd").fetchone()[0]
    assert n == 0


# A trap that a naive query survives is decoration, not difficulty. Each case
# below is the query a model plausibly writes when it misses the trap; it must
# return something different from the gold, or the task does not discriminate.
NAIVE = {
    "med-001": "SELECT sex_cd, COUNT(*) FROM pat GROUP BY sex_cd ORDER BY 2 DESC",
    # the plausible miss: the discharge date column instead of the status code
    "med-002": "SELECT d.full_name, COUNT(*) FROM enc e JOIN doc d ON d.id = e.doc_id WHERE e.discharged IS NOT NULL GROUP BY d.full_name ORDER BY 2 DESC, 1 LIMIT 5",
    "med-003": "SELECT COUNT(*) FROM enc WHERE dt_adm >= '2026-01-01' AND dt_adm < '2026-04-01'",
    "med-004": "SELECT code, COUNT(*) FROM dx WHERE primary_flag = 1 GROUP BY code ORDER BY 2 DESC, 1 LIMIT 3",
    "med-005": "SELECT DISTINCT p.full_name FROM pat p JOIN enc e ON e.pat_id = p.id ORDER BY 1",
    # the plausible miss: grouping by the route code rather than its name
    "med-006": "SELECT x.route_cd, AVG(x.days) FROM rx x GROUP BY x.route_cd ORDER BY 2 DESC",
    "med-007": "SELECT d.dept, COUNT(*) FROM enc e JOIN doc d ON d.id = e.doc_id GROUP BY d.dept ORDER BY 2 DESC, 1",
    "med-008": "SELECT p.full_name, COUNT(*) FROM enc e JOIN pat p ON p.id = e.pat_id GROUP BY p.id, p.full_name ORDER BY 2 DESC, 1",

    "bank-001": "SELECT cur_cd, COUNT(*) FROM acct GROUP BY cur_cd ORDER BY 2 DESC, 1",
    # the plausible miss: summing the amount as if its sign carried the direction
    "bank-002": "SELECT SUM(amt_cents) / 100.0 FROM txn",
    "bank-003": "SELECT COUNT(*) FROM txn WHERE dt_op >= '2026-04-01' AND dt_op < '2026-07-01'",
    "bank-004": "SELECT mcc, COUNT(*) FROM txn GROUP BY mcc ORDER BY 2 DESC, 1 LIMIT 3",
    "bank-005": "SELECT DISTINCT c.full_name FROM cust c JOIN acct a ON a.cust_id = c.id ORDER BY 1",
    # the plausible miss: basis points read as per cent
    "bank-006": "SELECT AVG(rate_bp) FROM loan WHERE closed_at IS NULL",
    "bank-007": "SELECT r.title, COUNT(*) FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY 2 DESC, 1",
    "bank-008": "SELECT c.full_name, COUNT(*) FROM acct a JOIN cust c ON c.id = a.cust_id GROUP BY c.id, c.full_name ORDER BY 2 DESC, 1",

    "log-001": "SELECT mode_cd, COUNT(*) FROM carr GROUP BY mode_cd ORDER BY 2 DESC, 1",
    # the plausible miss: one join, so both ends read as the same place
    "log-002": "SELECT l.title, COUNT(*) FROM shp s JOIN loc_ref l ON l.cd = s.org_cd GROUP BY l.title ORDER BY 2 DESC, 1 LIMIT 5",
    "log-003": "SELECT COUNT(*) FROM shp WHERE dt_disp >= '2026-07-01' AND dt_disp < '2026-10-01'",
    "log-004": "SELECT SUM(cost_cents) FROM leg",
    "log-005": "SELECT DISTINCT s.id FROM shp s JOIN inc i ON i.shp_id = s.id ORDER BY 1",
    # the plausible miss: the date column instead of the status code
    "log-006": "SELECT COUNT(*) FROM shp WHERE delivered_at IS NOT NULL",
    "log-007": "SELECT l.title, COUNT(*) FROM leg g JOIN shp s ON s.id = g.shp_id JOIN loc_ref l ON l.cd = s.dst_cd GROUP BY l.title ORDER BY 2 DESC, 1",
    "log-008": "SELECT g.shp_id, SUM(g.dist_km) FROM leg g GROUP BY g.shp_id ORDER BY 2 DESC, 1",

    "gov-001": "SELECT o.title, COUNT(*) FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY o.title ORDER BY 2 DESC, 1",
    # the plausible miss: a strict comparison that also counts the cases closed
    # exactly on the deadline, which are not late
    "gov-002": "SELECT COUNT(*) FROM case_rec WHERE closed_at >= due_dt",
    "gov-003": "SELECT COUNT(*) FROM case_rec",
    "gov-004": "SELECT COUNT(*) FROM case_rec WHERE dt_sub >= '2026-04-01' AND dt_sub < '2026-07-01'",
    "gov-005": "SELECT DISTINCT a.full_name FROM applicant a JOIN case_rec c ON c.applicant_id = a.id ORDER BY 1",
    # the plausible miss: counting the open stages as a result of their own
    "gov-006": "SELECT s.result_cd, COUNT(*) FROM stage s GROUP BY s.result_cd ORDER BY 2 DESC, 1",
    "gov-007": "SELECT sv.title, COUNT(*) FROM case_rec c JOIN service sv ON sv.id = c.service_id GROUP BY sv.title ORDER BY 2 DESC, 1",
    "gov-008": "SELECT a.full_name, COUNT(*) FROM case_rec c JOIN applicant a ON a.id = c.applicant_id GROUP BY a.id, a.full_name ORDER BY 2 DESC, 1",

    "mfg-001": "SELECT kind_cd, COUNT(*) FROM mov GROUP BY kind_cd ORDER BY 2 DESC, 1",
    # the plausible miss: adding pieces to kilograms to tonnes
    "mfg-002": "SELECT SUM(qty) FROM mov WHERE kind_cd = 3",
    "mfg-003": "SELECT COUNT(*) FROM mov WHERE dt_op >= '2026-01-01' AND dt_op < '2026-04-01'",
    # the plausible miss: joining the price on part_id alone, which multiplies
    # every movement by the number of price rows the part has
    "mfg-004": "SELECT p.title, SUM(m.qty * pp.minor / 100.0) FROM mov m JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id GROUP BY p.title ORDER BY 2 DESC, 1 LIMIT 3",
    "mfg-005": "SELECT DISTINCT m.id FROM mov m JOIN defect d ON d.mov_id = m.id ORDER BY 1",
    "mfg-006": "SELECT l.shift_cd, COUNT(*) FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id GROUP BY l.shift_cd ORDER BY 2 DESC, 1",
    "mfg-007": "SELECT u.title, COUNT(*) FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd GROUP BY u.title ORDER BY 2 DESC, 1",
    "mfg-008": "SELECT p.title, COUNT(*) FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.id, p.title ORDER BY 2 DESC, 1",

    "hr-001": "SELECT status_cd, COUNT(*) FROM emp GROUP BY status_cd ORDER BY 2 DESC, 1",
    # the plausible miss: unpaid leave has no leaving date and is not working
    "hr-002": "SELECT COUNT(*) FROM emp WHERE left_at IS NULL",
    # the plausible miss: every pay row, not the latest one per person
    "hr-003": "SELECT e.full_name, p.amount_minor / 100.0 FROM emp e JOIN pay_hist p ON p.emp_id = e.id ORDER BY 2 DESC, 1 LIMIT 5",
    "hr-004": "SELECT d.title, COUNT(*) FROM emp e JOIN dept d ON d.id = e.dept_id GROUP BY d.title ORDER BY 2 DESC, 1",
    "hr-005": "SELECT DISTINCT e.full_name FROM emp e JOIN pay_hist p ON p.emp_id = e.id ORDER BY 1",
    "hr-006": "SELECT e.mgr_id, COUNT(*) FROM emp e GROUP BY e.mgr_id ORDER BY 2 DESC, 1 LIMIT 5",
    "hr-007": "SELECT k.title, COUNT(*) FROM absence a JOIN absence_kind_ref k ON k.cd = a.kind_cd GROUP BY k.title ORDER BY 2 DESC, 1",
    "hr-008": "SELECT c.title, COUNT(*) FROM pay_hist p JOIN cur_ref c ON c.cd = p.cur_cd GROUP BY c.title ORDER BY 2 DESC, 1",
}


@pytest.mark.parametrize("tid,naive_sql", sorted(NAIVE.items()))
def test_the_trap_actually_bites(dbs, tid, naive_sql):
    domain, task = next((d, t) for d, t in TASKS if t.tid == tid)
    gold = dbs[domain.name].execute(task.gold_sql).fetchall()
    naive = dbs[domain.name].execute(naive_sql).fetchall()
    assert gold != naive, f"{tid}: наивный запрос даёт тот же ответ, ловушка не работает"


def test_every_task_with_a_trap_has_a_naive_counterexample():
    # Without this, a task can quietly lose its counterexample and nobody finds
    # out that the trap stopped discriminating.
    missing = [t.tid for _, t in TASKS if t.tid not in NAIVE]
    assert missing == [], f"нет наивного контрпримера: {missing}"


def test_the_inclusive_deadline_has_cases_sitting_exactly_on_it(dbs):
    # gov-002 only discriminates if some cases closed on the due date: those
    # are the ones a strict comparison gets wrong, in either direction.
    n = dbs["public_services"].execute(
        "SELECT COUNT(*) FROM case_rec WHERE closed_at = due_dt").fetchone()[0]
    assert n > 0


def test_pay_history_really_has_several_rows_per_person(dbs):
    # hr-003 is about the latest row per person, which is only hard when more
    # than one exists.
    n = dbs["hr"].execute(
        "SELECT COUNT(*) FROM (SELECT emp_id FROM pay_hist GROUP BY emp_id "
        "HAVING COUNT(*) > 1)").fetchone()[0]
    assert n > 0


def test_units_really_differ_within_one_table(dbs):
    # mfg-002 is about conversion, which needs more than one unit in use.
    units = [r[0] for r in dbs["manufacturing"].execute(
        "SELECT DISTINCT unit_cd FROM mov")]
    assert len(units) > 1


def test_price_windows_do_not_overlap(dbs):
    # Overlapping windows would make mfg-004 ambiguous rather than hard: a
    # movement would match two prices and the gold query would be wrong too.
    n = dbs["manufacturing"].execute(
        "SELECT COUNT(*) FROM part_price a JOIN part_price b "
        "ON a.part_id = b.part_id AND a.id < b.id "
        "WHERE a.valid_to IS NULL OR (b.valid_from < a.valid_to "
        "AND (b.valid_to IS NULL OR a.valid_from < b.valid_to))"
    ).fetchone()[0]
    assert n == 0, "окна цен пересекаются, эталон mfg-004 неоднозначен"


def test_the_manager_reference_has_no_cycles(dbs):
    # A cycle would make any question about managers unanswerable, and the
    # safety check forbids the recursive query that would detect one at runtime.
    rows = dict(dbs["hr"].execute("SELECT id, mgr_id FROM emp WHERE mgr_id IS NOT NULL"))
    for start in rows:
        seen, cur = {start}, rows.get(start)
        while cur is not None:
            assert cur not in seen, f"цикл в mgr_id около {cur}"
            seen.add(cur)
            cur = rows.get(cur)
