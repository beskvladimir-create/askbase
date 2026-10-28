"""Run a recipe config over BIRD dev and write per-example results + a summary.

Examples are processed concurrently: each example is independent, so a thread
pool fans them out and the vLLM server batches the in-flight requests. Within an
example the recipe stays sequential (generate -> correct -> vote). Records are
written in the original dataset order regardless of completion order.
"""
from __future__ import annotations

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from func_timeout import FunctionTimedOut
from tqdm import tqdm

from .data import Example, load_bird_dev, load_holdout
from .evaluator import execution_accuracy
from .model_client import ModelClient
from .pipeline import Recipe
from .schema import table_recall
from .stats import (
    _percentile,
    bootstrap_mean,
    bootstrap_mean_clustered,
    wording_agreement,
)


def _identity(ex: Example) -> dict:
    """What a record says about which question it was, before any answer.

    The held-out fields are written only when the set has them, so a BIRD
    record keeps the shape it has always had and old results files stay
    readable by the same code.
    """
    out = {"qid": ex.qid, "db_id": ex.db_id}
    if ex.task is not None:
        out["task"] = ex.task
        out["lang"] = ex.lang
        out["wording"] = ex.wording
        # The trap travels with the record because the mandatory manual review
        # of failures reads these files, and "which trick was this question
        # for" is the first thing that review needs.
        out["traps"] = list(ex.traps)
    return out


def _process(
    ex: Example,
    client: ModelClient,
    flags: dict,
    exec_timeout: float,
) -> dict:
    recipe = Recipe(client=client, exec_timeout=exec_timeout, **flags)
    # Per example, not per stage. The stage total divided by the count is an
    # average that hides the tail, and П5 is a threshold on p95 latency, which
    # cannot be recovered from a mean after the fact.
    t0 = time.perf_counter()
    try:
        pred = recipe.run(ex.db_path, ex.question, ex.evidence)
        ok, err = execution_accuracy(ex.db_path, pred, ex.gold_sql, exec_timeout)
    except (Exception, FunctionTimedOut) as e:  # one wedged example must not kill the stage
        return {
            **_identity(ex), "correct": False,
            "error": f"runtime: {type(e).__name__}: {e}",
            "pred_sql": "", "gold_sql": ex.gold_sql,
            "usage": asdict(recipe.usage),
            "table_recall": None,
            "seconds": round(time.perf_counter() - t0, 3),
        }
    seconds = round(time.perf_counter() - t0, 3)
    rec = (table_recall(recipe.linked_tables, ex.gold_sql)
           if recipe.linked_tables is not None else None)
    return {
        **_identity(ex), "correct": ok, "error": err,
        "pred_sql": pred, "gold_sql": ex.gold_sql,
        "usage": asdict(recipe.usage),
        "table_recall": rec,
        "seconds": seconds,
    }


