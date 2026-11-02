"""Schema serialization + lightweight schema linking.

`serialize_schema` renders a compact CREATE-style view of the db for the prompt.
`link_schema` is the recipe's schema-linking step: keep only tables/columns whose
names overlap the question/evidence tokens (plus their primary/foreign keys), to
cut prompt size and distractors on wide databases. Deliberately simple and
model-agnostic — the ablation measures how much this lexical filter alone buys.
"""
from __future__ import annotations

import re
import sqlite3


def _tables(conn: sqlite3.Connection, views: bool = False,
            order: str = "create") -> dict[str, list[str]]:
    """Table names and their columns.

    Views are included only on request: in a database somebody else designed
    the readable part is often a set of views, and leaving them out hides them
    from the model. Order is the order of creation unless asked for by name,
    and the two are kept apart from each other and from the rendering because
    bundling them made a measured difference impossible to attribute. Creation
    order puts a table next to the dictionary that decodes it; by name it does
    not.
    """
    kinds = "('table', 'view')" if views else "('table')"
    sort = " ORDER BY name" if order == "name" else ""
    cur = conn.execute(
        f"SELECT name FROM sqlite_master WHERE type IN {kinds}{sort}")
    names = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]
    schema: dict[str, list[str]] = {}
    for t in names:
        cols = conn.execute(f'PRAGMA table_info("{t}")').fetchall()
        schema[t] = [c[1] for c in cols]  # c[1] = column name
    return schema


def _quoted(name: str) -> str:
    """A SQLite identifier, safe to paste into SQL whatever it is called."""
    return '"' + name.replace('"', '""') + '"'


def render_schema(tables: dict[str, list[str]],
                  samples: dict[str, list[str]] | None = None,
                  ddl: bool = False) -> str:
    """The schema block of the prompt, from data rather than from a path.

    One renderer for the harness and for the desktop application, which take
    their input from different places: the harness opens the file, the
    application already holds a bounded snapshot that its safety check works
    off and must not re-read. Two renderers is how the number stops describing
    the product: the published figure was measured on `t(a, b)` while the
    application was shipping quoted CREATE TABLE statements with example
    values attached, and nobody had measured that prompt at all.
    """
    lines = []
    for t, cols in tables.items():
        if ddl:
            body = ", ".join(_quoted(c) for c in cols)
            lines.append(f"CREATE TABLE {_quoted(t)} ({body});")
        else:
            lines.append(f"{t}({', '.join(cols)})")
        hints = [h for h in (samples or {}).get(t, []) if h]
        if hints:
            lines.append(f"-- example values in {_quoted(t)}: {'; '.join(hints)}")
    return "\n".join(lines)


def sample_values(conn: sqlite3.Connection, table: str, cols: list[str],
                  n: int) -> list[str]:
    """Example values for the columns that hold only a handful of them.

    A column holding 1 and 2 instead of 'male' and 'female' is a common reason
    a generated filter is wrong, and the name does not give the encoding away.
    A column of unique names teaches the model nothing, so only low-cardinality
    columns are quoted.
    """
    out = []
    for c in cols:
        try:
            vals = [r[0] for r in conn.execute(
                f'SELECT DISTINCT {_quoted(c)} FROM {_quoted(table)} '
                f'WHERE {_quoted(c)} IS NOT NULL LIMIT {n + 1}')]
        except sqlite3.Error:
            continue
        if 0 < len(vals) <= n:
            out.append(f"{c} is one of {', '.join(repr(v) for v in vals)}")
    return out


def serialize_schema(db_path: str, tables: list[str] | None = None, *,
                     ddl: bool = False, samples: int = 0,
                     views: bool | None = None,
                     order: str | None = None) -> str:
    """The schema block for the prompt, read from the database.

    `ddl` and `samples` together reproduce what the desktop application puts
    in front of the model, which is why they exist: so that one measurement
    can describe the shipped prompt instead of a near relative of it. `views`
    and `order` follow `ddl` unless given, so that the application's rendering
    stays one argument away while an experiment can still vary one thing.
    """
    if views is None:
        views = ddl
    if order is None:
        order = "name" if ddl else "create"
    conn = sqlite3.connect(db_path)
    try:
        schema = _tables(conn, views=views, order=order)
        if tables is not None:
            schema = {t: c for t, c in schema.items() if t in tables}
        hints = {}
        if samples:
            for t, cols in schema.items():
                got = sample_values(conn, t, cols, samples)
                if got:
                    hints[t] = got
    finally:
        conn.close()
    return render_schema(schema, hints, ddl=ddl)


