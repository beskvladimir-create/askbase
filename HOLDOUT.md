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

   `scripts/holdout_queue.sh` walks the participants in this order, both steps
   per model, and stops on the first failure instead of going on to the next
   one. Expect hours: 192 wordings per model, one request at a time.
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

### What the review of set 1 found, 29 October 2026

Twenty failures from each of the twelve runs, 240 in all, read against the
question and both result sets. No case was left as "unsure". Fifty of the 240
turned out to be false alarms of the evaluator rather than model errors, a
share of 20.8%, and over all 1152 records 125 were affected, 10.9%. The share
per run is in `results/*.review.json`, the sample is deterministic from seed 0,
and `scripts/ex_relaxed.py` holds the arithmetic with one stated relaxation per
defect.

One defect was in our code. `result_set_match` compared `repr(row)` rather than
the rows, inherited from an earlier multiset version that had to sort and so
needed a string key. Under that comparison 10996 and 10996.0 are different
answers, so a model writing `amount / 100` against a gold of `amount / 100.0`
scored zero for a correct answer. Fixed, with a test and a mutant; it moved one
record of 1152.

Three defects were in the set, and the freeze means they stay. Floating-point
noise in the last bit after AVG, eight records. The gold of ten tasks returns a
column its question never asks for, 67 records: "Which customers hold more than
two accounts?" is answered by a list of customers, and the gold also returns
the count, so every model that answered the question scored zero. The mirror of
it, a model returning every gold column plus others, 49 records.

The numbers in this file and on the site stay the pre-registered ones. The
relaxed figures are published beside them as a sensitivity, not instead of
them, because a rule chosen after seeing the data is not a pre-registered rule.
The ranking is the same under both: Qwen2.5-Coder-14B first, both XiYan builds
last. The relaxation is not even across models, which is itself a finding: it
is worth 15 points to Qwen2.5-Coder-7B and 7 to XiYan-14B, so strict EX scores
query style as well as correctness.

The reported share is a lower bound. The review found a fourth shape it does
not count: an answer of the same width with a different column composition,
`(id, name)` against a gold of `(name, count)`.

Rules this adds to set 2, before it is generated:

1. The gold's select list holds exactly what the question asks for, and the
   wordings of one task agree on which columns those are.
2. A Russian wording is checked for words that read as a filter condition.
   "Сколько счетов открыто в каждой валюте?" made models add
   `WHERE status_cd = 'open'`, which inflates the language gap for a reason
   that has nothing to do with language.


### The schema-metadata arms, written down 1 November 2026, before the run

Set 1 is spent. Its failures were read on 29 October 2026, and HOLDOUT.md says
plainly that reading them turns the set into development data. So what follows
is **not** a held-out measurement and no figure from it may be reported as
one. The stage names carry `dev-` for that reason, and a number taken from
`results/*.dev-notes*` is a development number wherever it later appears.

What these arms are for is one engineering decision: should the product carry
a schema annotation step. The review answered why it might. Splitting the 62
traps by who holds the missing information gives 29 schema-semantics traps, 14
genuine ambiguities and 19 that are plain SQL skill. On tasks whose only trap
is schema semantics Qwen2.5-Coder-14B scored 39%; on tasks with no such trap
it scored 90%. Both figures are on the relaxed measure. That was
not said when they were first written down, and they were then quoted on the
site beside a strict headline; on the strict measure the same split is 31.6%
and 68.8%, and `scripts/by_trap.py` computes it into the summary files. That is not a model that cannot write SQL.

Two interventions, run separately so one run can tell them apart.

**`dev-notes-keys`** prints the foreign keys the databases already declare.
`serialize_schema` was dropping them, so the model saw
`shp(id, cust_id, org_cd, dst_cd, ...)` with no way to learn that both route
columns point at `loc_ref`. This adds no inference at all; it stops throwing
away what the DDL says.

**`dev-notes`** adds the four mechanical detectors in
`src/nl2sql_app/bench/annotate.py`: unit suffixes, coded columns expanded into
their lookup rows, date columns that are one field split by a migration, and
effective-dated history tables. **`dev-notes-both`** runs the two together.

