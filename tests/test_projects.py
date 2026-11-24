from pathlib import Path

import pytest

from src.backend.db import init_db
from src.backend.projects import (
    ProjectNotFoundError,
    ValidationError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


def test_create_and_read_project(db_path: Path) -> None:
    created = create_project(
        db_path,
        name="  Базы данных  ",
        goal="Сдать экзамен",
        description="Материалы лекций",
    )

    loaded = get_project(db_path, created.id)

    assert loaded == created
    assert loaded.id > 0
    assert loaded.name == "Базы данных"
    assert loaded.goal == "Сдать экзамен"
    assert loaded.description == "Материалы лекций"


@pytest.mark.parametrize("name", ["", " \t\n", None, 42])
def test_invalid_name(db_path: Path, name) -> None:
    with pytest.raises(ValidationError):
        create_project(db_path, name=name)


def test_missing_project(db_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError):
        get_project(db_path, project_id=999)


def test_reinitialization_preserves_project(db_path: Path) -> None:
    created = create_project(db_path, name="Математика")

    init_db(db_path)

    assert get_project(db_path, created.id) == created


def test_name_with_apostrophe(db_path: Path) -> None:
    name = "Курс O'Reilly"
    created = create_project(db_path, name=name)

    assert get_project(db_path, created.id).name == name

def test_empty_project_list(db_path: Path) -> None:
    assert list_projects(db_path) == []


def test_list_projects(db_path: Path) -> None:
    first = create_project(db_path, name="Базы данных")
    second = create_project(db_path, name="Математика")

    assert list_projects(db_path) == [first, second]


def test_update_name_preserves_other_data(db_path: Path) -> None:
    created = create_project(
        db_path,
        name="Базы данных",
        goal="Сдать экзамен",
        description="Лекции",
    )
    other = create_project(db_path, name="Другой проект")

    updated = update_project(
        db_path,
        created.id,
        name="  Подготовка по БД  ",
    )

    assert updated.name == "Подготовка по БД"
    assert updated.goal == created.goal
    assert updated.description == created.description
    assert updated.created_at == created.created_at
    assert get_project(db_path, created.id) == updated
    assert get_project(db_path, other.id) == other


def test_update_all_fields(db_path: Path) -> None:
    created = create_project(db_path, name="Черновик")

    updated = update_project(
        db_path,
        created.id,
        name="Базы данных",
        goal="Изучить SQL",
        description="Лекции и практика",
    )

    assert updated.name == "Базы данных"
    assert updated.goal == "Изучить SQL"
    assert updated.description == "Лекции и практика"
    assert updated.created_at == created.created_at
    assert get_project(db_path, created.id) == updated


def test_clear_optional_fields(db_path: Path) -> None:
    created = create_project(
        db_path,
        name="Базы данных",
        goal="Сдать экзамен",
        description="Лекции",
    )

    updated = update_project(
        db_path,
        created.id,
        goal="",
        description=" ",
    )

    assert updated.goal == ""
    assert updated.description == ""
    assert get_project(db_path, created.id) == updated


def test_update_without_fields(db_path: Path) -> None:
    created = create_project(db_path, name="Базы данных")

    assert update_project(db_path, created.id) == created


@pytest.mark.parametrize("name", ["", " \t\n", 123])
def test_invalid_update_preserves_project(
    db_path: Path,
    name,
) -> None:
    created = create_project(
        db_path,
        name="Базы данных",
        goal="Сдать экзамен",
    )

    with pytest.raises(ValidationError):
        update_project(
            db_path,
            created.id,
            name=name,
            goal="Другая цель",
        )

    assert get_project(db_path, created.id) == created


@pytest.mark.parametrize("field_name", ["goal", "description"])
def test_invalid_optional_field(
    db_path: Path,
    field_name: str,
) -> None:
    created = create_project(db_path, name="Базы данных")

    with pytest.raises(ValidationError):
        update_project(
            db_path,
            created.id,
            **{field_name: 42},
        )

    assert get_project(db_path, created.id) == created


def test_update_missing_project(db_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError):
        update_project(db_path, 999, name="Новое название")


def test_delete_preserves_other_project(db_path: Path) -> None:
    deleted = create_project(db_path, name="Удаляемый")
    other = create_project(db_path, name="Оставляемый")

    delete_project(db_path, deleted.id)

    with pytest.raises(ProjectNotFoundError):
        get_project(db_path, deleted.id)

    assert list_projects(db_path) == [other]


def test_delete_missing_project(db_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError):
        delete_project(db_path, 999)