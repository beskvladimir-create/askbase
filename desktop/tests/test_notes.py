"""The schema notes, and the promise that they can always be given up.

The detectors are tested where they live, in `tests/test_annotate.py`. What is
tested here is the part that is this application's own: the notes reach the
prompt, the structure the safety check works off does not depend on them, and
a database that defeats or outlasts a detector opens without them rather than
failing to open.
"""
from __future__ import annotations

import sqlite3

from askbase.engine import snapshot
from askbase.notes import collect, outline_text, render

SHOP = """
CREATE TABLE status_ref (cd INTEGER PRIMARY KEY, title TEXT);
INSERT INTO status_ref VALUES (1, 'paid'), (2, 'refunded');
CREATE TABLE sale (
    id        INTEGER PRIMARY KEY,
    total_cents INTEGER,
    status_cd INTEGER REFERENCES status_ref(cd)
);
INSERT INTO sale VALUES (1, 1990, 1);
"""


def make(tmp_path, script):
    p = tmp_path / "t.sqlite"
    con = sqlite3.connect(p)
    con.executescript(script)
    con.commit()
    con.close()
    return str(p)


def test_the_notes_reach_the_prompt(tmp_path):
    text = snapshot(make(tmp_path, SHOP)).serialise()
    # The example values already say the column holds 1 and 2. The note is
    # what says which of them means paid.
    assert 'example values in "status_ref"' in text
    assert "sale.status_cd: a code (status_ref): 1=paid, 2=refunded" in text
    assert "sale.total_cents" in text and "divide by 100" in text
    assert "sale.status_cd -> status_ref.cd" in text


def test_the_structure_the_safety_check_uses_is_unchanged_by_notes(tmp_path):
    """The check must not come to depend on a detector having found anything.

    `as_dict` is what decides whether a generated query names a real table.
    If the notes ever leaked into it, a database with no notes would start
    rejecting valid queries, and the failure would look like a safety bug.
    """
    schema = snapshot(make(tmp_path, SHOP))
    assert schema.as_dict() == {
        "status_ref": {"cd", "title"},
        "sale": {"id", "total_cents", "status_cd"},
    }


def test_an_interrupted_scan_costs_the_notes_and_not_the_file(tmp_path):
    """A deadline fires mid-detector. The file still opens, without notes.

    This is the real case, not a hypothetical one: proving a date pair is
    mutually exclusive means reading every row, and on a database of any size
    the connection's progress handler is what stops it.
    """
    path = make(tmp_path, SHOP)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        con.set_progress_handler(lambda: 1, 1)      # abort at the first chance
        assert collect(con, ["sale", "status_ref"]) == ([], [])
    finally:
        con.set_progress_handler(None, 1)
        con.close()


def test_a_connection_that_cannot_be_read_costs_the_notes_and_not_the_file():
    con = sqlite3.connect(":memory:")
    con.close()
    assert collect(con, ["anything"]) == ([], [])


def test_nothing_to_say_adds_nothing_to_the_prompt(tmp_path):
    plain = make(tmp_path, "CREATE TABLE a (id INTEGER PRIMARY KEY, nm TEXT);")
    text = snapshot(plain).serialise()
    assert "Notes on the columns" not in text
    assert "Foreign keys" not in text
    # And no stray blank lines where the block would have gone.
    assert not text.endswith("\n")
    assert render([], []) == ""


def test_every_note_kind_has_a_wording_in_both_languages():
    """The guard that keeps a new detector from shipping half-translated.

    A detector added in the research package reaches this window the moment it
    is written, because the window renders whatever notes it is handed. Without
    this test the new kind would simply not appear on screen, which is the one
    failure mode that looks like nothing at all: the model is told a fact and
    the person is not shown it, which is exactly the asymmetry the panel exists
    to remove.
    """
    from askbase.i18n import TEXTS

    from nl2sql_app.bench.annotate import TEMPLATES

    for kind in TEMPLATES:
        for lang, texts in TEXTS.items():
            assert f"note_{kind}" in texts, f"{kind} has no wording in {lang}"


def test_the_notes_are_on_screen_in_the_language_of_the_window(tmp_path):
    from askbase.i18n import TEXTS

    schema = snapshot(make(tmp_path, SHOP))
    ru = outline_text(schema, TEXTS["ru"])
    en = outline_text(schema, TEXTS["en"])
    assert TEXTS["ru"]["understood"] in ru
    assert "sale.status_cd: код из status_ref: 1=paid, 2=refunded" in ru
    assert "sale.total_cents: копейки" in ru
    assert "sale.status_cd: a code from status_ref: 1=paid, 2=refunded" in en
    # The instruction to the model stays out of it. The person is checking
    # whether this is true of their database, and COALESCE is not something
    # they can confirm or deny.
    assert "COALESCE" not in ru and "COALESCE" not in en
    # And the tables are still there, above.
    assert ru.index("sale:") < ru.index(TEXTS["ru"]["understood"])


def test_a_long_dictionary_is_shortened_on_screen_and_not_in_the_prompt(tmp_path):
    from askbase.i18n import TEXTS

    rows = ", ".join(f"({i}, 'title number {i}')" for i in range(1, 13))
    schema = snapshot(make(tmp_path, f"""
        CREATE TABLE mcc_ref (cd INTEGER PRIMARY KEY, title TEXT);
        INSERT INTO mcc_ref VALUES {rows};
        CREATE TABLE txn (id INTEGER PRIMARY KEY, mcc_cd INTEGER);
        INSERT INTO txn VALUES (1, 1);
    """))
    on_screen = outline_text(schema, TEXTS["en"])
    in_prompt = schema.serialise()
    assert "…" in on_screen
    assert "title number 12" in in_prompt
    assert "title number 12" not in on_screen


def test_a_note_with_no_wording_is_left_out_rather_than_shown_raw(tmp_path):
    """Belt and braces for the test above, which only fails in development."""
    from askbase.notes import for_person

    schema = snapshot(make(tmp_path, SHOP))
    assert for_person(schema.notes, {}) == []


def test_the_measured_prompt_is_the_shipped_prompt(tmp_path):
    """The schema block the harness measures is the one this window sends.

    They were two renderers and nobody had compared them. The published
    figure was measured on a compact `t(a, b)` listing with no example values,
    in creation order and without views, while the application sent quoted
    CREATE TABLE statements with example values attached, in alphabetical
    order and with views included. Neither number described the other prompt.
    One renderer now serves both, and this is what keeps it that way: the only
    thing the window adds is the notes block.
    """
    from nl2sql_app.bench.schema import serialize_schema

    path = make(tmp_path, SHOP)
    shipped = snapshot(path).serialise()
    measured = serialize_schema(path, ddl=True, samples=3)
    assert shipped.startswith(measured)
    rest = shipped[len(measured):]
    assert rest.lstrip("\n").startswith("Foreign keys:")
