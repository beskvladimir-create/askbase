"""Askbase: three screens, connect then ask then read.

The window is deliberately thin. Everything that can be wrong about an answer
is decided in engine.py and safety.py, which are tested without Qt; this file
arranges it on screen and keeps the model off the interface thread.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QPlainTextEdit, QPushButton, QSizePolicy, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import theme
from .engine import AskError, Engine
from .models import ModelClient, installed_models

STEPS = {
    "writing": "Составляю запрос",
    "checking": "Проверяю запрос",
    "fixing": "Исправляю запрос",
    "running": "Выполняю",
}


def card(*children: QWidget, spacing: int = 16) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(24, 24, 24, 24)
    lay.setSpacing(spacing)
    for c in children:
        lay.addWidget(c)
    return f


def label(text: str, name: str = "") -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(True)
    return lb


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    step = Signal(str)


class AskTask(QRunnable):
    """One question, off the interface thread so the window stays alive."""

    def __init__(self, engine: Engine, question: str):
        super().__init__()
        self.engine, self.question = engine, question
        self.signals = Signals()

    @Slot()
    def run(self) -> None:
        try:
            answer = self.engine.ask(self.question, on_step=self.signals.step.emit)
        except AskError as e:
            self.signals.failed.emit(str(e))
        except Exception:                       # never leave the user at a frozen screen
            self.signals.failed.emit(
                "Непредвиденная ошибка. Подробности:\n" + traceback.format_exc(limit=3)
            )
        else:
            self.signals.done.emit(answer)


class Window(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Askbase")
        self.resize(1060, 760)
        self.engine: Engine | None = None
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(1)          # one model, one question at a time

        root = QWidget()
        root.setObjectName("root")
        self.pages = QStackedWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.pages)
        self.status = label("", "status")
        outer.addWidget(self.status)
        self.setCentralWidget(root)

        self.pages.addWidget(self._connect_screen())
        self.pages.addWidget(self._ask_screen())
        self.pages.addWidget(self._answer_screen())
        self.pages.setCurrentIndex(0)

    # ---------- screen 1: connect ----------
    def _connect_screen(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(48, 48, 48, 32)
        lay.setSpacing(20)

        lay.addWidget(label("ПОДКЛЮЧЕНИЕ", "micro"))
        lay.addWidget(label("Спросите свою базу данных\nобычными словами", "headline"))
        lay.addWidget(label("Данные и модель остаются на этом компьютере.", "sub"))

        self.drop = label("Перетащите файл .sqlite или .db сюда", "doctitle")
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop.setMinimumHeight(120)
        pick = QPushButton("Выбрать файл")
        pick.setProperty("primary", True)
        pick.clicked.connect(self._pick_file)
        lay.addWidget(card(self.drop, pick))

        self.model_box = QComboBox()
        found = installed_models()
        self.model_box.addItems(found or ["модель не найдена"])
        self.model_box.setEnabled(bool(found))
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(label("Модель на этом компьютере", "note"))
        rl.addWidget(self.model_box, 1)
        lay.addWidget(row)

        if not found:
            lay.addWidget(label(
                "Модель не найдена. Askbase работает с моделью, установленной локально "
                "через Ollama. Установите её командой:\n"
                "ollama pull hf.co/mradermacher/XiYanSQL-QwenCoder-7B-2504-GGUF:Q4_K_M",
                "errbody",
            ))

        lay.addStretch(1)
        lay.addWidget(label("Приложению не нужна сеть", "footer"))
        self.setAcceptDrops(True)
        return w

    def dragEnterEvent(self, e) -> None:          # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:               # noqa: N802
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self._open(path)
                return

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите базу данных", str(Path.home()),
            "Базы SQLite (*.sqlite *.sqlite3 *.db);;Все файлы (*)",
        )
        if path:
            self._open(path)

    def _open(self, path: str) -> None:
        if not os.path.isfile(path):
            self._say(f"Файл не найден: {path}")
            return
        try:
            self.engine = Engine(path, ModelClient(self.model_box.currentText()))
        except Exception as e:
            self._say(f"Не удалось открыть базу. {e}")
            return
        s = self.engine.schema
        self.db_line.setText(
            f"{Path(path).name} · {len(s.tables)} таблиц · {s.n_columns} столбцов · только чтение"
        )
        self.examples.setText(self._examples())
        self.pages.setCurrentIndex(1)
        self.question.setFocus()
        self._say("")

    def _examples(self) -> str:
        """Suggestions built from this database, because an empty field is a dead end."""
        if not self.engine:
            return ""
        names = list(self.engine.schema.tables)[:3]
        return "Например: " + "; ".join(f"сколько записей в {n}" for n in names)

    # ---------- screen 2: ask ----------
    def _ask_screen(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(48, 40, 48, 32)
        lay.setSpacing(16)

        self.db_line = label("", "micro")
        lay.addWidget(self.db_line)

        self.question = QPlainTextEdit()
        self.question.setObjectName("doc")
        self.question.setPlaceholderText("Сколько новых клиентов пришло из каждого региона в сентябре")
        self.question.setFixedHeight(120)
        lay.addWidget(card(self.question))

        self.examples = label("", "note")
        lay.addWidget(self.examples)

        self.ask_btn = QPushButton("Спросить")
        self.ask_btn.setProperty("primary", True)
        self.ask_btn.clicked.connect(self._ask)
        back = QPushButton("Другая база")
        back.setProperty("small", True)
        back.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.ask_btn)
        rl.addWidget(back)
        rl.addStretch(1)
        lay.addWidget(row)
        lay.addStretch(1)
        return w

    def _ask(self) -> None:
        q = self.question.toPlainText().strip()
        if not q:
            self._say("Напишите вопрос.")
            return
        if not self.engine:
            self.pages.setCurrentIndex(0)
            return
        self.ask_btn.setEnabled(False)
        task = AskTask(self.engine, q)
        task.signals.step.connect(lambda s: self._say(STEPS.get(s, s) + "…"))
        task.signals.done.connect(self._show_answer)
        task.signals.failed.connect(self._show_error)
        self.pool.start(task)

    # ---------- screen 3: answer ----------
    def _answer_screen(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(48, 40, 48, 32)
        lay.setSpacing(14)

        self.asked = label("", "errtitle")
        lay.addWidget(self.asked)

        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(120)
        lay.addWidget(self.table, 1)

        self.rowline = label("", "note")
        lay.addWidget(self.rowline)

        lay.addWidget(label("ЧТО ПОСЧИТАНО", "micro"))
        self.said = label("", "summary")
        lay.addWidget(self.said)

        self.sql_view = QPlainTextEdit()
        self.sql_view.setObjectName("doc")
        self.sql_view.setReadOnly(True)
        self.sql_view.setFixedHeight(110)
        self.sql_view.setFont(theme.mono())
        lay.addWidget(card(label("ЗАПРОС SQL", "micro"), self.sql_view, spacing=10))

        again = QPushButton("Новый вопрос")
        again.setProperty("primary", True)
        again.clicked.connect(self._new_question)
        copy = QPushButton("Копировать SQL")
        copy.setProperty("small", True)
        copy.clicked.connect(self._copy_sql)
        save = QPushButton("Сохранить CSV")
        save.setProperty("small", True)
        save.clicked.connect(self._save_csv)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        for b in (again, copy, save):
            rl.addWidget(b)
        rl.addStretch(1)
        lay.addWidget(row)
        return w

    def _show_answer(self, a) -> None:
        self.ask_btn.setEnabled(True)
        self.asked.setText(self.question.toPlainText().strip())
        self.table.clear()
        self.table.setColumnCount(len(a.columns))
        self.table.setHorizontalHeaderLabels(a.columns)
        self.table.setRowCount(len(a.rows))
        for r, row in enumerate(a.rows):
            for c, value in enumerate(row):
                text = "" if value is None else str(value)
                self.table.setItem(r, c, QTableWidgetItem(text))
        if not a.rows:
            self.rowline.setText("Запрос выполнен, подходящих строк нет.")
        else:
            extra = "  ·  ".join(a.notes)
            self.rowline.setText(
                f"{len(a.rows)} строк, {a.seconds:.1f} с" + (f"  ·  {extra}" if extra else "")
            )
        self.table.clearSelection()          # no stray box on the first row
        self.said.setText(a.explanation)
        self.sql_view.setPlainText(a.sql)
        self._answer = a
        self.pages.setCurrentIndex(2)
        self._say("")

    def _show_error(self, message: str) -> None:
        self.ask_btn.setEnabled(True)
        self._say(message)

    def _new_question(self) -> None:
        self.question.selectAll()
        self.pages.setCurrentIndex(1)
        self.question.setFocus()

    def _copy_sql(self) -> None:
        QGuiApplication.clipboard().setText(self.sql_view.toPlainText())
        self._say("Запрос скопирован")

    def _save_csv(self) -> None:
        import csv

        path, _ = QFileDialog.getSaveFileName(self, "Сохранить", "answer.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self._answer.columns)
            writer.writerows(self._answer.rows)
        self._say(f"Сохранено: {path}")

    def _say(self, text: str) -> None:
        self.status.setText(text)


def main() -> int:
    app = QApplication(sys.argv)
    theme.apply(app)
    Window().show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
