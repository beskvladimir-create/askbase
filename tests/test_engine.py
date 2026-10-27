"""The engine, with a stub model. No Ollama, no network, no GPU.

These tests exist to pin the promise rather than the plumbing: the model never
reaches the database, nothing but a single SELECT is executed, and a wrong
answer is reported as wrong rather than dressed up.
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop"))
from askbase.engine import AskError, Engine, extract_sql, snapshot


@dataclass
class Reply:
    text: str


class StubModel:
    """Returns the prepared answers in order, and records what it was shown."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, prompt: str, **_):
        self.prompts.append(prompt)
        return Reply(self.replies.pop(0) if self.replies else "")


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "shop.sqlite"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE regions (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT,
                              region_id INTEGER, status_cd INTEGER);
        INSERT INTO regions VALUES (1,'North'),(2,'South');
        INSERT INTO clients VALUES (1,'Ann',1,1),(2,'Bob',1,2),(3,'Cid',2,1),(4,'Dee',NULL,1);
    """)
    con.commit()
    con.close()
    return str(path)


def test_snapshot_reads_the_structure(db):
    s = snapshot(db)
    assert set(s.tables) == {"regions", "clients"}
    assert "region_id" in s.tables["clients"]
    assert s.n_columns == 6


def test_snapshot_samples_coded_columns_but_not_unique_ones(db):
    # status_cd holds 1 and 2: the model cannot guess that from the name.
    # Names are all different, so listing them would teach nothing.
    s = snapshot(db)
    hints = " ".join(s.samples.get("clients", []))
    assert "status_cd" in hints
    assert "name is one of" not in hints


def test_the_schema_shown_to_the_model_carries_the_samples(db):
    model = StubModel("```sql\nSELECT name FROM clients\n```")
    Engine(db, model).ask("who are the clients")
    assert "status_cd is one of" in model.prompts[0]


def test_a_question_becomes_an_answer(db):
    model = StubModel("```sql\nSELECT name FROM clients ORDER BY name\n```")
    a = Engine(db, model).ask("list the clients")
    assert a.columns == ["name"]
    assert [r[0] for r in a.rows] == ["Ann", "Bob", "Cid", "Dee"]
    assert "LIMIT" in a.sql.upper()          # the row cap is added for us
    assert a.explanation


def test_an_inner_join_answer_states_what_it_dropped(db):
    model = StubModel(
        "```sql\nSELECT c.name FROM clients c JOIN regions r ON r.id = c.region_id\n```"
    )
    a = Engine(db, model).ask("clients with a region")
    assert len(a.rows) == 3                  # Dee has no region
    assert "не попали" in a.explanation      # and the user is told so


def test_a_write_is_refused_and_never_reaches_the_database(db):
    model = StubModel("```sql\nDELETE FROM clients\n```", "```sql\nDROP TABLE clients\n```")
    with pytest.raises(AskError):
        Engine(db, model).ask("remove everyone")
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 4
    con.close()


def test_a_broken_query_gets_one_repair_attempt(db):
    model = StubModel(
        "```sql\nSELECT nome FROM clients\n```",        # typo, rejected by the check
        "```sql\nSELECT name FROM clients\n```",
    )
    a = Engine(db, model).ask("list the clients")
    assert len(a.rows) == 4
    assert len(model.prompts) == 2


def test_a_second_failure_is_reported_not_hidden(db):
    model = StubModel("```sql\nSELECT nope FROM nowhere\n```",
                      "```sql\nSELECT still FROM missing\n```")
    with pytest.raises(AskError) as e:
        Engine(db, model).ask("nonsense")
    assert str(e.value)


def test_an_empty_reply_is_an_error_with_a_readable_message(db):
    with pytest.raises(AskError) as e:
        Engine(db, StubModel("")).ask("anything")
    assert "Попробуйте" in str(e.value)


def test_rows_are_capped_and_the_cap_is_declared(db):
    model = StubModel("```sql\nSELECT name FROM clients\n```")
    a = Engine(db, model, max_rows=2).ask("list the clients")
    assert len(a.rows) == 2
    assert a.truncated
    assert any("2" in n for n in a.notes)


def test_zero_rows_is_an_answer_not_a_failure(db):
    model = StubModel("```sql\nSELECT name FROM clients WHERE name = 'nobody'\n```")
    a = Engine(db, model).ask("find nobody")
    assert a.rows == []
    assert a.explanation


def test_the_connection_is_read_only_even_if_the_check_were_bypassed(db):
    from askbase.engine import run_query
    with pytest.raises(sqlite3.OperationalError):
        run_query(db, "DELETE FROM clients", 10, 5.0)


@pytest.mark.parametrize("reply,expected", [
    ("```sql\nSELECT 1\n```", "SELECT 1"),
    ("```\nSELECT 1\n```", "SELECT 1"),
    ("Sure! Here you go:\nSELECT 1;", "SELECT 1"),
    ("Thinking...\nThe answer is\nWITH a AS (SELECT 1) SELECT * FROM a", "WITH a AS (SELECT 1) SELECT * FROM a"),
])
def test_sql_is_extracted_from_whatever_the_model_wraps_it_in(reply, expected):
    assert extract_sql(reply) == expected


def test_steps_are_reported_for_the_interface(db):
    seen: list[str] = []
    model = StubModel("```sql\nSELECT name FROM clients\n```")
    Engine(db, model).ask("list", on_step=seen.append)
    assert seen[0] == "writing"
    assert "running" in seen


def test_the_row_cap_shown_is_the_one_the_user_was_promised(db):
    # The check runs with max_rows + 1 so truncation can be detected. That
    # extra row is an implementation detail: "LIMIT 1001" on screen is
    # nonsense to read and invites a question with no good answer.
    model = StubModel("```sql\nSELECT name FROM clients\n```")
    a = Engine(db, model, max_rows=1000).ask("list the clients")
    assert "LIMIT 1000" in a.sql.upper()
    assert "1001" not in a.sql
    assert "1001" not in a.explanation
    assert not any("1001" in n for n in a.notes)


def test_an_explicit_limit_from_the_model_is_left_alone(db):
    model = StubModel("```sql\nSELECT name FROM clients LIMIT 3\n```")
    a = Engine(db, model, max_rows=1000).ask("three clients")
    assert "LIMIT 3" in a.sql.upper()
def test_a_hash_in_the_path_opens_that_file_and_not_a_new_one(tmp_path):
    # The path is pasted into a file: URI. A '#' starts the fragment, so SQLite
    # used to open a different file, create it because it was missing, and
    # report a database with no tables. "Отчёты #2" is an ordinary folder name.
    folder = tmp_path / "Отчёты #2"
    folder.mkdir()
    path = folder / "база.sqlite"
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE clients (id INTEGER, name TEXT); INSERT INTO clients VALUES (1,'Ann');")
    con.commit()
    con.close()

    s = snapshot(str(path))
    assert set(s.tables) == {"clients"}, "база с '#' в пути открылась не та"
    assert sorted(p.name for p in folder.iterdir()) == ["база.sqlite"], "рядом появился лишний файл"


def test_the_connection_stays_read_only_for_a_path_with_a_hash(tmp_path):
    # The same escaping hole broke the promise the whole product rests on: with
    # the URI cut short at the '#', mode=ro never reached SQLite and the
    # connection came back writable.
    path = tmp_path / "data #1.sqlite"
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE clients (id INTEGER); INSERT INTO clients VALUES (1);")
    con.commit()
    con.close()

    from askbase.engine import run_query
    with pytest.raises(sqlite3.OperationalError):
        run_query(str(path), "DELETE FROM clients", 10, 5.0)
    with pytest.raises(sqlite3.OperationalError):
        run_query(str(path), "CREATE TABLE sneaky (a)", 10, 5.0)


def test_a_view_is_part_of_the_schema(tmp_path):
    # In somebody else's database the readable part is often a set of views.
    # Leaving them out hid them from the model and made the safety check refuse
    # the question as a name that does not exist.
    path = tmp_path / "views.sqlite"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE raw_clients (id INTEGER, nm TEXT, deleted INTEGER);
        INSERT INTO raw_clients VALUES (1,'Ann',0),(2,'Bob',1);
        CREATE VIEW clients AS SELECT id, nm AS name FROM raw_clients WHERE deleted = 0;
    """)
    con.commit()
    con.close()

    s = snapshot(str(path))
    assert "clients" in s.tables
    assert s.tables["clients"] == ["id", "name"]

    model = StubModel("```sql\nSELECT name FROM clients\n```")
    a = Engine(str(path), model).ask("who are the clients")
    assert [r[0] for r in a.rows] == ["Ann"]


