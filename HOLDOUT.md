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
   empty string, an extra column, rounding. Jin et al. found annotation errors
   in 52.8% of BIRD Mini-Dev problems; assuming our own evaluator is clean
   would be the same mistake one level closer to home.
3. Measure the gap between languages, which needs the paired wordings and not
   the volume: the pairing is within a task, so it is the one quantity this
   set estimates comparatively well.

Set 2 is the deciding set. It was planned at 100 tasks per domain and the
size was amended on 2 November to 48 per domain, 288 in all, after the first
144 measured what the schemas actually hold; the reason and the cost are
recorded below, under the first pass. 288 tasks buy about 4 points on either
side, which is the resolution П3 needs. It is generated, hashed and published
here before anything is run on it, exactly as this one was.

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


### Set 2, first pass and an amended size, 2 November 2026, before the second pass

Six domains, 24 tasks each: 144 tasks and 576 wordings, written today. The
authoring rules of the previous section ran against every one of them, and
they caught two real defects while the set could still be changed. `log2-019`
asked for customers who had never sent anything, and in that domain every
customer has a shipment, so the gold returned nothing and a model answering
"none" would have scored correct; the anti-join moved one level out, to
customers with no incident, where the answer is 33 rows. The second was the
rule firing on a cut inside a tie, which is the defect set 1 is stuck with in
two of its tasks.

Reproducibility, not a freeze. The command is

```
python -m nl2sql_app.holdout.generate --domain <name> \
    --seed 20261102 --now 2026-11-02 --out data/holdout2 --set 2
```

and the SHA-256 of each `canonical.json` as it stands after the first pass:

| Domain | Tasks | SHA-256 of `canonical.json` |
| --- | ---: | --- |
| banking | 24 | `3c7b7876f59b1d3e06ac9f5a8a04f51f8332ebeea21117cbc36deec3a95f9a3d` |
| hr | 24 | `8ac8273aca64225344870acb16c0f3c62b3027cd5c2dd5ce74b524a0ce7116c2` |
| logistics | 24 | `eb592be0b5bedbeafc05640efc7a1e906412d31a871f6e6c68adc2787a304ac7` |
| manufacturing | 24 | `302d411fa486aa64d9199a780db2099de7ba58ecd222c07bb14304d381b2a08e` |
| medicine | 24 | `621a419cc82397f304d9e4d1051a54bc03ccbe64f355bcaf71ab6de36b8bd127` |
| public_services | 24 | `a5dc24d7ba56be1890bb8cf255327b7e62a97d07335bb746f168b9c3fc04422d` |

These digests will change with the second pass, and saying so here is the
point: `DIGESTS2.json` carries `"frozen": false`, and `verify.record` refuses
to write a run against a set whose registry says that. No tool can be run on
set 2 today, and the refusal is a test, not a convention.

**The size recorded earlier in this file is amended, and here is the reason.**
The spec said 100 tasks per domain, 600 in all, and the sizing note above
decided to keep that figure. Writing the first 144 measured what that costs.
A schema carries about 24 questions that hide something different from one
another; past that the traps start repeating, and a task that re-asks an
earlier trap against another column lengthens the set without making it more
informative. 600 would be two to three more days of authoring and a set whose
extra 456 tasks are mostly variations of its first 144.

What the sizes buy, resampling the 48 per-task scores of the best measured
arm (`dev-app-ord`, 75.0% on English) up to larger sets, 2000 resamples,
seeds 0 and 5:

| tasks | per domain | half-width, seed 0 | seed 5 |
| ---: | ---: | ---: | ---: |
| 48 | 8 | ±9.9 | ±9.4 |
| 144 | 24 | ±5.6 | ±5.6 |
| 288 | 48 | ±4.0 | ±3.8 |
| 600 | 100 | ±2.7 | ±2.7 |

The earlier table in this file gives slightly different widths because it
resampled a different arm's scores. Both are development numbers and neither
is a result.

So the target becomes 48 tasks per domain, 288 in all, which buys ±4.0 and
leaves 144 of the work done. That is the resolution this file already said
П1 and П3 need, and it is reached without padding. 144 would have been ±5.6,
which is wider than the whole points the thresholds are written in, and
freezing there would have been a decision to stop asking those two questions
while still printing their names in the table.

The set is frozen once, when it is complete, and not between passes.

### Set 2, second pass and the freeze, 2 November 2026

