"""Tests for the authoring checks.

Each rule exists because a defect of that shape was found by hand in set 1,
and each is built here against a throwaway database so that a change to the
set cannot quietly change what the rule is asserted to do. The last test is
the other half: it pins what the rules find in the real set, because a
checker validated only against its own fixtures is a checker that agrees with
itself.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from nl2sql_app.holdout.lint import check_set_wide, check_task, lint_set, report_row

ROOT = Path(__file__).resolve().parent.parent


def db(tmp_path, script):
    p = tmp_path / "t.sqlite"
    c = sqlite3.connect(p)
    c.executescript(script)
    c.commit()
    c.close()
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def rules(findings):
    return {f.rule for f in findings}


RANKED = """
CREATE TABLE dx (id INTEGER PRIMARY KEY, title TEXT);
INSERT INTO dx (title) VALUES
  ('a'), ('a'), ('a'),
  ('b'), ('b'),
  ('c'), ('c'),
  ('d');
"""


def test_a_cut_inside_a_tie_is_reported(tmp_path):
    """The defect found by reading the model's failures, not the scores.

    Two diagnoses both appear twice. "The top two" has no second place, and
    the gold's alphabetical tiebreak invents one the question never asked for.
    """
    conn = db(tmp_path, RANKED)
    gold = ("SELECT title, COUNT(*) AS n FROM dx GROUP BY title "
            "ORDER BY n DESC, title LIMIT 2")
    assert "ambiguous_cut" in rules(check_task(conn, "t", gold, [], ["x"]))


def test_a_cut_between_different_counts_is_not_reported(tmp_path):
    """The discrimination that makes the rule worth having.

    Top one is 'a' with three, second is 'b' with two. The cut at one falls
    between three and two, so there is nothing arbitrary about it, even
    though ties exist further down the list.
    """
    conn = db(tmp_path, RANKED)
    gold = ("SELECT title, COUNT(*) AS n FROM dx GROUP BY title "
            "ORDER BY n DESC, title LIMIT 1")
    assert "ambiguous_cut" not in rules(check_task(conn, "t", gold, [], ["x"]))


def test_a_gold_tied_on_every_ordering_key_is_reported(tmp_path):
    """The gold itself is a coin flip, not merely the question.

    Two titles both appear twice and the only ordering key is the count, so
    which of them is "the top one" is whatever the query plan reached first.
    The first version of this check was syntactic and missed it: the gold
    says `ORDER BY n DESC` and `n` is an alias, so no aggregate appears in
    the last key and the rule saw a tiebreak that is not there.
    """
    conn = db(tmp_path, "CREATE TABLE dx (title TEXT);"
                        "INSERT INTO dx VALUES ('a'),('a'),('b'),('b');")
    gold = "SELECT title, COUNT(*) AS n FROM dx GROUP BY title ORDER BY n DESC LIMIT 1"
    assert "nondeterministic_gold" in rules(check_task(conn, "t", gold, [], ["x"]))


def test_a_gold_with_a_tiebreak_is_only_called_ambiguous(tmp_path):
    """The same data with a tiebreak: reproducible gold, unanswerable question."""
    conn = db(tmp_path, "CREATE TABLE dx (title TEXT);"
                        "INSERT INTO dx VALUES ('a'),('a'),('b'),('b');")
    gold = ("SELECT title, COUNT(*) AS n FROM dx GROUP BY title "
            "ORDER BY n DESC, title LIMIT 1")
    got = rules(check_task(conn, "t", gold, [], ["x"]))
    assert "nondeterministic_gold" not in got
    assert "ambiguous_cut" in got


def test_a_gold_that_returns_nothing_is_reported(tmp_path):
    conn = db(tmp_path, RANKED)
    gold = "SELECT title FROM dx WHERE title = 'нет такого'"
    assert "gold_empty" in rules(check_task(conn, "t", gold, [], ["x"]))


def test_a_gold_that_does_not_run_is_reported_not_raised(tmp_path):
    conn = db(tmp_path, RANKED)
    assert "gold_fails" in rules(check_task(conn, "t", "SELECT nope FROM dx", [], ["x"]))


def test_an_average_with_a_long_tail_is_reported(tmp_path):
    conn = db(tmp_path, "CREATE TABLE m (v INTEGER); INSERT INTO m VALUES (1),(1),(2);")
    gold = "SELECT AVG(v) AS a FROM m"
    # 1/3 cannot be written down, so no answer can match it exactly and every
    # model loses the task to the last bit of a float.
    assert "float_noise" in rules(check_task(conn, "t", gold, [], ["x"]))


def test_a_clean_average_is_not(tmp_path):
    conn = db(tmp_path, "CREATE TABLE m (v INTEGER); INSERT INTO m VALUES (1),(3);")
    assert "float_noise" not in rules(
        check_task(conn, "t", "SELECT AVG(v) AS a FROM m", [], ["x"]))


def test_a_russian_wording_that_reads_as_a_filter_is_reported(tmp_path):
    conn = db(tmp_path, RANKED)
    w = [{"lang": "ru", "idx": 0, "text": "Сколько счетов открыто в каждой валюте?"}]
    gold = "SELECT title, COUNT(*) AS n FROM dx GROUP BY title"
    assert "filter_word_without_filter" in rules(check_task(conn, "t", gold, w, ["x"]))


def test_the_same_wording_is_fine_when_the_gold_does_filter(tmp_path):
    conn = db(tmp_path, RANKED)
    w = [{"lang": "ru", "idx": 0, "text": "Сколько счетов открыто в каждой валюте?"}]
    gold = ("SELECT title, COUNT(*) AS n FROM dx WHERE title <> 'd' "
            "GROUP BY title")
    assert "filter_word_without_filter" not in rules(
        check_task(conn, "t", gold, w, ["x"]))


def test_a_task_with_no_traps_is_reported(tmp_path):
    conn = db(tmp_path, RANKED)
    assert "no_traps" in rules(check_task(conn, "t", "SELECT title FROM dx", [], []))


def test_the_select_list_is_printed_beside_the_question():
    """The one judgement no rule makes, made cheap instead of automated."""
    row = report_row("t-1", "SELECT a, COUNT(*) AS n FROM x GROUP BY a",
                     [{"lang": "en", "idx": 0, "text": "How many per a?"}])
    assert "How many per a?" in row
    assert "a, COUNT(*) AS n" in row


@pytest.mark.parametrize("rule,tids", [
    ("float_noise", {"bank-006", "med-006"}),
    ("filter_word_without_filter", {"bank-001"}),
    ("ambiguous_cut", {"med-004"}),
])
def test_the_rules_find_what_the_hand_review_found(rule, tids):
    """The checker against the set the defects were found in by reading.

    `float_noise` is the eight records HOLDOUT.md attributes to floating-point
    noise after AVG, two tasks of four wordings each. `filter_word` is the
    exact example that file records, "Сколько счетов открыто в каждой
    валюте?". `ambiguous_cut` is med-004, found on 2 November in the queries
    the model got wrong rather than in any score. Set 1 is frozen, so these
    stay; set 2 is what the checker is for.

    Reads the generated set off disk, and `data/` is not published, so in the
    public copy there is nothing to read. Skipped there rather than asserted
    against an empty result, which is how this test used to fail on every
    public run while saying nothing about the checker.
    """
    if not (ROOT / "data/holdout").is_dir():
        pytest.skip("data/holdout не сгенерирован, проверять нечего")
    findings, _ = lint_set("data/holdout")
    assert {f.tid for f in findings if f.rule == rule} == tids


def test_a_tie_is_found_even_when_the_key_is_not_returned(tmp_path):
    """"Name the customer who received the most" returns a name, not an amount.

    The ordering key is then an aggregate that appears nowhere in the output,
    and the first version of the rule gave up and said so. On 600 tasks that
    would be a large and silent hole, because the questions shaped like this
    are exactly the ones a tie ruins. The key is spliced into the select list
    and read back instead.
    """
    conn = db(tmp_path, """
        CREATE TABLE sale (person TEXT, amount INTEGER);
        INSERT INTO sale VALUES ('a', 5), ('b', 3), ('c', 3);
    """)
    gold = ("SELECT person FROM sale GROUP BY person "
            "ORDER BY SUM(amount) DESC, person LIMIT 2")
    got = rules(check_task(conn, "t", gold, [], ["x"]))
    assert "ambiguous_cut" in got
    assert "cut_unchecked" not in got


def test_the_same_shape_is_clean_when_the_cut_misses_the_tie(tmp_path):
    conn = db(tmp_path, """
        CREATE TABLE sale (person TEXT, amount INTEGER);
        INSERT INTO sale VALUES ('a', 5), ('b', 3), ('c', 3);
    """)
    gold = ("SELECT person FROM sale GROUP BY person "
            "ORDER BY SUM(amount) DESC, person LIMIT 1")
    assert not rules(check_task(conn, "t", gold, [], ["x"]))


def test_an_ordering_key_holding_a_comma_is_still_checked(tmp_path):
    """Found while authoring med2-035, whose key is AVG of two julianday calls.

    `ORDER BY AVG(julianday(a) - julianday(COALESCE(b, c)))` holds a comma
    inside its brackets. The key list was split on every comma, so the rule
    rewrote half an expression, the query failed to parse and the cut was
    reported unchecked. That is a hole precisely where the hard tasks are, so
    the split now tracks bracket depth and this pins it: a tie behind such a
    key is found, not excused.
    """
    conn = db(tmp_path, """
        CREATE TABLE stay (dept TEXT, a TEXT, b TEXT);
        INSERT INTO stay VALUES
          ('x', '2026-01-01', '2026-01-11'),
          ('y', '2026-01-01', '2026-01-11'),
          ('z', '2026-01-01', '2026-01-02');
    """)
    gold = ("SELECT dept FROM stay GROUP BY dept "
            "ORDER BY AVG(julianday(b) - julianday(COALESCE(a, b))) DESC, dept "
            "LIMIT 1")
    got = rules(check_task(conn, "t", gold, [], ["x"]))
    assert "cut_unchecked" not in got
    assert "ambiguous_cut" in got


def test_a_gold_ordering_by_nothing_real_fails_before_the_cut_is_judged(tmp_path):
    """Written expecting cut_unchecked, and the code was right instead.

    A gold that orders by a column which does not exist never runs, so it is
    caught as a broken query rather than as an unverifiable cut. That is the
    better finding of the two and it comes first, which is what this pins.
    """
    conn = db(tmp_path, "CREATE TABLE sale (person TEXT); INSERT INTO sale VALUES ('a'),('b');")
    gold = "SELECT person FROM sale ORDER BY nonexistent DESC LIMIT 1"
    assert rules(check_task(conn, "t", gold, [], ["x"])) == {"gold_fails"}


# --- правила на весь набор, а не на одну задачу -----------------------------


def task(tid, gold, texts=()):
    return {"tid": tid, "gold_sql": gold,
            "wordings": [{"lang": "en", "idx": i, "text": t}
                         for i, t in enumerate(texts)],
            "traps": ["x"]}


def test_the_same_gold_twice_in_one_set_is_reported():
    """The defect found by hand after both passes of set 2 were written.

    bank2-024 and log2-024 held the same gold and the same English wording,
    differing only in which database they ran against, because banking and
    logistics both have a `cust` table with a nullable city. No per-task rule
    can see this, and the effect is a set that asks 288 questions and measures
    287.
    """
    got = check_set_wide([
        task("bank2-024", "SELECT COUNT(*) AS n FROM cust WHERE city IS NULL"),
        task("log2-024", "SELECT COUNT(*)  AS n FROM cust  WHERE city IS NULL"),
    ])
    assert [f.rule for f in got] == ["duplicate_gold"]
    assert got[0].tid == "log2-024", "сообщать надо о позднейшей задаче"


def test_the_same_wording_twice_is_reported_even_with_different_golds():
    got = check_set_wide([
        task("a-1", "SELECT 1", ["How many customers have no city?"]),
        task("b-1", "SELECT 2", ["How many customers have no city?"]),
    ])
    assert [f.rule for f in got] == ["duplicate_wording"]


def test_two_different_tasks_are_not_reported():
    got = check_set_wide([
        task("a-1", "SELECT COUNT(*) FROM cust WHERE city IS NULL", ["One?"]),
        task("b-1", "SELECT COUNT(*) FROM shp WHERE weight_kg > 10", ["Two?"]),
    ])
    assert got == []


def test_a_task_does_not_duplicate_itself():
    """Two wordings of one task are the point, not a defect."""
    t = task("a-1", "SELECT 1", ["How many?", "How many?"])
    assert check_set_wide([t]) == []
