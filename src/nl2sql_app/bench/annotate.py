"""Schema notes: the facts a model cannot infer and an end user does not know.

The hand review of set 1 split its 62 traps by who holds the missing
information. 29 of them are schema semantics: `amt_cents` is cents,
`status_cd = 1` is active, `dt_op` and `posted_at` are one field left in two
columns by a migration. On tasks carrying only that kind of trap
Qwen2.5-Coder-14B scored 39%; on tasks with no such trap it scored 90%, both
on the relaxed measure; strictly the same split is 31.6% and 68.8%, which
`scripts/by_trap.py` computes into the summary files. The
model is not weak at SQL, it is blind to what the columns mean.

Asking the person who typed the question is the wrong fix. They do not know
whether cost is in cents either, and demanding it teaches them the product is
guessing. The fact lives in the database, so it is read from the database.

Everything here is derived from the schema and from the contents of small
lookup tables. Nothing reads a question, a task file or a gold query, which is
the property that makes this a product feature rather than a benchmark hack:
it runs on a database nobody has seen. The notes give the model only what a
join could already have reached, which is what those traps were about.

Two interventions, kept apart on purpose so a run can tell them apart.

`foreign_keys` is not inference at all. The databases declare their keys, and
`serialize_schema` was throwing them away: the model saw
`shp(id, cust_id, org_cd, dst_cd, ...)` and had no way to learn that org_cd
points at loc_ref. Printing what the DDL already says is a serialization fix.

`schema_notes` is the semantic part, four deliberately dumb detectors:

units     a name ending in a unit suffix. `_cents`/`_minor` is hundredths of a
          currency unit, `_bp` is basis points, a hundredth of a percent.

codes     a column standing in for a label, found by declared foreign key
          first and by name second, because the same schemas declare
          `shp.org_cd -> loc_ref.cd` and leave `shp.status_cd -> status_ref`
          undeclared. The note carries the lookup table's rows in full, so
          "active" stops being a word the model has to guess a number for and
          `unit_ref.to_base` arrives with the conversion factor attached.

date pair two date columns in one table never both filled in the same row.
          Mutual exclusivity is what a migrated field looks like and what
          separates it from two genuine events: on set 1 it splits the five
          real pairs from the four coincidences with nothing in between
          (`dispatched_at`/`delivered_at` share 363 rows, `dt_op`/`posted_at`
          share none), so no human confirmation step is needed.

history   a table where a foreign key repeats and a validity date begins the
          row. With a closing column it is a range and an open end means
          still in force; without one, the current row is the latest start per
          key.

One class is deliberately left out. A loan with `closed_at IS NULL` is open,
but a shipment with `delivered_at IS NOT NULL` is not necessarily delivered,
because a lost one can carry a delivery attempt. The two look identical to any
rule phrased over names and nullability, so a note would be right once and
wrong once. That residue is what a person who knows the business has to
answer, and it is the honest limit of doing this mechanically.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

# A lookup table is only worth quoting if the whole thing fits in the prompt.
# Above this it is cheaper to name it and let the model join, which it does.
MAX_LOOKUP_ROWS = 24

# What counts as a dictionary table. Two signals, because neither survives a
# database someone else designed. Size is the general one: a table of twenty
# rows that other tables point at is a lookup whatever it is called, and the
# first version of this file instead required the name to end in `_ref`, which
# is a convention of the schemas in `data/holdout` and of nothing else. On
# Chinook or on a shop database that detector would have found nothing and the
# feature would have shipped as a benchmark artefact. The name is the fallback,
# for the dictionaries a size test misses: five hundred diagnosis codes are
# still a dictionary.
LOOKUP_NAME = re.compile(r"(_ref|_lookup|_dict|_codes?|_types?)$", re.I)
# A small table with many columns is configuration, not a dictionary.
MAX_LOOKUP_COLS = 6

# The notes are English because the prompt and the column names are. The
# Russian stage differs only in the question, so one language for the notes
# keeps the two stages comparable instead of adding a second variable.
UNITS = (
    (re.compile(r"_(cents|minor)$"), "minor_units"),
    (re.compile(r"_bp$"), "basis_points"),
)

# A note is a kind plus the names it is about, and the English sentence is one
# rendering of it. The desktop application shows the same notes to the person
# in the language of its interface, and it can only do that from the parts.
# Rendering from a template also means there is one wording and not two: a
# sentence edited for the prompt cannot drift away from the sentence on screen,
# because they are the same template.
TEMPLATES = {
    # The divisor is written 100.0 and says why. "Divide by 100" is what the
    # first version said, the model did exactly that, and SQLite's integer
    # division threw the fraction away: a total of 8 579 947.13 came back as
    # 8 579 038, which is not a rounding difference but a loss of a sum of
    # money per row. Four of the sixteen real errors on the English wordings
    # were this and nothing else, and before the notes existed there was one,
    # so the note created the failure it was meant to prevent.
    "minor_units": "{table}.{column}: stored in minor units, hundredths of a "
                   "currency unit: divide by 100.0, not by 100, because "
                   "integer division in SQLite drops the fraction",
    "basis_points": "{table}.{column}: basis points, hundredths of a percent: "
                    "divide by 100.0 for a percentage, not by 100, because "
                    "integer division in SQLite drops the fraction",
    "code": "{table}.{column}: a code ({ref}): {rows}",
    "code_opaque": "{table}.{column}: a code, decoded in {ref}",
    "date_pair": "{table}: {a} and {b} are one field split by a migration, "
                 "exactly one is filled per row: use COALESCE({a}, {b})",
    "history_range": "{table}: rows are effective-dated per {key}; {end} IS "
                     "NULL means still in force; match on {start} <= date < "
                     "{end}",
    "history_latest": "{table}: history per {key}; the current row is the "
                      "latest {start} for each {key}",
}


@dataclass(frozen=True)
class Note:
    """One fact about one table, before it is put into words."""

    kind: str
    fields: dict[str, str]

    def render(self, templates: dict[str, str] | None = None) -> str:
        return (templates or TEMPLATES)[self.kind].format(**self.fields)
DATE_NAME = re.compile(r"(^dt_|_at$|_dt$|_from$|_to$)")
VALID_FROM = re.compile(r"(^from_dt$|^valid_from$|^effective_from$)")
VALID_TO = re.compile(r"(^to_dt$|^valid_to$|^valid_until$|^effective_to$)")


def _tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]


def _columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [(r[1], (r[2] or "").upper()) for r in rows]


def _fks(conn: sqlite3.Connection, table: str) -> list[tuple[str, str, str]]:
    """Declared foreign keys of one table as (column, target table, target column)."""
    rows = conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
    return [(r[3], r[2], r[4]) for r in rows if r[3] and r[2]]


def keys_from(conn: sqlite3.Connection,
              tables: list[str] | None = None) -> list[str]:
    """Every declared key, on a connection the caller owns.

    The connection is a parameter and not a path because the desktop
    application opens its own: read-only, bounded in time by a progress
    handler and bounded in the size of one value, and those bounds are the
    reason it can run this over a database nobody has seen. Duplicating the
    detectors there instead would have let the shipped behaviour drift away
    from the behaviour that was measured.
    """
    names = _tables(conn)
    if tables is not None:
        names = [t for t in names if t in tables]
    out = []
    for t in names:
        for col, ref, refcol in _fks(conn, t):
            out.append(f"{t}.{col} -> {ref}.{refcol}")
    return out


def foreign_keys(db_path: str, tables: list[str] | None = None) -> list[str]:
    """Every declared key, which `serialize_schema` does not print."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return keys_from(conn, tables)
    finally:
        conn.close()


