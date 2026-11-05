import asyncio
import subprocess

import edge_tts
import ollama
import os

# Сначала получаем текст от вашей локальной модели llama3.1
print("Генерация ответа от LLM...")
response = ollama.generate(model='llama3.2', prompt='Поздоровайся с пользователем на русском языке')
text = response['response']
print(f"Ollama: {text}")


# Функция для озвучки через Microsoft Edge (Голос Дмитрий)
async def speak(text_to_speak):
    voice = "ru-RU-DmitryNeural"  # Для женского голоса используйте "ru-RU-SvetlanaNeural"
    output_file = "output.mp3"

    communicate = edge_tts.Communicate(text_to_speak, voice)
    await communicate.save(output_file)

    # Воспроизводим созданный файл в системе
    # os.system(f"start {output_file}")  # Команда для Windows
    subprocess.run(["start", "", output_file], shell=True)

# Запуск асинхронного кода
if __name__ == "__main__":
    asyncio.run(speak(text))

async def speak_with_retry(text, retries=3):
    for i in range(retries):
        try:
            await speak(text)
            if os.path.getsize("output.mp3") > 0:
                return
        except Exception as e:
            print(f"Попытка {i+1} не удалась: {e}")
            await asyncio.sleep(2)
    print("Все попытки не удались")