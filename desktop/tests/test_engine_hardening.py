"""The engine's defences, each pinned by the thing it was found failing on.

A database file is untrusted input: it may have been emailed to the user by
somebody who chose what is in it. Everything here was reproduced before it was
fixed, so each test is a regression and not a hypothesis.
"""
from __future__ import annotations

import sqlite3
import time

import pytest
from askbase.engine import (
    MAX_CELL_BYTES,
    AskError,
    Engine,
    export_csv,
    run_query,
    snapshot,
    verify_read_only,
)


def make(tmp_path, script, rows=()):
    p = tmp_path / "t.sqlite"
    con = sqlite3.connect(p)
    con.executescript(script)
    for sql, data in rows:
        con.executemany(sql, data)
    con.commit()
    con.close()
    return str(p)


class Stub:
    def __init__(self, sql):
        self.text = f"```sql\n{sql}\n```"

    def complete(self, prompt):
        return self

    def reset(self):
        pass

    def cancel(self):
        pass


# ---- read-only is verified, not assumed -----------------------------------

def test_a_normal_database_refuses_the_write_probe(tmp_path):
    db = make(tmp_path, "CREATE TABLE a (id INTEGER);")
    verify_read_only(db)            # must not raise


def test_the_probe_leaves_nothing_behind(tmp_path):
    db = make(tmp_path, "CREATE TABLE a (id INTEGER);")
    verify_read_only(db)
    con = sqlite3.connect(db)
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master")]
    con.close()
    assert names == ["a"], "пробник записи остался в базе"


def test_a_writable_connection_is_refused_outright(tmp_path, monkeypatch):
    # The branch that matters and that nothing exercised: gutting the whole
    # function to a bare `return` left every test green, so the words
    # "read-only, checked" were decoration as far as the suite was concerned.
    from askbase import engine

    db = make(tmp_path, "CREATE TABLE a (id INTEGER);")
    monkeypatch.setattr(engine, "read_only_uri", lambda p: str(p))  # drop mode=ro
    with pytest.raises(engine.AskError) as caught:
        engine.verify_read_only(db)
    assert caught.value.kind == "db"
    con = sqlite3.connect(db)
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master")]
    con.close()
    assert "askbase_write_probe__" not in names, "проба оставила таблицу в базе пользователя"


# ---- a crafted schema cannot inject SQL ------------------------------------

def test_a_column_named_to_inject_sql_does_not_run_it(tmp_path):
    # Column name: pw" FROM "secret" --  . Interpolated raw, it turned the
    # sample query into `SELECT DISTINCT "pw" FROM "secret" --...` and read
    # another table, on open, before any check exists.
    db = make(
        tmp_path,
        'CREATE TABLE t1 ("pw"" FROM ""secret"" --" TEXT);'
        "CREATE TABLE secret (pw TEXT);",
        [("INSERT INTO secret VALUES (?)", [("hunter2",)]),
         ("INSERT INTO t1 VALUES (?)", [("safe",)])],
    )
    s = snapshot(db)
    hints = s.samples.get("t1", [])
    assert not any("hunter2" in h for h in hints), f"утечка из secret: {hints}"
    assert any("safe" in h for h in hints), hints


def test_a_table_named_to_inject_sql_does_not_run_it(tmp_path):
    db = make(tmp_path, 'CREATE TABLE "t"") --" (a TEXT);'
                        "CREATE TABLE other (b TEXT);")
    s = snapshot(db)
    assert 't") --' in s.tables


# ---- bounds the row cap cannot express -------------------------------------

