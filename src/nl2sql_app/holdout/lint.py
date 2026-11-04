"""Refuse to author set 2 with the defects set 1 was found to have.

The hand review of set 1 read 240 failures and found that fifty of them were
not model errors at all. Three of the four causes were defects in the set, and
the freeze meant they had to stay: a gold whose select list answers more than
the question asked, floating-point noise in the last bit after AVG, and
questions whose answer depends on which of two tied rows a LIMIT happens to
take. A fourth, found on 2 November while reading the queries the model got
wrong, is the same tie problem seen from the other side: two of the five
hardest tasks on English are ones where the model wrote the right query and
the gold broke the tie differently.

Set 1 has 48 tasks and the defects were found by reading. Set 2 has 600 and
they will not be. So the authoring rules recorded in HOLDOUT.md stop being
prose and become checks that run.

What is deliberately not automated: whether the gold's select list holds
exactly what the question asks for. That is a judgement about two sentences in
two languages and a SQL statement, and a rule that guessed it would either
pass everything or fail honest tasks. The report prints the select list beside
the question instead, so the judgement is cheap to make and impossible to
skip.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

# A gold that takes the top k must say what breaks a tie. The first version
# of this check was syntactic, looking for an ORDER BY whose last key is not
# an aggregate, and it was wrong in the ordinary case: a gold writes
# `COUNT(*) AS n ... ORDER BY n DESC`, and the last key is then an alias with
# no aggregate anywhere in it. The checks below are empirical instead, and
# they separate two different defects that the syntactic one confused.
AGGREGATE = re.compile(r"\b(count|sum|avg|min|max|total)\s*\(", re.I)
LIMIT = re.compile(r"\blimit\s+(\d+)\s*$", re.I | re.M)
ORDER_BY = re.compile(r"\border\s+by\b(.*?)(?:\blimit\b|$)", re.I | re.S)

# Words a Russian wording can carry that a model reads as a filter when the
# gold has none. "Сколько счетов открыто в каждой валюте?" made models write
# `WHERE status_cd = 'open'`, which inflates the language gap for a reason
# that has nothing to do with the language.
STATE_WORDS = (
    "открыт", "закрыт", "активн", "действующ", "просроч", "отменённ",
    "отменен", "завершённ", "завершен", "текущ", "незакрыт", "неоплач",
)


@dataclass(frozen=True)
class Finding:
    tid: str
    rule: str
    detail: str


def _strip_limit(sql: str) -> tuple[str, int | None]:
    m = LIMIT.search(sql.strip())
    if not m:
        return sql, None
    return sql[: m.start()].rstrip(), int(m.group(1))


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside brackets.

    Written because of med2-035, whose ordering key is
    `AVG(julianday(a) - julianday(COALESCE(b, c)))`. A plain `split(",")` cut
    that expression in half, the rewritten query failed to parse, and the rule
    reported that the cut could not be checked. A tie check that gives up on
    every key holding a function call with two arguments is a hole exactly
    where the hard tasks are, so the depth is tracked.
    """
    out: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return [k.strip() for k in out if k.strip()]


def _order_keys(sql: str) -> list[str]:
    m = ORDER_BY.search(sql)
    if not m:
        return []
    return _split_top_level(m.group(1))


def _order_expr(sql: str) -> str | None:
    """The first ORDER BY expression, without its direction."""
    keys = _order_keys(sql)
    if not keys:
        return None
    return re.sub(r"\s+(asc|desc)\s*$", "", keys[0], flags=re.I).strip()


def _with_key(body: str, expr: str | None) -> str | None:
    """The query with the ordering expression added to what it returns."""
    if not expr:
        return None
    m = re.search(r"\bfrom\b", body, re.I)
    if not m:
        return None
    head, tail = body[: m.start()], body[m.start():]
    return f"{head.rstrip()}, ({expr}) AS __lint_key {tail}"


