"""A run that did not happen must not become a figure.

This is not hypothetical. A queue script compared model names only up to the
first colon, so `qwen2.5-coder:14b` matched the installed `qwen2.5-coder:7b`
and the Q8 Arctic matched the installed Q4. Both ran against a tag Ollama does
not have, collected 500 errors in half a second, and wrote 0.0% into results/
beside the real measurements, where the site builder reads from.

The shell bug was one line. The reason it reached results/ is that the harness
wrote a summary whatever came back, and that is the part worth a test.
"""
from __future__ import annotations

import pytest

from nl2sql_app.bench import runner


class Dead:
    """A model endpoint that is not there."""

    model = "no-such-model"
    temperature = 0.0

    def complete(self, prompt, temperature=None):
        raise RuntimeError("NotFoundError: Error code: 404")

    def reset(self):
        pass


class Flaky:
    """Answers most of the time, which is the model's own business."""

    model = "flaky"
    temperature = 0.0
    # Mirrors ModelClient, because the summary records the conditions a run
    # happened under and a stub that lacks them would hide that it stopped.
    timeout_s = 600.0
    max_retries = 2

    def __init__(self, fail_every: int) -> None:
        self.fail_every = fail_every
        self.n = 0

    def complete(self, prompt, temperature=None):
        self.n += 1
        if self.n % self.fail_every == 0:
            raise RuntimeError("NotFoundError: Error code: 404")
        return type("R", (), {"text": "```sql\nSELECT 1\n```",
                              "prompt_tokens": 1, "completion_tokens": 1,
                              "latency_s": 0.0})()

    def reset(self):
        pass


@pytest.fixture
def bird(tmp_path):
    """The smallest thing load_bird_dev will accept."""
    import json
    import sqlite3

    root = tmp_path / "bird"
    dbdir = root / "dev_databases" / "shop"
    dbdir.mkdir(parents=True)
    con = sqlite3.connect(dbdir / "shop.sqlite")
    con.executescript("CREATE TABLE t (a INTEGER);")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()
    (root / "dev.json").write_text(json.dumps([
        {"question_id": i, "db_id": "shop", "question": "how many",
         "SQL": "SELECT a FROM t", "evidence": ""}
        for i in range(8)
    ]), encoding="utf-8")
    return str(root)


def test_a_run_where_nothing_answered_writes_no_result(bird, tmp_path):
    out = tmp_path / "dead.base.jsonl"
    with pytest.raises(RuntimeError) as e:
        runner.run(bird, Dead(), str(out), concurrency=1)
    # and it says why, rather than failing with a number nobody can explain
    assert "404" in str(e.value)
    assert "не состоялся" in str(e.value)
    assert not out.exists()
    assert not out.with_suffix(".summary.json").exists()


def test_a_run_with_a_few_failures_is_still_a_result(bird, tmp_path):
    # Some failures are the model's own doing and belong in the score. The bar
    # only catches losing almost everything, which is infrastructure.
    out = tmp_path / "flaky.base.jsonl"
    summary = runner.run(bird, Flaky(fail_every=4), str(out), concurrency=1)
    assert summary["n"] == 8
    assert out.exists()


def test_the_summary_carries_the_interval_and_the_conditions(bird, tmp_path):
    out = tmp_path / "ok.base.jsonl"
    summary = runner.run(bird, Flaky(fail_every=100), str(out), concurrency=1)
    assert summary["ex_ci"]["resamples"] == 2000
    assert summary["ex_ci"]["seed"] == 0
    assert summary["timed_out"] == 0
    assert summary["request_timeout_s"] is not None
