"""Askbase: connect, ask, read.

Built on the same frame as pii-roundtrip, so the two look like one house: the
navy Ground with its aurora and particles is the window itself, the brand mark
sits top left under the system buttons, the progress line runs under the bar,
and the body is a stack of pages separated by hairlines.

The window is deliberately thin. Everything that can be wrong about an answer
is decided in engine.py and safety.py, which are tested without Qt.
"""
from __future__ import annotations

import csv
import os
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
    QAction, QCursor, QDesktopServices, QFontMetrics, QGuiApplication, QIcon, QKeySequence,
    QShortcut, QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication, QDialog, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import i18n, journal, offline, recent, suggest, theme
from .engine import AskError, Engine, export_csv
from .models import Cancelled, ModelClient, installed_models
from .widgets import BrandMark, DropZone, Ground, LangSwitch, ProgressLine, Segmented, glow, keycap

ICON = Path(__file__).with_name("icon.svg")
MAKER = "Besk Tech"


def label(text: str = "", name: str = "") -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(True)
    return lb


def button(text: str, *, primary: bool = False, small: bool = False, link: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)  # as in pii-roundtrip: pressable things say so
    if primary:
        b.setProperty("primary", True)
    if small:
        b.setProperty("small", True)
    if link:
        b.setProperty("link", True)
        return b
    return glow(b, primary)


def card(*children: QWidget, spacing: int = 14, pad: int = 22) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(pad, pad, pad, pad)
    lay.setSpacing(spacing)
    for c in children:
        lay.addWidget(c)
    return f


def hairline() -> QFrame:
    f = QFrame()
    f.setObjectName("hair")
    return f


# Kept in step with docs/readonly-role.md, which carries the reasoning around
# it. Only the statements are here: a dialog is not the place for an essay, and
# the full page is one button away.
READONLY_SQL = """-- PostgreSQL
CREATE ROLE askbase_ro LOGIN PASSWORD 'set_your_own_password';
GRANT CONNECT ON DATABASE analytics TO askbase_ro;
GRANT USAGE ON SCHEMA public TO askbase_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO askbase_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO askbase_ro;

-- MySQL
CREATE USER 'askbase_ro'@'localhost' IDENTIFIED BY 'set_your_own_password';
GRANT SELECT ON analytics.* TO 'askbase_ro'@'localhost';

-- SQLite
-- There are no roles. Give the user a copy of the file, or set the file
-- permissions to read-only; the application opens it with mode=ro either way
-- and verifies on connect that a write is refused."""


def _ellipsis(text: str, n: int) -> str:
    """Shorten for a one-line button without hiding that it was shortened."""
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "\u2026"


def _prefs():
    from PySide6.QtCore import QSettings

    # Same override as recent.py, and for the same reason: a test run must not
    # write into the preferences of whoever is running it.
    override = os.environ.get("ASKBASE_SETTINGS")
    if override:
        return QSettings(override, QSettings.Format.IniFormat)
    return QSettings("Besk Tech", "Askbase")


def _pref(key: str, default, *, low=None, high=None):
    """One preference, coerced to the default's type and kept inside its range.

    QSettings on macOS hands numbers back as strings often enough that reading
    them raw and using them as a row limit is a crash waiting for the first
    person who changes a setting.

    Clamped as well as coerced. A plist written by anything other than the
    settings screen can hold 0, a negative number or inf, and all three got
    through: a row bound of 0 made every answer empty, with a row line
    reporting that more than zero rows existed and the first zero were shown,
    and a negative one removed the row bound altogether, because SQLite reads
    LIMIT -1 as no limit and fetchmany of a negative count returns everything.
    The spin box cannot even display those values, so there was no way to see
    what was wrong, let alone fix it.
    """
    raw = _prefs().value(key, default)
    try:
        value = type(default)(raw)
    except (TypeError, ValueError):
        return default
    if value != value or value in (float("inf"), float("-inf")):   # NaN or infinite
        return default
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


class Signals(QObject):
    done = Signal(object)
    # The message and, when the failure was about a query that exists, that
    # query. A refusal that will not show what it refused asks to be believed.
    failed = Signal(str, str)
    step = Signal(str)


class AskTask(QRunnable):
    """One question, off the interface thread so the window stays alive."""

    def __init__(self, engine: Engine, question: str, unexpected: str):
        super().__init__()
        self.engine, self.question = engine, question
        self.unexpected = unexpected
        self.signals = Signals()

    @Slot()
    def run(self) -> None:
        try:
            answer = self.engine.ask(self.question, on_step=lambda s: self._tell(self.signals.step, s))
        except Cancelled:
            pass                                # asked for: the window has already moved on
        except AskError as e:
            self._tell(self.signals.failed, str(e), getattr(e, "sql", ""))
        except Exception:                       # never leave the user at a frozen screen
            self._tell(self.signals.failed,
                       f"{self.unexpected}\n" + traceback.format_exc(limit=2), "")
        else:
            self._tell(self.signals.done, answer)

    def _tell(self, signal, *payload) -> None:
        """Report back, unless there is no longer anybody to report to.

        A question outlives the window that asked it: closing the window, or
        switching language, which rebuilds it. Emitting into the deleted window
        then raised inside the thread, which lost the answer and, when it
        happened on a step rather than at the end, abandoned the question
        halfway with the progress line still running.

        emit(*payload), not emit(payload). The signature took *payload when a
        failure started carrying its SQL, and the body was left emitting the
        tuple itself. Qt then tried to marshal a tuple into the first argument:
        `done` and `step` were dropped silently in the queued connection, and
        `failed(str, str)` raised "needs 2 argument(s), 1 given" inside the
        worker thread, which `except RuntimeError` does not catch. Every
        question hung forever with the clock running and no answer and no
        error, and all 382 tests passed, because nothing asked a question
        through the window end to end. test_window.py now does.
        """
        try:
            signal.emit(*payload)
        except RuntimeError:
            pass


