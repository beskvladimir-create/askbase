"""What the columns mean, read from the database and put in the prompt.

A model that writes good SQL still cannot know that `amt_cents` is hundredths,
that `status_cd = 1` means active, or that `dt_op` and `posted_at` are one
field left in two columns by a migration. The hand review of the held-out set
split every failure by who held the missing information, and schema semantics
was the largest share by a distance: on tasks whose only difficulty was of that
kind the model scored 39%, against 90% where no such difficulty existed, both
on the relaxed measure; strictly, 31.6% against 68.8%. Adding
these notes moved the same model from 49% to 69% on that set. Those are
development numbers on a set whose failures have been read, and `HOLDOUT.md`
says so plainly; what they settled is that this step belongs in the product,
not what it scores.

Asking the person is the wrong fix. They do not know whether cost is in cents
either, and demanding it teaches them the application is guessing. The fact is
in the database, so it is read from the database.

Nothing here reads the question. The notes are a property of the file that was
opened, collected once when it opens, and they say only what a join could
already have reached.

The detectors themselves are `nl2sql_app.bench.annotate`, imported rather than
copied, so the text this application puts in a prompt is the same text the
published measurement ran against. A copy would have been free to drift, and
the drift would have been invisible: both versions would keep passing their
own tests while the shipped one slowly stopped being the measured one. What
this module adds is the part a product needs and a benchmark does not, which
is the bounds and the refusal to fail.
"""
from __future__ import annotations

import contextlib
import sqlite3

from nl2sql_app.bench.annotate import Note, detail_from, keys_from

# Note collection runs while a file is opening, with the person waiting at a
# dialog, so it gets its own budget rather than the connection timeout. The
# detectors scan: a mutually-exclusive date pair is only proved by looking at
# every row, and on a large table that is the one query here that cannot stop
# early. Five seconds is enough for the databases this is for and short enough
# that nobody watches it.
BUDGET = 5.0


def collect(con: sqlite3.Connection, tables: list[str]
            ) -> tuple[list[str], list[Note]]:
    """The declared keys and the notes for those tables, and never an error.

    A note improves a prompt, it is not a condition of opening a file. A
    database that defeats the detectors, or one large enough that the
    connection's deadline interrupts a scan, loses its notes and opens anyway.
    The alternative is a file the person cannot open because the part meant to
    help it failed, which is a worse product than one with no notes at all.
    """
    keys: list[str] = []
    notes: list[Note] = []
    with contextlib.suppress(sqlite3.Error):
        keys = keys_from(con, tables)
    with contextlib.suppress(sqlite3.Error):
        # The parts and not the sentence: the window shows the same notes to
        # the person in the language of its interface, and the prompt gets the
        # English wording from the same template.
        notes = detail_from(con, tables)
    return keys, notes


def render(keys: list[str], notes: list[Note]) -> str:
    """The prompt block, empty when there is nothing to say.

    Names appear here unquoted, as prose about columns rather than as SQL to
    copy. The CREATE TABLE block above quotes every identifier and is where
    the model takes names from, and this is the wording that was measured.
    """
    blocks = []
    if keys:
        blocks.append("Foreign keys:\n" + "\n".join(f"- {k}" for k in keys))
    if notes:
        blocks.append("Notes on the columns:\n"
                      + "\n".join(f"- {n.render()}" for n in notes))
    return "\n\n".join(blocks)


# A dictionary of eight rows belongs in the prompt in full and on screen in
# part. The person is checking that the application found the right dictionary,
# not reading it, and an untruncated one runs off the side of a panel that does
# not wrap.
PANEL_ROWS = 80


def for_person(notes: list[Note], t: dict[str, str]) -> list[str]:
    """The notes in the words of the interface, one line each.

    A note whose kind has no wording in `t` is left out rather than shown as a
    key or as English in a Russian window. The test that every kind has a pair
    in both languages is what keeps that from silently hiding a detector.
    """
    out = []
    for n in notes:
        template = t.get(f"note_{n.kind}")
        if template is None:
            continue
        fields = dict(n.fields)
        rows = fields.get("rows")
        if rows and len(rows) > PANEL_ROWS:
            fields["rows"] = rows[:PANEL_ROWS].rstrip(" ;,") + "…"
        out.append(template.format(**fields))
    return out


def outline_text(schema, t: dict[str, str]) -> str:
    """The tables, and under them what the application read out of them.

    The panel's promise is that what the model is shown is shown to the person
    as well. Until the notes arrived that was the whole schema; with them it
    stopped being true, and the half that was missing is the half that is
    interpretation rather than fact. A note that is wrong about somebody's
    database produces a confident wrong answer with nothing on screen to
    question, so it goes where they can see it.
    """
    text = schema.outline()
    lines = for_person(schema.notes, t)
    if lines:
        text += "\n\n" + t["understood"] + "\n"
        text += "\n".join("  " + x for x in lines)
    return text
