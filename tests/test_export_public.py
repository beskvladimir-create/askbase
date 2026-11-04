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

import export_public

# ---- the whitelist ---------------------------------------------------------

@pytest.mark.parametrize("private", [
    # docs/design.md and docs/roles.md are internal: they carry the plan, the
    # open questions and the owner's decisions. Only research.md and
    # readonly-role.md are meant to be read by anyone.
    "docs/design.md",
    "docs/roles.md",
    # Anything to do with keys.
    ".secrets/token",
    ".env",
])
def test_private_paths_are_not_in_the_whitelist(private):
    top = private.split("/")[0]
    assert private not in export_public.INCLUDE
    if top not in ("docs",):
        assert top not in export_public.INCLUDE, f"{top} открыт целиком"


def test_the_predictions_of_every_published_run_are_exported():
    """The ranking page promises them, so the export has to carry them.

    They were private while no run was published. The six held-out runs have
    since been through the protocol end to end, their figures are on the
    site, and the page says the per-question predictions are published
    alongside every published run, the wrong ones included. A promise of
    verifiability kept only for the numbers that flatter us is not one.

    The withdrawn runs under results/void/ travel too. Hiding a withdrawal is
    how it stops being distinguishable from a result that never existed.
    """
    assert "results" in export_public.INCLUDE
    assert export_public.keep(pathlib.Path("results/m.holdout-en.jsonl"))
    assert export_public.keep(pathlib.Path("results/m.holdout-en.review.md"))
    assert export_public.keep(pathlib.Path("results/void/README.md"))
    # In this repository the file is .gitignore.public; in the exported tree
    # it has already been renamed, and this test travels with it.
    here = pathlib.Path(__file__).resolve().parent.parent
    ignore = next(p for p in (here / ".gitignore.public", here / ".gitignore")
                  if p.is_file())
    assert "results/" not in ignore.read_text()


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
    # A prediction file is the one .jsonl that travels, because the ranking
    # page promises the per-question predictions of every published run.
    ("results/run.jsonl", True),
    ("results/void/withdrawn.jsonl", True),
    ("logs/anything.jsonl", False),
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
    found = export_public.audit(out, [])
    assert found, f"не поймано: {why}"
    assert "src/thing.py" in found[0]


def test_the_audit_passes_a_clean_tree(tmp_path):
    out = _tree(tmp_path, "src/thing.py", "def add(a, b):\n    return a + b\n")
    assert export_public.audit(out, []) == []


def test_the_audit_does_not_cry_wolf_over_a_font_name(tmp_path):
    # The loose version of these patterns flagged SpaceGrotesk-500 as an API
    # key, and a check that cries wolf gets switched off.
    out = _tree(tmp_path, "site/assets/style.css",
                "@font-face { src: url('/assets/SpaceGrotesk-500.woff2'); }")
    assert export_public.audit(out, []) == []


def test_the_audit_reads_every_text_file_not_only_python(tmp_path):
    out = _tree(tmp_path, "site/pages/index.html",
                "<p>write to me at " + "someone" + "@" + "yandex" + ".ru</p>")
    assert export_public.audit(out, []), "аудит не читает html"


def test_the_audit_reports_the_line_number(tmp_path):
    out = _tree(tmp_path, "src/a.py", "ok = 1\nok = 2\nbad = '" + "/Us" + "ers/x/y'\n")
    assert export_public.audit(out, [])[0].endswith(":3: абсолютный путь с именем пользователя")


def test_the_audit_ignores_the_clones_own_git_directory(tmp_path):
    # Exporting into a clone of the public repository put .git in the tree, and
    # its reflog carries whoever ran the clone, with the personal address. That
    # is local bookkeeping: git does not push a reflog. A check that fails on it
    # is a check that gets switched off.
    out = _tree(tmp_path, ".git/logs/HEAD",
                "0000 e49d70a Vladimir <" + "beskvladimir" + "@" + "gmail" + ".com> 1793788501 +0400\tclone\n")
    assert export_public.audit(out, []) == []


def test_the_audit_still_reads_a_file_whose_name_merely_starts_with_git(tmp_path):
    out = _tree(tmp_path, "gitignore-notes.md",
                "write to me at " + "someone" + "@" + "gmail" + ".com")
    assert export_public.audit(out, []), "аудит пропустил обычный файл"


