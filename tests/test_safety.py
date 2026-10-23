"""Threshold P4 is absolute, so every rejection path gets a test."""
from __future__ import annotations

import pytest

from nl2sql_app.safety import check

SCHEMA = {
    "clients": {"id", "name", "region_id", "dt_reg"},
    "regions": {"id", "name"},
}


def test_plain_select_passes_and_gets_a_limit():
    v = check("SELECT name FROM clients", schema=SCHEMA)
    assert v.ok
    assert v.limit_added
    assert "LIMIT 1000" in v.sql.upper()
    assert v.notes


def test_existing_limit_is_left_alone():
    v = check("SELECT name FROM clients LIMIT 5", schema=SCHEMA)
    assert v.ok
    assert not v.limit_added
    assert "LIMIT 5" in v.sql.upper()


def test_join_with_aliases_resolves_columns():
    v = check(
        "SELECT r.name, COUNT(*) FROM clients c JOIN regions r ON r.id = c.region_id GROUP BY r.name",
        schema=SCHEMA,
    )
    assert v.ok, v.reason


def test_non_recursive_with_passes():
    v = check(
        "WITH recent AS (SELECT id FROM clients WHERE dt_reg > '2026-01-01') SELECT id FROM recent",
        schema=SCHEMA,
    )
    assert v.ok, v.reason


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM clients",
        "UPDATE clients SET name = 'x'",
        "INSERT INTO clients (name) VALUES ('x')",
        "DROP TABLE clients",
        "CREATE TABLE t (a int)",
        "ALTER TABLE clients ADD COLUMN x int",
    ],
)
def test_writes_are_rejected(sql):
    v = check(sql, schema=SCHEMA)
    assert not v.ok
    assert v.sql == ""          # a rejected query is never handed back for execution
    assert v.reason


def test_second_statement_is_rejected():
    v = check("SELECT name FROM clients; DROP TABLE clients", schema=SCHEMA)
    assert not v.ok
    assert "одно" in v.reason


def test_write_hidden_in_a_cte_is_rejected():
    v = check(
        "WITH gone AS (DELETE FROM clients RETURNING id) SELECT id FROM gone",
        schema=SCHEMA,
        dialect="postgres",
    )
    assert not v.ok


def test_recursive_cte_is_rejected():
    v = check(
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT n FROM r",
        schema=SCHEMA,
    )
    assert not v.ok
    assert "екурсив" in v.reason


def test_unknown_table_is_rejected():
    v = check("SELECT * FROM salaries", schema=SCHEMA)
    assert not v.ok
    assert "salaries" in v.reason


def test_unknown_qualified_column_is_rejected():
    v = check("SELECT c.salary FROM clients c", schema=SCHEMA)
    assert not v.ok
    assert "salary" in v.reason


def test_bare_column_is_left_to_the_database():
    # Deliberately allowed: resolving unqualified names would need full scope
    # analysis, and a false rejection is worse than a clear error from the db.
    v = check("SELECT salary FROM clients", schema=SCHEMA)
    assert v.ok


def test_schema_check_is_case_insensitive():
    v = check("SELECT NAME FROM Clients", schema=SCHEMA)
    assert v.ok, v.reason


def test_names_are_not_checked_without_a_schema():
    v = check("SELECT whatever FROM nowhere")
    assert v.ok, v.reason


@pytest.mark.parametrize("sql", ["", "   ", "this is not sql at all ((("])
def test_empty_and_unparsable_are_rejected(sql):
    v = check(sql, schema=SCHEMA)
    assert not v.ok
    assert v.reason


def test_pragma_is_rejected():
    v = check("PRAGMA table_info(clients)", schema=SCHEMA)
    assert not v.ok


def test_union_is_bounded_even_without_a_limit_slot():
    v = check(
        "SELECT name FROM clients UNION SELECT name FROM regions",
        schema=SCHEMA,
    )
    assert v.ok, v.reason
    assert v.notes          # the executor is told to cap the fetch
def test_a_comment_after_the_semicolon_is_not_a_second_statement():
    # A model that signs off with "; -- all of them" wrote one ordinary query.
    # sqlglot hands the lone semicolon back as a statement of its own, so this
    # was refused as an injection attempt and the single repair attempt went on
    # fixing nothing.
    v = check("SELECT name FROM clients; -- all of them", schema=SCHEMA)
    assert v.ok, v.reason
    assert "LIMIT" in v.sql.upper()


def test_a_semicolon_still_does_not_hide_a_second_statement():
    # The reason the count exists in the first place: a comment between the two
    # statements must not make the second one invisible.
    v = check("SELECT name FROM clients; -- \n DROP TABLE clients", schema=SCHEMA)
    assert not v.ok
    assert "одно" in v.reason
@pytest.mark.parametrize("sql", [
    "ATTACH DATABASE '/tmp/other.db' AS other",
    "ATTACH DATABASE 'file:/tmp/other.db?mode=rwc' AS other",
    "DETACH DATABASE other",
    "VACUUM",
])
def test_reaching_for_another_file_is_rejected(sql):
    # A read-only connection does not stop ATTACH: SQLite applies mode=ro to
    # the main database only, and the connection is opened with URIs enabled,
    # so an attached file could be opened for writing. This layer is the one
    # that stops it, which is why it is pinned here.
    v = check(sql, schema=SCHEMA)
    assert not v.ok
    assert v.sql == ""
