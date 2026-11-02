#!/usr/bin/env python3
"""EX as pre-registered, and EX with the evaluator's false alarms removed.

The pre-registered metric is strict set equality against the gold query, BIRD
semantics. HOLDOUT.md also requires a hand review of failures that publishes
the share which are false alarms of the evaluator rather than model errors.
This script is the arithmetic of that review: it applies one stated relaxation
per defect found, and prints both numbers side by side. The pre-registered
figure is the headline and this one is the sensitivity; swapping them would be
choosing the rule after seeing the data.

Four defects, found by reading 240 sampled failures:

repr      evaluator.py compared {repr(row)} rather than the rows, so 10996 and
          10996.0 counted as different answers. The official BIRD script
          compares the tuples, where they do not. Our code did not implement
          the semantics its own docstring claims. This one is a bug and is
          fixed in place; it moved exactly one record of 1152.

float     AVG(x)/100 and AVG(x/100) are the same quantity and differ in the
          last bit. BIRD compares exactly too, so this is not a deviation from
          the benchmark, but an answer wrong in the fifteenth significant digit
          is not a wrong answer. Tolerance is 1e-9 relative, which is tight
          enough to still fail SUM(cost_cents)/100 against /100.0: integer
          division loses the cents, and that is a real mistake.

columns+  The model returned every column the gold returns, same rows, plus
          others: SELECT * where the gold selects the name. Everything asked
          for is present and correct and no false claim is added, so no
          per-task judgement is needed for this direction.

columns-  The gold of some tasks returns a column its question never asks for.
          "Which customers hold more than two accounts?" is answered by a list
          of customers; the gold also returns the count, so a model that
          answered the question scored zero. This direction does need
          judgement, because here something is missing rather than added, and
          whether it was asked for depends on the wording. ASKED below records
          that judgement per wording, not per task: wording 1 of the same task
          usually does ask for the count ("and how many each holds"), and
          there the relaxation does not apply.

The two column defects are authoring faults of set 1, not code faults. They
cannot be repaired without breaking the freeze and the pre-registration, so
they are reported, and the authoring rules for set 2 gain one line: the gold's
select list must hold exactly what the question asks for.
"""
from __future__ import annotations

import itertools
import json
import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nl2sql_app.bench.stats import (  # noqa: E402
    bootstrap_mean_clustered,
    paired_difference_clustered,
)

RES = ROOT / "results"
DATA = ROOT / "data" / "holdout"
MODELS = ["qwen25-coder-14b", "qwen25-coder-7b", "arctic-7b-q4", "arctic-7b-q8",
          "xiyan-7b-q4", "xiyan-14b-q4"]

# (task, wording) -> the gold columns that wording actually asks for. Only
# wordings that ask for less than the gold returns appear here. Wording index
# is shared across languages: idx 0 in Russian is the translation of idx 0 in
# English, so the judgement is made once per pair.
#
# Read off the wordings one at a time. Two deliberate exclusions:
#   mfg-007 "How many distinct parts are measured in each unit?" needs both the
#     unit and the count, so it is not here at all, although models failed it
#     in the same mechanical shape by returning the count without the unit.
#   hr-003 wording 1 "the salary in force today, in whole units" mentions the
#     unit of the amount, which only matters if the amount is shown, so only
#     wording 0 ("Who are the five highest paid people") is relaxed.
ASKED: dict[tuple[str, int], tuple[int, ...]] = {
    ("banking/bank-004", 0): (0,),        # "...used most often, by name?"
    ("banking/bank-008", 0): (0,),        # "Which customers hold more than two accounts?"
    ("hr/hr-003", 0): (0,),               # "Who are the five highest paid people...?"
    ("hr/hr-006", 0): (0,),               # "Which five managers have the most direct reports?"
    ("hr/hr-006", 1): (0,),               # "Name the top five people by..."
    ("hr/hr-008", 0): (0,),               # "Which currencies are more than two people paid in?"
    ("logistics/log-002", 0): (0, 1),     # "Which five origin and destination pairs...?"
    ("logistics/log-002", 1): (0, 1),     # "...the place it left from and the place it was going to"
    ("logistics/log-008", 0): (0,),       # "Which shipments travelled more than 3000 km?"
    ("manufacturing/mfg-008", 0): (0,),   # "Which parts have more than ten defects?"
    ("medicine/med-008", 0): (0,),        # "Which patients were admitted more than twice?"
    ("public_services/gov-008", 0): (0,),  # "Which people have submitted more than two cases?"
}


def rows(db: Path, sql: str) -> list[tuple] | None:
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()
    except Exception:
        return None


