"""Logistics domain.

Third domain. Medicine and banking were chosen because RedSQL found them
hardest; this one is here for a difficulty the other two cannot express. A
shipment has an origin and a destination, and both are codes into the same
lookup table, so the gold query joins one table twice under two aliases. A
model that treats a lookup as a single join silently answers about the wrong
end of the route, and the result is a plausible table of the wrong thing.

Country-neutral by the decision of 20.10.2026: invented place names, no customs
regimes, no national carrier registries.

The warts here, each deliberate and each the source of at least one task:
  - `shp.org_cd` and `shp.dst_cd`: two codes into one `loc_ref`, the self-join
  - `shp.dt_disp` vs `shp.dispatched_at`: a legacy duplicate from a migration,
    exactly one of the two is set per row
  - `shp.status_cd` alongside `shp.delivered_at`: two ways to ask "delivered"
    that do not agree, because a lost shipment can carry a delivery attempt
  - `leg.cost_cents`: money as an integer of minor units, with no comment
  - `mode_cd`, `status_cd`, `kind_cd`: codes, never words
"""
from __future__ import annotations

from datetime import date, timedelta

from ..pools import person
from ..schema_spec import Domain, Table, Task

TABLES = (
    Table(
        name="cust",
        ddl="""
CREATE TABLE cust (
    id    INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    city  TEXT
)""",
    ),
    Table(
        name="loc_ref",
        ddl="""
CREATE TABLE loc_ref (
    cd      INTEGER PRIMARY KEY,
    title   TEXT NOT NULL,
    country TEXT NOT NULL
)""",
    ),
    Table(
        name="carr",
        ddl="""
CREATE TABLE carr (
    id      INTEGER PRIMARY KEY,
    title   TEXT    NOT NULL,
    mode_cd INTEGER NOT NULL,
    since   TEXT    NOT NULL
)""",
        coded_columns=("mode_cd",),
    ),
    Table(
        name="mode_ref",
        ddl="""
CREATE TABLE mode_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="shp",
        ddl="""
CREATE TABLE shp (
    id            INTEGER PRIMARY KEY,
    cust_id       INTEGER NOT NULL REFERENCES cust(id),
    org_cd        INTEGER NOT NULL REFERENCES loc_ref(cd),
    dst_cd        INTEGER NOT NULL REFERENCES loc_ref(cd),
    dt_disp       TEXT,
    dispatched_at TEXT,
    delivered_at  TEXT,
    status_cd     INTEGER NOT NULL,
    weight_kg     INTEGER NOT NULL
)""",
        coded_columns=("org_cd", "dst_cd", "status_cd"),
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
        name="leg",
        ddl="""
CREATE TABLE leg (
    id         INTEGER PRIMARY KEY,
    shp_id     INTEGER NOT NULL REFERENCES shp(id),
    carr_id    INTEGER NOT NULL REFERENCES carr(id),
    seq        INTEGER NOT NULL,
    dist_km    INTEGER NOT NULL,
    cost_cents INTEGER NOT NULL
)""",
    ),
    Table(
        name="inc",
        ddl="""
CREATE TABLE inc (
    id      INTEGER PRIMARY KEY,
    shp_id  INTEGER NOT NULL REFERENCES shp(id),
    kind_cd INTEGER NOT NULL,
    at      TEXT    NOT NULL
)""",
        coded_columns=("kind_cd",),
    ),
    Table(
        name="kind_ref",
        ddl="""
CREATE TABLE kind_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
)

# Lookup contents are fixed, not generated: they are part of the schema's
# meaning, and a model is expected to reach them through a join.
LOOKUPS: dict[str, list[tuple]] = {
    "mode_ref": [(1, "road"), (2, "rail"), (3, "sea"), (4, "air")],
    "status_ref": [(0, "booked"), (1, "in transit"), (2, "delivered"), (3, "lost")],
    "kind_ref": [(1, "delay"), (2, "damage"), (3, "customs hold"), (4, "reroute")],
    "loc_ref": [
        (1, "Northport", "Aldoria"),
        (2, "Eastvale", "Aldoria"),
        (3, "Marden", "Breland"),
        (4, "Lowick", "Breland"),
        (5, "Thorne", "Cavira"),
        (6, "Avelin", "Cavira"),
        (7, "Kesling", "Dornia"),
        (8, "Harrow", "Dornia"),
    ],
}

_FIRM = ("Meridian", "Alder", "Castwell", "Pirelo", "Vanta", "Orbis", "Kestrel",
         "Lumen", "Brackwater", "Solvay")
_SUFFIX = ("Freight", "Logistics", "Shipping", "Haulage", "Transit")

TASKS = (
    Task(
        tid="log-001",
        gold_sql="""
SELECT m.title AS mode, COUNT(*) AS n
FROM carr c JOIN mode_ref m ON m.cd = c.mode_cd
GROUP BY m.title
ORDER BY n DESC, m.title
""",
        en=(
            "How many carriers work in each transport mode?",
            "Break the carrier list down by mode of transport and give me the counts.",
        ),
        ru=(
            "Сколько перевозчиков работает в каждом виде транспорта?",
            "Разбей перевозчиков по виду транспорта и покажи количество в каждой группе.",
        ),
        traps=("mode is a code, needs the lookup join",),
    ),
    Task(
        tid="log-002",
        gold_sql="""
SELECT o.title AS origin, d.title AS destination, COUNT(*) AS n
FROM shp s
JOIN loc_ref o ON o.cd = s.org_cd
JOIN loc_ref d ON d.cd = s.dst_cd
GROUP BY o.title, d.title
ORDER BY n DESC, o.title, d.title
LIMIT 5
""",
        en=(
            "Which five origin and destination pairs are shipped most often, by place name?",
            "Name the top five routes, giving the place each shipment left from and the place it was going to.",
        ),
        ru=(
            "Какие пять пар отправления и назначения встречаются чаще всего, по названиям мест?",
            "Назови пятёрку самых частых маршрутов, указывая откуда ушла отправка и куда она шла.",
        ),
        traps=(
            "one lookup table joined twice under two aliases",
            "a single join answers about one end of the route and looks correct",
        ),
    ),
    Task(
        tid="log-003",
        gold_sql="""
SELECT COUNT(*) AS n
FROM shp
WHERE COALESCE(dt_disp, dispatched_at) >= '2026-07-01'
  AND COALESCE(dt_disp, dispatched_at) <  '2026-10-01'
""",
        en=(
            "How many shipments were dispatched in the third quarter of 2026?",
            "Count the shipments sent out between July and September 2026 inclusive.",
        ),
        ru=(
            "Сколько отправок ушло в третьем квартале 2026 года?",
            "Посчитай отправки, выехавшие с июля по сентябрь 2026 года включительно.",
        ),
        traps=("dispatch date is split across the legacy pair dt_disp/dispatched_at",),
    ),
    Task(
        tid="log-004",
        gold_sql="""
SELECT SUM(cost_cents) / 100.0 AS total_cost
FROM leg
""",
        en=(
            "What do all the legs cost in total, in currency units?",
            "Add up the cost of every leg and give the answer in whole units rather than minor units.",
        ),
        ru=(
            "Сколько стоят все плечи маршрутов вместе, в денежных единицах?",
            "Сложи стоимость всех плеч и дай ответ в основных единицах, а не в копейках.",
        ),
        traps=("cost is stored in minor units and must be divided by 100",),
    ),
    Task(
        tid="log-005",
        gold_sql="""
SELECT s.id
FROM shp s
WHERE NOT EXISTS (SELECT 1 FROM inc i WHERE i.shp_id = s.id)
ORDER BY s.id
""",
        en=(
            "Which shipments had no incident at all?",
            "List the shipments that never had an incident recorded against them.",
        ),
        ru=(
            "По каким отправкам не было ни одного происшествия?",
            "Перечисли отправки, по которым не зафиксировано ни одного происшествия.",
        ),
        traps=("anti-join; an inner join silently returns the opposite set",),
    ),
    Task(
        tid="log-006",
        gold_sql="""
SELECT COUNT(*) AS n
FROM shp
WHERE status_cd = 2
""",
        en=(
            "How many shipments are delivered?",
            "Count the shipments whose current state is delivered.",
        ),
        ru=(
            "Сколько отправок доставлено?",
            "Посчитай отправки, которые сейчас находятся в состоянии «доставлено».",
        ),
        traps=(
            "'delivered' is status_cd = 2, not delivered_at IS NOT NULL",
            "a lost shipment can carry a delivery attempt date, so the two disagree",
        ),
    ),
    Task(
        tid="log-007",
        gold_sql="""
SELECT l.title AS destination, COUNT(DISTINCT g.carr_id) AS carriers
FROM leg g
JOIN shp s ON s.id = g.shp_id
JOIN loc_ref l ON l.cd = s.dst_cd
GROUP BY l.title
ORDER BY carriers DESC, l.title
""",
        en=(
            "How many distinct carriers serve each destination?",
            "Per destination, count the unique carriers that have carried a leg there.",
        ),
        ru=(
            "Сколько разных перевозчиков обслуживает каждое место назначения?",
            "По каждому месту назначения посчитай число уникальных перевозчиков.",
        ),
        traps=(
            "DISTINCT carrier, not leg count",
            "the destination end of the route, not the origin",
        ),
    ),
    Task(
        tid="log-008",
        gold_sql="""
SELECT g.shp_id, SUM(g.dist_km) AS km
FROM leg g
GROUP BY g.shp_id
HAVING SUM(g.dist_km) > 3000
ORDER BY km DESC, g.shp_id
""",
        en=(
            "Which shipments travelled more than three thousand kilometres in total?",
            "Show the shipments whose legs add up to over 3000 km, with the total for each.",
        ),
        ru=(
            "Какие отправки прошли в сумме больше трёх тысяч километров?",
            "Покажи отправки, у которых сумма плеч превышает 3000 км, и общий пробег каждой.",
        ),
        traps=("HAVING on an aggregate, which RedSQL found models get wrong most often",),
    ),
)

DOMAIN = Domain(
    name="logistics",
    tables=TABLES,
    tasks=TASKS,
    row_counts={"cust": 120, "carr": 45, "shp": 700, "leg": 1800, "inc": 260},
)


def _iso(d: date) -> str:
    return d.isoformat()


def build_rows(rng, now: date, row_counts: dict[str, int]) -> dict[str, list[tuple]]:
    """Every non-lookup table, deterministically from the shared rng."""
    rows: dict[str, list[tuple]] = {}
    places = [r[0] for r in LOOKUPS["loc_ref"]]

    n_cust = row_counts["cust"]
    rows["cust"] = [
        (
            i + 1,
            f"{rng.choice(_FIRM)} {rng.choice(_SUFFIX)}",
            rng.choice([r[1] for r in LOOKUPS["loc_ref"]]) if rng.random() > 0.1 else None,
        )
        for i in range(n_cust)
    ]

    n_carr = row_counts["carr"]
    rows["carr"] = [
        (
            i + 1,
            f"{person(rng).split()[1]} {rng.choice(_SUFFIX)}",
            rng.choices((1, 2, 3, 4), weights=(52, 18, 17, 13))[0],
            _iso(now - timedelta(days=rng.randint(400, 9_000))),
        )
        for i in range(n_carr)
    ]

    n_shp = row_counts["shp"]
    shipments: list[tuple] = []
    for i in range(n_shp):
        disp = now - timedelta(days=rng.randint(0, 540))
        status = rng.choices((0, 1, 2, 3), weights=(7, 15, 72, 6))[0]
        # A delivery attempt date exists for delivered shipments and, on purpose,
        # for a few lost ones too: that is what makes status_cd and delivered_at
        # disagree, and it is the whole of task log-006.
        has_date = status == 2 or (status == 3 and rng.random() < 0.4)
        delivered = _iso(disp + timedelta(days=rng.randint(1, 40))) if has_date else None
        org = rng.choice(places)
        dst = rng.choice([p for p in places if p != org])
        # The legacy split: rows older than a year kept the old column, newer
        # rows use the new one. Exactly one of the two is ever populated.
        old_row = (now - disp).days > 365
        shipments.append((
            i + 1,
            rng.randint(1, n_cust),
            org,
            dst,
            _iso(disp) if old_row else None,
            None if old_row else _iso(disp),
            delivered,
            status,
            rng.randint(5, 24_000),
        ))
    rows["shp"] = shipments

    n_leg = row_counts["leg"]
    legs: list[tuple] = []
    seq_of: dict[int, int] = {}
    for i in range(n_leg):
        shp_id = rng.randint(1, n_shp)
        seq_of[shp_id] = seq_of.get(shp_id, 0) + 1
        legs.append((
            i + 1,
            shp_id,
            rng.randint(1, n_carr),
            seq_of[shp_id],
            rng.randint(40, 2_600),
            rng.randint(8_000, 940_000),
        ))
    rows["leg"] = legs

    # Incidents are dealt to a prefix of the shipments, so the anti-join task
    # has a non-empty answer by construction rather than by luck of the seed.
    n_inc = row_counts["inc"]
    affected = int(n_shp * 0.3)
    rows["inc"] = [
        (
            i + 1,
            rng.randint(1, affected),
            rng.choices((1, 2, 3, 4), weights=(46, 22, 20, 12))[0],
            _iso(now - timedelta(days=rng.randint(0, 540))),
        )
        for i in range(n_inc)
    ]
    return rows