def test_one_enormous_cell_is_refused_instead_of_built(tmp_path):
    # The row cap bounds rows, not bytes. This query passes every check and
    # returns one row; it took 57 s against a 2 s timeout and 3.1 GB resident,
    # because a single scalar call is one uninterruptible instruction and the
    # progress handler only fires between instructions.
    db = make(tmp_path, "CREATE TABLE sales (id INTEGER);",
              [("INSERT INTO sales VALUES (?)", [(i,) for i in range(200)])])
    t0 = time.monotonic()
    with pytest.raises(sqlite3.Error):
        run_query(db, "SELECT hex(zeroblob(300000000)) FROM sales LIMIT 2", 1, 2.0)
    assert time.monotonic() - t0 < 5.0, "отклонено, но слишком долго"


def test_an_ordinary_large_cell_still_comes_through(tmp_path):
    # The bound must be far past anything a person reads and far short of what
    # hurts, or it becomes a bug of its own.
    db = make(tmp_path, "CREATE TABLE notes (body TEXT);",
              [("INSERT INTO notes VALUES (?)", [("x" * 200_000,)])])
    _cols, rows, _ = run_query(db, "SELECT body FROM notes LIMIT 2", 1, 10.0)
    assert len(rows[0][0]) == 200_000
    assert MAX_CELL_BYTES > 200_000


def test_a_runaway_query_is_still_stopped_by_the_timeout(tmp_path):
    db = make(tmp_path, "CREATE TABLE t (a INTEGER);",
              [("INSERT INTO t VALUES (?)", [(i,) for i in range(60)])])
    t0 = time.monotonic()
    with pytest.raises(AskError) as e:
        run_query(db, "SELECT COUNT(*) FROM t a, t b, t c, t d, t e", 10, 1.0)
    assert e.value.kind == "timeout", e.value.kind
    assert time.monotonic() - t0 < 6.0


# ---- the limit rewrite, on the parse tree ----------------------------------

@pytest.mark.parametrize("model_sql,max_rows,must_keep,must_not", [
    # The model's own inner limit is part of the answer and must survive.
    ("SELECT COUNT(*) AS n FROM (SELECT id FROM orders ORDER BY total DESC LIMIT 11)",
     10, "LIMIT 11", None),
    # A string literal is not SQL and must not be edited.
    ("SELECT id, 'LIMIT 1001' AS tag FROM orders", 1000, "'LIMIT 1001'", None),
])
def test_the_export_query_keeps_what_the_model_wrote(tmp_path, model_sql, max_rows,
                                                     must_keep, must_not):
    db = make(tmp_path, "CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL);",
              [("INSERT INTO orders VALUES (?,?)", [(i, i * 1.5) for i in range(59)])])
    answer = Engine(db, Stub(model_sql), max_rows=max_rows).ask("x")
    assert must_keep in answer.export_sql, answer.export_sql
    assert must_keep in answer.sql, answer.sql


def test_a_bare_offset_can_still_be_exported(tmp_path):
    # The check turns a bare OFFSET into `LIMIT 1001 OFFSET 5`. Removing the
    # LIMIT as text left SQL SQLite rejects, so Save to CSV could not work at
    # all for that answer.
    db = make(tmp_path, "CREATE TABLE orders (id INTEGER PRIMARY KEY);",
              [("INSERT INTO orders VALUES (?)", [(i,) for i in range(59)])])
    answer = Engine(db, Stub("SELECT id FROM orders OFFSET 5"), max_rows=1000).ask("x")
    out = tmp_path / "o.csv"
    assert export_csv(db, answer.export_sql, str(out)) == 54


def test_the_shown_query_promises_the_row_count_on_screen(tmp_path):
    db = make(tmp_path, "CREATE TABLE orders (id INTEGER PRIMARY KEY);",
              [("INSERT INTO orders VALUES (?)", [(i,) for i in range(59)])])
    answer = Engine(db, Stub("SELECT id FROM orders"), max_rows=10).ask("x")
    assert "LIMIT 10" in answer.sql
    assert len(answer.rows) == 10
    assert answer.truncated
    out = tmp_path / "o.csv"
    assert export_csv(db, answer.export_sql, str(out)) == 59, "экспорт обрезан по экрану"
