"""Human resources domain.

Here for a shape none of the first three can express: the latest row per
person. Salary lives in a history table, one row per change, and almost every
real question about pay means "the row in force now". Written naively it
returns one row per change and the totals come out several times too large,
which is the kind of wrong that looks right: the table has the right columns,
the right names, and a plausible number in it.

The second difficulty is a disagreement that mirrors medicine's and logistics'
but on the question people ask most often here. Who works here now can be read
from `status_cd` or from `left_at IS NULL`, and the two do not agree, because
somebody on unpaid leave has no leaving date and is not working.

Country-neutral by the decision of 20.10.2026: no national insurance numbers,
no local labour law, no statutory leave arithmetic.

The warts, each deliberate:
  - `pay_hist`: effective-dated rows, so the current salary is the latest
    `from_dt` per person and not a column anywhere
  - `emp.status_cd` against `emp.left_at`: two ways to ask who works here
  - `emp.mgr_id`: a self-reference, so a question about managers joins the
    same table twice under two aliases
  - `amount_minor` with `cur_cd`: pay in minor units and in several
    currencies, so a bare SUM is wrong twice over
  - `dept.parent_id`: one level of hierarchy, enough to need a self-join and
    not enough to need recursion, which the safety check forbids anyway
"""
from __future__ import annotations

from datetime import date, timedelta

from ..pools import person
from ..schema_spec import Domain, Table, Task

