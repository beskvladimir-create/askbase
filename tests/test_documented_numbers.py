"""The test count printed in the documentation is the real one.

It went stale within a day of being written: CONTRIBUTING said 669 and "there
is no CI yet" while the workflow was already running 680. A number in prose is
a number nobody re-derives, which is the same failure the site build guards
against by refusing a figure no results file backs. This does the same for the
documents, so the next person to add a test is told to update them.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ("README.md", "CONTRIBUTING.md", "CONTRIBUTING.ru.md")
# Russian agrees the noun with the number: 684 теста, 685 тестов, 681 тест.
QUOTED = re.compile(r"#\s*(\d+)\s+(?:tests|тест(?:а|ов)?), ")


def collected(python: Path, args: list[str], cwd: Path) -> int:
    r = subprocess.run(
        [str(python), "-m", "pytest", *args, "-q", "-p", "no:cacheprovider",
         "--collect-only"],
        cwd=cwd, capture_output=True, text=True, check=False,
    )
    m = re.search(r"(\d+) tests collected", r.stdout)
    # Not a skip. A guard that quietly stops guarding when the command changes
    # is the thing it was written to prevent.
    assert m, f"не удалось собрать {args}:\n{r.stdout[-400:]}\n{r.stderr[-400:]}"
    return int(m.group(1))


@pytest.fixture(scope="module")
def total() -> int:
    """Every suite scripts/test_all.sh runs, split exactly as it splits them.

    The three commands are not interchangeable: the benchmark environment has
    no Qt and cannot even collect the interface suite, and the desktop suite
    runs from desktop/ with its own rootdir.
    """
    bench = ROOT / ".venv" / "bin" / "python"
    qt = ROOT / "desktop" / ".venv" / "bin" / "python"
    if not bench.exists() or not qt.exists():
        pytest.skip("нужны обе среды, как у scripts/test_all.sh")
    return (
        collected(bench, ["tests", "--ignore=tests/test_window.py"], ROOT)
        + collected(qt, ["tests/test_window.py"], ROOT)
        + collected(qt, ["tests"], ROOT / "desktop")
    )


@pytest.mark.parametrize("name", DOCS)
def test_the_documented_test_count_is_the_real_one(name, total):
    text = (ROOT / name).read_text(encoding="utf-8")
    found = [int(m) for m in QUOTED.findall(text)]
    assert found, f"{name}: не нашёл строку с числом тестов"
    for n in found:
        assert n == total, f"{name}: написано {n}, а тестов {total}"


def test_contributing_does_not_claim_there_is_no_ci():
    # The workflow exists and runs on every push. A document saying otherwise
    # is the kind of thing a reviewer checks first.
    assert (ROOT / ".github" / "workflows" / "tests.yml").exists()
    for name in ("CONTRIBUTING.md", "CONTRIBUTING.ru.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "no CI yet" not in text
        assert "Непрерывной интеграции пока нет" not in text