def _row_cap(conn: sqlite3.Connection, table: str, cap: int) -> int | None:
    """Rows, counted no further than cap + 1, or None when it cannot be read.

    `COUNT(*)` on a fact table of fifty million rows is a full scan, and this
    runs over every table in a database the moment one is opened. Counting
    inside a LIMIT stops at the only question being asked, which is whether
    the table is small.
    """
    try:
        return conn.execute(
            f'SELECT COUNT(*) FROM (SELECT 1 FROM "{table}" LIMIT {cap + 1})'
        ).fetchone()[0]
    except sqlite3.Error:
        return None


def _lookups(conn: sqlite3.Connection, names: list[str]) -> list[str]:
    """The tables that behave like dictionaries, by size or by name."""
    out = []
    for t in names:
        if LOOKUP_NAME.search(t):
            out.append(t)
            continue
        cols = _columns(conn, t)
        if not cols or len(cols) > MAX_LOOKUP_COLS:
            continue
        n = _row_cap(conn, t, MAX_LOOKUP_ROWS)
        if n and n <= MAX_LOOKUP_ROWS:
            out.append(t)
    return out


def _lookup_rows(conn: sqlite3.Connection, ref: str) -> list[tuple] | None:
    """A lookup table in full, or None when it is too big to quote.

    Every column, not just a key and a label: `unit_ref` carries `to_base`,
    the factor that converts pieces, kilograms and tonnes to one scale, and a
    note that dropped it would answer half of that task.
    """
    n = _row_cap(conn, ref, MAX_LOOKUP_ROWS)
    if not n or n > MAX_LOOKUP_ROWS:
        return None
    cols = [c for c, _ in _columns(conn, ref)]
    quoted = ", ".join(f'"{c}"' for c in cols)
    rows = conn.execute(f'SELECT {quoted} FROM "{ref}" ORDER BY 1').fetchall()
    return rows


