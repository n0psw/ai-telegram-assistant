import os
import time
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ai_service import get_ai_response
from middleware import check_rate_limit
from config import MAX_HISTORY_PAIRS, MAX_MESSAGE_LENGTH, CHAT_LOG_FILE, LOG_DIR
import database

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

chat_logger = logging.getLogger("chat")
chat_handler = logging.FileHandler(CHAT_LOG_FILE, encoding="utf-8")
chat_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
chat_logger.addHandler(chat_handler)
chat_logger.setLevel(logging.INFO)

HISTORY_TTL_SECONDS = 2 * 60 * 60

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

NON_TEXT_TEXT = (
    "Я понимаю только текстовые сообщения 😊\n"
    "Напишите вопрос о компании «Центр Красок #1», и я помогу!"
)

FAQ_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏢 О компании", callback_data="faq_about")],
    [InlineKeyboardButton("🎨 Какие бренды?", callback_data="faq_brands")],
    [InlineKeyboardButton("🚚 Доставка", callback_data="faq_delivery")],
    [InlineKeyboardButton("📍 Адреса салонов", callback_data="faq_contacts")],
    [InlineKeyboardButton("💳 Оплата", callback_data="faq_payment")],
    [InlineKeyboardButton("🤝 Сотрудничество", callback_data="faq_partners")],
    [InlineKeyboardButton("🔄 Новый диалог", callback_data="new_dialog")],
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


def _check_and_reset_ttl(user_id: int):
    # In a full implementation, we'd fetch last_seen from DB.
    # For MVP, we can rely on context or just keep history until explicitly reset.
    # Actually, we can fetch last_seen:
    try:
        with database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_seen FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row[0]:
                last_seen = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S.%f")
                if (datetime.now() - last_seen).total_seconds() > HISTORY_TTL_SECONDS:
                    database.clear_history(user_id)
                    logger.info(f"Conversation history reset due to TTL for user {user_id}")
    except Exception as e:
        logger.error(f"Error checking TTL: {e}")


def _update_user_db(user):
    database.update_user(user.id, user.username or "", user.first_name or "")


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    _update_user_db(user)
    database.clear_history(user.id)
    context.user_data["greeted"] = True
    await update.message.reply_text(WELCOME_TEXT, reply_markup=FAQ_KEYBOARD)


async def new_dialog_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer("Диалог сброшен ✅")
    _update_user_db(user)
    database.clear_history(user.id)
    await query.message.reply_text(WELCOME_TEXT, reply_markup=FAQ_KEYBOARD)


async def faq_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    faq_key = query.data
    if faq_key not in FAQ_QUESTIONS:
        return

    user = query.from_user
    _check_and_reset_ttl(user.id)
    _update_user_db(user)

    user_text = FAQ_QUESTIONS[faq_key]
    database.add_message(user.id, "user", user_text)

    history = database.get_history(user.id)

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(query.message.chat, stop_event))

    chat_logger.info(f"USER:{user.id}:{user.username} | Q(FAQ): {user_text}")

    try:
        reply = await get_ai_response(history)
    finally:
        stop_event.set()
        typing_task.cancel()

    chat_logger.info(f"USER:{user.id}:{user.username} | A: {reply[:200]}")

    database.add_message(user.id, "assistant", reply)

    await query.message.reply_text(reply, reply_markup=FAQ_KEYBOARD)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text

    if not user_text or not user_text.strip():
        return

    if user.is_bot:
        return

    if not check_rate_limit(user.id):
        await update.message.reply_text(RATE_LIMIT_TEXT)
        return

    if len(user_text) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text(TOO_LONG_TEXT)
        return

    _check_and_reset_ttl(user.id)
    _update_user_db(user)

    if not context.user_data.get("greeted"):
        context.user_data["greeted"] = True
        database.clear_history(user.id)
        await update.message.reply_text(WELCOME_TEXT, reply_markup=FAQ_KEYBOARD)

    database.add_message(user.id, "user", user_text)
    history = database.get_history(user.id)

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(update.message.chat, stop_event))

    chat_logger.info(f"USER:{user.id}:{user.username} | Q: {user_text}")

    try:
        reply = await get_ai_response(history)
    finally:
        stop_event.set()
        typing_task.cancel()

    chat_logger.info(f"USER:{user.id}:{user.username} | A: {reply[:200]}")

    database.add_message(user.id, "assistant", reply)

    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i: i + 4096])
    else:
        await update.message.reply_text(reply, reply_markup=FAQ_KEYBOARD)


async def non_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(NON_TEXT_TEXT)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # В идеале здесь должна быть проверка на ADMIN_ID, но для MVP покажем всем (или можно скрыть).
    # Пока оставим открытой командой /stats для демонстрации.
    stats_text = database.get_stats()
    await update.message.reply_text(stats_text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")
