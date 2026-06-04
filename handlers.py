import os
import time
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ai_service import stream_ai_response
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


def _check_and_reset_ttl(user_id: int):
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


async def _process_stream(history: list[dict], message_obj, user, user_text: str):
    """
    Универсальная функция стриминга ответа в Telegram-сообщение.
    """
    chat_logger.info(f"USER:{user.id}:{user.username} | Q: {user_text}")

    current_text = ""
    last_edit_time = time.time()
    
    try:
        async for chunk in stream_ai_response(history):
            current_text += chunk
            
            # Обновляем сообщение в Telegram не чаще раза в секунду
            if time.time() - last_edit_time > 1.0 and current_text.strip():
                try:
                    await message_obj.edit_text(current_text + " ✍️")
                    last_edit_time = time.time()
                except Exception:
                    pass # Игнорируем ошибки MessageNotModified
                    
    except Exception as e:
        logger.error(f"Error during stream: {e}")
        current_text = "Извините, произошла ошибка. Попробуйте еще раз."

    # Финальный апдейт с клавиатурой
    final_text = current_text.strip() or "Ой, я не смог сформировать ответ 😔"
    try:
        await message_obj.edit_text(final_text, reply_markup=FAQ_KEYBOARD)
    except Exception:
        pass

    chat_logger.info(f"USER:{user.id}:{user.username} | A: {final_text[:200]}")
    database.add_message(user.id, "assistant", final_text)


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
    
    # Отправляем вопрос юзера от его имени (так как это callback)
    await query.message.reply_text(f"👤 *Вы:* {user_text}", parse_mode="Markdown")
    
    # Создаем placeholder для ответа
    bot_msg = await query.message.reply_text("⏳ Думаю...")

    database.add_message(user.id, "user", user_text)
    history = database.get_history(user.id)

    # Запускаем стриминг в placeholder
    await _process_stream(history, bot_msg, user, user_text)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text

    if not user_text or not user_text.strip() or user.is_bot:
        return

    if not check_rate_limit(user.id):
        await update.message.reply_text(RATE_LIMIT_TEXT)
        return

    if len(user_text) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text(TOO_LONG_TEXT)
        return

    _check_and_reset_ttl(user.id)
    _update_user_db(user)

    history = database.get_history(user.id)
    
    # Если история пуста (например, новый пользователь или после TTL/сброса диалога), 
    # здороваемся, прежде чем отвечать.
    if not history and not context.user_data.get("greeted_this_session"):
        context.user_data["greeted_this_session"] = True
        await update.message.reply_text(WELCOME_TEXT, reply_markup=FAQ_KEYBOARD)

    # Создаем placeholder для ответа
    bot_msg = await update.message.reply_text("⏳ Думаю...")

    database.add_message(user.id, "user", user_text)
    history = database.get_history(user.id) # Обновляем историю с новым сообщением

    # Запускаем стриминг в placeholder
    await _process_stream(history, bot_msg, user, user_text)


async def non_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(NON_TEXT_TEXT)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = database.get_stats()
    await update.message.reply_text(stats_text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")
