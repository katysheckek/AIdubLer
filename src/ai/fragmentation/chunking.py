

#два параметра:
# chunk_size = 1200   максимальная длина фрагмента в символах.
# overlap = 200   число символов, которые повторяются в соседних фрагментах.
#
# Перекрытие помогает сохранить контекст, если важная мысль находится на границе чанков.

# не идеальный чанкер: он может разрезать заголовки и списки,
# а один чанк может содержать несколько предложений.
# Позже можно перейти к разделению по заголовкам, абзацам и токенам.

"""
Проверить его отдельно:
from src.chunking import split_text

text = (
    "Фотосинтез — процесс преобразования энергии света. "
    "Хлорофилл поглощает свет. "
    "Растения используют воду и углекислый газ."
)

for i, chunk in enumerate(split_text(text, 70, 10)):
    print(f"\nЧанк {i + 1}: {chunk}")
"""

def split_text(
           text: str,
     chunk_size: int = 1200,
        overlap: int = 200,
) -> list[str]:
    """Преобразует пользовательский текст в чанки, размером 1200 символов.
    Может содержать часть другого чанка, перекрытие, чтобы лучше сохранить контекст (200 символов)"""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")

    text = " ".join(text.split())
    chunks = []

    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # По возможности не разрываем предложение.
        if end < len(text):
            boundary = text.rfind(". ", start, end)

            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        start = end - overlap

    return chunks


def chunk_documents(
    documents: list[dict],
) -> list[dict]:
    """description"""
    result = []

    for document in documents:
        for index, text in enumerate(
            split_text(document["text"])
        ):
            result.append({
                "text": text,
                "source": document["source"],
                "location": document["location"],
                "chunk_index": index,
            })

    return result
