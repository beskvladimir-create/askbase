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


_AGG = {
    "count": "посчитал количество",
    "sum": "сложил",
    "avg": "посчитал среднее",
    "min": "взял наименьшее",
    "max": "взял наибольшее",
}


def explain(sql: str, dialect: str = "sqlite") -> Explanation:
    """Return a plain-language account of what the query does and omits."""
    try:
        stmt = sqlglot.parse_one(sql, dialect=dialect)
    except Exception:
        return Explanation("Не удалось разобрать запрос, поэтому описания нет.")
    if stmt is None:
        return Explanation("Запрос пуст.")

    tables = _tables(stmt)
    aggs = _aggregates(stmt)
    groups = [_name(g) for g in stmt.args.get("group").expressions] if stmt.args.get("group") else []
    limit = stmt.args.get("limit")

    bits: list[str] = []
    if aggs:
        bits.append(_join_ru(aggs))
    else:
        bits.append("Выбрал строки")
    if tables:
        bits.append("из " + _join_ru(tables))
    if groups:
        bits.append("с группировкой по " + _join_ru(groups))
    where = stmt.args.get("where")
    if where is not None:
        bits.append("с отбором по условию")
    if stmt.args.get("order"):
        bits.append("с сортировкой")
    if limit is not None:
        n = limit.expression.this if limit.expression is not None else None
        bits.append(f"не больше {n} строк" if n else "с ограничением на число строк")

    summary = " ".join(bits).strip()
    summary = summary[0].upper() + summary[1:] + "." if summary else ""
    return Explanation(summary, _omissions(stmt))


def _omissions(stmt: exp.Expression) -> list[str]:
    """The quiet exclusions, which are what makes an answer wrong unnoticed."""
    out: list[str] = []

    inner = [
        j for j in stmt.find_all(exp.Join)
        if (j.side or "").upper() not in {"LEFT", "RIGHT", "FULL"}
    ]
    if inner:
        names = sorted({_name(j.this) for j in inner if _name(j.this)})
        if names:
            out.append(
                "Строки без совпадения в " + _join_ru(names) + " в ответ не попали."
            )

    cols = sorted({
        c.name for c in (stmt.args.get("where").find_all(exp.Column)
                         if stmt.args.get("where") is not None else [])
        if c.name
    })
    if cols:
        out.append(
            "Строки, где " + _join_ru(cols) + " не заполнено, тоже не попали."
        )

    if stmt.find(exp.Having) is not None:
        out.append("Группы, не прошедшие условие HAVING, отброшены.")

    if any(isinstance(d, exp.Distinct) for d in stmt.find_all(exp.Distinct)):
        out.append("Повторяющиеся строки объединены в одну.")

    return out


def _tables(stmt: exp.Expression) -> list[str]:
    seen: list[str] = []
    for t in stmt.find_all(exp.Table):
        n = t.name
        if n and n not in seen:
            seen.append(n)
    return seen


def _aggregates(stmt: exp.Expression) -> list[str]:
    out: list[str] = []
    select = stmt.args.get("expressions") or []
    for e in select:
        for fn in e.find_all(exp.Func):
            key = fn.sql_name().lower()
            if key in _AGG:
                what = _name(fn.this) if fn.this is not None else ""
                phrase = _AGG[key]
                if key != "count" and what:
                    phrase += f" значения {what}"
                if phrase not in out:
                    out.append(phrase)
                break
    return out


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


def _join_ru(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " и " + items[-1]
