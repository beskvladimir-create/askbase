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
        "ex_count": "сколько записей в {table}",
        "ex_breakdown": "сколько {table} в разрезе {column}",
        "ex_ranking": "десять {table} с наибольшим {column}",
        "ex_period": "сколько {table} за сентябрь по {column}",
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
        "saved_full": "Сохранено полностью, {n} строк: {path}",
        "cannot_save_full": "База уже закрыта, а показанные строки это не весь ответ. Откройте базу и спросите заново.",
        # journal
        "journal": "ВАШИ ВОПРОСЫ",
        "journal_again": "Спросить это же ещё раз",
        "journal_meta": "{when}  ·  {n} стр.  ·  {db}",
        "refused_sql": "Запрос, который был отклонён:",
        # settings
        "settings": "Настройки",
        "ro_title": "Роль только на чтение",
        "ro_intro": "Для администратора базы. Askbase ничего не пишет и проверяет это при "
                    "подключении, но проверка приложения это не право доступа. Настоящая "
                    "граница ставится здесь, на стороне базы.",
        "ro_note": "Замените analytics на имя своей базы и задайте свой пароль. "
                   "PostgreSQL и MySQL в версии 0.1.0 ещё не поддерживаются приложением, "
                   "SQL приведён для подготовки контура заранее.",
        "ro_copy": "Скопировать SQL",
        "ro_page": "Открыть страницу целиком",
        "close": "Закрыть",
        "settings_bounds": "ГРАНИЦЫ ОТВЕТА",
        "set_max_rows": "Сколько строк показывать",
        "set_timeout": "Сколько ждать запрос",
        "set_bounds_note": "В CSV сохраняется весь результат, а не только показанные строки.",
        "settings_journal": "ЖУРНАЛ ВОПРОСОВ",
        "set_journal_note": "Лежит файлом здесь: {path}. Вопросы и запросы, без самих ответов.",
        "set_journal_show": "Показать в Finder",
        "set_journal_clear": "Очистить журнал",
        "set_journal_cleared": "Журнал очищен.",
        "settings_collect": "ЧТО СОБИРАЕТСЯ",
        "set_no_telemetry": "Ничего. Телеметрии нет, аналитики нет, учётной записи нет. "
                            "Журнал остаётся на этом компьютере и никуда не отправляется.",
        "save": "Сохранить",
        "set_saved": "Настройки сохранены.",
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
        "ex_count": "how many rows in {table}",
        "ex_breakdown": "how many {table} by {column}",
        "ex_ranking": "the ten {table} with the largest {column}",
        "ex_period": "how many {table} in September, by {column}",
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
        "saved_full": "Saved in full, {n} rows: {path}",
        "cannot_save_full": "The database is closed, and the rows on screen are not the whole answer. Open it and ask again.",
        # journal
        "journal": "YOUR QUESTIONS",
        "journal_again": "Ask this one again",
        "journal_meta": "{when}  ·  {n} rows  ·  {db}",
        "refused_sql": "The query that was refused:",
        # settings
        "settings": "Settings",
        "ro_title": "Read-only role",
        "ro_intro": "For the database administrator. Askbase writes nothing and verifies that "
                    "on connect, but a check inside an application is not a permission. The "
                    "real boundary is set here, on the database side.",
        "ro_note": "Replace analytics with your own database name and set your own password. "
                   "PostgreSQL and MySQL are not supported by the application in 0.1.0; the SQL "
                   "is here so the environment can be prepared in advance.",
        "ro_copy": "Copy the SQL",
        "ro_page": "Open the full page",
        "close": "Close",
        "settings_bounds": "BOUNDS ON AN ANSWER",
        "set_max_rows": "Rows to show",
        "set_timeout": "How long to wait for a query",
        "set_bounds_note": "A CSV holds the whole result, not only the rows on screen.",
        "settings_journal": "JOURNAL OF QUESTIONS",
        "set_journal_note": "A file, here: {path}. Questions and queries, never the answers.",
        "set_journal_show": "Show in Finder",
        "set_journal_clear": "Clear the journal",
        "set_journal_cleared": "Journal cleared.",
        "settings_collect": "WHAT IS COLLECTED",
        "set_no_telemetry": "Nothing. No telemetry, no analytics, no account. The journal stays "
                            "on this computer and is never sent anywhere.",
        "save": "Save",
        "set_saved": "Settings saved.",
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
