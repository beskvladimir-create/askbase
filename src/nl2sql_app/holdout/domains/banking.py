"""Banking domain.

Second after medicine because RedSQL found the two hardest for every model it
tested. Hard domains are the point; an easy one would flatter us.

Country-neutral by the decision of 20.10.2026: no national account formats, no
local legislation, no tax rules. The difficulty is in the schema, not in locale
trivia a model has either memorised or not.

The warts here, each deliberate and each the source of at least one task:
  - `txn.amt_cents`: money as an integer of minor units, so any task about
    sums has to divide, and a model that answers in cents is simply wrong
  - `txn.dir_cd`: the sign of a transaction lives in a code column, not in the
    amount, so `SUM(amt_cents)` reads plausibly and answers the wrong question
  - `txn.dt_op` vs `txn.posted_at`: a legacy duplicate left by a migration,
    exactly one of the two is set per row
  - `loan.rate_bp`: interest in basis points, not per cent, with no comment
  - `cur_cd`, `resid_cd`, `status_cd`, `dir_cd`: codes, never words, so a
    filter cannot be written without reaching the lookup table
  - `mcc_ref`: the merchant category name lives away from the code, so
    "groceries" has to be resolved through a join and never matched on a code
"""
from __future__ import annotations

from datetime import date, timedelta

from ..pools import CITY, person
from ..schema_spec import Domain, Table, Task

TABLES = (
    Table(
        name="cust",
        ddl="""
CREATE TABLE cust (
    id        INTEGER PRIMARY KEY,
    full_name TEXT    NOT NULL,
    dt_reg    TEXT    NOT NULL,
    resid_cd  INTEGER NOT NULL,
    city      TEXT
)""",
        coded_columns=("resid_cd",),
    ),
    Table(
        name="resid_ref",
        ddl="""
CREATE TABLE resid_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="acct",
        ddl="""
CREATE TABLE acct (
    id        INTEGER PRIMARY KEY,
    cust_id   INTEGER NOT NULL REFERENCES cust(id),
    cur_cd    INTEGER NOT NULL,
    opened_at TEXT    NOT NULL,
    closed_at TEXT,
    status_cd INTEGER NOT NULL
)""",
        coded_columns=("cur_cd", "status_cd"),
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
        name="acct_status_ref",
        ddl="""
CREATE TABLE acct_status_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="txn",
        ddl="""
CREATE TABLE txn (
    id        INTEGER PRIMARY KEY,
    acct_id   INTEGER NOT NULL REFERENCES acct(id),
    dt_op     TEXT,
    posted_at TEXT,
    amt_cents INTEGER NOT NULL,
    dir_cd    INTEGER NOT NULL,
    mcc       TEXT    NOT NULL
)""",
        coded_columns=("dir_cd",),
    ),
    Table(
        name="dir_ref",
        ddl="""
CREATE TABLE dir_ref (
    cd    INTEGER PRIMARY KEY,
    title TEXT NOT NULL
)""",
    ),
    Table(
        name="mcc_ref",
        ddl="""
CREATE TABLE mcc_ref (
    code  TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    grp   TEXT NOT NULL
)""",
    ),
    Table(
        name="loan",
        ddl="""
CREATE TABLE loan (
    id        INTEGER PRIMARY KEY,
    cust_id   INTEGER NOT NULL REFERENCES cust(id),
    principal INTEGER NOT NULL,
    rate_bp   INTEGER NOT NULL,
    opened_at TEXT    NOT NULL,
    closed_at TEXT
)""",
    ),
)

# Lookup contents are fixed, not generated: they are part of the schema's
# meaning, and a model is expected to reach them through a join.
LOOKUPS: dict[str, list[tuple]] = {
    "resid_ref": [(1, "resident"), (2, "non-resident")],
    "cur_ref": [(1, "EUR"), (2, "USD"), (3, "GBP")],
    "acct_status_ref": [(0, "pending"), (1, "active"), (2, "frozen"), (3, "closed")],
    "dir_ref": [(1, "debit"), (2, "credit")],
}

_MCC = (
    ("5411", "grocery stores", "retail"),
    ("5812", "restaurants", "hospitality"),
    ("4111", "commuter transport", "travel"),
    ("5912", "pharmacies", "health"),
    ("6011", "cash withdrawal", "cash"),
    ("5732", "electronics stores", "retail"),
    ("7011", "hotels", "hospitality"),
    ("4814", "telecoms", "utilities"),
)

