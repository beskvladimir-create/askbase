"""Build the real window, in both languages, off-screen.

Every other test here avoids Qt, which is why a leftover reference to a
deleted name reached a packaged build and stopped it from starting at all.
Constructing the window once per language catches that class of mistake for
the price of a second.
"""
from __future__ import annotations

import csv
import sys
import threading
from pathlib import Path

import pytest

DESKTOP = Path(__file__).resolve().parent.parent / "desktop"
sys.path.insert(0, str(DESKTOP))

pytest.importorskip("PySide6", reason="интерфейс проверяется там, где установлен Qt")

from askbase.engine import AskError  # noqa: E402


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
    # Reported in the alert, with the path in it and something to press next:
    # a failure is where the user most needs to be able to read and to act.
    assert not w.alert.isHidden()        # the window itself is never shown in a test
    assert "/nope/not/here.sqlite" in w.err_body.text()
    assert not w.err_do.isHidden()
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
class SlowEngine:
    """An engine that holds its thread until the test lets it finish."""

    def __init__(self):
        self.db_path = "сделано.sqlite"
        self.calls = 0
        self.go = threading.Event()

    def ask(self, question, *, on_step=None):
        self.calls += 1
        self.go.wait(5)
        raise AskError("ничего страшного")


def answer(rows=((1,),), columns=("x",)):
    from askbase.engine import Answer

    return Answer(sql="SELECT 1", columns=list(columns), rows=list(rows),
                  explanation="описание", notes=[], seconds=0.1)


def test_two_quick_questions_ask_the_model_once(app):
    # The keyboard shortcut does not know the button is disabled, so two quick
    # presses used to queue a second question behind the first and drop its
    # answer on top of the one already on screen.
    from askbase.app import Window

    w = Window("ru")
    engine = SlowEngine()
    w.engine = engine
    w.question.setPlainText("сколько клиентов")
    w._ask()
    w._ask()
    engine.go.set()
    assert w.pool.waitForDone(5000)
    assert engine.calls == 1, "второй вопрос не должен уходить в очередь"
    w.close()


def test_an_answer_to_an_abandoned_question_is_not_shown(app):
    # The thread cannot be stopped mid-answer, so an answer to a question the
    # user walked away from arrives anyway, a minute later, and used to throw
    # the connect page away and show a table from the previous database.
    from askbase.app import Window

    w = Window("ru")
    w.engine = SlowEngine()
    w.question.setPlainText("сколько клиентов")
    w._ask()
    rid = w.request
    w._go_home()                          # the user goes to open another database
    w._show_answer(answer(), rid)
    assert w.pages.currentIndex() == 0, "брошенный ответ не должен менять экран"
    w._show_error("поздняя ошибка", rid)
    assert "поздняя" not in w.status.text(), "брошенная ошибка не должна писать в строку состояния"
    w.engine.go.set()
    w.pool.waitForDone(5000)
    w.close()


def test_walking_away_frees_the_button_and_stops_the_line(app):
    # Otherwise the application stays visibly busy forever: the ask button is
    # dead and the progress line keeps running under the bar.
    from askbase.app import Window

    w = Window("ru")
    w.engine = SlowEngine()
    w.question.setPlainText("сколько клиентов")
    w._ask()
    assert not w.ask_btn.isEnabled()
    w._go_home()
    assert w.ask_btn.isEnabled()
    assert w.progress.isHidden()
    assert not w.asking
    assert not w.status.text(), "строка состояния не должна обещать работу, которой нет"
    w.engine.go.set()
    w.pool.waitForDone(5000)
    w.close()


def test_the_answer_to_the_question_on_screen_is_still_shown(app):
    # The guard above must not swallow the answer the user is waiting for.
    from askbase.app import Window

    w = Window("ru")
    w.engine = SlowEngine()
    w.question.setPlainText("сколько клиентов")
    w._ask()
    w._show_answer(answer(), w.request)
    assert w.pages.currentIndex() == 2
    assert w.ask_btn.isEnabled()
    assert w.progress.isHidden()
    w.engine.go.set()
    w.pool.waitForDone(5000)
    w.close()


