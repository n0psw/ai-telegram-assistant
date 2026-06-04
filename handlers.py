import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    "Спросите меня о:\n"
    "🎨 Продукции и брендах\n"
    "🏪 Салонах и контактах\n"
    "🚚 Доставке и оплате\n"
    "🤝 Сотрудничестве\n\n"
    "Или выберите тему ниже 👇"
)

RATE_LIMIT_TEXT = (
    "⏳ Вы отправляете сообщения слишком часто.\n"
    "Подождите немного и попробуйте снова."
)

TOO_LONG_TEXT = (
    "📝 Сообщение слишком длинное.\n"
    f"Максимальная длина — {MAX_MESSAGE_LENGTH} символов."
)

FAQ_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏢 О компании", callback_data="faq_about")],
    [InlineKeyboardButton("🎨 Какие бренды?", callback_data="faq_brands")],
    [InlineKeyboardButton("🚚 Доставка", callback_data="faq_delivery")],
    [InlineKeyboardButton("📍 Адреса салонов", callback_data="faq_contacts")],
    [InlineKeyboardButton("💳 Оплата", callback_data="faq_payment")],
    [InlineKeyboardButton("🤝 Сотрудничество", callback_data="faq_partners")],
])

FAQ_QUESTIONS = {
    "faq_about": "Расскажи о компании Центр Красок #1",
    "faq_brands": "Какие бренды представлены в магазине?",
    "faq_delivery": "Как работает доставка? В какие города доставляете?",
    "faq_contacts": "Где находятся ваши салоны? Какие адреса и телефоны?",
    "faq_payment": "Какие способы оплаты доступны?",
    "faq_partners": "Как стать партнёром? Какие условия для дизайнеров и строителей?",
}


async def _keep_typing(chat, stop_event: asyncio.Event):
    while not stop_event.is_set():
        await chat.send_action("typing")
        try:
            await asyncio.wait_for(asyncio.shield(stop_event.wait()), timeout=4)
        except asyncio.TimeoutError:
            pass


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    context.user_data["greeted"] = True
    await update.message.reply_text(WELCOME_TEXT, reply_markup=FAQ_KEYBOARD)


async def faq_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    faq_key = query.data
    if faq_key not in FAQ_QUESTIONS:
        return

    user_text = FAQ_QUESTIONS[faq_key]
    user = query.from_user

    if "history" not in context.user_data:
        context.user_data["history"] = []

    history = context.user_data["history"]
    history.append({"role": "user", "content": user_text})

    if len(history) > MAX_HISTORY_PAIRS * 2:
        history = history[-(MAX_HISTORY_PAIRS * 2):]
        context.user_data["history"] = history

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(query.message.chat, stop_event))

    chat_logger.info(f"USER:{user.id}:{user.username} | Q(FAQ): {user_text}")

    try:
        reply = await asyncio.get_event_loop().run_in_executor(None, get_ai_response, history)
    finally:
        stop_event.set()
        typing_task.cancel()

    chat_logger.info(f"USER:{user.id}:{user.username} | A: {reply[:200]}")

    history.append({"role": "assistant", "content": reply})
    context.user_data["history"] = history

    await query.message.reply_text(reply, reply_markup=FAQ_KEYBOARD)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text

    if not user_text or not user_text.strip():
        return

    if update.effective_user.is_bot:
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
        await update.message.reply_text(WELCOME_TEXT, reply_markup=FAQ_KEYBOARD)

    history = context.user_data.get("history", [])
    history.append({"role": "user", "content": user_text})

    if len(history) > MAX_HISTORY_PAIRS * 2:
        history = history[-(MAX_HISTORY_PAIRS * 2):]
        context.user_data["history"] = history

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update.message.chat, stop_event))

    chat_logger.info(f"USER:{user.id}:{user.username} | Q: {user_text}")

    try:
        reply = await asyncio.get_event_loop().run_in_executor(None, get_ai_response, history)
    finally:
        stop_event.set()
        typing_task.cancel()

    chat_logger.info(f"USER:{user.id}:{user.username} | A: {reply[:200]}")

    history.append({"role": "assistant", "content": reply})
    context.user_data["history"] = history

    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i: i + 4096])
    else:
        await update.message.reply_text(reply, reply_markup=FAQ_KEYBOARD)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")
