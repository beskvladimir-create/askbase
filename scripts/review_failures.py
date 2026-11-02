#!/usr/bin/env python3
"""The mandatory manual review of failures, in two commands.

HOLDOUT.md fixes it before the run: from each run, take a random sample of at
least 20 failures and read them by hand. Classify each as a model error or a
false failure of the evaluator, and publish the proportion. A verdict announced
without this step is a verdict about the evaluator as much as about the model.

That step cannot be automated, which is exactly why it needs a tool: a review
done in a text editor leaves no record of which failures were looked at, and a
sample chosen by eye is not a sample.

    python scripts/review_failures.py prepare results/arctic-7b-q4.holdout-en.jsonl
    # ... read the file it writes, fill in each verdict ...
    python scripts/review_failures.py summarise results/arctic-7b-q4.holdout-en.review.md

`prepare` draws the sample deterministically (seed recorded in the file) and
writes one block per failure with the question, the trap, both queries and both
result sets side by side. `summarise` refuses a file with a blank verdict,
counts the classes and writes the proportion next to the run's summary.

Deliberately file-based rather than interactive. A prompt-and-answer loop
cannot be paused, re-read or revised, and this review is the one place in the
protocol where someone is expected to change their mind halfway through.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 0
MIN_SAMPLE = 20

# Written in the file, parsed back out. Short on purpose: a long vocabulary
# invites a third category for "complicated", and the whole point is to force
# the question "is the model wrong, or is my evaluator wrong".
VERDICTS = {
    "model": "модель ответила неверно",
    "evaluator": "ложное срабатывание проверяльщика: ответ по сути верен",
    "unsure": "не разобрался, нужен ещё один взгляд",
}
BLOCK = re.compile(r"^## (?P<n>\d+)\. (?P<task>\S+) +(?P<lang>\w+)/(?P<wording>\d+)$",
                   re.M)
VERDICT_LINE = re.compile(r"^вердикт:\s*(?P<v>\S*)\s*$", re.M)
NOTE_LINE = re.compile(r"^заметка:\s*(?P<note>.*)$", re.M)
# A verdict line with something on it, used to refuse overwriting a review.
VERDICT_FILLED = re.compile(r"^вердикт:[ \t]*\S", re.M)


def rows_of(db_path: str, sql: str, limit: int = 8) -> str:
    """Run a query and show the first few rows, or the error it raised."""
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = con.execute(sql)
            got = cur.fetchmany(limit)
            more = cur.fetchone() is not None
        finally:
            con.close()
    except Exception as e:                       # the error is the finding
        return f"    ОШИБКА: {type(e).__name__}: {e}"
    if not got:
        return "    (пусто)"
    out = [f"    {r}" for r in got]
    if more:
        out.append(f"    ... и ещё строки (показаны первые {limit})")
    return "\n".join(out)


def load(results: Path) -> list[dict]:
    return [json.loads(ln) for ln in results.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def questions(data_root: Path) -> dict[tuple[str, str, int], str]:
    """Every wording of the set, keyed the way a result record identifies one.

    The run records carry `task`, `lang` and `wording` but not the question
    text: putting it on every record would have duplicated the frozen set into
    the results and given a second, editable copy of the thing under SHA-256.
    So the text is read back from the set here, and a record that points at a
    wording the set does not have is an error rather than a blank line.
    """
    out: dict[tuple[str, str, int], str] = {}
    for tasks_file in sorted(data_root.glob("*/tasks.json")):
        for task in json.loads(tasks_file.read_text(encoding="utf-8")):
            tid = f"{task['domain']}/{task['tid']}"
            for w in task["wordings"]:
                out[(tid, w["lang"], int(w["idx"]))] = w["text"].strip()
    if not out:
        raise SystemExit(f"в {data_root} нет ни одной задачи, набор не на месте")
    return out


def prepare(results: Path, sample: int, seed: int) -> Path:
    records = load(results)
    failures = [r for r in records if not r.get("correct")]
    if not failures:
        raise SystemExit(f"в {results.name} нет провалов, разбирать нечего")

    # The whole population when it is smaller than the sample. Reviewing 14 of
    # 14 is complete, not insufficient; the floor is on the sample, not on how
    # many failures a model is allowed to have.
    take = min(sample, len(failures))
    rng = random.Random(seed)
    chosen = sorted(rng.sample(failures, take),
                    key=lambda r: (r.get("task", ""), r.get("wording", 0)))

    data_root = ROOT / "data" / "holdout"
    # The same check the runner makes. A review read against a set that has
    # moved since the run would classify failures by comparing a prediction
    # with a question nobody was asked.
    from nl2sql_app.holdout.verify import check_set
    check_set(data_root)
    texts = questions(data_root)

    lines = [
        f"# Ручной разбор провалов: {results.name}",
        "",
        f"Провалов всего: {len(failures)} из {len(records)}.",
        f"В выборке: {take}, зерно {seed}, отбор детерминированный.",
        f"Порог протокола: не меньше {MIN_SAMPLE} (или все, если их меньше).",
        "",
        "В каждом блоке заполните строку «вердикт» одним из значений:",
        *[f"  {k:<10} {v}" for k, v in VERDICTS.items()],
        "",
        "Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,",
        "он попадёт в публикуемую долю отдельной категорией, а не растворится.",
        "",
    ]
    for i, r in enumerate(chosen, 1):
        db = data_root / r["db_id"] / f"{r['db_id']}.sqlite"
        key = (r.get("task", ""), r.get("lang", ""), int(r.get("wording", 0)))
        if key not in texts:
            raise SystemExit(
                f"ОТКАЗ: записи и набор не совпадают: {key} нет в наборе. "
                "Прогон сделан по другой версии набора, разбор был бы не о нём."
            )
        lines += [
            "",
            f"## {i}. {r.get('task', '?')} {r.get('lang', '?')}/{r.get('wording', 0)}",
            "",
            f"ловушка: {'; '.join(r.get('traps') or ['(не указана)'])}",
            f"вопрос:  {texts[key]}",
            "",
            "эталон:",
            f"    {r['gold_sql']}",
            rows_of(str(db), r["gold_sql"]),
            "",
            "ответ модели:",
            f"    {r['pred_sql'] or '(пусто)'}",
            rows_of(str(db), r["pred_sql"]) if r["pred_sql"] else "    (запрос пуст)",
            "",
            f"ошибка исполнения: {r.get('error') or 'нет'}",
            "",
            "вердикт: ",
            "заметка: ",
        ]
    # Not with_suffix: the stage is part of the stem, not a suffix, so
    # with_suffix("").with_suffix(".review.md") turned
    # "qwen.holdout-en.jsonl" into "qwen.review.md" and the English and
    # Russian reviews of one model overwrote each other in silence.
    out = Path(str(results).removesuffix(".jsonl") + ".review.md")
    # Never over an answered review. Re-running prepare to check that prepare
    # works overwrote a finished file and threw twenty verdicts away; the
    # sample is deterministic, so the rewrite looked identical apart from the
    # verdicts being gone. Hours of reading sit in these files and nothing
    # else holds them.
    if out.is_file() and VERDICT_FILLED.search(out.read_text(encoding="utf-8")):
        raise SystemExit(
            f"ОТКАЗ: в {out.name} уже есть заполненные вердикты. "
            "Удалите файл сами, если разбор правда надо начать заново."
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def summarise(review: Path) -> dict:
    text = review.read_text(encoding="utf-8")
    blocks = list(BLOCK.finditer(text))
    if not blocks:
        raise SystemExit(f"{review.name}: не нашёл ни одного блока разбора")

    got: list[dict] = []
    blank: list[str] = []
    unknown: list[str] = []
    for i, m in enumerate(blocks):
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(text)
        body = text[m.start():end]
        vm = VERDICT_LINE.search(body)
        verdict = (vm.group("v") if vm else "").strip()
        label = f"{m.group('task')} {m.group('lang')}/{m.group('wording')}"
        if not verdict:
            blank.append(label)
            continue
        if verdict not in VERDICTS:
            unknown.append(f"{label}: {verdict!r}")
            continue
        nm = NOTE_LINE.search(body)
        got.append({"task": m.group("task"), "lang": m.group("lang"),
                    "wording": int(m.group("wording")), "verdict": verdict,
                    "note": (nm.group("note").strip() if nm else "")})

    problems = []
    if blank:
        problems.append(f"без вердикта: {', '.join(blank[:6])}"
                        + (f" и ещё {len(blank) - 6}" if len(blank) > 6 else ""))
    if unknown:
        problems.append(f"неизвестный вердикт: {', '.join(unknown[:6])}")
    if problems:
        # Refuses rather than counts what is filled in. A review that is
        # half done and reported as a proportion is worse than no review: the
        # share would be computed over the easy cases.
        raise SystemExit("ОТКАЗ: разбор не закончен.\n  " + "\n  ".join(problems))

    counts = {k: sum(1 for g in got if g["verdict"] == k) for k in VERDICTS}
    n = len(got)
    out = {
        "review_file": (str(review.relative_to(ROOT)) if review.is_relative_to(ROOT)
                        else str(review)),
        "reviewed": n,
        "counts": counts,
        "false_alarm_share": round(counts["evaluator"] / n, 4) if n else None,
        "unsure_share": round(counts["unsure"] / n, 4) if n else None,
        "meets_protocol_minimum": n >= MIN_SAMPLE,
        "items": got,
    }
    dest = Path(str(review).removesuffix(".review.md") + ".review.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="выбрать провалы и записать файл для разбора")
    p.add_argument("results", type=Path)
    p.add_argument("--sample", type=int, default=MIN_SAMPLE)
    p.add_argument("--seed", type=int, default=SEED)
    s = sub.add_parser("summarise", help="посчитать доли по заполненному файлу")
    s.add_argument("review", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "prepare":
        if args.sample < MIN_SAMPLE:
            raise SystemExit(
                f"ОТКАЗ: протокол требует не меньше {MIN_SAMPLE} провалов в выборке, "
                f"запрошено {args.sample}"
            )
        out = prepare(args.results, args.sample, args.seed)
        print(f"файл для разбора: {out}")
        print("заполните строки «вердикт» и запустите summarise")
        return 0

    out = summarise(args.review)
    print(f"разобрано: {out['reviewed']}")
    for k, v in out["counts"].items():
        print(f"  {k:<10} {v}")
    print(f"доля ложных срабатываний проверяльщика: {out['false_alarm_share']:.1%}")
    if out["unsure_share"]:
        print(f"доля неразобранных: {out['unsure_share']:.1%}")
    if not out["meets_protocol_minimum"]:
        print(f"ВНИМАНИЕ: разобрано меньше {MIN_SAMPLE}, порог протокола не выполнен")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
