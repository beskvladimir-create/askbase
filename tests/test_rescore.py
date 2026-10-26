"""Re-scoring saved predictions, and the sidecar the site publishes from.

This script exists because of a bug and then carried one of its own: it built
the summary filename with two with_suffix calls, so it looked for
"x.summary.json" where "x.base.summary.json" lives, found nothing, and silently
skipped the update. The corrected figure was printed to the terminal while the
file the build reads kept the old one, which is how 44.6% outlived its own
correction.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")


@pytest.fixture
def run(tmp_path):
    """A two-question BIRD-shaped set, with one right and one wrong prediction."""
    data = tmp_path / "bird"
    (data / "dev_databases" / "shop" / "shop.sqlite").parent.mkdir(parents=True)
    con = sqlite3.connect(data / "dev_databases" / "shop" / "shop.sqlite")
    con.executescript("CREATE TABLE t (a INTEGER);")
    con.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    con.commit()
    con.close()

    results = tmp_path / "results"
    results.mkdir()
    preds = results / "m.base.jsonl"
    preds.write_text("".join(json.dumps(r) + "\n" for r in [
        {"qid": 0, "db_id": "shop", "gold_sql": "SELECT a FROM t",
         "pred_sql": "SELECT a FROM t", "correct": False},
        {"qid": 1, "db_id": "shop", "gold_sql": "SELECT a FROM t",
         "pred_sql": "SELECT 999", "correct": True},
    ]), encoding="utf-8")
    (results / "m.base.summary.json").write_text(
        json.dumps({"model": "m", "n": 2, "ex_accuracy": 0.9}), encoding="utf-8")
    return preds, results / "m.base.summary.json", data


def rescore(preds, data, *extra):
    return subprocess.run(
        [PY, str(ROOT / "scripts" / "rescore.py"), str(preds),
         "--data-root", str(data), *extra],
        capture_output=True, text=True, cwd=ROOT)


def test_the_sidecar_beside_the_predictions_is_the_one_updated(run):
    preds, summary, data = run
    assert rescore(preds, data).returncode == 0
    got = json.loads(summary.read_text())
    assert got["ex_accuracy"] == 0.5, "сводка рядом с предсказаниями не обновлена"
    assert got["ex_accuracy_before_rescore"] == 0.9
    assert got["rescored"] is True
    # and nothing was written under the wrong name
    assert not (summary.parent / "m.summary.json").exists()


def test_the_verdicts_in_the_predictions_are_rewritten(run):
    preds, _, data = run
    rescore(preds, data)
    recs = [json.loads(l) for l in preds.read_text().splitlines()]
    assert [r["correct"] for r in recs] == [True, False]
    # the old verdict is kept, so a score cannot silently replace an earlier one
    assert [r["correct_before"] for r in recs] == [False, True]


def test_a_missing_sidecar_is_an_error_not_a_shrug(run):
    preds, summary, data = run
    summary.unlink()
    r = rescore(preds, data)
    assert r.returncode != 0
    assert "сводк" in (r.stdout + r.stderr)


def test_an_empty_predictions_file_does_not_divide_by_zero(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    preds = results / "m.base.jsonl"
    preds.write_text("", encoding="utf-8")
    (results / "m.base.summary.json").write_text("{}", encoding="utf-8")
    data = tmp_path / "bird"
    (data / "dev_databases").mkdir(parents=True)
    r = rescore(preds, data)
    assert r.returncode != 0
    # and the file it was given is still there: the division used to raise
    # after write_text had already replaced it
    assert preds.exists()
