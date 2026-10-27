"""Intervals and the verdict rule.

The ranking page promises both in print. The properties that matter are that
the numbers are reproducible, that the interval covers the truth about as often
as it claims, and that the verdict is genuinely allowed to be undetermined,
because the whole value of fixing the rule in advance is that a result which
does not clear a threshold can be reported as "we do not know".
"""
from __future__ import annotations

import random

import pytest

from nl2sql_app.bench.stats import (
    LEVEL,
    RESAMPLES,
    SEED,
    bootstrap_mean,
    bootstrap_quantile,
    paired_difference,
    stable_across_seeds,
    verdict,
)


def coin(n, p, seed=1):
    rng = random.Random(seed)
    return [1 if rng.random() < p else 0 for _ in range(n)]


# ---- the interval ----------------------------------------------------------

def test_the_point_estimate_is_the_plain_mean():
    values = [1, 1, 0, 1, 0, 0, 1, 0]
    assert bootstrap_mean(values).point == pytest.approx(0.5)


def test_the_same_seed_gives_the_same_interval():
    values = coin(300, 0.6)
    a, b = bootstrap_mean(values), bootstrap_mean(values)
    assert (a.low, a.high) == (b.low, b.high)


def test_a_different_seed_moves_it():
    values = coin(300, 0.6)
    a = bootstrap_mean(values, seed=0)
    b = bootstrap_mean(values, seed=5)
    assert (a.low, a.high) != (b.low, b.high)
    assert a.point == b.point           # the estimate itself does not move


def test_the_interval_contains_the_estimate():
    values = coin(400, 0.55)
    i = bootstrap_mean(values)
    assert i.low <= i.point <= i.high


def test_more_questions_give_a_narrower_interval():
    small = bootstrap_mean(coin(50, 0.6))
    large = bootstrap_mean(coin(2000, 0.6))
    assert (large.high - large.low) < (small.high - small.low)


def test_the_defaults_are_the_published_protocol():
    i = bootstrap_mean([1, 0, 1])
    assert (i.resamples, i.seed, i.level) == (RESAMPLES, SEED, LEVEL)
    assert (RESAMPLES, SEED, LEVEL) == (2000, 0, 0.95)


def test_an_all_correct_run_has_a_degenerate_interval():
    i = bootstrap_mean([1] * 100)
    assert (i.point, i.low, i.high) == (1.0, 1.0, 1.0)


def test_one_question_is_handled_rather_than_crashing():
    i = bootstrap_mean([1])
    assert (i.point, i.low, i.high) == (1.0, 1.0, 1.0)


def test_no_questions_is_an_error_not_a_zero():
    # A score of 0.0 from an empty run is the most dangerous number there is.
    with pytest.raises(ValueError):
        bootstrap_mean([])


def test_the_interval_covers_the_truth_about_as_often_as_it_claims():
    # The property the interval exists for. Not a proof, but it would catch an
    # interval that is wildly too narrow, which is the direction that flatters.
    truth, covered, trials = 0.6, 0, 60
    for s in range(trials):
        i = bootstrap_mean(coin(200, truth, seed=s), resamples=400, seed=s)
        if i.low <= truth <= i.high:
            covered += 1
    assert covered >= int(trials * 0.85), f"покрытие {covered}/{trials}"


# ---- quantiles, for the latency threshold ----------------------------------

def test_a_quantile_interval_brackets_the_quantile():
    values = [float(x) for x in range(1, 101)]
    i = bootstrap_quantile(values, 0.95)
    assert i.low <= i.point <= i.high
    assert 90 <= i.point <= 100


# ---- the verdict rule ------------------------------------------------------

def test_met_only_when_the_whole_interval_clears_the_threshold():
    v = verdict("П2", bootstrap_mean([1] * 200), 0.65)
    assert v.outcome == "met"


def test_not_met_when_the_whole_interval_is_on_the_wrong_side():
    v = verdict("П2", bootstrap_mean([0] * 200), 0.65)
    assert v.outcome == "not_met"


def test_undetermined_when_the_interval_straddles_the_threshold():
    # The outcome that has to be a normal result rather than an embarrassment,
    # or fixing the rule in advance buys nothing.
    v = verdict("П2", bootstrap_mean(coin(100, 0.65), resamples=400), 0.65)
    assert v.outcome == "undetermined"


def test_the_point_estimate_does_not_decide_it():
    # A run whose point estimate clears the threshold but whose interval does
    # not must be undetermined; deciding by the point would make the interval
    # decoration.
    # Built explicitly rather than drawn: the point has to sit just above the
    # threshold and the sample has to be small enough that the interval still
    # reaches below it, and a random draw does not reliably give that.
    values = [1] * 27 + [0] * 13            # 0.675, on 40 questions
    i = bootstrap_mean(values, resamples=400)
    assert i.point > 0.65, i.point
    assert i.low < 0.65, i.low
    assert verdict("П2", i, 0.65).outcome == "undetermined"


def test_an_at_most_threshold_is_read_the_other_way():
    # П5 is a latency ceiling: lower is better.
    fast = bootstrap_quantile([1.0] * 200, 0.95)
    slow = bootstrap_quantile([99.0] * 200, 0.95)
    assert verdict("П5", fast, 20.0, direction="at_most").outcome == "met"
    assert verdict("П5", slow, 20.0, direction="at_most").outcome == "not_met"


def test_an_unknown_direction_is_refused():
    with pytest.raises(ValueError):
        verdict("x", bootstrap_mean([1, 0]), 0.5, direction="roughly")


def test_a_verdict_carries_its_own_reasoning():
    v = verdict("П2", bootstrap_mean([1] * 200), 0.65)
    assert v.reason
    assert v.as_dict()["interval"]["resamples"] == RESAMPLES


# ---- seed stability --------------------------------------------------------

def test_a_clear_result_is_stable_across_seeds():
    stable, outcomes = stable_across_seeds([1] * 300, 0.65, resamples=400)
    assert stable and set(outcomes) == {"met"}


def test_a_borderline_result_can_move_and_that_is_reported():
    stable, outcomes = stable_across_seeds(coin(60, 0.66, seed=7), 0.65, resamples=200)
    assert len(outcomes) == 2
    assert stable == (len(set(outcomes)) == 1)


# ---- paired differences ----------------------------------------------------

def test_a_paired_difference_keeps_the_pairing():
    # The same questions answered by both, so the results are not independent.
    a = [1, 1, 1, 0, 1, 1, 0, 1, 1, 1] * 20
    b = [1, 0, 1, 0, 1, 0, 0, 1, 0, 1] * 20
    i = paired_difference(a, b)
    assert i.point == pytest.approx(sum(a) / len(a) - sum(b) / len(b))
    assert i.low <= i.point <= i.high


def test_identical_runs_give_a_difference_of_exactly_zero():
    a = coin(200, 0.6)
    i = paired_difference(a, a)
    assert (i.point, i.low, i.high) == (0.0, 0.0, 0.0)


def test_unpaired_lengths_are_refused():
    with pytest.raises(ValueError):
        paired_difference([1, 0, 1], [1, 0])
