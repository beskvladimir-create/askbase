"""The held-out stage: loading the frozen set and running it under the fixed rules.

The rules were published before the run (HOLDOUT.md), so what these tests
check is not that numbers come out. It is that the code computes the statistic
that was promised and refuses the shortcuts that would quietly change the
experiment: a set that moved, a subset chosen after the fact, three requests in
flight while p95 is being measured, a run that skipped the journal, and an
interval taken over wordings instead of tasks.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nl2sql_app.bench import data, runner, stats
from nl2sql_app.holdout import verify

ROOT = Path(__file__).resolve().parent.parent

# The set comes from the `frozen_holdout` fixture in conftest, which
# regenerates it from the recorded seed and date. Deliberately not read from
# `data/holdout`: that directory is not in the public export, so a disk-backed
# test passes on this machine and skips on GitHub, which is the kind of check
# that stops being true without anyone noticing.


# ---- loading ----------------------------------------------------------------

@pytest.mark.parametrize("lang", ["en", "ru"])
def test_one_example_per_wording_and_the_task_is_on_the_record(lang, frozen_holdout):
    ex = data.load_holdout(str(frozen_holdout), lang)
    by_task: dict[str, list[int]] = {}
    for e in ex:
        by_task.setdefault(e.task, []).append(e.wording)
    assert len(by_task) == 48, "задач не 48"
    assert len(ex) == 96, "формулировок на язык не 96"
    # Two per task per language, and the other language's wordings are absent
    # rather than silently mixed in: the two columns on the ranking page are
    # only comparable because they cover the same tasks.
    assert all(sorted(v) == [0, 1] for v in by_task.values())
    assert {e.lang for e in ex} == {lang}


def test_the_two_languages_cover_exactly_the_same_tasks(frozen_holdout):
    en = {e.task for e in data.load_holdout(str(frozen_holdout), "en")}
    ru = {e.task for e in data.load_holdout(str(frozen_holdout), "ru")}
    assert en == ru, "наборы задач по языкам разошлись, разность некорректна"


def test_the_gold_query_is_the_same_for_every_wording_of_a_task(frozen_holdout):
    gold: dict[str, set[str]] = {}
    for lang in ("en", "ru"):
        for e in data.load_holdout(str(frozen_holdout), lang):
            gold.setdefault(e.task, set()).add(e.gold_sql)
    bad = {t: g for t, g in gold.items() if len(g) > 1}
    assert not bad, f"у задачи больше одного эталона: {sorted(bad)[:3]}"


def test_the_trap_travels_with_the_example(frozen_holdout):
    # The mandatory manual review of failures reads these records, and "which
    # trick was this question for" is the first thing it needs.
    ex = data.load_holdout(str(frozen_holdout), "en")
    assert any(e.traps for e in ex)
    assert all(isinstance(e.traps, tuple) for e in ex)


def test_a_set_that_moved_is_refused_before_any_request(tmp_path, frozen_holdout):
    # Not a warning. A run on a set that is not the frozen one is a different
    # experiment wearing the same name.
    for d in sorted(verify.expected()["domains"]):
        (tmp_path / d).mkdir()
        src = frozen_holdout / d
        (tmp_path / d / "canonical.json").write_bytes(
            (src / "canonical.json").read_bytes())
        (tmp_path / d / "tasks.json").write_bytes((src / "tasks.json").read_bytes())
        (tmp_path / d / f"{d}.sqlite").write_bytes((src / f"{d}.sqlite").read_bytes())
    assert data.load_holdout(str(tmp_path), "en")          # the copy is fine

    victim = tmp_path / "hr" / "canonical.json"
    victim.write_text(victim.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(verify.NotFrozen) as e:
        data.load_holdout(str(tmp_path), "en")
    assert "hr" in str(e.value)


def test_a_task_missing_a_language_is_refused_rather_than_dropped(tmp_path, monkeypatch, frozen_holdout):
    # Dropping it would leave the English column measured on 48 tasks and the
    # Russian on 47, and the gap between them would include the difference
    # between two sets of questions.
    (tmp_path / "medicine").mkdir()
    tasks = json.loads((frozen_holdout / "medicine" / "tasks.json").read_text(encoding="utf-8"))
    tasks[0]["wordings"] = [w for w in tasks[0]["wordings"] if w["lang"] != "ru"]
    (tmp_path / "medicine" / "tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "medicine" / "medicine.sqlite").write_bytes(
        (frozen_holdout / "medicine" / "medicine.sqlite").read_bytes())
    monkeypatch.setattr(verify, "check_set", lambda _p: {})
    monkeypatch.setattr(verify, "expected", lambda: {"domains": {"medicine": "x"}})
    with pytest.raises(ValueError, match="нет формулировок"):
        data.load_holdout(str(tmp_path), "ru")


# ---- the statistic that was promised ----------------------------------------

def test_the_interval_is_over_tasks_not_wordings():
    # HOLDOUT.md: "the resampling unit is the task, not the wording ... n = 48,
    # not 96". The two wordings of a task tend to be right or wrong together,
    # so resampling them separately narrows the interval in the direction that
    # flatters us. Same data, both ways, and the clustered one has to be wider.
    groups = [[1.0, 1.0]] * 24 + [[0.0, 0.0]] * 24
    clustered = stats.bootstrap_mean_clustered(groups)
    naive = stats.bootstrap_mean([v for g in groups for v in g])
    assert clustered.n == 48 and naive.n == 96
    assert clustered.point == naive.point == 0.5
    assert (clustered.high - clustered.low) > (naive.high - naive.low) * 1.2


def test_the_clustered_interval_is_reproducible_and_honours_its_seed():
    groups = [[1.0, 0.0]] * 20 + [[1.0, 1.0]] * 28
    a = stats.bootstrap_mean_clustered(groups)
    assert a.as_dict() == stats.bootstrap_mean_clustered(groups).as_dict()
    assert stats.bootstrap_mean_clustered(groups, seed=5).as_dict() != a.as_dict()


def test_an_empty_cluster_list_is_an_error_not_a_zero():
    with pytest.raises(ValueError):
        stats.bootstrap_mean_clustered([])
    with pytest.raises(ValueError):
        stats.bootstrap_mean_clustered([[], []])


def test_the_language_gap_resamples_the_task_once_for_both_languages():
    en = [[1.0, 1.0]] * 40 + [[0.0, 0.0]] * 8
    ru = [[1.0, 0.0]] * 40 + [[0.0, 0.0]] * 8
    d = stats.paired_difference_clustered(en, ru)
    assert d.n == 48
    assert d.point == pytest.approx(40 / 48 - 20 / 48)
    with pytest.raises(ValueError, match="не спарены"):
        stats.paired_difference_clustered(en, ru[:10])


def test_wording_pairs_agree_only_when_both_verdicts_match():
    share, n = stats.wording_agreement([
        ("t1", True), ("t1", True),       # agree
        ("t2", True), ("t2", False),      # disagree
        ("t3", False), ("t3", False),     # agree
    ])
    assert (round(share, 4), n) == (round(2 / 3, 4), 3)
    # Three wordings of one task make three pairs, not one.
    assert stats.wording_agreement([("t", True), ("t", True), ("t", False)]) == (
        pytest.approx(1 / 3), 3)
    assert stats.wording_agreement([("t", True)]) == (0.0, 0)


# ---- the refusals -----------------------------------------------------------

def test_a_bare_run_never_touches_the_held_out_set():
    """The most expensive mistake available here, so it is the one pinned hardest.

    Set 1 is run once and reading its failures turns it into development data.
    A command typed out of habit must not spend it, so the holdout stages are
    not in the default sweep and have to be named.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_bench

    default = [name for name, _ in run_bench.pick_stages(None)]
    assert default, "ablation пуста"
    assert not any("holdout" in name for name in default)
    assert all(f.get("dataset") in (None, "bird") for _, f in run_bench.pick_stages(None))

    named = run_bench.pick_stages(["holdout-en", "holdout-ru"])
    assert [n for n, _ in named] == ["holdout-en", "holdout-ru"]
    assert [f["lang"] for _, f in named] == ["en", "ru"]
    with pytest.raises(SystemExit, match="неизвестные стадии"):
        run_bench.pick_stages(["holdout-de"])