def test_names_that_need_quoting_are_quoted_in_the_schema(tmp_path):
    # "CREATE TABLE sales 2026 (order, ...)" is not SQL. The model copies the
    # schema it is shown, so the application was handing it a name it could
    # only write back wrongly.
    path = tmp_path / "odd.sqlite"
    con = sqlite3.connect(path)
    con.executescript(
        'CREATE TABLE "sales 2026" ("order" TEXT, "итого" INTEGER);'
        'INSERT INTO "sales 2026" VALUES (\'a\', 5);'
    )
    con.commit()
    con.close()

    model = StubModel('```sql\nSELECT "итого" FROM "sales 2026"\n```')
    engine = Engine(str(path), model)
    assert '"sales 2026"' in engine.schema.serialise()
    assert '"order"' in engine.schema.serialise()
    a = engine.ask("сколько итого")
    assert [r[0] for r in a.rows] == [5]


def test_a_file_without_tables_is_refused_when_it_is_opened(tmp_path):
    # Otherwise the file looks opened, and every question dies a minute later
    # with "there is no such thing in the database", which reads as the
    # application failing rather than the file being wrong.
    path = tmp_path / "empty.sqlite"
    sqlite3.connect(path).close()
    with pytest.raises(AskError) as e:
        Engine(str(path), StubModel())
    assert "таблиц" in str(e.value)


