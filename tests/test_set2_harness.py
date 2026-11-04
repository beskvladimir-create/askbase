"""The harness that reads set 2, and the three ways it could read the wrong set.

Set 2 is frozen and will be run once. The code that runs it was written for
set 1 and carried three assumptions that were true only while one frozen set
existed: the data root in the config, the set number in the registry, and the
journal entry the runner demands before it sends a request. Each of them is a
way to spend the deciding set on a run nobody can trust, so each has a test.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from nl2sql_app.bench.data import load_holdout
from nl2sql_app.holdout.verify import NotFrozen

ROOT = Path(__file__).resolve().parent.parent


def _run_bench():
    spec = importlib.util.spec_from_file_location(
        "run_bench_mod", ROOT / "scripts" / "run_bench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_set_two_config_points_at_set_two():
    cfg = yaml.safe_load((ROOT / "configs" / "holdout2.yaml").read_text(encoding="utf-8"))
    assert cfg["data_root"] == "data/holdout2"
    assert cfg["holdout_set"] == 2
    # П5 is a threshold on p95 latency: requests in flight would measure the
    # queue, which is why the runner refuses a concurrency above 1 as well.
    assert cfg["concurrency"] == 1
    one = yaml.safe_load((ROOT / "configs" / "holdout.yaml").read_text(encoding="utf-8"))
    assert set(cfg["models"]) == set(one["models"]), \
        "участники должны быть те же, иначе наборы не поставить рядом"


def test_the_set_two_stages_are_three_arms_and_not_in_the_default_sweep():
    mod = _run_bench()
    names = [n for n in mod.BY_NAME if n.startswith("set2-")]
    assert sorted(names) == [
        "set2-app-en", "set2-app-ord-en", "set2-app-ord-ru", "set2-app-ru",
        "set2-base-en", "set2-base-ru",
    ]
    # A run with no --stages must never touch a held-out set.
    assert not any(n.startswith("set2-") for n, _ in mod.ABLATION)
    assert all(f["dataset"] == "holdout" for n, f in mod.BY_NAME.items()
               if n.startswith("set2-"))


def test_the_three_arms_differ_only_in_what_they_were_named_for():
    mod = _run_bench()
    base = mod.BY_NAME["set2-base-en"]
    app = mod.BY_NAME["set2-app-en"]
    ord_ = mod.BY_NAME["set2-app-ord-en"]
    assert not base.get("schema_ddl") and not base.get("schema_notes")
    assert app["schema_ddl"] and app["schema_notes"] and app["schema_samples"] == 3
    assert app.get("schema_order") is None
    assert ord_["schema_order"] == "create"
    # The candidate is the shipped prompt plus one change, and nothing else.
    assert {k: v for k, v in ord_.items() if k != "schema_order"} == app


def test_set_two_data_is_refused_when_the_set_number_says_one(frozen_holdout_2):
    """The failure this is here to prevent is silent.

    `load_holdout` took no set number: it checked set 1's digests whatever
    directory it was given. A set-2 run configured with `holdout_set: 1` would
    have been refused by the digest check, which is the behaviour wanted, and
    this pins it so the parameter cannot quietly default its way back.
    """
    assert len(load_holdout(str(frozen_holdout_2), "en", 2)) == 576
    with pytest.raises(NotFrozen):
        load_holdout(str(frozen_holdout_2), "en", 1)


def test_both_languages_cover_the_same_tasks(frozen_holdout_2):
    en = {e.task for e in load_holdout(str(frozen_holdout_2), "en", 2)}
    ru = {e.task for e in load_holdout(str(frozen_holdout_2), "ru", 2)}
    assert en == ru and len(en) == 288


def test_a_set_two_run_is_refused_without_its_own_journal_entry(tmp_path, monkeypatch):
    """A set-1 entry must not wave a set-2 run through.

    `require_recorded_run` read the set number from the registry, where it is
    always 1, so the journal lookup asked whether the tool had been run on set
    1. Every participant has been, which means the check it exists to perform
    would have passed for every set-2 run.
    """
    mod = _run_bench()
    from nl2sql_app.holdout import verify

    journal = tmp_path / "holdout_runs.jsonl"
    journal.write_text(json.dumps({
        "tool": "qwen25-coder-14b", "set": 1, "at": "2026-10-27T00:00:00",
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(verify, "JOURNAL", journal)

    with pytest.raises(SystemExit) as e:
        mod.require_recorded_run("qwen25-coder-14b", 2, "data/holdout2")
    assert "--set 2" in str(e.value)
    # And the set-1 entry still counts for set 1.
    mod.require_recorded_run("qwen25-coder-14b", 1, "data/holdout")


def test_the_queue_names_the_arms_in_the_order_the_document_fixes():
    text = (ROOT / "scripts" / "holdout2_queue.sh").read_text(encoding="utf-8")
    order = [line.split(":")[0] for line in text.splitlines()
             if ":set2-" in line]
    assert order[:3] == ["qwen25-coder-14b"] * 3, \
        "первым идёт наш движок, потом кандидат, потом те же веса без промпта"
    assert len(order) == 8, "шесть участников, три плеча у нашего"
    assert "SET=2" in text and '--set "$SET"' in text
    assert "configs/holdout2.yaml" in text
    # The loop may not be fed by a pipeline. `printf ... | while read` runs the
    # body in a subshell, so the `exit 1` on a failed run leaves the subshell
    # and the queue walks on to the next model, which is the one thing a queue
    # over a set that is spent once must not do. Caught by trying it.
    code = "\n".join(x for x in text.splitlines() if not x.lstrip().startswith("#"))
    assert "| while" not in code, "цикл не должен читать из конвейера"
    assert 'done < "$plan_file"' in code
    assert "data/holdout2" in text