def _subtokens(s: str) -> set[str]:
    """Split an identifier or sentence into lowercase word tokens (len > 1)."""
    return {w for w in re.split(r"[^a-z0-9]+", s.lower()) if len(w) > 1}


def link_schema(db_path: str, question: str, evidence: str = "") -> list[str]:
    """Return the subset of table names judged relevant to the question.

    Match on word-level sub-tokens. BIRD column names contain spaces and
    punctuation (e.g. ``Free Meal Count (K-12)``), so a column must be split
    into words before overlap testing; comparing the whole column string
    against single question tokens never matches multi-word columns and prunes
    away the very table that holds the answer.
    """
    conn = sqlite3.connect(db_path)
    try:
        schema = _tables(conn)
    finally:
        conn.close()
    q_tokens = _subtokens(f"{question} {evidence}")
    kept = []
    for t, cols in schema.items():
        name_tokens = _subtokens(t)
        for c in cols:
            name_tokens |= _subtokens(c)
        if name_tokens & q_tokens:
            kept.append(t)
    # Fallback: if nothing matched, keep everything rather than starve the model.
    return kept or list(schema.keys())


# --- retrieval-based (embedding) schema linker -------------------------------
# Rehabilitated comparison vs the lexical linker: embed each table (name + its
# column names) and the question+evidence with a sentence-transformer, keep the
# top-k tables by cosine similarity. Heavy deps (sentence-transformers, torch)
# are imported lazily so the rest of the harness runs without them.

_EMB_MODEL = None
_EMB_CACHE: dict[str, tuple] = {}  # db_path -> (table_names, table_matrix)


def _get_embedder(model_name: str = "all-MiniLM-L6-v2"):
    global _EMB_MODEL
    if _EMB_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMB_MODEL = SentenceTransformer(model_name)
    return _EMB_MODEL


def _table_doc(name: str, cols: list[str]) -> str:
    return f"{name}: " + ", ".join(cols)


def _db_table_embeddings(db_path: str, model_name: str):
    """(table_names, normalized embedding matrix) for a db, cached per process."""
    if db_path in _EMB_CACHE:
        return _EMB_CACHE[db_path]
    import numpy as np
    conn = sqlite3.connect(db_path)
    try:
        schema = _tables(conn)
    finally:
        conn.close()
    names = list(schema.keys())
    docs = [_table_doc(t, schema[t]) for t in names]
    emb = _get_embedder(model_name).encode(docs, normalize_embeddings=True)
    emb = np.asarray(emb, dtype="float32")
    _EMB_CACHE[db_path] = (names, emb)
    return names, emb


def link_schema_emb(
    db_path: str, question: str, evidence: str = "", k: int = 5,
    model_name: str = "all-MiniLM-L6-v2",
) -> list[str]:
    """Top-k tables by cosine similarity between table docs and question+evidence."""
    import numpy as np
    names, emb = _db_table_embeddings(db_path, model_name)
    if len(names) <= k:
        return names
    q = _get_embedder(model_name).encode(
        [f"{question} {evidence}".strip()], normalize_embeddings=True
    )
    q = np.asarray(q, dtype="float32")[0]
    sims = emb @ q  # cosine (both already normalized)
    idx = np.argsort(-sims)[:k]
    return [names[i] for i in idx]


# --- gold-table recall (linker evaluation, model-free) -----------------------

_GOLD_TBL = re.compile(r"\b(?:from|join)\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_SQL_KW = {"select", "where", "group", "order", "by", "having", "on", "as",
           "and", "or", "limit", "distinct", "count", "sum", "avg", "min", "max"}


def gold_tables(sql: str) -> set[str]:
    """Best-effort set of table names referenced in a (gold) SQL query."""
    cands = {m.lower() for m in _GOLD_TBL.findall(sql)}
    return {t for t in cands if t not in _SQL_KW}


def table_recall(kept: list[str], gold_sql: str) -> float | None:
    """Fraction of gold tables retained by the linker (None if no gold tables found)."""
    gold = gold_tables(gold_sql)
    if not gold:
        return None
    keptl = {t.lower() for t in kept}
    return len(gold & keptl) / len(gold)