def _cut_findings(conn: sqlite3.Connection, tid: str, gold: str,
                  body: str, limit: int) -> list[Finding]:
    """Whether the cut at LIMIT falls inside a group the question cannot split.

    Comparing whole rows is not the test and it finds nothing: the tiebreak
    column is exactly the one that differs. The test is the key the question
    actually names. "The three most common diagnoses" names the count, and if
    third and fourth place both hold 96 then the question has no third place,
    whatever the gold's alphabetical tiebreak decides. "The five doctors who
    discharged the most" with 21, 21, 21, 19 at positions three to six is
    fine, because the cut falls between 21 and 19.
    """
    keys = _order_keys(gold)
    if not keys:
        return []
    primary = keys[0].split()[0].split(".")[-1].strip('"')
    try:
        cur = conn.execute(f"{body} LIMIT {limit + 1}")
        rows = cur.fetchall()
        names = [d[0] for d in cur.description]
    except sqlite3.Error:
        return []
    if len(rows) <= limit:
        return []
    if primary not in names:
        # The ordering key is an expression the query does not return, which
        # is the ordinary shape of "name the customer who received the most":
        # the answer is a name and the amount deciding it is nowhere in the
        # output. Rather than give up, ask for it: the key is spliced into the
        # select list and the widened query is run. A gold whose select list
        # cannot be found, or whose rewrite does not execute, still reports
        # unchecked, because a cut nobody verified is the defect this rule is
        # named after.
        widened = _with_key(body, _order_expr(gold))
        if widened is None:
            return [Finding(tid, "cut_unchecked",
                            f"cannot find the ordering key {primary!r} among "
                            f"the returned columns {names}, so the cut was "
                            "not checked")]
        try:
            rows = conn.execute(f"{widened} LIMIT {limit + 1}").fetchall()
        except sqlite3.Error as e:
            return [Finding(tid, "cut_unchecked",
                            f"the ordering key could not be read back: {e}")]
        if len(rows) <= limit:
            return []
        if rows[limit - 1][-1] == rows[limit][-1]:
            return [Finding(tid, "ambiguous_cut",
                            f"rows {limit} and {limit + 1} are equal on the "
                            "key the question orders by, so the cut is "
                            "arbitrary")]
        return []

    # Every ordering key that can be found among the returned columns. Tied
    # on all of them and the gold itself is a coin flip, run to run, because
    # nothing in the query decides the order. Tied on the first alone and the
    # gold is reproducible but the question is not: it asks for the top three
    # and there are four.
    idx = []
    for k in keys:
        name = k.split()[0].split(".")[-1].strip('"')
        if name in names:
            idx.append(names.index(name))
    a, b = rows[limit - 1], rows[limit]
    if idx and all(a[i] == b[i] for i in idx):
        return [Finding(tid, "nondeterministic_gold",
                        f"rows {limit} and {limit + 1} are tied on every "
                        "ordering key, so the gold returns a different answer "
                        "depending on the query plan")]
    i = names.index(primary)
    if a[i] == b[i]:
        return [Finding(tid, "ambiguous_cut",
                        f"rows {limit} and {limit + 1} both have "
                        f"{primary}={b[i]!r}: the question does not say which "
                        "one it wants, and the gold decides by a tiebreak it "
                        "never mentions")]
    return []


def check_task(conn: sqlite3.Connection, tid: str, gold: str,
               wordings: list[dict], traps: list[str]) -> list[Finding]:
    """Every rule, against one task. Never raises on a bad query."""
    out: list[Finding] = []
    if not traps:
        out.append(Finding(tid, "no_traps", "task declares no traps"))

    try:
        rows = conn.execute(gold).fetchall()
    except sqlite3.Error as e:
        return [*out, Finding(tid, "gold_fails", str(e))]

    if not rows:
        out.append(Finding(tid, "gold_empty",
                           "the gold returns no rows, so every answer that "
                           "returns none scores correct"))

    body, limit = _strip_limit(gold)
    if limit is not None:
        out += _cut_findings(conn, tid, gold, body, limit)

    if AGGREGATE.search(gold) and re.search(r"\bavg\s*\(", gold, re.I):
        for r in rows:
            for v in r:
                if isinstance(v, float) and len(repr(v).split(".")[-1]) > 10:
                    out.append(Finding(
                        tid, "float_noise",
                        f"{v!r} carries more decimals than any answer can "
                        "match: round it in the gold"))
                    break
            else:
                continue
            break

    has_where = re.search(r"\bwhere\b", gold, re.I) is not None
    if not has_where:
        for w in wordings:
            if w.get("lang") != "ru":
                continue
            low = w["text"].lower()
            hit = next((s for s in STATE_WORDS if s in low), None)
            if hit:
                out.append(Finding(
                    tid, "filter_word_without_filter",
                    f'"{hit}" reads as a condition, and the gold has no '
                    "WHERE: a model that filters is punished for the wording"))
    return out