The second 24 tasks per domain are written, and the set is frozen at 288
tasks and 1152 wordings. What the second pass is made of, by domain, is the
part worth recording: the first pass used each schema's headline difficulty,
and a second pass of the same difficulty would have been the padding the
sizing note warned about.

| domain | what the second pass works that the first did not |
| --- | --- |
| banking | a closing date that has not arrived, so the status and the date disagree; accounts older than their holder and transactions older than their account; a balance built from `dir_cd` because no column holds one; an account in every currency of the reference; two loans whose terms overlap; minor units and basis points in one expression |
| logistics | `leg.seq`, the first and the last leg and their carriers; `inc.at`, which is independent of the shipment's own dates, so an incident can precede dispatch or follow delivery; `carr.since` later than the shipment; legs of one shipment in different modes; cost per kilometre and per kilogram |
| medicine | a doctor hired after the admission; a prescribed course outlasting the stay; `primary_flag` read from the other side, an encounter with no primary diagnosis; age at the date of admission rather than today; two correlated subqueries compared with each other |
| hr | the adjacent pair of pay rows, which is the revision itself and its sign; a pay row or an absence dated before hire or after leaving; the currency changing inside one history; the second level of `mgr_id`; a department compared with its own parent inside HAVING; the salary in force on the leaving day |
| manufacturing | several defects on one movement and several grades among them; the distance in days from movement to defect; the price window read from the other side, including the price in force at a part's first movement; the sign of `kind_cd` together with the range join; the same quantity priced twice, at the time and today |
| public services | the order of stages inside a case, an undecided stage before a decided one, and the last stage against the state of the case in both directions; an applicant who has used every region and every service; `sla_days` as a quantity for arithmetic rather than as a boundary; the share of local filings, where the applicant's city is compared with a region name |

**What the rules caught this time**, while the set could still be changed:

- Nine tasks were discarded after running them, because their gold was empty
  or identically zero: a carrier with no legs, a carrier that never crossed a
  border, a doctor with no encounters, a doctor who never prescribed
  intravenously, a revision that changed nothing, a department with no dollar
  salary, a movement with no price in force, a price window with no movement,
  a part that is never scrapped. Each was replaced by a question the data can
  answer.
- `mfg2-034` tripped `filter_word_without_filter` on my own Russian wording:
  it said "открытое окно цены" while the condition on `valid_to` lived in the
  ON clause. The condition moved into WHERE, which changes nothing about what
  the query returns and makes it say what it does.
- `med2-035` exposed a hole in the checker rather than in itself. Its ordering
  key is `AVG(julianday(a) - julianday(COALESCE(b, c)))`, the key list was
  split on every comma, and the rewritten query failed to parse, so the tie
  check reported that it could not check the cut. A tie behind such a key was
  invisible, which is a hole exactly where the hard tasks are. The split now
  tracks bracket depth, with a test.

**And one the rules could not catch, so they were extended.** `bank2-024` and
`log2-024` held the same gold and the same English wording, differing only in
the database they run against, because banking and logistics both have a
`cust` table with a nullable city. No per-task rule can see that; it was found
by comparing every gold and every wording in the set against every other
before the freeze. The logistics task now counts shipments whose customer has
no city, which still reads the NULL but through a join, and `duplicate_gold`
and `duplicate_wording` are rules of the checker with tests of their own.

**The freeze.** Generated with

```
python -m nl2sql_app.holdout.generate --domain <name> \
    --seed 20261102 --now 2026-11-02 --out data/holdout2 --set 2
```

| Domain | Tasks | SHA-256 of `canonical.json` |
| --- | ---: | --- |
| banking | 48 | `f3a2f7ca7cec85022a5db1f18c01e909ace4d023767690dd9ba0c680db9814e4` |
| hr | 48 | `c817a306308705184dc62d0d0cba4ad13211f957275c1812b6fe8e500ac8834a` |
| logistics | 48 | `536c7ad4db30d3c48444606d218a5e7332cab61f3baaa745965a0e9e4de4dd2e` |
| manufacturing | 48 | `a7dd4121dc122605c3cebc82742b48edd5f1def9ecb3662f24281f565cced6e7` |
| medicine | 48 | `f6e6fd845df7867588efc821956af47e3f5fb006c42d89af6de948dfb5328d67` |
| public_services | 48 | `fcfbe883ae32204c86221283f5fcbcffef55327f06de0f7a48be745e4b581e36` |

