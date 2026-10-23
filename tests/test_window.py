"""Build the real window, in both languages, off-screen.

Every other test here avoids Qt, which is why a leftover reference to a
deleted name reached a packaged build and stopped it from starting at all.
Constructing the window once per language catches that class of mistake for
the price of a second.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESKTOP = Path(__file__).resolve().parent.parent / "desktop"
sys.path.insert(0, str(DESKTOP))

pytest.importorskip("PySide6", reason="интерфейс проверяется там, где установлен Qt")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    from askbase import theme

    a = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])
    theme.apply(a)
    return a


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_the_window_builds(app, lang):
    from askbase.app import Window

    w = Window(lang)
    assert w.pages.count() == 3
    assert w.windowTitle()
    w.close()


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_every_screen_can_be_shown(app, lang):
    from askbase.app import Window

    w = Window(lang)
    for i in range(w.pages.count()):
        w.pages.setCurrentIndex(i)
        assert w.pages.currentWidget() is not None
    w.close()


def test_the_about_window_opens_and_closes(app, monkeypatch):
    from askbase.app import Window

    w = Window("ru")
    shown = {}
    monkeypatch.setattr("PySide6.QtWidgets.QDialog.exec", lambda self: shown.setdefault("yes", True))
    w._about()
    assert shown
    w.close()


def test_a_typed_path_that_does_not_exist_is_reported_not_raised(app):
    from askbase.app import Window

    w = Window("ru")
    w.path.setText("/nope/not/here.sqlite")
    w._open_typed()                      # must not raise
    assert w.status.text()
    w.close()


def test_a_pasted_file_url_is_understood(app, tmp_path):
    # Dragging from Finder into a terminal, or copying a path, often yields
    # file:// with percent escapes.
    from askbase.app import Window

    db = tmp_path / "my db.sqlite"
    db.write_bytes(b"")
    w = Window("ru")
    w.path.setText(f"file://{db}".replace(" ", "%20"))
    w._open_typed()
    assert "not_a_file" not in w.status.text()
    w.close()