def report_row(tid: str, gold: str, wordings: list[dict]) -> str:
    """The select list beside the question, for the judgement no rule makes."""
    head = re.split(r"\bfrom\b", gold, maxsplit=1, flags=re.I)[0]
    cols = re.sub(r"^\s*select\s+", "", head.strip(), flags=re.I)
    en = next((w["text"] for w in wordings if w.get("lang") == "en"), "")
    return f"{tid}\n    спрашивают: {en}\n    возвращает: {' '.join(cols.split())}"


def check_set_wide(tasks: list[dict]) -> list[Finding]:
    """The rules that no single task can break on its own.

    Found by hand on 2 November 2026, after both passes of set 2 were written:
    `bank2-024` and `log2-024` held the same gold, word for word the same
    English wording, and differed only in which database they ran against,
    because banking and logistics both have a table called `cust` with a
    nullable city. Two identical questions in one set are one question and a
    padded count, and no per-task rule can see it. The later task is the one
    reported, since the earlier one is usually the one worth keeping.
    """
    out: list[Finding] = []
    seen_gold: dict[str, str] = {}
    seen_text: dict[str, str] = {}
    for t in tasks:
        gold = " ".join(t["gold_sql"].split())
        first = seen_gold.setdefault(gold, t["tid"])
        if first != t["tid"]:
            out.append(Finding(t["tid"], "duplicate_gold",
                               f"the same gold as {first}, so the set asks one "
                               "question twice and counts it twice"))
        for w in t.get("wordings") or []:
            text = " ".join(w["text"].split())
            first = seen_text.setdefault(text, t["tid"])
            if first != t["tid"]:
                out.append(Finding(t["tid"], "duplicate_wording",
                                   f"this wording is already {first}'s: "
                                   f"{text!r}"))
    return out


def lint_set(data: str = "data/holdout") -> tuple[list[Finding], list[str]]:
    """Every task of every domain on disk, plus the rows for human judgement."""
    import json
    from pathlib import Path

    findings: list[Finding] = []
    rows: list[str] = []
    everything: list[dict] = []
    for tasks_file in sorted(Path(data).glob("*/tasks.json")):
        dom = tasks_file.parent.name
        d = json.loads(tasks_file.read_text(encoding="utf-8"))
        conn = sqlite3.connect(f"file:{tasks_file.parent / dom}.sqlite?mode=ro",
                               uri=True)
        try:
            for t in (d if isinstance(d, list) else d["tasks"]):
                findings += check_task(conn, t["tid"], t["gold_sql"],
                                       t["wordings"], t.get("traps") or [])
                rows.append(report_row(t["tid"], t["gold_sql"], t["wordings"]))
                everything.append(t)
        finally:
            conn.close()
    return findings + check_set_wide(everything), rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/holdout")
    ap.add_argument("--select-lists", action="store_true",
                    help="печатать, что возвращает эталон, рядом с вопросом")
    a = ap.parse_args(argv)

    findings, rows = lint_set(a.data)
    if a.select_lists:
        print("\n".join(rows))
        print()
    by_rule: dict[str, list[Finding]] = {}
    for f in findings:
        by_rule.setdefault(f.rule, []).append(f)
    for rule, items in sorted(by_rule.items(), key=lambda x: -len(x[1])):
        print(f"{rule}: {len(items)}")
        for f in items:
            print(f"    {f.tid}: {f.detail}")
    if not findings:
        print("правила составления соблюдены")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
