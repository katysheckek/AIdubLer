import os
import sys
import json
import time
import re

from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()  # ищет .env в текущей директории и поднимается вверх по дереву

# ================= НАСТРОЙКИ =================
API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    raise ValueError("Установите OPENROUTER_API_KEY")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

# Можно переопределить переменной окружения.
# Список моделей и бесплатные варианты могут меняться.
MODELS = [
    # "nvidia/nemotron-3-ultra-550b-a55b:free",
    # "baidu/ernie-5.5-flash-preview:free",
    # "dots-studio/dots-3-note-preview:free",
     "cohere/north-mini-code:free"
    # "openrouter/free",
]
# Модель-судья (должна быть стабильной; можно использовать ту же, что и кандидат, но лучше отдельную)
JUDGE_MODEL = "openrouter/free"
TOP_K = 4
PREVIEW_CHARS = 90  # сколько символов фрагмента показывать в консоли

# Ретривер создаётся в main(). Если он не поднялся — тесты НЕ запускаются.
_retriever = None


# ================= СТРУКТУРА =================
@dataclass
class TestCase:
    id: str
    type: str  # simple / complex / incomplete / wrong / out_of_scope / russian / grading
    question: str
    expected: str         # эталонный ответ / комментарий преподавателя (только для оценки, модели НЕ показывается)
    keywords: List[str] = field(default_factory=list)            # ключевые слова, которые должны быть в ОТВЕТЕ модели
    retrieval_keywords: List[str] = field(default_factory=list)  # что должно найтись в ТЕКСТЕ, который вернул ретривер
    student_answer: Optional[str] = None   # для wrong / incomplete / grading
    teacher_grade: Optional[int] = None    # для grading (1-5)
    teacher_comment: Optional[str] = None  # для grading


# ================= ТЕСТ-КЕЙСЫ =================
# Контекст для модели больше не хранится в тестах: он берётся только из ретривера.
# retrieval_keywords — это лишь проверка, нашёл ли ретривер нужное место в документах.
# Подправь их под реальный текст твоих файлов, если формулировки отличаются.

