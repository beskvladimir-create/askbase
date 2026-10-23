#!/usr/bin/env python3
"""Build the Askbase site from page bodies, and refuse to publish unbacked numbers.

    python scripts/build_site.py            # build
    python scripts/build_site.py --check    # verify only, write nothing

Pages live in site/pages/<name>.html. The first line carries metadata in an
HTML comment, the rest is the body. The builder wraps the body in the shared
nav and footer, adds schema.org and hreflang, and writes site/<path>/index.html.

The point of this script, beyond assembly, is the number guard. Every figure
that comes from our own measurements is written in a page as a reference, for
example {=xiyan-7b-q4|holdout:en|ex}, and resolved from results/. A reference
with no backing file is a hard error and the build stops.

That rule exists because the alternative has a known failure mode: a number
typed into a page by hand, correct on the day it was typed, silently wrong
after the next run. The house style forbids unverified claims, and this makes
the prohibition mechanical rather than a matter of discipline. A figure quoted
from somebody else's paper or model card is not a reference: it is prose, and it
carries its source link inline.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PAGES = SITE / "pages"
RESULTS = ROOT / "results"
# GitHub Pages serves a project repository under /<repo>/, so every root
# relative link needs that prefix. Set both when deploying there; leave them
# empty for a custom domain, where the site sits at the root.
BASE = os.environ.get("SITE_BASE", "https://askbase.besk.tech")
PREFIX = os.environ.get("SITE_PREFIX", "").rstrip("/")

# Primary language is English (decision of 20.10.2026); Russian lives under /ru/.
PRIMARY_LANG = "en"

@dataclass(frozen=True)
class Route:
    path: str      # published path, without leading or trailing slash
    lang: str
    title: str
    desc: str
    twin: str      # the same page in the other language, by ROUTES key
    signed: bool = True   # running text under his name carries the article byline


# Russian pages keep Russian slugs, which is the point of having them: a
# transliterated path is what people search for. That means the two languages do
# not share a path, so hreflang cannot be derived by prefixing "ru/" and the
# pairing is declared here instead. Getting this wrong points every alternate
# link at a page that does not exist.
ROUTES: dict[str, Route] = {
    "index": Route(
        "", "en",
        "Askbase: ask your database in plain words",
        "A desktop application that answers questions about your own database. "
        "The model runs on your machine, so the question and the data never leave it.",
        twin="ru-index", signed=False,
    ),
    "ru-index": Route(
        "ru", "ru",
        "Askbase: спросите свою базу обычными словами",
        "Настольное приложение, которое отвечает на вопросы к вашей базе данных. "
        "Модель работает на вашем компьютере, вопрос и данные его не покидают.",
        twin="index", signed=False,
    ),
    "model-ranking": Route(
        "model-ranking", "en",
        "Askbase: open model ranking",
        "Open text-to-SQL models measured under one protocol, published before the run.",
        twin="ru-reyting",
    ),
    "ru-reyting": Route(
        "ru/reyting-modeley", "ru",
        "Askbase: открытый рейтинг моделей",
        "Открытые модели text-to-SQL, измеренные по одному протоколу, опубликованному до прогона.",
        twin="model-ranking",
    ),
    "read-only-access": Route(
        "read-only-access", "en",
        "Askbase: read-only access",
        "What Askbase runs against your database, and the SQL to create a role that cannot do anything else.",
        twin="ru-dostup", signed=False,
    ),
    "ru-dostup": Route(
        "ru/dostup-tolko-chtenie", "ru",
        "Askbase: доступ только на чтение",
        "Что Askbase выполняет в вашей базе и готовый SQL для роли, которая больше ничего не умеет.",
        twin="read-only-access", signed=False,
    ),
    "notfound": Route(
        "404", "en", "Askbase: page not found",
        "This page is not here.", twin="ru-notfound", signed=False,
    ),
    "ru-notfound": Route(
        "ru/404", "ru", "Askbase: страница не найдена",
        "Этой страницы здесь нет.", twin="notfound", signed=False,
    ),
    "comparison": Route(
        "comparison", "en",
        "Askbase: how it compares",
        "What the existing text-to-SQL tools do, under which licence, and where the model runs.",
        twin="ru-sravnenie",
    ),
    "where-your-data-goes": Route(
        "where-your-data-goes", "en",
        "Askbase: where your data goes",
        "Which products process your schema and questions off your machine, and which do not.",
        twin="ru-kuda-uhodyat-dannye",
    ),
    "author": Route(
        "author", "en",
        "Askbase: author",
        "Vladimir Beskorovainyi, Besk Tech. Publications and benchmarks.",
        twin="ru-avtor",
    ),
    "ru-sravnenie": Route(
        "ru/sravnenie", "ru",
        "Askbase: сравнение",
        "Что умеют существующие инструменты text-to-SQL, под какой лицензией и где работает модель.",
        twin="comparison",
    ),
    "ru-kuda-uhodyat-dannye": Route(
        "ru/kuda-uhodyat-dannye", "ru",
        "Askbase: куда уходят данные",
        "Какие продукты обрабатывают вашу схему и вопросы вне вашей машины, а какие нет.",
        twin="where-your-data-goes",
    ),
    "ru-avtor": Route(
        "ru/avtor", "ru",
        "Askbase: автор",
        "Владимир Бескоровайный, Besk Tech. Публикации и бенчмарки.",
        twin="author",
    ),
}

# Pages that may not be built until our own measurements exist. Listed rather
# than silently missing, so that "the ranking page is not written yet" is a
# visible fact and not an oversight.
BLOCKED: dict[str, str] = {}

REF = re.compile(r"\{=([^|}]+)\|([^|}]+)\|([^}]+)\}")
# A page may be published before the run that fills it. The region marked
# data-when="results" is kept only when every reference inside it resolves;
# otherwise it is dropped and the data-when="pending" region is shown instead.
# Partial data is treated as missing: half a results table is worse than none,
# because a reader cannot tell which half is real.
REGION = re.compile(
    r'<(\w+)[^>]*\sdata-when="(results|pending)"[^>]*>(.*?)</\1>', re.S)


class Unbacked(Exception):
    """A page quotes one of our numbers that no results file provides."""


def load_results() -> dict:
    """Every summary under results/, keyed by its file stem."""
    out = {}
    for path in sorted(RESULTS.rglob("*.summary.json")):
        try:
            out[path.stem.replace(".summary", "")] = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise Unbacked(f"{path}: нечитаемый JSON: {e}") from e
    return out


def split_regions(body: str, results: dict) -> tuple[str, bool]:
    """Keep the results region or the pending one. Returns (body, filled)."""
    regions = {m.group(2): m for m in REGION.finditer(body)}
    if "results" not in regions and "pending" not in regions:
        return body, True
    if "results" not in regions or "pending" not in regions:
        raise Unbacked("регионы data-when должны идти парой: results и pending")

    filled = all(
        (results.get(f"{m.group(1).strip()}.{m.group(2).strip()}") or {}).get(m.group(3).strip()) is not None
        for m in REF.finditer(regions["results"].group(3))
    ) and REF.search(regions["results"].group(3)) is not None

    drop = regions["pending" if filled else "results"]
    body = body[: drop.start()] + body[drop.end():]
    return body, filled


def resolve(body: str, results: dict, page: str) -> str:
    """Replace every {=model|set|metric} with its measured value, or fail."""
    missing: list[str] = []

    def one(m: re.Match) -> str:
        model, dataset, metric = (g.strip() for g in m.groups())
        key = f"{model}.{dataset}"
        summary = results.get(key)
        if summary is None or metric not in summary:
            missing.append(f"{{={model}|{dataset}|{metric}}}")
            return m.group(0)
        value = summary[metric]
        if metric.startswith("ex") and isinstance(value, (int, float)):
            return f"{value * 100:.1f}"
        return str(value)

    text = REF.sub(one, body)
    if missing:
        raise Unbacked(
            f"{page}: в странице есть числа без подтверждения в results/: "
            + ", ".join(sorted(set(missing)))
        )
    return text


def url_of(route: "Route") -> str:
    """Site path for a route, with the leading and trailing slash.

    The home page has an empty path, and naive f"/{path}/" turns that into
    "//", which a browser reads as a protocol relative URL to another host.
    """
    return f"/{route.path}/" if route.path else "/"


def head(route: Route) -> str:
    path, lang, title, desc = route.path, route.lang, route.title, route.desc
    url = f"{BASE}/{path}/" if path else f"{BASE}/"
    twin = ROUTES[route.twin]
    alt = twin.path
    other_lang = twin.lang
    # x-default points at the primary language, which is English.
    default = path if lang == PRIMARY_LANG else alt
    schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "description": desc,
        "inLanguage": lang,
        "url": url,
        "isPartOf": {"@type": "WebSite", "name": "Askbase", "url": f"{BASE}/"},
    }
    locale = "ru_RU" if lang == "ru" else "en_GB"
    card = "og-ru.png" if lang == "ru" else "og.png"
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<script>document.documentElement.classList.add("js")</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="{lang}" href="{url}">
<link rel="alternate" hreflang="{other_lang}" href="{BASE}/{alt}/">
<link rel="alternate" hreflang="x-default" href="{BASE}/{default}/">
<link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Askbase">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{locale}">
<meta property="og:image" content="{BASE}/assets/{card}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/fonts.css">
<link rel="stylesheet" href="/assets/style.css">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
</head>
<body>
"""


