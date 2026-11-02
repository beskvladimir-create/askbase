"""Everything the application imports from the research package is packaged.

The built application has no source tree beside it. An import that works in
development because `../src` is on the path, and is not listed in the spec,
fails only in the signed .app on somebody else's machine, which is the most
expensive place to find out. The spec is therefore checked against the
imports rather than kept in step by memory.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
SPEC = APP / "askbase.spec"
IMPORT = re.compile(r"^(?:from|import)\s+(nl2sql_app(?:\.[\w.]+)?)", re.M)


def test_every_nl2sql_app_import_is_in_the_spec():
    spec = SPEC.read_text(encoding="utf-8")
    wanted = set()
    for src in sorted((APP / "askbase").glob("*.py")):
        for m in IMPORT.finditer(src.read_text(encoding="utf-8")):
            # `from nl2sql_app.bench.annotate import x` needs the module, and
            # PyInstaller needs each package above it to exist in the bundle.
            parts = m.group(1).split(".")
            wanted |= {".".join(parts[: i + 1]) for i in range(len(parts))}
    assert wanted, "no imports found, so this test is checking nothing"
    missing = sorted(w for w in wanted if f'"{w}"' not in spec)
    assert not missing, f"not in askbase.spec hiddenimports: {missing}"