`DIGESTS2.json` now carries `"frozen": true` and `"frozen_at": "2026-11-02"`,
and the same digests, so the file a reader checks and the file the code checks
are one file. The test that asserted set 2 was not yet frozen is gone, deleted
in the commit that flipped the flag, and the guard it protected is now tested
against a registry built for the purpose, so it outlives this set and is there
for the next one.

**What this set is not.** It is 288 tasks against six schemas, not a sample of
anything. Every number it will produce is conditional on these schemas, these
traps and this one generator seed, and a model that happens to fit this
generator's idea of a legacy column will do better here than in a warehouse.
The trap mix is 206 tasks whose traps are all schema semantics, 51 schema and
skill together, 15 skill alone and 16 involving an intent ambiguity, which
says plainly that this set mostly measures reading a schema nobody documented.

### The set 2 run, written down 2 November 2026, before it starts

Three arms, named before the first request, because a set that is run once
and read afterwards cannot be used to choose among seven.

| stage | what it is | who runs it |
| --- | --- | --- |
| `set2-base` | the bare protocol, byte for byte what set 1's `holdout-en`/`holdout-ru` sent | all six participants, ours among them with no privileges |
| `set2-app` | the prompt the application actually sends, including the divisor fix that shipped after set 1 | our engine |
| `set2-app-ord` | the same prompt with the tables left in creation order | the single candidate, named in the section above before this set existed |

Order, fixed: our engine, then the candidate, then the same weights bare,
then the other five participants. `scripts/holdout2_queue.sh` walks exactly
that, records the journal entry before each tool's first stage, and stops on
the first failure rather than walking past it. 576 wordings per language, one
request at a time; on set 1's timings that is about an hour per language for
the 14B models and four for Arctic, so the queue is a day of compute and not
a coffee break.

**Predictions.** Written now so that a null result is informative later.

| what | prediction | why this number |
| --- | --- | --- |
| `set2-app` English | 62%, surprised outside 54 to 70 | set 1 gave 74.0% at the fixed divisor on 48 tasks of first-pass difficulty; half of set 2 is the second pass, which was written to need correlated subqueries, self-joins, range joins and quantities no column holds, so a drop of 10 to 14 points is the honest expectation |
| `set2-app` Russian | 4 to 8 points below English | set 1's gaps were 4.2 and 7.3 points at the same prompt |
| П3а, Russian within 10 points of English | met | the gap has been under 8 points in every measured arm |
| `set2-base`, Qwen2.5-Coder-14B | 38%, surprised outside 30 to 46 | 49.0% on set 1, scaled by the same difficulty argument |
| the engine against the same weights bare | +20 points, whole interval above +10 | set 1 gave +22.9 [+11.5, +34.4] at n = 48, and at n = 288 the interval is about ±4, so if the effect is real this is where it stops being undetermined |
| `set2-app-ord` against `set2-app` | undetermined on English, between −2 and +4; positive on Russian, between +2 and +6, and short of +10 | set 1 gave +1.0 [−5.2, +7.3] and +4.2 [−1.0, +10.4], consistent in direction and significant on neither |
| П6, wording agreement | 70 to 80%, so **not met** | every measured arm has been between 70.8% and 75.0%, and the threshold is 80%. This is a prediction that a threshold this project wrote down fails |
| П5, p95 latency | 12 to 18 s, met | 16.7 s and 13.1 s on set 1 with the same schemas and the same prompt, on the same machine |
| the trap split | the bucket with no schema trap at least 25 points above the bucket where every trap is schema semantics | set 1 gave 68.8% against 31.6% |

**What ships on what evidence.** The order change ships only if the paired
interval against `set2-app` excludes zero on the positive side in both
languages. One language, or a point estimate with an interval crossing zero,
means it does not ship: that is the same rule the divisor was held to, and the
divisor cleared it on a mechanism rather than on a score.

**What happens after, and it is not optional.** At least 20 random failures
per run are read by hand and classified as a model error or a false failure of
the evaluator, and the proportion is published. Set 2 is then spent, exactly
as set 1 was.

## Set 2, the deciding set

Frozen on 2 November 2026: 48 tasks in each of the six domains, four wordings
each, 288 tasks and 1152 wordings. The command, the per-domain digests and
what the second pass was made of are in the section above. Nothing has been
run on it yet. The run plan at the top of this file applies: each tool once,
from committed code, journalled, and a repeat stays a repeat.

