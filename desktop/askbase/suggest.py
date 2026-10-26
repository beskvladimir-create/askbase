"""Example questions written against the schema actually open.

docs/roles.md, role 1: "example questions on screen, filled in against their
own schema", because an empty input box is a dead end for somebody who does
not know what can be asked. The application had the mechanism and one example:
"how many rows in <table>", for the first three tables in alphabetical order.
One shape, and the least interesting one, since counting rows is the question
a person is least likely to need and most likely to already know how to get.

What is produced here is four shapes, each only offered when the schema can
support it:

    count       how many rows are in <table>
    breakdown   <table> broken down by <low-cardinality column>
    ranking     the ten <table> with the largest <numeric column>
    period      how many <table> fall in a given month, by <date column>

The shapes are not templates filled at random. A breakdown is offered only for
a column the snapshot found to hold a handful of distinct values, which is the
same signal the engine uses to decide a column is a lookup. A ranking needs a
numeric column that is not an identifier, and a period needs a column whose
values look like dates. Where the schema offers none of that, the count is
still there, so the list is never empty.

Everything here is a question in words. Nothing generates SQL: the point is to
show a person what they are allowed to say, not to answer for them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A column of this type holds a number worth ranking by. TEXT and BLOB cannot,
# and an INTEGER PRIMARY KEY is an identifier, which is handled separately.
_NUMERIC = ("INT", "REAL", "FLOA", "DOUB", "NUM", "DEC", "MONEY")

# Identifiers are numeric and meaningless to rank. Matched on the whole name or
# a clear suffix, never on a substring: a column called "idle_days" is not an id.
#
# The CamelCase alternatives are not decoration. Requiring an underscore meant
# that on Chinook, the most widely used sample SQLite file in existence, the
# suggestion offered was "the ten Invoice with the largest InvoiceId" — the
# primary key, ranked. Primary keys are now also excluded by what they are,
# read from the snapshot, which is what the docstring always claimed.
_ID = re.compile(
    r"^(id|.*_id|.*_?key|.*_?code|.*_cd|.*_no|.*_num|.*[a-z](Id|Key|Code|No|Num))$"
)

_DATEISH = re.compile(r"^(dt_.*|.*_at|.*_date|date.*|.*_on|.*day|created|updated|joined|placed)$", re.I)
_DATE_TYPE = ("DATE", "TIME")
_DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Suggestion:
    kind: str
    text: str


def _is_numeric(decl: str) -> bool:
    return any(k in decl for k in _NUMERIC)


def _looks_like_a_date(name: str, decl: str, samples: dict[str, list[str]]) -> bool:
    if any(k in decl for k in _DATE_TYPE):
        return True
    if _DATEISH.match(name):
        return True
    # Last resort: a sampled value shaped like a date, for a column whose name
    # gives nothing away. Two bugs lived in this line. The snapshot stores a
    # sample as a sentence ("period is one of '2026-01-01', ..."), and the
    # pattern was anchored with ^, so it could never match and the fallback was
    # dead. Un-anchoring it alone would have been worse: the whole table's
    # samples were passed in, so one dated column made every column in the
    # table answer True. The samples are now indexed by column.
    return any(_DATE_VALUE.search(v) for v in samples.get(name, []))


def _values_by_column(schema, table: str) -> dict[str, list[str]]:
    """The sampled values, per column, parsed out of the snapshot's sentences."""
    out: dict[str, list[str]] = {}
    for hint in schema.samples.get(table, []):
        name, sep, rest = hint.partition(" is one of ")
        if sep and name in schema.tables.get(table, []):
            out[name] = [v.strip().strip("'\"") for v in rest.split(",")]
    return out


def _coded_columns(schema, table: str) -> list[str]:
    """Columns the snapshot found to hold a handful of distinct values.

    The snapshot stores these as sentences ("status is one of 'new', 'paid'"),
    because that is the form the model is shown. The column name is the part
    before " is one of ", and reading it back here keeps one source of truth
    for what counts as a lookup.
    """
    out = []
    for hint in schema.samples.get(table, []):
        name, sep, _ = hint.partition(" is one of ")
        if sep and name in schema.tables.get(table, []):
            out.append(name)
    return out


def for_schema(schema, texts: dict, limit: int = 4) -> list[Suggestion]:
    """Up to `limit` questions, in the interface language, best shapes first.

    Tables are considered in the order the snapshot lists them, which is the
    database's own alphabetical order, so the same database always produces the
    same suggestions. A person who learns the list should find it where they
    left it.
    """
    tables = list(schema.tables)
    if not tables:
        return []

    picked: list[Suggestion] = []
    seen_kinds: set[str] = set()

    def add(kind: str, key: str, **fmt) -> None:
        # One of each shape before a second of any, so the list teaches four
        # different things rather than the same thing four times.
        if kind in seen_kinds or len(picked) >= limit:
            return
        picked.append(Suggestion(kind, texts[key].format(**fmt)))
        seen_kinds.add(kind)

    for table in tables:
        cols = schema.tables.get(table, [])
        decls = schema.types.get(table, {})
        samples = _values_by_column(schema, table)
        keys = schema.keys.get(table, set()) if hasattr(schema, "keys") else set()

        for col in _coded_columns(schema, table):
            add("breakdown", "ex_breakdown", table=table, column=col)
            break

        for col in cols:
            decl = decls.get(col, "")
            if _is_numeric(decl) and not _ID.match(col) and col not in keys:
                add("ranking", "ex_ranking", table=table, column=col)
                break

        for col in cols:
            if _looks_like_a_date(col, decls.get(col, ""), samples):
                add("period", "ex_period", table=table, column=col)
                break

        if len(picked) >= limit:
            break

    # The count goes last in preference but is never missing: a schema with
    # nothing but opaque text columns still gets one thing to try.
    add("count", "ex_count", table=tables[0])
    return picked[:limit]