def _render_lookup(conn: sqlite3.Connection, ref: str, rows: list[tuple]) -> str:
    cols = [c for c, _ in _columns(conn, ref)]
    if len(cols) == 2:
        return ", ".join(f"{a}={b}" for a, b in rows)
    body = "; ".join(
        "(" + ", ".join(f"{c}={v}" for c, v in zip(cols, r, strict=True)) + ")"
        for r in rows
    )
    return body


def _norm(name: str) -> str:
    """A name with case and separators removed: GenreId and genre_id agree."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _stem(ref: str) -> str:
    """What a dictionary is a dictionary of: cur_ref -> cur, genres -> genre."""
    out = LOOKUP_NAME.sub("", ref).lower()
    if out == ref.lower() and len(out) > 3 and out.endswith("s") \
            and not out.endswith("ss"):
        out = out[:-1]
    return out


def _code_targets(conn: sqlite3.Connection, table: str,
                  cols: list[tuple[str, str]], refs: list[str]
                  ) -> list[tuple[str, str]]:
    """(column, lookup table) pairs, from declared keys first then from names.

    Declared keys come first because they are facts and they catch what names
    cannot: `shp.org_cd` and `shp.dst_cd` both point at `loc_ref`, which no
    rule over the string "loc" would find. Names are the fallback because the
    same schemas leave `status_cd -> status_ref` and `dx.code -> dx_ref`
    undeclared, and a product cannot assume a tidy DDL.
    """
    found: dict[str, str] = {}
    for col, ref, _ in _fks(conn, table):
        if ref in refs:
            found[col] = ref
    # Names are compared with case and separators removed, because SQLite
    # identifiers are case-insensitive and because the databases people
    # actually open spell a key GenreId where mine spell it genre_id. A rule
    # that only matches exact lower case with underscores works on my schemas
    # and on nothing downloaded.
    names = {_norm(n): n for n, _ in cols}
    taken = {_norm(c) for c in found}
    for ref in refs:
        stem = _stem(ref)
        short = stem.split("_")[-1]           # mov_kind_ref -> kind
        cands = [stem, f"{stem}_cd", f"{stem}_code", f"{stem}_id",
                 short, f"{short}_cd", f"{short}_code", f"{short}_id"]
        # The lookup's own key name is only safe to match when this table is
        # the one the lookup is named for. Allowing it generally made every
        # `cd` column in the database claim the first lookup it was compared
        # against, so `mode_ref.cd` came back annotated as a location.
        if stem and (stem == table.lower() or stem in table.lower().split("_")):
            cands.append(next((c for c, _ in _columns(conn, ref)), None))
        for cand in cands:
            if not cand:
                continue
            key = _norm(cand)
            if key in names and key != "id" and key not in taken:
                found[names[key]] = ref
                taken.add(key)
                break
    return sorted(found.items())


def _unit_notes(cols: list[tuple[str, str]], table: str) -> list[Note]:
    out = []
    for name, _ in cols:
        for pattern, kind in UNITS:
            if pattern.search(name):
                out.append(Note(kind, {"table": table, "column": name}))
    return out


def _code_notes(conn: sqlite3.Connection, table: str,
                cols: list[tuple[str, str]], refs: list[str]) -> list[Note]:
    out = []
    for col, ref in _code_targets(conn, table, cols, refs):
        rows = _lookup_rows(conn, ref)
        base = {"table": table, "column": col, "ref": ref}
        if rows is None:
            out.append(Note("code_opaque", base))
        else:
            out.append(Note("code",
                            base | {"rows": _render_lookup(conn, ref, rows)}))
    return out


def _date_pair_notes(conn: sqlite3.Connection, table: str,
                     cols: list[tuple[str, str]]) -> list[Note]:
    """Columns that are one migrated field, told apart by mutual exclusivity."""
    dates = [n for n, _ in cols if DATE_NAME.search(n)]
    out = []
    for i, a in enumerate(dates):
        for b in dates[i + 1:]:
            q = (f'SELECT SUM("{a}" IS NULL AND "{b}" IS NOT NULL), '
                 f'SUM("{a}" IS NOT NULL AND "{b}" IS NULL), '
                 f'SUM("{a}" IS NOT NULL AND "{b}" IS NOT NULL) FROM "{table}"')
            try:
                only_b, only_a, both = conn.execute(q).fetchone()
            except sqlite3.Error:
                continue
            # Both sides must be used somewhere, or there is no pair to report,
            # and a single shared row is enough to mean two separate events.
            if (only_a or 0) > 0 and (only_b or 0) > 0 and not (both or 0):
                out.append(Note("date_pair",
                                {"table": table, "a": a, "b": b}))
    return out


def _history_notes(conn: sqlite3.Connection, table: str,
                   cols: list[tuple[str, str]]) -> list[Note]:
    """Effective-dated rows: a repeated key plus a validity start."""
    names = [n for n, _ in cols]
    start = next((n for n in names if VALID_FROM.search(n)), None)
    if start is None:
        return []
    end = next((n for n in names if VALID_TO.search(n)), None)
    for key in (n for n in names if n.endswith("_id") and n != "id"):
        total, distinct = conn.execute(
            f'SELECT COUNT("{key}"), COUNT(DISTINCT "{key}") FROM "{table}"'
        ).fetchone()
        if not distinct or total <= distinct:
            continue  # the key does not repeat, so there is no history here
        if end:
            return [Note("history_range", {"table": table, "key": key,
                                           "start": start, "end": end})]
        return [Note("history_latest", {"table": table, "key": key,
                                        "start": start})]
    return []


def detail_from(conn: sqlite3.Connection,
                tables: list[str] | None = None) -> list[Note]:
    """Every note the four detectors find, in parts rather than in words."""
    names = _tables(conn)
    refs = _lookups(conn, names)
    if tables is not None:
        # Lookup tables stay in scope even when the linker dropped them: a
        # code is useless without its labels, and the note costs less than
        # the table.
        names = [t for t in names if t in tables]
    out: list[Note] = []
    for t in names:
        cols = _columns(conn, t)
        out += _unit_notes(cols, t)
        # A dictionary is also a user of other dictionaries. `line` holds four
        # rows, so it is one, and it still has a shift_cd that needs decoding.
        # Excluding the whole table lost exactly that note, so what is
        # excluded is narrower: a dictionary does not get its own key
        # annotated as a code pointing somewhere else, which is the garbage
        # the exclusion was added for (`mode_ref.cd: a code (loc_ref)`).
        out += _code_notes(conn, t, cols, [r for r in refs if r != t])
        out += _date_pair_notes(conn, t, cols)
        out += _history_notes(conn, t, cols)
    return out


def notes_from(conn: sqlite3.Connection,
               tables: list[str] | None = None) -> list[str]:
    """The same notes as English sentences, which is what a prompt takes."""
    return [n.render() for n in detail_from(conn, tables)]


def schema_notes(db_path: str, tables: list[str] | None = None) -> list[str]:
    """Every note the four detectors find, in table order."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return notes_from(conn, tables)
    finally:
        conn.close()


def annotate_schema(db_path: str, tables: list[str] | None = None,
                    notes: bool = True, keys: bool = False) -> str:
    """The requested blocks as prompt text, empty when there is nothing to say."""
    blocks = []
    if keys:
        fk = foreign_keys(db_path, tables)
        if fk:
            blocks.append("Foreign keys:\n" + "\n".join(f"- {k}" for k in fk))
    if notes:
        n = schema_notes(db_path, tables)
        if n:
            blocks.append("Notes on the columns:\n"
                          + "\n".join(f"- {x}" for x in n))
    return "\n\n".join(blocks)
