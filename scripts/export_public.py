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


def audit(out: Path) -> list[str]:
    """Last line of defence: refuse to hand over a tree with obvious problems."""
    bad: list[str] = []
    for f in sorted(out.rglob("*")):
        if f.is_dir() or f.suffix in {".png", ".ttf", ".ico", ".sqlite", ".svg"}:
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
    problems = audit(out)

    print(f"скопировано файлов: {len(copied)}")
    print(f"каталог: {out}")
    print("\nне выгружается намеренно:")
    print("  docs/design.md   проект продукта: план, цены, открытые вопросы")
    print("  docs/roles.md    кого обслуживаем и кого нет")

    if problems:
        print("\nПРОВЕРКА НЕ ПРОЙДЕНА:")
        for p in problems:
            print(f"  {p}")
        raise SystemExit(1)
    print("\nпроверка пройдена: личных путей, почты и ключей не найдено")

    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    (out / "SOURCE_COMMIT").write_text(rev + "\n", encoding="utf-8")
    print(f"исходный коммит записан в SOURCE_COMMIT: {rev}")


if __name__ == "__main__":
    main()