def test_a_missing_whitelisted_path_stops_the_export(tmp_path, monkeypatch):
    # Silently skipping a missing entry would publish a tree with a hole in it.
    monkeypatch.setattr(export_public, "INCLUDE", ("no-such-thing",))
    with pytest.raises(SystemExit):
        export_public.copy_into(tmp_path / "out")


def test_the_public_gitignore_is_renamed_on_the_way_out(tmp_path):
    assert export_public.RENAME[".gitignore.public"] == ".gitignore"
    assert ".gitignore.public" in export_public.INCLUDE
    assert ".gitignore" not in export_public.INCLUDE


# ---- the live set --------------------------------------------------------
#
# Set 2 is the one thing redacted rather than withheld, and the redaction has
# to survive the shape of the file it edits. The first version used a regular
# expression, several gold queries contain a line that is exactly ")", and it
# cut the block in half and left a module that no longer parsed. These pin the
# two properties that matter: nothing of set 2 survives, and what survives is
# still a module.

SAMPLE_DOMAIN = '''\
"""Домен для теста."""
TASKS = (
    Task(tid="x-001", gold_sql="""
SELECT a
FROM t
WHERE b IN (
    SELECT c FROM u
)
"""),
)

TASKS_2 = (
    Task(tid="x2-001", gold_sql="""
SELECT a
FROM t
WHERE b IN (
    SELECT c FROM u
)
""", en=("Secret question of set two?",)),
)

DOMAIN = Domain(name="x", tasks=TASKS, tasks_2=TASKS_2)
'''


def _domain_tree(tmp_path, body=SAMPLE_DOMAIN):
    f = tmp_path / export_public.DOMAINS_DIR / "x.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return tmp_path


def test_the_redaction_empties_set_two_and_leaves_a_module(tmp_path):
    out = _domain_tree(tmp_path)
    assert export_public.redact_set2(out)
    text = (out / export_public.DOMAINS_DIR / "x.py").read_text(encoding="utf-8")
    assert "TASKS_2: tuple = ()" in text
    assert "Secret question of set two?" not in text
    # Set 1 is published in full and must come through untouched, including
    # the gold query whose closing parenthesis sits in column zero.
    assert 'tid="x-001"' in text
    assert "SELECT c FROM u" in text
    assert "DOMAIN = Domain(" in text
    compile(text, "x.py", "exec")


def test_the_redaction_refuses_a_tree_with_no_tasks_to_redact(tmp_path):
    out = _domain_tree(tmp_path, '"""Пусто."""\nTASKS = ()\n')
    with pytest.raises(SystemExit):
        export_public.redact_set2(out)


def test_the_audit_catches_a_planted_set_two_wording(tmp_path):
    out = _tree(tmp_path, "docs/notes.md", "note: Secret question of set two?")
    found = export_public.audit(out, ["Secret question of set two?"])
    assert found and found[0].endswith(":1: формулировка набора 2")


def test_the_review_files_lose_the_question_and_keep_everything_else(tmp_path):
    body = ("## 1. hr/hr2-005 ru/1\n\n"
            "ловушка: что-то\n"
            "вопрос:  Secret question of set two?\n\n"
            "эталон:\n    SELECT 1\n\n"
            "вердикт: model\n")
    out = _tree(tmp_path, "results/m.set2-base-ru.review.md", body)
    assert export_public.redact_reviews(out)
    text = (out / "results/m.set2-base-ru.review.md").read_text(encoding="utf-8")
    assert "Secret question of set two?" not in text
    assert "не публикуется" in text
    for keep in ("ловушка: что-то", "SELECT 1", "вердикт: model"):
        assert keep in text


def test_the_review_files_of_set_one_are_left_alone(tmp_path):
    # Set 1 is spent and published in full, questions included.
    out = _tree(tmp_path, "results/m.holdout-ru.review.md",
                "вопрос:  Сколько счетов?\n")
    assert export_public.redact_reviews(out) == []
    assert "Сколько счетов?" in (
        out / "results/m.holdout-ru.review.md").read_text(encoding="utf-8")
