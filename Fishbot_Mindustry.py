import keyboard
import pyautogui
import time
import re
import traceback
from collections import deque
from openai import OpenAI
import threading
import pyperclip

print("Starting in 3 seconds...")
time.sleep(1)
print("2...")
time.sleep(1)
print("1...")

# Define constants
MAX_TOKENS = 30
MESSAGE_COOLDOWN = 1
QUESTION_COOLDOWN = 20
RECENT_LINES_COUNT = 3
CONTEXT_LINES_COUNT = 10

# File paths
FILE_PATH = r'C:\Users\saved\AppData\Roaming\Mindustry\last_log.txt'
welcome_players = r'C:\Users\saved\PycharmProjects\Private-Bananabot\welcome_players'
INSTRUCTIONS_PATH = r'C:\Users\saved\PycharmProjects\Private-Bananabot\instructions.txt'
API_KEY_PATH = r'C:\Users\saved\OneDrive\Documents\Python stuff\API_KEY.txt'

with open(API_KEY_PATH, 'r', encoding='utf-8') as file:
    api_key = file.read().strip()

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Initialize global variables
recent_lines = deque(maxlen=RECENT_LINES_COUNT)
context_lines = deque(maxlen=CONTEXT_LINES_COUNT)
last_question = ""
last_question_time = 0
last_message_time = 0

# List of valid mining resources
valid_resources = ["copper", "lead", "beryllium", "sand", "coal", "graphite", "scrap", "titanium"]

# Load instructions
def load_instructions(path):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

instructions = load_instructions(INSTRUCTIONS_PATH)

# Function to send instructions to ChatGPT
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

# Function to generate and send a personalized message
def paste_message_from_clipboard():
    """Paste the message from the clipboard into the chat."""
    keyboard.press_and_release('enter')
    time.sleep(0.2)
    keyboard.press_and_release('ctrl+v')
    time.sleep(0.2)
    keyboard.press_and_release('enter')

def send_message_to_chatgpt(question, context):
    # Filter context lines to include only relevant information
    filtered_context = [line for line in context if "relevant" in line.lower()]  # Adjust filter criteria as needed

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

            # Copy the response to the clipboard
            pyperclip.copy(assistant_response)

            # Ensure the message fits within the token limit
            if len(assistant_response.split()) <= MAX_TOKENS:
                print("R:", assistant_response)

                # Use the new function to paste the message
                paste_message_from_clipboard()
                break
        except Exception as e:
            print(f"Error sending message: {e}")

# Function to send a message
send_message_lock = threading.Lock()
def send_message(message):
    global last_message_time
    current_time = time.time()

    with send_message_lock:
        # Check if the cooldown period has passed
        time_since_last_message = current_time - last_message_time
        if time_since_last_message < MESSAGE_COOLDOWN:
            wait_time = MESSAGE_COOLDOWN - time_since_last_message
            print(f"Cooldown in effect. Waiting for {wait_time:.2f} seconds...")
            time.sleep(wait_time)
            current_time = time.time()  # Update current_time after waiting

        # Send the message
        try:
            # Copy the message to the clipboard and paste it using the new function
            pyperclip.copy(message)
            paste_message_from_clipboard()
            print(f"Message sent: {message}")
        except Exception as e:
            print(f"Error sending message: {e}")

        # Update the last message time
        last_message_time = current_time
        print(f"Updated last_message_time to {last_message_time}")

def send_start_message():
    send_message("[cyan]FishBot is online.")
    print("Fishbot is online")

# Function to handle the response to a question
def handle_miner_question(question_text):
    global last_question, last_question_time

    current_time = time.time()
    if question_text == last_question and current_time - last_question_time < QUESTION_COOLDOWN:
        return

    last_question = question_text
    last_question_time = current_time

    print(f"Q: {question_text}")

    # Handle different commands or questions
    if re.search(r'\bhey fishbot mine\b', question_text, re.IGNORECASE):
        # Example command handling
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

    # Send personalized message using the clipboard
    send_message_to_chatgpt(question_text, list(context_lines))

# Function to load a list of players from a file
def load_list_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

def clean_chat_log(line):
    return line.replace("[I] [Chat] ", "").strip()

# Function to detect questions and new player connections in the log file
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

# Main function
def main():
    try:
        send_start_message()
        send_instructions()  # Send instructions only once at the start

        # Start monitoring the log file
        detect_fishbot_questions(FILE_PATH)
    except KeyboardInterrupt:
        print("Script stopped by user.")

if __name__ == "__main__":
    main()