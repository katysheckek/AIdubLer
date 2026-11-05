import ollama
import pyttsx3

# Запрос к Ollama
response = ollama.generate(model='llama3.2', prompt='Подоровайся с пользователем кратко')
text = response['response']
print(f"Ollama: {text}")

# Озвучка
engine = pyttsx3.init()
engine.say(text)
engine.runAndWait()