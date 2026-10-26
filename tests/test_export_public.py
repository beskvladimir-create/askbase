"""The whitelist and the audit that stand between this repo and a public one.

165 lines with no test, and the failure mode is a publication: irreversible,
and the sort of thing that is noticed by somebody else. The two properties that
matter are that the whitelist excludes what it claims, and that the audit
actually catches a planted secret rather than merely existing.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import export_public  # noqa: E402


# ---- the whitelist ---------------------------------------------------------

@pytest.mark.parametrize("private", [
    # docs/design.md and docs/roles.md are internal: they carry the plan, the
    # open questions and the owner's decisions. Only research.md and
    # readonly-role.md are meant to be read by anyone.
    "docs/design.md",
    "docs/roles.md",
    # Measurements, raw predictions and the voided runs.
    "results/xiyan-7b-q4.base.jsonl",
    "results/void/arctic-7b-q4.base.summary.json",
    # Anything to do with keys.
    ".secrets/token",
    ".env",
])
def test_private_paths_are_not_in_the_whitelist(private):
    top = private.split("/")[0]
    assert private not in export_public.INCLUDE
    if top not in ("docs",):
        assert top not in export_public.INCLUDE, f"{top} открыт целиком"


def test_docs_are_listed_file_by_file_not_as_a_directory():
    # The one directory that must never be copied wholesale, because it holds
    # both the two public documents and the internal plan.
    assert "docs" not in export_public.INCLUDE
    docs = [i for i in export_public.INCLUDE if i.startswith("docs/")]
    assert sorted(docs) == ["docs/readonly-role.md", "docs/research.md"]


@pytest.mark.parametrize("path,kept", [
    ("src/nl2sql_app/safety.py", True),
    ("desktop/askbase/app.py", True),
    ("site/pages/index.html", True),
    ("src/__pycache__/x.pyc", False),
    ("desktop/.venv/lib/thing.py", False),
    ("desktop/dist/Askbase.app/x", False),
    ("desktop/build/x", False),
    ("results/run.jsonl", False),
    ("site/_mobile.html", False),
    ("src/.DS_Store", False),
])
def test_keep_excludes_what_it_claims(path, kept):
    assert export_public.keep(pathlib.Path(path)) is kept


# ---- the audit -------------------------------------------------------------

def _tree(tmp_path, name, body):
    f = tmp_path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return tmp_path


# Assembled from pieces rather than written out, because this file is itself
# exported and the audit reads it: spelled in full, the samples below are
# exactly what the audit is looking for, and it correctly refused the whole
# export over them. Exempting the file by name was the other option and is
# worse, since a real secret in it would then pass.
_U = "/Us" + "ers/someone/Desktop/db.sqlite"
_MAIL = "person" + "@" + "gmail" + ".com"
_GH = "gh" + "p_" + "a" * 36
_OAI = "sk" + "-" + "b" * 32
_AWS = "AK" + "IA" + "C" * 16
_KEY = "-----BE" + "GIN RSA PRIVATE KEY-----"


@pytest.mark.parametrize("body,why", [
    (f"path = '{_U}'", "абсолютный путь"),
    (f"contact: {_MAIL}", "личная почта"),
    (f"token = '{_GH}'", "токен GitHub"),
    (f"key = '{_OAI}'", "ключ OpenAI"),
    (f"aws = '{_AWS}'", "ключ AWS"),
    (_KEY, "закрытый ключ"),
])
def test_the_audit_catches_a_planted_secret(tmp_path, body, why):
    out = _tree(tmp_path, "src/thing.py", body)
    found = export_public.audit(out)
    assert found, f"не поймано: {why}"
    assert "src/thing.py" in found[0]


def test_the_audit_passes_a_clean_tree(tmp_path):
    out = _tree(tmp_path, "src/thing.py", "def add(a, b):\n    return a + b\n")
    assert export_public.audit(out) == []


def test_the_audit_does_not_cry_wolf_over_a_font_name(tmp_path):
    # The loose version of these patterns flagged SpaceGrotesk-500 as an API
    # key, and a check that cries wolf gets switched off.
    out = _tree(tmp_path, "site/assets/style.css",
                "@font-face { src: url('/assets/SpaceGrotesk-500.woff2'); }")
    assert export_public.audit(out) == []


def test_the_audit_reads_every_text_file_not_only_python(tmp_path):
    out = _tree(tmp_path, "site/pages/index.html",
                "<p>write to me at " + "someone" + "@" + "yandex" + ".ru</p>")
    assert export_public.audit(out), "аудит не читает html"


def test_the_audit_reports_the_line_number(tmp_path):
    out = _tree(tmp_path, "src/a.py", "ok = 1\nok = 2\nbad = '" + "/Us" + "ers/x/y'\n")
    assert export_public.audit(out)[0].endswith(":3: абсолютный путь с именем пользователя")


def test_a_missing_whitelisted_path_stops_the_export(tmp_path, monkeypatch):
    # Silently skipping a missing entry would publish a tree with a hole in it.
    monkeypatch.setattr(export_public, "INCLUDE", ("no-such-thing",))
    with pytest.raises(SystemExit):
        export_public.copy_into(tmp_path / "out")


def test_the_public_gitignore_is_renamed_on_the_way_out(tmp_path):
    assert export_public.RENAME[".gitignore.public"] == ".gitignore"
    assert ".gitignore.public" in export_public.INCLUDE
    assert ".gitignore" not in export_public.INCLUDE
