# Contributing

[Русская версия](CONTRIBUTING.ru.md)

Issues and pull requests are welcome. Write in Russian or English, whichever
is easier for you.

One thing to know before you start: this repository is exported from a working
tree rather than developed in place, so a pull request is applied by hand and
credited in the commit message. That is a limitation of how the project is run
today, not a judgement on the contribution, and it is on the list to remove.


## Setup

Two environments, because they exist for different reasons. The first has the
benchmark dependencies, the second has Qt.

```bash
uv venv && uv pip install -e '.[dev]'
cd desktop && uv venv && uv pip install PySide6 sqlglot pytest && cd ..
```

To run the application you also need a model served locally:

```bash
ollama pull hf.co/mradermacher/XiYanSQL-QwenCoder-7B-2504-GGUF:Q4_K_M
cd desktop && .venv/bin/python -m askbase
```


## Checks

```bash
./scripts/test_all.sh          # 669 tests, no model needed
.venv/bin/python -m ruff check .
python scripts/build_site.py --check
```

There is no CI yet. The three commands above are what has to pass, and they
have to be run locally.

`test_all.sh` runs all three suites on purpose. Running only the first silently
skips every interface test, which is how a window that could not answer a
question reached a packaged build.


## Rules for changes

- **A behaviour change comes with a test that fails before the fix.** Release
  0.1.0 did not answer questions at all and 382 tests were green, because none
  of them pressed Ask and waited for a result. A test that cannot fail is
  worse than no test: it reports a property nobody is checking.
- **Numbers on the site are never typed by hand.** A figure from our own
  measurements is written as a reference, `{=model|dataset|metric}`, and
  resolved from `results/` at build time. `scripts/build_site.py` stops the
  build on a reference nothing backs. A figure quoted from somebody else's
  paper is prose and carries its source link inline.
- **A failed run is not a result.** The runner refuses to write a summary when
  more than half the requests failed, and a run withdrawn after the fact moves
  to `results/void/` with a file saying why. Do not delete it quietly.
- **The held-out set is not for development.** Do not tune anything against
  `src/nl2sql_app/holdout/` output, and do not change the generator without
  saying so: it is reproducible byte for byte and that is the point of it.
- **The safety layer only ever gets stricter by accident.** A change to
  `src/nl2sql_app/safety.py` that allows something new needs a test showing
  what it now allows and why that is safe.
- **No real data in issues.** Reproduce a problem with an invented SQLite file.
  If the schema itself is the problem, rename the tables and columns first.
