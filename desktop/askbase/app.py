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
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QDialog, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import i18n, offline, theme
from .engine import AskError, Engine
from .models import ModelClient, installed_models
from .widgets import BrandMark, DropZone, Ground, LangSwitch, ProgressLine, glow

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


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
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
            answer = self.engine.ask(self.question, on_step=self.signals.step.emit)
        except AskError as e:
            self.signals.failed.emit(str(e))
        except Exception:                       # never leave the user at a frozen screen
            self.signals.failed.emit(f"{self.unexpected}\n" + traceback.format_exc(limit=2))
        else:
            self.signals.done.emit(answer)


class Window(QMainWindow):
    language_changed = Signal(str)

    def __init__(self, lang: str = "ru") -> None:
        super().__init__()
        self.lang = lang
        self.t = i18n.TEXTS[lang]
        self.engine: Engine | None = None
        self.answer = None
        self.first_question = True
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
        bv.addWidget(self.pages, 1)
        outer.addWidget(body, 1)

        self.setCentralWidget(root)
        self.pages.setCurrentIndex(0)
        self._menu()

    def _menu(self) -> None:
        m = self.menuBar().addMenu(self.t["menu_file"])
        about = QAction(self.t["about"], self)
        about.setMenuRole(QAction.MenuRole.AboutRole)   # lands in the app menu on macOS
        about.triggered.connect(self._about)
        m.addAction(about)
        open_db = QAction(self.t["open_db"], self)
        open_db.setShortcut(QKeySequence.StandardKey.Open)
        open_db.triggered.connect(self._pick)
        m.addAction(open_db)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._ask)
        QShortcut(QKeySequence("Meta+Return"), self, self._ask)

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
        h.addWidget(self.where, 1)

        self.trust = label(self.t["trust"], "trust")
        self.trust.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.trust.setWordWrap(False)   # one line, or it rides up into the window buttons
        self.langs = LangSwitch(self.lang)
        self.langs.changed.connect(self.language_changed.emit)
        right = QWidget()
        right.setMinimumWidth(210)
        rh = QHBoxLayout(right)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(14)
        rh.addStretch(1)
        rh.addWidget(self.trust)
        rh.addWidget(self.langs)
        h.addWidget(right)
        return bar

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
        ph.addWidget(label(self.t["path_label"], "note"), 0)
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
        rh.addWidget(label(self.t["model_label"], "note"), 0)
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
        self.model_box.setCurrentText(old.model_box.currentText())
        if self.engine is not None:
            s = self.engine.schema
            self.where.setText(
                f"{Path(self.engine.db_path).name}  ·  "
                + self.t["tables"].format(n=len(s.tables), c=s.n_columns)
            )
            self.examples.setText(
                self.t["examples"] + ";  ".join(
                    self.t["example_of"].format(table=n) for n in list(s.tables)[:3]
                )
            )
            self.question.setPlainText(old.question.toPlainText())
            self.pages.setCurrentIndex(1)

    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.t["choose_db"], str(Path.home()),
            self.t["db_filter"],
        )
        if path:
            self._open(path)

    def _open(self, path: str) -> None:
        if not os.path.isfile(path):
            self._say(self.t["not_a_file"].format(path=path))
            return
        try:
            self.engine = Engine(path, ModelClient(self.model_box.currentText()))
        except Exception as e:
            self._say(self.t["cannot_open"].format(error=e))
            return
        s = self.engine.schema
        self.where.setText(
            f"{Path(path).name}  ·  " + self.t["tables"].format(n=len(s.tables), c=s.n_columns)
        )
        self.examples.setText(
            self.t["examples"] + ";  ".join(
                self.t["example_of"].format(table=n) for n in list(s.tables)[:3]
            )
        )
        self.pages.setCurrentIndex(1)
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

        self.examples = label("", "note")
        v.addWidget(self.examples)
        v.addStretch(1)
        v.addWidget(hairline())

        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 12, 0, 0)
        rh.setSpacing(12)
        self.ask_btn = button(self.t["ask"], primary=True)
        self.ask_btn.clicked.connect(self._ask)
        back = button(self.t["other_db"], link=True)
        back.clicked.connect(self._go_home)
        rh.addWidget(back)
        rh.addStretch(1)
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
        self.ask_btn.setEnabled(False)
        self.progress.start()
        if self.first_question:
            self._say(self.t["first_slow"])
        task = AskTask(self.engine, q, self.t["unexpected"])
        task.signals.step.connect(lambda s: self._say(self.t.get(s, s) + "…"))
        task.signals.done.connect(self._show_answer)
        task.signals.failed.connect(self._show_error)
        self.pool.start(task)

    # ---------- page 3: answer ----------
    def _answer_page(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(12)

        self.asked = label("", "errtitle")
        v.addWidget(self.asked)

        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(140)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # no dotted rectangle on row one
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        v.addWidget(self.table, 1)

        self.rowline = label("", "note")
        v.addWidget(self.rowline)

        v.addWidget(label(self.t["counted"], "micro"))
        self.said = label("", "summary")
        v.addWidget(self.said)

        self.sql_view = QPlainTextEdit()
        self.sql_view.setObjectName("doc")
        self.sql_view.setReadOnly(True)
        self.sql_view.setFixedHeight(104)
        self.sql_view.setFont(theme.mono())
        v.addWidget(card(label(self.t["sql"], "micro"), self.sql_view, spacing=10))

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

    def _show_answer(self, a) -> None:
        self.ask_btn.setEnabled(True)
        self.progress.stop()
        self.first_question = False
        self.answer = a
        self.asked.setText(self.question.toPlainText().strip())
        self.table.clear()
        self.table.setColumnCount(len(a.columns))
        self.table.setHorizontalHeaderLabels(a.columns)
        self.table.setRowCount(len(a.rows))
        for r, row in enumerate(a.rows):
            for c, value in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        self.table.clearSelection()
        if not a.rows:
            self.rowline.setText(self.t["no_rows"])
        else:
            extra = "  ·  ".join(a.notes)
            self.rowline.setText(
                self.t["rows"].format(n=len(a.rows), s=a.seconds) + (f"  ·  {extra}" if extra else "")
            )
        self.said.setText(a.explanation)
        self.sql_view.setPlainText(a.sql)
        self.pages.setCurrentIndex(2)
        self._say("")

    def _show_error(self, message: str) -> None:
        self.ask_btn.setEnabled(True)
        self.progress.stop()
        self.first_question = False
        self._say(message)

    def _new_question(self) -> None:
        self.question.selectAll()
        self.pages.setCurrentIndex(1)
        self.question.setFocus()

    def _go_home(self) -> None:
        self.where.setText("")
        self.pages.setCurrentIndex(0)

    def _copy_sql(self) -> None:
        QGuiApplication.clipboard().setText(self.sql_view.toPlainText())
        self._say(self.t["copied"])

    def _save_csv(self) -> None:
        if not self.answer:
            return
        path, _ = QFileDialog.getSaveFileName(self, self.t["save_as"], "answer.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.answer.columns)
            writer.writerows(self.answer.rows)
        self._say(self.t["saved"].format(path=path))

    def _say(self, text: str) -> None:
        self.status.setText(text)
        self.status.setVisible(bool(text))


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
