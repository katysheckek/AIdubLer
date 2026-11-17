import sqlite3
from contextlib import closing
from pathlib import Path


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    """Открывает БД и включает проверку связей между таблицами."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | Path) -> None:
    """Создаёт начальную таблицу, сохраняя существующие данные."""
    with closing(connect_db(db_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                    goal TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )