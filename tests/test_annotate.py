"""Tests for the schema-note detectors.

Most of these build a throwaway database rather than leaning on the held-out
set, so a change to the set cannot quietly change what the detectors are
asserted to do. The two that do read the real set pin empirical claims the
module's docstring makes out loud, which would otherwise be prose nobody
checks.
"""
from __future__ import annotations

import sqlite3

import pytest

from nl2sql_app.bench.annotate import (
    annotate_schema,
    foreign_keys,
    schema_notes,
)

HOLDOUT = "data/holdout"


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "t.sqlite"
    c = sqlite3.connect(p)
    c.executescript(
        """
        CREATE TABLE status_ref (cd INTEGER PRIMARY KEY, title TEXT);
        INSERT INTO status_ref VALUES (1, 'open'), (2, 'shut');
        CREATE TABLE big_ref (cd INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE item (
            id        INTEGER PRIMARY KEY,
            cost_cents INTEGER,
            rate_bp   INTEGER,
            status_cd INTEGER REFERENCES status_ref(cd),
            big_cd    INTEGER
        );
        INSERT INTO item VALUES (1, 100, 50, 1, 1);
        """
    )
    c.executemany("INSERT INTO big_ref VALUES (?, ?)",
                  [(i, f"n{i}") for i in range(1, 40)])
    c.commit()
    c.close()
    return str(p)


def test_minor_units_and_basis_points_are_both_named(db):
    notes = " | ".join(schema_notes(db))
    assert "item.cost_cents" in notes and "divide by 100" in notes
    assert "item.rate_bp" in notes and "basis points" in notes


def test_a_small_lookup_is_quoted_and_a_large_one_is_only_named(db):
    notes = " | ".join(schema_notes(db))
    assert "item.status_cd: a code (status_ref): 1=open, 2=shut" in notes
    # 39 rows is past MAX_LOOKUP_ROWS: naming the table beats flooding the
    # prompt, and the model joins correctly once it knows where to look.
    assert "item.big_cd: a code, decoded in big_ref" in notes


def test_a_lookup_table_does_not_annotate_its_own_key(db):
    # status_ref.cd IS the dictionary. Describing it as a code to decode says
    # nothing and used to crowd out the notes that do.
    assert not any(n.startswith("status_ref.") for n in schema_notes(db))


def test_nothing_to_say_gives_an_empty_block(tmp_path):
    p = tmp_path / "plain.sqlite"
    c = sqlite3.connect(p)
    c.executescript("CREATE TABLE a (id INTEGER PRIMARY KEY, name TEXT);")
    c.commit()
    c.close()
    assert annotate_schema(str(p)) == ""
    assert annotate_schema(str(p), keys=True) == ""


def test_a_migrated_date_pair_is_reported_and_two_events_are_not(tmp_path):
    """Mutual exclusivity is the whole discriminator, so it gets its own test."""
    p = tmp_path / "d.sqlite"
    c = sqlite3.connect(p)
    c.executescript(
        """
        CREATE TABLE split (id INTEGER PRIMARY KEY, dt_op TEXT, posted_at TEXT);
        INSERT INTO split VALUES (1, '2026-01-01', NULL), (2, NULL, '2026-01-02');
        CREATE TABLE events (id INTEGER PRIMARY KEY, sent_at TEXT, got_at TEXT);
        INSERT INTO events VALUES (1, '2026-01-01', NULL),
                                  (2, NULL, '2026-01-02'),
                                  (3, '2026-01-03', '2026-01-04');
        """
    )
    c.commit()
    c.close()
    notes = " | ".join(schema_notes(str(p)))
    assert "COALESCE(dt_op, posted_at)" in notes
    # One row with both filled is enough to mean two separate events. Without
    # this the detector called dispatched_at/delivered_at a migration too, and
    # told the model to collapse two different dates into one.
    assert "got_at" not in notes


def test_history_tables_get_the_right_one_of_the_two_shapes(tmp_path):
    p = tmp_path / "h.sqlite"
    c = sqlite3.connect(p)
    c.executescript(
        """
        CREATE TABLE pay (id INTEGER PRIMARY KEY, emp_id INTEGER, from_dt TEXT);
        INSERT INTO pay VALUES (1, 7, '2025-01-01'), (2, 7, '2026-01-01');
        CREATE TABLE price (id INTEGER PRIMARY KEY, part_id INTEGER,
                            valid_from TEXT, valid_to TEXT);
        INSERT INTO price VALUES (1, 3, '2025-01-01', '2026-01-01'),
                                 (2, 3, '2026-01-01', NULL);
        CREATE TABLE once (id INTEGER PRIMARY KEY, thing_id INTEGER, from_dt TEXT);
        INSERT INTO once VALUES (1, 1, '2026-01-01'), (2, 2, '2026-01-01');
        """
    )
    c.commit()
    c.close()
    notes = " | ".join(schema_notes(str(p)))
    assert "pay: history per emp_id" in notes and "latest from_dt" in notes
    assert "price: rows are effective-dated per part_id" in notes
    assert "valid_to IS NULL means still in force" in notes
    # A key that never repeats is not a history, whatever its columns suggest.
    assert "once:" not in notes


def test_keys_are_printed_because_serialize_schema_drops_them():
    fk = foreign_keys(f"{HOLDOUT}/logistics/logistics.sqlite")
    # Both ends of the route point at the same lookup, which is exactly what
    # no rule over column names could have found.
    assert "shp.org_cd -> loc_ref.cd" in fk
    assert "shp.dst_cd -> loc_ref.cd" in fk