def test_a_query_that_runs_out_of_time_is_not_sent_back_to_the_model(db):
    # A query stopped by the clock is not a broken query: there is nothing for
    # the model to repair, and the user would wait the whole round again only
    # to be told "interrupted", which explains nothing.
    joins = ", ".join(f"clients t{i}" for i in range(14))      # 4**14 combinations
    heavy = f"SELECT COUNT(*) FROM {joins}"
    model = StubModel(f"```sql\n{heavy}\n```", "```sql\nSELECT name FROM clients\n```")
    engine = Engine(db, model, timeout=0.2)
    with pytest.raises(AskError) as e:
        engine.ask("тяжёлый вопрос")
    assert "слишком тяжёлый" in str(e.value)
    assert len(model.prompts) == 1, "запрос по таймауту не должен уходить на исправление"


def test_a_model_that_is_not_running_is_reported_readably(db):
    # ModelClient raises RuntimeError when nothing answers on the loopback
    # port. Unwrapped it reached the window as "unexpected error" with a
    # traceback under it, for the most ordinary failure there is.
    class Absent:
        def complete(self, prompt, **_):
            raise RuntimeError("Локальная модель не отвечает. Проверьте, что Ollama запущена.")

    with pytest.raises(AskError) as e:
        Engine(db, Absent()).ask("сколько клиентов")
    assert "Ollama" in str(e.value)


def test_a_model_that_times_out_is_reported_readably(db):
    class TooSlow:
        def complete(self, prompt, **_):
            raise TimeoutError("timed out")

    with pytest.raises(AskError):
        Engine(db, TooSlow()).ask("сколько клиентов")