# The article byline from the house style, used verbatim on signed running text.
# Two bylines exist and a third is never invented; this is the article one.
BYLINE = {
    "en": (
        '<div class="byline"><span>Vladimir Beskorovainyi, Enterprise AI Architect &amp; CTO, '
        'author of the Amazon bestseller &ldquo;Enterprise AI: The KATA Way&rdquo;, '
        'founder of Besk Tech (<a href="https://besk.tech">besk.tech</a>)</span></div>'
    ),
    "ru": (
        '<div class="byline"><span>Владимир Бескоровайный, архитектор корпоративного ИИ и CTO, '
        'автор бестселлера Amazon &laquo;Enterprise AI: The KATA Way&raquo;, '
        'основатель Besk Tech (<a href="https://besk.tech">besk.tech</a>)</span></div>'
    ),
}

# The hero demo, one block per language so the two never drift apart. The SQL is
# the same in both: it is the product's output, not copy.
_SQL = (
    "<span class=\"ln\"><span class=\"kw\">SELECT</span> r.name, <span class=\"kw\">COUNT</span>(*) <span class=\"kw\">AS</span> n</span><span class=\"ln\"><span class=\"kw\">FROM</span> clients c</span><span class=\"ln\"><span class=\"kw\">JOIN</span> regions r <span class=\"kw\">ON</span> r.id = c.region_id</span><span class=\"ln\"><span class=\"kw\">WHERE</span> c.dt_reg &gt;= '2026-09-01'</span><span class=\"ln\">  <span class=\"kw\">AND</span> c.dt_reg &lt;  '2026-10-01'</span><span class=\"ln\"><span class=\"kw\">GROUP BY</span> r.name <span class=\"lim\">LIMIT 1000</span></span>"
)

