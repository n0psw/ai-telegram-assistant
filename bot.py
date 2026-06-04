import os
import logging
from logging.handlers import RotatingFileHandler
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from config import TELEGRAM_BOT_TOKEN, LOG_DIR, LOG_FILE
from database import init_db
from handlers import (
    start_handler,
    message_handler,
    faq_callback_handler,
    new_dialog_callback_handler,
    non_text_handler,
    stats_handler,
    error_handler,
)

os.makedirs(LOG_DIR, exist_ok=True)

rotating_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
rotating_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        rotating_handler,
    ],
)
logger = logging.getLogger(__name__)


async def post_init(application):
    init_db()
    await application.bot.set_my_commands([])


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CallbackQueryHandler(new_dialog_callback_handler, pattern="^new_dialog$"))
    app.add_handler(CallbackQueryHandler(faq_callback_handler, pattern="^faq_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, non_text_handler))
    app.add_error_handler(error_handler)

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    # --- ФЕЙКОВЫЙ ВЕБ-СЕРВЕР ДЛЯ ОБХОДА ОГРАНИЧЕНИЙ RENDER ---
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class DummyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")
            
        def log_message(self, format, *args):
            # Отключаем логирование запросов, чтобы не мусорить в консоли
            pass

    def start_dummy_server():
        try:
            port = int(os.environ.get("PORT", 8080))
            server = HTTPServer(("0.0.0.0", port), DummyHandler)
            server.serve_forever()
        except Exception:
            pass


    threading.Thread(target=start_dummy_server, daemon=True).start()
    # ---------------------------------------------------------

    main()
