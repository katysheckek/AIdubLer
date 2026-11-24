# Ручная проверка загрузки и обработки документов

По решению команды для #8 и #9 выполнена только ручная проверка через
запущенный Uvicorn, curl, просмотр файлов и SQL-запросы из Python.
Автотесты для этих задач не добавлялись и не запускались.

## Окружение и фактический результат

Проверено 18 ноября 2026 года (Asia/Novosibirsk) в существующем окружении:
Python 3.12.14, SQLite 3.53.1, FastAPI 0.141.1, Uvicorn 0.52.1,
python-multipart 0.0.32, PyMuPDF 1.26.6, python-docx 1.2.0,
python-pptx 1.0.2. Версии FastAPI и Uvicorn в этом окружении отличаются от
закреплённых в проекте; установка полного окружения из lockfile не выполнялась.
Минимальная версия Python в проекте снижена с 3.14 до 3.12; lockfile
пересчитан штатным `uv lock` без обновления версий прежних зависимостей.

| Действие | Наблюдаемый результат |
| --- | --- |
| Загрузка `materials/Химия. Вещество.pdf` | `201`; файл 231765 байт, исходное имя сохранено; 12 фрагментов со страницами 1–7 |
| Сравнение исходного и сохранённого PDF | Одинаковый SHA256: `0a097b3acbf2c94680209149dc7eb23fde597c50b3ae04f7bcda6a7183918d4b` |
| Сверка каждого PDF-фрагмента со страницей | Текст всех 12 фрагментов найден на странице `page_number` после нормализации пробелов |
| Повторная загрузка одноимённого PDF | Новый `document_id` и отдельный файл; прежний файл сохранён |
| Демо-DOCX | `201`, 10 фрагментов; `location=document`, `page_number=null` |
| Демо-PPTX | `201`, 15 фрагментов; `location=slide:N`, `page_number=null` |
| PDF с именем `UPPER.PDF` во втором проекте | `201`; регистр расширения не мешает загрузке, `source=UPPER.PDF` |
| Выборки фрагментов двух проектов | В каждой выборке только `document_id` своего проекта; у пустого проекта первоначально `[]` |
| Загрузка демо-TXT | `415`, понятная ошибка с перечнем допустимых форматов |
| Несуществующий проект | `404` для загрузки, списка документов и списка фрагментов |
| Некорректные байты с расширением `.pdf` | `400`, ошибка извлечения текста |
| Текстовый файл, переименованный в `.pdf` | `400`, ошибка формата содержимого |
| Повреждённый `startxref` и обрезанный наполовину PDF | `400`, даже если PyMuPDF может восстановить документ |
| Корректный PDF с одной пустой страницей | `400`, сообщение об отсутствии извлекаемого текста и необходимости OCR для сканов |
| Файл `.pdf` нулевого размера | `400`, сообщение «Файл пуст» |
| Просмотр БД и папки после неудачных загрузок | Новых документов, фрагментов и оставшихся файлов нет |
| Повторный `init_db` после #8 и добавления таблицы фрагментов | Ранее созданные проект и документ сохранены |
| `PRAGMA foreign_key_check` | Пустой результат, нарушенных связей нет |
| `uv lock --check --python python --no-python-downloads --cache-dir /workspace/work/uv-cache` | Успешно; lockfile соответствует зависимостям |
| `git diff --check` | Успешно |

## Как повторить

Выполняйте команды из корня репозитория с установленными зависимостями.
Если используется uv, замените `python` на `uv run --no-sync python`.
Для временных материалов используется `work/`; не добавляйте их в коммит.

Создайте проект и запомните выведенный ID:

```bash
python - <<'PY'
from src.backend.db import init_db
from src.backend.projects import create_project
init_db('data/aidubler.db')
print(create_project('data/aidubler.db', name='Ручная проверка: химия').id)
PY
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

В другом терминале подставьте ID и загрузите демо-PDF:

```bash
project_id=1
curl -i -F 'file=@materials/Химия. Вещество.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl "http://127.0.0.1:8000/projects/$project_id/documents"
curl "http://127.0.0.1:8000/projects/$project_id/chunks"
```

Для проверки файлов на диске, текста и страниц подставьте тот же ID в Python:

```bash
python - <<'PY'
import hashlib
from pathlib import Path
import pymupdf
from src.backend.documents import list_documents, list_project_chunks

