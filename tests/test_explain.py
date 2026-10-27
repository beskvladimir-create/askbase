"""The explanation is what a user without SQL has instead of reading the query.

Its job is not to be pretty. Its job is to name the rows that silently did not
make it into the answer, because that is how a wrong answer passes for a right
one.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop"))
from askbase.explain import explain


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


def test_a_limit_that_is_not_a_plain_number_is_not_guessed():
    # "LIMIT 2 + 3" used to be read as "не больше 2 строк": a wrong number
    # stated with confidence is worse than no number at all, because nobody
    # reads the SQL to check it.
    e = explain("SELECT name FROM clients LIMIT 2 + 3")
    assert "не больше 2" not in e.summary
    assert "ограничением" in e.summary


def test_an_offset_is_stated():
    # The rows at the top are missing from the answer and nothing else on the
    # screen says so.
    e = explain("SELECT name FROM clients ORDER BY name LIMIT 10 OFFSET 20")
    assert "20" in e.summary
    assert "пропуст" in e.summary


def test_asking_for_empty_values_is_not_reported_as_dropping_them():
    # "WHERE region_id IS NULL" keeps exactly the rows that the omission line
    # claimed were thrown away, which turns the explanation into the opposite
    # of the truth.
    e = explain("SELECT name FROM clients WHERE region_id IS NULL")
    assert not any("region_id" in o and "не заполнено" in o for o in e.omissions)


def test_requiring_a_value_still_warns_about_the_empty_ones():
    # The other way round the sentence is correct: IS NOT NULL does drop them.
    e = explain("SELECT name FROM clients WHERE region_id IS NOT NULL")
    assert any("region_id" in o and "не заполнено" in o for o in e.omissions)


def test_the_english_interface_gets_an_english_explanation():
    # This sentence is the product's trust claim. In the English build it came
    # out in Russian, which is worse than saying nothing: it reads as a product
    # that was translated carelessly and therefore measured carelessly.
    e = explain("SELECT a FROM t JOIN u ON u.id = t.u_id WHERE t.x = 1 LIMIT 10", lang="en")
    assert not re.search(r"[А-Яа-яЁё]", e.text()), e.text()
    assert "rows" in e.text()


def test_russian_is_still_the_default():
    e = explain("SELECT a FROM t")
    assert re.search(r"[А-Яа-яЁё]", e.summary)


def test_an_unknown_language_falls_back_rather_than_crashing():
    e = explain("SELECT a FROM t", lang="de")
    assert e.summary


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_both_languages_cover_every_phrase_the_module_uses(lang):
    from askbase.explain import PHRASES

    assert set(PHRASES["ru"]) == set(PHRASES["en"])
    assert all(v.strip() for v in PHRASES[lang].values())


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_every_sentence_ends_as_a_sentence(lang):
    e = explain("SELECT DISTINCT a FROM t JOIN u ON u.id = t.u_id GROUP BY a HAVING COUNT(*) > 1", lang=lang)
    assert e.summary.endswith(".")
    for o in e.omissions:
        assert o.endswith(".")


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_qualifiers_are_separated_by_commas(lang):
    # Without them the sentence runs on without a breath: "grouped by name
    # sorted limited to 50 rows skipping the first 10 rows".
    e = explain(
        "SELECT a FROM t GROUP BY a ORDER BY a LIMIT 50 OFFSET 10", lang=lang
    )
    assert e.summary.count(",") >= 3


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_a_short_sentence_has_no_stray_comma(lang):
    e = explain("SELECT a FROM t", lang=lang)
    assert "," not in e.summary
