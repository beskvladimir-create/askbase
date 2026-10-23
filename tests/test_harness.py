"""GPU-free tests for the harness core: EX comparison, schema, SQL extraction.

Builds a tiny sqlite db so the evaluator and schema utilities can be exercised
end-to-end without any model.
"""
import os
import sqlite3
import tempfile

from nl2sql_app.bench.evaluator import execution_accuracy, result_set_match
from nl2sql_app.bench.pipeline import extract_sql
from nl2sql_app.bench.schema import link_schema, serialize_schema


def _make_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL);
        INSERT INTO customers VALUES (1,'Ann','Lisbon'),(2,'Bob','Porto');
        INSERT INTO orders VALUES (1,1,100.0),(2,1,50.0),(3,2,200.0);
        """
    )
    conn.commit()
    conn.close()


def test_ex_match_and_order_insensitivity():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "t.sqlite")
        _make_db(db)
        gold = "SELECT name FROM customers ORDER BY id"
        pred_same = "SELECT name FROM customers ORDER BY name DESC"  # same set, diff order
        ok, err = execution_accuracy(db, pred_same, gold)
        assert ok and err is None


def test_ex_mismatch():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "t.sqlite")
        _make_db(db)
        gold = "SELECT name FROM customers WHERE city='Lisbon'"
        pred = "SELECT name FROM customers"  # different set
        ok, _ = execution_accuracy(db, pred, gold)
        assert not ok


def test_ex_pred_error_is_wrong_not_crash():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "t.sqlite")
        _make_db(db)
        ok, err = execution_accuracy(db, "SELECT nope FROM nothing", "SELECT 1")
        assert not ok and err == "pred_sql failed to execute"


def test_result_set_match():
    assert result_set_match([(1,), (2,)], [(2,), (1,)])
    assert not result_set_match([(1,)], [(1,), (2,)])


def test_schema_and_linking():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "t.sqlite")
        _make_db(db)
        full = serialize_schema(db)
        assert "customers(" in full and "orders(" in full
        linked = link_schema(db, "how many orders per customer", "")
        assert "orders" in linked  # 'orders' token present
        sub = serialize_schema(db, linked)
        assert "orders(" in sub


def test_extract_sql():
    assert extract_sql("```sql\nSELECT 1;\n```") == "SELECT 1"
    assert extract_sql("Here you go: SELECT a FROM t") == "SELECT a FROM t"
    assert extract_sql("WITH x AS (SELECT 1) SELECT * FROM x").startswith("WITH")


def test_duplicate_rows_do_not_change_the_verdict():
    """SELECT name and SELECT DISTINCT name score the same, as in official BIRD.

    The official evaluator compares set(predicted) == set(ground_truth), so
    duplicates collapse. Scoring these as different was a real defect here: it
    understated accuracy by 5.4 points on a 500-question sample and made the
    figures incomparable with every published BIRD number.
    """
    with_dupes = [("a",), ("a",), ("b",)]
    without = [("a",), ("b",)]
    assert result_set_match(with_dupes, without)
    assert result_set_match(without, with_dupes)


def test_order_still_does_not_matter():
    assert result_set_match([("b",), ("a",)], [("a",), ("b",)])


def test_different_contents_still_fail():
    assert not result_set_match([("a",)], [("b",)])
    assert not result_set_match([("a",)], [])


def test_a_missing_value_is_not_the_same_as_an_empty_string():
    # The kind of near-match that an evaluator must not wave through.
    assert not result_set_match([(None,)], [("",)])