_ROWS = (
    "<tr><td>Manchester</td><td class=\"num\">412</td></tr><tr><td>Leeds</td><td class=\"num\">188</td></tr><tr><td>Bristol</td><td class=\"num\">94</td></tr><tr><td>Cardiff</td><td class=\"num\">71</td></tr>"
)

_LOCK = ('<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">'
         '<rect x="4" y="10" width="16" height="10" rx="2.5" stroke="currentColor" stroke-width="1.5"/>'
         '<path d="M8 10V7.5a4 4 0 0 1 8 0V10" stroke="currentColor" stroke-width="1.5"/></svg>')

def _ask(lang: str) -> str:
    """The hero demo: three steps shown one at a time in a fixed frame."""
    w = {
        "en": dict(
            aria="How Askbase answers a question",
            db="<span class=\"pre\">connected to </span><b>analytics</b> &middot; read-only",
            steps=("Question", "Query", "Answer"),
            q="How many new customers came from each region in September?",
            th=("Region", "Customers"),
            said="<b>What it counted.</b> Customers whose registration date falls in "
                 "September 2026, grouped by region. Customers with no region are not in the answer.",
            foot="Model and data stay on this computer",
            play="PLAY", stop="PAUSE",
        ),
        "ru": dict(
            aria="Как Askbase отвечает на вопрос",
            db="<span class=\"pre\">база </span><b>analytics</b> &middot; только чтение",
            steps=("Вопрос", "Запрос", "Ответ"),
            q="Сколько новых клиентов пришло из каждого региона в сентябре?",
            th=("Регион", "Клиентов"),
            said="<b>Что посчитано.</b> Клиенты с датой регистрации в сентябре 2026 года, "
                 "с группировкой по региону. Клиенты без региона в ответ не попали.",
            foot="Модель и данные остаются на этом компьютере",
            play="ПУСК", stop="ПАУЗА",
        ),
    }[lang]
    rail = "".join(
        f'<button type="button" data-step="{i}"{" aria-current=\"step\"" if i == 0 else ""}>'
        f'<span class="t"></span><span class="s">{i + 1}. {name}</span></button>'
        for i, name in enumerate(w["steps"])
    )
    return f"""<figure class="ask" tabindex="0" aria-label="{w['aria']}">
  <div class="chrome"><span class="dot"></span>Askbase<span class="db">{w['db']}</span></div>
  <div class="rail">{rail}</div>
  <div class="panes">
    <div class="pane" data-on>
      <p class="plabel">{w['steps'][0]}</p>
      <p class="q"><span class="text" data-q="{w['q']}">{w['q']}</span><span class="caret"></span></p>
    </div>
    <div class="pane">
      <p class="plabel">{w['steps'][1]}</p>
      <pre class="sql">{_SQL}</pre>
    </div>
    <div class="pane">
      <p class="plabel">{w['steps'][2]}</p>
      <table><thead><tr><th>{w['th'][0]}</th><th class="num">{w['th'][1]}</th></tr></thead>
      <tbody>{_ROWS}</tbody></table>
      <p class="said">{w['said']}</p>
    </div>
  </div>
  <figcaption class="bar">{_LOCK}<span>{w['foot']}</span>
    <button class="pause" type="button" aria-pressed="false" data-play="{w['play']}" data-stop="{w['stop']}">{w['stop']}</button>
  </figcaption>
</figure>"""


