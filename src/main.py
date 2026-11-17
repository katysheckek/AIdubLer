from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse

from src.backend.db import init_db
from src.backend.documents import (
    Document,
    UnsupportedFormatError,
    list_documents,
    upload_document,
)
from src.backend.projects import ProjectNotFoundError, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def create_app(
    db_path: str | Path = PROJECT_ROOT / "data" / "aidubler.db",
    storage_dir: str | Path = PROJECT_ROOT / "data" / "uploads",
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(db_path)
        yield

    app = FastAPI(title="AIdubLer", lifespan=lifespan)

    @app.exception_handler(ProjectNotFoundError)
    async def missing_project(request: Request, error: ProjectNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(UnsupportedFormatError)
    async def unsupported_format(request: Request, error: UnsupportedFormatError):
        return JSONResponse(status_code=415, content={"detail": str(error)})

    @app.exception_handler(ValidationError)
    async def invalid_document(request: Request, error: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.post("/projects/{project_id}/documents", status_code=201)
    def upload(project_id: int, file: Annotated[UploadFile, File()]) -> Document:
        return upload_document(
            db_path, storage_dir, project_id, file.filename or "", file.file
        )

    @app.get("/projects/{project_id}/documents")
    def documents(project_id: int) -> list[Document]:
        return list_documents(db_path, project_id)

    return app


app = create_app()
