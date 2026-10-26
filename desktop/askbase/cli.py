"""askbase: ask a database a question from the terminal.

Stage В5а of docs/design.md, and the surface docs/roles.md gives role 2, the
data engineer. Their problem is not SQL, it is somebody else's schema, so what
they want back is usually the query rather than the answer. Hence --sql-only.

Three rules this file follows, all from the plan:

  - It is a wrapper over the engine the application already uses, and it adds
    nothing of its own. The safety check, the read-only connection, the row
    bound and the timeout are the same code paths. A terminal that was allowed
    more than the window would make the window's promises meaningless.
  - It does not import Qt. The engine, the model client and the journal are
    free of it, which is what makes this runnable on Windows and Linux where
    the packaged application does not go.
  - It stays the second surface. No feature lands here that is not in the
    application, because the plan's stated risk is that effort leaks to the
    terminal, which is easier to build and closer to its author's habits.

Exit codes, as roles.md specifies them, because a script has to tell apart
"could not understand" from "the database fell over":

    0   an answer, or a query with --sql-only
    1   wrong usage, or the local model is absent or not answering
    2   the question produced nothing a read-only check would pass
    3   the database refused the query, could not be opened, or the query was
        stopped for running past the timeout

The mapping comes from AskError.kind, not from the mere fact that an AskError
was raised. Every failure inside the engine used to leave here as a 2, so
Ollama dying mid-question and a query killed by the timeout both reported
"your question could not be turned into a query", and a script branching on
the documented contract mis-routed both.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import journal, offline
from .engine import AskError, Engine, export_csv
from .models import ModelClient, installed_models

OK, USAGE, REFUSED, DB_ERROR = 0, 1, 2, 3


def _read_question(args) -> str:
    """The question from the arguments, or from standard input when piped.

    A bare `-` is the conventional way to say "read it from stdin"; so is
    giving no question at all while something is piped in. Both work, because
    a pipeline is the reason this surface exists.
    """
    if args.question and args.question != "-":
        return " ".join(args.question.split())
    # sys.stdin is None when the descriptor is closed, which is how launchd and
    # cron invoke things. `.isatty()` on None was an AttributeError traceback
    # where "no question given" was wanted.
    if sys.stdin is None:
        return ""
    try:
        if args.question == "-" or not sys.stdin.isatty():
            # surrogateescape leaves lone surrogates in the string for bytes
            # that are not valid UTF-8. They reach json.dumps in the journal
            # and raise after the question has already been answered, so they
            # are dropped here instead.
            raw = sys.stdin.read()
            return " ".join(raw.encode("utf-8", "replace").decode("utf-8").split())
    except (OSError, ValueError):
        return ""
    return ""


def _print_table(columns, rows, out) -> None:
    """A plain aligned table. No box drawing: this gets piped more than it gets read."""
    if not columns:
        return
    widths = [len(str(c)) for c in columns]
    cells = [[("" if v is None else str(v)) for v in r] for r in rows]
    for row in cells:
        for i, v in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(v))
    widths = [min(w, 40) for w in widths]

    def line(values):
        return "  ".join(str(v)[:w].ljust(w) for v, w in zip(values, widths))

    print(line(columns), file=out)
    print("  ".join("-" * w for w in widths), file=out)
    for row in cells:
        print(line(row), file=out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="askbase",
        description="Ask a database a question in plain words. The model runs on this machine.",
        epilog="Exit codes: 0 answer, 1 usage, 2 question refused by the read-only check, "
               "3 database error.",
    )
    p.add_argument("question", nargs="?",
                   help="the question; '-' or a pipe reads it from standard input")
    p.add_argument("--db", required=True, metavar="PATH", help="path to an SQLite file")
    p.add_argument("--sql-only", action="store_true",
                   help="print the query and do not execute it")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="machine-readable output on stdout")
    p.add_argument("--csv", metavar="PATH",
                   help="write the whole result to this file, not only the rows shown")
    p.add_argument("--model", metavar="NAME",
                   help="model to use; the first installed one by default")
    p.add_argument("--max-rows", type=int, default=1000, metavar="N",
                   help="rows to return (default 1000)")
    p.add_argument("--timeout", type=float, default=30.0, metavar="SECONDS",
                   help="how long one query may run (default 30)")
    p.add_argument("--list-models", action="store_true",
                   help="print the models installed on this machine and exit")
    p.add_argument("--no-journal", action="store_true",
                   help="do not write this question to the local journal")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="no progress on stderr")
    p.add_argument("--selftest", action="store_true",
                   help="check the network guard holds, and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    # The same guard the window installs, and for the same reason. It was
    # missing here: the shipped `askbase` command had no network restriction of
    # any kind, on the one promise that is hardest for a user to re-check, and
    # this file's own pyproject note says the two surfaces exist so the safety
    # layers cannot drift apart. They had drifted.
    offline.enable()
    args = build_parser().parse_args(argv)
    # Progress goes to stderr, never stdout: stdout is the answer, and a
    # pipeline must be able to take it whole.
    err = sys.stderr

    if args.selftest:
        return offline.selftest()

    if args.list_models:
        names = installed_models()
        for n in names:
            print(n)
        return OK if names else USAGE

    question = _read_question(args)
    if not question and not args.list_models:
        print("askbase: no question given. Pass it as an argument or pipe it in.", file=err)
        return USAGE

    if args.max_rows < 1:
        print("askbase: --max-rows must be at least 1. 0 returns nothing and a "
              "negative value removes the row bound altogether, because SQLite "
              "reads LIMIT -1 as no limit.", file=err)
        return USAGE
    if args.timeout <= 0:
        print("askbase: --timeout must be greater than 0.", file=err)
        return USAGE

    db = str(Path(args.db).expanduser())
    if not Path(db).is_file():
        print(f"askbase: no such file: {db}", file=err)
        return DB_ERROR

    models = installed_models()
    model = args.model or (models[0] if models else "")
    if not model:
        print("askbase: no local model found. Install one, for example:\n"
              "  ollama pull hf.co/mradermacher/XiYanSQL-QwenCoder-7B-2504-GGUF:Q4_K_M",
              file=err)
        return USAGE

    client = ModelClient(model)
    try:
        engine = Engine(db, client, max_rows=args.max_rows, timeout=args.timeout, lang="en")
    except AskError as e:
        print(f"askbase: {e}", file=err)
        return DB_ERROR
    except sqlite3.Error as e:
        print(f"askbase: {db}: {e}", file=err)
        return DB_ERROR

    def step(name: str) -> None:
        if not args.quiet:
            print(f"  {name}...", file=err, flush=True)

    try:
        answer = engine.ask(question, on_step=step)
    except AskError as e:
        # The query, when there is one, goes to stdout even on a refusal: for
        # this user the query is often the deliverable, and a refusal they
        # cannot see the query behind is not useful feedback.
        sql = getattr(e, "sql", "")
        code = {"model": USAGE, "timeout": DB_ERROR, "db": DB_ERROR}.get(
            getattr(e, "kind", "refused"), REFUSED)
        if args.as_json:
            json.dump({"ok": False, "error": str(e), "kind": getattr(e, "kind", "refused"),
                       "sql": sql, "question": question},
                      sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print(f"askbase: {e}", file=err)
            if sql:
                print(sql)
        if not args.no_journal:
            _journal(question, sql, 0, 0.0, db, ok=False, error=str(e))
        return code
    except sqlite3.Error as e:
        print(f"askbase: {e}", file=err)
        return DB_ERROR

    if not args.no_journal:
        _journal(question, answer.sql, len(answer.rows), answer.seconds, db,
                 truncated=answer.truncated)

    if args.sql_only and args.csv:
        print("askbase: --sql-only and --csv ask for different things; "
              "--sql-only does not produce rows to write.", file=err)
        return USAGE

    if args.sql_only:
        # Deliberately after the question has been asked and checked: the
        # point is a query that passed the same check the application applies,
        # not a draft nobody has validated.
        print(answer.sql)
        return OK

    written = None
    if args.csv:
        try:
            written = export_csv(db, answer.export_sql or answer.sql, args.csv,
                                 timeout=max(120.0, args.timeout * 4))
        except (OSError, sqlite3.Error) as e:
            print(f"askbase: could not write {args.csv}: {e}", file=err)
            return DB_ERROR

    if args.as_json:
        json.dump({
            "ok": True,
            "question": question,
            "sql": answer.sql,
            "columns": answer.columns,
            "rows": [list(r) for r in answer.rows],
            "row_count": len(answer.rows),
            "truncated": answer.truncated,
            "explanation": answer.explanation,
            "notes": answer.notes,
            "seconds": round(answer.seconds, 2),
            "csv": args.csv if written is not None else None,
            "csv_rows": written,
            "model": model,
        }, sys.stdout, ensure_ascii=False, indent=2, default=str)
        print()
        return OK

    _print_table(answer.columns, answer.rows, sys.stdout)
    if not args.quiet:
        print(file=err)
        print(answer.sql, file=err)
        if answer.explanation:
            print(f"\n{answer.explanation}", file=err)
        for note in answer.notes:
            print(f"note: {note}", file=err)
        if written is not None:
            print(f"wrote {written} rows to {args.csv}", file=err)
    return OK


def _journal(question: str, sql: str, rows: int, seconds: float, db: str, *,
             truncated: bool = False, ok: bool = True, error: str = "") -> None:
    journal.append(journal.Entry(
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        question=question, sql=sql, rows=rows, seconds=round(seconds, 2),
        db_path=db, truncated=truncated, ok=ok, error=error.partition("\n")[0][:300],
    ))


if __name__ == "__main__":
    sys.exit(main())