def run(
    data_root: str,
    client: ModelClient,
    out_path: str,
    *,
    dataset: str = "bird",
    lang: str | None = None,
    schema_link: bool = False,
    schema_link_emb: bool = False,
    emb_top_k: int = 5,
    self_correct: bool = False,
    self_consistency: bool = False,
    limit: int | None = None,
    sample: int | None = None,
    sample_seed: int = 0,
    exec_timeout: float = 30.0,
    concurrency: int = 32,
) -> dict:
    if dataset == "bird":
        examples: list[Example] = load_bird_dev(data_root)
    elif dataset == "holdout":
        # Argument checks first, before the set is touched: a refusal should
        # cost nothing and should not depend on the data being there.
        if lang is None:
            raise ValueError("для отложенного набора нужен --lang: en или ru")
        if concurrency > 1:
            # HOLDOUT.md, run plan item 4: "Temperature 0, one request at a
            # time". П5 is a threshold on p95 latency and this is the set that
            # calibrates it; three requests in flight on one machine measures
            # the queue rather than the model, and the number would be
            # published as if it were latency.
            raise ValueError(
                f"отложенный набор идёт по одному запросу: concurrency={concurrency}. "
                "Иначе p95 меряет очередь, а не модель."
            )
        if sample or limit:
            # A held-out set that is run on a subset is a set that was chosen
            # after the fact. It is 48 tasks; it is run whole.
            raise ValueError("отложенный набор прогоняется целиком, без --sample и --limit")
        # Refuses a set whose SHA-256 moved, before a single request is sent.
        examples = load_holdout(data_root, lang)
    else:
        raise ValueError(f"неизвестный набор: {dataset!r}")
    if limit:
        # First N in file order. dev.json is grouped by db_id, so a small limit
        # collapses onto one or two databases: fine for a smoke test, useless as
        # a measurement. Use `sample` for screening.
        examples = examples[:limit]
    if sample and sample < len(examples):
        # Deterministic screening subset: the same questions for every model and
        # every arm, so comparisons stay matched. Re-sorted into dataset order so
        # per-example records line up across runs.
        rng = random.Random(sample_seed)
        examples = sorted(rng.sample(examples, sample), key=lambda e: e.qid)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    flags = {
        "schema_link": schema_link,
        "schema_link_emb": schema_link_emb,
        "emb_top_k": emb_top_k,
        "self_correct": self_correct,
        "self_consistency": self_consistency,
    }

    records: list[dict | None] = [None] * len(examples)
    workers = max(1, min(concurrency, len(examples)))
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(_process, ex, client, flags, exec_timeout): i
            for i, ex in enumerate(examples)
        }
        for fut in tqdm(as_completed(futs), total=len(futs), desc=os.path.basename(out_path)):
            i = futs[fut]
            records[i] = fut.result()
    wall_s = time.perf_counter() - t0

    # A run in which nothing answered is not a result of 0%, it is a run that
    # did not happen, and writing it as a figure is how a broken shell script
    # becomes a published number. This cost two bogus 0.0% entries in results/:
    # a queue script matched the model name only up to the colon, ran against a
    # tag Ollama does not have, got 500 404s in half a second and wrote them
    # out as a measurement next to the real ones.
    #
    # The bar is deliberately low. Some failures are the model's own doing and
    # belong in the score; losing almost everything is infrastructure.
    asked = len(examples)
    failed = sum(1 for r in records if r and r.get("error"))
    if asked and failed / asked > 0.5:
        reasons = {(r.get("error") or "")[:80] for r in records if r and r.get("error")}
        raise RuntimeError(
            f"прогон не состоялся: {failed} из {asked} запросов не выполнились, "
            f"результат не записан. Причины: {sorted(reasons)[:3]}"
        )

    n_correct = sum(int(r["correct"]) for r in records if r)
    with open(out_path, "w") as fout:
        for r in records:
            fout.write(json.dumps(r) + "\n")

    n = len(examples)
    recalls = [r["table_recall"] for r in records if r and r.get("table_recall") is not None]
    # The interval goes in beside the figure, for every run, because the
    # ranking page promises it in print and because a point estimate on its own
    # invites a comparison the sample size does not support. Over questions,
    # 2000 resamples, seed 0, which is the published protocol.
    per_question = [1.0 if (r and r["correct"]) else 0.0 for r in records]
    clustered = dataset == "holdout"
    try:
        if clustered:
            # Over tasks, not over wordings. The rule is pre-registered in
            # HOLDOUT.md and the difference is not cosmetic: the same data
            # gives about ±13.5 points by task and ±10 by wording, and the
            # narrower one would be the published figure.
            by_task: dict[str, list[float]] = {}
            for r, score in zip(records, per_question, strict=True):
                by_task.setdefault((r or {}).get("task", "?"), []).append(score)
            ci = bootstrap_mean_clustered(list(by_task.values())).as_dict()
        else:
            ci = bootstrap_mean(per_question).as_dict()
    except ValueError:
        ci = None               # no questions at all; ex_accuracy is 0.0 below

    summary = {
        "model": client.model,
        "n": n,
        "ex_accuracy": round(n_correct / n, 4) if n else 0.0,
        "ex_ci": ci,
        "config": {
            "schema_link": schema_link,
            "schema_link_emb": schema_link_emb,
            "emb_top_k": emb_top_k,
            "self_correct": self_correct,
            "self_consistency": self_consistency,
        },
        "sample": sample,
        "sample_seed": sample_seed if sample else None,
        "wall_s": round(wall_s, 2),
        "queries_per_s": round(n / wall_s, 3) if wall_s else None,
        "s_per_query": round(wall_s / n, 2) if n else None,
        "mean_table_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "concurrency": workers,
        # Only meaningful at concurrency 1, which is why the two sit together.
        # Reading a p95 taken with requests in flight as a latency figure is
        # the mistake this pairing is here to make obvious.
        "p95_s": round(_percentile(sorted(r["seconds"] for r in records
                                          if r and r.get("seconds") is not None), 0.95), 2)
        if any(r and r.get("seconds") is not None for r in records) else None,
        # Recorded so a run can be read back against the conditions it ran under.
        # A timeout that drops answers is indistinguishable from a model that
        # gets them wrong, unless the number is written down next to the score.
        "request_timeout_s": getattr(client, "timeout_s", None),
        "max_retries": getattr(client, "max_retries", None),
        "timed_out": sum(1 for r in records
                         if r and "APITimeoutError" in (r.get("error") or "")),
        "results_file": out_path,
    }
    if clustered:
        agreement, pair_count = wording_agreement(
            ((r or {}).get("task", "?"), bool(r and r["correct"])) for r in records
        )
        summary.update({
            "dataset": "holdout",
            "lang": lang,
            "tasks": len({(r or {}).get("task") for r in records}),
            "wordings": n,
            # П6, fixed before the run: not below 80% of wording pairs give the
            # same verdict. Published whether or not it is flattering, and the
            # pair count goes with it so a share out of two pairs cannot be
            # mistaken for a share out of forty-eight.
            "wording_agreement": round(agreement, 4),
            "wording_pairs": pair_count,
        })
    with open(out_path.replace(".jsonl", ".summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary
