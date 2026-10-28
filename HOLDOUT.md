# The held-out set

[Русская версия](HOLDOUT.ru.md)

A benchmark a tool has seen is not a benchmark. This file freezes a set before
anything is run on it: the generator is in the repository and reproduces every
domain byte for byte, the SHA-256 of each domain is recorded here, and the
rules by which the results will be judged are written down below rather than
chosen afterwards.

The discipline is the one worked out in
[pii-roundtrip](https://github.com/beskvladimir-create/pii-roundtrip/blob/main/HOLDOUT.md).
What is new here is that the set is bilingual on one gold query: each task has
one schema, one gold SQL and four question wordings, two English and two
Russian, written from the meaning rather than translated. That makes the gap
between languages measurable on an identical target, which no published set
offers.

`python -m nl2sql_app.holdout.verify` checks the digests before a run and
refuses a set that does not match. It also refuses to record a run from an
uncommitted tree, and refuses a second run of the same tool on the same set
unless a reason is given; the reason stays in `results/holdout_runs.jsonl`.

The data files are not committed. They are generated, so committing them would
add 16 000 rows of noise to every diff for no gain: the generator plus the
digest is a stronger guarantee than a checked-in copy, because it can be
re-derived and compared by anyone.


## Set 1, the calibration set. Frozen 27 October 2026, before any run

### Reproducing it

```bash
for d in medicine banking logistics public_services manufacturing hr; do
  python -m nl2sql_app.holdout.generate --domain "$d" \
      --seed 20261027 --now 2026-10-27 --out data/holdout
done
python -m nl2sql_app.holdout.verify --data data/holdout
```

`--now` is fixed on purpose and is never `date.today()`. Dates in the data are
derived from it, so a set regenerated on a different day would differ from the
frozen one in values that have nothing to do with the task.

The digest is over `canonical.json`, a sorted JSON dump of every table and
every task, not over the `.sqlite` file. Two SQLite files holding identical
data differ byte for byte, so hashing the blob would fail for reasons that say
nothing about the data.

### What is in it

| Domain | Tables | Rows | Tasks | SHA-256 of `canonical.json` |
|---|---:|---:|---:|---|
| banking | 9 | 3569 | 8 | `59dfd23d17ba05ebffc2d94f42ac46ab5f61320637341bd7c8b7230d99e8d6f7` |
| hr | 7 | 1394 | 8 | `08e446f428d5595573d8bfa85159d33130bb2468b3d20c54538b4c8b6e1640f3` |
| logistics | 9 | 2945 | 8 | `95df177d3cd716c39528156078a959da95b7a30e5804d54729cd38021376b683` |
| manufacturing | 9 | 1265 | 8 | `c7a40eed77fe0a9c03e1d763b839777d4306147a51c49d5a84dfa5889008eaca` |
| medicine | 9 | 4058 | 8 | `72c891de040330d98c2c02af7e2ec5370435dfdc3573ec35a4b079470ce557c6` |
| public_services | 7 | 2577 | 8 | `59276e69a8cfecc59ea03fafde325b0fbf272d4296ef8bbea1b47b09e8f8f857` |

48 tasks, 192 wordings, 50 tables, 15 808 rows. The same digests are held
machine-readably in `src/nl2sql_app/holdout/DIGESTS.json`, and a test asserts
that the two agree so they cannot drift apart.

The schemas carry the warts of a real database on purpose, because that is
what the benchmark is for: opaque column names, no comments, lookup tables of
codes rather than words, and a legacy duplicate column. RedSQL's own stated
limitation is that its schemas are clean and synthetic. A model that only
works on tidy schemas has to fail here.

The domains are country-neutral. Names, cities and currencies read as
international and carry no national identifier formats or local legislation,
so the difficulty comes from the schema rather than from locale trivia a model
either memorised or did not.

### What this set can decide, and what it cannot

This is the part that is usually left out, so it goes first.

At 48 tasks a 95% interval around an accuracy near 50% is about 14 points
wide on either side. Two models whose true accuracies differ by less than
roughly 28 points cannot be told apart on this set. The four open models
measured on BIRD so far sit between 40.8% and 51.2%, inside that band. So the
honest expectation, written down before the run rather than after it, is that
**П3 will come out "undetermined" on this set, and that is the correct
answer, not a disappointment.**

That is why set 1 is labelled a calibration set rather than the deciding one.
Its job is the one the plan needs doing first and does not need volume for:

1. Fix П3а, П5 and П6, which are hypotheses until a first measurement exists.
   A latency threshold invented before anything has been timed on this
   hardware would be a number made up.
2. Shake out the evaluator. Execution comparison fails in ways that look like
   model errors and are not: row order, integer against string, NULL against
   empty string, an extra column, rounding. CIDR 2026 found annotation errors
   in 52.8% of BIRD Mini-Dev problems; assuming our own evaluator is clean
   would be the same mistake one level closer to home.
3. Measure the gap between languages, which needs the paired wordings and not
   the volume: the pairing is within a task, so it is the one quantity this
   set estimates comparatively well.

Set 2, at the planned 100 tasks per domain, is the deciding set. At 600 tasks
the interval is about 4 points on either side, which is the resolution П3
needs. It will be generated, hashed and published here before anything is run
on it, exactly as this one was.

### Rules fixed before the run

**Execution accuracy.** A prediction is correct when the result set of the
generated query equals the result set of the gold query, compared as sets, as
the official BIRD evaluator does (`set(predicted_res) == set(ground_truth_res)`
in `bird/llm/src/evaluation.py`). Comparing multisets instead, which this
project did originally, scores `SELECT name` differently from
`SELECT DISTINCT name` and understated accuracy by 5.4 points on a 500
question sample.

**The resampling unit is the task, not the wording.** The four wordings of a
task share a schema and a gold query, so they are not independent, and
resampling them separately would narrow every interval in the direction that
flatters us. Per-language accuracy therefore has n = 48, not 96.

**Intervals.** Percentile bootstrap over tasks, 2000 resamples, seed 0, 95%
level (`src/nl2sql_app/bench/stats.py`). The language gap and any comparison
between two systems on the same set are paired: the pairs are resampled
together, because the same tasks are answered by both.

**Seed stability.** A verdict that changes between seeds 0 and 5 is recorded
as undetermined. A verdict that exists only because of which resamples were
drawn is not a finding.

**One verdict rule for every threshold.** Met when the whole 95% interval lies
on the right side of the threshold. Not met when the whole interval lies on
the wrong side. Otherwise undetermined. The point estimate does not enter into
it: deciding by the point and printing the interval beside it would make the
interval decoration.

**Thresholds.**

| | Threshold | Status on set 1 |
|---|---|---|
| П1 | Our engine's EX on the held-out set is not below the best available single model under the same protocol | fixed in advance; expect undetermined at this n |
| П2 | EX on BIRD dev not below 65% | fixed in advance; measured on BIRD, not here |
| П3 | EX on the English wordings not below the best closed model under the same protocol on the same set | fixed in advance; expect undetermined at this n |
| П3а | EX on the Russian wordings not more than 10 points below the English | hypothesis, **this set calibrates it** |
| П4 | 100% of attempts to leave SELECT blocked, 0 queries executed without a row limit and a timeout | absolute, no interval |
| П5 | p95 latency not above 20 s on an Apple M4 with 24 GB, schema up to 30 tables | hypothesis, **this set calibrates it** |
| П6 | Not below 80% of wording pairs give the same verdict | hypothesis, **this set calibrates it** |

A threshold marked as calibrated by this set is fixed here, in writing, before
set 2 is generated, and is not moved afterwards.

**Mandatory manual review of failures, before any verdict.** From each run,
take a random sample of at least 20 failures and read them by hand. Classify
each as a model error or a false failure of the evaluator, and publish the
proportion. A verdict announced without this step is a verdict about the
evaluator as much as about the model.

### Run plan, each step once, from committed code

1. `python -m nl2sql_app.holdout.verify --data data/holdout --record <tool>`
   before anything else. It refuses a set that does not match, a tree that is
   not committed, and a repeat without a reason.
2. All participants over the same interface, ours among them with no
   privileges: Arctic-Text2SQL-R1-7B, XiYanSQL-QwenCoder 7B and 14B,
   Qwen2.5-Coder 7B and 14B, and our engine. Per participant:

   ```
   python scripts/run_bench.py --config configs/holdout.yaml \
       --model <tool> --stages holdout-en holdout-ru
   ```

   The two stages are not part of the default ablation and have to be named,
   so that a sweep typed out of habit cannot spend the set. The runner refuses
   a run whose journal entry from step 1 is missing, a set whose digests have
   moved, `--sample` and `--limit`, and a concurrency above 1.
3. Closed models over an API on this synthetic set only, never on anyone's
   data. They are a reference point for П3 and nothing else.
4. Temperature 0, one request at a time, the timeout and retry count recorded
   in the summary. A run in which more than half the requests fail is refused
   by the runner rather than written out. Latency is recorded per question, not
   as a stage average, because П5 is a threshold on p95 and a mean cannot be
   turned back into one.
5. Per-question predictions are published with every run, failures included.

### After the run

Set 1 is run once. Its failures are then read by hand, which is the point of
it, and reading them makes it development data: from that moment it may not be
used to decide anything. Set 2 is generated and published before it is run,
and is what П1, П3 and П6 are decided on.


## Set 2, the deciding set

Not yet generated. 100 tasks in each of the six domains, four wordings each:
600 tasks and 2400 wordings. It will appear here with its command, its digests
and its rules before any tool is run on it, and this file will say on what
date and at which commit that happened.
