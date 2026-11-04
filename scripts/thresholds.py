#!/usr/bin/env python3
"""Вердикты по порогам П1, П3, П3а, П5 и П6 на отложенном наборе 2.

Правило взято из HOLDOUT.md и не выбиралось после просмотра чисел: перцентильный
бутстрап, 2000 повторов, уровень 95%, «выполнено» только если весь интервал по
нужную сторону порога, «не выполнено» только если весь интервал по другую,
иначе «не определено». Точечная оценка в решение не входит. Вердикт, который
меняется между зёрнами 0 и 5, записывается как «не определено».

Единица ресэмплинга это задача, а не формулировка: четыре формулировки одной
задачи делят схему и эталонный запрос, и бутстрап по 1152 формулировкам дал бы
интервал примерно в полтора раза уже заслуженного. Поэтому здесь зовутся
кластерные функции из `nl2sql_app.bench.stats`, а не их обычные версии, и
правило вердикта тоже берётся оттуда: вторая реализация того же правила рано
или поздно разойдётся с первой.

    python scripts/thresholds.py            # напечатать
    python scripts/thresholds.py --write    # и записать сводку для сайта

Сводка нужна, потому что страница рейтинга печатает вердикты, а сборщик сайта
отказывается публиковать число, под которым нет файла в results/. Без неё
интервал по П1 пришлось бы набрать на странице руками, то есть ровно так, как
этот проект публиковать числа не разрешает.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nl2sql_app.bench.stats import (  # noqa: E402
    bootstrap_mean_clustered,
    bootstrap_quantile_clustered,
    paired_difference_clustered,
    verdict,
)

RES = ROOT / "results"
SEEDS = (0, 5)
OURS = "qwen25-coder-14b"
PARTICIPANTS = ("arctic-7b-q4", "arctic-7b-q8", "qwen25-coder-7b",
                "qwen25-coder-14b", "xiyan-7b-q4", "xiyan-14b-q4")
OUTCOMES = {"met": "выполнено", "not_met": "не выполнено",
            "undetermined": "не определено"}
# Что уходит в сводку: ключ в results/thresholds.set2.summary.json, под
# которым страница его и читает.
RECORD: dict[str, dict] = {}


def by_task(model: str, stage: str) -> dict[str, list[dict]]:
    path = RES / f"{model}.{stage}.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            out.setdefault(r["task"], []).append(r)
    return out


def scores(groups: dict[str, list[dict]], keys: list[str]) -> list[list[float]]:
    return [[float(bool(r["correct"])) for r in groups[t]] for t in keys]


def agreements(groups: dict[str, list[dict]]) -> list[list[float]]:
    """Доля согласившихся пар формулировок внутри задачи, по одному числу на задачу."""
    out = []
    for g in groups.values():
        v = [bool(r["correct"]) for r in g]
        pairs = [(v[i], v[j]) for i in range(len(v)) for j in range(i + 1, len(v))]
        if pairs:
            out.append([float(a == b) for a, b in pairs])
    return out


def say(title: str, intervals: list, bound: float, direction: str,
        scale: float = 1.0, unit: str = "пп", key: str | None = None) -> None:
    outs = [verdict(title, i, bound / scale, direction=direction).outcome
            for i in intervals]
    stable = len(set(outs)) == 1
    v = OUTCOMES[outs[0]] if stable else "не определено (расходится по зерну)"
    i = intervals[0]
    if key:
        RECORD[key] = {
            "point": round(i.point * scale, 2),
            "low": round(i.low * scale, 2),
            "high": round(i.high * scale, 2),
            "bound": round(bound, 2),
            "direction": direction,
            "tasks": i.n,
            "outcome": outs[0] if stable else "undetermined",
            "stable_across_seeds": stable,
            "verdict": v,
        }
    print(f"{title}\n"
          f"    точка {i.point * scale:.2f} {unit}, "
          f"интервал [{i.low * scale:.2f}, {i.high * scale:.2f}] при зерне 0, "
          f"задач {i.n}\n"
          f"    порог {bound:.2f} {unit} ({'не ниже' if direction == 'at_least' else 'не выше'})"
          f"\n    вердикт: {v}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="вердикты по порогам на наборе 2")
    ap.add_argument("--write", action="store_true",
                    help="записать results/thresholds.set2.summary.json")
    args = ap.parse_args(argv)

    print("Пороги на отложенном наборе 2, правило из HOLDOUT.md\n")

    # П1. Наше решение против лучшей доступной одиночной модели под тем же
    # протоколом. «Лучшая» берётся по точечной оценке на голой стадии: выбирать
    # соперника по интервалу сравнения значит выбирать его по ответу.
    for lang in ("en", "ru"):
        ours = by_task(OURS, f"set2-app-{lang}")
        best, best_ex = None, -1.0
        for m in PARTICIPANTS:
            g = by_task(m, f"set2-base-{lang}")
            if not g:
                continue
            flat = [bool(r["correct"]) for v in g.values() for r in v]
            e = sum(flat) / len(flat)
            if e > best_ex:
                best, best_ex = m, e
        rival = by_task(best, f"set2-base-{lang}")
        keys = sorted(set(ours) & set(rival))
        say(f"П1 ({lang}): наше решение против лучшей одиночной модели, "
            f"{best} на голой стадии {best_ex:.1%}",
            [paired_difference_clustered(scores(ours, keys), scores(rival, keys), seed=s)
             for s in SEEDS], 0.0, "at_least", 100.0, key=f"p1_{lang}")

    # П3. Шаг 3 плана прогона, закрытые модели по API, на этом наборе не
    # выполнялся, поэтому сравнивать не с чем. Это отсутствие точки отсчёта,
    # а не интервал, пересёкший порог, и записывается оно отдельно.
    print("П3 (en): наше решение против лучшей закрытой модели\n"
          "    не измерен: на наборе 2 не прогонялась ни одна закрытая модель.\n"
          "    Точки отсчёта нет, поэтому вердикт не выносится вовсе, а не\n"
          "    выносится как «не определено».\n")

    # П3а. Русский не ниже английского больше чем на 10 пунктов, парно.
    en, ru = by_task(OURS, "set2-app-en"), by_task(OURS, "set2-app-ru")
    keys = sorted(set(en) & set(ru))
    say("П3а: русский против английского, поставляемый промпт",
        [paired_difference_clustered(scores(ru, keys), scores(en, keys), seed=s)
         for s in SEEDS], -10.0, "at_least", 100.0, key="p3a")

    # П5 и П6 по каждому плечу нашего движка. Голые стадии печатаются рядом,
    # потому что порог записан на продукт, а не на веса, и разницу видно только
    # когда обе строки стоят вместе.
    for stage in ("set2-app-en", "set2-app-ru", "set2-base-en", "set2-base-ru"):
        groups = by_task(OURS, stage)
        if not groups:
            continue
        lat = [[r["seconds"] for r in g] for g in groups.values()]
        say(f"П5 ({stage}): p95 задержки",
            [bootstrap_quantile_clustered(lat, 0.95, seed=s) for s in SEEDS],
            20.0, "at_most", 1.0, "с", key=f"p5_{stage.replace('-', '_')}")
        say(f"П6 ({stage}): согласие формулировок",
            [bootstrap_mean_clustered(agreements(groups), seed=s) for s in SEEDS],
            80.0, "at_least", 100.0, "%", key=f"p6_{stage.replace('-', '_')}")

    # Решение о поставке, записанное до прогона: порядок таблиц уходит в
    # продукт только если парный интервал против `set2-app` исключает ноль с
    # положительной стороны на обоих языках. Один язык этого не делает, и
    # точка с интервалом через ноль тоже.
    print("Решение о поставке: порядок таблиц против поставляемого промпта\n")
    for lang in ("en", "ru"):
        a, b = by_task(OURS, f"set2-app-ord-{lang}"), by_task(OURS, f"set2-app-{lang}")
        if not a or not b:
            continue
        keys = sorted(set(a) & set(b))
        say(f"set2-app-ord против set2-app ({lang})",
            [paired_difference_clustered(scores(a, keys), scores(b, keys), seed=s)
             for s in SEEDS], 0.0, "at_least", 100.0, key=f"ord_{lang}")

    # П3 попадает в сводку как отсутствие измерения, а не как широкий
    # интервал, чтобы страница не могла напечатать его как «не определено».
    RECORD["p3_en"] = {"outcome": "not_measured",
                       "verdict": "не измерен: закрытых моделей на наборе 2 не было"}
    if args.write:
        dest = RES / "thresholds.set2.summary.json"
        dest.write_text(json.dumps(RECORD, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"записано: {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
