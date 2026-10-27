"""Manufacturing domain.

Here for the difficulty the other domains cannot express: quantities that are
not in the same unit. Material movements are recorded in whatever unit the line
used, with a unit code beside the number and a conversion table to the base
unit. `SUM(qty)` is the query anyone writes and it adds kilograms to tonnes to
pieces, which produces a number that is plausible, wrong, and impossible to
spot in the answer.

The second difficulty is an effective-dated price: a part's cost comes from the
row whose validity window covers the movement's date, so the join is on a range
rather than on equality. Written as a plain join on part_id it multiplies every
movement by however many price rows the part has.

Country-neutral by the decision of 20.10.2026: no national standards, no local
certification regimes.

The warts, each deliberate:
  - `mov.qty` with `mov.unit_cd` and `unit_ref.to_base`: three units in one
    column, and the conversion lives in a lookup
  - `part_price.valid_from` / `valid_to`: a range join, with `valid_to` NULL
    meaning "still in force"
  - `mov.dt_op` vs `mov.recorded_at`: a legacy duplicate from a migration
  - `line.shift_cd`, `mov.kind_cd`: codes, never words
  - `defect.found_at` against `mov` dates: a defect can be found after the
    movement that produced it, so date arithmetic has a direction
"""
from __future__ import annotations

from datetime import date, timedelta

from ..schema_spec import Domain, Table, Task

