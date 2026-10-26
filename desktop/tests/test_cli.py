"""The terminal command, tested without a model and without Qt.

Role 2 in docs/roles.md wants this inside scripts, and a script can only react
to what it can tell apart. So the exit codes are the contract here, and each
one gets a test: an answer, a refusal, a database that is not there. The model
is a stub, because what is being checked is the wrapper, not the weights.

The Qt absence is checked too. The command exists so that Windows and Linux
get something, and the only thing keeping that true is that nothing on this
path imports PySide6.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from askbase import cli

MODEL = "stub-model"


@pytest.fixture
def db(tmp_path) -> str:
    p = tmp_path / "shop.sqlite"
    con = sqlite3.connect(p)
    con.executescript(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, region TEXT);"
    )
    con.executemany(
        "INSERT INTO customers VALUES (?,?,?)",
        [(i, f"C{i}", ["Leeds", "Thorne"][i % 2]) for i in range(1, 41)],
    )
    con.commit()
    con.close()
    return str(p)


class StubReply:
    def __init__(self, text: str) -> None:
        self.text = text


class StubClient:
    """Answers with whatever it was told to answer, however many times."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.asked: list[str] = []

    def complete(self, prompt: str):
        self.asked.append(prompt)
        text = self.replies[min(len(self.asked) - 1, len(self.replies) - 1)]
        return StubReply(text)

    def reset(self) -> None:
        pass

    def cancel(self) -> None:
        pass


@pytest.fixture
def stub(monkeypatch):
    """Install a stub model, and hand back a setter for its replies."""
    holder: dict[str, StubClient] = {}

    def install(*replies: str) -> StubClient:
        client = StubClient(*replies)
        holder["c"] = client
        monkeypatch.setattr(cli, "ModelClient", lambda *a, **k: client)
        monkeypatch.setattr(cli, "installed_models", lambda: [MODEL])
        return client

    return install


@pytest.fixture(autouse=True)
def journal_in_tmp(tmp_path, monkeypatch):
    # The journal is a real file in the user's Application Support folder. A
    # test run must not append to the journal of whoever is running it.
    monkeypatch.setenv("ASKBASE_JOURNAL", str(tmp_path / "journal.jsonl"))


# ---------------------------------------------------------------- codes ----

def test_an_answer_exits_zero_and_prints_a_table(db, stub, capsys):
    stub("```sql\nSELECT region, COUNT(*) FROM customers GROUP BY region\n```")
    code = cli.main(["How many customers per region", "--db", db, "--quiet"])
    out = capsys.readouterr().out
    assert code == cli.OK
    assert "Leeds" in out and "Thorne" in out


def test_a_question_that_cannot_pass_the_check_exits_two(db, stub, capsys):
    # The model insists on a write. One repair attempt happens, then refusal.
    stub("```sql\nDELETE FROM customers\n```")
    code = cli.main(["Remove everyone", "--db", db, "--quiet"])
    assert code == cli.REFUSED
    assert "DELETE" in capsys.readouterr().out      # the refused query is shown


def test_a_missing_database_exits_three(tmp_path, stub, capsys):
    stub("```sql\nSELECT 1\n```")
    code = cli.main(["anything", "--db", str(tmp_path / "nope.sqlite"), "--quiet"])
    assert code == cli.DB_ERROR


def test_no_question_exits_one(db, stub, monkeypatch, capsys):
    stub("```sql\nSELECT 1\n```")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert cli.main(["--db", db, "--quiet"]) == cli.USAGE


def test_no_model_exits_one(db, monkeypatch, capsys):
    monkeypatch.setattr(cli, "installed_models", lambda: [])
    assert cli.main(["anything", "--db", db, "--quiet"]) == cli.USAGE


# ----------------------------------------------------------------- shape ---

def test_sql_only_prints_the_query_and_does_not_print_rows(db, stub, capsys):
    stub("```sql\nSELECT region FROM customers\n```")
    code = cli.main(["regions", "--db", db, "--sql-only", "--quiet"])
    out = capsys.readouterr().out
    assert code == cli.OK
    assert out.strip().upper().startswith("SELECT")
    assert "Leeds" not in out


def test_json_output_is_the_whole_of_stdout(db, stub, capsys):
    # A pipeline does `askbase ... --json | jq`. One stray line of progress on
    # stdout and that breaks, which is why progress goes to stderr.
    stub("```sql\nSELECT region, COUNT(*) AS n FROM customers GROUP BY region\n```")
    code = cli.main(["counts", "--db", db, "--json"])
    captured = capsys.readouterr()
    assert code == cli.OK
    payload = json.loads(captured.out)          # raises if anything else got in
    assert payload["ok"] is True
    assert payload["row_count"] == 2
    assert payload["columns"][0] == "region"


