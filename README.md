# AIdubLer

Учебные проекты и подготовка материалов для ИИ-тьютора. Backend использует
FastAPI, файлы на диске и SQLite из стандартной библиотеки Python.

## Загрузка материалов (#8)

Команды выполняются из корня репозитория в существующем Python-окружении.
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
```

Успешная загрузка возвращает `201` и метаданные документа. Допустимы `.pdf`,
`.docx`, `.pptx` без учёта регистра. Исходное имя хранится в `original_filename`,
а файл — под уникальным именем в `data/uploads/<project_id>/`. Документ связан
с проектом через `documents.project_id` в `data/aidubler.db`. Одноимённые файлы
не перезаписывают друг друга. Рабочие данные исключены из Git.

Неизвестный проект возвращает `404`, неподдерживаемый формат — `415`,
файл без имени или содержимого — `400`. Текст ошибки находится в `detail`.
Интерактивное описание API: <http://127.0.0.1:8000/docs>.