TEST_CASES: List[TestCase] = [
    # ---------- SIMPLE ----------
    TestCase("s1", "simple", "Что такое атом?",
             "Мельчайшая частица химического элемента, состоящая из ядра и электронов.",
             keywords=["ядр", "электрон"],
             retrieval_keywords=["ядр", "электрон"]),
    TestCase("s2", "simple", "Что такое молекула?",
             "Мельчайшая частица вещества, имеющая все его основные химические свойства.",
             keywords=["частица", "свойств"],
             retrieval_keywords=["молекул", "свойств"]),

    # ---------- COMPLEX ----------
    TestCase("c1", "complex", "В чём разница между простым и сложным веществом? Приведи примеры.",
             "Простые — атомы одного элемента (H2, O2); сложные — атомы разных элементов (H2O, HCl).",
             keywords=["одного", "разных"],
             retrieval_keywords=["простые", "сложные"]),
    TestCase("c2", "complex", "Почему кислород O2 и озон O3 — аллотропные модификации?",
             "Это простые вещества одного элемента (кислорода), но с разным числом атомов в молекуле.",
             keywords=["одного элемента", "число атомов"],
             retrieval_keywords=["аллотроп"]),

    # ---------- INCOMPLETE ----------
    TestCase("i1", "incomplete", "Что такое атом?",
             "Ответ неполный — нужно уточнить, что атом состоит из ядра и электронов, и что это частица химического элемента.",
             student_answer="Атом — это маленькая частица.",
             keywords=["ядр", "электрон"],
             retrieval_keywords=["ядр", "электрон"]),
    TestCase("i2", "incomplete", "Что такое аллотропия?",
             "Ответ неполный — нужно уточнить, что это способность атомов ОДНОГО элемента образовывать НЕСКОЛЬКО простых веществ.",
             student_answer="Аллотропия — это разные вещества.",
             keywords=["одного элемента", "несколько"],
             retrieval_keywords=["аллотроп"]),

    # ---------- WRONG ----------
    TestCase("w1", "wrong", "Что такое молекула?",
             "Молекула — мельчайшая частица ВЕЩЕСТВА, обладающая его химическими свойствами (не элемента!).",
             student_answer="Молекула — это мельчайшая частица химического элемента.",
             keywords=["веществ", "свойств"],
             retrieval_keywords=["молекул", "свойств"]),
    TestCase("w2", "wrong", "В чём измеряется молярная масса?",
             "Молярная масса измеряется в г/моль (кг/моль), а не в молях.",
             student_answer="Молярная масса измеряется в молях.",
             keywords=["г/моль"],
             retrieval_keywords=["молярн"]),

    # ---------- OUT OF SCOPE ----------
    # retrieval_keywords пустые: от ретривера ничего конкретного не ждём,
    # модель должна честно сказать, что в найденных фрагментах ответа нет.
    TestCase("o1", "out_of_scope", "Как получить кислород в лаборатории?",
             "В материале нет способов лабораторного получения кислорода.",
             keywords=["нет", "отсутств", "не содержит"]),
    TestCase("o2", "out_of_scope", "Сколько стоит килограмм золота?",
             "В материале нет экономической информации о стоимости металлов.",
             keywords=["нет", "отсутств", "не содержит"]),

    # ---------- RUSSIAN ----------
    TestCase("r1", "russian", "Объясни закон Авогадро так, чтобы понял школьник.",
             "В равных объёмах газов при одинаковых условиях — одинаковое число молекул; следствие: 1 моль газа = 22,4 л при н.у.",
             keywords=["объём", "молекул", "22,4"],
             retrieval_keywords=["22,4"]),
    TestCase("r2", "russian", "Что такое аллотропия? Объясни на примере углерода.",
             "Аллотропия — разные простые вещества из одного элемента. Углерод: графит и алмаз — разные кристаллические формы.",
             keywords=["графит", "алмаз", "кристалл"],
             retrieval_keywords=["аллотроп", "графит"]),

    # ---------- GRADING ----------
    # Модель должна ОЦЕНИТЬ ответ студента и совпасть с оценкой преподавателя (±1)
    TestCase("g1", "grading", "Что такое молекула?",
             "Оценка преподавателя: 3 (неполно — не указаны химические свойства).",
             student_answer="Молекула — это частица вещества.",
             retrieval_keywords=["молекул"],
             teacher_grade=3, teacher_comment="Верно, но неполно: не указано, что молекула обладает химическими свойствами."),
    TestCase("g2", "grading", "Что такое аллотропия?",
             "Оценка преподавателя: 5 (точный ответ с сутью явления).",
             student_answer="Аллотропия — способность атомов одного элемента образовывать несколько простых веществ.",
             retrieval_keywords=["аллотроп"],
             teacher_grade=5, teacher_comment="Точный ответ."),
]


# ================= РЕТРИВЕР =================
def init_retriever():
    """
    Поднимает реальный Retriever. Никаких запасных вариантов:
    если не получилось — печатаем причину и завершаем программу.
    """
    try:
        from src.ai.fragmentation.retriever import Retriever
        retriever = Retriever()
    except Exception as e:
        sys.exit(
            f"ОШИБКА: ретривер не запустился ({type(e).__name__}: {e}).\n"
            "Проверь: запуск из корня проекта (чтобы работал import src...), "
            "наличие индекса (DB_DIR) и коллекции (COLLECTION_NAME) — "
            "возможно, индексатор ещё не запускали."
        )

    count = retriever.collection.count()
    if count == 0:
        sys.exit(
            "ОШИБКА: индекс пуст — в коллекции 0 фрагментов. "
            "Сначала проиндексируй документы (indexer), потом запускай тесты."
        )
    return retriever


def print_index_report(retriever) -> None:
    """Показывает, какие файлы реально лежат в индексе и сколько фрагментов из каждого."""
    data = retriever.collection.get(include=["metadatas"])
    metadatas = data.get("metadatas") or []
    by_source = Counter((m or {}).get("source", "<без source>") for m in metadatas)

    print(f"\n📚 Индекс: {len(metadatas)} фрагментов из {len(by_source)} файл(ов)")
    for source, n in sorted(by_source.items()):
        print(f"   📄 {source}: {n} фрагм.")
    print()