Three things fixed in advance, so the result cannot be talked into shape
afterwards.

1. **What would count.** The arms are worth building into the product if
   `dev-notes-both` beats the plain stage by at least 10 points on the English
   wordings, judged by the paired bootstrap over tasks that every comparison
   here uses. Below that the annotation screen is not worth the friction.
2. **What would sink it.** Any arm that scores *below* the plain stage says
   the notes are crowding the prompt rather than informing it, and the feature
   is dropped rather than tuned until it passes.
3. **What cannot be claimed either way.** Set 1 is development data, so a
   gain here is a reason to build the step and to measure it properly on set
   2. It is not evidence about accuracy on unseen questions, and it does not
   touch П1 to П6, which stay exactly as they were measured.

The annotations are generated from the schema and from the contents of small
lookup tables. Nothing in `annotate.py` reads a question, a task file or a
gold query, and a test asserts over the whole set that no note contains any
wording or any gold query. Without that property the arm would measure a leak
instead of an annotation.

One class of trap is deliberately left undetected. A loan with
`closed_at IS NULL` is open, but a shipment with `delivered_at IS NOT NULL` is
not necessarily delivered, because a lost one can carry a delivery attempt.
No rule phrased over names and nullability separates those two, so a note
would be right once and wrong once. That residue is what a person who knows
the business has to answer, and it is the honest limit of doing this
mechanically.


### What the arms measured, 1 November 2026, after the run

Qwen2.5-Coder-14B, set 1, six stages, strict EX, paired bootstrap over tasks
against the plain stage. Development numbers, as the section above says.

| arm | en | vs plain | ru | vs plain |
| --- | --- | --- | --- | --- |
| plain stage | 49.0% | | 50.0% | |
| `dev-notes-keys` | 55.2% | +6.2 [+2.1, +12.5] | 45.8% | -4.2 [-9.4, +1.0] |
| `dev-notes` | 67.7% | +18.8 [+8.3, +31.2] | 68.8% | +18.8 [+9.4, +29.2] |
| `dev-notes-both` | 68.8% | +19.8 [+9.4, +31.2] | 68.8% | +18.8 [+9.4, +29.2] |
| `dev-notes-gen` | **71.9%** | **+22.9 [+13.5, +34.4]** | 67.7% | +17.7 [+8.3, +29.2] |

Both seeds agree on every verdict. The relaxed metric moves the baselines and
not the picture: 62.5% to 80.2% on English, 60.4% to 79.2% on Russian.

**The verdict against the +10 line is undetermined, on every arm.** The one
verdict rule says met only when the whole interval lies on the right side of
the threshold, and the point estimate does not enter into it. `dev-notes-both`
has a point estimate of +19.8, twice the line, and a lower bound of +9.4,
which is one task-wording below it. That is the rule doing exactly what it was
written to do, and the honest reading is that the direction is certain and the
size is not. Set 2 is what sizes it.

**The sinking condition did not fire.** `dev-notes-keys` on Russian is the only
arm whose point estimate is below the plain stage, and its interval straddles
zero, so by the same rule it has not scored below. Keys are kept, because
`serialize_schema` discarding the declared foreign keys is a defect whatever
the arm says, but the measurement gives them no credit of their own: added on
top of the notes they are worth +1.1 on English and nothing on Russian.

**Where the gain landed, which is the part that was predictable in advance.**
Splitting the 48 tasks by the hand-audited trap classes and comparing the plain
stage with `dev-notes-both` on English: schema-only tasks 31.6% to 68.4%,
mixed tasks 16.7% to 58.3%, skill-only tasks 63.3% to 63.3%, clarification-only
tasks 87.5% to 87.5%. Twenty-three of the 48 tasks did not move by a single
wording. A longer prompt or a luckier decode would not sort itself into the
classes that way, and that is the reason to believe the mechanism rather than
the headline.

So the schema annotation step gets built, and it is measured on set 2 before
any figure from it is published.