def test_the_declared_key_catches_what_the_name_cannot():
    notes = " | ".join(schema_notes(f"{HOLDOUT}/logistics/logistics.sqlite"))
    for col in ("shp.org_cd", "shp.dst_cd"):
        assert f"{col}: a code (loc_ref)" in notes


def test_the_notes_never_mention_a_question_or_a_gold_query():
    """The property that makes this a feature and not a benchmark hack.

    Every detector reads the database and nothing else. If a note ever carried
    text from a task file, the arm would be measuring a leak instead of an
    annotation, and no later number could be trusted. Asserted over the whole
    set rather than argued in a comment.
    """
    import json
    from pathlib import Path

    wordings: set[str] = set()
    golds: set[str] = set()
    for f in sorted(Path(HOLDOUT).glob("*/tasks.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for t in (d if isinstance(d, list) else d["tasks"]):
            golds.add(t["gold_sql"])
            for w in t["wordings"]:
                wordings.add(w["text"] if isinstance(w, dict) else str(w))
    for dom in sorted(p.name for p in Path(HOLDOUT).iterdir() if p.is_dir()):
        notes = schema_notes(f"{HOLDOUT}/{dom}/{dom}.sqlite")
        blob = " ".join(notes)
        for q in wordings:
            assert q not in blob
        for g in golds:
            assert g not in blob


def test_a_dictionary_without_the_ref_suffix_is_still_found(tmp_path):
    """The generalisation that keeps this from being a benchmark artefact.

    The first version of the detector required a lookup table's name to end in
    `_ref`, which is a convention of `data/holdout` and of nothing a user will
    ever open. Here the dictionary is called `genres`, declares no foreign key
    and spells its key in camel case, which is what the databases people
    actually have look like.
    """
    p = tmp_path / "chinook.sqlite"
    c = sqlite3.connect(p)
    c.executescript(
        """
        CREATE TABLE genres (GenreId INTEGER PRIMARY KEY, Name TEXT);
        INSERT INTO genres VALUES (1, 'Rock'), (2, 'Jazz');
        CREATE TABLE tracks (TrackId INTEGER PRIMARY KEY, Name TEXT,
                             GenreId INTEGER);
        INSERT INTO tracks VALUES (1, 'a', 1);
        """
    )
    c.commit()
    c.close()
    notes = " | ".join(schema_notes(str(p)))
    assert "tracks.GenreId: a code (genres): 1=Rock, 2=Jazz" in notes


def test_a_dictionary_also_gets_its_own_codes_decoded(tmp_path):
    """A small table is a dictionary to others and a user of others at once.

    `line` holds four rows, so the size rule calls it a dictionary, and it
    still has a shift_cd that needs decoding. Excluding a dictionary from
    decoding altogether lost exactly this note when the size rule arrived.
    """
    p = tmp_path / "mfg.sqlite"
    c = sqlite3.connect(p)
    c.executescript(
        """
        CREATE TABLE shift_ref (cd INTEGER PRIMARY KEY, title TEXT);
        INSERT INTO shift_ref VALUES (1, 'day'), (2, 'night');
        CREATE TABLE line (id INTEGER PRIMARY KEY, title TEXT,
                           shift_cd INTEGER);
        INSERT INTO line VALUES (1, 'A', 1), (2, 'B', 2);
        """
    )
    c.commit()
    c.close()
    notes = schema_notes(str(p))
    assert any(n.startswith("line.shift_cd: a code (shift_ref)") for n in notes)
    # Its own key is still not described as a code pointing elsewhere.
    assert not any(n.startswith("line.id") for n in notes)
    assert not any(n.startswith("shift_ref.cd") for n in notes)


def test_a_table_past_the_cap_is_not_treated_as_a_dictionary(tmp_path):
    p = tmp_path / "wide.sqlite"
    c = sqlite3.connect(p)
    c.executescript(
        """
        CREATE TABLE person (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE visit (id INTEGER PRIMARY KEY, person_id INTEGER);
        INSERT INTO visit VALUES (1, 1);
        """
    )
    c.executemany("INSERT INTO person VALUES (?, ?)",
                  [(i, f"n{i}") for i in range(1, 60)])
    c.commit()
    c.close()
    # 59 people are not a dictionary, and quoting them would be the prompt
    # filled with data instead of with facts about the schema.
    assert not any("person" in n for n in schema_notes(str(p)))


def test_counting_a_table_stops_at_the_cap(tmp_path):
    """The bound that makes this safe to run on a database of any size.

    `COUNT(*)` on a fact table is a full scan, and the notes are collected the
    moment a file is opened. The counter must stop as soon as the answer is
    known to be "more than the cap".
    """
    from nl2sql_app.bench.annotate import _row_cap

    p = tmp_path / "many.sqlite"
    c = sqlite3.connect(p)
    c.executescript("CREATE TABLE t (id INTEGER PRIMARY KEY);")
    c.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(5000)])
    c.commit()
    c.close()
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        assert _row_cap(conn, "t", 24) == 25
        assert _row_cap(conn, "t", 4) == 5
    finally:
        conn.close()


def test_a_unit_note_asks_for_a_divisor_that_keeps_the_fraction(db):
    """The note used to say "divide by 100" and that cost money.

    SQLite divides integers into integers. A column of cents summed and
    divided by 100 comes back whole, so a total of 8 579 947.13 was returned
    as 8 579 038. Four of the sixteen real errors on the English wordings were
    this and nothing else, and on the plain stage, with no note telling the
    model to divide at all, there was one. A note that creates the failure it
    exists to prevent is worse than no note.
    """
    notes = " | ".join(schema_notes(db))
    assert "divide by 100.0" in notes
    assert "divide by 100," not in notes and "divide by 100 " not in notes
