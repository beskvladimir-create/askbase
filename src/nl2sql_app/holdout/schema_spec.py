"""Building blocks for a holdout domain: the schema, its data, and its tasks.

A domain is declared as data, not as code that writes SQL strings by hand, so
that the generator can guarantee byte-identical output and the tests can check
determinism without running a model.

Design rule for every domain, from docs/design.md section 2.2: the schema must
carry the warts of a real database, because that is what the benchmark is for.
RedSQL's own limitation is that its schemas are clean and synthetic. Ours get
opaque column names, code lookups instead of words, a legacy duplicate column,
and no comments. A model that only works on tidy schemas must fail here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Table:
    name: str
    ddl: str
    # Columns whose values are codes rather than words. The engine's value
    # grounding feature targets exactly these, and the benchmark must contain
    # them or that feature is untested.
    coded_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class Task:
    """One question, in four wordings, against one gold query.

    The four wordings share the gold SQL on purpose: that is what makes the
    language gap measurable on an identical target, which no published set has.
    `en` and `ru` each hold two independent phrasings. The Russian ones are
    written from the meaning, never translated from the English, or the measure
    collapses into a translation-quality test.
    """

    tid: str
    gold_sql: str
    en: tuple[str, str]
    ru: tuple[str, str]
    # Why this task is hard, kept for the error analysis in the report.
    traps: tuple[str, ...] = ()

    def wordings(self) -> list[tuple[str, int, str]]:
        """(language, index, text) for every wording, in a fixed order."""
        return (
            [("en", i, q) for i, q in enumerate(self.en)]
            + [("ru", i, q) for i, q in enumerate(self.ru)]
        )


@dataclass(frozen=True)
class Domain:
    name: str
    tables: tuple[Table, ...]
    tasks: tuple[Task, ...] = field(default=())
    # Rows per table, fixed so the data is reproducible and small enough that a
    # gold query's result set is stable and quick to compare.
    row_counts: dict[str, int] = field(default_factory=dict)

    def ddl(self) -> str:
        # Each statement gets its own terminator: executescript() needs them,
        # and the same text is what a model is shown as the schema.
        return "\n\n".join(t.ddl.strip().rstrip(";") + ";" for t in self.tables)
