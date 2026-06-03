import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from ai_service import get_ai_response
from middleware import check_rate_limit
from config import MAX_HISTORY_PAIRS, MAX_MESSAGE_LENGTH, CHAT_LOG_FILE, LOG_DIR

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

chat_logger = logging.getLogger("chat")
chat_handler = logging.FileHandler(CHAT_LOG_FILE, encoding="utf-8")
chat_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
chat_logger.addHandler(chat_handler)
chat_logger.setLevel(logging.INFO)

WELCOME_TEXT = (
    "Здравствуйте! 👋\n\n"
    "Я — AI-ассистент компании «Центр Красок #1».\n\n"
    "Вы можете задать мне любой вопрос:\n"
    "🎨 О продукции и брендах\n"
    "🏪 О наших салонах и контактах\n"
    "🚚 О доставке и оплате\n"
    "🤝 О сотрудничестве\n\n"
    "Просто напишите ваш вопрос!"
)

RATE_LIMIT_TEXT = (
    "⏳ Вы отправляете сообщения слишком часто.\n"
    "Подождите немного и попробуйте снова."
)

TOO_LONG_TEXT = (
    "📝 Сообщение слишком длинное.\n"
    f"Максимальная длина — {MAX_MESSAGE_LENGTH} символов."
)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    context.user_data["greeted"] = True
    await update.message.reply_text(WELCOME_TEXT)


async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("🔄 Контекст диалога очищен. Задайте новый вопрос!")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text

    if not user_text or not user_text.strip():
        return

    if not check_rate_limit(user.id):
        await update.message.reply_text(RATE_LIMIT_TEXT)
        return

    if len(user_text) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text(TOO_LONG_TEXT)
        return

    if not context.user_data.get("greeted"):
        context.user_data["greeted"] = True
        context.user_data["history"] = []

    history = context.user_data.get("history", [])
    history.append({"role": "user", "content": user_text})

    if len(history) > MAX_HISTORY_PAIRS * 2:
        history = history[-(MAX_HISTORY_PAIRS * 2):]
        context.user_data["history"] = history

    await update.message.chat.send_action("typing")

    chat_logger.info(f"USER:{user.id}:{user.username} | Q: {user_text}")

    reply = get_ai_response(history)

    chat_logger.info(f"USER:{user.id}:{user.username} | A: {reply[:200]}")

    history.append({"role": "assistant", "content": reply})
    context.user_data["history"] = history

    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i : i + 4096])
    else:
        await update.message.reply_text(reply)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")
