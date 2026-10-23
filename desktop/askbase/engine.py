"""Connect to a database, turn a question into SQL, and run it safely.

No Qt in here on purpose: everything below is testable without an interface,
and the window is a thin layer over it.

The order of operations is the product's promise in code form. The model never
touches the database. It is handed a schema snapshot and returns text; that
text is parsed and checked before anything is executed, and the connection it
is executed on is read-only.
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from nl2sql_app.safety import check  # noqa: E402

from .explain import explain  # noqa: E402

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
    columns: list[str]
    rows: list[tuple]
    explanation: str
    notes: list[str]
    seconds: float
    truncated: bool = False


class AskError(Exception):
    """Something the user needs to read, phrased for a user and not a log."""


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


def snapshot(db_path: str, value_samples: int = 3) -> Schema:
    """Read the structure once, at connect time, and sample coded columns.

    Sampling matters more than it looks. A column holding 1 and 2 instead of
    'male' and 'female' is the single most common reason a generated filter is
    wrong, and the model cannot guess the encoding from the column name.
    """
    con = sqlite3.connect(read_only_uri(db_path), uri=True)
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
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            schema.tables[t] = cols
            hints: list[str] = []
            for c in cols:
                try:
                    vals = [
                        r[0] for r in con.execute(
                            f'SELECT DISTINCT "{c}" FROM "{t}" '
                            f'WHERE "{c}" IS NOT NULL LIMIT {value_samples + 1}'
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
    con = sqlite3.connect(read_only_uri(db_path), uri=True, timeout=timeout)
    try:
        deadline = time.monotonic() + timeout
        con.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
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
                    "Попробуйте спросить об отрезке поменьше."
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
        self.schema = snapshot(db_path)
        if not self.schema.tables:
            # Refused here rather than on the first question. With nothing to
            # validate names against, every question is rejected by the safety
            # check with "there is no such thing in the database", after a
            # minute of waiting for the model, and the file looks opened.
            raise AskError(
                "В этом файле нет ни одной таблицы. Это либо не база SQLite, либо она пустая."
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
            raise AskError(str(e) or "Локальная модель не ответила.") from e
        return extract_sql(reply.text)

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
                    f"Запрос не выполнен, он выходил за рамки чтения данных. {verdict.reason}"
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
                raise AskError(f"Не смог составить работающий запрос. {verdict.reason}") from e
            try:
                cols, rows, truncated = run_query(
                    self.db_path, verdict.sql, self.max_rows, self.timeout
                )
            except sqlite3.Error as e2:
                raise AskError(f"База отклонила запрос: {e2}") from e2

        shown_sql = verdict.sql
        if verdict.limit_added:
            shown_sql = re.sub(
                rf"\bLIMIT\s+{self.max_rows + 1}\b", f"LIMIT {self.max_rows}",
                shown_sql, flags=re.I,
            )

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
        )