TASKS = (
    Task(
        tid="bank-001",
        gold_sql="""
SELECT c.title AS currency, COUNT(*) AS n
FROM acct a JOIN cur_ref c ON c.cd = a.cur_cd
GROUP BY c.title
ORDER BY n DESC, c.title
""",
        en=(
            "How many accounts are there in each currency?",
            "Break the accounts down by currency and give me the counts.",
        ),
        ru=(
            "Сколько счетов открыто в каждой валюте?",
            "Разбей счета по валютам и покажи количество в каждой.",
        ),
        traps=("currency is a code, needs the lookup join",),
    ),
    Task(
        tid="bank-002",
        gold_sql="""
SELECT SUM(CASE WHEN dir_cd = 2 THEN amt_cents ELSE -amt_cents END) / 100.0 AS net
FROM txn
""",
        en=(
            "What is the net movement across all transactions, in currency units?",
            "Add up the credits, take away the debits, and give the result in whole units rather than minor units.",
        ),
        ru=(
            "Каков чистый оборот по всем операциям в денежных единицах?",
            "Сложи приходы, вычти расходы и дай результат в основных единицах, а не в копейках.",
        ),
        traps=(
            "direction lives in dir_cd, not in the sign of amt_cents",
            "amounts are minor units and must be divided by 100",
        ),
    ),
    Task(
        tid="bank-003",
        gold_sql="""
SELECT COUNT(*) AS n
FROM txn
WHERE COALESCE(dt_op, posted_at) >= '2026-04-01'
  AND COALESCE(dt_op, posted_at) <  '2026-07-01'
""",
        en=(
            "How many transactions fall in the second quarter of 2026?",
            "Count the operations dated between April and June 2026 inclusive.",
        ),
        ru=(
            "Сколько операций приходится на второй квартал 2026 года?",
            "Посчитай операции, датированные с апреля по июнь 2026 года включительно.",
        ),
        traps=("operation date is split across the legacy pair dt_op/posted_at",),
    ),
    Task(
        tid="bank-004",
        gold_sql="""
SELECT m.title, COUNT(*) AS n
FROM txn t JOIN mcc_ref m ON m.code = t.mcc
GROUP BY m.title
ORDER BY n DESC, m.title
LIMIT 3
""",
        en=(
            "Which three merchant categories are used most often, by name?",
            "Name the top three spending categories and how many transactions each has.",
        ),
        ru=(
            "Какие три категории торговых точек встречаются чаще всего, по названию?",
            "Назови тройку самых частых категорий трат и число операций в каждой.",
        ),
        traps=("the category name lives in mcc_ref, the code alone is not an answer",),
    ),
    Task(
        tid="bank-005",
        gold_sql="""
SELECT c.full_name
FROM cust c
WHERE NOT EXISTS (SELECT 1 FROM acct a WHERE a.cust_id = c.id)
ORDER BY c.full_name
""",
        en=(
            "Which customers hold no account at all?",
            "List the customers who have never had an account opened for them.",
        ),
        ru=(
            "У каких клиентов нет ни одного счёта?",
            "Перечисли клиентов, которым ни разу не открывали счёт.",
        ),
        traps=("anti-join; an inner join silently returns the opposite set",),
    ),
    Task(
        tid="bank-006",
        gold_sql="""
SELECT AVG(rate_bp) / 100.0 AS avg_rate_pct
FROM loan
WHERE closed_at IS NULL
""",
        en=(
            "What is the average interest rate on open loans, as a percentage?",
            "For loans that have not been closed yet, give the mean rate in per cent.",
        ),
        ru=(
            "Какая средняя ставка по непогашенным кредитам в процентах?",
            "По кредитам, которые ещё не закрыты, посчитай среднюю ставку в процентах годовых.",
        ),
        traps=(
            "rate_bp is basis points, so the answer is a hundredth of the stored number",
            "an open loan is closed_at IS NULL, there is no status column here",
        ),
    ),
    Task(
        tid="bank-007",
        gold_sql="""
SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers
FROM acct a
JOIN cust c ON c.id = a.cust_id
JOIN resid_ref r ON r.cd = c.resid_cd
WHERE a.status_cd = 1
GROUP BY r.title
ORDER BY customers DESC, r.title
""",
        en=(
            "How many distinct customers hold an active account, by residency?",
            "Split holders of active accounts into residents and non-residents, counting each customer once.",
        ),
        ru=(
            "Сколько разных клиентов держат действующий счёт, в разрезе резидентства?",
            "Раздели владельцев действующих счетов на резидентов и нерезидентов, считая каждого клиента один раз.",
        ),
        traps=(
            "DISTINCT customer, not account count",
            "'active' is status_cd = 1, and residency is a second coded column",
        ),
    ),
    Task(
        tid="bank-008",
        gold_sql="""
SELECT c.full_name, COUNT(*) AS accounts
FROM acct a JOIN cust c ON c.id = a.cust_id
GROUP BY c.id, c.full_name
HAVING COUNT(*) > 2
ORDER BY accounts DESC, c.full_name
""",
        en=(
            "Which customers hold more than two accounts?",
            "Show customers with three or more accounts, and how many each holds.",
        ),
        ru=(
            "У каких клиентов больше двух счетов?",
            "Покажи клиентов с тремя и более счетами и число счетов у каждого.",
        ),
        traps=("HAVING, which RedSQL found models get wrong most often",),
    ),
)

