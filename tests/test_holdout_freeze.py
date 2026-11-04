"""The freeze, and the machinery that makes it more than a promise.

Three things can quietly undo a pre-registration, and there is a test here for
each. The recorded digests can stop matching what the generator produces. The
document and the machine-readable copy can drift apart, so that the file a
reader checks and the file the code checks say different things. And the
verifier can be lenient about exactly the cases it exists to catch.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nl2sql_app.holdout import verify
from nl2sql_app.holdout.generate import DOMAINS

ROOT = Path(__file__).resolve().parent.parent
DOC_EN = ROOT / "HOLDOUT.md"
DOC_RU = ROOT / "HOLDOUT.ru.md"


@pytest.fixture(scope="module")
def frozen(frozen_holdout) -> Path:
    """Regenerate the whole set from the recorded seed and date.

    The generation itself lives in conftest, because the stage tests need the
    same set and neither suite may read it off `data/holdout`: that directory
    is not in the public export, so a disk-backed fixture skips on GitHub.
    """
    return frozen_holdout


def test_the_recorded_command_reproduces_every_recorded_digest(frozen):
    # The whole freeze rests on this. If it ever fails, either the generator
    # changed or the digests did, and neither may happen silently.
    assert verify.check_set(frozen) == verify.expected()["domains"]


def test_the_document_and_the_machine_readable_copy_agree():
    # A digest a human checks in HOLDOUT.md and a digest the code checks in
    # DIGESTS.json have to be the same digest. Two sources of truth is one too
    # many, and the one that drifts is always the one nobody runs.
    digests = verify.expected()["domains"]
    for doc in (DOC_EN, DOC_RU):
        text = doc.read_text(encoding="utf-8")
        for name, digest in digests.items():
            assert digest in text, f"{doc.name}: нет хеша для {name}"
            assert name in text, f"{doc.name}: не упомянута область {name}"


def test_the_freeze_covers_every_domain_the_generator_knows():
    # A domain added to the generator and not to the freeze would be a domain
    # outside the pre-registration, available to be included after the fact.
    assert set(verify.expected()["domains"]) == set(DOMAINS)


def test_a_changed_set_is_refused(frozen, tmp_path):
    import shutil
    copy = tmp_path / "tampered"
    shutil.copytree(frozen, copy)
    target = copy / "hr" / "canonical.json"
    target.write_text(target.read_text(encoding="utf-8").replace("hr", "hr ", 1),
                      encoding="utf-8")
    with pytest.raises(verify.NotFrozen) as e:
        verify.check_set(copy)
    assert "hr" in str(e.value)


def test_a_missing_domain_is_refused_not_skipped(frozen, tmp_path):
    import shutil
    copy = tmp_path / "partial"
    shutil.copytree(frozen, copy)
    shutil.rmtree(copy / "medicine")
    # Running five of six and publishing the number is the quiet version of
    # choosing the sample after looking at it.
    with pytest.raises(verify.NotFrozen) as e:
        verify.check_set(copy)
    assert "medicine" in str(e.value)


def test_an_extra_domain_is_refused(frozen, tmp_path):
    import shutil
    copy = tmp_path / "extra"
    shutil.copytree(frozen, copy)
    (copy / "invented").mkdir()
    with pytest.raises(verify.NotFrozen) as e:
        verify.check_set(copy)
    assert "invented" in str(e.value)


def test_a_second_run_of_the_same_tool_needs_a_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    first = verify.record("xiyan-7b-q4", 1)
    assert first["repeat"] == 0

    with pytest.raises(verify.NotFrozen) as e:
        verify.record("xiyan-7b-q4", 1)
    assert "xiyan-7b-q4" in str(e.value)

    second = verify.record("xiyan-7b-q4", 1, reason="оценщик исправлен")
    assert second["repeat"] == 1
    assert second["reason"] == "оценщик исправлен"

    rows = [json.loads(ln) for ln in
            verify.JOURNAL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [r["repeat"] for r in rows] == [0, 1]
    # The reason stays in the journal: that is the only thing making a repeat
    # cost anything.
    assert rows[1]["reason"] == "оценщик исправлен"


def test_a_different_tool_on_the_same_set_is_not_a_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    verify.record("xiyan-7b-q4", 1)
    assert verify.record("arctic-7b-q4", 1)["repeat"] == 0


def test_every_run_records_the_commit_it_ran_from(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    row = verify.record("ours", 1)
    assert row["commit"] and row["commit"] != "unknown"
    assert row["at"].startswith("20")


def test_the_document_states_what_the_set_cannot_decide():
    # The power statement is load-bearing: without it a reader takes an
    # undetermined verdict for a weak result rather than for the expected one.
    en = DOC_EN.read_text(encoding="utf-8")
    ru = DOC_RU.read_text(encoding="utf-8")
    assert "undetermined" in en and "не определено" in ru
    assert "48" in en and "48" in ru


@pytest.mark.parametrize("domain", ["banking", "hr", "logistics",
                                    "manufacturing", "medicine", "public_services"])
def test_set_two_cannot_disturb_set_one(domain, tmp_path):
    """Growing set 2 must leave set 1 byte for byte where it was frozen.

    Set 1's SHA-256 covers its task list, and `verify.py` refuses to run a
    tool on a set whose digest does not match. If a task added for set 2 ever
    landed in the set 1 tuple, every figure already published would become
    unreproducible, and the failure would look like a hashing bug rather than
    like what it is. So the digest is recomputed here from the code as it
    stands, against the number recorded on the day of the freeze.
    """
    import subprocess
    import sys

    out = tmp_path / "regenerated"
    subprocess.run(
        [sys.executable, "-m", "nl2sql_app.holdout.generate", "--domain", domain,
         "--seed", "20261027", "--now", "2026-10-27", "--out", str(out)],
        check=True, capture_output=True,
    )
    frozen = json.loads(
        Path("src/nl2sql_app/holdout/DIGESTS.json").read_text(encoding="utf-8"))
    got = (out / domain / "SHA256").read_text().strip()
    assert got == frozen["domains"][domain], f"{domain}: набор 1 сдвинулся"


# --- набор 2, заморожен 2 ноября 2026 ---------------------------------------
#
# Written in two passes of 24 tasks per domain and frozen when the second
# finished: 288 tasks, 1152 wordings. These are now freeze tests like the ones
# above. The set has to regenerate identically from its recorded seed, the
# documents have to quote the digests the code checks, it must not have become
# a copy of the spent set, every task must declare a trap, and the authoring
# rules must still pass on all of it. The guard that refuses a run against an
# unfrozen set is tested against a registry built for the purpose, because set
# 2 can no longer provide one and the guard outlives it.


@pytest.fixture(scope="module")
def pass_two(frozen_holdout_2) -> Path:
    return frozen_holdout_2


def test_set_two_regenerates_identically_from_its_seed(pass_two):
    assert verify.check_set(pass_two, 2) == verify.expected(2)["domains"]


def test_set_two_is_frozen_and_says_when():
    want = verify.expected(2)
    assert want["frozen"] is True
    assert want["frozen_at"] == "2026-11-02"
    assert want["tasks_per_domain"] == 48


def test_the_set_two_documents_quote_the_digests_the_code_checks():
    # Same reason as for set 1: a digest a reader verifies in HOLDOUT.md and a
    # digest verify.py enforces have to be one digest.
    digests = verify.expected(2)["domains"]
    for doc in (DOC_EN, DOC_RU):
        text = doc.read_text(encoding="utf-8")
        for name, digest in digests.items():
            assert digest in text, f"{doc.name}: нет хеша набора 2 для {name}"


def test_no_tool_can_be_recorded_against_an_unfrozen_set(tmp_path, monkeypatch):
    """The guard outlives the set it was written for.

    Until 2 November this asserted against set 2 itself, which was the honest
    thing while set 2 was half written. Now that it is frozen the guard needs
    its own unfrozen registry, otherwise the test would have to be deleted
    together with the thing it protects, and the next set would be authored
    without it.
    """
    registry = tmp_path / "DIGESTS3.json"
    registry.write_text(json.dumps({
        "set": 3, "frozen": False, "tasks_per_domain": 48,
        "note": "в написании", "domains": {},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setitem(verify.REGISTRY, 3, registry)
    monkeypatch.setattr(verify, "JOURNAL", tmp_path / "holdout_runs.jsonl")
    with pytest.raises(verify.NotFrozen) as e:
        verify.record("qwen25-coder-14b", 3)
    assert "не заморожен" in str(e.value)
    # The frozen sets are unaffected, and a missing flag means frozen.
    assert verify.record("qwen25-coder-14b", 1)["repeat"] == 0
    assert verify.record("qwen25-coder-14b", 2)["repeat"] == 0


def test_the_two_sets_do_not_share_a_digest():
    one = verify.expected(1)["domains"]
    two = verify.expected(2)["domains"]
    assert set(one) == set(two)
    for name in one:
        assert one[name] != two[name], f"{name}: набор 2 совпал с набором 1"


def test_set_two_covers_every_domain_the_generator_knows():
    assert set(verify.expected(2)["domains"]) == set(DOMAINS)


def test_each_domain_holds_the_recorded_number_of_tasks(pass_two):
    """The target lives in the registry, so one number states the whole size.

    The spec asked for 100 per domain. A schema carries about 24 honest tasks
    per pass before the traps start repeating, and the amended target of 48
    and its cost in interval width are recorded in HOLDOUT.md, dated, before
    the second pass was written.

    While the set was being authored this assertion was one-sided, because a
    domain could be short of the target between the two passes. The freeze
    makes it exact, which is what makes the size a pre-registration rather
    than a wish.
    """
    want = verify.expected(2)["tasks_per_domain"]
    total = 0
    for name in sorted(verify.expected(2)["domains"]):
        tasks = json.loads((pass_two / name / "tasks.json").read_text(encoding="utf-8"))
        tasks = tasks if isinstance(tasks, list) else tasks["tasks"]
        assert len(tasks) == want, f"{name}: {len(tasks)} задач, а не {want}"
        total += len(tasks)
    assert total == 288


def test_every_set_two_task_declares_a_trap(pass_two):
    """A task with no trap measures nothing this benchmark exists to measure.

    The linter checks it while authoring; this keeps it checked against a
    later edit that drops the field.
    """
    for name in sorted(verify.expected(2)["domains"]):
        tasks = json.loads((pass_two / name / "tasks.json").read_text(encoding="utf-8"))
        tasks = tasks if isinstance(tasks, list) else tasks["tasks"]
        for t in tasks:
            assert t.get("traps"), f"{name}/{t['tid']}: ловушек не объявлено"


def test_the_authoring_rules_pass_on_all_of_set_two(pass_two):
    """The linter against the real set, not only against its own fixtures.

    Every rule exists because set 1 shipped with a defect of that shape and
    the freeze meant it had to stay. A finding here is a defect to fix before
    the set is frozen, which is the only time it can still be fixed.
    """
    from nl2sql_app.holdout.lint import lint_set

    findings, rows = lint_set(str(pass_two))
    assert rows, "линтер не прочитал ни одной задачи"
    assert not findings, "\n".join(f"{f.tid}: {f.rule}: {f.detail}" for f in findings)


def test_an_unknown_set_is_refused():
    with pytest.raises(verify.NotFrozen):
        verify.expected(3)