### What set 2 measured, 4 November 2026, after the run

The queue ran from 2 to 4 November, sixteen runs, no repeats and no stops.
Three arms, named before the first request, and six participants, our engine
among them through the same interface.

| run | EX | 95% interval | p95 | wording agreement | evaluator false alarms |
| --- | ---: | --- | ---: | ---: | ---: |
| `set2-app`, English | **57.47** | 52.43 – 62.33 | 23.88 s | 76.7% | 15% |
| `set2-app`, Russian | **48.61** | 43.58 – 53.99 | 17.52 s | 75.7% | 20% |
| `set2-app-ord`, English | 55.73 | 50.69 – 60.76 | 22.14 s | 79.5% | 5% |
| `set2-app-ord`, Russian | 49.83 | 44.79 – 55.03 | 23.73 s | 76.7% | 10% |
| `set2-base`, Qwen2.5-Coder-14B, English | 36.81 | 31.77 – 41.67 | 16.34 s | 79.2% | 0% |
| `set2-base`, Qwen2.5-Coder-14B, Russian | 30.90 | 26.04 – 35.94 | 14.73 s | 86.1% | 0% |
| `set2-base`, Arctic-7B Q4_K_M, English | 33.68 | 28.65 – 38.54 | 43.67 s | 80.6% | 0% |
| `set2-base`, Arctic-7B Q4_K_M, Russian | 28.65 | 23.78 – 33.51 | 54.13 s | 83.0% | 0% |
| `set2-base`, Arctic-7B Q8_0, English | 32.29 | 27.60 – 37.15 | 51.33 s | 82.6% | 10% |
| `set2-base`, Arctic-7B Q8_0, Russian | 28.30 | 23.78 – 32.64 | 66.04 s | 78.1% | 20% |
| `set2-base`, Qwen2.5-Coder-7B, English | 25.87 | 21.53 – 30.21 | 9.15 s | 82.3% | 10% |
| `set2-base`, Qwen2.5-Coder-7B, Russian | 22.22 | 17.88 – 26.56 | 10.52 s | 85.4% | 5% |
| `set2-base`, XiYanSQL-7B, English | 22.40 | 18.40 – 26.39 | 8.83 s | 80.2% | 5% |
| `set2-base`, XiYanSQL-7B, Russian | 17.88 | 13.89 – 21.88 | 7.83 s | 87.2% | 0% |
| `set2-base`, XiYanSQL-14B, English | 19.27 | 15.10 – 23.61 | 15.88 s | 88.5% | 5% |
| `set2-base`, XiYanSQL-14B, Russian | 17.53 | 13.72 – 21.53 | 12.88 s | 91.3% | 0% |

Intervals are a percentile bootstrap over tasks, 2000 resamples, seed 0, with
n = 288 tasks rather than 1152 wordings. `scripts/thresholds.py` computes them
through the clustered helpers in `nl2sql_app.bench.stats`, which is the same
implementation of the verdict rule the rest of the project uses.

**Threshold verdicts.**

| threshold | measured | verdict |
| --- | --- | --- |
| П1, the engine not below the best single model | +20.66 pp [+15.62, +25.69] in English, +17.71 pp [+12.85, +22.57] in Russian, against Qwen2.5-Coder-14B on the bare arm | **met** in both languages |
| П3, English not below the best closed model | not measured | **no verdict**: step 3 of the run plan, closed models over an API, was not carried out on this set, so the threshold has no other side |
| П3а, Russian not more than 10 points below English | −8.85 pp [−12.33, −5.56] | **undetermined**: the interval crosses ten points |
| П5, p95 not above 20 s | 23.88 s [20.66, 27.70] in English, 17.52 s [16.55, 19.45] in Russian | **not met** in English, **met** in Russian |
| П6, wording agreement not below 80% | 76.7% [71.87, 81.26] in English, 75.7% [70.82, 80.56] in Russian | **undetermined** in both languages |
| П4, safety | every attempt to leave SELECT blocked | **met**, an absolute threshold with no interval |

П3 is left without a verdict on purpose. It was written as a comparison with a
closed model on the same set, no closed model was run on set 2, and until one
is there is no second side to compare with. Recording it as "undetermined"
would pass off a missing measurement as a wide interval.

**What ships.** Nothing. The rule was written before the run: the table order
ships only if the paired interval against `set2-app` excludes zero on the
positive side in both languages. It came out at −1.74 pp [−4.34, +1.04] in
English and +1.22 pp [−1.56, +3.82] in Russian, so the interval crosses zero
either way. The arm does not ship, and on set 1 it looked better than it is.