def get_rag_context(question: str, top_k: int = TOP_K) -> Tuple[str, list, list]:
    """
    Возвращает (context_str, sources, chunks) — только из реального ретривера.
    Любая ошибка ретривера пробрасывается наверх, подмены текстом нет.
    context_str форматируется как [S1], [S2]...
    """
    chunks = _retriever.search(question, top_k=top_k)
    if not chunks:
        return "", [], []

    parts, sources = [], []
    for i, chunk in enumerate(chunks, 1):
        sid = f"S{i}"
        parts.append(
            f"[{sid}]\n"
            f"Документ: {chunk['source']}\n"
            f"Расположение: {chunk['location']}\n"
            f"Текст: {chunk['text']}"
        )
        sources.append({
            "id": sid,
            "source": chunk["source"],
            "location": chunk["location"],
            "distance": chunk["distance"],
        })
    return "\n\n".join(parts), sources, chunks


def print_retrieved(chunks: list) -> None:
    """Выводит, какие фрагменты каких файлов ретривер реально достал для вопроса."""
    for i, c in enumerate(chunks, 1):
        preview = c["text"].replace("\n", " ").strip()
        if len(preview) > PREVIEW_CHARS:
            preview = preview[:PREVIEW_CHARS] + "…"
        print(f"      📎 S{i} | {c['source']} | {c['location']} | dist={c['distance']:.3f}")
        print(f"         «{preview}»")


# ================= ПРОМПТЫ =================
def build_prompt(tc: TestCase, context: str) -> Tuple[str, str]:
    if tc.type == "grading":
        system = (
            "Ты — AI-тьютор по химии. Оцени ответ студента по 5-балльной шкале, "
            "опираясь ТОЛЬКО на предоставленный материал. "
            "Верни строго: 'Оценка: X' (X — 1..5), затем 1-2 предложения комментария."
        )
        user = f"МАТЕРИАЛ:\n{context}\n\nВОПРОС: {tc.question}\nОТВЕТ СТУДЕНТА: {tc.student_answer}\n\nОцени от 1 до 5."
        return system, user

    system = (
        "Ты — AI-тьютор по химии. Отвечай, ОПИРАЯСЬ ТОЛЬКО на предоставленный фрагмент "
        "учебного материала. Если информации в материале нет — честно скажи, не придумывай. "
        "Ссылайся на источники в формате [S1], [S2], если используешь их. "
        "Отвечай на русском, понятно и по существу."
    )
    user = f"МАТЕРИАЛ:\n{context}\n\nВОПРОС: {tc.question}"
    if tc.type == "incomplete":
        user += f"\n\nСтудент дал неполный ответ: \"{tc.student_answer}\". Задай уточняющий вопрос."
    elif tc.type == "wrong":
        user += f"\n\nСтудент ответил: \"{tc.student_answer}\". Найди КОНКРЕТНУЮ ошибку и объясни."
    return system, user


# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def call_model(model_id: str, messages: List[dict], temperature: float = 0.2) -> str:
    try:
        r = client.chat.completions.create(
            model=model_id, messages=messages, temperature=temperature, max_tokens=1024
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        return f"[ОШИБКА: {e}]"

def check_keywords(answer: str, keywords: List[str]) -> Tuple[bool, List[str], List[str]]:
    """Возвращает (все_найдены, найденные, отсутствующие). Регистронезависимо."""
    if not keywords:
        return True, [], []
    a = answer.lower().replace("ё", "е")
    found, missing = [], []
    for kw in keywords:
        if kw.lower().replace("ё", "е") in a:
            found.append(kw)
        else:
            missing.append(kw)
    return len(missing) == 0, found, missing

def extract_grade(text: str) -> Optional[int]:
    """Извлекает оценку 1-5 из ответа модели-тьютора."""
    patterns = [
        r'оценк[аи]?\s*[:\-—]?\s*([1-5])',
        r'([1-5])\s*(?:из|/)\s*5',
        r'\b([1-5])\s*балл',
    ]
    for p in patterns:
        m = re.search(p, text.lower())
        if m:
            return int(m.group(1))
    # fallback: первая цифра 1-5
    m = re.search(r'\b([1-5])\b', text)
    return int(m.group(1)) if m else None


def get_judge_prompt(tc: TestCase, model_answer: str) -> Tuple[str, str]:
    judge_system = (
        "Ты — строгий преподаватель химии. Оцени ответ AI-тьютора по рубрике. "
        "Верни ТОЛЬКО одно число от 1 до 5."
    )
    if tc.type == "grading":
        return judge_system, "N/A (считается детерминированно в коде)"

    if tc.type in ("simple", "complex"):
        rubric = "5 — факт верен и соответствует материалу.\n3 — в целом верен, но с неточностями.\n1 — неверен или выдуман."
    elif tc.type == "incomplete":
        rubric = "5 — задан релевантный уточняющий вопрос.\n3 — дан правильный ответ, но БЕЗ уточняющего вопроса.\n1 — согласился с неполным ответом."
    elif tc.type == "wrong":
        rubric = "5 — указана КОНКРЕТНАЯ ошибка студента и дана правильная информация.\n3 — дан правильный ответ, но без явного указания на ошибку.\n1 — согласился с ошибкой."
    elif tc.type == "out_of_scope":
        rubric = (
            "5 — модель честно сказала, что в материале НЕТ этой информации.\n"
            "3 — частичный ответ с оговоркой, что в материале этого нет.\n"
            "1 — модель выдумала конкретный факт, которого нет в материале "
            "(даже если факт верен в реальности — для RAG это галлюцинация)."
        )
    elif tc.type == "russian":
        rubric = "5 — естественное, понятное объяснение на хорошем русском.\n3 — верно, но сухо/тяжело.\n1 — непонятно или с ошибками."
    else:
        rubric = "5 — отлично.\n1 — плохо."

    missing_kw = ""
    if tc.keywords:
        _, _, missing = check_keywords(model_answer, tc.keywords)
        if missing:
            missing_kw = f"\nВНИМАНИЕ: в ответе нет ключевых слов: {missing}. Снизь оценку."

    judge_user = (
        f"Вопрос: {tc.question}\n"
        f"Эталон: {tc.expected}\n"
        f"Ответ AI: {model_answer}\n"
        f"{missing_kw}\n{rubric}\nОдно число 1-5."
    )
    return judge_system, judge_user


# ================= ЗАПУСК =================
def run_evaluation():
    results = {}
    total = len(TEST_CASES)

    for model_id in MODELS:
        print(f"\n{'='*70}\n🔬 {model_id}\n{'='*70}")
        results[model_id] = []
        scores, retrieval_hits, pipeline_oks = [], [], []

        for i, tc in enumerate(TEST_CASES, 1):
            print(f"  [{i}/{total}] {tc.id} ({tc.type}): {tc.question[:45]}...")

            # 1. RAG: контекст ТОЛЬКО из реального ретривера
            retrieval_error = None
            try:
                ctx, sources, chunks = get_rag_context(tc.question, top_k=TOP_K)
                if not ctx:
                    retrieval_error = "ретривер вернул 0 фрагментов"
            except Exception as e:
                ctx, sources, chunks = "", [], []
                retrieval_error = f"{type(e).__name__}: {e}"

            # 2. Ретривер не сработал → ошибку показываем, модель НЕ вызываем, подстановок нет
            if retrieval_error:
                print(f"      ❌ ОШИБКА РЕТРИВЕРА: {retrieval_error} — тест пропущен (score=0)")
                scores.append(0)
                retrieval_hits.append(False)
                pipeline_oks.append(False)
                results[model_id].append({
                    "test_id": tc.id, "type": tc.type,
                    "question": tc.question,
                    "retrieved": [],
                    "sources": [],
                    "retrieval_error": retrieval_error,
                    "retrieval_hit": False,
                    "retrieval_missing": tc.retrieval_keywords,
                    "model_answer": None,
                    "answer_score": 0,
                    "pipeline_ok": False,
                    "judge_raw": "тест не выполнен: ошибка ретривера",
                })
                continue

            # 3. Показываем, какие файлы/фрагменты реально прочитаны
            print_retrieved(chunks)

            # 4. Диагностика ретривера: нашлось ли нужное в тексте, который он вернул
            if tc.retrieval_keywords:
                retrieval_hit, _, rkw_missing = check_keywords(ctx, tc.retrieval_keywords)
            else:
                retrieval_hit, rkw_missing = True, []  # out_of_scope: не ожидаем ничего

            # 5. Запрос к модели
            system, user = build_prompt(tc, ctx)
            answer = call_model(model_id, [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            time.sleep(1.2)

            # 6. Оценка
            if tc.type == "grading":
                ai_grade = extract_grade(answer)
                if ai_grade is None:
                    score = 1
                    judge_raw = "AI не вернула оценку в формате 'Оценка: X'"
                else:
                    diff = abs(ai_grade - tc.teacher_grade)
                    score = 5 if diff == 0 else (3 if diff == 1 else 1)
                    judge_raw = f"AI={ai_grade}, teacher={tc.teacher_grade}, diff={diff}"
            else:
                js, ju = get_judge_prompt(tc, answer)
                judge_raw = call_model(JUDGE_MODEL, [
                    {"role": "system", "content": js},
                    {"role": "user", "content": ju},
                ], temperature=0.0)
                m = re.search(r'[1-5]', judge_raw)
                score = int(m.group()) if m else 0
                # Штраф за отсутствие ключевых слов в ответе
                if tc.keywords:
                    ok, _, _ = check_keywords(answer, tc.keywords)
                    if not ok:
                        score = min(score, 2)
                time.sleep(1.2)

            pipeline_ok = retrieval_hit and score >= 4
            scores.append(score)
            retrieval_hits.append(retrieval_hit)
            pipeline_oks.append(pipeline_ok)

            # Логирование
            rh = "✅" if retrieval_hit else "❌"
            print(f"      {rh} retrieval | score={score} | pipeline_ok={pipeline_ok}")

            results[model_id].append({
                "test_id": tc.id, "type": tc.type,
                "question": tc.question,
                "retrieved": [
                    {"id": s["id"], "source": c["source"], "location": c["location"],
                     "distance": c["distance"], "text": c["text"]}
                    for s, c in zip(sources, chunks)
                ],
                "sources": sources,
                "retrieval_error": None,
                "retrieval_hit": retrieval_hit,
                "retrieval_missing": rkw_missing,
                "model_answer": answer,
                "answer_score": score,
                "pipeline_ok": pipeline_ok,
                "judge_raw": judge_raw,
            })

        # Итоги по модели
        avg = sum(scores) / len(scores)
        rh_rate = sum(retrieval_hits) / len(retrieval_hits)
        po_rate = sum(pipeline_oks) / len(pipeline_oks)
        print(f"\n  answer_score: {avg:.2f}/5  |  retrieval_hit: {rh_rate*100:.1f}%  |  pipeline_ok: {po_rate*100:.1f}%")
        for t in ["simple", "complex", "incomplete", "wrong", "out_of_scope", "russian", "grading"]:
            ts = [r for r in results[model_id] if r["type"] == t]
            if ts:
                t_avg = sum(r["answer_score"] for r in ts) / len(ts)
                t_rh = sum(r["retrieval_hit"] for r in ts) / len(ts)
                print(f"     - {t:14}: score={t_avg:.2f}  retrieval={t_rh*100:.0f}%  (n={len(ts)})")

    # Финальный отчёт
    print(f"\n{'='*70}\nИТОГ\n{'='*70}")
    rows = []
    for m, rs in results.items():
        rows.append({
            "model": m,
            "avg_score": sum(r["answer_score"] for r in rs) / len(rs),
            "retrieval_hit": sum(r["retrieval_hit"] for r in rs) / len(rs),
            "pipeline_ok": sum(r["pipeline_ok"] for r in rs) / len(rs),
        })
    rows.sort(key=lambda x: -x["pipeline_ok"])
    print(f"{'Модель':45} {'score':>6} {'retrieval':>10} {'pipeline':>10}")
    for r in rows:
        print(f"{r['model']:45} {r['avg_score']:>6.2f} {r['retrieval_hit']*100:>9.0f}% {r['pipeline_ok']*100:>9.0f}%")

    with open("rag_chem_eval_v2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nrag_chem_eval_v2.json")


def main():
    global _retriever
    _retriever = init_retriever()   # при ошибке программа завершится с сообщением
    print("✅ Retriever инициализирован")
    print_index_report(_retriever)  # видно, какие файлы прочитаны и сколько в них фрагментов

    print(f"Тестов: {len(TEST_CASES)} | Моделей: {len(MODELS)} | TOP_K: {TOP_K}")
    print("Лимит OpenRouter: 20 RPM, 50 запросов/день без пополнения на $10.")
    run_evaluation()


if __name__ == "__main__":
    main()