**`dev-notes-gen` is the arm that ships, and it is the first one whose whole
interval clears the +10 line on English.** It is `dev-notes-both` run against
a detector that finds a dictionary table by its size and by its declared keys
instead of by a name ending in `_ref`, which was a convention of the schemas
in `data/holdout` and of nothing a user will ever open. On Chinook the old
detector would have found nothing, so the +19.8 above was partly a measurement
of my own naming.

The caveat belongs with the number and not after it. The +10 line was fixed in
advance for `dev-notes-both`, and this is a second version of the code, written
once the first result had been seen. It was changed to fix a validity problem
rather than to chase the threshold, the reason was written down and committed
before the arm ran, and the change was verified on set 1 to add notes without
removing any. That is the best case a second attempt can be, and it is still a
second attempt. One pre-registered shot it is not, so what this settles is
which code ships. Set 2 is where the number counts.

Russian stays undetermined at +17.7 [+8.3, +29.2], and the gap between the two
languages is 4.2 points, inside the ten of П3а. p95 is 14.05 s against the
20 s of П5, so the shipped arm meets the latency threshold with 6 s to spare.

Where the gain landed, against the plain stage on English: schema-only tasks
31.6% to 68.4%, mixed 16.7% to 58.3%, skill-only 63.3% to 70.0% and
clarification-only 87.5% to 93.8%. The last two are one task of fifteen and
half a task of eight. They are noise at this n and not a mechanism: a note
about a column has no way to help a model that has to write an anti-join, and
claiming otherwise from a single task would be reading the resample rather
than the result.

### The remaining bucket, written down 1 November 2026, before the run

The notes moved schema-only tasks from 31.6% to 68.4% and skill-only tasks by
exactly nothing: 63.3% before and after, fifteen of the 48 tasks. That is the
detectors behaving as described rather than a disappointment, because no note
about a column helps a model that has to write an anti-join. The question this
raises is what, if anything, does.

**What is being run.** `dev-notes-correct`, which is the shipped arm plus the
self-correction step the ablation already carries: execute the query, and on
an error feed the error back and revise, at most twice.

**What is predicted, in advance, so that a null result is a finding.** Close to
nothing. The skill failures in the review are queries that run: an inner join
where an anti-join was needed returns the wrong set successfully, and a repair
loop driven by an error message never sees it. The share of failures that were
malformed queries at all was small. If this arm does deliver, then the account
of the failures in this file is wrong somewhere, which is worth more than the
points.

**What would count.** At least 5 points over `dev-notes-gen` on the English
wordings, whole interval above the line by the paired bootstrap, and p95 not
above the 20 s of П5. A second model call that buys less than that is not
worth the latency it costs.

**What is deliberately not being run, and why that is a result too.**
Self-consistency: five samples at temperature 0.6, voted by result set. It is
the only mechanism available here that can touch a query which runs and
returns the wrong rows, because the vote compares result sets rather than
error messages. It is also out of reach. p95 is 11.58 s on the plain stage and
15.02 s with the notes, against a ceiling of 20 s fixed in П5, and five
samples put it near seventy-five. A feature that cannot meet a pre-registered
latency threshold is not a product option, and measuring its accuracy would
only produce a number that cannot be used. If it is ever run it is as a
declared slow mode with a threshold of its own.

That latency figure is a cost of the notes and is recorded as one. The notes
spend 3.4 s of p95 and 8.4 s of headroom under П5 becomes 5.0 s. It is paid
for by 19 points on set 1, which is a trade worth making, and it is the reason
the prompt gets facts about the columns rather than the contents of every
small table in the file.


### What the self-correction arm measured, 1 November 2026, after the run

Nothing, and the reason is worth more than the points.

`dev-notes-correct` scored 71.9% on English and 67.7% on Russian, which is
`dev-notes-gen` to the last digit on both languages, with identical intervals.
All 96 generated queries were byte-identical in each language.

