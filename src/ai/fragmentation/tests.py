

# Тест chunking

from src.ai.fragmentation.chunking import split_text

text = (
    "Фотосинтез — процесс преобразования энергии света. "
    "Хлорофилл поглощает свет. "
    "Растения используют воду и углекислый газ."
)

for i, chunk in enumerate(split_text(text, 70, 10)):
    print(f"\nЧанк {i + 1}: {chunk}")


