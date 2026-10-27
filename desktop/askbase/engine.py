"""Connect to a database, turn a question into SQL, and run it safely.

No Qt in here on purpose: everything below is testable without an interface,
and the window is a thin layer over it.

The order of operations is the product's promise in code form. The model never
touches the database. It is handed a schema snapshot and returns text; that
text is parsed and checked before anything is executed, and the connection it
is executed on is read-only.
"""
from __future__ import annotations

import contextlib
import csv
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import sqlglot
from sqlglot import exp

from nl2sql_app.safety import check

from .explain import explain

PROMPT = """You are an expert SQLite analyst. Given the schema, write ONE SQLite \
query that answers the question. Return only the query in a ```sql block.

Schema:
{schema}

Question: {question}"""

REPAIR = """The query below failed. Fix it. Return only the corrected query in a \
```sql block.

Schema:
{schema}

Question: {question}

Query:
{sql}

Error: {error}"""


def _quoted(name: str) -> str:
    """A SQLite identifier, safe to paste into SQL whatever it is called."""
    return '"' + name.replace('"', '""') + '"'


@dataclass
class Schema:
    """What the model is shown, and what the safety check validates against."""

    tables: dict[str, list[str]] = field(default_factory=dict)
    samples: dict[str, list[str]] = field(default_factory=dict)
    # Primary key columns, table -> set of column names. Needed because a
    # primary key is a number nobody wants ranked, and its name is not always
    # shaped like an identifier: Chinook, the most common sample database
    # there is, calls it InvoiceId, which no underscore-based rule catches.
    keys: dict[str, set[str]] = field(default_factory=dict)
    # Declared column types, table -> column -> type as SQLite reports it.
    # Names alone cannot tell a sum from a label, and guessing from a column
    # called "total" works until it meets a column called "total_status".
    # Only the suggestions use this; the safety check still works off names.
    types: dict[str, dict[str, str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, set[str]]:
        return {t: set(c) for t, c in self.tables.items()}

    def serialise(self) -> str:
        # Every name is quoted. A table called "sales 2026" or a column called
        # "order" produced a schema that is not valid SQL, and the model then
        # wrote the name back unquoted, which fails to parse and burns the one
        # repair attempt on a mistake the application handed it.
        out: list[str] = []
        for table, cols in self.tables.items():
            columns = ", ".join(_quoted(c) for c in cols)
            out.append(f"CREATE TABLE {_quoted(table)} ({columns});")
            hints = [s for s in self.samples.get(table, []) if s]
            if hints:
                out.append(f"-- example values in {_quoted(table)}: {'; '.join(hints)}")
        return "\n".join(out)

    @property
    def n_columns(self) -> int:
        return sum(len(c) for c in self.tables.values())

    def outline(self) -> str:
        """The tables and their columns, for the person to read.

        A question written against a database nobody has described is a guess,
        and a guess is how a confident answer about the wrong column happens.
        This is the same structure the model is shown, in the same order, so
        the two are never reading different things.
        """
        return "\n".join(f"{t}:  {', '.join(cols)}" for t, cols in self.tables.items())


@dataclass
class Answer:
    sql: str
    # The query as executed, injected LIMIT and all. `sql` is the one shown to
    # the user, rewritten to the row count promised on screen; this is the one
    # that must be re-run to export the full result.
    columns: list[str]
    rows: list[tuple]
    explanation: str
    notes: list[str]
    seconds: float
    truncated: bool = False
    # The query to re-run when the whole result is wanted on disk rather than
    # the page of it on screen: the same query with the LIMIT this application
    # injected taken back off. A limit the model wrote because the question
    # said "top ten" is part of the answer and stays.
    export_sql: str = ""
    # The database this answer came from. Carried on the answer because the
    # window can have another one open by the time the user presses Save: with
    # monthly copies of one schema (shop-2025.sqlite, shop-2026.sqlite) the
    # export ran against whichever was open now and wrote the wrong year's
    # rows under the right year's answer, without erroring.
    db_path: str = ""


class AskError(Exception):
    """Something the user needs to read, phrased for a user and not a log.

    `sql` carries the query the message is about, when the failure happened to
    a query that exists. A refusal that will not show what was refused asks to
    be taken on trust, which is the opposite of what this product sells.

    `kind` says what sort of failure it was, because the terminal command
    publishes exit codes as a contract and a script has to tell "the model is
    not running" from "the question could not be turned into a readable query".
    Both used to arrive as the same exception and leave as the same exit code.

        "model"    the local model is absent, down, or did not answer
        "timeout"  the query ran and was stopped for taking too long
        "db"       the database refused the query or could not be opened
        "refused"  nothing came out that the read-only check would pass
    """

    def __init__(self, message: str, *, sql: str = "", kind: str = "refused") -> None:
        super().__init__(message)
        self.sql = sql
        self.kind = kind


def read_only_uri(db_path: str) -> str:
    """The SQLite URI that means this exact file, opened for reading only.

    The path goes inside a URI, so the characters that have a meaning there
    have to be escaped first. A '#' anywhere in the path or in a folder name
    otherwise cuts the URI short: SQLite opens a different file, creates it if
    it is missing, and never sees mode=ro, so the connection the application
    promises to be read-only is writable. A '?' hands the rest of the path to
    SQLite as connection parameters, which is the same hole from the other end.
    """
    # The separators and the Windows drive colon stay as they are; everything
    # else, '#' and '?' and '%' included, is percent-encoded.
    return "file:" + quote(str(db_path), safe="/\\:") + "?mode=ro"


# One cell may not exceed this. SQLite is told, so it refuses before building
# the value rather than after.
#
# Why it exists: the row cap bounds rows, not bytes. A single question whose
# query is `SELECT hex(zeroblob(300000000)) FROM sales` passes every check,
# returns well under a thousand rows, and took 57 seconds against a 2 second
# timeout while reaching 3.1 GB resident. The timeout cannot help: the progress
# handler fires between instructions, and one scalar call is a single
# uninterruptible instruction. SQLITE_LIMIT_LENGTH refuses the same query in
# 0.00 s with no allocation.
#
# 4 MB is far past anything a person reads in a table cell and far short of
# what hurts. A legitimate answer does not have a four-megabyte field in it.
MAX_CELL_BYTES = 4 * 1024 * 1024


def _connect(db_path: str, timeout: float = 30.0):
    """A read-only connection, bounded in time and in the size of one value.

    Every connection in this file goes through here. The bounds were previously
    applied per call site, so each new one had to remember all of them, and the
    one opened at connect time remembered none.
    """
    con = sqlite3.connect(read_only_uri(db_path), uri=True, timeout=timeout)
    deadline = time.monotonic() + timeout
    con.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    # setlimit arrived in Python 3.11. The application requires 3.11, so this
    # is belt and braces for a source build on something older.
    with contextlib.suppress(AttributeError):
        con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_CELL_BYTES)
    return con


