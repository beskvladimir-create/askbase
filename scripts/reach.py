#!/usr/bin/env python3
"""How many people reached the product, without a single tracker.

    python scripts/reach.py

The site promises, in its own words, no cookies, no analytics, no tracking
pixel, no third-party script and no usage counter, and the privacy page says
every statement on it is one you can check in the source. Installing a counter
to answer "how many downloads" would make that page false, which is a worse
trade than not knowing.

Nothing has to be installed, because the numbers already exist on the other
side of the link. GitHub counts a release asset download when it serves it,
and counts views and clones of a repository for its owner. Those are facts of
the distribution channel, recorded by the party that does the distributing,
and reading them adds nothing to what a visitor's browser does.

What this cannot tell you, and no honest counter on this site could: how many
people opened the application after downloading it, whether they connected a
database, and whether the answer was any good. The application sends nothing,
so that is not measured and is not going to be. The way to learn it is to ask
the people who wrote in, which is a smaller number and a better one.

Needs the `gh` command, authenticated as the repository's owner: the traffic
figures are owner-only.
"""
from __future__ import annotations

import json
import subprocess
import sys

REPO = "beskvladimir-create/askbase"


def api(path: str):
    out = subprocess.run(["gh", "api", f"repos/{REPO}/{path}"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    releases = api("releases")
    if releases is None:
        print("не удалось прочитать GitHub. Нужен gh, авторизованный "
              "владельцем репозитория.", file=sys.stderr)
        return 1

    print(f"=== {REPO} ===\n")
    print("Скачивания сборок, счёт ведёт GitHub при выдаче файла")
    total = 0
    for r in releases:
        assets = r.get("assets") or []
        if not assets:
            print(f"  {r['tag_name']:10s} {r['published_at'][:10]}  "
                  "файлов нет")
            continue
        for a in assets:
            total += a["download_count"]
            print(f"  {r['tag_name']:10s} {r['published_at'][:10]}  "
                  f"{a['name']:36s} {a['download_count']:5d}")
    print(f"  {'':10s} {'':10s}  {'всего':36s} {total:5d}")

    for name, title, key in (("views", "Просмотры репозитория за 14 дней",
                              "views"),
                             ("clones", "Клоны за 14 дней", "clones")):
        data = api(f"traffic/{name}")
        if data is None:
            print(f"\n{title}: нет доступа, нужен токен владельца")
            continue
        print(f"\n{title}: {data['count']} всего, {data['uniques']} уникальных")
        days = [d for d in data.get(key, []) if d["count"]]
        for d in days[-7:]:
            print(f"  {d['timestamp'][:10]}  {d['count']:4d}  "
                  f"({d['uniques']} уник.)")

    paths = api("traffic/popular/paths")
    if paths:
        print("\nЧто смотрели в репозитории")
        for p in paths[:8]:
            print(f"  {p['count']:4d}  {p['path']}")

    print("\nЧего здесь нет и не будет: сколько человек открыли приложение, "
          "подключили базу и получили верный ответ.\nПриложение ничего не "
          "отправляет, поэтому это не измеряется. Это знают только те, кто "
          "написал письмом.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