**The hand review.** Twenty random failures from each of the sixteen runs, 320
in all, read with the gold query, the prediction and both result sets side by
side. 299 model errors, 21 false alarms of the evaluator, nothing left
unresolved. The false-alarm share per run runs from 0% to 20%, and 6.6% over
all of them. On set 1 the same share was 20.8% and reached 45%. The difference
is not in the evaluator, which is unchanged: on set 1 some gold queries
returned a column the question had not asked for, and the evaluator honestly
counted the difference as a failure. Set 2's gold queries were written to the
rule "the answer holds only what was asked", and false alarms fell threefold.

The classification followed a list written in advance: a false alarm is
rounding or precision, extra columns, or an equivalent way of naming the same
entity. One case on set 2 was not on that list, the same two numbers with the
columns swapped on a question that does not fix their order. Before counting
it as a false alarm I checked all 300 failures reviewed up to that point by
machine: the pattern occurs exactly once, so extending the rule changes no
earlier verdict. The opposite case also came up and was counted as a model
error, because there the question fixed the column order and the model
swapped it.

**Predictions and outcomes.** Written down before the run, in the section
above.

| prediction | outcome | |
| --- | --- | --- |
| `set2-app`, English 62%, surprised outside 54 and 70 | 57.47% | hit |
| `set2-base`, Qwen2.5-Coder-14B 38%, surprised outside 30 and 46 | 36.81% | hit |
| the engine against the same weights without the prompt: +20 points, the whole interval above +10 | +20.66 [+15.62, +25.69] | hit |
| the trap split: a gap of at least 25 points | 26.3 points in English, 27.4 in Russian | hit |
| `set2-app-ord` against `set2-app`, English: undetermined, between −2 and +4 | −1.74, undetermined | hit |
| `set2-app`, Russian 4 to 8 points below English | 8.85 points below | missed, at the edge |
| П3а met | undetermined | **missed** |
| `set2-app-ord` against `set2-app`, Russian: positive, between +2 and +6 | +1.22, undetermined | **missed** |
| П5 met, p95 between 12 and 18 s | 23.88 s in English, the threshold is not met | **missed** |
| П6 not met, between 70 and 80% | 76.7% and 75.7%, but the verdict is undetermined | the point landed, the verdict did not |

Four predictions out of ten did not come true, and three of them in the same
direction: I underestimated how much harder the second pass is, not only in
accuracy but in time. p95 rose from 16.7 s on set 1 to 23.88 s, because second
pass tasks need correlated subqueries and self-joins, and the model takes
longer to write them. The latency threshold I expected to clear with room to
spare is not met in English. This is exactly why the predictions are written
down first.

**Set 2 is spent.** From 4 November 2026 nothing may be decided on it, exactly
as with set 1. The next threshold that needs checking needs a set 3.

### What of set 2 is published and what is not, 4 November 2026

Set 2 is spent for decisions, but as reading material it is live: put its 1152
wordings on the open web and the next model measured on it will have read
them. That is exactly the contamination that makes BIRD figures untrustworthy,
and reproducing it on our own set would be odd.

So the export to the public repository (`scripts/export_public.py`) removes
the `TASKS_2` block from the six domain modules and leaves an empty tuple with
an explanation in its place. Nothing else is removed.

What is published for each of the 1152 wordings:

- the gold query,
- the query the model wrote,
- the verdict, right or wrong, and the execution error if there was one,
- the description of the trap,
- latency and token usage,
- the freeze digests in `DIGESTS2.json`, the proof that the set was fixed
  before the first request,
- the whole hand review of the failures, with a verdict and a note per case.

Only the question text is withheld. A result record does not carry it anyway:
the wording was deliberately not duplicated into the results, so that there is
no second, editable copy of the thing under SHA-256. The ranking page's
promise that per-question predictions are published with every run, wrong ones
included, is kept literally.

The guarantee is not discipline. After copying, the export searches the
resulting tree for each of the 1152 wordings and refuses to hand it over if it
finds even one. Tests that need set-2 tasks skip in the public copy through
the `frozen_holdout_2` fixture rather than being weakened: the skip is on data
absent by design, never on an assertion that fails.

The wordings will be published once the set has served its term the way set 1
did, which is when a set 3 exists and the decisions move to it.
