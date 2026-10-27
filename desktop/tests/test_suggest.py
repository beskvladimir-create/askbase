"""Example questions built from the schema in front of the user.

The thing worth testing is not that text comes out. It is that a shape is
offered only when the schema can carry it, because a suggestion the database
cannot answer is worse than no suggestion: it teaches the wrong thing about
what the product can do, to exactly the person who has no other way to find
out.
"""
from __future__ import annotations

import sqlite3

import pytest
from askbase import i18n, suggest
from askbase.engine import snapshot

RU = i18n.TEXTS["ru"]
EN = i18n.TEXTS["en"]


def build(tmp_path, script: str, fill=None) -> object:
    p = tmp_path / "x.sqlite"
    con = sqlite3.connect(p)
    con.executescript(script)
    if fill:
        for sql, rows in fill:
            con.executemany(sql, rows)
    con.commit()
    con.close()
    return snapshot(str(p))


SHOP = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, region TEXT, joined TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL,
                     placed TEXT, status TEXT);
"""
SHOP_ROWS = [
    ("INSERT INTO customers VALUES (?,?,?,?)",
     [(i, f"c{i}", ["Leeds", "Thorne"][i % 2], f"2026-03-{i % 28 + 1:02d}") for i in range(30)]),
    ("INSERT INTO orders VALUES (?,?,?,?,?)",
     [(i, i % 30, i * 3.5, f"2026-05-{i % 28 + 1:02d}", ["new", "paid", "sent"][i % 3])
      for i in range(40)]),
]


@pytest.fixture
def shop(tmp_path):
    return build(tmp_path, SHOP, SHOP_ROWS)


def kinds(schema, texts=RU):
    return [s.kind for s in suggest.for_schema(schema, texts)]


def test_four_different_shapes_not_the_same_one_four_times(shop):
    got = kinds(shop)
    assert len(got) == len(set(got)), got
    assert len(got) == 4


def test_a_breakdown_is_offered_on_a_column_with_few_values(shop):
    text = next(s.text for s in suggest.for_schema(shop, RU) if s.kind == "breakdown")
    # region holds two values across thirty rows; name holds thirty
    assert "region" in text
    assert "name" not in text


def test_a_ranking_never_picks_an_identifier(shop):
    text = next(s.text for s in suggest.for_schema(shop, RU) if s.kind == "ranking")
    assert "total" in text
    assert "customer_id" not in text and "id" not in text.split()


def test_a_period_picks_a_date_shaped_column(shop):
    text = next(s.text for s in suggest.for_schema(shop, RU) if s.kind == "period")
    assert "joined" in text or "placed" in text


def test_a_schema_of_nothing_but_opaque_text_still_gets_one_suggestion(tmp_path):
    s = build(tmp_path, "CREATE TABLE notes (a TEXT, b TEXT);",
              [("INSERT INTO notes VALUES (?,?)",
                [(f"free text {i}", f"other {i}") for i in range(50)])])
    out = suggest.for_schema(s, RU)
    assert [x.kind for x in out] == ["count"]
    assert "notes" in out[0].text


def test_an_empty_schema_suggests_nothing_rather_than_raising(tmp_path):
    p = tmp_path / "empty.sqlite"
    sqlite3.connect(p).close()
    assert suggest.for_schema(snapshot(str(p)), RU) == []


def test_the_same_database_always_gives_the_same_list(shop):
    first = [s.text for s in suggest.for_schema(shop, RU)]
    second = [s.text for s in suggest.for_schema(shop, RU)]
    assert first == second


def test_both_languages_produce_the_same_shapes(shop):
    assert kinds(shop, RU) == kinds(shop, EN)
    ru = [s.text for s in suggest.for_schema(shop, RU)]
    en = [s.text for s in suggest.for_schema(shop, EN)]
    assert ru != en                              # and they are actually translated


def test_an_id_like_name_is_not_mistaken_for_a_measure(tmp_path):
    s = build(tmp_path, "CREATE TABLE t (order_no INTEGER, part_cd INTEGER, idle_days INTEGER);",
              [("INSERT INTO t VALUES (?,?,?)", [(i, i, i) for i in range(50)])])
    ranking = [x.text for x in suggest.for_schema(s, RU) if x.kind == "ranking"]
    # order_no and part_cd are identifiers; idle_days is a number worth ranking,
    # and must not be refused merely for containing the letters "id".
    assert ranking and "idle_days" in ranking[0]


def test_the_limit_is_honoured(shop):
    assert len(suggest.for_schema(shop, RU, limit=2)) == 2


def test_every_suggestion_is_a_question_not_sql(shop):
    for s in suggest.for_schema(shop, RU):
        assert "SELECT" not in s.text.upper()
        assert ";" not in s.text


# ---- found by review -------------------------------------------------------

def test_a_camelcase_primary_key_is_not_ranked(tmp_path):
    # Chinook, the most widely used sample SQLite file there is. The rule
    # required an underscore, so the suggestion offered was "the ten Invoice
    # with the largest InvoiceId": the primary key, ranked.
    s = build(tmp_path,
              "CREATE TABLE Invoice (InvoiceId INTEGER PRIMARY KEY, "
              "CustomerId INTEGER, Total REAL);",
              [("INSERT INTO Invoice VALUES (?,?,?)",
                [(i, i % 7, i * 2.5) for i in range(1, 50)])])
    ranking = [x.text for x in suggest.for_schema(s, EN) if x.kind == "ranking"]
    assert ranking, "ранжирование не предложено вовсе"
    assert "Total" in ranking[0]
    assert "InvoiceId" not in ranking[0] and "CustomerId" not in ranking[0]


def test_a_primary_key_is_excluded_by_what_it_is_not_by_its_name(tmp_path):
    s = build(tmp_path, "CREATE TABLE t (serial INTEGER PRIMARY KEY, weight REAL);",
              [("INSERT INTO t VALUES (?,?)", [(i, i * 1.1) for i in range(1, 40)])])
    ranking = [x.text for x in suggest.for_schema(s, EN) if x.kind == "ranking"]
    assert ranking and "weight" in ranking[0], ranking


def test_a_dated_column_with_a_meaningless_name_is_found_by_its_values(tmp_path):
    # The fallback was dead: samples are stored as sentences and the pattern
    # was anchored with ^, so it could never match.
    s = build(tmp_path, "CREATE TABLE visits (period TEXT, who TEXT);",
              [("INSERT INTO visits VALUES (?,?)",
                [(f"2026-0{i % 3 + 1}-01", "a") for i in range(30)])])
    period = [x.text for x in suggest.for_schema(s, EN) if x.kind == "period"]
    assert period and "period" in period[0], period


def test_one_dated_column_does_not_make_every_column_a_date(tmp_path):
    # Un-anchoring the pattern alone would have been worse than leaving it
    # dead: the whole table's samples were passed in, so any table with one
    # dated column answered True for every column in it.
    s = build(tmp_path, "CREATE TABLE t (period TEXT, note TEXT);",
              [("INSERT INTO t VALUES (?,?)",
                [(f"2026-0{i % 3 + 1}-01", "x") for i in range(30)])])
    decls = s.types["t"]
    from askbase.suggest import _looks_like_a_date, _values_by_column
    by_col = _values_by_column(s, "t")
    assert _looks_like_a_date("period", decls["period"], by_col)
    assert not _looks_like_a_date("note", decls["note"], by_col)