def numbers_close(a: list[tuple], b: list[tuple], rel: float = 1e-9) -> bool:
    if len(a) != len(b):
        return False
    for ra, rb in zip(sorted(a, key=repr), sorted(b, key=repr), strict=True):
        if len(ra) != len(rb):
            return False
        for x, y in zip(ra, rb, strict=True):
            numeric = (isinstance(x, (int, float)) and isinstance(y, (int, float))
                       and not isinstance(x, bool) and not isinstance(y, bool))
            if numeric:
                if not math.isclose(float(x), float(y), rel_tol=rel, abs_tol=1e-9):
                    return False
            elif x != y:
                return False
    return True


def appears_in(target: set[tuple], wide: list[tuple]) -> bool:
    """Is `target` one of the column projections of `wide`, as a set of rows?"""
    if not wide or not target:
        return False
    k = len(next(iter(target)))
    if k > len(wide[0]):
        return False
    return any({tuple(r[c] for c in cols) for r in wide} == target
               for cols in itertools.combinations(range(len(wide[0])), k))


def reclassify(rec: dict) -> tuple[bool, str | None]:
    """(correct after relaxation, which relaxation) for one result record."""
    if rec["correct"]:
        return True, None
    if not rec["pred_sql"]:
        return False, None
    db = DATA / rec["db_id"] / f"{rec['db_id']}.sqlite"
    gold, pred = rows(db, rec["gold_sql"]), rows(db, rec["pred_sql"])
    if gold is None or pred is None:
        return False, None
    if set(pred) == set(gold):
        return True, "repr"
    if numbers_close(pred, gold):
        return True, "float"
    # An empty result on either side has no columns to compare, and an empty
    # answer to a question with rows in it is simply wrong.
    if not pred or not gold:
        return False, None
    if len(pred[0]) > len(gold[0]) and appears_in(set(gold), pred):
        return True, "columns+"
    cols = ASKED.get((rec["task"], rec["wording"]))
    if cols and appears_in({tuple(r[c] for c in cols) for r in gold}, pred):
        return True, "columns-"
    return False, None


def grouped(recs: list[dict], field: str) -> list[list[float]]:
    by: dict[str, list[float]] = {}
    for r in recs:
        by.setdefault(r["task"], []).append(float(r[field]))
    return [by[t] for t in sorted(by)]


def main() -> int:
    counts: dict[str, int] = {}
    runs: dict[tuple[str, str], list[dict]] = {}
    print(f"{'модель':<18}{'яз':<4}{'EX предрег.':>12}{'EX ослабл.':>12}"
          f"{'интервал ослабл.':>22}   поправлено")
    for m in MODELS:
        for lang in ("en", "ru"):
            f = RES / f"{m}.holdout-{lang}.jsonl"
            recs = [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines()
                    if ln.strip()]
            local: dict[str, int] = {}
            for r in recs:
                ok, why = reclassify(r)
                r["relaxed"] = ok
                if why:
                    local[why] = local.get(why, 0) + 1
                    counts[why] = counts.get(why, 0) + 1
            runs[(m, lang)] = recs
            base = sum(r["correct"] for r in recs) / len(recs)
            rel = sum(r["relaxed"] for r in recs) / len(recs)
            ci = bootstrap_mean_clustered(grouped(recs, "relaxed"))
            note = ", ".join(f"{k}:{v}" for k, v in sorted(local.items())) or "нет"
            print(f"{m:<18}{lang:<4}{base:>12.3f}{rel:>12.3f}"
                  f"{f'[{ci.low:.3f}, {ci.high:.3f}]':>22}   {note}")

    print()
    for m in MODELS:
        g = paired_difference_clustered(grouped(runs[(m, "en")], "relaxed"),
                                        grouped(runs[(m, "ru")], "relaxed"))
        verdict = ("выполнен" if g.low > 0.10 or g.high < -0.10 else
                   "НЕ выполнен" if g.high < 0.10 and g.low > -0.10 else "не определён")
        print(f"{m:<18} разрыв en-ru {g.point * 100:+.1f} пп "
              f"[{g.low * 100:+.1f}, {g.high * 100:+.1f}]  П3а {verdict}")

    total = sum(counts.values())
    n = sum(len(v) for v in runs.values())
    print(f"\nложных срабатываний: {total} из {n} записей ({total / n:.1%})")
    for k, v in sorted(counts.items()):
        print(f"  {k:<10} {v}")
    print("\nЭто нижняя граница. Разбор нашёл ещё один вид расхождения, который "
          "здесь не учтён:\nответ той же ширины с другим составом столбцов, "
          "например (id, имя) против (имя, счёт).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
