"""Interface text in Russian and English.

Kept as two flat dictionaries with the same keys, because a missing key should
be a loud failure in the tests rather than a half-translated window. The
language is remembered between launches in the system settings store, and the
first guess comes from the system language.
"""
from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "app": "Askbase",
        "trust": "данные остаются у вас",
        "trust_tip": "База открывается только на чтение, каждый запрос проверяется до выполнения, "
                     "сеть приложению не нужна.",
        # connect
        "drop_title": "Перетащите базу данных сюда",
        "recent": "НЕДАВНИЕ",
        "forget": "Убрать из списка",
        "drop_sub": "файл .sqlite, .sqlite3 или .db",
        "drop_release": "Отпустите, чтобы открыть",
        "choose_file": "Выбрать файл",
        "path_label": "Или укажите путь",
        "path_hint": "~/Documents/база.sqlite",
        "open": "Открыть",
        "model_label": "Модель на этом компьютере",
        "no_model_short": "модель не найдена",
        "no_model": "Модель не найдена. Askbase работает с моделью, установленной локально: "
                    "ollama pull hf.co/mradermacher/XiYanSQL-QwenCoder-7B-2504-GGUF:Q4_K_M",
        "readonly_note": "Подключение только на чтение. Приложению не нужна сеть.",
        # ask
        "question": "ВОПРОС",
        "placeholder": "Сколько новых клиентов пришло из каждого региона в сентябре",
        "examples": "Например: ",
        "example_of": "сколько записей в {table}",
        "in_base": "В ЭТОЙ БАЗЕ",
        "ask": "Спросить",
        "ask_key": "⌘↩",
        "stop": "Остановить",
        "stopped": "Вопрос остановлен.",
        "working_for": "{step}…  {s} с",
        "other_db": "←  другая база",
        "first_slow": "Первый вопрос дольше: модель загружается в память",
        "write_question": "Напишите вопрос.",
        # answer
        "counted": "ЧТО ПОСЧИТАНО",
        "sql": "ЗАПРОС SQL",
        "tab_answer": "Ответ",
        "tab_sql": "Запрос",
        "again": "Новый вопрос",
        "copy": "Копировать SQL",
        "copied": "Запрос скопирован",
        "copied_cells": "Скопировано в буфер",
        "csv": "Сохранить CSV",
        "saved": "Сохранено: {path}",
        "cannot_save": "Не удалось сохранить файл. {error}",
        "seconds": "{s:.1f} с",
        "rows_1": "{n} строка",
        "rows_2": "{n} строки",
        "rows_5": "{n} строк",
        "no_rows": "Запрос выполнен, подходящих строк нет.",
        "tables_1": "{n} таблица",
        "tables_2": "{n} таблицы",
        "tables_5": "{n} таблиц",
        "columns_1": "{n} столбец",
        "columns_2": "{n} столбца",
        "columns_5": "{n} столбцов",
        "readonly_short": "только чтение",
        # steps and errors
        "writing": "Составляю запрос",
        "checking": "Проверяю запрос",
        "fixing": "Исправляю запрос",
        "running": "Выполняю",
        "not_a_file": "Файл не найден: {path}",
        "cannot_open": "Не удалось открыть базу. {error}",
        "unexpected": "Непредвиденная ошибка.",
        "err_db": "База не открылась",
        "err_ask": "Ответа нет",
        "retry": "Спросить ещё раз",
        "choose_other": "Выбрать другой файл",
        # about
        "about": "О программе",
        "menu_file": "Файл",
        "open_db": "Открыть базу…",
        "close": "Закрыть",
        "about_1": "Вопрос к своей базе обычными словами.",
        "about_2": "Модель и данные остаются на этом компьютере.",
        "maker": "Сделано в {maker}",
        "choose_db": "Выберите базу данных",
        "db_filter": "Базы SQLite (*.sqlite *.sqlite3 *.db);;Все файлы (*)",
        "save_as": "Сохранить",
    },
    "en": {
        "app": "Askbase",
        "trust": "your data stays with you",
        "trust_tip": "The database is opened for reading only, every query is checked before it runs, "
                     "and the application does not need a network.",
        "drop_title": "Drop a database here",
        "recent": "RECENT",
        "forget": "Remove from the list",
        "drop_sub": "a .sqlite, .sqlite3 or .db file",
        "drop_release": "Release to open",
        "choose_file": "Choose a file",
        "path_label": "Or type a path",
        "path_hint": "~/Documents/database.sqlite",
        "open": "Open",
        "model_label": "Model on this computer",
        "no_model_short": "no model found",
        "no_model": "No model found. Askbase uses a model installed locally: "
                    "ollama pull hf.co/mradermacher/XiYanSQL-QwenCoder-7B-2504-GGUF:Q4_K_M",
        "readonly_note": "The connection is read-only. The application does not need a network.",
        "question": "QUESTION",
        "placeholder": "How many new customers came from each region in September",
        "examples": "For example: ",
        "example_of": "how many rows in {table}",
        "in_base": "IN THIS DATABASE",
        "ask": "Ask",
        "ask_key": "⌘↩",
        "stop": "Stop",
        "stopped": "The question was stopped.",
        "working_for": "{step}…  {s} s",
        "other_db": "←  another database",
        "first_slow": "The first question is slower while the model loads",
        "write_question": "Write a question.",
        "counted": "WHAT IT COUNTED",
        "sql": "SQL QUERY",
        "tab_answer": "Answer",
        "tab_sql": "Query",
        "again": "New question",
        "copy": "Copy SQL",
        "copied": "Query copied",
        "copied_cells": "Copied to the clipboard",
        "csv": "Save CSV",
        "saved": "Saved: {path}",
        "cannot_save": "Could not save the file. {error}",
        "seconds": "{s:.1f} s",
        "rows_1": "{n} row",
        "rows_2": "{n} rows",
        "rows_5": "{n} rows",
        "no_rows": "The query ran, and no rows matched.",
        "tables_1": "{n} table",
        "tables_2": "{n} tables",
        "tables_5": "{n} tables",
        "columns_1": "{n} column",
        "columns_2": "{n} columns",
        "columns_5": "{n} columns",
        "readonly_short": "read-only",
        "writing": "Writing the query",
        "checking": "Checking the query",
        "fixing": "Fixing the query",
        "running": "Running",
        "not_a_file": "File not found: {path}",
        "cannot_open": "Could not open the database. {error}",
        "unexpected": "Unexpected error.",
        "err_db": "The database did not open",
        "err_ask": "No answer",
        "retry": "Ask again",
        "choose_other": "Choose another file",
        "about": "About Askbase",
        "menu_file": "File",
        "open_db": "Open database…",
        "close": "Close",
        "about_1": "Ask your own database in plain words.",
        "about_2": "The model and the data stay on this computer.",
        "maker": "Made at {maker}",
        "choose_db": "Choose a database",
        "db_filter": "SQLite databases (*.sqlite *.sqlite3 *.db);;All files (*)",
        "save_as": "Save",
    },
}


def plural(t: dict[str, str], stem: str, n: int) -> str:
    """Count with its noun. Russian needs three forms where English needs two.

    "34 столбцов" in the title bar of a product sold on care is the kind of
    detail that is read as carelessness everywhere else, so the forms are in
    the tables rather than in a format string.
    """
    tens, ones = n % 100, n % 10
    if ones == 1 and tens != 11:
        form = "1"
    elif 2 <= ones <= 4 and not 12 <= tens <= 14:
        form = "2"
    else:
        form = "5"
    return t[f"{stem}_{form}"].format(n=n)


def settings():
    # Imported here, not at module level: the text table is plain data, and the
    # tests that check it should not need a GUI toolkit installed.
    from PySide6.QtCore import QSettings

    return QSettings("Besk Tech", "Askbase")


def ui_language() -> str:
    """The remembered language, or the system one, or Russian."""
    from PySide6.QtCore import QLocale

    saved = str(settings().value("lang", "") or "")
    if saved in TEXTS:
        return saved
    return "ru" if QLocale.system().language() == QLocale.Language.Russian else "en"


def remember(code: str) -> None:
    settings().setValue("lang", code)