def verify_read_only(db_path: str) -> None:
    """Prove the connection cannot write, by trying to write and expecting to fail.

    `mode=ro` is SQLite's own guarantee and there is no reason to doubt it, but
    the interface says "read-only, checked" and the site prints the same words.
    A claim with "checked" in it has to be checked by something, or the word is
    decoration. So the probe is real: create a table, which must be refused.

    It is a CREATE and not an INSERT on purpose. An INSERT needs an existing
    table and would either touch the user's data or fail for the wrong reason,
    while CREATE fails on permission before it touches anything at all.
    """
    con = _connect(db_path)
    try:
        con.execute("CREATE TABLE askbase_write_probe__ (x)")
    except sqlite3.OperationalError as e:
        if "readonly" not in str(e).lower() and "read-only" not in str(e).lower():
            raise AskError(
                "Соединение отклонило запись, но по другой причине: "
                f"{e}. Проверка режима только для чтения не пройдена.",
                kind="db",
            ) from e
        return                                  # refused, which is the point
    else:
        # rollback() is not enough and never was: Python's sqlite3 in legacy
        # mode opens a transaction for DML only, so a CREATE is already
        # committed and the rollback is a no-op. The function whose whole job
        # is to prove the database cannot be written would have left a table
        # in the user's database on the one day it mattered. Dropped
        # explicitly, and the failure is still reported either way.
        try:
            con.execute("DROP TABLE IF EXISTS askbase_write_probe__")
            con.commit()
        except sqlite3.Error:
            pass
        raise AskError(
            "База открыта с правом записи, хотя должна была открыться только на чтение. "
            "Вопросы к ней задавать нельзя.",
            kind="db",
        )
    finally:
        con.close()