def test_the_stage_names_are_the_ones_the_site_asks_for():
    # The ranking page references {=<model>|holdout-en|ex_accuracy}, and the
    # build refuses a figure with no results file behind it. A stage renamed
    # here would leave the table permanently empty with no error anywhere.
    page = (ROOT / "site" / "pages" / "model-ranking.html").read_text(encoding="utf-8")
    assert "|holdout-en|" in page and "|holdout-ru|" in page


def test_a_run_that_skipped_the_journal_is_refused(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_bench

    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    with pytest.raises(SystemExit, match="не записан в журнал"):
        run_bench.require_recorded_run("some-model")

    verify.record("some-model", verify.expected()["set"])
    run_bench.require_recorded_run("some-model")          # now it may proceed


@pytest.mark.parametrize("kwargs, message", [
    ({"lang": None, "concurrency": 1}, "нужен --lang"),
    ({"lang": "en", "concurrency": 3}, "по одному запросу"),
    ({"lang": "en", "concurrency": 1, "sample": 20}, "целиком"),
    ({"lang": "en", "concurrency": 1, "limit": 20}, "целиком"),
])
def test_the_shortcuts_that_would_change_the_experiment_are_refused(kwargs, message, frozen_holdout):
    # No client and no output path: each of these has to be refused before the
    # run reaches either, so a bare object() and a path that cannot be written
    # are enough to prove it.
    with pytest.raises(ValueError, match=message):
        runner.run(str(frozen_holdout), object(), "/dev/null/never",
                   dataset="holdout", **kwargs)


def test_an_unknown_dataset_is_an_error(frozen_holdout):
    with pytest.raises(ValueError, match="неизвестный набор"):
        runner.run(str(frozen_holdout), object(), "/dev/null/never", dataset="spider")


# ---- end to end, with a stub model -----------------------------------------

class StubClient:
    """Answers the gold query for every task, and spoils one wording in two.

    Enough to make the summary's numbers non-trivial: accuracy 75%, agreement
    50%. A stub that always answers correctly would let a broken agreement
    calculation return 1.0 and look right.
    """

    model = "stub"
    temperature = 0.0
    timeout_s = 1.0
    max_retries = 0

    def __init__(self, examples):
        self.answers = {}
        tasks = sorted({e.task for e in examples})
        for e in examples:
            spoil = tasks.index(e.task) % 2 == 1 and e.wording == 1
            self.answers[e.question] = ("SELECT -12345 AS x" if spoil else e.gold_sql)

    def complete(self, prompt, temperature=None):
        from nl2sql_app.bench.model_client import Completion

        question = prompt.rsplit("Question: ", 1)[1].strip()
        return Completion(f"```sql\n{self.answers[question]}\n```", 10, 5, 0.01)


def test_the_stage_runs_and_the_summary_says_what_it_measured(tmp_path, frozen_holdout):
    examples = data.load_holdout(str(frozen_holdout), "ru")
    out = tmp_path / "stub.holdout-ru.jsonl"
    summary = runner.run(str(frozen_holdout), StubClient(examples), str(out),
                         dataset="holdout", lang="ru", concurrency=1)

    assert summary["dataset"] == "holdout" and summary["lang"] == "ru"
    assert summary["tasks"] == 48 and summary["wordings"] == 96
    assert summary["ex_accuracy"] == pytest.approx(0.75)
    # n is the task count, not the wording count: the whole point of the rule.
    assert summary["ex_ci"]["n"] == 48
    assert summary["ex_ci"]["low"] < 0.75 < summary["ex_ci"]["high"]
    assert summary["wording_pairs"] == 48
    assert summary["wording_agreement"] == pytest.approx(0.5)
    assert summary["p95_s"] is not None and summary["p95_s"] >= 0

    records = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 96
    assert all(r["lang"] == "ru" and r["task"] and r["wording"] in (0, 1)
               for r in records)
    assert all("seconds" in r for r in records)
    # Published with every run, failures included.
    assert any(not r["correct"] for r in records)
    assert all(r["pred_sql"] for r in records)


def test_the_bird_record_keeps_the_shape_it_had():
    # Old results files are read by the same code, and a holdout-only field
    # appearing on a BIRD record would make the two indistinguishable.
    ex = data.Example(qid=1, db_id="db", question="q", evidence="", gold_sql="SELECT 1",
                      db_path="/x.sqlite")
    assert runner._identity(ex) == {"qid": 1, "db_id": "db"}


def test_the_verifier_still_refuses_from_the_command_line(frozen_holdout):
    # The stage checks the digests itself, which could tempt someone to drop
    # step 1. The step is also what writes the journal, so it stays, and it
    # stays working.
    r = subprocess.run(
        [sys.executable, "-m", "nl2sql_app.holdout.verify", "--data", str(frozen_holdout)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "совпало доменов: 6 из 6" in r.stdout
