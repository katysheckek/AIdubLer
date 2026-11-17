from pathlib import Path

from .db import init_db
from .projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    db_path = project_root / "data" / "demo_projects.db"
    init_db(db_path)

    project = create_project(
        db_path,
        name="Базы данных",
        goal="Подготовиться к экзамену",
    )
    print("Создан:", project)

    loaded = get_project(db_path, project.id)
    print("Прочитан из БД:", loaded)

    updated = update_project(
        db_path,
        project.id,
        goal="Изучить JOIN и транзакции",
    )
    print("Изменён:", updated)

    print("Список проектов:", list_projects(db_path))

    delete_project(db_path, project.id)
    print("После удаления:", list_projects(db_path))


if __name__ == "__main__":
    main()