from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .db import connect_db


@dataclass(frozen=True)
class Project:
    id: int
    name: str
    goal: str
    description: str
    created_at: str
    updated_at: str


class ValidationError(ValueError):
    """Входные данные не соответствуют требованиям."""


class ProjectNotFoundError(LookupError):
    """Проект с указанным ID отсутствует."""


def _normalize_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(
            f"Поле '{field_name}' должно быть строкой."
        )
    return value.strip()


def create_project(
    db_path: str | Path,
    name: str,
    goal: str = "",
    description: str = "",
) -> Project:
    """Проверяет данные, сохраняет проект и возвращает его."""
    name = _normalize_text(name, "name")
    goal = _normalize_text(goal, "goal")
    description = _normalize_text(description, "description")

    if not name:
        raise ValidationError(
            "Название проекта не должно быть пустым."
        )

    now = datetime.now(UTC).isoformat()

    with closing(connect_db(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    name, goal, description, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, goal, description, now, now),
            )

            project_id = cursor.lastrowid
            if project_id is None:
                raise RuntimeError(
                    "Не удалось получить ID созданного проекта."
                )

    return Project(
        id=project_id,
        name=name,
        goal=goal,
        description=description,
        created_at=now,
        updated_at=now,
    )


def get_project(
    db_path: str | Path,
    project_id: int,
) -> Project:
    """Возвращает проект или сообщает, что он отсутствует."""
    with closing(connect_db(db_path)) as connection:
        row = connection.execute(
            """
            SELECT id, name, goal, description, created_at, updated_at
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

    if row is None:
        raise ProjectNotFoundError(
            f"Проект с ID {project_id} не найден."
        )

    return Project(**dict(row))

def list_projects(db_path: str | Path) -> list[Project]:
    """Возвращает проекты в порядке их ID."""
    with closing(connect_db(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, name, goal, description, created_at, updated_at
            FROM projects
            ORDER BY id
            """
        ).fetchall()

    return [Project(**dict(row)) for row in rows]


def update_project(
    db_path: str | Path,
    project_id: int,
    *,
    name: str | None = None,
    goal: str | None = None,
    description: str | None = None,
) -> Project:
    """Изменяет только переданные поля проекта."""
    if name is not None:
        name = _normalize_text(name, "name")
        if not name:
            raise ValidationError(
                "Название проекта не должно быть пустым."
            )

    if goal is not None:
        goal = _normalize_text(goal, "goal")

    if description is not None:
        description = _normalize_text(description, "description")

    if name is None and goal is None and description is None:
        return get_project(db_path, project_id)

    now = datetime.now(UTC).isoformat()

    with closing(connect_db(db_path)) as connection:
        with connection:
            row = connection.execute(
                """
                UPDATE projects
                SET name = COALESCE(?, name),
                    goal = COALESCE(?, goal),
                    description = COALESCE(?, description),
                    updated_at = ?
                WHERE id = ?
                RETURNING
                    id, name, goal, description, created_at, updated_at
                """,
                (name, goal, description, now, project_id),
            ).fetchone()

            if row is None:
                raise ProjectNotFoundError(
                    f"Проект с ID {project_id} не найден."
                )

    return Project(**dict(row))


def delete_project(
    db_path: str | Path,
    project_id: int,
) -> None:
    """Удаляет проект или сообщает, что он отсутствует."""
    with closing(connect_db(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                "DELETE FROM projects WHERE id = ?",
                (project_id,),
            )

            if cursor.rowcount == 0:
                raise ProjectNotFoundError(
                    f"Проект с ID {project_id} не найден."
                )