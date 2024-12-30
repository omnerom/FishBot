import discord
import openai
import asyncio
import threading
import time
import re
from collections import deque
import pyautogui
import pyperclip
import keyboard

# Define constants
MAX_TOKENS = 30
MESSAGE_COOLDOWN = 1.5
QUESTION_COOLDOWN = 20
RECENT_LINES_COUNT = 3
CONTEXT_LINES_COUNT = 10

# File paths
FILE_PATH = r'C:\Users\saved\AppData\Roaming\Mindustry\last_log.txt'
welcome_players = r'C:\Users\saved\PycharmProjects\Private-Bananabot\welcome_players'
INSTRUCTIONS_PATH = r'C:\Users\saved\PycharmProjects\Private-Bananabot\instructions.txt'
API_KEY_PATH = r'C:\Users\saved\OneDrive\Documents\Python stuff\API_KEY.txt'
DISCORD_TOKEN = 'MTI4MDIxNjcyMTcyMTkxNzQ4MA.G7sOHX.rXIkOk5ln59e6x_8YAJkLJyWa2fHlyM1KwoZlA'

# Initialize OpenAI client
with open(API_KEY_PATH, 'r', encoding='utf-8') as file:
    api_key = file.read().strip()

openai.api_key = api_key

# Initialize global variables
recent_lines = deque(maxlen=RECENT_LINES_COUNT)
context_lines = deque(maxlen=CONTEXT_LINES_COUNT)
last_question = ""
last_question_time = 0
last_message_time = 0
send_message_lock = threading.Lock()
discord_channel = None  # Initialize the channel variable

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
async def send_instructions():
    """Send the instructions to ChatGPT."""
    if not instructions:
        print("No instructions to send.")
        return

    messages = [{"role": "system", "content": "\n".join(instructions)}]
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=messages,
            max_tokens=15  # Adjust as necessary
        )
        print(f"Instructions sent: {response}")
    except Exception as e:
        print(f"Error sending instructions: {e}")

# Function to count tokens using tiktoken
def count_tokens(messages):
    tokens = sum(len(encoding.encode(message["content"])) for message in messages)
    return tokens

# Function to generate and send a personalized message
async def send_message_to_chatgpt(question, context):
    # Filter context lines to include only relevant information
    filtered_context = [line for line in context if "relevant" in line.lower()]  # Adjust filter criteria as needed

    messages = [{"role": "user", "content": question}]
    messages.extend({"role": "system", "content": instruction} for instruction in instructions)
    messages.extend({"role": "system", "content": line} for line in filtered_context)

    print(f"T: {count_tokens(messages)}")

    while True:
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=messages,
                max_tokens=MAX_TOKENS
            )
            assistant_response = response.choices[0].message["content"].strip()

            if assistant_response.lower().startswith("fishbot:"):
                assistant_response = assistant_response[len("fishbot:"):].strip()

            assistant_response = f"[#f]{assistant_response}"

            # Copy the response to the clipboard
            pyperclip.copy(assistant_response)

            # Ensure the message fits within the token limit
            if len(assistant_response.split()) <= MAX_TOKENS:
                print("R:", assistant_response)
                print(f"T: {len(encoding.encode(assistant_response))}")

                # Use the new function to paste the message
                await paste_message_from_clipboard()
                break
        except Exception as e:
            print(f"Error sending message: {e}")

# Function to send a message
async def send_message(message):
    global last_message_time
    current_time = time.time()

    with send_message_lock:
        # Check if the cooldown period has passed
        time_since_last_message = current_time - last_message_time
        if time_since_last_message < MESSAGE_COOLDOWN:
            wait_time = MESSAGE_COOLDOWN - time_since_last_message
            print(f"Cooldown in effect. Waiting for {wait_time:.2f} seconds...")
            await asyncio.sleep(wait_time)
            current_time = time.time()  # Update current_time after waiting

        # Send the message
        try:
            # Copy the message to the clipboard and paste it using the new function
            pyperclip.copy(message)
            await paste_message_from_clipboard()
            print(f"Message sent: {message}")
        except Exception as e:
            print(f"Error sending message: {e}")

        # Update the last message time
        last_message_time = current_time
        print(f"Updated last_message_time to {last_message_time}")

async def paste_message_from_clipboard():
    """Paste the message from the clipboard into the chat."""
    keyboard.press_and_release('enter')
    await asyncio.sleep(0.2)
    keyboard.press_and_release('ctrl+v')
    await asyncio.sleep(0.2)
    keyboard.press_and_release('enter')

async def send_start_message():
    # Define start messages for Discord and in-game
    start_message_discord = "[cyan]Fishbot is online."
    start_message_in_game = "[cyan]Fishbot is online."

    # Send message to Discord
    try:
        if discord_channel:
            await discord_channel.send(start_message_discord)
            print("Fishbot is online in Discord")
        else:
            print("Discord channel is not defined.")
    except Exception as e:
        print(f"Error sending message to Discord: {e}")

    # Send message in-game
    await send_message(start_message_in_game)
    print("Fishbot is online in-game")

# Function to handle the response to a question
async def handle_miner_question(question_text):
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
            await send_message("[gold]Mining everything")
            await asyncio.sleep(0.5)
            await send_message("!miner * 1000000")
            return

        resources = [resource for resource in valid_resources if resource in question_text.lower()]
        if resources:
            resource_list = ", ".join(resources)
            await send_message(f"[gold]Mining {resource_list}")
            await asyncio.sleep(0.5)
            await send_message(f"!miner {' '.join(resources)} 1000000")
            return

    # Send personalized message using the clipboard
    await send_message_to_chatgpt(question_text, list(context_lines))

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
async def detect_fishbot_questions(file_path):
    fishbot_pattern = re.compile(r'\bhey fishbot\b', re.IGNORECASE)
    connected_pattern = re.compile(r'has connected', re.IGNORECASE)
    received_world_data_pattern = re.compile(r'Received world data', re.IGNORECASE)

    with open(file_path, 'r', encoding='utf-8') as file:
        file.seek(0, 2)

        while True:
            line = file.readline()
            if not line:
                await asyncio.sleep(0.1)
                continue

            recent_lines.append(line.strip())
            context_lines.extend(recent_lines)
            if len(context_lines) > CONTEXT_LINES_COUNT:
                context_lines.popleft()

            if fishbot_pattern.search(line):
                await handle_miner_question(clean_chat_log(line.strip()))

            if connected_pattern.search(line):
                welcome_player = load_list_from_file(welcome_players)
                if welcome_player:
                    await send_message(f"Welcome, {welcome_player}.")

            if received_world_data_pattern.search(line):
                await send_instructions()

async def main():
    global discord_channel

    # Start Discord client
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        nonlocal discord_channel
        discord_channel = client.get_channel(1280217973965197497)  # Replace with your channel ID
        if discord_channel:
            print(f"Logged in as {client.user}")
            await send_start_message()
        else:
            print("Failed to find Discord channel")

    # Start the Discord client and the log file detection
    await asyncio.gather(
        client.start(DISCORD_TOKEN),
        detect_fishbot_questions(FILE_PATH)
    )

if __name__ == "__main__":
    asyncio.run(main())
