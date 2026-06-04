import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN in ("your_token_here", ""):
    raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env файле")
if not OPENAI_API_KEY or OPENAI_API_KEY in ("your_key_here", ""):
    raise ValueError("OPENAI_API_KEY не задан в .env файле")

MAX_HISTORY_PAIRS = 10
MAX_MESSAGE_LENGTH = 2000
MAX_TOKENS = 1024
TEMPERATURE = 0.3
OPENAI_TIMEOUT = 30
RATE_LIMIT_MESSAGES = 10
RATE_LIMIT_WINDOW = 60
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "bot.log")
CHAT_LOG_FILE = os.path.join(LOG_DIR, "conversations.log")