def test_a_refusal_in_json_is_still_json(db, stub, capsys):
    stub("```sql\nDROP TABLE customers\n```")
    code = cli.main(["drop it", "--db", db, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == cli.REFUSED
    assert payload["ok"] is False
    assert payload["error"]


def test_the_question_can_come_from_stdin(db, stub, monkeypatch, capsys):
    client = stub("```sql\nSELECT region FROM customers\n```")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdin, "read", lambda: "  regions   please \n")
    code = cli.main(["--db", db, "--sql-only", "--quiet"])
    assert code == cli.OK
    # Whitespace collapsed, so a heredoc does not reach the model as ragged
    # text. Checked against the prompt the model actually received.
    assert "regions please" in client.asked[0]


def test_csv_holds_every_row_not_only_the_shown_ones(db, stub, tmp_path, capsys):
    stub("```sql\nSELECT id, name FROM customers\n```")
    out = tmp_path / "all.csv"
    code = cli.main(["everyone", "--db", db, "--max-rows", "5",
                     "--csv", str(out), "--quiet"])
    assert code == cli.OK
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    # 40 rows plus a header, although only 5 were shown
    assert len(lines) == 41, lines[:3]


# --------------------------------------------------------------- journal ---

def test_an_asked_question_lands_in_the_journal(db, stub):
    from askbase import journal

    stub("```sql\nSELECT region FROM customers\n```")
    cli.main(["how many regions", "--db", db, "--quiet"])
    kept = journal.entries()
    assert len(kept) == 1
    assert kept[0].question == "how many regions"
    assert kept[0].ok is True


def test_no_journal_writes_nothing(db, stub):
    from askbase import journal

    stub("```sql\nSELECT region FROM customers\n```")
    cli.main(["quiet one", "--db", db, "--quiet", "--no-journal"])
    assert journal.entries() == []


# ------------------------------------------------------------------- Qt ----

def test_the_command_runs_without_pyside6_installed():
    """The only thing making a Windows and Linux build possible.

    Run in a subprocess with PySide6 blocked at import, because an import that
    already happened in this process would hide a new one.
    """
    code = (
        "import sys\n"
        "class Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        return self if name.split('.')[0] == 'PySide6' else None\n"
        "    def load_module(self, name):\n"
        "        raise ImportError('PySide6 must not be needed by the CLI')\n"
        "sys.meta_path.insert(0, Block())\n"
        "from askbase import cli\n"
        "cli.build_parser()\n"
        "print('ok')\n"
    )
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=root)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


# ---- the exit-code contract, one test per code ----------------------------
# The site publishes these as a contract a script can branch on. Every engine
# failure used to leave as a 2, so "Ollama is down" and "the query ran too
# long" both said "your question could not be turned into a query".

def test_the_model_being_down_exits_one_not_two(db, stub, monkeypatch, capsys):
    client = stub("unused")

    def dead(prompt):
        raise RuntimeError("Локальная модель не отвечает. Проверьте, что Ollama запущена.")

    monkeypatch.setattr(client, "complete", dead)
    code = cli.main(["anything", "--db", db, "--quiet"])
    assert code == cli.USAGE, "модель не отвечает это не отказ в запросе"


def test_a_query_stopped_by_the_timeout_exits_three_not_two(db, stub, monkeypatch, capsys):
    from askbase import engine

    stub("```sql\nSELECT region FROM customers\n```")

    def too_slow(*a, **k):
        raise engine.AskError("Запрос слишком тяжёлый.", kind="timeout")

    monkeypatch.setattr(engine, "run_query", too_slow)
    code = cli.main(["slow one", "--db", db, "--quiet"])
    assert code == cli.DB_ERROR


def test_a_refusal_by_the_safety_check_exits_two(db, stub, capsys):
    stub("```sql\nUPDATE customers SET region = 'x'\n```")
    assert cli.main(["change them", "--db", db, "--quiet"]) == cli.REFUSED


def test_the_json_failure_names_the_kind(db, stub, capsys):
    stub("```sql\nDROP TABLE customers\n```")
    cli.main(["drop", "--db", db, "--json"])
    assert json.loads(capsys.readouterr().out)["kind"] == "refused"


def test_an_empty_database_exits_three(tmp_path, stub, capsys):
    import sqlite3

    p = tmp_path / "empty.sqlite"
    sqlite3.connect(p).close()
    stub("```sql\nSELECT 1\n```")
    # No tables at all: the engine refuses at connect, and that is a database
    # problem rather than a problem with the question.
    assert cli.main(["anything", "--db", str(p), "--quiet"]) == cli.DB_ERROR


# ---- arguments that used to be accepted and should not be ------------------

@pytest.mark.parametrize("rows", ["0", "-5"])
def test_a_row_bound_below_one_is_refused(db, stub, rows, capsys):
    # 0 reported success with an empty table and a row line reading "больше 0,
    # показаны первые 0". Negative was worse: SQLite reads LIMIT -1 as no
    # limit and fetchmany(-n) returns everything, so the bound was gone.
    stub("```sql\nSELECT id FROM customers\n```")
    assert cli.main(["everyone", "--db", db, "--max-rows", rows, "--quiet"]) == cli.USAGE


def test_a_timeout_of_zero_is_refused(db, stub, capsys):
    stub("```sql\nSELECT id FROM customers\n```")
    assert cli.main(["x", "--db", db, "--timeout", "0", "--quiet"]) == cli.USAGE


def test_sql_only_with_csv_is_refused_rather_than_ignored(db, stub, tmp_path, capsys):
    stub("```sql\nSELECT id FROM customers\n```")
    out = tmp_path / "x.csv"
    assert cli.main(["x", "--db", db, "--sql-only", "--csv", str(out),
                     "--quiet"]) == cli.USAGE
    assert not out.exists()


def test_a_closed_stdin_gives_the_usage_error_not_a_traceback(db, stub, monkeypatch, capsys):
    # How launchd and cron invoke things: sys.stdin is None, and .isatty() on
    # None was an AttributeError traceback.
    stub("```sql\nSELECT id FROM customers\n```")
    monkeypatch.setattr(sys, "stdin", None)
    assert cli.main(["--db", db, "--quiet"]) == cli.USAGE


def test_undecodable_bytes_on_stdin_do_not_crash_after_the_answer(db, stub, monkeypatch, capsys):
    client = stub("```sql\nSELECT id FROM customers\n```")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys, "stdin", type("S", (), {
        "isatty": staticmethod(lambda: False),
        "read": staticmethod(lambda: "x\udcff\udcfe q"),
    })())
    assert cli.main(["--db", db, "--sql-only", "--quiet"]) == cli.OK
