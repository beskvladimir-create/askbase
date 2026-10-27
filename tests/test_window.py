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

from PySide6.QtWidgets import QPushButton, QWidget  # noqa: E402

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
    # Not `currentWidget() is not None`, which is true for every valid index of
    # a QStackedWidget and merely restated count() == 3 from the test above.
    # Each page has to be a different widget that actually holds its screen's
    # controls, which is what breaks when a page is built but never populated.
    seen = []
    for i in range(w.pages.count()):
        w.pages.setCurrentIndex(i)
        page = w.pages.currentWidget()
        assert page is w.pages.widget(i)
        assert page.findChildren(QWidget), f"страница {i} пуста"
        seen.append(page)
    assert len({id(p) for p in seen}) == w.pages.count(), "страницы это один и тот же виджет"
    # The controls each screen is for, so a page swapped for another is caught.
    w.pages.setCurrentIndex(0)
    assert w.drop in w.pages.widget(0).findChildren(type(w.drop))
    assert w.question in w.pages.widget(1).findChildren(type(w.question))
    assert w.table in w.pages.widget(2).findChildren(type(w.table))
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
    # The point is that the file:// URL was decoded into a real path and the
    # file was reached. The old assertion looked for the i18n key "not_a_file"
    # in the status line, where a key never appears and where this message is
    # never sent, so it held however the branch behaved: removing the whole
    # file:// handling left every test passing.
    #
    # The file is empty, so opening it must fail for the right reason, and the
    # reason is the evidence. "There is not a single table in this file" means
    # the path was decoded and the file was found and opened. A URL that was
    # not decoded would have failed with "file not found" instead, which is a
    # different message and a different screen.
    assert not w.alert.isHidden(), "пустой файл открылся без возражений"
    shown = w.err_body.text()
    assert "таблиц" in shown, f"файл не был найден, URL не раскодирован: {shown}"
    assert w.t["not_a_file"].split("{")[0] not in shown, (
        "сообщение про отсутствующий файл: URL не раскодирован")
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
    # Not a disjunction against the unformatted template, which can never
    # appear in a status line and made the whole assertion true for any text.
    # The failure has to be reported, and reported as a failure.
    shown = w.status.text()
    assert shown
    assert shown.startswith(w.t["cannot_save"].split("{")[0]), shown
    assert not shown.startswith(w.t["saved"].split("{")[0]), "провал показан как успех"
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


# ---- journal, examples, settings: the parts added after the first release ----
# The window has been green while the application could not start, so anything
# that draws itself from data gets built here rather than trusted.

@pytest.fixture
def journal_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("ASKBASE_JOURNAL", str(tmp_path / "journal.jsonl"))
    from askbase import journal
    journal.clear()
    return journal


def _shop(tmp_path):
    import sqlite3
    p = tmp_path / "shop.sqlite"
    con = sqlite3.connect(p)
    con.executescript(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, region TEXT, joined TEXT);"
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL);"
    )
    con.executemany("INSERT INTO customers VALUES (?,?,?,?)",
                    [(i, f"c{i}", ["Leeds", "Thorne"][i % 2], f"2026-03-{i % 28 + 1:02d}")
                     for i in range(30)])
    con.executemany("INSERT INTO orders VALUES (?,?,?)",
                    [(i, i % 30, i * 2.5) for i in range(30)])
    con.commit()
    con.close()
    return str(p)


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_the_journal_block_is_hidden_until_there_is_something_in_it(app, lang, journal_in_tmp):
    from askbase.app import Window

    w = Window(lang)
    assert w.journal_box.isVisibleTo(w.journal_box.parentWidget()) is False
    w.close()


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_a_journalled_question_appears_and_can_be_repeated(app, lang, journal_in_tmp):
    from askbase.app import Window

    journal_in_tmp.append(journal_in_tmp.Entry(
        at="2026-10-26T09:00:00+00:00", question="сколько клиентов по регионам",
        sql="SELECT 1", rows=4, seconds=1.0, db_path="/x/shop.sqlite"))
    w = Window(lang)
    w._refresh_journal()
    assert w.journal_rows.count() == 1
    # The row is pressed, not bypassed. The earlier version called _repeat with
    # the question as a literal and then asserted the row was not None, which
    # is guaranteed by the count above: if the button were unconnected, or
    # wired to the wrong entry, it still passed.
    row = w.journal_rows.itemAt(0).widget()
    button = next(b for b in row.findChildren(QPushButton))
    assert "сколько клиентов" in button.text()
    w.question.setPlainText("")
    button.click()
    assert w.question.toPlainText() == "сколько клиентов по регионам"
    w.close()


