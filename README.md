# Askbase

A desktop application that answers questions about your own database in plain
language, with the model running on your machine. Free, no account, no telemetry.

**Status: 0.1.1 released for macOS on Apple Silicon.** The .dmg is on the
[releases page](https://github.com/beskvladimir-create/askbase/releases).
Release 0.1.0 is still listed and should not be used: it does not answer
questions at all, because the answer never reached the window from the thread
computing it. That is fixed in 0.1.1. The build is not signed with an Apple
developer certificate, so macOS asks to allow it once and the SHA-256 in the
release notes is worth checking. No accuracy figure of our own is published
yet: the screening runs are still going. Set 1 of the held-out set was frozen
on 27 October 2026 with a SHA-256 per domain and its rules written down before
any run; see [HOLDOUT.md](HOLDOUT.md).

[SECURITY.md](SECURITY.md) says what the application protects and what it does
not, and where to report a vulnerability. [NOTICE](NOTICE) lists every
third-party component and its licence. [CONTRIBUTING.md](CONTRIBUTING.md) has
the setup and the rules for changes. [HOLDOUT.md](HOLDOUT.md) is the frozen
held-out set: digests, thresholds and evaluation rules, all dated before the
run. The privacy notice is at
[askbase.besk.tech/privacy/](https://askbase.besk.tech/privacy/).

## Why this exists

Specialised text-to-SQL models became good at a size that fits in a laptop's
memory. Snowflake's Arctic-Text2SQL-R1-7B reports 68.9% execution accuracy on
BIRD dev at seven billion parameters under Apache-2.0. My own measurement of a
general-purpose Qwen2.5-Coder-32B with self-correction on the same split was
51.63% ([arXiv:2606.29733](https://arxiv.org/abs/2606.29733)). A specialised
model four and a half times smaller changes what a local product can promise.

Every existing desktop tool was built around a cloud model, because a year ago
that was the only option. See [docs/research.md](docs/research.md) for the
market review, with a source for each claim.

## What is in here

| Path | What it is |
|---|---|
| `src/nl2sql_app/bench/` | benchmark harness: BIRD loading, schema serialisation, the recipe, execution accuracy |
| `src/nl2sql_app/safety.py` | static check of generated SQL before execution: one SELECT, no recursive CTEs, forced row limit |
| `src/nl2sql_app/holdout/` | generator for the held-out evaluation set, reproducible byte for byte |
| `scripts/` | run a benchmark arm, re-score saved predictions, summarise a run, build the site |
| `desktop/askbase/` | the application: three screens, a settings dialog, the engine, the journal, and the plain-language explanation of each answer |
| `desktop/askbase/cli.py` | the same engine from the terminal: returns the query rather than the answer, and needs no Qt |
| `site/` | the site, built by `scripts/build_site.py` |
| `docs/research.md` | market and benchmark review, every claim with a source |
| `docs/readonly-role.md` | for database administrators: what the application runs, and the SQL to constrain it |

## Two things worth reading even if you never run this

**The evaluator was wrong, and the fix is documented.** Execution accuracy here
originally compared multisets of rows, while the official BIRD evaluator
compares sets (`set(predicted_res) == set(ground_truth_res)` in
`bird/llm/src/evaluation.py`). Scoring `SELECT name` differently from
`SELECT DISTINCT name` understated accuracy by 5.4 points on a 500-question
sample. The same code produced the numbers in arXiv:2606.29733, so those
absolute figures are understated by about as much. It was found by a mandatory
manual review of failures, which is now part of the protocol.

**Public benchmarks are not as solid as their scores suggest.** A CIDR 2026
study found annotation errors in 52.8% of BIRD Mini-Dev problems and 66.1% of
the Spider 2.0-Snow problems with open gold queries; correcting them moved
leading systems by up to 19 points and three ranking places. That is why this
project freezes a held-out set of its own with a SHA-256 digest and registers
the thresholds before the run.

## Running the application

```bash
cd desktop && uv venv && uv pip install PySide6 sqlglot
ollama pull hf.co/mradermacher/XiYanSQL-QwenCoder-7B-2504-GGUF:Q4_K_M
.venv/bin/python -m askbase
```

Drop in a `.sqlite` file, ask a question in Russian or English, and you get the
table, the query and a sentence saying what was counted and what was left out.
The model never touches the database: it is shown a schema snapshot and returns
text, that text is parsed and checked before anything runs, and it runs on a
read-only connection with a row limit and a timeout.

## Running the benchmark

```bash
uv venv && uv pip install -e '.[dev]'
./scripts/test_all.sh                  # 707 tests, no model needed

# Download BIRD dev from https://bird-bench.github.io/ into data/bird/
# then serve a model, for example with Ollama:
ollama pull hf.co/mradermacher/XiYanSQL-QwenCoder-7B-2504-GGUF:Q4_K_M
python scripts/run_bench.py --config configs/screen.yaml --model xiyan-7b-q4 \
    --stages base --sample 500
python scripts/arm_report.py results/xiyan-7b-q4.base.jsonl
```

`--sample` takes a deterministic random subset. `--limit` takes the first N in
file order, which collapses onto one or two databases and is only good for a
smoke test.

A change to the evaluator never means re-running a model: `scripts/rescore.py`
re-scores saved predictions and keeps the previous verdict in `correct_before`.

## Building the site

```bash
python scripts/make_images.py          # icons and link cards
python scripts/build_site.py           # pages, sitemap, robots, llms.txt
```

The build refuses to publish a figure that no results file backs. Numbers are
written into pages as references and substituted from `results/`, and a page
that quotes a measurement must also declare what to show while it does not
exist. Fonts are served from the site rather than a CDN, because a CDN request
would tell a third party who opened the page.

## Author

Vladimir Beskorovainyi, Enterprise AI Architect & CTO, author of the Amazon
bestseller "Enterprise AI: The KATA Way", founder of Besk Tech
([besk.tech](https://besk.tech)). ORCID
[0009-0004-7005-6242](https://orcid.org/0009-0004-7005-6242).

Related work: the on-prem text-to-SQL benchmark this grew from
([arXiv:2606.29733](https://arxiv.org/abs/2606.29733), code and results at
[Zenodo](https://doi.org/10.5281/zenodo.20952794)), and
[pii-roundtrip](https://github.com/beskvladimir-create/pii-roundtrip), an open
benchmark of anonymisation tools using the same evaluation discipline.

## Licence

MIT, see [LICENSE](LICENSE).