ASK = {"en": _ask("en"), "ru": _ask("ru")}


# Nav and footer are built per language so that every link inside a language
# stays inside it. A visitor who lands on a Russian page and clicks through
# should not silently end up reading English.
NAV = {
    "en": """<nav class="nav" aria-label="Main navigation">
  <a class="brand" href="/" aria-label="Askbase, home">
    <svg viewBox="0 0 28 28" fill="none" aria-hidden="true"><rect x="2.75" y="2.75" width="22.5" height="22.5" rx="6.5" stroke="#fff" stroke-opacity=".42" stroke-width="1.5"/><path d="M8 10.5h8.4" stroke="#fff" stroke-width="1.9" stroke-linecap="round"/><path d="M8 14.5h12" stroke="#fff" stroke-opacity=".72" stroke-width="1.9" stroke-linecap="round"/><path d="M8 18.5h5.6" stroke="#fff" stroke-opacity=".42" stroke-width="1.9" stroke-linecap="round"/><rect x="18.7" y="8.7" width="1.7" height="3.6" rx=".85" fill="#fff"/></svg>
    Askbase</a>
  <ul>
    <li><a href="/model-ranking/">Ranking</a></li>
    <li><a href="/comparison/">Comparison</a></li>
    <li><a href="/where-your-data-goes/">Your data</a></li>
    <li><a href="/read-only-access/">Read-only</a></li>
    <li><a href="/author/">Author</a></li>
  </ul>
  <div class="lang" role="group" aria-label="Language">
    <a href="{self}" aria-current="true" hreflang="en" lang="en">EN</a>
    <span aria-hidden="true">/</span>
    <a href="{twin}" hreflang="ru" lang="ru">RU</a>
  </div>
</nav>
""",
    "ru": """<nav class="nav" aria-label="Основная навигация">
  <a class="brand" href="/ru/" aria-label="Askbase, на главную">
    <svg viewBox="0 0 28 28" fill="none" aria-hidden="true"><rect x="2.75" y="2.75" width="22.5" height="22.5" rx="6.5" stroke="#fff" stroke-opacity=".42" stroke-width="1.5"/><path d="M8 10.5h8.4" stroke="#fff" stroke-width="1.9" stroke-linecap="round"/><path d="M8 14.5h12" stroke="#fff" stroke-opacity=".72" stroke-width="1.9" stroke-linecap="round"/><path d="M8 18.5h5.6" stroke="#fff" stroke-opacity=".42" stroke-width="1.9" stroke-linecap="round"/><rect x="18.7" y="8.7" width="1.7" height="3.6" rx=".85" fill="#fff"/></svg>
    Askbase</a>
  <ul>
    <li><a href="/ru/reyting-modeley/">Рейтинг</a></li>
    <li><a href="/ru/sravnenie/">Сравнение</a></li>
    <li><a href="/ru/kuda-uhodyat-dannye/">Ваши данные</a></li>
    <li><a href="/ru/dostup-tolko-chtenie/">Только чтение</a></li>
    <li><a href="/ru/avtor/">Автор</a></li>
  </ul>
  <div class="lang" role="group" aria-label="Язык">
    <a href="{twin}" hreflang="en" lang="en">EN</a>
    <span aria-hidden="true">/</span>
    <a href="{self}" aria-current="true" hreflang="ru" lang="ru">RU</a>
  </div>
</nav>
""",
}