def test_a_failed_question_is_not_offered_for_repeat(app, journal_in_tmp):
    from askbase.app import Window

    journal_in_tmp.append(journal_in_tmp.Entry(
        at="2026-10-26T09:00:00+00:00", question="удали всё", sql="DELETE FROM x",
        rows=0, seconds=0.2, db_path="/x/shop.sqlite", ok=False, error="refused"))
    w = Window("ru")
    w._refresh_journal()
    assert w.journal_rows.count() == 0      # repeating a refusal helps nobody
    w.close()


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_examples_are_built_from_the_open_schema(app, lang, tmp_path, journal_in_tmp):
    from askbase.app import Window
    from askbase.engine import Engine

    class Stub:
        def complete(self, prompt):
            raise AssertionError("describing a schema must not ask the model")

        def reset(self):
            pass

    w = Window(lang)
    w.engine = Engine(_shop(tmp_path), Stub())
    w._describe(w.engine.db_path)
    texts = [w.example_row.itemAt(i).widget().text()
             for i in range(1, w.example_row.count())
             if w.example_row.itemAt(i).widget() is not None]
    assert len(texts) >= 3
    # Grounded in this database, and not four copies of one shape.
    assert any("region" in t for t in texts)
    assert any("total" in t for t in texts)
    assert len(set(texts)) == len(texts)
    w.close()


def test_the_new_menu_entries_exist(app):
    from askbase.app import Window

    w = Window("ru")
    titles = {a.text() for a in w.findChildren(type(w.menuBar().actions()[0]))}
    for key in ("settings", "ro_title"):
        assert w.t[key] in titles, key
    w.close()


def test_the_read_only_sql_is_the_one_the_document_specifies(app):
    from askbase.app import READONLY_SQL

    # A dialog that drifts from docs/readonly-role.md would hand a DBA
    # different instructions from the ones the site gives them.
    for must in ("CREATE ROLE askbase_ro", "GRANT SELECT ON ALL TABLES IN SCHEMA public",
                 "CREATE USER 'askbase_ro'@'localhost'", "mode=ro"):
        assert must in READONLY_SQL, must


# ---- a question asked through the window, end to end ------------------------
# The gap that let a dead application ship with 382 tests green: every test
# here built widgets or called _show_answer directly, and none pressed Ask and
# waited for what came back. The signal marshalling between the worker thread
# and the window was broken for a whole commit without one test noticing.

def _answering_window(app, lang, tmp_path, monkeypatch, reply):
    from askbase.app import Window
    from askbase.engine import Engine

    monkeypatch.setenv("ASKBASE_JOURNAL", str(tmp_path / "journal.jsonl"))

    class Stub:
        text = reply

        def complete(self, prompt):
            return self

        def reset(self):
            pass

        def cancel(self):
            pass

    db = tmp_path / "shop.sqlite"
    import sqlite3
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, region TEXT);")
    con.executemany("INSERT INTO customers VALUES (?,?,?)",
                    [(i, f"c{i}", ["Leeds", "Thorne"][i % 2]) for i in range(20)])
    con.commit()
    con.close()

    w = Window(lang)
    w.client = Stub()
    w.engine = Engine(str(db), w.client, lang=lang)
    w._describe(w.engine.db_path)
    w._to_page(1)
    return w