class Window(QMainWindow):
    language_changed = Signal(str)

    def __init__(self, lang: str = "ru") -> None:
        super().__init__()
        self.lang = lang
        self.t = i18n.TEXTS[lang]
        self.engine: Engine | None = None
        self.client: ModelClient | None = None
        self.answer = None
        self.asked_question = ""                # the question in flight, for the journal
        self.in_flight = None                   # keeps the running task alive
        self.first_question = True
        self.asking = False
        # The bounds on an answer. Defaults from design.md 4.5, overridable on
        # the settings screen, remembered between launches. They are held on
        # the window rather than inside Engine because a change has to apply to
        # the next question without reopening the database.
        self.max_rows = int(_pref("max_rows", 1000, low=10, high=100_000))
        self.timeout_s = float(_pref("timeout_s", 30.0, low=5.0, high=600.0))
        self.step = ""                          # the stage the question has reached
        # A local model can think for a minute. Without a clock on the screen
        # there is no way to tell working from hung, so the wait is counted.
        self.ticker = QTimer(self)
        self.ticker.setInterval(1000)
        self.ticker.timeout.connect(self._tick)
        self.waited = 0
        # Every question gets a number, and only the current number may write
        # on the screen. A question the user has walked away from still ends,
        # a minute later, in a thread that knows nothing about that.
        self.request = 0
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(1)          # one model, one question at a time

        self.setWindowTitle(self.t["app"])
        self.resize(980, 720)
        self.setMinimumSize(820, 620)
        # the navy ground runs under the native title bar, as in pii-roundtrip
        self.setWindowFlag(Qt.WindowType.ExpandedClientAreaHint, True)
        self.setWindowFlag(Qt.WindowType.NoTitleBarBackgroundHint, True)

        root = Ground()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._bar())

        self.progress = ProgressLine()
        outer.addWidget(self.progress)

        self.status = label("", "status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setVisible(False)
        outer.addWidget(self.status)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._connect_page())
        self.pages.addWidget(self._ask_page())
        self.pages.addWidget(self._answer_page())
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(24, 10, 24, 22)
        bv.setSpacing(0)
        bv.addWidget(self._alert())
        bv.addWidget(self.pages, 1)
        outer.addWidget(body, 1)

        self.setCentralWidget(root)
        self._refresh_recent()
        self._to_page(0)
        self._menu()

    # ---------- what went wrong, and what to do about it ----------
    def _alert(self) -> QWidget:
        """One card for every failure, because a failure is where the user needs help.

        Errors used to arrive as one grey line of twelve point text across the
        top of the window, a full screen away from whatever had just been
        pressed, truncated at the window edge, and with nothing to press next.
        """
        self.err_title = label("", "errtitle")
        self.err_body = label("", "errbody")
        # a path or a message from SQLite is something people quote to whoever
        # can help them, so it can be selected and copied
        self.err_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.err_do = button("", small=True)
        # Connected once to a slot that reads what the alert currently offers:
        # reconnecting per failure left old handlers behind, or warned about
        # disconnecting one that was never there.
        self.err_then = None
        self.err_do.clicked.connect(lambda: self.err_then and self.err_then())
        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.addWidget(self.err_do)
        rh.addStretch(1)
        self.alert = card(self.err_title, self.err_body, row, spacing=8, pad=18)
        self.alert.hide()
        box = QWidget()
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)
        bv.addWidget(self.alert)
        bv.addSpacing(12)
        self.alert_box = box
        box.hide()
        return box

    def _fail(self, title: str, body: str, action: str = "", then=None) -> None:
        self.err_title.setText(title)
        self.err_body.setText(body)
        self.err_do.setVisible(bool(action))
        self.err_do.setText(action)
        self.err_then = then
        self.alert.show()
        self.alert_box.show()

    def _clear_alert(self) -> None:
        self.alert_box.hide()

    def _menu(self) -> None:
        m = self.menuBar().addMenu(self.t["menu_file"])
        about = QAction(self.t["about"], self)
        about.setMenuRole(QAction.MenuRole.AboutRole)   # lands in the app menu on macOS
        about.triggered.connect(self._about)
        m.addAction(about)
        # The menu is where a keyboard shortcut is found. Everything the
        # buttons do is here with its keys written next to it, which is also
        # the only place the application can say that ⌘↩ asks the question.
        for text, keys, fn in (
            (self.t["open_db"], QKeySequence(QKeySequence.StandardKey.Open), self._pick),
            (self.t["ask"], QKeySequence("Ctrl+Return"), self._ask),
            (self.t["again"], QKeySequence(QKeySequence.StandardKey.New), self._new_question),
            (self.t["copy"], QKeySequence("Shift+Ctrl+C"), self._copy_sql),
            (self.t["csv"], QKeySequence(QKeySequence.StandardKey.Save), self._save_csv),
            (self.t["settings"], QKeySequence("Ctrl+,"), self._settings),
            (self.t["ro_title"], QKeySequence("Shift+Ctrl+R"), self._readonly_role),
        ):
            a = QAction(text, self)
            a.setShortcut(keys)
            a.triggered.connect(fn)
            m.addAction(a)
        QShortcut(QKeySequence("Meta+Return"), self, self._ask)
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._view(0))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._view(1))
        # Escape is how a person leaves something: out of the answer back to
        # the question, out of the question back to the list of databases.
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._back)

    def _settings(self) -> None:
        """design.md 4.5. Absent until now: the bounds existed only as defaults.

        Four things live here and nothing else. The row limit and the timeout,
        because they are the two numbers that decide whether a heavy question
        returns or is cut off. The journal, because a local file the
        application writes must be openable and deletable from inside it. And
        the statement that there is no telemetry, which belongs on the screen
        where a person comes looking for what the application collects.
        """
        d = QDialog(self)
        d.setWindowTitle(self.t["settings"])
        d.setMinimumWidth(460)
        v = QVBoxLayout(d)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(18)

        v.addWidget(label(self.t["settings_bounds"], "micro"))

        rows_box = QSpinBox()
        rows_box.setRange(10, 100_000)
        rows_box.setSingleStep(100)
        rows_box.setValue(self.max_rows)
        rows_row = QWidget()
        rr = QHBoxLayout(rows_row)
        rr.setContentsMargins(0, 0, 0, 0)
        rr.addWidget(label(self.t["set_max_rows"], "note"), 1)
        rr.addWidget(rows_box, 0)
        v.addWidget(rows_row)

        time_box = QSpinBox()
        time_box.setRange(5, 600)
        time_box.setSuffix(" s")
        time_box.setValue(int(self.timeout_s))
        time_row = QWidget()
        tr = QHBoxLayout(time_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.addWidget(label(self.t["set_timeout"], "note"), 1)
        tr.addWidget(time_box, 0)
        v.addWidget(time_row)

        v.addWidget(label(self.t["set_bounds_note"], "note"))
        v.addWidget(hairline())

        v.addWidget(label(self.t["settings_journal"], "micro"))
        v.addWidget(label(self.t["set_journal_note"].format(path=journal.path()), "note"))
        jrow = QWidget()
        jh = QHBoxLayout(jrow)
        jh.setContentsMargins(0, 0, 0, 0)
        jh.setSpacing(12)
        show = button(self.t["set_journal_show"], link=True)
        show.clicked.connect(lambda: self._reveal(journal.path()))
        wipe = button(self.t["set_journal_clear"], link=True)

        def _wipe() -> None:
            journal.clear()
            self._refresh_journal()
            self._say(self.t["set_journal_cleared"])
        wipe.clicked.connect(_wipe)
        jh.addWidget(show, 0)
        jh.addWidget(wipe, 0)
        jh.addStretch(1)
        v.addWidget(jrow)
        v.addWidget(hairline())

        v.addWidget(label(self.t["settings_collect"], "micro"))
        v.addWidget(label(self.t["set_no_telemetry"], "note"))

        close = button(self.t["save"], primary=True)

        def _save() -> None:
            self.max_rows = rows_box.value()
            self.timeout_s = float(time_box.value())
            s = _prefs()
            s.setValue("max_rows", self.max_rows)
            s.setValue("timeout_s", self.timeout_s)
            if self.engine is not None:
                # Applies to the next question without reopening the database.
                self.engine.max_rows = self.max_rows
                self.engine.timeout = self.timeout_s
            d.accept()
            self._say(self.t["set_saved"])
        close.clicked.connect(_save)
        brow = QWidget()
        bh = QHBoxLayout(brow)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.addStretch(1)
        bh.addWidget(close)
        v.addWidget(brow)
        d.exec()

    def _readonly_role(self) -> None:
        """The SQL a database administrator needs, inside the application.

        docs/roles.md serves role 3, the gatekeeper, "with documents rather
        than features", and the document exists on the site. The application
        had no way to reach it, which left the one person who decides whether
        anybody may use this with nothing to read where they are standing.

        It is shown here rather than linked because the application works with
        the network off, and material a DBA needs during an evaluation should
        not require a browser and a working connection. The full page is still
        one button away for whoever wants the reasoning around the SQL.
        """
        d = QDialog(self)
        d.setWindowTitle(self.t["ro_title"])
        d.setMinimumWidth(620)
        v = QVBoxLayout(d)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(16)
        v.addWidget(label(self.t["ro_intro"], "note"))

        box = QPlainTextEdit()
        box.setObjectName("doc")
        box.setReadOnly(True)
        box.setFont(theme.mono())
        box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        box.setPlainText(READONLY_SQL)
        box.setMinimumHeight(260)
        v.addWidget(box, 1)

        v.addWidget(label(self.t["ro_note"], "note"))

        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(12)
        copy = button(self.t["ro_copy"], link=True)

        def _copy() -> None:
            QGuiApplication.clipboard().setText(READONLY_SQL)
            self._say(self.t["copied"])
        copy.clicked.connect(_copy)
        page = button(self.t["ro_page"], link=True)
        page.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(
            "https://askbase.besk.tech/read-only-access/" if self.lang == "en"
            else "https://askbase.besk.tech/ru/dostup-tolko-chtenie/")))
        done = button(self.t["close"], primary=True)
        done.clicked.connect(d.accept)
        rh.addWidget(copy, 0)
        rh.addWidget(page, 0)
        rh.addStretch(1)
        rh.addWidget(done, 0)
        v.addWidget(row)
        d.exec()

    def _reveal(self, p) -> None:
        """Show a file in Finder, or its folder if it does not exist yet."""
        target = Path(p)
        if not target.exists():
            target = target.parent
            target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _about(self) -> None:
        d = QDialog(self)
        d.setWindowTitle(self.t["about"])
        v = QVBoxLayout(d)
        v.setContentsMargins(36, 32, 36, 28)
        v.setSpacing(12)
        pic = QLabel()
        pic.setPixmap(QIcon(str(ICON)).pixmap(72, 72))
        v.addWidget(pic, 0, Qt.AlignmentFlag.AlignHCenter)
        name = label("Askbase", "aboutname")
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(name)
        for line in (
            self.t["about_1"],
            self.t["about_2"],
            self.t["maker"].format(maker=MAKER) + " · besk.tech",
        ):
            lb = label(line, "note")
            lb.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            v.addWidget(lb)
        close = button(self.t["close"], small=True)
        close.clicked.connect(d.accept)
        v.addWidget(close, 0, Qt.AlignmentFlag.AlignHCenter)
        d.exec()

    # ---------- the bar, under the system buttons ----------
    def _bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(76)
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 32, 24, 8)

        self.brand = BrandMark()
        self.brand.clicked.connect(self._go_home)
        left = QWidget()
        left.setFixedWidth(210)
        lh = QHBoxLayout(left)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.addWidget(self.brand, 0, Qt.AlignmentFlag.AlignLeft)
        h.addWidget(left)

        self.where = label("", "doctitle")
        self.where.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.where.setWordWrap(False)   # one line, like the trust line beside it
        # It takes the room that is left and no more. Asking for the width of
        # its text pushed the language switch off the edge of a small window.
        self.where.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.where_full = ""
        # Re-elided whenever the layout gives the label a new width: asking
        # for that width from resizeEvent returns the one it had before.
        self.where.installEventFilter(self)
        h.addWidget(self.where, 1)

        self.trust = label(self.t["trust"], "trust")
        self.trust.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.trust.setWordWrap(False)   # one line, or it rides up into the window buttons
        # The promise is three concrete facts; the line in the bar is only its
        # headline, and the facts are a hover away rather than nowhere.
        self.trust.setToolTip(self.t["trust_tip"])
        self.tabs = Segmented((self.t["tab_answer"], self.t["tab_sql"]))
        self.tabs.setFixedWidth(170)
        self.tabs.changed.connect(self._view)
        self.tabs.hide()
        self.langs = LangSwitch(self.lang)
        self.langs.changed.connect(self.language_changed.emit)
        right = QWidget()
        right.setMinimumWidth(210)
        rh = QHBoxLayout(right)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(14)
        rh.addStretch(1)
        rh.addWidget(self.trust)
        rh.addWidget(self.tabs)
        rh.addWidget(self.langs)
        h.addWidget(right)
        return bar

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._fit_bar()

    def eventFilter(self, obj, e) -> bool:
        from PySide6.QtCore import QEvent

        if obj is self.where and e.type() == QEvent.Type.Resize:
            self._fit_bar()
        return False

    def _fit_bar(self) -> None:
        # Narrow, the promise in Playfair and the name of the open file fight
        # for the same strip and both lose. The file name wins: it says which
        # database is open and that it is read-only, and the promise is still
        # under the drop zone and in the tooltip.
        self.trust.setVisible(self.width() >= (1180 if self.tabs.isVisible() else 960))
        # Cut with an ellipsis rather than at the window edge, so that what is
        # left still reads as a sentence. The whole of it is in the tooltip.
        room = self.where.width() - 16
        self.where.setText(
            QFontMetrics(self.where.font()).elidedText(
                self.where_full, Qt.TextElideMode.ElideMiddle, room
            ) if room > 0 else ""
        )
        self.where.setToolTip(self.where_full)


    # ---------- page 1: connect ----------
    def _connect_page(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(16)

        self.drop = DropZone(self.t)
        self.drop.file_dropped.connect(self._open)
        self.drop.choose.connect(self._pick)
        v.addWidget(self.drop, 1)

        # The databases opened before. Without them the application forgets
        # everything each morning and the first act of every day is hunting
        # for the same file in Finder.
        self.recent_box = QWidget()
        rv = QVBoxLayout(self.recent_box)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(4)
        head = label(self.t["recent"], "micro")
        head.setContentsMargins(12, 0, 12, 4)
        rv.addWidget(head)
        self.recent_rows = QVBoxLayout()
        self.recent_rows.setSpacing(0)
        rv.addLayout(self.recent_rows)
        v.addWidget(self.recent_box)

        # Typing or pasting a path is how many people hand over a file, and a
        # drop zone on its own quietly excludes anyone working from a terminal
        # or reading a path out of a note.
        self.path = QLineEdit()
        self.path.setPlaceholderText(self.t["path_hint"])
        self.path.setClearButtonEnabled(True)
        self.path.returnPressed.connect(self._open_typed)
        go = button(self.t["open"], small=True)
        go.clicked.connect(self._open_typed)
        prow = QWidget()
        ph = QHBoxLayout(prow)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(12)
        ph.addWidget(self._row_label(self.t["path_label"]), 0)
        ph.addWidget(self.path, 1)
        ph.addWidget(go, 0)
        v.addWidget(prow)

        found = installed_models()
        self.model_box = QComboBox()
        self.model_box.addItems(found or [self.t["no_model_short"]])
        self.model_box.setEnabled(bool(found))
        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(12)
        rh.addWidget(self._row_label(self.t["model_label"]), 0)
        rh.addWidget(self.model_box, 1)
        v.addWidget(row)

        if not found:
            v.addWidget(label(
                self.t["no_model"],
                "errbody",
            ))
        v.addWidget(hairline())
        foot = QWidget()
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(0, 0, 0, 0)
        fh.addWidget(label(self.t["readonly_note"], "footer"), 1)
        fh.addWidget(label(self.t["maker"].format(maker=MAKER), "maker"), 0)
        v.addWidget(foot)
        return w

    def _size(self, schema) -> str:
        """How big the open database is, counted in the right grammatical form."""
        return "  ·  ".join((
            i18n.plural(self.t, "tables", len(schema.tables)),
            i18n.plural(self.t, "columns", schema.n_columns),
            self.t["readonly_short"],
        ))

    def _row_label(self, text: str) -> QLabel:
        """A label in the left column of a form row. One width, so the fields line up."""
        lb = label(text, "note")
        lb.setFixedWidth(170)
        return lb

    def _refresh_recent(self) -> None:
        while self.recent_rows.count():
            item = self.recent_rows.takeAt(0)
            row = item.widget()
            if row is not None:
                # Held in a name: once the row has no parent the layout item no
                # longer knows about it and asking again returns None. Detached
                # at once, or a row waiting for deleteLater is still drawn
                # underneath the new ones.
                row.hide()
                row.setParent(None)
                row.deleteLater()
        paths = recent.paths()
        self.recent_box.setVisible(bool(paths))
        for p in paths:
            row = QPushButton()
            row.setProperty("recent", True)
            row.setFixedHeight(36)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setToolTip(p)
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 0, 8, 0)
            name = label(Path(p).name)
            name.setStyleSheet("color: #FAFAFA; font-size: 14px;")
            where = label(str(Path(p).parent).replace(str(Path.home()), "~"), "note")
            where.setWordWrap(False)
            h.addWidget(name)
            h.addStretch(1)
            h.addWidget(where)
            h.addSpacing(8)
            forget = QPushButton("✕")
            forget.setObjectName("remove")
            forget.setToolTip(self.t["forget"])
            forget.setCursor(Qt.CursorShape.PointingHandCursor)
            forget.setFixedSize(26, 26)
            forget.clicked.connect(lambda _=False, path=p: self._forget(path))
            h.addWidget(forget)
            row.clicked.connect(lambda _=False, path=p: self._open(path))
            self.recent_rows.addWidget(row)

    def _forget(self, path: str) -> None:
        recent.forget(path)
        self._refresh_recent()

    def _open_typed(self) -> None:
        text = self.path.text().strip().strip('"').strip("'")
        if text.startswith("file://"):
            from urllib.parse import unquote, urlparse
            text = unquote(urlparse(text).path)
        if text:
            self._open(str(Path(text).expanduser()))

    def adopt(self, old: "Window") -> None:
        """Take over the open database from the window being replaced."""
        self.engine = old.engine
        self.client = old.client
        self.model_box.setCurrentText(old.model_box.currentText())
        if self.engine is not None:
            # The engine writes the "what it counted" sentence, so switching
            # the interface language has to reach it too, or the next answer
            # explains itself in the language the user just left.
            self.engine.lang = self.lang
            self._describe(self.engine.db_path)
            self.question.setPlainText(old.question.toPlainText())
            self._to_page(1)

    def _describe(self, path: str) -> None:
        """Put the open database on the screen: its size in the bar, its shape on the page."""
        s = self.engine.schema
        self.where_full = f"{Path(path).name}  ·  " + self._size(s)
        self._fit_bar()
        self.outline.setPlainText(s.outline())
        while self.example_row.count() > 1:     # everything after the "for example" label
            old = self.example_row.takeAt(1).widget()
            if old is not None:                 # the stretch at the end has no widget
                old.setParent(None)
                old.deleteLater()
        # An example that can only be read leaves the hardest part, the first
        # sentence, to the person. Pressed, it writes itself into the box.
        # The shapes come from this schema: a breakdown is offered only where
        # a column holds a handful of values, a ranking only where a number
        # that is not an identifier exists. "How many rows in X" four times
        # over taught nothing about what else could be asked.
        for s_ in suggest.for_schema(s, self.t):
            b = button(s_.text, link=True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, q=s_.text: self._use_example(q))
            self.example_row.addWidget(b)
        self.example_row.addStretch(1)

    def _use_example(self, text: str) -> None:
        self.question.setPlainText(text)
        self.question.setFocus()
        self.question.moveCursor(QTextCursor.MoveOperation.End)

    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.t["choose_db"], str(Path.home()),
            self.t["db_filter"],
        )
        if path:
            self._open(path)

    def _open(self, path: str) -> None:
        if not os.path.isfile(path):
            self._fail(self.t["err_db"], self.t["not_a_file"].format(path=path),
                       self.t["choose_other"], self._pick)
            self._forget(path)      # a file that moved should stop being offered
            return
        self._abandon()
        try:
            self.client = ModelClient(self.model_box.currentText())
            self.engine = Engine(path, self.client, lang=self.lang,
                                 max_rows=self.max_rows, timeout=self.timeout_s)
        except Exception as e:
            self._fail(self.t["err_db"], self.t["cannot_open"].format(error=e),
                       self.t["choose_other"], self._pick)
            return
        recent.remember(path)
        self._refresh_recent()
        self._clear_alert()
        self._describe(path)
        self._to_page(1)
        self.question.setFocus()
        self._say("")

    # ---------- page 2: ask ----------
    def _ask_page(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(14)

        v.addWidget(label(self.t["question"], "micro"))
        self.question = QPlainTextEdit()
        self.question.setObjectName("doc")
        self.question.setPlaceholderText(self.t["placeholder"])
        self.question.setFixedHeight(130)
        v.addWidget(card(self.question))

        examples = QWidget()
        self.example_row = QHBoxLayout(examples)
        self.example_row.setContentsMargins(0, 0, 0, 0)
        self.example_row.setSpacing(16)
        self.example_row.addWidget(label(self.t["examples"], "note"), 0)
        v.addWidget(examples)

        # What the model is shown, shown to the person as well. A question is
        # written against whatever the writer believes is in there, and this
        # is the only place the two beliefs can be compared before asking.
        self.outline = QPlainTextEdit()
        self.outline.setObjectName("doc")
        self.outline.setReadOnly(True)
        self.outline.setFont(theme.mono())
        self.outline.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.outline.setMinimumHeight(64)   # it gives way when an alert needs the room
        v.addWidget(card(label(self.t["in_base"], "micro"), self.outline, spacing=10), 1)

        # docs/roles.md, role 1: "a journal of one's own questions with
        # one-click repeat", because monthly reporting is the same question
        # twelve times. Until now the only list in the application was of
        # database files, so the one thing a person could repeat was opening
        # a file.
        self.journal_box = QWidget()
        jv = QVBoxLayout(self.journal_box)
        jv.setContentsMargins(0, 0, 0, 0)
        jv.setSpacing(10)
        jv.addWidget(label(self.t["journal"], "micro"))
        self.journal_list = QWidget()
        self.journal_rows = QVBoxLayout(self.journal_list)
        self.journal_rows.setContentsMargins(0, 0, 0, 0)
        self.journal_rows.setSpacing(2)
        jv.addWidget(self.journal_list)
        v.addWidget(self.journal_box)
        self._refresh_journal()

        v.addWidget(hairline())

        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 12, 0, 0)
        rh.setSpacing(12)
        self.ask_btn = button(self.t["ask"], primary=True)
        self.ask_btn.clicked.connect(self._ask)
        back = button(self.t["other_db"], link=True)
        back.clicked.connect(self._go_home)
        # The step and the seconds belong next to the button that started
        # them, not in a line of small grey text at the other end of the window.
        self.working = label("", "note")
        self.working.setWordWrap(False)
        self.stop_btn = button(self.t["stop"], link=True)
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.hide()
        # The key is shown only while it works: during a question it is
        # refused, and a key printed next to a dead button teaches nothing.
        self.key_hint = keycap(self.t["ask_key"])
        rh.addWidget(back)
        rh.addStretch(1)
        rh.addWidget(self.working)
        rh.addWidget(self.stop_btn)
        rh.addWidget(self.key_hint)
        rh.addSpacing(-4)
        rh.addWidget(self.ask_btn)
        v.addWidget(row)
        return w

    def _ask(self) -> None:
        q = self.question.toPlainText().strip()
        if not q:
            self._say(self.t["write_question"])
            return
        if not self.engine:
            self._go_home()
            return
        if self.asking:
            # The keyboard shortcut does not know that the button is disabled,
            # so two quick presses used to queue a second question. One model
            # answers one question at a time, so the second waited for the
            # first and then landed on top of its answer.
            return
        self._clear_alert()
        self.asked_question = q
        self.asking = True
        self.request += 1
        rid = self.request
        self.ask_btn.setEnabled(False)
        self.key_hint.hide()
        self.stop_btn.show()
        self.step, self.waited = self.t["writing"], 0
        self._tick()
        self.ticker.start()
        self.progress.start()
        if self.first_question:
            self._say(self.t["first_slow"])
        if self.client is not None:
            self.client.reset()
        task = AskTask(self.engine, q, self.t["unexpected"])
        task.signals.step.connect(lambda s, r=rid: self._step(r, s))
        task.signals.done.connect(lambda a, r=rid: self._show_answer(a, r))
        task.signals.failed.connect(lambda m, s, r=rid: self._show_error(m, r, s))
        # Held on the window, not left as a local. QThreadPool.start() does not
        # take a reference the Python side can see, so the only reference was
        # this frame's, and the task was collected before a worker picked it
        # up: activeThreadCount stayed 0, run() was never called, and the
        # window waited for an answer nobody was computing. The clock ticked,
        # the Stop button worked, and no question was ever answered. It took a
        # test that presses Ask and waits to see it; every earlier test built
        # widgets or called _show_answer directly.
        self.in_flight = task
        self.pool.start(task)

    def _abandon(self) -> None:
        """Stop waiting for the question in flight: its answer is no longer wanted.

        Called when the user opens another database or goes back to the start.
        The thread cannot be interrupted mid-answer, so instead the answer is
        dropped when it arrives, and the interface stops pretending to work.
        """
        self.request += 1
        self.asking = False
        self.ticker.stop()
        self.working.setText("")
        self.stop_btn.hide()
        self.key_hint.show()
        self.progress.stop()
        self.ask_btn.setEnabled(True)
        self._say("")       # nothing is being waited for, so nothing is being reported

    def _stop(self) -> None:
        """The question is given up on: the window moves on and the model is let go."""
        if self.client is not None:
            # Without this the next question would wait behind this one, and
            # the interface would look stuck for a reason nobody can see.
            self.client.cancel()
        self._abandon()
        self._say(self.t["stopped"])

    def _tick(self) -> None:
        self.working.setText(self.t["working_for"].format(step=self.step, s=self.waited))
        self.waited += 1

    def _current(self, rid: int) -> bool:
        """True when `rid` is still the question on screen."""
        if rid != self.request:
            return False
        self.asking = False
        self.ask_btn.setEnabled(True)
        self.stop_btn.hide()
        self.key_hint.show()
        self.ticker.stop()
        self.working.setText("")
        self.progress.stop()
        self._say("")       # the hint about the first question has had its moment
        self.first_question = False
        return True

    def _step(self, rid: int, name: str) -> None:
        if rid == self.request:
            self.step = self.t.get(name, name)
            self._tick()

    # ---------- page 3: answer ----------
    def _result_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        self.table = QTableWidget()
        head = self.table.horizontalHeader()
        # Not stretched to the window any more: a column is as wide as what is
        # in it, capped, and can be dragged. Stretching cut every value longer
        # than its share down to three dots, with no way to read the rest.
        head.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        head.setStretchLastSection(True)
        head.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(72)   # header and one row; above that it follows the answer
        # Reachable from the keyboard: four hundred rows cannot be read with
        # the mouse alone, and a cell nobody can select is a cell nobody can
        # copy. The dotted rectangle it once showed came from selecting row
        # one, which no longer happens.
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        copy = QShortcut(QKeySequence(QKeySequence.StandardKey.Copy), self.table, self._copy_cells)
        copy.setContext(Qt.ShortcutContext.WidgetShortcut)
        v.addWidget(self.table, 1)

        # Nothing found is an answer too, and it belongs where the rows would
        # have been rather than in a footnote under an empty frame.
        self.nothing = label(self.t["no_rows"], "sub")
        self.nothing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nothing.hide()
        v.addWidget(self.nothing, 1)

        self.rowline = label("", "note")
        v.addWidget(self.rowline)
        v.addWidget(label(self.t["counted"], "micro"))
        self.said = label("", "summary")
        v.addWidget(self.said)
        v.addStretch(0)     # takes what a short table leaves, so the table can hug its rows
        return w

    def _query_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        self.sql_view = QPlainTextEdit()
        self.sql_view.setObjectName("doc")
        self.sql_view.setReadOnly(True)
        self.sql_view.setFont(theme.mono())
        v.addWidget(card(label(self.t["sql"], "micro"), self.sql_view, spacing=10), 0)
        self.sql_note = label("", "note")
        v.addWidget(self.sql_note)
        v.addStretch(1)         # the card is as tall as the query, not as the window
        return w

    def _view(self, i: int) -> None:
        """Switch between the rows and the query; ⌘1 and ⌘2 do the same."""
        if self.pages.currentIndex() != 2:
            return
        self.tabs.select(i)
        self.views.setCurrentIndex(i)

    def _answer_page(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(12)

        self.asked = label("", "errtitle")
        v.addWidget(self.asked)

        # The table and the query are two readings of one answer, and on a
        # laptop screen they were taking each other's room: four rows of four
        # hundred above a query box with nothing in it. The switch in the bar
        # gives whichever one is being read the whole page.
        self.views = QStackedWidget()
        self.views.addWidget(self._result_view())
        self.views.addWidget(self._query_view())
        v.addWidget(self.views, 1)

        v.addWidget(hairline())
        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 12, 0, 0)
        rh.setSpacing(12)
        again = button(self.t["again"], primary=True)
        again.clicked.connect(self._new_question)
        copy = button(self.t["copy"], small=True)
        copy.clicked.connect(self._copy_sql)
        save = button(self.t["csv"], small=True)
        save.clicked.connect(self._save_csv)
        rh.addWidget(copy)
        rh.addWidget(save)
        rh.addStretch(1)
        rh.addWidget(again)
        v.addWidget(row)
        return w

    def _show_answer(self, a, rid: int = 0) -> None:
        if not self._current(rid):
            return
        self.answer = a
        # The question that was asked, not whatever is in the box now. A local
        # model thinks for about a minute, so typing the next question while
        # waiting is the ordinary thing to do, and the answer then appeared
        # under a heading naming a question it does not answer.
        self.asked.setText(self.asked_question or self.question.toPlainText().strip())
        self.table.clear()
        self.table.setColumnCount(len(a.columns))
        self.table.setHorizontalHeaderLabels(a.columns)
        self.table.setRowCount(len(a.rows))
        for r, row in enumerate(a.rows):
            for c, value in enumerate(row):
                text = "" if value is None else str(value)
                item = QTableWidgetItem(text)
                item.setToolTip(text)   # a value too wide for its column is still readable
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        for c in range(self.table.columnCount()):
            # One long free-text column must not push the other six off the
            # screen; past this width the rest is read in the tooltip.
            self.table.setColumnWidth(c, min(self.table.columnWidth(c), 320))
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        # Two rows in a frame the height of the window read as a table that
        # failed to load. Past what fits, it fills the page and scrolls.
        self.table.setMaximumHeight(
            self.table.horizontalHeader().height() + self.table.verticalHeader().length() + 4
        )
        self.table.setVisible(bool(a.rows))
        self.nothing.setVisible(not a.rows)
        extra = "  ·  ".join(a.notes)
        if not a.rows:
            self.rowline.setText(self.t["seconds"].format(s=a.seconds) + (f"  ·  {extra}" if extra else ""))
        else:
            self.rowline.setText(
                i18n.plural(self.t, "rows", len(a.rows))
                + "  ·  " + self.t["seconds"].format(s=a.seconds)
                + (f"  ·  {extra}" if extra else "")
            )
        self.said.setText(a.explanation)
        self.sql_view.setPlainText(a.sql)
        # Four lines of SQL in a box the height of the window read as a
        # mistake; forty lines need the room. The box follows the query.
        line = QFontMetrics(self.sql_view.font()).lineSpacing()
        self.sql_view.setFixedHeight(min(max(3, a.sql.count("\n") + 1) * line + 12, 460))
        self.sql_note.setText(extra)
        self._log(self.asked_question, a.sql, rows=len(a.rows), seconds=a.seconds,
                  truncated=a.truncated)
        self._to_page(2)
        self._view(0)
        self._say("")

    def _show_error(self, message: str, rid: int = 0, sql: str = "") -> None:
        if not self._current(rid):
            return
        self._log(self.asked_question, sql, rows=0, seconds=0.0, ok=False, error=message)
        # The first line is what happened; the rest is the detail, which can
        # be long and is worth keeping rather than cutting at the window edge.
        head, _, rest = message.partition("\n")
        detail = (rest.strip() and f"{head}\n{rest.strip()}") or head
        if sql:
            # design.md 4.4: "the query is shown, but not executed". It was
            # neither shown nor executed, so a user told their question went
            # beyond reading data had no way to see what had been written.
            detail = f"{detail}\n\n{self.t['refused_sql']}\n{sql}"
        self._fail(self.t["err_ask"], detail, self.t["retry"], self._ask)

    def _refresh_journal(self) -> None:
        """Redraw the recent questions. Hidden entirely when there are none."""
        if not hasattr(self, "journal_rows"):
            return                              # called before the page is built
        while self.journal_rows.count():
            old = self.journal_rows.takeAt(0).widget()
            if old is not None:
                old.deleteLater()
        shown = [e for e in journal.entries(limit=4) if e.ok and e.question]
        self.journal_box.setVisible(bool(shown))
        for entry in shown:
            row = QWidget()
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(12)
            # The question itself is the button. A row that looks like a label
            # with a separate "repeat" control beside it is two decisions where
            # the user has one intention.
            again = button(_ellipsis(entry.question, 72), link=True)
            again.setToolTip(self.t["journal_again"])
            again.clicked.connect(lambda _=False, q=entry.question: self._repeat(q))
            meta = label(
                self.t["journal_meta"].format(
                    when=entry.when(), n=entry.rows, db=entry.db_name),
                "note")
            rh.addWidget(again, 0)
            rh.addStretch(1)
            rh.addWidget(meta, 0)
            self.journal_rows.addWidget(row)

    def _repeat(self, question: str) -> None:
        """Put a past question back in the box and ask it again."""
        self.question.setPlainText(question)
        self.question.setFocus()
        self._ask()

    def _log(self, question: str, sql: str, *, rows: int, seconds: float,
             truncated: bool = False, ok: bool = True, error: str = "") -> None:
        """Write one line to the local journal. Never fatal, never remote."""
        if not question:
            return
        journal.append(journal.Entry(
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            question=question, sql=sql, rows=rows, seconds=round(seconds, 2),
            db_path=self.engine.db_path if self.engine else "", truncated=truncated, ok=ok,
            error=error.partition("\n")[0][:300],
        ))
        self._refresh_journal()

    def _new_question(self) -> None:
        self.question.selectAll()
        self._to_page(1)
        self.question.setFocus()

    def _back(self) -> None:
        """Escape: one step back, wherever that is from here."""
        if self.pages.currentIndex() == 2:
            self._new_question()
        elif self.pages.currentIndex() == 1:
            self._go_home()

    def _go_home(self) -> None:
        self._abandon()
        self.where_full = ""
        self._refresh_recent()
        self._to_page(0)

    def _to_page(self, i: int) -> None:
        # The switch in the bar belongs to the answer and nothing else; an
        # alert belongs to the screen it was raised on.
        self.pages.setCurrentIndex(i)
        self.tabs.setVisible(i == 2)
        self._fit_bar()
        self._clear_alert()
        self.updateGeometry()

    def _copy_cells(self) -> None:
        """⌘C over the table: the selected cells, tab separated, ready to paste into a sheet."""
        rows: dict[int, dict[int, str]] = {}
        for item in self.table.selectedItems():
            rows.setdefault(item.row(), {})[item.column()] = item.text()
        if not rows:
            return
        text = "\n".join(
            "\t".join(cells[c] for c in sorted(cells)) for _, cells in sorted(rows.items())
        )
        QGuiApplication.clipboard().setText(text)
        self._say(self.t["copied_cells"])

    def _copy_sql(self) -> None:
        if not self.answer:
            return              # the menu reaches here from every screen
        QGuiApplication.clipboard().setText(self.sql_view.toPlainText())
        self._say(self.t["copied"])

    def _save_csv(self) -> None:
        if not self.answer:
            return
        path, _ = QFileDialog.getSaveFileName(self, self.t["save_as"], "answer.csv", "CSV (*.csv)")
        if not path:
            return
        # A truncated answer holds only the page of rows that fits the screen,
        # so saving what is in memory would quietly save the part already seen.
        # That case re-runs the query and streams the whole result. An answer
        # that was not truncated already *is* the whole result, so it is
        # written straight out: no second query, nothing to get wrong.
        # The answer carries its own database, and it has to match the one open
        # now. "An engine exists" was not enough: opening another file after an
        # answer made the export run against that one instead, and with two
        # monthly copies of one schema it succeeded and wrote the wrong rows.
        same_db = (self.engine is not None
                   and self.answer.db_path
                   and self.engine.db_path == self.answer.db_path)
        full = self.answer.truncated and same_db
        if self.answer.truncated and not same_db:
            # The rows on screen are not the whole answer and the database they
            # came from is no longer the one open. Refusing beats writing a
            # short file, or another database's rows, and calling it the answer.
            self._say(self.t["cannot_save_full"])
            return
        try:
            if full:
                written = export_csv(self.answer.db_path,
                                     self.answer.export_sql or self.answer.sql,
                                     path, timeout=max(120.0, self.timeout_s * 4))
            else:
                # utf-8-sig, not utf-8: the file is opened in Excel more often
                # than anywhere else, and without the byte order mark Excel
                # reads it in the local codepage and every Cyrillic name comes
                # out as noise.
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.answer.columns)
                    writer.writerows(self.answer.rows)
                written = len(self.answer.rows)
        except (OSError, sqlite3.Error) as e:
            # A read-only folder or a full disk is the user's problem to fix,
            # but they have to be told. This used to raise inside the slot,
            # which prints a traceback nobody sees and leaves the saved-file
            # line off the screen with no hint of why.
            self._say(self.t["cannot_save"].format(error=e))
            return
        if full:
            # The screen said "first N of more". The file is not capped, and
            # saying so is the whole point of having re-run the query.
            self._say(self.t["saved_full"].format(path=path, n=written))
        else:
            self._say(self.t["saved"].format(path=path))

    def _say(self, text: str) -> None:
        """A passing word: copied, saved, stopped. Failures go to the alert instead.

        It clears itself after a few seconds. Left on the screen, "Запрос
        скопирован" is still there an hour later, next to a different answer.
        """
        self.status.setText(text)
        self.status.setVisible(bool(text))
        if text:
            QTimer.singleShot(5000, lambda said=text: self._unsay(said))

    def _unsay(self, said: str) -> None:
        if self.status.text() == said:
            self.status.setVisible(False)