TABLES = (
    Table(
        name="dept",
        ddl="""
CREATE TABLE dept (
    id        INTEGER PRIMARY KEY,
    title     TEXT    NOT NULL,
    parent_id INTEGER REFERENCES dept(id)
)""",
    ),
    Table(
        name="emp",
        ddl="""
CREATE TABLE emp (
    id        INTEGER PRIMARY KEY,
    full_name TEXT    NOT NULL,
    dept_id   INTEGER NOT NULL REFERENCES dept(id),
    mgr_id    INTEGER REFERENCES emp(id),
    hired_at  TEXT    NOT NULL,
    left_at   TEXT,
    status_cd INTEGER NOT NULL
)""",
        coded_columns=("status_cd",),
    ),
    Table(
        name="emp_status_ref",
        ddl="""
CREATE TABLE emp_status_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="pay_hist",
        ddl="""
CREATE TABLE pay_hist (
    id           INTEGER PRIMARY KEY,
    emp_id       INTEGER NOT NULL REFERENCES emp(id),
    from_dt      TEXT    NOT NULL,
    amount_minor INTEGER NOT NULL,
    cur_cd       INTEGER NOT NULL
)""",
        coded_columns=("cur_cd",),
    ),
    Table(
        name="cur_ref",
        ddl="""
CREATE TABLE cur_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="absence",
        ddl="""
CREATE TABLE absence (
    id      INTEGER PRIMARY KEY,
    emp_id  INTEGER NOT NULL REFERENCES emp(id),
    kind_cd INTEGER NOT NULL,
    days    INTEGER NOT NULL,
    at      TEXT    NOT NULL
)""",
        coded_columns=("kind_cd",),
    ),
    Table(
        name="absence_kind_ref",
        ddl="""
CREATE TABLE absence_kind_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
)

LOOKUPS: dict[str, list[tuple]] = {
    "emp_status_ref": [(1, "working"), (2, "unpaid leave"), (3, "left")],
    "cur_ref": [(1, "EUR"), (2, "USD")],
    "absence_kind_ref": [(1, "annual leave"), (2, "sick"), (3, "training")],
}

_DEPTS = (
    (1, "Operations", None),
    (2, "Engineering", None),
    (3, "Platform", 2),
    (4, "Data", 2),
    (5, "Support", 1),
    (6, "Finance", None),
)

TASKS = (
    Task(
        tid="hr-001",
        gold_sql="""
SELECT s.title AS status, COUNT(*) AS n
FROM emp e JOIN emp_status_ref s ON s.cd = e.status_cd
GROUP BY s.title
ORDER BY n DESC, s.title
""",
        en=(
            "How many people are there in each employment status?",
            "Break the staff list down by status and give me the counts.",
        ),
        ru=(
            "Сколько человек в каждом статусе занятости?",
            "Разбей сотрудников по статусу и покажи количество в каждой группе.",
        ),
        traps=("status is a code, needs the lookup join",),
    ),
    Task(
        tid="hr-002",
        gold_sql="""
SELECT COUNT(*) AS n
FROM emp
WHERE status_cd = 1
""",
        en=(
            "How many people work here right now?",
            "Count the employees whose current status is working.",
        ),
        ru=(
            "Сколько человек работает сейчас?",
            "Посчитай сотрудников, у которых текущий статус «работает».",
        ),
        traps=(
            "'working' is status_cd = 1, not left_at IS NULL",
            "somebody on unpaid leave has no leaving date and is not working",
        ),
    ),
    Task(
        tid="hr-003",
        gold_sql="""
SELECT e.full_name, p.amount_minor / 100.0 AS pay
FROM emp e
JOIN pay_hist p ON p.emp_id = e.id
WHERE p.from_dt = (
    SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id
)
ORDER BY pay DESC, e.full_name
LIMIT 5
""",
        en=(
            "Who are the five highest paid people, at their current salary?",
            "Give me the top five by the salary in force today, in whole units.",
        ),
        ru=(
            "Кто пять самых высокооплачиваемых по действующей сейчас зарплате?",
            "Покажи пятёрку по зарплате, которая действует на сегодня, в основных единицах.",
        ),
        traps=(
            "salary is effective-dated; the current one is the latest from_dt per person",
            "amounts are minor units and must be divided by 100",
        ),
    ),
    Task(
        tid="hr-004",
        gold_sql="""
SELECT d.title, COUNT(*) AS n
FROM emp e JOIN dept d ON d.id = e.dept_id
WHERE e.status_cd = 1
GROUP BY d.title
ORDER BY n DESC, d.title
""",
        en=(
            "How many working people are in each department, by department name?",
            "Per department, count the staff currently working there.",
        ),
        ru=(
            "Сколько работающих в каждом подразделении, по названию подразделения?",
            "По каждому подразделению посчитай сотрудников, которые сейчас работают.",
        ),
        traps=("department name lives in dept; status is a code",),
    ),
    Task(
        tid="hr-005",
        gold_sql="""
SELECT e.full_name
FROM emp e
WHERE NOT EXISTS (SELECT 1 FROM pay_hist p WHERE p.emp_id = e.id)
ORDER BY e.full_name
""",
        en=(
            "Which employees have no salary record at all?",
            "List the people who have never had a pay row written for them.",
        ),
        ru=(
            "У каких сотрудников нет ни одной записи о зарплате?",
            "Перечисли людей, которым ни разу не заводили строку оплаты.",
        ),
        traps=("anti-join; an inner join silently returns the opposite set",),
    ),
    Task(
        tid="hr-006",
        gold_sql="""
SELECT m.full_name AS manager, COUNT(*) AS reports
FROM emp e JOIN emp m ON m.id = e.mgr_id
GROUP BY m.id, m.full_name
ORDER BY reports DESC, m.full_name
LIMIT 5
""",
        en=(
            "Which five managers have the most direct reports?",
            "Name the top five people by how many staff report straight to them.",
        ),
        ru=(
            "У каких пяти руководителей больше всего прямых подчинённых?",
            "Назови пятёрку тех, у кого больше всего людей в прямом подчинении.",
        ),
        traps=("the same table joined twice under two aliases, through mgr_id",),
    ),
    Task(
        tid="hr-007",
        gold_sql="""
SELECT k.title AS kind, SUM(a.days) AS days
FROM absence a JOIN absence_kind_ref k ON k.cd = a.kind_cd
GROUP BY k.title
ORDER BY days DESC, k.title
""",
        en=(
            "How many days were taken for each kind of absence?",
            "For every absence type, add up the days taken.",
        ),
        ru=(
            "Сколько дней взято по каждому виду отсутствия?",
            "По каждому виду отсутствия сложи количество дней.",
        ),
        traps=("kind is a code; SUM over days, not a row count",),
    ),
    Task(
        tid="hr-008",
        gold_sql="""
SELECT c.title AS title, COUNT(DISTINCT p.emp_id) AS people
FROM pay_hist p JOIN cur_ref c ON c.cd = p.cur_cd
GROUP BY c.title
HAVING COUNT(DISTINCT p.emp_id) > 2
ORDER BY people DESC, c.title
""",
        en=(
            "Which currencies are more than two people paid in?",
            "Per currency, count the distinct people paid in it, keeping only those above two.",
        ),
        ru=(
            "В каких валютах платят больше чем двум людям?",
            "По каждой валюте посчитай разных людей, оставив только те, где их больше двух.",
        ),
        traps=(
            "DISTINCT person, not a count of pay rows",
            "HAVING on the distinct count, which RedSQL found models get wrong most often",
        ),
    ),
)

DOMAIN = Domain(
    name="hr",
    tables=TABLES,
    tasks=TASKS,
    row_counts={"emp": 260, "pay_hist": 700, "absence": 420},
)


def _iso(d: date) -> str:
    return d.isoformat()


def build_rows(rng, now: date, row_counts: dict[str, int]) -> dict[str, list[tuple]]:
    """Every non-lookup table, deterministically from the shared rng."""
    rows: dict[str, list[tuple]] = {"dept": list(_DEPTS)}

    n_emp = row_counts["emp"]
    dept_ids = [d[0] for d in _DEPTS]
    employees: list[tuple] = []
    for i in range(n_emp):
        hired = now - timedelta(days=rng.randint(30, 5_000))
        status = rng.choices((1, 2, 3), weights=(72, 9, 19))[0]
        # Only someone who left has a leaving date. Unpaid leave does not, and
        # that is the whole of hr-002: "working" by status and "working" by the
        # absence of a leaving date are different sets.
        left = _iso(hired + timedelta(days=rng.randint(60, 2_000))) if status == 3 else None
        # Managers are drawn from the earlier part of the list, so the
        # self-reference never points forward and no cycle can form.
        mgr = rng.randint(1, max(1, i // 3)) if i > 8 and rng.random() < 0.8 else None
        employees.append((
            i + 1,
            person(rng),
            rng.choice(dept_ids),
            mgr,
            _iso(hired),
            left,
            status,
        ))
    rows["emp"] = employees

    # Pay rows are dealt to a prefix of the staff, so hr-005 has a non-empty
    # answer by construction rather than by luck of the seed.
    paid = int(n_emp * 0.85)
    n_pay = row_counts["pay_hist"]
    pay: list[tuple] = []
    for i in range(n_pay):
        emp_id = rng.randint(1, paid)
        pay.append((
            i + 1,
            emp_id,
            _iso(now - timedelta(days=rng.randint(0, 2_400))),
            rng.randint(2_200, 11_000) * 100,
            rng.choices((1, 2), weights=(78, 22))[0],
        ))
    rows["pay_hist"] = pay

    n_abs = row_counts["absence"]
    rows["absence"] = [
        (
            i + 1,
            rng.randint(1, n_emp),
            rng.choices((1, 2, 3), weights=(58, 28, 14))[0],
            rng.randint(1, 21),
            _iso(now - timedelta(days=rng.randint(0, 700))),
        )
        for i in range(n_abs)
    ]
    return rows