DOMAIN = Domain(
    name="banking",
    tables=TABLES,
    tasks=TASKS,
    row_counts={"cust": 350, "acct": 620, "txn": 2400, "loan": 180},
)


def _iso(d: date) -> str:
    return d.isoformat()


def build_rows(rng, now: date, row_counts: dict[str, int]) -> dict[str, list[tuple]]:
    """Every non-lookup table, deterministically from the shared rng."""
    rows: dict[str, list[tuple]] = {"mcc_ref": list(_MCC)}

    n_cust = row_counts["cust"]
    rows["cust"] = [
        (
            i + 1,
            person(rng),
            _iso(now - timedelta(days=rng.randint(30, 5_000))),
            rng.choices((1, 2), weights=(82, 18))[0],
            rng.choice(CITY) if rng.random() > 0.08 else None,   # some rows lack a city
        )
        for i in range(n_cust)
    ]

    # Accounts are dealt to a prefix of the customers, so the anti-join task has
    # a non-empty answer by construction rather than by luck of the seed.
    n_acct = row_counts["acct"]
    holders = int(n_cust * 0.8)
    accounts: list[tuple] = []
    for i in range(n_acct):
        status = rng.choices((0, 1, 2, 3), weights=(6, 72, 7, 15))[0]
        opened = now - timedelta(days=rng.randint(10, 4_000))
        closed = _iso(opened + timedelta(days=rng.randint(30, 900))) if status == 3 else None
        accounts.append((
            i + 1,
            rng.randint(1, holders),
            rng.choices((1, 2, 3), weights=(55, 30, 15))[0],
            _iso(opened),
            closed,
            status,
        ))
    rows["acct"] = accounts

    n_txn = row_counts["txn"]
    txns: list[tuple] = []
    for i in range(n_txn):
        op = now - timedelta(days=rng.randint(0, 540))
        # The legacy split: rows older than a year kept the old column, newer
        # rows use the new one. Exactly one of the two is ever populated.
        old_row = (now - op).days > 365
        txns.append((
            i + 1,
            rng.randint(1, n_acct),
            _iso(op) if old_row else None,
            None if old_row else _iso(op),
            rng.randint(120, 480_00),
            rng.choices((1, 2), weights=(68, 32))[0],
            rng.choice(_MCC)[0],
        ))
    rows["txn"] = txns

    n_loan = row_counts["loan"]
    loans: list[tuple] = []
    for i in range(n_loan):
        opened = now - timedelta(days=rng.randint(60, 3_000))
        closed = _iso(opened + timedelta(days=rng.randint(180, 1_500))) if rng.random() < 0.45 else None
        loans.append((
            i + 1,
            rng.randint(1, holders),
            rng.randint(500, 90_000) * 100,
            rng.randint(310, 1_940),          # basis points, i.e. 3.10% to 19.40%
            _iso(opened),
            closed,
        ))
    rows["loan"] = loans
    return rows
