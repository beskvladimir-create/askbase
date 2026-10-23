"""Both languages must carry the same keys, or a window comes out half-translated.

A missing key is a KeyError at the worst moment, in front of whoever opened the
application, so it is caught here instead.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

DESKTOP = Path(__file__).resolve().parent.parent / "desktop"
sys.path.insert(0, str(DESKTOP))
from askbase import i18n  # noqa: E402


def test_the_two_languages_have_the_same_keys():
    ru, en = set(i18n.TEXTS["ru"]), set(i18n.TEXTS["en"])
    assert ru == en, f"только в ru: {ru - en}; только в en: {en - ru}"


def test_nothing_is_empty():
    for lang, table in i18n.TEXTS.items():
        for key, value in table.items():
            assert value.strip(), f"{lang}.{key} пусто"


def test_placeholders_match_between_languages():
    # "{path}" in one language and "{file}" in the other is a crash waiting
    # for whoever switches language at the wrong moment.
    for key in i18n.TEXTS["ru"]:
        ru = set(re.findall(r"\{(\w+)", i18n.TEXTS["ru"][key]))
        en = set(re.findall(r"\{(\w+)", i18n.TEXTS["en"][key]))
        assert ru == en, f"{key}: подстановки различаются, ru={ru} en={en}"


def test_the_english_table_holds_no_cyrillic():
    for key, value in i18n.TEXTS["en"].items():
        assert not re.search(r"[А-Яа-яЁё]", value), f"en.{key} содержит кириллицу"


def test_the_keys_the_drop_zone_reads_exist():
    # DropZone reads these four directly and raises KeyError without them,
    # which is how the window failed to open once already.
    for key in ("drop_title", "drop_sub", "drop_release", "choose_file"):
        for lang in i18n.TEXTS:
            assert key in i18n.TEXTS[lang], f"{lang} не хватает {key}"


def test_every_key_used_in_the_window_is_defined():
    source = (DESKTOP / "askbase" / "app.py").read_text(encoding="utf-8")
    used = set(re.findall(r'self\.t\[\s*"(\w+)"\s*\]', source))
    used |= set(re.findall(r'self\.t\.get\(\s*"(\w+)"', source))
    missing = {k for k in used if k not in i18n.TEXTS["ru"]}
    assert not missing, f"в коде есть, в переводах нет: {sorted(missing)}"


def test_the_window_has_no_hardcoded_russian_left():
    source = (DESKTOP / "askbase" / "app.py").read_text(encoding="utf-8")
    # comments are prose for the reader, string literals are the interface
    literals = re.findall(r'"([^"\n]*[А-Яа-яЁё][^"\n]*)"', source)
    assert not literals, f"строки мимо перевода: {literals}"


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_the_step_names_the_engine_emits_are_translated(lang):
    for step in ("writing", "checking", "fixing", "running"):
        assert step in i18n.TEXTS[lang]
