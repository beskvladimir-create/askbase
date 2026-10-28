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
    return bootstrap_mean([x - y for x, y in zip(xs, ys, strict=False)],
                          resamples=resamples, seed=seed, level=level)


# ---- the held-out set: clusters, because a task has four wordings ------------
#
# HOLDOUT.md fixes this before the run: "The resampling unit is the task, not
# the wording. The four wordings of a task share a schema and a gold query, so
# they are not independent, and resampling them separately would narrow every
# interval in the direction that flatters us. Per-language accuracy therefore
# has n = 48, not 96."
#
# These are that rule in code. Calling bootstrap_mean on 96 wordings would
# produce an interval about √2 too narrow and would be the published figure.


def bootstrap_mean_clustered(groups, *, resamples: int = RESAMPLES, seed: int = SEED,
                             level: float = LEVEL) -> Interval:
    """Percentile bootstrap for the mean, resampling whole clusters.

    `groups` holds one list per task: that task's wording scores. Tasks are
    drawn with replacement and every wording of a drawn task comes with it, so
    the interval accounts for the fact that two wordings of one question tend
    to be right or wrong together.

    The point estimate is still the mean over all wordings, because that is the
    accuracy on the set as published. Only the uncertainty changes, and `n` is
    reported as the number of tasks so that the figure cannot be read as if it
    came from 96 independent questions.
    """
    clusters = [[float(v) for v in g] for g in groups if len(g)]
    if not clusters:
        raise ValueError("нечего считать: ни одной задачи")
    flat = [v for g in clusters for v in g]
    point = sum(flat) / len(flat)
    k = len(clusters)
    if k == 1:
        return Interval(point, point, point, 1, resamples, seed, level)

    sums = [sum(g) for g in clusters]
    sizes = [len(g) for g in clusters]
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        total = 0.0
        count = 0
        for _ in range(k):
            j = rng.randrange(k)
            total += sums[j]
            count += sizes[j]
        means.append(total / count)
    means.sort()
    tail = (1.0 - level) / 2.0
    return Interval(
        point=point,
        low=_percentile(means, tail),
        high=_percentile(means, 1.0 - tail),
        n=k, resamples=resamples, seed=seed, level=level,
    )


def paired_difference_clustered(a_groups, b_groups, *, resamples: int = RESAMPLES,
                                seed: int = SEED, level: float = LEVEL) -> Interval:
    """Interval for a difference of means when both sides share the clusters.

    For the language gap, П3а: the same 48 tasks are answered in English and in
    Russian, so the task is drawn once and both languages' wordings for it come
    along. Resampling the two sides independently would throw the pairing away
    and widen the interval for no reason, which here is the direction that
    hides a gap rather than inventing one.

    The two lists are aligned by position: `a_groups[i]` and `b_groups[i]` must
    be the same task.
    """
    if len(a_groups) != len(b_groups):
        raise ValueError(f"выборки не спарены: {len(a_groups)} против {len(b_groups)}")
    pairs = [([float(v) for v in a], [float(v) for v in b])
             for a, b in zip(a_groups, b_groups, strict=True) if len(a) and len(b)]
    if not pairs:
        raise ValueError("нечего считать: ни одной задачи с обеими сторонами")

    def pooled(chosen) -> float:
        a_total = sum(sum(a) for a, _ in chosen)
        a_n = sum(len(a) for a, _ in chosen)
        b_total = sum(sum(b) for _, b in chosen)
        b_n = sum(len(b) for _, b in chosen)
        return a_total / a_n - b_total / b_n

    point = pooled(pairs)
    k = len(pairs)
    if k == 1:
        return Interval(point, point, point, 1, resamples, seed, level)

    rng = random.Random(seed)
    draws = [pooled([pairs[rng.randrange(k)] for _ in range(k)]) for _ in range(resamples)]
    draws.sort()
    tail = (1.0 - level) / 2.0
    return Interval(point, _percentile(draws, tail), _percentile(draws, 1.0 - tail),
                    k, resamples, seed, level)


def wording_agreement(pairs) -> tuple[float, int]:
    """П6: the share of wording pairs of one task that get the same verdict.

    `pairs` is (task key, correct) once per wording. Every two wordings of the
    same task form a pair, and a pair agrees when both are right or both are
    wrong. The threshold fixed before the run is "not below 80% of wording
    pairs give the same verdict": a model that answers the same question
    correctly only when it is phrased one particular way is not at the accuracy
    its score claims, and this is the number that says so.

    Returns (share, number of pairs). With no pair at all the share is 0.0,
    which is reported next to a count of 0 rather than hidden as a None: this
    statistic was promised in advance and its absence has to be visible.
    """
    by_task: dict[str, list[bool]] = {}
    for task, correct in pairs:
        by_task.setdefault(task, []).append(bool(correct))
    agree = total = 0
    for verdicts in by_task.values():
        for i in range(len(verdicts)):
            for j in range(i + 1, len(verdicts)):
                total += 1
                agree += int(verdicts[i] == verdicts[j])
    return (agree / total if total else 0.0), total
