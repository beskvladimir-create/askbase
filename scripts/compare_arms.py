#!/usr/bin/env python3
"""Compare a schema-metadata arm against the plain held-out stage.

The verdict rule is the frozen one, not one chosen after seeing these numbers.
HOLDOUT.md fixes the recipe: percentile bootstrap over tasks (n = 48, never
over the 96 wordings, which are not independent), 2000 resamples, seed 0, 95%
level, and a verdict that changes between seeds 0 and 5 is recorded as
undetermined. Comparisons between two systems on the same set are paired, so
the task is resampled once and both arms are read from that same draw.

The thresholds were also written down first: an arm is worth building into the
product at +10 points or better on the English wordings, and an arm that lands
below the plain stage sinks the feature instead of inviting a second attempt.

Both metrics are printed. Strict EX is the pre-registered one. The relaxed
column removes the evaluator's own false alarms, measured at 20.8% of failures
by the hand review, and is the sensitivity, never the headline.

    python scripts/compare_arms.py qwen25-coder-14b
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
REPS = 2000
TARGET = 0.10          # the pre-registered "worth building" line

spec = importlib.util.spec_from_file_location("exr", ROOT / "scripts/ex_relaxed.py")
exr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exr)


def per_task(model: str, stage: str, relaxed: bool) -> dict[str, float]:
    """Mean correctness per task over that task's wordings, or {} if absent."""
    path = RES / f"{model}.{stage}.jsonl"
    if not path.is_file():
        return {}
    acc: dict[str, list[bool]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            ok = exr.reclassify(r)[0] if relaxed else bool(r["correct"])
            acc.setdefault(r["task"], []).append(ok)
    return {t: sum(v) / len(v) for t, v in acc.items()}


def paired(a: dict[str, float], b: dict[str, float], seed: int
           ) -> tuple[float, float, float]:
    tasks = sorted(set(a) & set(b))
    d = [a[t] - b[t] for t in tasks]
    rng = random.Random(seed)
    boot = sorted(sum(s) / len(s)
                  for s in ([rng.choice(d) for _ in d] for _ in range(REPS)))
    return (sum(d) / len(d), boot[int(0.025 * REPS)], boot[int(0.975 * REPS)])


def verdict(point: float, lo: float, hi: float) -> str:
    """The frozen one-verdict rule, applied to the two pre-registered lines.

    HOLDOUT.md: met when the whole interval lies on the right side of the
    threshold, not met when the whole interval lies on the wrong side,
    otherwise undetermined, and the point estimate does not enter into it. So
    an arm whose interval straddles +10 is undetermined against the build
    line rather than below it, and an arm whose interval straddles zero has
    not scored below the plain stage in the sense that sinks the feature.
    """
    if hi < 0:
        return "весь интервал ниже обычной стадии: фича отбрасывается"
    if lo >= TARGET:
        return f"весь интервал выше +{TARGET:.0%}: строить"
    if hi < TARGET:
        return f"весь интервал ниже +{TARGET:.0%}: порог не взят"
    return f"НЕ ОПРЕДЕЛЁН: интервал пересекает +{TARGET:.0%}"


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen25-coder-14b"
    # `-gen` is `-both` run against the generalised detectors, which find a
    # dictionary by size and by declared key instead of by a name ending in
    # `_ref`. It is the arm the product ships, so it is the one to read.
    arms = ["dev-notes-keys", "dev-notes", "dev-notes-both", "dev-notes-gen",
            "dev-notes-correct", "dev-samples", "dev-app", "dev-app2", "dev-app-ord"]
    for relaxed in (False, True):
        label = "ослабленная (чувствительность)" if relaxed else "строгая (предрег.)"
        print(f"\n=== {model}, метрика {label} ===")
        for lang in ("en", "ru"):
            base = per_task(model, f"holdout-{lang}", relaxed)
            if not base:
                print(f"  {lang}: нет обычной стадии, сравнивать не с чем")
                continue
            b = sum(base.values()) / len(base)
            print(f"  {lang}  обычная стадия {b:.1%} (n={len(base)})")
            for arm in arms:
                cur = per_task(model, f"{arm}-{lang}", relaxed)
                if not cur:
                    print(f"      {arm:16s} файла нет")
                    continue
                a = sum(cur.values()) / len(cur)
                p0, lo0, hi0 = paired(cur, base, 0)
                p5, lo5, hi5 = paired(cur, base, 5)
                v0, v5 = verdict(p0, lo0, hi0), verdict(p5, lo5, hi5)
                # The stability rule outranks either seed on its own.
                v = v0 if v0 == v5 else "НЕ ОПРЕДЕЛЁН (расходится по seed)"
                print(f"      {arm:16s} {a:6.1%}  {p0*100:+5.1f} пп "
                      f"[{lo0*100:+5.1f},{hi0*100:+5.1f}]  {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
