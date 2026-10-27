"""The number guard is the reason this build script exists, so it gets tested.

A page that quotes one of our measurements must not be publishable until the
measurement exists. Without this, the first landing page would carry a figure
typed by hand, and nothing would catch it going stale after the next run.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_site  # noqa: E402


@pytest.fixture
def results(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "RESULTS", tmp_path)
    return tmp_path


def write_summary(dirpath: Path, stem: str, payload: dict) -> None:
    (dirpath / f"{stem}.summary.json").write_text(json.dumps(payload))


def test_a_backed_number_is_substituted(results):
    write_summary(results, "xiyan-7b-q4.base", {"ex_accuracy": 0.551, "s_per_query": 9.56})
    loaded = build_site.load_results()
    out = build_site.resolve(
        "<p>EX {=xiyan-7b-q4|base|ex_accuracy}%, {=xiyan-7b-q4|base|s_per_query} s</p>",
        loaded,
        "test",
    )
    assert "55.1" in out
    assert "9.56" in out
    assert "{=" not in out


def test_an_unbacked_number_stops_the_build(results):
    loaded = build_site.load_results()
    # No pytest.fail inside the block: it is unreachable the moment resolve
    # raises, which reads as a safety net that does not exist. pytest.raises
    # already fails the test if nothing is raised.
    with pytest.raises(build_site.Unbacked) as e:
        build_site.resolve("<p>EX {=askbase|holdout|ex_accuracy}%</p>", loaded, "index")
    assert "index" in str(e.value)
    assert "askbase" in str(e.value)


def test_a_known_model_with_an_unknown_metric_also_stops_the_build(results):
    write_summary(results, "xiyan-7b-q4.base", {"ex_accuracy": 0.551})
    loaded = build_site.load_results()
    with pytest.raises(build_site.Unbacked):
        build_site.resolve("<p>{=xiyan-7b-q4|base|p95_latency}</p>", loaded, "test")


def test_every_missing_reference_is_reported_at_once(results):
    # One run should list all of them: fixing them one build at a time is how a
    # page ends up half-sourced.
    loaded = build_site.load_results()
    with pytest.raises(build_site.Unbacked) as e:
        build_site.resolve("{=a|b|c} and {=d|e|f}", loaded, "test")
    msg = str(e.value)
    assert "{=a|b|c}" in msg and "{=d|e|f}" in msg


def test_any_page_quoting_a_measurement_has_a_pending_twin():
    # Blocking a page used to be how we avoided publishing unmeasured numbers.
    # Now such a page is published with the table held back, so the invariant
    # moves: a page may reference results only if it also declares what to show
    # while they do not exist.
    for name in build_site.ROUTES:
        src = pathlib.Path(build_site.PAGES) / f"{name}.html"
        if not src.exists():
            continue
        body = src.read_text(encoding="utf-8")
        if build_site.REF.search(body):
            assert 'data-when="pending"' in body, f"{name}: числа без запасного состояния"
            assert 'data-when="results"' in body, f"{name}: нет региона результатов"


def test_anything_still_blocked_says_why():
    """Every deliberately unbuilt page carries a reason.

    BLOCKED is empty today, so iterating it asserted nothing: the loop body
    never ran. The property is checked against a stand-in instead, which keeps
    working whether the real dictionary is empty or not, and the emptiness is
    asserted separately so that filling it is a deliberate act.
    """
    assert build_site.BLOCKED == {}, (
        "страницы снова блокируются: проверьте, что у каждой есть причина")

    stand_in = {"some-page": "   ", "other-page": "есть причина"}
    bad = [name for name, why in stand_in.items() if not why.strip()]
    assert bad == ["some-page"], "правило «у блокировки есть причина» не работает"


def test_the_home_page_quotes_no_measurement(results):
    # It is built before any run exists, so it must not reference one.
    body = (pathlib.Path(build_site.PAGES) / "index.html").read_text(encoding="utf-8")
    assert not build_site.REF.search(body)


def test_every_route_is_paired_both_ways():
    # House style: English material always ships with a Russian version. The
    # pairing is declared, because Russian pages keep Russian slugs.
    for key, route in build_site.ROUTES.items():
        twin = build_site.ROUTES.get(route.twin)
        assert twin is not None, f"{key}: пара {route.twin} не объявлена"
        assert twin.lang != route.lang, f"{key}: пара на том же языке"
        assert twin.twin == key, f"{key}: пара не ссылается обратно"


def test_hreflang_points_at_a_real_path():
    # The bug this catches: deriving the Russian URL as "ru/" + English slug,
    # which sends every alternate link to a page that does not exist.
    known = {r.path for r in build_site.ROUTES.values()}
    for route in build_site.ROUTES.values():
        html = build_site.head(route)
        # Built with url_of, not with a naive f-string. The naive version is
        # what the page used to emit, so this test asserted the defect and
        # passed: both home pages declared their alternate at BASE + "//".
        twin = build_site.ROUTES[route.twin]
        twin_url = f"{build_site.BASE}{build_site.url_of(twin)}"
        assert f'hreflang="{twin.lang}" href="{twin_url}"' in html
        assert build_site.ROUTES[route.twin].path in known


def test_x_default_points_at_the_primary_language():
    for route in build_site.ROUTES.values():
        html = build_site.head(route)
        en_route = route if route.lang == "en" else build_site.ROUTES[route.twin]
        en_url = f"{build_site.BASE}{build_site.url_of(en_route)}"
        assert f'hreflang="x-default" href="{en_url}"' in html


def test_prose_figures_are_left_alone(results):
    # A number quoted from someone else's model card is prose with a source
    # link, not a reference, and must pass through untouched.
    loaded = build_site.load_results()
    text = "<p>XiYanSQL reports 62.13% on BIRD dev (<a href='#'>model card</a>).</p>"
    assert build_site.resolve(text, loaded, "test") == text


def test_sitemap_urls_match_the_canonical_links(tmp_path, monkeypatch):
    # Catches the mismatch where the sitemap lists /comparison while the page
    # declares /comparison/ as canonical, which counts as two URLs for one page.
    monkeypatch.setattr(build_site, "SITE", tmp_path)
    build_site.write_meta([r.path for r in build_site.ROUTES.values()])
    sitemap = (tmp_path / "sitemap.xml").read_text()
    for route in build_site.ROUTES.values():
        canonical = build_site.head(route).split('rel="canonical" href="')[1].split('"')[0]
        assert f"<loc>{canonical}</loc>" in sitemap, canonical


def test_the_js_hook_is_set_before_the_stylesheet():
    # Every "reveal until scripted" rule is written as ".js ...". Without the
    # class the page renders every state at once, and after the stylesheet it
    # renders them for one frame.
    html = build_site.head(build_site.ROUTES["index"])
    assert 'classList.add("js")' in html
    assert html.index('classList.add("js")') < html.index("style.css")


def test_hero_buttons_have_a_gap():
    # The spacing rule was written for the old ".hero" section only, so in the
    # ".open" section the buttons sat with no gap and touched once they wrapped.
    css = (pathlib.Path(build_site.SITE) / "assets" / "style.css").read_text(encoding="utf-8")
    rule = [ln for ln in css.splitlines() if ".open .cta {" in ln or ".open .cta," in ln
            or (".cta {" in ln and ".open" in ln)]
    assert rule, "нет правила отступа для кнопок в секции .open"
    assert "gap:" in rule[0]


def test_every_page_declares_an_icon_and_a_link_card():
    # A product that spreads by a pasted link is judged on that card before the
    # page is opened, so a missing one is a real loss, not a nicety.
    for route in build_site.ROUTES.values():
        html = build_site.head(route)
        assert 'rel="icon"' in html
        assert 'property="og:image"' in html
        card = "og-ru.png" if route.lang == "ru" else "og.png"
        assert f"/assets/{card}" in html
        assert (pathlib.Path(build_site.SITE) / "assets" / card).exists(), card


PAGE = (
    '<div data-when="pending"><p>Прогона ещё не было.</p></div>'
    '<div data-when="results"><p>A {=m1|base|ex_accuracy} B {=m2|base|ex_accuracy}</p></div>'
)


def test_without_data_the_pending_region_is_kept(results):
    body, filled = build_site.split_regions(PAGE, build_site.load_results())
    assert not filled
    assert "Прогона ещё не было" in body
    assert "{=m1" not in body          # the unfilled table must not reach the page


def test_with_full_data_the_results_region_is_kept(results):
    write_summary(results, "m1.base", {"ex_accuracy": 0.68})
    write_summary(results, "m2.base", {"ex_accuracy": 0.55})
    body, filled = build_site.split_regions(PAGE, build_site.load_results())
    assert filled
    assert "Прогона ещё не было" not in body
    out = build_site.resolve(body, build_site.load_results(), "ranking")
    assert "68.0" in out and "55.0" in out


def test_partial_data_counts_as_no_data(results):
    # The case that matters: one model measured, one not. A half-filled table is
    # worse than an empty one, because a reader cannot tell which half is real.
    write_summary(results, "m1.base", {"ex_accuracy": 0.68})
    body, filled = build_site.split_regions(PAGE, build_site.load_results())
    assert not filled
    assert "Прогона ещё не было" in body


def test_a_lone_region_is_an_error(results):
    # A results region without its pending twin would publish an empty table.
    with pytest.raises(build_site.Unbacked):
        build_site.split_regions('<div data-when="results">{=m|s|x}</div>', build_site.load_results())


def test_the_ranking_page_is_published_and_waiting():
    assert "model-ranking" in build_site.ROUTES
    assert "model-ranking" not in build_site.BLOCKED
    body = (pathlib.Path(build_site.PAGES) / "model-ranking.html").read_text(encoding="utf-8")
    assert 'data-when="pending"' in body and 'data-when="results"' in body


def test_root_links_get_the_deployment_prefix(monkeypatch):
    # GitHub Pages serves a project repo under /<repo>/, where a link written
    # as "/comparison/" is a 404.
    monkeypatch.setattr(build_site, "PREFIX", "/askbase")
    out = build_site.with_prefix('<a href="/comparison/">x</a><link href="/assets/style.css">')
    assert '/askbase/comparison/' in out
    assert '/askbase/assets/style.css' in out


def test_absolute_urls_are_left_alone(monkeypatch):
    monkeypatch.setattr(build_site, "PREFIX", "/askbase")
    out = build_site.with_prefix('<a href="https://besk.tech">x</a><a href="//cdn/x">y</a>')
    assert 'href="https://besk.tech"' in out
    assert 'href="//cdn/x"' in out


def test_the_canonical_url_does_not_get_the_prefix_twice(monkeypatch):
    monkeypatch.setattr(build_site, "PREFIX", "/askbase")
    out = build_site.with_prefix(f'<link rel="canonical" href="{build_site.BASE}/comparison/">')
    assert f'{build_site.BASE}/comparison/' in out
    assert "/askbase/askbase/" not in out


def test_the_home_page_link_is_not_protocol_relative():
    # f"/{path}/" with an empty path yields "//", which a browser reads as a
    # URL on another host. Both home pages have an empty path.
    assert build_site.url_of(build_site.ROUTES["index"]) == "/"
    assert build_site.url_of(build_site.ROUTES["ru-index"]) == "/ru/"
    assert build_site.url_of(build_site.ROUTES["comparison"]) == "/comparison/"


def test_no_built_page_contains_a_double_slash_link():
    for route in build_site.ROUTES.values():
        out = pathlib.Path(build_site.SITE) / route.path / "index.html"
        if not out.exists():
            continue
        html = out.read_text(encoding="utf-8")
        assert 'href="//"' not in html, route.path


def test_the_not_found_page_is_where_the_host_looks_for_it():
    # Vercel serves /404.html from the root. Our page also lives at /404/, but
    # only the root file replaces the platform's default.
    assert (pathlib.Path(build_site.SITE) / "404.html").exists()


REFERENCE = "https://pii-roundtrip.besk.tech/"


def test_the_header_has_the_same_parts_as_the_other_site():
    # Both products share one stylesheet, so the header must carry the same
    # pieces or the two sites stop looking like one house: brand with a 24px
    # mark, a list of sections, then a .right holding the language pair and
    # one primary small button.
    # the built page, because the mark and the button icon are substituted
    page = (pathlib.Path(build_site.SITE) / "index.html").read_text(encoding="utf-8")
    html = re.search(r"<nav class=\"nav\".*?</nav>", page, re.S).group(0)
    assert 'class="brand"' in html
    assert 'viewBox="0 0 24 24"' in html      # same box as the other site
    assert html.count("<li>") == 4
    assert 'class="right"' in html
    assert '<span class="lang">' in html
    assert 'aria-current="page"' in html
    assert 'class="btn primary small"' in html


def test_both_languages_declare_the_same_header_shape():
    for lang in ("en", "ru"):
        html = build_site.NAV[lang]
        assert html.count("<li>") == 4
        assert 'class="right"' in html
        assert 'class="btn primary small"' in html


def test_the_footer_is_two_spans_author_then_links():
    for lang in ("en", "ru"):
        html = build_site.FOOT[lang]
        assert html.count("<span>") == 2
        assert "Besk Tech" in html
        assert "besk.tech" in html
        assert " · " in html          # the separator the other site uses


def test_the_brand_mark_is_not_resized_locally():
    # An override here would make the two headers differ by a few pixels,
    # which is exactly the kind of drift nobody notices until both are open
    # side by side.
    css = (pathlib.Path(build_site.SITE) / "assets" / "style.css").read_text(encoding="utf-8")
    assert css.count(".brand svg {") == 1
    assert "width: 24px" in css.split(".brand svg {")[1].split("}")[0]


# ---- the publish gate itself ------------------------------------------------
# Everything above tests one level down, inside resolve() and split_regions().
# The gate is build(), and it was found deciding hard failure from soft by
# substring-matching a Russian sentence, so rewording a message turned a
# blocked publish into exit 0 with nothing failing anywhere.

def test_an_unbacked_number_stops_the_build(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "RESULTS", tmp_path / "results")
    (tmp_path / "results").mkdir()
    pages = tmp_path / "pages"
    pages.mkdir()
    site = tmp_path / "site"
    route = build_site.Route(path="made-up", lang="en", title="T", desc="D", twin="made-up", signed=False)
    monkeypatch.setattr(build_site, "PAGES", pages)
    monkeypatch.setattr(build_site, "SITE", site)
    monkeypatch.setattr(build_site, "ROUTES", {"made-up": route})
    (pages / "made-up.html").write_text(
        "<p>accuracy {=never-ran|holdout:en|ex}</p>", encoding="utf-8")
    assert build_site.build(check_only=True) == 1


def test_a_reworded_message_still_stops_the_build(tmp_path, monkeypatch):
    # The regression this pins. The gate must not depend on the words in the
    # message; an Unbacked is fatal because of what it is.
    monkeypatch.setattr(build_site, "RESULTS", tmp_path / "results")
    (tmp_path / "results").mkdir()
    pages = tmp_path / "pages"
    pages.mkdir()
    route = build_site.Route(path="made-up", lang="en", title="T", desc="D", twin="made-up", signed=False)
    monkeypatch.setattr(build_site, "PAGES", pages)
    monkeypatch.setattr(build_site, "SITE", tmp_path / "site")
    monkeypatch.setattr(build_site, "ROUTES", {"made-up": route})
    (pages / "made-up.html").write_text("<p>{=nope|holdout:en|ex}</p>", encoding="utf-8")

    real = build_site.resolve

    def reworded(body, results, page):
        try:
            return real(body, results, page)
        except build_site.Unbacked:
            raise build_site.Unbacked("anything at all, in any language") from None

    monkeypatch.setattr(build_site, "resolve", reworded)
    assert build_site.build(check_only=True) == 1


def test_a_page_that_loses_its_backing_is_removed_not_left_behind(tmp_path, monkeypatch):
    # Skipping the write kept the previous build's file in site/, so a page
    # whose number lost its backing went on being served with the old number,
    # and deploy_site.sh, which gates only on the exit code, published it.
    monkeypatch.setattr(build_site, "RESULTS", tmp_path / "results")
    (tmp_path / "results").mkdir()
    pages = tmp_path / "pages"
    pages.mkdir()
    site = tmp_path / "site"
    (site / "made-up").mkdir(parents=True)
    stale = site / "made-up" / "index.html"
    stale.write_text("<p>accuracy 99.9%</p>", encoding="utf-8")
    route = build_site.Route(path="made-up", lang="en", title="T", desc="D", twin="made-up", signed=False)
    monkeypatch.setattr(build_site, "PAGES", pages)
    monkeypatch.setattr(build_site, "SITE", site)
    monkeypatch.setattr(build_site, "ROUTES", {"made-up": route})
    (pages / "made-up.html").write_text("<p>{=nope|holdout:en|ex}</p>", encoding="utf-8")

    assert build_site.build(check_only=False) == 1
    assert not stale.exists(), "страница со старым числом осталась в site/"


def test_a_missing_page_is_not_a_publish_failure(tmp_path, monkeypatch):
    # Work outstanding is not a false number going out, and must not block a
    # deploy of everything else.
    monkeypatch.setattr(build_site, "RESULTS", tmp_path / "results")
    (tmp_path / "results").mkdir()
    pages = tmp_path / "pages"
    pages.mkdir()
    route = build_site.Route(path="unwritten", lang="en", title="T", desc="D", twin="unwritten", signed=False)
    monkeypatch.setattr(build_site, "PAGES", pages)
    monkeypatch.setattr(build_site, "SITE", tmp_path / "site")
    monkeypatch.setattr(build_site, "ROUTES", {"unwritten": route})
    assert build_site.build(check_only=True) == 0


# ---- which runs the build is allowed to see ---------------------------------

def test_runs_in_subdirectories_are_not_published(tmp_path, monkeypatch):
    # results/void/ holds runs withdrawn with a written reason and results/probe/
    # holds smoke tests. Walking the tree made a voided run indistinguishable
    # from a measurement: the withdrawn Arctic-7B run resolved under exactly the
    # key the ranking page references.
    monkeypatch.setattr(build_site, "RESULTS", tmp_path)
    (tmp_path / "void").mkdir()
    (tmp_path / "void" / "m.base.summary.json").write_text(
        '{"ex_accuracy": 0.456, "n": 500}', encoding="utf-8")
    (tmp_path / "probe").mkdir()
    (tmp_path / "probe" / "m.base.summary.json").write_text(
        '{"ex_accuracy": 0.9, "n": 20}', encoding="utf-8")
    assert build_site.load_results() == {}


def test_a_real_run_beside_a_voided_one_is_the_one_that_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "RESULTS", tmp_path)
    (tmp_path / "void").mkdir()
    (tmp_path / "void" / "m.base.summary.json").write_text(
        '{"ex_accuracy": 0.456}', encoding="utf-8")
    (tmp_path / "m.base.summary.json").write_text(
        '{"ex_accuracy": 0.5}', encoding="utf-8")
    assert build_site.load_results() == {"m.base": {"ex_accuracy": 0.5}}


def test_two_summaries_under_one_name_are_refused(tmp_path, monkeypatch):
    # Cannot arise from the filesystem at the top level, but can from a rename
    # or a merge, and resolving it by sort order is how an n=20 smoke test gets
    # published as the run.
    monkeypatch.setattr(build_site, "RESULTS", tmp_path)
    (tmp_path / "m.base.summary.json").write_text('{"ex_accuracy": 0.5}', encoding="utf-8")
    real_glob = build_site.pathlib.Path.glob

    def doubled(self, pattern):
        got = list(real_glob(self, pattern))
        return got + got

    monkeypatch.setattr(build_site.pathlib.Path, "glob", doubled)
    with pytest.raises(build_site.Unbacked):
        build_site.load_results()


def test_unreadable_json_is_a_publish_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "RESULTS", tmp_path)
    (tmp_path / "m.base.summary.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(build_site.Unbacked):
        build_site.load_results()


def test_no_link_in_any_head_has_a_double_slash():
    """A browser reads "//" as a protocol-relative URL to another host.

    url_of exists for this and guarded the canonical only; the two alternates
    and x-default were built by hand and did not, so every head on the two home
    pages carried three links to https://askbase.besk.tech// . The tests that
    covered hreflang built the expected value the same wrong way and passed.
    """
    for route in build_site.ROUTES.values():
        html = build_site.head(route)
        for link in re.findall(r'href="(https://[^"]+)"', html):
            assert "//" not in link[len("https://"):], f"{route.path or 'главная'}: {link}"