def export_csv(db_path: str, sql: str, path: str, timeout: float = 120.0) -> int:
    """Write every row the query returns, not only the rows on screen.

    The answer on screen is capped, because a table of a million rows helps
    nobody. The saved file used to be capped by the same number without saying
    so, which quietly turns "save to CSV" into "save the part you already saw".
    This streams the whole result instead, and the caller is told how many rows
    it wrote so the interface can say the number out loud.

    The injected LIMIT has to go first, or the file would be capped by the same
    bound all over again. Only a limit this application added is removed; one
    the model wrote on purpose, because the question said "top ten", stays.
    """
    con = _connect(db_path, timeout)
    try:
        cur = con.execute(sql)
        written = 0
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if cur.description:
                w.writerow([d[0] for d in cur.description])
            while True:
                batch = cur.fetchmany(5_000)
                if not batch:
                    break
                w.writerows(batch)
                written += len(batch)
        return written
    finally:
        con.close()


def snapshot(db_path: str, value_samples: int = 3, timeout: float = 30.0) -> Schema:
    """Read the structure once, at connect time, and sample coded columns.

    Sampling matters more than it looks. A column holding 1 and 2 instead of
    'male' and 'female' is the single most common reason a generated filter is
    wrong, and the model cannot guess the encoding from the column name.

    Two things here are defences rather than conveniences, because a database
    file is untrusted input: it may have been emailed to the user by somebody
    who chose what is in it.

    Identifiers go through `_quoted`, which doubles embedded quotes. They were
    interpolated raw, so a column named `pw" FROM "secret" --` turned the
    sample query into a different query and ran it on the user's connection,
    before the safety check exists and with nothing to stop it. It cannot write
    (the connection really is read-only) and it cannot reach another file, but
    it is arbitrary execution and, with `hex(zeroblob(...))` in the name, an
    unbounded hang on open.

    And the connection is bounded in time like every other one. This runs when
    a file is opened, before the user has asked anything, so none of the
    per-question limits apply to it.
    """
    con = _connect(db_path, timeout)
    try:
        # Views are included on purpose. In a database somebody else designed,
        # the readable part is often a set of views over narrow tables, and
        # leaving them out of the snapshot both hides them from the model and
        # makes the safety check reject a question about them as a name that
        # does not exist.
        names = [
            r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        schema = Schema()
        for t in names:
            info = list(con.execute(f"PRAGMA table_info({_quoted(t)})"))
            cols = [r[1] for r in info]
            schema.tables[t] = cols
            schema.types[t] = {r[1]: (r[2] or "").upper() for r in info}
            schema.keys[t] = {r[1] for r in info if r[5]}      # pk column index
            hints: list[str] = []
            for c in cols:
                try:
                    vals = [
                        r[0] for r in con.execute(
                            f"SELECT DISTINCT {_quoted(c)} FROM {_quoted(t)} "
                            f"WHERE {_quoted(c)} IS NOT NULL LIMIT {value_samples + 1}"
                        )
                    ]
                except sqlite3.Error:
                    continue
                # Only low-cardinality columns are worth showing: those are the
                # lookups. A column of unique names teaches the model nothing.
                if 0 < len(vals) <= value_samples:
                    hints.append(f"{c} is one of {', '.join(repr(v) for v in vals)}")
            if hints:
                schema.samples[t] = hints
        return schema
    finally:
        con.close()


def extract_sql(text: str) -> str:
    """Pull the query out of a model's reply, whatever wrapping it used."""
    fenced = re.search(r"```(?:sql)?\s*(.+?)```", text, re.S | re.I)
    body = fenced.group(1) if fenced else text
    m = re.search(r"\b(WITH|SELECT)\b.+", body, re.S | re.I)
    return (m.group(0) if m else body).strip().rstrip(";").strip()


def run_query(db_path: str, sql: str, max_rows: int, timeout: float) -> tuple[list[str], list[tuple], bool]:
    """Execute on a read-only connection, bounded in rows and in time."""
    con = _connect(db_path, timeout)
    try:
        deadline = time.monotonic() + timeout
        try:
            cur = con.execute(sql)
            rows = cur.fetchmany(max_rows + 1)
        except sqlite3.OperationalError:
            # The progress handler stops the query by raising "interrupted",
            # which is indistinguishable from a broken query to the caller.
            # Told apart here, because a query that ran out of time must not be
            # sent back to the model for repair: there is nothing to repair,
            # and the user would wait for the whole round again to be told
            # "interrupted", a word that explains nothing.
            if time.monotonic() > deadline:
                raise AskError(
                    f"Запрос слишком тяжёлый: не уложился в {timeout:.0f} с и был остановлен. "
                    "Попробуйте спросить об отрезке поменьше.",
                    kind="timeout",
                ) from None
            raise
        cols = [d[0] for d in cur.description or []]
        truncated = len(rows) > max_rows
        return cols, rows[:max_rows], truncated
    finally:
        con.close()


class Engine:
    """One database, one model, one question at a time."""

    def __init__(self, db_path: str, client, *, max_rows: int = 1000, timeout: float = 30.0,
                 lang: str = "ru"):
        self.db_path = db_path
        self.client = client
        self.max_rows = max_rows
        self.lang = lang
        self.timeout = timeout
        verify_read_only(db_path)
        self.schema = snapshot(db_path, timeout=timeout)
        if not self.schema.tables:
            # Refused here rather than on the first question. With nothing to
            # validate names against, every question is rejected by the safety
            # check with "there is no such thing in the database", after a
            # minute of waiting for the model, and the file looks opened.
            raise AskError(
                "В этом файле нет ни одной таблицы. Это либо не база SQLite, либо она пустая.",
                kind="db",
            )

    def _write(self, prompt: str) -> str:
        """Ask the model, and turn its failures into something readable.

        The client raises a plain RuntimeError when the local server is not
        there or does not answer in time. Left alone it reaches the window as
        an unexpected error with a traceback under it, and "Ollama is not
        running" is the most ordinary thing that can happen here, not a bug.
        """
        try:
            reply = self.client.complete(prompt)
        except (RuntimeError, OSError) as e:
            raise AskError(str(e) or "Локальная модель не ответила.", kind="model") from e
        return extract_sql(reply.text)

    def _rewrite_limit(self, verdict) -> tuple[str, str]:
        """The query to show, and the query to export, from the one executed.

        Both are the same rewrite seen from two sides. The check appends
        LIMIT max_rows+1 so that "exactly N rows exist" and "more exist and
        were cut" can be told apart; the screen must not show that extra row
        in the query, and an export must not be bounded by it at all.

        Done on the parse tree, not with a regular expression over the rendered
        text. The regex matched `LIMIT <n>` anywhere in the statement, and
        every one of these was reproduced:

          - `SELECT COUNT(*) FROM (SELECT id FROM t ORDER BY total DESC LIMIT 11)`
            at max_rows 10: the model's own inner limit was stripped, so the
            export returned every row in the table instead of eleven, and the
            shown query said LIMIT 10 where the model wrote 11. One answer,
            three different numbers.
          - `SELECT id, 'LIMIT 1001' AS tag FROM t`: the rewrite reached inside
            a string literal, so the exported column held falsified data and
            the shown query had never been run in that form.
          - `SELECT id FROM t OFFSET 5`: the check turns a bare OFFSET into
            `LIMIT 1001 OFFSET 5`; removing the LIMIT left SQL SQLite rejects,
            so Save to CSV could not work at all for that answer.

        The AST touches only the statement's own top-level limit, which is the
        one this application put there, and renders back with sqlglot so the
        result is always valid SQL rather than edited text.
        """
        if not verdict.limit_added:
            return verdict.sql, verdict.sql
        try:
            stmt = sqlglot.parse_one(verdict.sql, read="sqlite")
        except Exception:
            # Unparsable here would mean the check parsed it and we cannot,
            # which should not happen. Fall back to showing the query as run
            # and exporting nothing rewritten, rather than editing text.
            return verdict.sql, verdict.sql

        shown = stmt.copy()
        shown.set("limit", exp.Limit(expression=exp.Literal.number(self.max_rows)))

        exported = stmt.copy()
        exported.set("limit", None)
        if exported.args.get("offset") is not None and not exported.args.get("limit"):
            # SQLite has no bare OFFSET. Keeping the offset means keeping a
            # limit, so the bound goes to -1, which SQLite reads as no limit.
            exported.set("limit", exp.Limit(expression=exp.Literal.number(-1)))
        return shown.sql(dialect="sqlite"), exported.sql(dialect="sqlite")

    def ask(self, question: str, *, on_step=None) -> Answer:
        step = on_step or (lambda _s: None)
        t0 = time.perf_counter()

        step("writing")
        sql = self._write(
            PROMPT.format(schema=self.schema.serialise(), question=question)
        )
        if not sql:
            raise AskError("Модель не вернула запрос. Попробуйте спросить иначе.")

        step("checking")
        # The cap handed to the safety check is one row higher than what gets
        # shown. Without that extra row the injected LIMIT makes "exactly N
        # rows exist" and "more exist and were cut" look identical, and the
        # user is quietly told that a truncated answer is the whole answer.
        verdict = check(sql, schema=self.schema.as_dict(), max_rows=self.max_rows + 1)
        if not verdict.ok:
            # One repair attempt: measured as worth it, and cheap. The error is
            # handed back verbatim because that is the signal the model needs.
            step("fixing")
            sql = self._write(
                REPAIR.format(schema=self.schema.serialise(), question=question,
                              sql=sql, error=verdict.reason)
            )
            verdict = check(sql, schema=self.schema.as_dict(), max_rows=self.max_rows + 1)
            if not verdict.ok:
                raise AskError(
                    f"Запрос не выполнен, он выходил за рамки чтения данных. {verdict.reason}",
                    sql=sql,
                )

        step("running")
        try:
            cols, rows, truncated = run_query(
                self.db_path, verdict.sql, self.max_rows, self.timeout
            )
        except sqlite3.Error as e:
            step("fixing")
            sql = self._write(
                REPAIR.format(schema=self.schema.serialise(), question=question,
                              sql=verdict.sql, error=str(e))
            )
            verdict = check(sql, schema=self.schema.as_dict(), max_rows=self.max_rows + 1)
            if not verdict.ok:
                raise AskError(
                    f"Не смог составить работающий запрос. {verdict.reason} "
                    "Попробуйте назвать таблицу или период точнее.",
                    sql=sql,
                ) from e
            try:
                cols, rows, truncated = run_query(
                    self.db_path, verdict.sql, self.max_rows, self.timeout
                )
            except sqlite3.Error as e2:
                raise AskError(f"База отклонила запрос: {e2}", sql=verdict.sql,
                               kind="db") from e2

        shown_sql, export_sql = self._rewrite_limit(verdict)

        notes = [n.replace(str(self.max_rows + 1), str(self.max_rows)) for n in verdict.notes]
        if truncated:
            notes.append(f"Строк больше {self.max_rows}, показаны первые {self.max_rows}")
        return Answer(
            sql=shown_sql,
            columns=cols,
            rows=rows,
            explanation=explain(shown_sql, lang=self.lang).text(),
            notes=notes,
            seconds=time.perf_counter() - t0,
            truncated=truncated,
            export_sql=export_sql,
            db_path=self.db_path,
        )