A null that exact is more likely to be a plumbing fault than a finding, so it
was checked rather than written up. The usage tally settles it. The arm records
`self_correct: true`, wall time rose from 597 s to 630 s, and `exec_calls` went
from 0 to 1 on every one of the 96 records: the step ran. `model_calls` stayed
at 1 on every record, which is the answer. The repair prompt never fired,
because no generated query raised an execution error for it to fire on.

So the prediction recorded before the run was right, and understated. It said
close to nothing. What the run shows is that the class of failure a repair loop
can address is **empty** on this set: with the notes in place, 192 of 192
queries execute. On the plain stage exactly one record of 96 failed to execute
at all.

The product consequence is direct and it is not about the model. Every
remaining failure is a query that runs and returns the wrong rows, so no step
keyed off an error message can ever reach it, and that includes the repair
attempt the application already makes. What is left is prevention, which is
what the notes are and why they worked, and making the wrongness visible to
the person, which is a question about the interface and not about the pipeline:
the SQL and the rows have to be on screen, because nothing inside the pipeline
can flag them.


### The prompt that ships, written down 2 November 2026, before the run

A gap found by looking rather than by measuring, which is the uncomfortable
kind. The harness rendered a schema as `cust(id, full_name, ...)`. The desktop
application rendered `CREATE TABLE "cust" ("id", "full_name", ...);`, in
alphabetical order instead of creation order, with views included, and with a
line of example values under any table holding a low-cardinality column. The
instruction text around them was identical, so the difference had gone
unnoticed. Every figure in this file was therefore measured on a prompt the
product does not send, and the prompt the product does send had never been
measured at all.

That is fixed at the root rather than per arm: one renderer, `render_schema`
in `nl2sql_app.bench.schema`, now serves both, and a test in the application's
suite asserts that what the harness produces with `ddl=True, samples=3` is
exactly what the window puts in front of the model, up to the notes block the
window adds. Two renderers is how a number stops describing a product.

**What is being run.** `dev-samples` is the shipped arm plus the example
values alone, keeping the compact listing. `dev-app` is the shipped prompt
entire, example values and CREATE TABLE form together. Both carry the keys and
the notes, so the comparison is against `dev-notes-gen` at 71.9% and not
against the plain stage.

**What is predicted, in advance.** Little, and possibly negative for the
example values. Before the notes existed they were the only hint that
`status_cd` holds 1 and 2; now a note says 1 is active, so the sample repeats
what the note already decodes and adds a column of digits to a prompt that has
grown by a third. The CREATE TABLE form is expected to be neutral here,
because its purpose is surviving names like `order` and `sales 2026`, and this
set has none. If the example values cost points, that is worth knowing twice
over: once for the product, which would then stop sending them, and once
because it would mean the notes have made an older feature redundant.

**What would count.** This arm is not looking for a gain. It is closing the
gap between the published figure and the shipped prompt, so the number that
matters is `dev-app`, whatever it is, and it replaces `dev-notes-gen` as the
figure that describes the product. A loss of more than 5 points on English
against `dev-notes-gen`, whole interval below the line, means the application
stops sending example values, and that change is then measured on set 2 like
any other.


### One word of a note, written down 2 November 2026, before the run

Reading the five tasks that fail in both English wordings turned out to be
worth more than another arm. Two of the five are not misunderstandings at all.

On `log-004` the gold is `SUM(cost_cents) / 100.0` and the model wrote
`SUM(cost_cents / 100)`. On `bank-002` the gold is
`SUM(CASE WHEN dir_cd = 2 THEN amt_cents ELSE -amt_cents END) / 100.0` and the
model wrote the same expression with the sign convention inverted, which is
the same thing, and `/ 100`. Both were run against the databases: 8 579 947.13
came back as 8 579 038, and -189 905.58 came back as -189 905. The model had
understood that direction lives in `dir_cd` and not in the sign, that the
amounts are hundredths, and that the question asks for currency units. It
divided by an integer and SQLite dropped the fraction.

The note said "divide by 100". The model did exactly that. Four of the sixteen
real errors on English carry integer division by 100, and four of twenty-one
on Russian; on the plain stage, with no note telling the model to divide at
all, there was one. **The note created the failure class it exists to
prevent**, which is the strongest argument in this file for reading the
output of a feature rather than reading its score.

