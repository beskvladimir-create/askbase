"""Confidence intervals and the verdict rule, as docs/design.md fixes them.

The ranking page promises both in print: "confidence intervals by bootstrap
over questions, 2000 resamples, seed 0", and one verdict rule for every
threshold, "met if the whole 95% interval lies on the right side of the
threshold, not met if the whole interval lies on the wrong side, otherwise
undetermined". Neither existed in code. A protocol that is only written down
is a promise; this file is the part that can be run.

Three decisions here, each with a reason.

**Resampling questions, not predictions.** The uncertainty being estimated is
"what would this model score on another sample of questions from the same
distribution", so the resampling unit is the question. Resampling at any finer
grain would understate the interval, which is the direction that flatters us.

**Seed fixed and recorded.** 2000 resamples and seed 0 are in the published
protocol, so they are arguments with those defaults and the summary records
what was used. A number whose seed is not written down cannot be reproduced.

**The verdict is deliberately allowed to be undetermined.** That is the whole
point of fixing the rule before the run: a result that does not clear a
threshold must be reportable as "we do not know" rather than rounded into an
answer. pii-roundtrip does the same, and the discipline only works if the
undetermined case is a normal outcome rather than an embarrassment.

Also here: a seed-stability check. design.md says a verdict that moves between
seeds 0 and 5 is recorded as undetermined, which is a guard against a verdict
that exists only because of which resamples happened to be drawn.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

RESAMPLES = 2000
SEED = 0
LEVEL = 0.95


@dataclass(frozen=True)
class Interval:
    """A point estimate and the interval around it, with how it was made."""

    point: float
    low: float
    high: float
    n: int
    resamples: int
    seed: int
    level: float

    def as_dict(self) -> dict:
        return {
            "point": round(self.point, 4),
            "low": round(self.low, 4),
            "high": round(self.high, 4),
            "n": self.n,
            "resamples": self.resamples,
            "seed": self.seed,
            "level": self.level,
        }


@dataclass(frozen=True)
class Verdict:
    """Met, not met, or undetermined, against one threshold."""

    name: str
    threshold: float
    direction: str          # "at_least" or "at_most"
    interval: Interval
    outcome: str            # "met", "not_met", "undetermined"
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "threshold": self.threshold,
            "direction": self.direction,
            "outcome": self.outcome,
            "reason": self.reason,
            "interval": self.interval.as_dict(),
        }


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear interpolation between order statistics.

    Written out rather than taken from numpy: the benchmark package is meant to
    run with nothing but the standard library and sqlglot, and a dependency
    added for one function is a dependency the packaged application also has to
    carry.
    """
    if not sorted_values:
        raise ValueError("нечего считать: пустая выборка")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


def bootstrap_mean(values, *, resamples: int = RESAMPLES, seed: int = SEED,
                   level: float = LEVEL) -> Interval:
    """A percentile bootstrap interval for the mean of `values`.

    `values` is one number per question: 1 and 0 for execution accuracy, or
    seconds for latency. The mean of a 0/1 list is the accuracy, so the same
    function serves both and there is one interval definition in the project
    rather than one per metric.
    """
    data = [float(v) for v in values]
    n = len(data)
    if n == 0:
        raise ValueError("нечего считать: ни одного вопроса")
    point = sum(data) / n
    if n == 1:
        return Interval(point, point, point, n, resamples, seed, level)

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += data[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    tail = (1.0 - level) / 2.0
    return Interval(
        point=point,
        low=_percentile(means, tail),
        high=_percentile(means, 1.0 - tail),
        n=n, resamples=resamples, seed=seed, level=level,
    )


def bootstrap_quantile(values, q: float, *, resamples: int = RESAMPLES,
                       seed: int = SEED, level: float = LEVEL) -> Interval:
    """The same, for a quantile. Threshold П5 is on p95 latency, not on a mean."""
    data = sorted(float(v) for v in values)
    n = len(data)
    if n == 0:
        raise ValueError("нечего считать: ни одного вопроса")
    point = _percentile(data, q)
    if n == 1:
        return Interval(point, point, point, n, resamples, seed, level)

    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(resamples):
        sample = sorted(data[rng.randrange(n)] for _ in range(n))
        draws.append(_percentile(sample, q))
    draws.sort()
    tail = (1.0 - level) / 2.0
    return Interval(point, _percentile(draws, tail), _percentile(draws, 1.0 - tail),
                    n, resamples, seed, level)


def verdict(name: str, interval: Interval, threshold: float, *,
            direction: str = "at_least") -> Verdict:
    """One rule for every threshold, from docs/design.md section 2.5.

    Met when the whole interval is on the right side, not met when the whole
    interval is on the wrong side, undetermined when it straddles. The point
    estimate deliberately does not enter into it: deciding by the point and
    quoting the interval beside it would make the interval decoration.
    """
    if direction not in ("at_least", "at_most"):
        raise ValueError(f"неизвестное направление порога: {direction}")

    if direction == "at_least":
        met = interval.low >= threshold
        failed = interval.high < threshold
    else:
        met = interval.high <= threshold
        failed = interval.low > threshold

    if met:
        outcome, reason = "met", "весь интервал по нужную сторону порога"
    elif failed:
        outcome, reason = "not_met", "весь интервал по другую сторону порога"
    else:
        outcome, reason = ("undetermined",
                           "интервал пересекает порог, вердикт не выносится")
    return Verdict(name, threshold, direction, interval, outcome, reason)


def stable_across_seeds(values, threshold: float, *, direction: str = "at_least",
                        seeds=(SEED, 5), resamples: int = RESAMPLES,
                        level: float = LEVEL) -> tuple[bool, list[str]]:
    """Does the verdict survive a change of seed?

    design.md: "a verdict that moves between seeds 0 and 5 is recorded as
    undetermined". A verdict that exists only because of which resamples were
    drawn is not a finding, and this is the cheapest way to notice.

    Returns (stable, outcomes) so the caller can record both.
    """
    outcomes = [
        verdict("", bootstrap_mean(values, resamples=resamples, seed=s, level=level),
                threshold, direction=direction).outcome
        for s in seeds
    ]
    return len(set(outcomes)) == 1, outcomes


def paired_difference(a, b, *, resamples: int = RESAMPLES, seed: int = SEED,
                      level: float = LEVEL) -> Interval:
    """Interval for the difference in means, resampling the pairs together.

    For "is our engine better than the single model" and for the gap between
    languages, where the same questions are answered by both and the two
    results are not independent. Resampling the two lists separately would
    throw away the pairing and widen the interval for no reason.
    """
    xs = [float(v) for v in a]
    ys = [float(v) for v in b]
    if len(xs) != len(ys):
        raise ValueError(f"выборки не спарены: {len(xs)} против {len(ys)}")
    return bootstrap_mean([x - y for x, y in zip(xs, ys)],
                          resamples=resamples, seed=seed, level=level)
