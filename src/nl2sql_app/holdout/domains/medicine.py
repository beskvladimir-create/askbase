"""Medicine domain.

Chosen first because RedSQL found it the hardest for every model it tested:
GPT-4o scored 0.333 there and Gemini Flash 0.044, against 0.565 and 0.457 on
aviation. Hard domains are the point; an easy one would flatter us.

Country-neutral by design (decision of 20.10.2026: the product is global), so
no national identifier formats and no local legislation. The difficulty comes
from the schema and the terminology, not from locale trivia.

The warts here, each deliberate:
  - `pat.dt_b` and `pat.sex_cd`: opaque abbreviations, no comments
  - `sex_cd`, `enc.status_cd`, `rx.route_cd`: integer codes, not words, so a
    filter cannot be written without looking at the lookup table
  - `enc.dt_adm` vs `enc.admitted_at`: a legacy duplicate, one of them is NULL
    for newer rows, which is how real tables rot after a migration
  - `dx.code` holds diagnosis codes while `dx_ref.title` holds the human name,
    so "diabetes" has to be resolved through a join, never a LIKE on the code
"""
from __future__ import annotations

from ..schema_spec import Domain, Table, Task

TABLES = (
    Table(
        name="pat",
        ddl="""
CREATE TABLE pat (
    id        INTEGER PRIMARY KEY,
    full_name TEXT    NOT NULL,
    dt_b      TEXT    NOT NULL,
    sex_cd    INTEGER NOT NULL,
    city      TEXT
)""",
        coded_columns=("sex_cd",),
    ),
    Table(
        name="sex_ref",
        ddl="""
CREATE TABLE sex_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="doc",
        ddl="""
CREATE TABLE doc (
    id        INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    dept      TEXT NOT NULL,
    hired_at  TEXT NOT NULL
)""",
    ),
    Table(
        name="enc",
        ddl="""
CREATE TABLE enc (
    id          INTEGER PRIMARY KEY,
    pat_id      INTEGER NOT NULL REFERENCES pat(id),
    doc_id      INTEGER NOT NULL REFERENCES doc(id),
    dt_adm      TEXT,
    admitted_at TEXT,
    discharged  TEXT,
    status_cd   INTEGER NOT NULL
)""",
        coded_columns=("status_cd",),
    ),
    Table(
        name="status_ref",
        ddl="""
CREATE TABLE status_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="dx",
        ddl="""
CREATE TABLE dx (
    id     INTEGER PRIMARY KEY,
    enc_id INTEGER NOT NULL REFERENCES enc(id),
    code   TEXT    NOT NULL,
    primary_flag INTEGER NOT NULL
)""",
    ),
    Table(
        name="dx_ref",
        ddl="""
CREATE TABLE dx_ref (
    code  TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    chapter TEXT NOT NULL
)""",
    ),
    Table(
        name="rx",
        ddl="""
CREATE TABLE rx (
    id       INTEGER PRIMARY KEY,
    enc_id   INTEGER NOT NULL REFERENCES enc(id),
    drug     TEXT    NOT NULL,
    route_cd INTEGER NOT NULL,
    days     INTEGER NOT NULL
)""",
        coded_columns=("route_cd",),
    ),
    Table(
        name="route_ref",
        ddl="""
CREATE TABLE route_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
)

# Lookup contents are fixed, not generated: they are part of the schema's
# meaning, and a model is expected to reach them through a join.
LOOKUPS: dict[str, list[tuple]] = {
    "sex_ref": [(1, "male"), (2, "female")],
    "status_ref": [(0, "planned"), (1, "active"), (2, "discharged"), (3, "cancelled")],
    "route_ref": [(1, "oral"), (2, "intravenous"), (3, "topical"), (4, "inhalation")],
}

TASKS = (
    Task(
        tid="med-001",
        gold_sql="""
SELECT r.title AS sex, COUNT(*) AS n
FROM pat p JOIN sex_ref r ON r.cd = p.sex_cd
GROUP BY r.title
ORDER BY n DESC
""",
        en=(
            "How many patients are there of each sex?",
            "Break the patient list down by sex and give me the counts.",
        ),
        ru=(
            "Сколько пациентов каждого пола?",
            "Разбей пациентов по полу и покажи количество в каждой группе.",
        ),
        traps=("sex is a code, needs the lookup join",),
    ),
    Task(
        tid="med-002",
        gold_sql="""
SELECT d.full_name, COUNT(*) AS n
FROM enc e JOIN doc d ON d.id = e.doc_id
WHERE e.status_cd = 2
GROUP BY d.full_name
ORDER BY n DESC, d.full_name
LIMIT 5
""",
        en=(
            "Which five doctors discharged the most patients?",
            "Give me the top five doctors by number of discharged encounters.",
        ),
        ru=(
            "Какие пять врачей выписали больше всего пациентов?",
            "Покажи пятёрку врачей с наибольшим числом выписанных случаев.",
        ),
        traps=("'discharged' is status_cd = 2, not the discharged column",),
    ),
    Task(
        tid="med-003",
        gold_sql="""
SELECT COUNT(*) AS n
FROM enc
WHERE COALESCE(dt_adm, admitted_at) >= '2026-01-01'
  AND COALESCE(dt_adm, admitted_at) <  '2026-04-01'
""",
        en=(
            "How many admissions happened in the first quarter of 2026?",
            "Count the encounters admitted between January and March 2026 inclusive.",
        ),
        ru=(
            "Сколько госпитализаций было в первом квартале 2026 года?",
            "Посчитай случаи, поступившие с января по март 2026 года включительно.",
        ),
        traps=("admission date is split across the legacy pair dt_adm/admitted_at",),
    ),
    Task(
        tid="med-004",
        gold_sql="""
SELECT x.title, COUNT(*) AS n
FROM dx JOIN dx_ref x ON x.code = dx.code
WHERE dx.primary_flag = 1
GROUP BY x.title
ORDER BY n DESC, x.title
LIMIT 3
""",
        en=(
            "What are the three most common primary diagnoses, by name?",
            "Name the top three primary diagnoses and how often each appears.",
        ),
        ru=(
            "Какие три основных диагноза встречаются чаще всего, по названию?",
            "Назови тройку самых частых основных диагнозов и сколько раз каждый встретился.",
        ),
        traps=("diagnosis name lives in dx_ref, the code alone is not an answer",),
    ),
    Task(
        tid="med-005",
        gold_sql="""
SELECT p.full_name
FROM pat p
WHERE NOT EXISTS (SELECT 1 FROM enc e WHERE e.pat_id = p.id)
ORDER BY p.full_name
""",
        en=(
            "Which patients have no encounters at all?",
            "List the patients who have never been admitted.",
        ),
        ru=(
            "У каких пациентов нет ни одного обращения?",
            "Перечисли пациентов, которые ни разу не поступали.",
        ),
        traps=("anti-join; an inner join silently returns the opposite set",),
    ),
    Task(
        tid="med-006",
        gold_sql="""
SELECT r.title AS route, AVG(x.days) AS avg_days
FROM rx x JOIN route_ref r ON r.cd = x.route_cd
GROUP BY r.title
ORDER BY avg_days DESC
""",
        en=(
            "What is the average course length for each administration route?",
            "For every route of administration, how many days does a course last on average?",
        ),
        ru=(
            "Какая средняя длительность курса для каждого способа введения?",
            "Для каждого способа введения препарата посчитай среднюю продолжительность курса в днях.",
        ),
        traps=("route is a code; AVG over days, not SUM",),
    ),
    Task(
        tid="med-007",
        gold_sql="""
SELECT d.dept, COUNT(DISTINCT e.pat_id) AS patients
FROM enc e JOIN doc d ON d.id = e.doc_id
GROUP BY d.dept
ORDER BY patients DESC, d.dept
""",
        en=(
            "How many distinct patients has each department seen?",
            "Per department, count the unique patients treated there.",
        ),
        ru=(
            "Сколько разных пациентов прошло через каждое отделение?",
            "По каждому отделению посчитай число уникальных пациентов.",
        ),
        traps=("DISTINCT patient, not encounter count",),
    ),
    Task(
        tid="med-008",
        gold_sql="""
SELECT p.full_name, COUNT(*) AS encounters
FROM enc e JOIN pat p ON p.id = e.pat_id
GROUP BY p.id, p.full_name
HAVING COUNT(*) > 2
ORDER BY encounters DESC, p.full_name
""",
        en=(
            "Which patients were admitted more than twice?",
            "Show patients with three or more encounters, and how many each had.",
        ),
        ru=(
            "Какие пациенты поступали больше двух раз?",
            "Покажи пациентов с тремя и более обращениями и число обращений у каждого.",
        ),
        traps=("HAVING, which RedSQL found models get wrong most often",),
    ),
)

DOMAIN = Domain(
    name="medicine",
    tables=TABLES,
    tasks=TASKS,
    row_counts={"pat": 400, "doc": 40, "enc": 900, "dx": 1200, "rx": 1500},
)