**What changes.** `TEMPLATES["minor_units"]` and `["basis_points"]` now say to
divide by 100.0 and say why. One word, plus the reason, which is there because
a bare 100.0 invites a model to normalise it back.

**What is being run.** `dev-app2`, the shipped prompt with the new wording.
Its only difference from `dev-app` is those two templates.

**What is predicted.** Four records on English and four on Russian, so about
four points each, which would be the whole of the integer-division class. Less
than that means the model is dividing by an integer for reasons the note does
not control, and the next step would be an instruction in the prompt rather
than in a note.

**This is not tuning to the set.** A product that silently truncates a sum of
money is wrong for every user, with or without a gold query to compare
against. Two other tasks in that hard core fail on tie-breaking inside
`ORDER BY ... LIMIT`, where the gold adds a deterministic second key and the
model does not. That one *would* be tuning: the question genuinely does not
say which of two tied rows it wants, and the answer belongs in set 2's
authoring rules and in showing the person the SQL, not in a prompt line that
teaches the model our gold's habit.


### What the prompt-format arms measured, 2 November 2026, after the run

The gap is closed: the shipped prompt scores 71.9% on English, the same as the
compact listing it was never the same as. On Russian it scores 63.5% against
67.7%. So the published English figure survives the discovery that it had been
measured on the wrong prompt, and the Russian one does not.

Paired against `dev-notes-gen`, strict, frozen recipe:

| | en | ru |
| --- | --- | --- |
| `dev-samples`, example values alone | -2.1 [-7.3, +3.1] | +3.1 [+0.0, +7.3] |
| `dev-app`, the shipped prompt | +0.0 [-7.3, +7.3] | -4.2 [-11.5, +3.1] |
| the CREATE TABLE change alone | +2.1 [-4.2, +8.3] | **-7.3 [-13.5, -1.0]** |

The example values do nothing in either direction, which was the prediction
and is the more useful half of it: the notes decode the codes those values
were hinting at, so an older feature has been made redundant rather than
harmful. It stays, because it costs nothing and covers columns no detector
reaches.

The one signal is the last row, stable across both seeds, whole interval below
zero. It is also confounded, and the confound is mine: `ddl` moved two things
at once, the quoting and the table order, which went from order of creation to
order by name. Creation order puts a table next to the dictionary that decodes
it, `cust` beside `resid_ref` and `acct` beside `cur_ref`; by name they are
scattered. That is a mechanism, not a conclusion, so `schema_order` is now a
parameter of its own and `dev-app-ord` measures the ordering with the quoting
held fixed.

Nothing is being changed in the application on the strength of these numbers.
Set 1 is development data and picking a prompt format by its score here is
fitting to the set, which is the thing this file exists to prevent. What the
arms were for was making one measurement describe the product, and that is
done.


### Authoring set 2: the rules became checks, 2 November 2026

Set 1 has 48 tasks and its defects were found by reading 240 failures by
hand. Set 2 has an order of magnitude more and they will not be. So the two
authoring rules this file recorded after the review, plus the two defects
found since, are now `nl2sql_app.holdout.lint`, which runs over a generated
set and prints what is wrong with it.

| rule | the defect it is made of |
| --- | --- |
| `gold_fails` | the gold does not execute |
| `gold_empty` | the gold returns no rows, so every empty answer scores correct |
| `nondeterministic_gold` | rows at the cut are tied on every ordering key, so the gold itself varies with the query plan |
| `ambiguous_cut` | rows at the cut are tied on the key the question names: it asks for the top three and there are four |
| `float_noise` | a float with a tail no answer can match, after AVG |
| `filter_word_without_filter` | a Russian wording reads as a condition the gold does not apply |
| `no_traps` | a task that declares no trap, which is a task nobody decided the point of |

