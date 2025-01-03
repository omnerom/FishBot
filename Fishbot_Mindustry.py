import time
import re
import traceback
import threading
import io
import tempfile
import os
import random
import string
import pygame
from collections import deque
from openai import OpenAI
from pathlib import Path
from queue import Queue
from gtts import gTTS

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

LOG_PATH = r'C:\Users\saved\AppData\Roaming\Mindustry\last_log.txt'
welcome_players = r'C:\Users\saved\PycharmProjects\FishBot\welcome_players.txt'
INSTRUCTIONS_PATH = r'C:\Users\saved\PycharmProjects\FishBot\instructions.txt'
API_KEY_PATH = r'C:\Users\saved\OneDrive\Documents\Python stuff\API_KEY.txt'
RESPONSES_FILE = r'C:\Users\saved\PycharmProjects\FishBot\responses.txt'
WINDOWS_STARTUP = r'C:\Users\saved\PycharmProjects\FishBot\windows-xp-startup.mp3'

tts_thread_running = True
audio_queue = Queue()

with open(API_KEY_PATH, 'r', encoding='utf-8') as file:
    client = OpenAI(api_key=file.read().strip())

context_lines = deque(maxlen=CONTEXT_LINES_COUNT)
last_message_time = 0

pygame.mixer.init()

def clear_responses_file():
    try:
        with open(RESPONSES_FILE, 'w', encoding='utf-8') as file:
            file.write('')
        print("Responses file cleared")
    except Exception as e:
        print(f"Error clearing responses file: {e}")

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

        if context:
            context_message = {"role": "system", "content": "\n".join(context)}
            messages.insert(1, context_message)

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=0.7
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
    print("Instructions loaded successfully")

def send_message_to_chatgpt(question, context):
    assistant_response = ai_model.get_response(question, context)

    if assistant_response.lower().startswith("fishbot:"):
        assistant_response = assistant_response[len("fishbot:"):].strip()

    use_color_tags = True  #safe mode toggle
    assistant_response = f"{'[cyan]' if use_color_tags else ''}{assistant_response}"

    print("R:", assistant_response)

    patterns_to_scrub = ["<> FishBot: ", "<> FishBot: ", "<> FishBot: "]
    cleaned_response = assistant_response
    for pattern in patterns_to_scrub:
        cleaned_response = cleaned_response.replace(pattern, "")
    cleaned_response = cleaned_response.strip()

    try:
        with open(RESPONSES_FILE, 'r+', encoding='utf-8') as file:
            existing_responses = file.read().splitlines()

            if cleaned_response not in existing_responses:
                file.write(cleaned_response + "\n")
    except Exception as e:
        print(f"Error logging response: {e}")

    threading.Thread(
        target=generate_and_play_audio,
        args=(assistant_response,),
        daemon=True
    ).start()

    print_message_with_cooldown(assistant_response)

def log_message_to_file(message):
    try:
        patterns_to_scrub = ["<> FishBot: ", "<> FishBot: ", "<> FishBot: "]
        cleaned_message = message
        for pattern in patterns_to_scrub:
            cleaned_message = cleaned_message.replace(pattern, "")
        cleaned_message = cleaned_message.strip()

        with open(RESPONSES_FILE, 'a', encoding='utf-8') as file:
            file.write(cleaned_message + "\n")
    except Exception as e:
        print(f"Error logging message: {e}")

def print_message_with_cooldown(message):
    global last_message_time
    current_time = time.time()

    time_since_last_message = current_time - last_message_time
    if time_since_last_message < MESSAGE_COOLDOWN:
        wait_time = MESSAGE_COOLDOWN - time_since_last_message
        print(f"Cooldown: Waiting {wait_time:.2f}s")
        time.sleep(wait_time)

    log_message_to_file(message)
    last_message_time = time.time()

def clean_chat_log(line):
    return line.replace("[I] [Chat] ", "").strip()

def handle_chat_message(line, cleaned_line):
    global running
    if 'hey fishbot off' in cleaned_line.lower():
        print(f"Shutdown Password: {SHUTDOWN_PASSWORD}")
        return

    if SHUTDOWN_PASSWORD in line:
        time.sleep(1)
        shutting_off_message = ("[#f]Shutting off")
        print_message_with_cooldown(shutting_off_message)
        send_message_to_chatgpt(shutting_off_message, [])
        shutdown_tts()
        running = False

def detect_fishbot_questions(file_path):
    global running
    running = True
    fishbot_pattern = re.compile(r'^hey fishbot\b', re.IGNORECASE)
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

                parts = line.split(":", 1)
                if len(parts) > 1:
                    message_part = parts[1].strip()

                    if (
                        fishbot_pattern.match(message_part)
                        and 'hey fishbot off' not in message_part.lower()
                        and SHUTDOWN_PASSWORD not in message_part
                    ):
                        question = line.replace("[I] [Chat] ", "").strip()
                        print(f"Q: {question}")
                        send_message_to_chatgpt(message_part, list(context_lines))

                handle_chat_message(line, cleaned_line)

                if connected_pattern.search(line):
                    for welcome_player in load_list_from_file(welcome_players):
                        if welcome_player.lower() in line.lower():
                            welcome_message = f"[gold]Hello, {welcome_player}!"
                            print_message_with_cooldown(welcome_message)
                            break

            elif received_world_data_pattern.search(line):
                print("New game detected.")

def load_list_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except (FileNotFoundError, Exception):
        return []

def startup():
    online_message = ("[cyan] FishBot is online")
    clear_responses_file()
    initialize_ai_model()
    send_instructions()
    pygame.mixer.music.set_volume(0.2)
    pygame.mixer.music.load(WINDOWS_STARTUP)
    pygame.mixer.music.play()
    time.sleep(1)
    print(online_message)
    print_message_with_cooldown(online_message)

def main():
    try:
        startup()
        detect_fishbot_questions(LOG_PATH)
    except KeyboardInterrupt:
        print("Script stopped by user.")

if __name__ == "__main__":
    main()
