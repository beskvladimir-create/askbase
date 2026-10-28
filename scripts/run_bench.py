#!/usr/bin/env python3
"""CLI: run one model through the full ablation (base -> +link -> +correct -> +consistency).

Example:
    python scripts/run_bench.py --config configs/run.yaml --model qwen25-coder-32b
    python scripts/run_bench.py --config configs/run.yaml --model qwen25-coder-32b --limit 50

The held-out set is a separate pair of stages and has to be named:

    python -m nl2sql_app.holdout.verify --data data/holdout --record xiyan-7b-q4
    python scripts/run_bench.py --config configs/holdout.yaml --model xiyan-7b-q4 \
        --stages holdout-en holdout-ru

Both steps, in that order. See HOLDOUT.md.
"""
from __future__ import annotations

import argparse
import json
import os

import yaml

from nl2sql_app.bench.model_client import ModelClient
from nl2sql_app.bench.runner import run

ABLATION = [
    ("base", {"schema_link": False, "self_correct": False, "self_consistency": False}),
    ("correct", {"schema_link": False, "self_correct": True, "self_consistency": False}),
    ("consistency", {"schema_link": False, "self_correct": True, "self_consistency": True}),
    ("link", {"schema_link": True, "self_correct": False, "self_consistency": False}),
    ("link_correct", {"schema_link": True, "self_correct": True, "self_consistency": False}),
    ("link_correct_consistency", {"schema_link": True, "self_correct": True, "self_consistency": True}),
    # retrieval-based (embedding) schema linker, for the lexical-vs-embedding comparison
    ("link_emb", {"schema_link_emb": True, "self_correct": False, "self_consistency": False}),
    ("link_emb_correct", {"schema_link_emb": True, "self_correct": True, "self_consistency": False}),
]

# The held-out stages are deliberately NOT in ABLATION. A run with no --stages
# sweeps everything in that list, and set 1 is run once: reading its failures
# afterwards is the point of it, and that reading turns it into development
# data (HOLDOUT.md, "After the run"). A set that gets spent by a command
# someone typed out of habit is not a held-out set. It has to be asked for by
# name, which is also why the names match the figures the site expects.
HOLDOUT_STAGES = [
    ("holdout-en", {"dataset": "holdout", "lang": "en",
                    "schema_link": False, "self_correct": False, "self_consistency": False}),
    ("holdout-ru", {"dataset": "holdout", "lang": "ru",
                    "schema_link": False, "self_correct": False, "self_consistency": False}),
]
BY_NAME = dict(ABLATION + HOLDOUT_STAGES)


def pick_stages(names: list[str] | None) -> list[tuple[str, dict]]:
    """Resolve --stages. Without it, the ablation only, never the held-out set."""
    if names is None:
        return list(ABLATION)
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        raise SystemExit(
            f"неизвестные стадии: {', '.join(unknown)}. "
            f"Известны: {', '.join(BY_NAME)}"
        )
    return [(n, BY_NAME[n]) for n in names]


def require_recorded_run(model: str) -> None:
    """Refuse a held-out run that was never written into the journal.

    Step 1 of the run plan is `verify --record <tool>`, which is what makes a
    second run of the same tool visible and a repeat need a reason. A first
    step that the second step does not check is advice, not a protocol, so the
    check lives here.
    """
    from nl2sql_app.holdout.verify import expected, previous_runs

    set_no = expected()["set"]
    if not previous_runs(model, set_no):
        raise SystemExit(
            f"ОТКАЗ: прогон {model} по набору {set_no} не записан в журнал.\n"
            f"Сначала шаг 1 плана прогона:\n"
            f"  python -m nl2sql_app.holdout.verify --data data/holdout --record {model}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True, help="key in config 'models'")
    ap.add_argument("--limit", type=int, default=None,
                    help="first N in file order; smoke tests only, collapses onto few dbs")
    ap.add_argument("--sample", type=int, default=None,
                    help="deterministic random subset of N examples; use this for screening")
    ap.add_argument("--sample-seed", type=int, default=0)
    ap.add_argument("--stages", nargs="*", default=None,
                    help="stage names; default is the whole ablation. The "
                         "holdout-en and holdout-ru stages are never in the "
                         "default and have to be named")
    ap.add_argument("--concurrency", type=int, default=None,
                    help="examples processed in parallel; overrides config")
    ap.add_argument("--emb-top-k", type=int, default=5,
                    help="top-k tables for the embedding schema linker (link_emb stages)")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    m = cfg["models"][args.model]
    data_root = cfg["data_root"]
    out_dir = cfg.get("out_dir", "results")
    concurrency = args.concurrency or m.get("concurrency") or cfg.get("concurrency", 32)

    client = ModelClient(
        model=m["model"],
        base_url=m.get("base_url", "http://localhost:8000/v1"),
        api_key=m.get("api_key", "EMPTY"),
        max_tokens=m.get("max_tokens", 1024),
        timeout_s=m.get("request_timeout_s", cfg.get("request_timeout_s", 600.0)),
        max_retries=m.get("max_retries", cfg.get("max_retries", 2)),
    )

    stages = pick_stages(args.stages)
    if any(f.get("dataset") == "holdout" for _, f in stages):
        require_recorded_run(args.model)
    for name, flags in stages:
        out = os.path.join(out_dir, f"{args.model}.{name}.jsonl")
        run_flags = dict(flags)
        if run_flags.get("schema_link_emb"):
            run_flags["emb_top_k"] = args.emb_top_k
        summary = run(data_root, client, out, limit=args.limit,
                      sample=args.sample, sample_seed=args.sample_seed,
                      concurrency=concurrency, **run_flags)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
