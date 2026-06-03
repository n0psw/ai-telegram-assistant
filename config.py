import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_HISTORY_PAIRS = 10
MAX_MESSAGE_LENGTH = 2000
MAX_TOKENS = 1024
TEMPERATURE = 0.3
RATE_LIMIT_MESSAGES = 10
RATE_LIMIT_WINDOW = 60
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "bot.log")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "conversations.log")
