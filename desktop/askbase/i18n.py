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
        # connect
        "drop_title": "Перетащите базу данных сюда",
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
        "ask": "Спросить",
        "other_db": "←  другая база",
        "first_slow": "Первый вопрос дольше: модель загружается в память",
        "write_question": "Напишите вопрос.",
        # answer
        "counted": "ЧТО ПОСЧИТАНО",
        "sql": "ЗАПРОС SQL",
        "again": "Новый вопрос",
        "copy": "Копировать SQL",
        "copied": "Запрос скопирован",
        "csv": "Сохранить CSV",
        "saved": "Сохранено: {path}",
        "rows": "{n} строк  ·  {s:.1f} с",
        "no_rows": "Запрос выполнен, подходящих строк нет.",
        "tables": "{n} таблиц  ·  {c} столбцов  ·  только чтение",
        # steps and errors
        "writing": "Составляю запрос",
        "checking": "Проверяю запрос",
        "fixing": "Исправляю запрос",
        "running": "Выполняю",
        "not_a_file": "Файл не найден: {path}",
        "cannot_open": "Не удалось открыть базу. {error}",
        "unexpected": "Непредвиденная ошибка.",
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
        "drop_title": "Drop a database here",
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
        "ask": "Ask",
        "other_db": "←  another database",
        "first_slow": "The first question is slower while the model loads",
        "write_question": "Write a question.",
        "counted": "WHAT IT COUNTED",
        "sql": "SQL QUERY",
        "again": "New question",
        "copy": "Copy SQL",
        "copied": "Query copied",
        "csv": "Save CSV",
        "saved": "Saved: {path}",
        "rows": "{n} rows  ·  {s:.1f} s",
        "no_rows": "The query ran, and no rows matched.",
        "tables": "{n} tables  ·  {c} columns  ·  read-only",
        "writing": "Writing the query",
        "checking": "Checking the query",
        "fixing": "Fixing the query",
        "running": "Running",
        "not_a_file": "File not found: {path}",
        "cannot_open": "Could not open the database. {error}",
        "unexpected": "Unexpected error.",
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
