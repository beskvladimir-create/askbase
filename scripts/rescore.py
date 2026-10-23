#!/usr/bin/env python3
"""Re-score saved predictions without asking a model anything.

    python scripts/rescore.py results/xiyan-7b-q4.base.jsonl --data-root <bird>

Predictions are the expensive part and they are already on disk, so a change to
the evaluator must never mean re-running a model. It also keeps the two apart:
re-scoring changes the verdict on a fixed set of answers, while re-running
changes the answers too, and only the first is legitimate after the fact.

The old verdict is kept in each record as `correct_before`, and the summary
reports both numbers. A score that silently replaces an earlier one is how a
benchmark loses its meaning.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nl2sql_app.bench.evaluator import execution_accuracy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--data-root", required=True, help="BIRD root with dev_databases/")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    path = Path(args.path)
    recs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    db_root = Path(args.data_root) / "dev_databases"

    before = sum(1 for r in recs if r.get("correct"))
    flipped_to_right: list[int] = []
    flipped_to_wrong: list[int] = []

    for r in recs:
        db = db_root / r["db_id"] / f"{r['db_id']}.sqlite"
        was = bool(r.get("correct"))
        if not r.get("pred_sql"):
            now, err = False, r.get("error")
        else:
            now, err = execution_accuracy(str(db), r["pred_sql"], r["gold_sql"], args.timeout)
        r["correct_before"] = was
        r["correct"] = now
        r["error"] = err
        if now and not was:
            flipped_to_right.append(r["qid"])
        elif was and not now:
            flipped_to_wrong.append(r["qid"])

    after = sum(1 for r in recs if r["correct"])
    n = len(recs)
    path.write_text("".join(json.dumps(r) + "\n" for r in recs))

    summary_path = path.with_suffix("").with_suffix(".summary.json")
    if summary_path.exists():
        s = json.loads(summary_path.read_text())
        s["ex_accuracy_before_rescore"] = s.get("ex_accuracy")
        s["ex_accuracy"] = round(after / n, 4) if n else 0.0
        s["rescored"] = True
        summary_path.write_text(json.dumps(s, indent=2))

    print(f"файл      {path}")
    print(f"было      {before}/{n} = {before / n:.1%}")
    print(f"стало     {after}/{n} = {after / n:.1%}")
    print(f"разница   {after - before:+d} примеров")
    print(f"стали верными: {len(flipped_to_right)}, стали неверными: {len(flipped_to_wrong)}")
    if flipped_to_wrong:
        print(f"  внимание, примеры, потерявшие верность: {flipped_to_wrong[:10]}")


if __name__ == "__main__":
    main()
