import keyboard
import pyautogui
import time
import re
import traceback
from collections import deque
from openai import OpenAI
import threading
import pyperclip
import pygame
from pathlib import Path
import shutil
import pyttsx3
from queue import Queue
import random
import string

ai_model = None

print("Starting in 3 seconds...")
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")

SHUTDOWN_PASSWORD = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
print(f"Shutdown password: {SHUTDOWN_PASSWORD}")

MAX_TOKENS = 30
MESSAGE_COOLDOWN = 1
CONTEXT_LINES_COUNT = 10

FILE_PATH = r'C:\Users\saved\AppData\Roaming\Mindustry\last_log.txt'
welcome_players = r'C:\Users\saved\PycharmProjects\FishBot\welcome_players.txt'
INSTRUCTIONS_PATH = r'C:\Users\saved\PycharmProjects\FishBot\instructions.txt'
API_KEY_PATH = r'C:\Users\saved\OneDrive\Documents\Python stuff\API_KEY.txt'

tts_thread_running = True
audio_queue = Queue()

with open(API_KEY_PATH, 'r', encoding='utf-8') as file:
    client = OpenAI(api_key=file.read().strip())

pygame.mixer.init()

context_lines = deque(maxlen=CONTEXT_LINES_COUNT)
last_message_time = 0

class CustomAIModel:
    def __init__(self, api_key, instructions_path):
        self.client = OpenAI(api_key=api_key)
        self.model_name = "gpt-4o-mini"
        self.base_instructions = self.load_instructions(instructions_path)

    def load_instructions(self, instructions_path):
        try:
            with open(instructions_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except (FileNotFoundError, Exception):
            return ""

    def get_response(self, question, context=[]):
        messages = [
            {"role": "system", "content": self.base_instructions},
            {"role": "user", "content": question}
        ]

        # Add relevant context if available
        if context:
            context_message = {"role": "system", "content": "\n".join(context)}
            messages.insert(1, context_message)

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error getting response: {e}")
            return ""

def initialize_ai_model():
    global ai_model
    with open(API_KEY_PATH, 'r', encoding='utf-8') as file:
        api_key = file.read().strip()
    ai_model = CustomAIModel(api_key, INSTRUCTIONS_PATH)

def send_instructions():
    if not ai_model.base_instructions:
        print("No instructions loaded.")
        return

    try:
        print("Instructions loaded successfully")
        pygame.mixer.music.set_volume(0.2)
        pygame.mixer.music.load("windows-xp-startup.mp3")
        pygame.mixer.music.play()
    except Exception as e:
        print(f"Error sending instructions: {e}")

def paste_message_from_clipboard():
    keyboard.press_and_release('enter')
    time.sleep(0.2)
    keyboard.press_and_release('ctrl+v')
    time.sleep(0.2)
    keyboard.press_and_release('enter')

def tts_worker():
    while tts_thread_running:
        try:
            text = audio_queue.get()
            if text is None:
                break
            # Clear the queue of any pending messages to avoid backlog
            while not audio_queue.empty():
                audio_queue.get()

            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 1.0)
            voices = engine.getProperty('voices')
            engine.setProperty('voice', voices[1].id)

            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"Error in TTS worker: {e}")
        finally:
            try:
                engine.stop()
            except:
                pass

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

def generate_and_play_audio(text):
    try:
        clean_text = re.sub(r'\[[^\]]+\]', '', text)
        while not audio_queue.empty():
            audio_queue.get()
        audio_queue.put(clean_text)
    except Exception as e:
        print(f"Error in TTS: {e}")

def shutdown_tts():
    global tts_thread_running
    tts_thread_running = False
    while not audio_queue.empty():
        audio_queue.get()
    audio_queue.put(None)
    tts_thread.join(timeout=2)

def send_message_to_chatgpt(question, context):
    print(f"Q: {question}")

    assistant_response = ai_model.get_response(question, context)

    if assistant_response.lower().startswith("fishbot:"):
        assistant_response = assistant_response[len("fishbot:"):].strip()

    use_color_tags = True #safe mode toggle #cb28fc
    assistant_response = f"{'[white]' if use_color_tags else ''}{assistant_response}"
    print("R:", assistant_response)

    threading.Thread(
        target=generate_and_play_audio,
        args=(assistant_response,),
        daemon=True
    ).start()

    send_message_with_cooldown(assistant_response)

def send_message_with_cooldown(message):
    global last_message_time
    current_time = time.time()

    time_since_last_message = current_time - last_message_time
    if time_since_last_message < MESSAGE_COOLDOWN:
        wait_time = MESSAGE_COOLDOWN - time_since_last_message
        print(f"Cooldown: Waiting {wait_time:.2f}s")
        time.sleep(wait_time)

    pyperclip.copy(message)
    paste_message_from_clipboard()
    last_message_time = time.time()

def clean_chat_log(line):
    return line.replace("[I] [Chat] ", "").strip()

def handle_chat_message(line, cleaned_line):
    global running
    if 'hey fishbot off' in cleaned_line.lower():
        print(f"Shutdown Password: {SHUTDOWN_PASSWORD}")
    elif SHUTDOWN_PASSWORD in line:
        time.sleep(1)
        send_message_with_cooldown("[#f]Shutting off")
        shutdown_tts()
        running = False

def detect_fishbot_questions(file_path):
    global running
    running = True
    fishbot_pattern = re.compile(r'\bhey fishbot\b', re.IGNORECASE)
    connected_pattern = re.compile(r'has connected', re.IGNORECASE)
    received_world_data_pattern = re.compile(r'Received world data', re.IGNORECASE)

    with open(file_path, 'r', encoding='utf-8') as file:
        file.seek(0, 2)

        while running:
            line = file.readline()
            if not line:
                time.sleep(0.1)
                continue

            if '[Chat]' in line:
                cleaned_line = clean_chat_log(line.strip())
                context_lines.append(cleaned_line)

                handle_chat_message(line, cleaned_line)

                if (
                    fishbot_pattern.search(line)
                    and 'hey fishbot shutdown' not in cleaned_line.lower()
                    and SHUTDOWN_PASSWORD not in cleaned_line
                ):
                    send_message_to_chatgpt(cleaned_line, list(context_lines))
                elif connected_pattern.search(line):
                    for welcome_player in load_list_from_file(welcome_players):
                        if welcome_player.lower() in line.lower():
                            welcome_message = f"[gold]Hello, {welcome_player}!"
                            send_message_with_cooldown(welcome_message)
                            break

            elif received_world_data_pattern.search(line):
                print("New game detected.")
                time.sleep(3)
                keyboard.press_and_release('esc')

def load_list_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except (FileNotFoundError, Exception):
        return []

def main():
    try:
        initialize_ai_model()
        send_instructions()
        send_message_with_cooldown("[cyan]FishBot is online.")
        print("Fishbot is online")
        detect_fishbot_questions(FILE_PATH)
    except KeyboardInterrupt:
        print("Script stopped by user.")

if __name__ == "__main__":
    main()