FOOT = {
    "en": """
<footer>
  <div class="wrap">
    <div>
      <p class="micro">Askbase &middot; Besk Tech</p>
      <p>The model runs on your machine. The application does not need a network, and there is no telemetry.</p>
    </div>
    <div class="links">
      <a href="/comparison/">Comparison</a>
      <a href="/where-your-data-goes/">Where your data goes</a>
      <a href="/read-only-access/">Read-only access</a>
      <a href="/author/">Author</a>
      <a href="https://besk.tech">besk.tech</a>
    </div>
  </div>
</footer>
""",
    "ru": """
<footer>
  <div class="wrap">
    <div>
      <p class="micro">Askbase &middot; Besk Tech</p>
      <p>Модель работает на вашем компьютере. Приложению не нужна сеть, телеметрии нет.</p>
    </div>
    <div class="links">
      <a href="/ru/sravnenie/">Сравнение</a>
      <a href="/ru/kuda-uhodyat-dannye/">Куда уходят данные</a>
      <a href="/ru/dostup-tolko-chtenie/">Доступ только на чтение</a>
      <a href="/ru/avtor/">Автор</a>
      <a href="https://besk.tech">besk.tech</a>
    </div>
  </div>
</footer>
""",
}

TAIL = """<script src="/assets/app.js" defer></script>
</body>
</html>
"""

