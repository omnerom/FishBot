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

print("Starting in 3 seconds...")
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")

MAX_TOKENS = 30
MESSAGE_COOLDOWN = 1
QUESTION_COOLDOWN = 20
RECENT_LINES_COUNT = 3
CONTEXT_LINES_COUNT = 10

FILE_PATH = r'C:\Users\saved\AppData\Roaming\Mindustry\last_log.txt'
welcome_players = r'C:\Users\saved\PycharmProjects\FishBot\welcome_players.txt'
INSTRUCTIONS_PATH = r'C:\Users\saved\PycharmProjects\FishBot\instructions.txt'
API_KEY_PATH = r'C:\Users\saved\OneDrive\Documents\Python stuff\API_KEY.txt'
AUDIO_OUTPUT_DIR = Path("tts_output")

shutil.rmtree(AUDIO_OUTPUT_DIR, ignore_errors=True)
AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)

with open(API_KEY_PATH, 'r', encoding='utf-8') as file:
    api_key = file.read().strip()

client = OpenAI(api_key=api_key)
pygame.mixer.init()

recent_lines = deque(maxlen=RECENT_LINES_COUNT)
context_lines = deque(maxlen=CONTEXT_LINES_COUNT)
last_question = ""
last_question_time = 0
last_message_time = 0

valid_resources = ["copper", "lead", "beryllium", "sand", "coal", "graphite", "scrap", "titanium"]

def load_instructions(path):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

instructions = load_instructions(INSTRUCTIONS_PATH)

def send_instructions():
    """Send the instructions to ChatGPT."""
    if not instructions:
        print("No instructions to send.")
        return

    messages = [{"role": "system", "content": "\n".join(instructions)}]
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=15  # Adjust as necessary
        )
        print(f"Instructions sent: {response}")
    except Exception as e:
        print(f"Error sending instructions: {e}")
    pygame.mixer.music.set_volume(0.2)
    pygame.mixer.music.load("windows-xp-startup.mp3");
    pygame.mixer.music.play()

def paste_message_from_clipboard():
    keyboard.press_and_release('enter')
    time.sleep(0.2)
    keyboard.press_and_release('ctrl+v')
    time.sleep(0.2)
    keyboard.press_and_release('enter')

def generate_and_play_audio(text):
    pygame.mixer.music.set_volume(1)
    try:
        clean_text = re.sub(r'\[[^\]]+\]', '', text)

        response = client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=clean_text
        )

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        audio_path = AUDIO_OUTPUT_DIR / f"response_{timestamp}.mp3"
        response.stream_to_file(str(audio_path))

        sound = pygame.mixer.Sound(str(audio_path))
        sound.play()

    except Exception as e:
        print(f"Error in TTS: {e}")

def send_message_to_chatgpt(question, context):
    filtered_context = [line for line in context if "relevant" in line.lower()]

    messages = [{"role": "user", "content": question}]
    messages.extend({"role": "system", "content": instruction} for instruction in instructions)
    messages.extend({"role": "system", "content": line} for line in filtered_context)

    while True:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=MAX_TOKENS,
                messages=messages
            )
            assistant_response = response.choices[0].message.content.strip()

            if assistant_response.lower().startswith("fishbot:"):
                assistant_response = assistant_response[len("fishbot:"):].strip()

            assistant_response = f"[#cb28fc]{assistant_response}"

            pyperclip.copy(assistant_response)

            if len(assistant_response.split()) <= MAX_TOKENS:
                print("R:", assistant_response)

                # Generate and play TTS in a separate thread
                threading.Thread(
                    target=generate_and_play_audio,
                    args=(assistant_response,),
                    daemon=True
                ).start()

                paste_message_from_clipboard()
                break

        except Exception as e:
            print(f"Error sending message: {e}")

send_message_lock = threading.Lock()
def send_message(message):
    global last_message_time
    current_time = time.time()

    with send_message_lock:
        time_since_last_message = current_time - last_message_time
        if time_since_last_message < MESSAGE_COOLDOWN:
            wait_time = MESSAGE_COOLDOWN - time_since_last_message
            print(f"Cooldown in effect. Waiting for {wait_time:.2f} seconds...")
            time.sleep(wait_time)
            current_time = time.time()

        try:
            pyperclip.copy(message)
            paste_message_from_clipboard()
            print(f"Message sent: {message}")
        except Exception as e:
            print(f"Error sending message: {e}")

        last_message_time = current_time
        print(f"Updated last_message_time to {last_message_time}")

def send_start_message():
    send_message("[cyan]FishBot is online.")
    print("Fishbot is online")

def load_list_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

def handle_miner_question(question_text):
    global last_question, last_question_time

    current_time = time.time()
    if question_text == last_question and current_time - last_question_time < QUESTION_COOLDOWN:
        return

    last_question = question_text
    last_question_time = current_time

    print(f"Q: {question_text}")

    if re.search(r'\bhey fishbot mine\b', question_text, re.IGNORECASE):
        if re.search(r'\bhey fishbot mine (everything|all)\b', question_text, re.IGNORECASE):
            send_message("[gold]Mining everything")
            time.sleep(0.5)
            send_message("!miner * 1000000")
            return

        resources = [resource for resource in valid_resources if resource in question_text.lower()]
        if resources:
            resource_list = ", ".join(resources)
            send_message(f"[gold]Mining {resource_list}")
            time.sleep(0.5)
            send_message(f"!miner {' '.join(resources)} 1000000")
            return

    send_message_to_chatgpt(question_text, list(context_lines))

def clean_chat_log(line):
    return line.replace("[I] [Chat] ", "").strip()

def detect_fishbot_questions(file_path):
    fishbot_pattern = re.compile(r'\bhey fishbot\b', re.IGNORECASE)
    connected_pattern = re.compile(r'has connected', re.IGNORECASE)
    received_world_data_pattern = re.compile(r'Received world data', re.IGNORECASE)

    with open(file_path, 'r', encoding='utf-8') as file:
        file.seek(0, 2)

        while True:
            line = file.readline()
            if not line:
                time.sleep(0.1)
                continue

            recent_lines.append(line.strip())

            if '[Chat]' in line:
                cleaned_line = clean_chat_log(line.strip())
                context_lines.append(cleaned_line)

            if fishbot_pattern.search(line):
                if not any(fishbot_pattern.search(recent_line) for recent_line in recent_lines):
                    print("Q:")

                handle_miner_question(clean_chat_log(line.strip()))

            if connected_pattern.search(line):
                for welcome_player in load_list_from_file(welcome_players):
                    if welcome_player.lower() in line.lower():
                        time.sleep(1)
                        welcome_message = f"[gold]Hello, {welcome_player}!"
                        send_message(welcome_message)
                        break

            if received_world_data_pattern.search(line):
                print("New game detected.")
                time.sleep(3)
                keyboard.press_and_release('esc')

def main():
    try:
        send_start_message()
        send_instructions()

        detect_fishbot_questions(FILE_PATH)
    except KeyboardInterrupt:
        print("Script stopped by user.")

if __name__ == "__main__":
    main()