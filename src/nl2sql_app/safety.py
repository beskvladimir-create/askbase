"""Static check of generated SQL before it ever reaches the database.

The threat model is not a malicious user typing SQL: it is a model that was
talked into writing something else, or that wrote something expensive by
accident. Pedro et al. (ICSE 2025) showed that hardening the prompt is a fragile
defence and that an injected instruction can get full read/write access through
an unmodified agent, so nothing here depends on the prompt. A read-only database
role is still required and is checked separately at connect time; this module is
the second of the four layers in docs/design.md and the one that catches what a
read-only role cannot (recursive CTEs, missing row limits).

Verdict rules, fixed before any measurement (threshold P4):
  - exactly one statement, and it must be a SELECT (a leading WITH is fine)
  - no DDL, no DML, no transaction or pragma control
  - no recursive CTE: Langchain-Chatchat issue #5446 is a denial of service
    through an infinite recursive CTE that a read-only role does not stop
  - every table and column must exist in the schema snapshot we took
  - a row limit is mandatory; if the model did not write one we add it
"""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

# Statement types that must never reach the database. Anything that is not a
# plain SELECT lands here by default: the check is a whitelist, not a blacklist,
# and this list only exists to give the user a precise reason.
_FORBIDDEN = {
    exp.Insert: "вставка данных",
    exp.Update: "изменение данных",
    exp.Delete: "удаление данных",
    exp.Drop: "удаление объектов базы",
    exp.Create: "создание объектов базы",
    exp.Alter: "изменение структуры базы",
    exp.TruncateTable: "очистка таблицы",
    exp.Grant: "выдача прав",
    exp.Transaction: "управление транзакцией",
    exp.Commit: "управление транзакцией",
    exp.Rollback: "управление транзакцией",
    exp.Pragma: "смена настроек базы",
    exp.Attach: "подключение другой базы",
    exp.Detach: "отключение базы",
    exp.Command: "служебная команда",
}


@dataclass
class Verdict:
    """Outcome of the static check.

    `sql` carries the statement that may be executed, which is the input with a
    row limit added when the model omitted one. It is empty when ok is False:
    a rejected query is shown to the user but never run.
    """

    ok: bool
    sql: str = ""
    reason: str = ""
    limit_added: bool = False
    notes: list[str] = field(default_factory=list)


def check(
    sql: str,
    *,
    schema: dict[str, set[str]] | None = None,
    max_rows: int = 1000,
    dialect: str = "sqlite",
) -> Verdict:
    """Decide whether `sql` may be executed, and return the statement to run.

    `schema` maps table name to its column names, lowercased, as taken from the
    snapshot made at connect time. When it is None the name check is skipped,
    which is what the benchmark does when it measures accuracy rather than
    safety. Names are compared case-insensitively because SQLite is.
    """
    if not sql or not sql.strip():
        return Verdict(False, reason="Запрос пустой.")

    try:
        statements = [s for s in sqlglot.parse(sql, dialect=dialect) if s is not None]
    except Exception as e:
        return Verdict(False, reason=f"Запрос не разобрался как SQL: {e}")

    if not statements:
        return Verdict(False, reason="Запрос не содержит ни одного выражения.")
    if len(statements) > 1:
        # Chaining a second statement is the classic way an injected instruction
        # turns a read into a write.
        return Verdict(False, reason="В запросе больше одного выражения, разрешено одно.")

    stmt = statements[0]

    for node_type, human in _FORBIDDEN.items():
        if isinstance(stmt, node_type) or stmt.find(node_type) is not None:
            return Verdict(False, reason=f"Запрос выходит за чтение данных: {human}.")

    if not isinstance(stmt, (exp.Select, exp.Union, exp.Subquery)):
        return Verdict(False, reason=f"Разрешён только SELECT, а это {type(stmt).__name__.upper()}.")

    # Found by walking the tree rather than by arg key: sqlglot renamed the slot
    # from "with" to "with_" in 30.x, and reading the key silently returned None,
    # which let a recursive CTE straight through. A whitelist check must not
    # depend on a key name that a minor upgrade can move.
    for with_clause in stmt.find_all(exp.With):
        if with_clause.args.get("recursive"):
            return Verdict(
                False,
                reason="Рекурсивные выражения WITH запрещены, они могут не завершиться.",
            )

    notes: list[str] = []
    if schema is not None:
        unknown = _unknown_names(stmt, schema)
        if unknown:
            shown = ", ".join(sorted(unknown)[:4])
            return Verdict(False, reason=f"В запросе есть то, чего нет в базе: {shown}.")

    limit_added = False
    if isinstance(stmt, exp.Select) and stmt.args.get("limit") is None:
        stmt.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
        limit_added = True
        notes.append(f"LIMIT {max_rows} добавлен приложением")
    elif not isinstance(stmt, exp.Select):
        # A UNION has no single LIMIT slot to patch safely, so the executor
        # bounds it by fetching at most max_rows rows instead.
        notes.append(f"Строк будет взято не больше {max_rows}")

    return Verdict(
        ok=True,
        sql=stmt.sql(dialect=dialect),
        limit_added=limit_added,
        notes=notes,
    )


def _unknown_names(stmt: exp.Expression, schema: dict[str, set[str]]) -> set[str]:
    """Tables and qualified columns in `stmt` that the schema snapshot lacks.

    Only columns carrying a table qualifier are checked. A bare column cannot be
    resolved without implementing name resolution over every scope, and getting
    that subtly wrong would reject valid queries, which is worse here than
    leaving the database to raise a clear error on a genuinely missing column.
    """
    tables = {t.name.lower(): t for t in stmt.find_all(exp.Table) if t.name}
    # Table names introduced by WITH are real for the duration of the query.
    cte_names = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
    known = {k.lower(): {c.lower() for c in v} for k, v in schema.items()}

    unknown = {name for name in tables if name not in known and name not in cte_names}

    # alias -> real table, so t.col can be resolved back to a column list
    alias_of: dict[str, str] = {}
    for name, node in tables.items():
        if node.alias:
            alias_of[node.alias.lower()] = name
        alias_of.setdefault(name, name)

    for col in stmt.find_all(exp.Column):
        qualifier = col.table.lower() if col.table else ""
        if not qualifier:
            continue
        target = alias_of.get(qualifier, qualifier)
        if target in cte_names or target not in known:
            continue
        if col.name.lower() not in known[target]:
            unknown.add(f"{qualifier}.{col.name}")

    return unknown
