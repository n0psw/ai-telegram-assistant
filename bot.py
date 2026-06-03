import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler,
)
from company_knowledge import COMPANY_INFO

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = f"""Ты — AI-ассистент компании «Центр Красок #1», интернет-магазина лакокрасочных материалов в Казахстане.

Твои правила:
1. Отвечай ТОЛЬКО на основе предоставленной информации о компании. Не выдумывай данные.
2. Если вопрос не связан с компанией или её продукцией — вежливо сообщи, что ты можешь помочь только с вопросами о «Центр Красок #1».
3. Отвечай на русском языке, дружелюбно и профессионально.
4. Если не знаешь точный ответ — скажи об этом честно и предложи обратиться по телефону +7 (777) 292-84-01 или email info@centr-krasok.kz.
5. Будь кратким, но информативным. Используй структурированные ответы со списками, когда это уместно.
6. При вопросах о конкретных товарах — предлагай посмотреть каталог на сайте https://centr-krasok.kz/catalog/
7. Если спрашивают о ценах конкретных товаров — направь на сайт или рекомендуй позвонить, так как цены могут меняться.

Вот информация о компании:

{COMPANY_INFO}
"""

MAX_HISTORY = 10


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "Здравствуйте! 👋\n\n"
        "Я — AI-ассистент компании «Центр Красок #1».\n"
        "Задайте мне любой вопрос о нашей компании, продукции, брендах, доставке или контактах.\n\n"
        "Просто напишите ваш вопрос! 🎨"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text or not user_text.strip():
        return

    if "history" not in context.user_data:
        context.user_data["history"] = []

    history = context.user_data["history"]
    history.append({"role": "user", "content": user_text})

    if len(history) > MAX_HISTORY * 2:
        history = history[-(MAX_HISTORY * 2):]
        context.user_data["history"] = history

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    await update.message.chat.send_action("typing")

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        reply = (
            "Извините, произошла техническая ошибка. "
            "Попробуйте позже или свяжитесь с нами по телефону: +7 (777) 292-84-01"
        )

    history.append({"role": "assistant", "content": reply})
    context.user_data["history"] = history

    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i : i + 4096])
    else:
        await update.message.reply_text(reply)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")


def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("Ошибка: укажите TELEGRAM_BOT_TOKEN в файле .env")
        return
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key_here":
        print("Ошибка: укажите OPENAI_API_KEY в файле .env")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("Бот запущен! Нажмите Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