One judgement is deliberately left to a person. Whether the gold's select
list holds exactly what the question asks is about two sentences in two
languages and a SQL statement, and a rule that guessed would either pass
everything or fail honest tasks. `--select-lists` prints the two side by side
so the judgement is cheap rather than automated away. That defect was the
largest of the four in set 1, 67 records.

The checker was validated against the set whose defects are known. It finds
`float_noise` in bank-006 and med-006, which are the eight records this file
attributes to floating-point noise, and `filter_word_without_filter` in
bank-001, which is the example recorded here word for word. It finds
`ambiguous_cut` in med-004, where the third and fourth most common diagnoses
both occur 96 times, and does not fire on med-002, where the cut at five
falls between 21 and 19. A checker validated only on its own fixtures agrees
only with itself, so both halves are tests.

Its first version was wrong in the ordinary case and the tests caught it. The
rule had been syntactic, looking for an ORDER BY whose last key is not an
aggregate, and a gold writes `COUNT(*) AS n ... ORDER BY n DESC`: the last key
is an alias, no aggregate appears in it, and the rule saw a tiebreak that was
not there. Both replacements are empirical.

**How large set 2 should be.** Resampling the 48 observed per-task scores up
to larger sets gives the width the spec is buying:

| tasks | half-width of the 95% interval | per domain |
| ---: | ---: | ---: |
| 48 | ±11.0 | 8 |
| 100 | ±7.7 | 16 |
| 200 | ±5.4 | 33 |
| 300 | ±4.5 | 50 |
| 600 | ±3.1 | 100 |

The 600 already written down buys ±3.1, which is what it takes to call a
five-point difference between two arms. 300 buys ±4.5 for half the authoring,
and 200 buys ±5.4. The figure stays at 600, because the thresholds in this
file are stated in whole points and П1 and П3 compare two systems, which
needs the pairs to be tighter than the gap being argued about. A smaller set
would be a decision to stop asking those questions.


### The divisor and the table order, 2 November 2026, after the run

| stage | en | ru |
| --- | --- | --- |
| `dev-notes-gen`, compact listing | 71.9% | 67.7% |
| `dev-app`, the shipped prompt | 71.9% | 63.5% |
| `dev-app2`, divisor fixed to 100.0 | 74.0% | 66.7% |
| `dev-app-ord`, and tables in creation order | **75.0%** | **70.8%** |

**The divisor.** Paired against `dev-app`: +2.1 [-4.2, +9.4] on English and
+3.1 [-2.1, +9.4] on Russian, neither significant. The mechanism, however, is
not in doubt and does not depend on the score: records whose prediction
divided by an integer 100 and failed went from 4 to 0 on English and from 5 to
0 on Russian. The class is gone. Six of those nine records became correct and
three did not, and all three are floating-point comparison, which is the
defect class the review already attributed to the set and which the new
`float_noise` rule flags in bank-006. So the prediction of four points per
language was right about the class and wrong about the points, because half
the class was sitting on a second defect.

**The order.** The 7.3 points the quoted form cost on Russian were mostly the
table order, not the quoting. Measured at the same divisor, creation order
beats alphabetical by +1.0 [-5.2, +7.3] on English and +4.2 [-1.0, +10.4] on
Russian, stable across both seeds, neither significant on its own but
consistent in direction across two languages. Creation order puts a table next
to the dictionary that decodes it, which is what the schemas were written to
do and what alphabetical order undoes.

**What ships and what does not, and the line between them.** The divisor ships.
It is a correctness fix with a reason that does not come from a score: a
product that silently truncates a sum of money is wrong for every user, and
the evidence is a class of nine records going to zero, not a point estimate.
The table order does not ship. It is a change whose only argument is that it
scored better on a set that has been read, and seven prompt variants have now
been run on that set; picking the highest is how a development number turns
into a published one. It is recorded here as the single candidate
configuration to carry to set 2, named in advance so that the comparison there
is one comparison and not seven.


## Set 2, the deciding set

Not yet generated. 100 tasks in each of the six domains, four wordings each:
600 tasks and 2400 wordings. It will appear here with its command, its digests
and its rules before any tool is run on it, and this file will say on what
date and at which commit that happened.
