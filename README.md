# AIdubLer

Учебные проекты и подготовка материалов для ИИ-тьютора. Backend использует
FastAPI, файлы на диске и SQLite из стандартной библиотеки Python.

## Запуск и загрузка материалов (#8, #9)

Команды выполняются из корня репозитория в существующем Python-окружении.
Нужен Python 3.12 или новее. Зависимости перечислены в `pyproject.toml` и
зафиксированы в `uv.lock`, включая PyMuPDF, python-docx и python-pptx для
загрузчиков. SQLite поставляется вместе с Python. Для установки зависимостей
в окружение проекта без скачивания нового Python:
`uv sync --locked --no-python-downloads`. При использовании uv запускайте команды ниже через
`uv run --no-sync python` вместо `python`.

Создайте учебный проект (ID выводится в терминал) и запустите API:

```bash
python - <<'PY'
from src.backend.db import init_db
from src.backend.projects import create_project
init_db('data/aidubler.db')
print(create_project('data/aidubler.db', name='Химия').id)
PY
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

В другом терминале укажите полученный ID:

```bash
project_id=1
curl -i -F 'file=@materials/Химия. Вещество.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl "http://127.0.0.1:8000/projects/$project_id/documents"
curl "http://127.0.0.1:8000/projects/$project_id/chunks"
```

Успешная загрузка возвращает `201` и метаданные документа. Допустимы `.pdf`,
`.docx`, `.pptx` без учёта регистра. Исходное имя хранится в `original_filename`,
а файл — под уникальным именем в `data/uploads/<project_id>/`. Документ связан
с проектом через `documents.project_id` в `data/aidubler.db`. Одноимённые файлы
не перезаписывают друг друга. Рабочие данные исключены из Git.

Неизвестный проект возвращает `404`, неподдерживаемый формат — `415`,
файл без имени или содержимого, документ без текста и повреждённый файл —
`400`. Текст ошибки находится в `detail`.
Интерактивное описание API: <http://127.0.0.1:8000/docs>.

## Как сохраняются фрагменты

1. API проверяет существование проекта и расширение файла.
2. Файл записывается под уникальным именем в папку проекта.
3. `load_document` из `src/ai/fragmentation` извлекает текст по страницам PDF,
   слайдам PPTX или всему DOCX. Исходное имя возвращается в поле `source`.
4. `chunk_documents` разбивает текст на фрагменты, сохраняя `location`.
5. Документ и все его фрагменты записываются одной транзакцией SQLite.
   Если обработка или запись завершается ошибкой, файл удаляется.

Таблица `document_chunks` хранит `text`, `document_id`, `source`, `location`,
`page_number` и `chunk_index`. Страницы PDF нумеруются с 1; у DOCX и PPTX
`page_number` равен `null`, а `location` содержит `document` или `slide:N`.
`chunk_index` начинается с 0 внутри каждой страницы/слайда/документа.
Выборка `GET /projects/{project_id}/chunks` использует связь
`document_chunks.document_id → documents.project_id` и возвращает фрагменты
только указанного проекта. То же доступно из Python через
`src.backend.documents.list_project_chunks`.

PDF, для открытия которого PyMuPDF применяет восстановление, и PDF с паролем
отклоняются. Скан без извлекаемого текста требует OCR; OCR пока не реализован.

Порядок ручной проверки и фактические результаты: [docs/manual-document-check.md](docs/manual-document-check.md).
