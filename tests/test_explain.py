"""The explanation is what a user without SQL has instead of reading the query.

Its job is not to be pretty. Its job is to name the rows that silently did not
make it into the answer, because that is how a wrong answer passes for a right
one.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop"))
from askbase.explain import explain  # noqa: E402


def test_a_plain_select_is_described():
    e = explain("SELECT name FROM clients")
    assert "clients" in e.summary
    assert e.summary.endswith(".")


def test_counting_and_grouping_are_named():
    e = explain("SELECT region, COUNT(*) FROM clients GROUP BY region")
    assert "количество" in e.summary
    assert "группировкой по region" in e.summary


def test_an_inner_join_warns_about_dropped_rows():
    # The single most common way to get a confidently wrong total.
    e = explain("SELECT c.name FROM clients c JOIN regions r ON r.id = c.region_id")
    assert any("не попали" in o for o in e.omissions)
    assert any("regions" in o for o in e.omissions)


def test_a_left_join_does_not_warn():
    e = explain("SELECT c.name FROM clients c LEFT JOIN regions r ON r.id = c.region_id")
    assert not any("regions" in o for o in e.omissions)


def test_a_filter_warns_about_empty_values():
    e = explain("SELECT name FROM clients WHERE region_id = 3")
    assert any("region_id" in o and "не заполнено" in o for o in e.omissions)


def test_having_is_called_out():
    e = explain("SELECT region, COUNT(*) FROM clients GROUP BY region HAVING COUNT(*) > 2")
    assert any("HAVING" in o for o in e.omissions)


def test_distinct_is_called_out():
    e = explain("SELECT DISTINCT name FROM clients")
    assert any("Повторяющиеся" in o for o in e.omissions)


def test_a_limit_is_stated_with_its_number():
    e = explain("SELECT name FROM clients LIMIT 25")
    assert "25" in e.summary


def test_unparsable_sql_says_so_rather_than_inventing():
    e = explain("this is not sql ((((")
    assert "не удалось" in e.summary.lower() or "Не удалось" in e.summary
    assert e.omissions == []


def test_the_text_joins_summary_and_omissions():
    e = explain("SELECT c.name FROM clients c JOIN regions r ON r.id = c.region_id WHERE c.active = 1")
    full = e.text()
    assert e.summary in full
    for o in e.omissions:
        assert o in full


def test_several_tables_are_listed_readably():
    e = explain("SELECT * FROM a JOIN b ON b.id = a.b_id JOIN c ON c.id = a.c_id")
    assert " и " in e.summary or " и " in " ".join(e.omissions)