def _pump(app, w, want_page, seconds=5.0):
    """Spin the event loop until the window leaves the question page."""
    import time
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if w.pages.currentIndex() == want_page or not w.alert.isHidden():
            return
        time.sleep(0.01)


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_asking_a_question_produces_an_answer_on_screen(app, lang, tmp_path, monkeypatch):
    w = _answering_window(app, lang, tmp_path, monkeypatch,
                          "```sql\nSELECT region, COUNT(*) AS n FROM customers GROUP BY region\n```")
    w.question.setPlainText("how many customers by region")
    w._ask()
    _pump(app, w, want_page=2)

    assert w.pages.currentIndex() == 2, "ответ не дошёл до экрана"
    assert w.answer is not None
    assert w.table.rowCount() == 2
    assert not w.asking, "окно так и считает, что вопрос в работе"
    assert w.working.text() == "", "часы продолжают идти после ответа"
    w.close()


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_a_refused_question_shows_an_error_and_the_query(app, lang, tmp_path, monkeypatch):
    w = _answering_window(app, lang, tmp_path, monkeypatch,
                          "```sql\nDELETE FROM customers\n```")
    w.question.setPlainText("remove everyone")
    w._ask()
    _pump(app, w, want_page=2)

    assert w.pages.currentIndex() != 2, "отказ показан как ответ"
    assert not w.alert.isHidden(), "отказ не показан вовсе"
    assert "DELETE" in w.err_body.text(), "отклонённый запрос не показан"
    assert not w.asking
    w.close()


def test_an_answered_question_reaches_the_journal(app, tmp_path, monkeypatch):
    from askbase import journal

    w = _answering_window(app, "ru", tmp_path, monkeypatch,
                          "```sql\nSELECT region FROM customers\n```")
    w.question.setPlainText("какие регионы есть")
    w._ask()
    _pump(app, w, want_page=2)

    kept = journal.entries()
    assert kept, "вопрос не записан в журнал"
    assert kept[0].question == "какие регионы есть"
    w.close()


# ---- the export has to come from the answer's own database ------------------

def test_saving_a_truncated_answer_after_opening_another_database_is_refused(
        app, tmp_path, monkeypatch):
    """Found by review: it silently wrote the wrong database's rows.

    `full = truncated and self.engine is not None` only checked that an engine
    existed. With two monthly copies of one schema, opening the second after
    getting an answer from the first made the export run against the second and
    succeed, writing the wrong year's rows under the right year's answer.
    """
    import sqlite3
    from askbase.app import Window
    from askbase.engine import Engine

    monkeypatch.setenv("ASKBASE_JOURNAL", str(tmp_path / "j.jsonl"))
    monkeypatch.setenv("ASKBASE_SETTINGS", str(tmp_path / "prefs.ini"))

    def make(name, n):
        p = tmp_path / name
        con = sqlite3.connect(p)
        con.executescript("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);")
        con.executemany("INSERT INTO customers VALUES (?,?)",
                        [(i, f"{name}-{i}") for i in range(n)])
        con.commit()
        con.close()
        return str(p)

    a_db, b_db = make("a.sqlite", 40), make("b.sqlite", 3)

    class Stub:
        text = "```sql\nSELECT id, name FROM customers\n```"

        def complete(self, prompt):
            return self

        def reset(self):
            pass

        def cancel(self):
            pass

    w = Window("ru")
    w.max_rows = 5
    w.client = Stub()
    w.engine = Engine(a_db, w.client, lang="ru", max_rows=5)
    w.asked_question = "все клиенты"
    answer = w.engine.ask("все клиенты")
    assert answer.truncated and answer.db_path == a_db
    w._show_answer(answer, w.request)

    # now the user opens the other month
    w.engine = Engine(b_db, w.client, lang="ru", max_rows=5)

    out = tmp_path / "saved.csv"
    monkeypatch.setattr("askbase.app.QFileDialog.getSaveFileName",
                        staticmethod(lambda *a, **k: (str(out), "")))
    w._save_csv()
    assert not out.exists(), "экспортировал из другой базы вместо отказа"
    assert w.status.text() == w.t["cannot_save_full"]
    w.close()


def test_the_answer_is_titled_with_the_question_that_was_asked(app, tmp_path, monkeypatch):
    # A local model thinks for about a minute, so typing the next question
    # while waiting is ordinary; the answer then appeared under a heading
    # naming a question it does not answer.
    w = _answering_window(app, "ru", tmp_path, monkeypatch,
                          "```sql\nSELECT region FROM customers\n```")
    w.question.setPlainText("какие регионы есть")
    w._ask()
    w.question.setPlainText("а сколько их в Лидсе")      # typing ahead
    _pump(app, w, want_page=2)
    assert w.asked.text() == "какие регионы есть"
    w.close()