def test_a_saved_csv_keeps_commas_quotes_newlines_and_cyrillic(app, tmp_path, monkeypatch):
    from askbase.app import Window

    out = tmp_path / "ответ.csv"
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                        lambda *a, **k: (str(out), "CSV (*.csv)"))
    w = Window("ru")
    w.answer = answer(
        columns=("имя", "примечание"),
        rows=[("Иванов, И.", 'сказал "да"'), ("две\nстроки", None)],
    )
    w._save_csv()

    # The byte order mark is why: this file is opened in Excel more often than
    # anywhere else, and without it every Cyrillic name comes out as noise.
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["имя", "примечание"]
    assert rows[1] == ["Иванов, И.", 'сказал "да"']
    assert rows[2] == ["две\nстроки", ""]       # None is an empty cell, not the word None
    w.close()


def test_an_empty_result_saves_as_a_header_only(app, tmp_path, monkeypatch):
    from askbase.app import Window

    out = tmp_path / "пусто.csv"
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                        lambda *a, **k: (str(out), "CSV (*.csv)"))
    w = Window("ru")
    w.answer = answer(rows=[], columns=("имя",))
    w._save_csv()
    with out.open(encoding="utf-8-sig", newline="") as f:
        assert list(csv.reader(f)) == [["имя"]]
    w.close()


def test_a_csv_that_cannot_be_written_is_reported_not_raised(app, monkeypatch):
    # A read-only folder used to raise inside the slot: a traceback nobody sees
    # and no file, with the screen saying nothing either way.
    from askbase.app import Window

    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                        lambda *a, **k: ("/нет/такой/папки/ответ.csv", "CSV (*.csv)"))
    w = Window("ru")
    w.answer = answer()
    w._save_csv()                        # must not raise
    assert w.status.text()
    assert "/нет/такой/папки" not in w.status.text() or w.t["saved"] not in w.status.text()
    w.close()
def test_a_question_whose_window_is_gone_ends_quietly(app):
    # A question outlives the window that asked it: the window is closed, or
    # the language is switched, which rebuilds it. Reporting back into the
    # deleted window raised inside the thread, and on a step that happens
    # mid-question, which lost the answer and left the line spinning.
    import shiboken6

    from askbase.app import AskTask

    engine = SlowEngine()
    engine.go.set()
    task = AskTask(engine, "сколько клиентов", "непредвиденное")
    shiboken6.delete(task.signals)       # the window that asked is no longer there
    task.run()                           # must not raise
    assert engine.calls == 1


class StoppableClient:
    """A model client that records being let go of."""

    def __init__(self):
        self.cancelled = self.restarted = 0

    def cancel(self):
        self.cancelled += 1

    def reset(self):
        self.restarted += 1


def test_stopping_a_question_lets_go_of_the_model(app):
    # Abandoning the answer in the window is not enough: one model answers one
    # question at a time, so until the connection is dropped the next question
    # waits behind a question nobody wants any more.
    from askbase.app import Window

    w = Window("ru")
    w.engine, w.client = SlowEngine(), StoppableClient()
    w.question.setPlainText("сколько клиентов")
    w._ask()
    assert w.client.restarted == 1       # a question stopped before must not stop this one
    w._stop()
    assert w.client.cancelled == 1
    assert w.ask_btn.isEnabled()
    assert not w.asking
    assert w.progress.isHidden()
    assert w.status.text() == w.t["stopped"]
    w.engine.go.set()
    assert w.pool.waitForDone(5000)
    w.close()


def test_an_example_writes_itself_into_the_question(app, tmp_path):
    # A blank box against a database nobody has described is the hardest
    # moment in the application; the examples are there to be pressed.
    import sqlite3

    from askbase.app import Window

    db = tmp_path / "дела.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE клиенты (id INTEGER, имя TEXT)")
    con.commit()
    con.close()
    w = Window("ru")
    w._open(str(db))
    first = w.example_row.itemAt(1).widget()
    first.click()
    assert w.question.toPlainText() == first.text()
    assert "клиенты" in w.outline.toPlainText()
    w.close()
