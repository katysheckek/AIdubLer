import shutil
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO

from .db import connect_db
from .projects import ValidationError, get_project


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}


@dataclass(frozen=True)
class Document:
    id: int
    project_id: int
    original_filename: str
    storage_path: str
    size_bytes: int
    created_at: str


class UnsupportedFormatError(ValidationError):
    """Для формата файла нет загрузчика."""


def upload_document(
    db_path: str | Path,
    storage_dir: str | Path,
    project_id: int,
    filename: str,
    content: BinaryIO,
) -> Document:
    """Сохраняет поток файла и его связь с существующим проектом."""
    get_project(db_path, project_id)
    # Браузер может передать путь Windows; имя не используется как путь хранения.
    original_filename = Path(filename.replace("\\", "/")).name
    if not original_filename or "\x00" in original_filename:
        raise ValidationError("Укажите имя файла.")

    extension = Path(original_filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            "Неподдерживаемый формат файла. Допустимы PDF, DOCX и PPTX."
        )

    project_dir = Path(storage_dir).resolve() / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    stored_path = None

    try:
        # Уникальное имя не позволяет перезаписать одноимённый материал.
        with NamedTemporaryFile(
            dir=project_dir, suffix=extension, delete=False
        ) as destination:
            stored_path = Path(destination.name)
            shutil.copyfileobj(content, destination, length=1024 * 1024)

        size_bytes = stored_path.stat().st_size
        if size_bytes == 0:
            raise ValidationError("Файл пуст. Загрузите документ с текстом.")

        created_at = datetime.now(UTC).isoformat()
        with closing(connect_db(db_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO documents (
                        project_id, original_filename, storage_path,
                        size_bytes, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        project_id, original_filename, str(stored_path),
                        size_bytes, created_at,
                    ),
                )
                document_id = cursor.lastrowid
                if document_id is None:
                    raise RuntimeError("Не удалось получить ID документа.")
    except Exception:
        if stored_path is not None:
            stored_path.unlink(missing_ok=True)
        raise

    return Document(
        id=document_id,
        project_id=project_id,
        original_filename=original_filename,
        storage_path=str(stored_path),
        size_bytes=size_bytes,
        created_at=created_at,
    )


def list_documents(db_path: str | Path, project_id: int) -> list[Document]:
    """Возвращает только документы указанного проекта."""
    get_project(db_path, project_id)
    with closing(connect_db(db_path)) as connection:
        rows = connection.execute(
            "SELECT * FROM documents WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
    return [Document(**dict(row)) for row in rows]
