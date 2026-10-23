#!/usr/bin/env python3
"""Summarise one results file: accuracy, latency, speed, truncation, failure mix.

    python scripts/arm_report.py results/arctic-7b-q4.base.jsonl [--max-tokens 1024]

Truncation matters for the product and not only for the score. A model that
writes a reasoning preamble before the SQL can hit the token cap before the
query appears, which shows up as a wrong answer while the model was not
actually wrong. Reporting that share separately keeps the two apart.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    i = min(int(q * len(xs)), len(xs) - 1)
    return xs[i]


def classify(rec: dict) -> str:
    """Bucket a wrong answer by why it was wrong, so the mix is actionable."""
    if rec.get("correct"):
        return "верно"
    err = (rec.get("error") or "").lower()
    if not rec.get("pred_sql"):
        return "SQL не извлечён"
    if "runtime:" in err or "timeout" in err or "timed out" in err:
        return "сбой или таймаут"
    if err:
        return "ошибка СУБД"
    return "неверный результат"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--max-tokens", type=int, default=1024,
                    help="cap used for the run; completions at the cap count as truncated")
    args = ap.parse_args()

    recs = [json.loads(line) for line in open(args.path) if line.strip()]
    if not recs:
        raise SystemExit(f"{args.path}: пусто")

    n = len(recs)
    correct = sum(1 for r in recs if r.get("correct"))
    lat = [r["usage"]["latency_s"] for r in recs if r.get("usage")]
    comp = [r["usage"]["completion_tokens"] for r in recs if r.get("usage")]
    calls = [r["usage"]["model_calls"] for r in recs if r.get("usage")]
    # Per-example cap: a stage with k calls can legitimately produce k*cap tokens.
    truncated = sum(
        1 for r in recs
        if r.get("usage") and r["usage"]["completion_tokens"] >= args.max_tokens * max(1, r["usage"]["model_calls"])
    )
    tok_s = (sum(comp) / sum(lat)) if sum(lat) else 0.0

    print(f"файл            {args.path}")
    print(f"примеров        {n}")
    print(f"точность EX     {correct / n:.1%}  ({correct} из {n})")
    print()
    print(f"задержка p50    {statistics.median(lat):.1f} с" if lat else "задержка       нет данных")
    if lat:
        print(f"задержка p95    {pct(lat, 0.95):.1f} с")
        print(f"задержка max    {max(lat):.1f} с")
    print(f"генерация       {tok_s:.1f} ток/с")
    if comp:
        print(f"выдано токенов  медиана {int(statistics.median(comp))}, max {max(comp)}")
    if calls:
        print(f"вызовов модели  медиана {int(statistics.median(calls))}")
    print(f"обрезано лимитом {truncated / n:.1%}  ({truncated} из {n})")
    print()
    print("разбор ответов")
    for label, k in Counter(classify(r) for r in recs).most_common():
        print(f"  {label:<20} {k:>4}  {k / n:>6.1%}")


if __name__ == "__main__":
    main()
