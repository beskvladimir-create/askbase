#!/usr/bin/env python3
"""Copy the publishable part of this repository into a clean public tree.

    python scripts/export_public.py --out ../askbase-public

The private repository stays the working one. What goes out is listed here
explicitly, as a whitelist, so that adding a file to the project never
publishes it by accident. The same pattern as pii-roundtrip.

What is deliberately kept private, and why:

  docs/design.md   the product design: the plan with day estimates, the pricing
                   reasoning, the open questions to the owner, and a frank note
                   that the moat is narrow. Useful to a competitor, and it is a
                   working document that changes weekly.
  docs/roles.md    which users are served and which are deliberately not. Same
                   reason.
(results/ used to be on this list. It is not any more: the six held-out runs
have been through the protocol end to end, including the hand review of
twenty failures each, their figures are on the site, and the ranking page
promises that the per-question predictions are published alongside every run
that is published, wrong ones included. A promise of verifiability that is
kept only for the numbers that flatter us is not one.)

One thing is redacted rather than withheld: the question wordings of held-out
set 2. Set 2 is live. Publishing its 1152 wordings would put them on the open
web, and the next model measured on it would have read them, which is the
contamination the paper's own limitations name as the reason BIRD figures
cannot be trusted. So the `TASKS_2` block of each domain module is emptied on
the way out, and everything else about the set goes out as usual: the freeze
digests in DIGESTS2.json, the gold query, the prediction and the verdict for
every single task in results/, and the hand review of the failures. A result
record carries no question text, so the ranking page's promise that per
question predictions are published with every run is kept literally.

The audit then refuses to hand over a tree in which any set 2 wording still
appears, so the redaction cannot be defeated by a copy of the text somewhere
else in the repository.

What goes out: the code, the held-out set generator, the benchmark harness, the
site, the market review and the administrator's documentation. All of it is
either verifiable by the reader or useful to them.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INCLUDE: tuple[str, ...] = (
    # The workflow has to travel with the code it checks: the public
    # repository is the one GitHub runs Actions for.
    ".github",
    "src",
    "scripts",
    "tests",
    "configs",
    "desktop",
    "site",
    "pyproject.toml",
    "docs/research.md",
    "docs/readonly-role.md",
    "README.md",
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "SECURITY.ru.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.ru.md",
    "HOLDOUT.md",
    "HOLDOUT.ru.md",
    # Every prediction of every published run, including the subdirectories
    # for the smoke test and for the runs withdrawn with a written reason.
    # Hiding a withdrawn run is how a withdrawal becomes indistinguishable
    # from a result that never existed.
    "results",
    ".gitignore.public",
)

# Renamed on the way out: the private repo ignores results/ and data/ for its
# own reasons, the public one needs its own list.
RENAME = {".gitignore.public": ".gitignore"}

# Never copied, whatever a glob above might pull in.
EXCLUDE_NAMES = {
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".venv", ".DS_Store", "_mobile.html", "uv.lock",
    # PyInstaller's working directory and output: machine-specific paths, and
    # a built application does not belong in a source repository anyway.
    "build", "dist",
}
# .jsonl is excluded everywhere except under results/, where it IS the
# per-question prediction file the protocol promises to publish.
EXCLUDE_SUFFIX = {".pyc", ".jsonl"}
JSONL_ALLOWED_UNDER = "results"
# icon.icns is binary and belongs in the package, so it is not excluded


def keep(path: Path) -> bool:
    if any(part in EXCLUDE_NAMES for part in path.parts):
        return False
    if path.suffix == ".jsonl":
        return JSONL_ALLOWED_UNDER in path.parts
    return path.suffix not in EXCLUDE_SUFFIX


# The six domain modules carry set 2 inline. `schema_spec.py` already
# declares `tasks_2: tuple[Task, ...] = field(default=())`, so an empty tuple
# imports and the DOMAIN definition below it needs no change.
#
# Found by the audit below: a regular expression cannot do this. The first
# version looked for the closing parenthesis in column zero, and several gold
# queries contain a line that is exactly ")", so it cut the block short and
# left half of set 2 behind as orphaned code in a file that no longer parsed.
# The parser knows where the statement ends, so the parser is asked.
TASKS_2_STUB = """\
# Набор 2 действующий отложенный набор: формулировки вопросов не публикуются,
# чтобы модель, которую на нём меряют, его не читала. Хеш заморозки лежит в
# DIGESTS2.json, а предсказание, эталонный запрос и вердикт по каждой задаче
# в results/. См. HOLDOUT.md, раздел про закрытые формулировки.
TASKS_2: tuple = ()
"""
DOMAINS_DIR = Path("src/nl2sql_app/holdout/domains")


def redact_set2(out: Path) -> list[Path]:
    """Replace the whole `TASKS_2` assignment in every exported domain module."""
    import ast

    touched: list[Path] = []
    for f in sorted((out / DOMAINS_DIR).glob("*.py")):
        text = f.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(f))
        node = next(
            (n for n in tree.body
             if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "TASKS_2" for t in n.targets)),
            None,
        )
        if node is None:
            continue
        lines = text.splitlines(keepends=True)
        cut = [*lines[: node.lineno - 1], TASKS_2_STUB, *lines[node.end_lineno:]]
        f.write_text("".join(cut), encoding="utf-8")
        # The file still has to be a module. A redaction that breaks the
        # import would be found by the public CI and not by us.
        ast.parse("".join(cut), filename=str(f))
        touched.append(f)
    if not touched:
        raise SystemExit(
            "ОТКАЗ: ни в одном модуле области не нашлось присваивание TASKS_2. "
            "Либо модули переименованы, либо набор лежит иначе, и тогда "
            "выгрузка опубликовала бы формулировки действующего набора."
        )
    return touched


# The hand review writes the question above the two queries, because a verdict
# on a failure cannot be read without it. That makes every reviewed set-2
# failure a published wording, which is the one thing being withheld, so the
# line is replaced on the way out. Everything else in the file stays: the gold
# query, the prediction, both result sets, the verdict and the note.
QUESTION_LINE = re.compile(r"^вопрос:.*$", re.M)
QUESTION_STUB = ("вопрос:  (не публикуется, набор 2 действующий; "
                 "см. HOLDOUT.md, раздел про закрытые формулировки)")


def redact_reviews(out: Path) -> list[Path]:
    """Drop the question text from the exported set-2 review files."""
    touched: list[Path] = []
    for f in sorted((out / "results").glob("*.set2-*.review.md")):
        text = f.read_text(encoding="utf-8")
        new_text, n = QUESTION_LINE.subn(QUESTION_STUB, text)
        if n:
            f.write_text(new_text, encoding="utf-8")
            touched.append(f)
    return touched


def set2_wordings() -> list[str]:
    """Every wording of set 2 that is not already public, for the audit.

    Three wordings are identical in both sets, written independently and come
    out the same because there are only so many ways to ask "which customers
    hold more than two accounts". Set 1 is published in full, so those three
    are public already and flagging them would make the check cry wolf about
    text it cannot withhold.
    """
    import json

    def read(root: str) -> set[str]:
        out: set[str] = set()
        for f in sorted((ROOT / root).glob("*/tasks.json")):
            for task in json.loads(f.read_text(encoding="utf-8")):
                out |= {w["text"].strip() for w in task["wordings"]}
        return out

    return sorted(read("data/holdout2") - read("data/holdout"))


def copy_into(out: Path) -> list[Path]:
    copied: list[Path] = []
    for item in INCLUDE:
        src = ROOT / item
        if not src.exists():
            raise SystemExit(f"нет в репозитории: {item}")
        if src.is_file():
            dst = out / RENAME.get(item, item)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(dst)
            continue
        for f in sorted(src.rglob("*")):
            if f.is_dir() or not keep(f.relative_to(ROOT)):
                continue
            dst = out / f.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            copied.append(dst)
    return copied


# Precise, because a check that cries wolf gets switched off. The loose
# version of this flagged a font called SpaceGrotesk-500 as an API key.
PATTERNS = (
    (re.compile(r"/Users/[a-z]", re.I), "абсолютный путь с именем пользователя"),
    (re.compile(r"[\w.+-]+@(?:gmail|yandex|mail|outlook)\.", re.I), "личная почта"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "токен GitHub"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "ключ OpenAI"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "ключ AWS"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "закрытый ключ"),
)


def audit(out: Path, wordings: list[str]) -> list[str]:
    """Last line of defence: refuse to hand over a tree with obvious problems."""
    bad: list[str] = []
    for f in sorted(out.rglob("*")):
        if f.is_dir() or f.suffix in {".png", ".ttf", ".ico", ".sqlite", ".svg"}:
            continue
        # The target can be a clone of the public repository, and then .git is
        # sitting in it. Its reflog records whoever ran the clone, with the
        # local git identity, so the check used to fail on the personal address
        # in .git/logs/HEAD. Repository metadata is not published content: git
        # never pushes a reflog. So the check reads the tree, not the clone's
        # bookkeeping.
        if ".git" in f.relative_to(out).parts:
            continue
        if f.name == "export_public.py":
            continue          # it is where the patterns are written down
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for rx, why in PATTERNS:
            m = rx.search(text)
            if m:
                line = text[: m.start()].count("\n") + 1
                bad.append(f"{f.relative_to(out)}:{line}: {why}")
        # The set 2 wordings, wherever they might have been copied to. One hit
        # is enough to stop the export: the set is only held out while nobody
        # can read it.
        for w in wordings:
            if w and w in text:
                line = text[: text.index(w)].count("\n") + 1
                bad.append(f"{f.relative_to(out)}:{line}: формулировка набора 2")
                break
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true", help="wipe the target tree first")
    args = ap.parse_args()

    out = Path(args.out).expanduser().resolve()
    if out.exists() and args.force:
        for child in out.iterdir():
            if child.name == ".git":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)

    copied = copy_into(out)
    redacted = redact_set2(out)
    reviews = redact_reviews(out)
    wordings = set2_wordings()
    if not wordings:
        raise SystemExit(
            "ОТКАЗ: data/holdout2 не сгенерирован, проверить выгрузку на "
            "утечку формулировок нечем. Сгенерируйте набор и повторите."
        )
    problems = audit(out, wordings)

    print(f"скопировано файлов: {len(copied)}")
    print(f"изъяты формулировки набора 2 из модулей: {len(redacted)}, "
          f"из файлов разбора: {len(reviews)}")
    print(f"каталог: {out}")
    print("\nне выгружается намеренно:")
    print("  docs/design.md   проект продукта: план, цены, открытые вопросы")
    print("  docs/roles.md    кого обслуживаем и кого нет")
    print("  формулировки набора 2: набор действующий, тексты вопросов закрыты,")
    print("                   эталон, предсказание и вердикт по каждой задаче в results/")

    if problems:
        print("\nПРОВЕРКА НЕ ПРОЙДЕНА:")
        for p in problems:
            print(f"  {p}")
        raise SystemExit(1)
    print("\nпроверка пройдена: личных путей, почты, ключей и формулировок "
          f"набора 2 не найдено ({len(wordings)} текстов проверено)")

    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    (out / "SOURCE_COMMIT").write_text(rev + "\n", encoding="utf-8")
    print(f"исходный коммит записан в SOURCE_COMMIT: {rev}")


if __name__ == "__main__":
    main()
