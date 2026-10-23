"""Describe a SQL query in plain language, including what it leaves out.

This is derived from the parsed query, not written by the model. Two reasons.
A model asked to describe its own query will describe what it meant rather than
what it wrote, which is exactly the case the user needs protection from. And a
second model call would double the wait for no gain.

The part that matters most is not the description, it is the omissions. An
INNER JOIN silently drops rows with no match, a filter on a column drops rows
where that column is NULL, and an aggregate over an empty group returns
nothing. Those are the ways a confident wrong answer gets produced, so they are
stated rather than left for the reader to infer from the SQL.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp


@dataclass
class Explanation:
    summary: str
    omissions: list[str] = field(default_factory=list)

    def text(self) -> str:
        parts = [self.summary]
        parts.extend(self.omissions)
        return " ".join(p for p in parts if p)



# Every sentence this module can produce, in both languages. Kept as a table
# rather than as f-strings scattered through the code: this is the product's
# trust claim, and in the English build it used to come out in Russian.
PHRASES: dict[str, dict[str, str]] = {
    "ru": {
        "unparsable": "Не удалось разобрать запрос, поэтому описания нет.",
        "empty": "Запрос пуст.",
        "selected": "Выбрал строки",
        "from": "из {what}",
        "grouped": "с группировкой по {what}",
        "filtered": "с отбором по условию",
        "ordered": "с сортировкой",
        "limit_n": "не больше {n} строк",
        "limit_some": "с ограничением на число строк",
        "offset_n": "пропустив первые {n} строк",
        "offset_some": "пропустив строки с начала",
        "and": " и ",
        "inner_join": "Строки без совпадения в {what} в ответ не попали.",
        "null_filter": "Строки, где {what} не заполнено, тоже не попали.",
        "having": "Группы, не прошедшие условие HAVING, отброшены.",
        "distinct": "Повторяющиеся строки объединены в одну.",
        "count": "посчитал количество",
        "sum": "сложил",
        "avg": "посчитал среднее",
        "min": "взял наименьшее",
        "max": "взял наибольшее",
        "of_column": " значения {what}",
    },
    "en": {
        "unparsable": "The query could not be parsed, so there is no description.",
        "empty": "The query is empty.",
        "selected": "Selected rows",
        "from": "from {what}",
        "grouped": "grouped by {what}",
        "filtered": "matching a condition",
        "ordered": "sorted",
        "limit_n": "limited to {n} rows",
        "limit_some": "with a limit on the number of rows",
        "offset_n": "skipping the first {n} rows",
        "offset_some": "skipping rows from the start",
        "and": " and ",
        "inner_join": "Rows with no match in {what} are not in the answer.",
        "null_filter": "Rows where {what} is empty are not in it either.",
        "having": "Groups that failed the HAVING condition were dropped.",
        "distinct": "Repeated rows were collapsed into one.",
        "count": "counted the rows",
        "sum": "added up",
        "avg": "averaged",
        "min": "took the smallest",
        "max": "took the largest",
        "of_column": " the values of {what}",
    },
}



def explain(sql: str, dialect: str = "sqlite", lang: str = "ru") -> Explanation:
    """Return a plain-language account of what the query does and omits."""
    w = PHRASES.get(lang, PHRASES["ru"])
    try:
        stmt = sqlglot.parse_one(sql, dialect=dialect)
    except Exception:
        return Explanation(w["unparsable"])
    if stmt is None:
        return Explanation(w["empty"])

    tables = _tables(stmt)
    aggs = _aggregates(stmt, w)
    groups = [_name(g) for g in stmt.args.get("group").expressions] if stmt.args.get("group") else []
    limit = stmt.args.get("limit")

    bits: list[str] = []
    if aggs:
        bits.append(_join(aggs, w))
    else:
        bits.append(w["selected"])
    if tables:
        bits.append(w["from"].format(what=_join(tables, w)))
    if groups:
        bits.append(w["grouped"].format(what=_join(groups, w)))
    where = stmt.args.get("where")
    if where is not None:
        bits.append(w["filtered"])
    if stmt.args.get("order"):
        bits.append(w["ordered"])
    if limit is not None:
        # Only a plain number is quoted back. "LIMIT 2 + 3" used to be read as
        # "не больше 2 строк": a wrong number stated with confidence, which is
        # the one thing this module must never do.
        n = _number(limit.expression)
        bits.append(w["limit_n"].format(n=n) if n else w["limit_some"])
    offset = stmt.args.get("offset")
    if offset is not None:
        # OFFSET is a silent exclusion like any other: the answer is missing
        # rows from the top, and nothing on screen said so.
        skipped = _number(offset.expression)
        bits.append(w["offset_n"].format(n=skipped) if skipped else w["offset_some"])

    # "what" and "from where" read as one phrase; every qualifier after them
    # gets a comma, or the sentence runs on without a breath: "grouped by name
    # sorted limited to 50 rows skipping the first 10 rows".
    head = " ".join(bits[:2]).strip()
    rest = ", ".join(bits[2:])
    summary = ", ".join(x for x in (head, rest) if x)
    summary = summary[0].upper() + summary[1:] + "." if summary else ""
    return Explanation(summary, _omissions(stmt, w))


def _omissions(stmt: exp.Expression, w: dict[str, str]) -> list[str]:
    """The quiet exclusions, which are what makes an answer wrong unnoticed."""
    out: list[str] = []

    inner = [
        j for j in stmt.find_all(exp.Join)
        if (j.side or "").upper() not in {"LEFT", "RIGHT", "FULL"}
    ]
    if inner:
        names = sorted({_name(j.this) for j in inner if _name(j.this)})
        if names:
            out.append(w["inner_join"].format(what=_join(names, w)))

    where = stmt.args.get("where")
    # A column the condition tests for emptiness is the exception: "WHERE
    # region_id IS NULL" keeps exactly the rows this sentence claims were
    # thrown away, so saying it would be the opposite of the truth. IS NOT NULL
    # is left in, because there the sentence is correct.
    asked_for_null = {
        c.name
        for node in (where.find_all(exp.Is) if where is not None else [])
        if isinstance(node.expression, exp.Null) and not isinstance(node.parent, exp.Not)
        for c in node.this.find_all(exp.Column)
        if c.name
    }
    cols = sorted({
        c.name for c in (where.find_all(exp.Column) if where is not None else [])
        if c.name and c.name not in asked_for_null
    })
    if cols:
        out.append(w["null_filter"].format(what=_join(cols, w)))

    if stmt.find(exp.Having) is not None:
        out.append(w["having"])

    if any(isinstance(d, exp.Distinct) for d in stmt.find_all(exp.Distinct)):
        out.append(w["distinct"])

    return out


def _tables(stmt: exp.Expression) -> list[str]:
    seen: list[str] = []
    for t in stmt.find_all(exp.Table):
        n = t.name
        if n and n not in seen:
            seen.append(n)
    return seen


def _aggregates(stmt: exp.Expression, w: dict[str, str]) -> list[str]:
    out: list[str] = []
    select = stmt.args.get("expressions") or []
    for e in select:
        for fn in e.find_all(exp.Func):
            key = fn.sql_name().lower()
            if key in w:
                what = _name(fn.this) if fn.this is not None else ""
                phrase = w[key]
                if key != "count" and what:
                    phrase += w["of_column"].format(what=what)
                if phrase not in out:
                    out.append(phrase)
                break
    return out


def _number(node) -> str:
    """The literal number in `node`, or "" when it is anything else."""
    if isinstance(node, exp.Literal) and not node.is_string:
        return str(node.this)
    return ""


def _name(node) -> str:
    if node is None:
        return ""
    if isinstance(node, exp.Column):
        return node.name
    if isinstance(node, exp.Table):
        return node.name
    if isinstance(node, exp.Star):
        return ""
    return getattr(node, "name", "") or ""


def _join(items: list[str], w: dict[str, str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + w["and"] + items[-1]