TABLES = (
    Table(
        name="part",
        ddl="""
CREATE TABLE part (
    id    INTEGER PRIMARY KEY,
    code  TEXT    NOT NULL,
    title TEXT    NOT NULL
)""",
    ),
    Table(
        name="unit_ref",
        ddl="""
CREATE TABLE unit_ref (
    cd      INTEGER PRIMARY KEY,
    title   TEXT NOT NULL,
    to_base REAL NOT NULL
)""",
    ),
    Table(
        name="line",
        ddl="""
CREATE TABLE line (
    id       INTEGER PRIMARY KEY,
    title    TEXT    NOT NULL,
    shift_cd INTEGER NOT NULL
)""",
        coded_columns=("shift_cd",),
    ),
    Table(
        name="shift_ref",
        ddl="""
CREATE TABLE shift_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="mov",
        ddl="""
CREATE TABLE mov (
    id          INTEGER PRIMARY KEY,
    part_id     INTEGER NOT NULL REFERENCES part(id),
    line_id     INTEGER NOT NULL REFERENCES line(id),
    dt_op       TEXT,
    recorded_at TEXT,
    qty         REAL    NOT NULL,
    unit_cd     INTEGER NOT NULL,
    kind_cd     INTEGER NOT NULL
)""",
        coded_columns=("unit_cd", "kind_cd"),
    ),
    Table(
        name="mov_kind_ref",
        ddl="""
CREATE TABLE mov_kind_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="part_price",
        ddl="""
CREATE TABLE part_price (
    id         INTEGER PRIMARY KEY,
    part_id    INTEGER NOT NULL REFERENCES part(id),
    valid_from TEXT    NOT NULL,
    valid_to   TEXT,
    minor      INTEGER NOT NULL
)""",
    ),
    Table(
        name="defect",
        ddl="""
CREATE TABLE defect (
    id       INTEGER PRIMARY KEY,
    mov_id   INTEGER NOT NULL REFERENCES mov(id),
    found_at TEXT    NOT NULL,
    grade_cd INTEGER NOT NULL
)""",
        coded_columns=("grade_cd",),
    ),
    Table(
        name="grade_ref",
        ddl="""
CREATE TABLE grade_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
)

LOOKUPS: dict[str, list[tuple]] = {
    "unit_ref": [(1, "piece", 1.0), (2, "kilogram", 1.0), (3, "tonne", 1000.0)],
    "shift_ref": [(1, "day"), (2, "night")],
    "mov_kind_ref": [(1, "issue"), (2, "receipt"), (3, "scrap")],
    "grade_ref": [(1, "minor"), (2, "major"), (3, "critical")],
}

_PARTS = (
    (1, "BR-100", "bracket"),
    (2, "SH-210", "shaft"),
    (3, "PL-330", "plate"),
    (4, "GR-440", "gearwheel"),
    (5, "BU-550", "bushing"),
    (6, "SP-660", "spring"),
)
_LINES = ((1, "Assembly A", 1), (2, "Assembly B", 2), (3, "Machining", 1), (4, "Finishing", 2))

TASKS = (
    Task(
        tid="mfg-001",
        gold_sql="""
SELECT k.title AS kind, COUNT(*) AS n
FROM mov m JOIN mov_kind_ref k ON k.cd = m.kind_cd
GROUP BY k.title
ORDER BY n DESC, k.title
""",
        en=(
            "How many movements are there of each kind?",
            "Break the movements down by their type and give me the counts.",
        ),
        ru=(
            "Сколько движений каждого вида?",
            "Разбей движения по видам и покажи количество в каждой группе.",
        ),
        traps=("kind is a code, needs the lookup join",),
    ),
    Task(
        tid="mfg-002",
        gold_sql="""
SELECT SUM(m.qty * u.to_base) AS base_qty
FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd
WHERE m.kind_cd = 3
""",
        en=(
            "How much was scrapped in total, converted to the base unit?",
            "Add up the scrapped quantity, bringing every row to the same unit first.",
        ),
        ru=(
            "Сколько всего ушло в брак в пересчёте на базовую единицу?",
            "Сложи забракованное количество, приведя все строки к одной единице.",
        ),
        traps=(
            "quantities are in three different units; the factor is in unit_ref",
            "'scrap' is kind_cd = 3",
        ),
    ),
    Task(
        tid="mfg-003",
        gold_sql="""
SELECT COUNT(*) AS n
FROM mov
WHERE COALESCE(dt_op, recorded_at) >= '2026-01-01'
  AND COALESCE(dt_op, recorded_at) <  '2026-04-01'
""",
        en=(
            "How many movements fall in the first quarter of 2026?",
            "Count the movements dated between January and March 2026 inclusive.",
        ),
        ru=(
            "Сколько движений приходится на первый квартал 2026 года?",
            "Посчитай движения, датированные с января по март 2026 года включительно.",
        ),
        traps=("the date is split across the legacy pair dt_op/recorded_at",),
    ),
    Task(
        tid="mfg-004",
        gold_sql="""
SELECT p.title, SUM(m.qty * u.to_base * pp.minor / 100.0) AS cost
FROM mov m
JOIN unit_ref u ON u.cd = m.unit_cd
JOIN part p ON p.id = m.part_id
JOIN part_price pp ON pp.part_id = m.part_id
 AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from
 AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to)
GROUP BY p.title
ORDER BY cost DESC, p.title
LIMIT 3
""",
        en=(
            "Which three parts cost the most in total, at the price in force on each movement?",
            "For every part, value its movements at the price valid on the day it moved, and name the three largest.",
        ),
        ru=(
            "Какие три детали обошлись дороже всего по цене, действовавшей на день движения?",
            "Оцени движения каждой детали по цене, действовавшей в тот день, и назови три самые дорогие.",
        ),
        traps=(
            "the price is effective-dated; the join is on a range, not on equality",
            "valid_to NULL means still in force",
            "quantities need converting and the price is in minor units",
        ),
    ),
    Task(
        tid="mfg-005",
        gold_sql="""
SELECT m.id
FROM mov m
WHERE NOT EXISTS (SELECT 1 FROM defect d WHERE d.mov_id = m.id)
ORDER BY m.id
""",
        en=(
            "Which movements had no defect recorded against them?",
            "List the movements that never had a defect found.",
        ),
        ru=(
            "По каким движениям не зафиксировано ни одного дефекта?",
            "Перечисли движения, по которым дефектов не находили.",
        ),
        traps=("anti-join; an inner join silently returns the opposite set",),
    ),
    Task(
        tid="mfg-006",
        gold_sql="""
SELECT s.title AS shift, COUNT(*) AS defects
FROM defect d
JOIN mov m ON m.id = d.mov_id
JOIN line l ON l.id = m.line_id
JOIN shift_ref s ON s.cd = l.shift_cd
GROUP BY s.title
ORDER BY defects DESC, s.title
""",
        en=(
            "How many defects were found on each shift?",
            "Split the defects by whether the line runs days or nights.",
        ),
        ru=(
            "Сколько дефектов нашли в каждую смену?",
            "Раздели дефекты по тому, дневная смена на линии или ночная.",
        ),
        traps=("the shift belongs to the line, not to the defect; two joins to reach it",),
    ),
    Task(
        tid="mfg-007",
        gold_sql="""
SELECT u.title AS unit, COUNT(DISTINCT m.part_id) AS parts
FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd
GROUP BY u.title
ORDER BY parts DESC, u.title
""",
        en=(
            "How many distinct parts are measured in each unit?",
            "Per unit of measure, count the different parts recorded in it.",
        ),
        ru=(
            "Сколько разных деталей измеряется в каждой единице?",
            "По каждой единице измерения посчитай число различных деталей.",
        ),
        traps=("DISTINCT part, not a movement count",),
    ),
    Task(
        tid="mfg-008",
        gold_sql="""
SELECT p.title, COUNT(*) AS defects
FROM defect d
JOIN mov m ON m.id = d.mov_id
JOIN part p ON p.id = m.part_id
GROUP BY p.id, p.title
HAVING COUNT(*) > 10
ORDER BY defects DESC, p.title
""",
        en=(
            "Which parts have more than ten defects?",
            "Show the parts with eleven or more defects, and how many each has.",
        ),
        ru=(
            "У каких деталей больше десяти дефектов?",
            "Покажи детали с одиннадцатью и более дефектами и число дефектов у каждой.",
        ),
        traps=("HAVING, which RedSQL found models get wrong most often",),
    ),
)

DOMAIN = Domain(
    name="manufacturing",
    tables=TABLES,
    tasks=TASKS,
    row_counts={"mov": 900, "part_price": 24, "defect": 320},
)


def _iso(d: date) -> str:
    return d.isoformat()


def build_rows(rng, now: date, row_counts: dict[str, int]) -> dict[str, list[tuple]]:
    """Every non-lookup table, deterministically from the shared rng."""
    rows: dict[str, list[tuple]] = {"part": list(_PARTS), "line": list(_LINES)}

    # Four price windows per part, back to back, the last one open-ended. Built
    # as a chain so the ranges cannot overlap: overlapping windows would make
    # mfg-004 ambiguous rather than hard.
    prices: list[tuple] = []
    pid = 0
    for part_id, _, _ in _PARTS:
        start = now - timedelta(days=1_200)
        minor = rng.randint(400, 9_000)
        for step in range(4):
            end = start + timedelta(days=300)
            pid += 1
            prices.append((
                pid, part_id, _iso(start),
                None if step == 3 else _iso(end),
                minor,
            ))
            start = end
            minor = int(minor * rng.uniform(1.02, 1.18))
    rows["part_price"] = prices

    n_mov = row_counts["mov"]
    movements: list[tuple] = []
    for i in range(n_mov):
        # Inside the priced window on purpose: a movement with no price in
        # force would silently drop out of mfg-004 and make the task about
        # missing data rather than about the range join.
        op = now - timedelta(days=rng.randint(0, 1_150))
        old_row = (now - op).days > 365
        unit = rng.choices((1, 2, 3), weights=(55, 33, 12))[0]
        qty = float(rng.randint(1, 400)) if unit != 3 else round(rng.uniform(0.2, 12.0), 2)
        movements.append((
            i + 1,
            # Unevenly, on purpose. With parts drawn uniformly every one ended
            # up with more than ten defects and mfg-008's HAVING filtered
            # nothing, so the task did not discriminate. No plant makes its
            # parts in equal numbers either.
            rng.choices(range(1, len(_PARTS) + 1), weights=(34, 26, 18, 12, 7, 3))[0],
            rng.randint(1, len(_LINES)),
            _iso(op) if old_row else None,
            None if old_row else _iso(op),
            qty,
            unit,
            rng.choices((1, 2, 3), weights=(46, 42, 12))[0],
        ))
    rows["mov"] = movements

    # Defects are dealt to a prefix of the movements, so mfg-005 has a
    # non-empty answer by construction rather than by luck of the seed.
    affected = int(n_mov * 0.35)
    rows["defect"] = [
        (
            i + 1,
            rng.randint(1, affected),
            _iso(now - timedelta(days=rng.randint(0, 1_100))),
            rng.choices((1, 2, 3), weights=(58, 30, 12))[0],
        )
        for i in range(row_counts["defect"])
    ]
    return rows