def main() -> int:
    # Before anything else: the claim is that nothing leaves this computer, so
    # the program enforces it rather than relying on nobody adding a call later.
    offline.enable()
    if "--selftest" in sys.argv:
        return offline.selftest()
    app = QApplication(sys.argv)
    app.setApplicationName("Askbase")
    app.setApplicationDisplayName("Askbase")
    app.setOrganizationName(MAKER)
    theme.apply(app)
    app.setWindowIcon(QIcon(str(ICON.with_suffix(".icns"))))
    windows: list[Window] = []

    def place(w: Window) -> None:
        # Centre on the screen the cursor is on and come to the front. Without
        # this the window can open off-screen, for instance at coordinates left
        # over from a display that is no longer attached, and the application
        # looks as though it did not start at all.
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        area = screen.availableGeometry()
        box = w.frameGeometry()
        box.moveCenter(area.center())
        w.move(max(area.left(), box.left()), max(area.top(), box.top()))

    def open_window(code: str, old: Window | None = None) -> None:
        i18n.remember(code)
        w = Window(code)
        w.language_changed.connect(lambda c, cur=w: open_window(c, cur))
        if old is not None:
            # Switching language rebuilds the window; keep where it was and
            # keep the database open, or the switch would feel like a restart.
            w.setGeometry(old.geometry())
            if old.engine is not None:
                w.adopt(old)
            old.close()
            windows.remove(old)
        else:
            place(w)
        windows.append(w)
        w.show()
        w.raise_()
        w.activateWindow()

    open_window(i18n.ui_language())
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