_OLD_FOOTER_UNUSED = """
<footer class="foot">
  <div class="wrap">
    <p class="micro">Besk Tech</p>
  </div>
</footer>
<script src="/assets/app.js" defer></script>
</body>
</html>
"""


def with_prefix(html: str) -> str:
    """Prefix every root relative link, so the site works under /<repo>/."""
    if not PREFIX:
        return html
    for attr in ('href="', 'src="', 'content="'):
        html = re.sub(
            rf'{re.escape(attr)}/(?!/)',       # "/..." but not "//host"
            f'{attr}{PREFIX}/',
            html,
        )
    # canonical and og:url already carry the absolute BASE, so undo those
    return html.replace(f'{BASE}{PREFIX}/', f'{BASE}/').replace(f'"{PREFIX}{BASE}', f'"{BASE}')


def build(check_only: bool) -> int:
    results = load_results()
    if not PAGES.exists():
        print(f"нет каталога {PAGES}", file=sys.stderr)
        return 1

    built, problems, pending = [], [], []
    for name, route in ROUTES.items():
        path = route.path
        src = PAGES / f"{name}.html"
        if not src.exists():
            problems.append(f"{name}: текст страницы не написан ({src.relative_to(ROOT)})")
            continue
        body = src.read_text(encoding="utf-8")
        body = re.sub(r"^<!--meta.*?-->\s*", "", body, flags=re.S)
        if route.signed and "<!--byline-->" not in body:
            problems.append(f"{name}: нет метки <!--byline-->, подписанная страница пойдёт без автора")
            continue
        body = body.replace("<!--byline-->", BYLINE[route.lang])
        body = body.replace("<!--ASK-->", ASK[route.lang])
        try:
            body, filled = split_regions(body, results)
            if not filled:
                pending.append(name)
            body = resolve(body, results, name)
        except Unbacked as e:
            problems.append(str(e))
            continue
        if not check_only:
            out = SITE / path / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            nav = (NAV[route.lang]
                   .replace("{twin}", url_of(ROUTES[route.twin]))
                   .replace("{self}", url_of(route)))
            page = head(route) + nav + body + FOOT[route.lang] + TAIL
            out.write_text(with_prefix(page), encoding="utf-8")
        built.append(path)
        if path.endswith("404"):
            built.pop()   # exists as a file, never in the sitemap

    for name, why in BLOCKED.items():
        problems.append(f"{name}: не собирается намеренно, {why}")

    print(f"собрано страниц: {len(built)}")
    for p in built:
        print(f"  /{p}/" if p not in ("", "/") else "  / (главная)")
    if pending:
        print("\nсобрано, но ждёт прогона:")
        for p in pending:
            print(f"  {p}: таблица результатов пуста, заполнится из results/")
    if problems:
        print("\nне собрано:")
        for p in problems:
            print(f"  {p}")
    # Unbacked numbers are a failure; a page simply not written yet is not.
    hard = [p for p in problems if "без подтверждения" in p or "нечитаемый" in p]
    if hard:
        print(f"\nсборка остановлена: {len(hard)} страниц с неподтверждёнными числами", file=sys.stderr)
        return 1
    if not check_only:
        write_meta(built)
    return 0


def write_meta(built: list[str]) -> None:
    # Trailing slash, to match the canonical link on every page. A sitemap that
    # lists /comparison while the page declares /comparison/ reports two URLs
    # for one page.
    urls = "\n".join(
        f"  <url><loc>{BASE}/{p + '/' if p.strip('/') else ''}</loc></url>"
        for p in sorted(built)
    )
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n",
        encoding="utf-8",
    )
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8"
    )
    tpl = SITE / "llms.tpl.txt"
    if tpl.exists():
        (SITE / "llms.txt").write_text(
            tpl.read_text(encoding="utf-8").replace("{DATE}", date.today().isoformat()),
            encoding="utf-8",
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only, write nothing")
    raise SystemExit(build(ap.parse_args().check))