project_id = 1
for doc in list_documents('data/aidubler.db', project_id):
    original = Path('materials') / doc.original_filename
    stored = Path(doc.storage_path)
    print(doc)
    print('Файл существует:', stored.is_file(), 'байт:', stored.stat().st_size)
    print('SHA256 исходника:', hashlib.sha256(original.read_bytes()).hexdigest())
    print('SHA256 копии:   ', hashlib.sha256(stored.read_bytes()).hexdigest())
    with pymupdf.open(original) as pdf:
        for chunk in list_project_chunks('data/aidubler.db', project_id):
            if chunk.document_id != doc.id:
                continue
            page_text = ' '.join(pdf[chunk.page_number - 1].get_text().split())
            print(chunk.id, chunk.document_id, chunk.source, chunk.location,
                  chunk.page_number, chunk.text in page_text)
            print(chunk.text[:120])
PY
```

Этот пример сверки рассчитан на проект только с демо-PDF. Ожидаются 12
фрагментов для каждой загрузки PDF, страницы 1–7 и `True` для текста каждой
страницы.

Подготовьте неудачные примеры (исходный демо-PDF остаётся без изменений):

```bash
mkdir -p work/manual-documents
python - <<'PY'
from pathlib import Path
import pymupdf

folder = Path('work/manual-documents')
(folder / 'broken.pdf').write_bytes(b'%PDF-1.7\nbroken')
(folder / 'zero.pdf').write_bytes(b'')
(folder / 'renamed.pdf').write_text('Plain text, not a PDF.', encoding='utf-8')
original = Path('materials/Химия. Вещество.pdf').read_bytes()
(folder / 'bad-startxref.pdf').write_bytes(original.replace(b'startxref', b'startxxxx'))
(folder / 'truncated.pdf').write_bytes(original[:len(original)//2])
with pymupdf.open() as pdf:
    pdf.new_page()
    pdf.save(folder / 'blank.pdf')
PY
```

Проверьте ошибки отдельно и сравните количество записей/файлов до и после:

```bash
curl -i -F 'file=@materials/Химия.Вещество.txt' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl -i -F 'file=@work/manual-documents/broken.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl -i -F 'file=@work/manual-documents/blank.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl -i -F 'file=@work/manual-documents/zero.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl -i -F 'file=@work/manual-documents/renamed.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl -i -F 'file=@work/manual-documents/bad-startxref.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl -i -F 'file=@work/manual-documents/truncated.pdf' \
  "http://127.0.0.1:8000/projects/$project_id/documents"
curl -i -F 'file=@materials/Химия. Вещество.pdf' \
  'http://127.0.0.1:8000/projects/999999/documents'
```

Если ID `999999` уже существует, выберите заведомо отсутствующий проект.
После отказов сохранённые файлы и строки должны остаться прежними:

```bash
python - <<'PY'
from pathlib import Path
from src.backend.db import connect_db
with connect_db('data/aidubler.db') as db:
    for table in ['documents', 'document_chunks']:
        print(table, db.execute(f'SELECT count(*) FROM {table}').fetchone()[0])
    print('Нарушения связей:', db.execute('PRAGMA foreign_key_check').fetchall())
print('Файлы:', sorted(str(path) for path in Path('data/uploads').rglob('*') if path.is_file()))
PY
```

Повторная загрузка PDF должна создать отдельный файл. Для DOCX и PPTX можно
повторить загрузку с `materials/Химия.Вещество.docx` и
`materials/Химия.metally.pptx`. Для проверки разделения проектов создайте
второй проект, загрузите в него PDF и сравните `/projects/{id}/chunks`:
наборы `document_id` должны относиться только к своим проектам.
