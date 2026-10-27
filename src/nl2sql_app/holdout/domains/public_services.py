"""Public services domain.

Here for two difficulties the other five do not carry.

The first is a deadline that is inclusive. A case is late when it was closed
after its due date, and "within thirty days" in the question means up to and
including the thirtieth. Written with a strict comparison the answer is off by
exactly the cases that landed on the deadline, which is a small number and a
wrong one, and nothing in the result hints at it.

The second is the same application submitted twice. People reapply, and the
duplicate carries the same applicant and the same service on a different date,
so counting applications and counting people who applied are different
questions with similar-looking queries.

Country-neutral by the decision of 20.10.2026: invented service names, no
national identifiers, no local administrative law.

The warts, each deliberate:
  - `case.due_dt` against `case.closed_at`: an inclusive deadline
  - duplicate (`applicant_id`, `service_id`) pairs across different dates
  - `office.region_cd` into `region_ref`, and `case.office_id` into `office`,
    so a question about regions needs two joins
  - `case.dt_sub` vs `case.submitted_at`: a legacy duplicate from a migration
  - `stage.result_cd` where NULL means "still open", which is not a code
"""
from __future__ import annotations

from datetime import date, timedelta

from ..pools import person
from ..schema_spec import Domain, Table, Task

TABLES = (
    Table(
        name="region_ref",
        ddl="""
CREATE TABLE region_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="office",
        ddl="""
CREATE TABLE office (
    id        INTEGER PRIMARY KEY,
    title     TEXT    NOT NULL,
    region_cd INTEGER NOT NULL REFERENCES region_ref(cd)
)""",
        coded_columns=("region_cd",),
    ),
    Table(
        name="service",
        ddl="""
CREATE TABLE service (
    id       INTEGER PRIMARY KEY,
    title    TEXT    NOT NULL,
    sla_days INTEGER NOT NULL
)""",
    ),
    Table(
        name="applicant",
        ddl="""
CREATE TABLE applicant (
    id        INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    city      TEXT
)""",
    ),
    Table(
        name="case_rec",
        ddl="""
CREATE TABLE case_rec (
    id           INTEGER PRIMARY KEY,
    applicant_id INTEGER NOT NULL REFERENCES applicant(id),
    service_id   INTEGER NOT NULL REFERENCES service(id),
    office_id    INTEGER NOT NULL REFERENCES office(id),
    dt_sub       TEXT,
    submitted_at TEXT,
    due_dt       TEXT    NOT NULL,
    closed_at    TEXT
)""",
    ),
    Table(
        name="stage",
        ddl="""
CREATE TABLE stage (
    id        INTEGER PRIMARY KEY,
    case_id   INTEGER NOT NULL REFERENCES case_rec(id),
    seq       INTEGER NOT NULL,
    result_cd INTEGER
)""",
        coded_columns=("result_cd",),
    ),
    Table(
        name="result_ref",
        ddl="""
CREATE TABLE result_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
)

LOOKUPS: dict[str, list[tuple]] = {
    "region_ref": [(1, "Northport"), (2, "Eastvale"), (3, "Marden"), (4, "Thorne")],
    "result_ref": [(1, "approved"), (2, "refused"), (3, "withdrawn")],
}

_SERVICES = (
    (1, "building permit", 30),
    (2, "business registration", 10),
    (3, "land record extract", 5),
    (4, "residence certificate", 14),
    (5, "trading licence", 21),
)
_OFFICES = (
    (1, "Northport central", 1),
    (2, "Northport east", 1),
    (3, "Eastvale office", 2),
    (4, "Marden office", 3),
    (5, "Thorne office", 4),
)

TASKS = (
    Task(
        tid="gov-001",
        gold_sql="""
SELECT r.title AS region, COUNT(*) AS n
FROM case_rec c
JOIN office o ON o.id = c.office_id
JOIN region_ref r ON r.cd = o.region_cd
GROUP BY r.title
ORDER BY n DESC, r.title
""",
        en=(
            "How many cases were submitted in each region?",
            "Break the cases down by region and give me the counts.",
        ),
        ru=(
            "Сколько дел подано в каждом регионе?",
            "Разбей дела по регионам и покажи количество в каждом.",
        ),
        traps=("the region belongs to the office, not to the case; two joins to reach it",),
    ),
    Task(
        tid="gov-002",
        gold_sql="""
SELECT COUNT(*) AS n
FROM case_rec
WHERE closed_at IS NOT NULL
  AND closed_at > due_dt
""",
        en=(
            "How many cases were closed after their deadline?",
            "Count the cases that finished late, that is after the due date rather than on it.",
        ),
        ru=(
            "Сколько дел закрыто после срока?",
            "Посчитай дела, завершённые с опозданием, то есть позже даты срока, а не в неё.",
        ),
        traps=(
            "the deadline is inclusive: closing on the due date is not late",
            "an open case has no closing date and cannot be late yet",
        ),
    ),
    Task(
        tid="gov-003",
        gold_sql="""
SELECT COUNT(DISTINCT applicant_id) AS people
FROM case_rec
""",
        en=(
            "How many different people have applied at all?",
            "Count the distinct applicants across every case, not the cases.",
        ),
        ru=(
            "Сколько разных людей вообще подавало заявления?",
            "Посчитай различных заявителей по всем делам, а не сами дела.",
        ),
        traps=("people reapply, so a case count and a people count differ",),
    ),
    Task(
        tid="gov-004",
        gold_sql="""
SELECT COUNT(*) AS n
FROM case_rec
WHERE COALESCE(dt_sub, submitted_at) >= '2026-04-01'
  AND COALESCE(dt_sub, submitted_at) <  '2026-07-01'
""",
        en=(
            "How many cases were submitted in the second quarter of 2026?",
            "Count the cases lodged between April and June 2026 inclusive.",
        ),
        ru=(
            "Сколько дел подано во втором квартале 2026 года?",
            "Посчитай дела, поданные с апреля по июнь 2026 года включительно.",
        ),
        traps=("the submission date is split across the legacy pair dt_sub/submitted_at",),
    ),
    Task(
        tid="gov-005",
        gold_sql="""
SELECT a.full_name
FROM applicant a
WHERE NOT EXISTS (SELECT 1 FROM case_rec c WHERE c.applicant_id = a.id)
ORDER BY a.full_name
""",
        en=(
            "Which registered people have never submitted a case?",
            "List the applicants with no case of their own.",
        ),
        ru=(
            "Кто из зарегистрированных ни разу не подавал дело?",
            "Перечисли заявителей, у которых нет ни одного дела.",
        ),
        traps=("anti-join; an inner join silently returns the opposite set",),
    ),
    Task(
        tid="gov-006",
        gold_sql="""
SELECT r.title AS result, COUNT(*) AS n
FROM stage s JOIN result_ref r ON r.cd = s.result_cd
GROUP BY r.title
ORDER BY n DESC, r.title
""",
        en=(
            "How many decided stages ended in each result?",
            "For the stages that have a result, break them down by what it was.",
        ),
        ru=(
            "Сколько решённых этапов закончилось каждым результатом?",
            "Для этапов, у которых есть результат, разбей их по тому, какой он.",
        ),
        traps=(
            "result_cd is NULL for a stage still open, and NULL is not a code",
            "an inner join is correct here, which is the opposite of gov-005",
        ),
    ),
    Task(
        tid="gov-007",
        gold_sql="""
SELECT sv.title, COUNT(DISTINCT c.applicant_id) AS people
FROM case_rec c JOIN service sv ON sv.id = c.service_id
GROUP BY sv.title
ORDER BY people DESC, sv.title
""",
        en=(
            "How many distinct people applied for each service?",
            "Per service, count the different applicants who asked for it.",
        ),
        ru=(
            "Сколько разных людей обращалось за каждой услугой?",
            "По каждой услуге посчитай число различных заявителей.",
        ),
        traps=("DISTINCT applicant, not a case count, because people reapply",),
    ),
    Task(
        tid="gov-008",
        gold_sql="""
SELECT a.full_name, COUNT(*) AS cases
FROM case_rec c JOIN applicant a ON a.id = c.applicant_id
GROUP BY a.id, a.full_name
HAVING COUNT(*) > 2
ORDER BY cases DESC, a.full_name
""",
        en=(
            "Which people have submitted more than two cases?",
            "Show the applicants with three or more cases, and how many each has.",
        ),
        ru=(
            "Кто подавал больше двух дел?",
            "Покажи заявителей с тремя и более делами и число дел у каждого.",
        ),
        traps=("HAVING, which RedSQL found models get wrong most often",),
    ),
)

DOMAIN = Domain(
    name="public_services",
    tables=TABLES,
    tasks=TASKS,
    row_counts={"applicant": 300, "case_rec": 760, "stage": 1500},
)


def _iso(d: date) -> str:
    return d.isoformat()


def build_rows(rng, now: date, row_counts: dict[str, int]) -> dict[str, list[tuple]]:
    """Every non-lookup table, deterministically from the shared rng."""
    rows: dict[str, list[tuple]] = {
        "service": list(_SERVICES),
        "office": list(_OFFICES),
    }

    n_app = row_counts["applicant"]
    rows["applicant"] = [
        (
            i + 1,
            person(rng),
            rng.choice([r[1] for r in LOOKUPS["region_ref"]]) if rng.random() > 0.1 else None,
        )
        for i in range(n_app)
    ]

    # Cases go to a prefix of the applicants, so gov-005 has a non-empty answer
    # by construction rather than by luck of the seed.
    filers = int(n_app * 0.8)
    sla = {s[0]: s[2] for s in _SERVICES}
    n_case = row_counts["case_rec"]
    cases: list[tuple] = []
    for i in range(n_case):
        sub = now - timedelta(days=rng.randint(0, 540))
        service = rng.randint(1, len(_SERVICES))
        due = sub + timedelta(days=sla[service])
        old_row = (now - sub).days > 365
        # Closing lands before, exactly on, or after the deadline, and the
        # "exactly on" group exists on purpose: it is the whole of gov-002,
        # where a strict comparison in either direction is wrong by that group.
        where = rng.choices(("early", "on", "late", "open"), weights=(58, 9, 21, 12))[0]
        if where == "open":
            closed = None
        elif where == "on":
            closed = _iso(due)
        elif where == "early":
            closed = _iso(due - timedelta(days=rng.randint(1, max(1, sla[service] - 1))))
        else:
            closed = _iso(due + timedelta(days=rng.randint(1, 40)))
        cases.append((
            i + 1,
            rng.randint(1, filers),
            service,
            rng.randint(1, len(_OFFICES)),
            _iso(sub) if old_row else None,
            None if old_row else _iso(sub),
            _iso(due),
            closed,
        ))
    rows["case_rec"] = cases

    n_stage = row_counts["stage"]
    seq_of: dict[int, int] = {}
    stages: list[tuple] = []
    for i in range(n_stage):
        case_id = rng.randint(1, n_case)
        seq_of[case_id] = seq_of.get(case_id, 0) + 1
        # NULL for a stage still open. Not a code: gov-006 is about telling a
        # missing value apart from a value that happens to mean "unknown".
        result = rng.choices((1, 2, 3, None), weights=(52, 19, 8, 21))[0]
        stages.append((i + 1, case_id, seq_of[case_id], result))
    rows["stage"] = stages
    return rows
