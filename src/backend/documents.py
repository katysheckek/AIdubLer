import shutil
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO

from src.ai.fragmentation.chunking import chunk_documents
from src.ai.fragmentation.loaders import SUPPORTED_EXTENSIONS, load_document

from .db import connect_db
from .projects import ValidationError, get_project


@dataclass(frozen=True)
class Document:
    id: int
    project_id: int
    original_filename: str
    storage_path: str
    size_bytes: int
    created_at: str


@dataclass(frozen=True)
class DocumentChunk:
    id: int
    document_id: int
    text: str
    source: str
    location: str
    page_number: int | None
    chunk_index: int


class UnsupportedFormatError(ValidationError):
    """Для формата файла нет загрузчика."""


class DocumentProcessingError(ValidationError):
    """Текст не удалось извлечь из документа."""


def _process_document(path: Path, original_filename: str) -> list[dict]:
    try:
        sections = load_document(path)
        for section in sections:
            # Загрузчик видит техническое имя файла, пользователю нужно исходное.
            section["source"] = original_filename
        chunks = chunk_documents(sections)
    except Exception as error:
        raise DocumentProcessingError(
            "Не удалось извлечь текст. Файл повреждён, защищён паролем "
            "или его содержимое не соответствует формату."
        ) from error

    if not chunks:
        raise DocumentProcessingError(
            "В документе нет извлекаемого текста. Загрузите документ с текстом; "
            "для сканированного PDF требуется OCR."
        )

    return chunks


def upload_document(
    db_path: str | Path,
    storage_dir: str | Path,
    project_id: int,
    filename: str,
    content: BinaryIO,
) -> Document:
    """Принимает файл, извлекает текст и сохраняет документ с фрагментами."""
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

        chunks = _process_document(stored_path, original_filename)
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
                connection.executemany(
                    """
                    INSERT INTO document_chunks (
                        document_id, text, source, location,
                        page_number, chunk_index
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            document_id, chunk["text"], chunk["source"],
                            chunk["location"],
                            int(chunk["location"].split(":")[1])
                            if extension == ".pdf" else None,
                            chunk["chunk_index"],
                        )
                        for chunk in chunks
                    ],
                )
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


def list_project_chunks(
    db_path: str | Path, project_id: int
) -> list[DocumentChunk]:
    """Находит фрагменты проекта через связь с исходными документами."""
    get_project(db_path, project_id)
    with closing(connect_db(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT chunks.*
            FROM document_chunks AS chunks
            JOIN documents ON documents.id = chunks.document_id
            WHERE documents.project_id = ?
            ORDER BY documents.id, chunks.id
            """,
            (project_id,),
        ).fetchall()
    return [DocumentChunk(**dict(row)) for row in rows]
