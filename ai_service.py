import logging
import time
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, MAX_TOKENS, TEMPERATURE
from company_knowledge import COMPANY_INFO

logger = logging.getLogger(__name__)

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
8. Используй эмодзи умеренно для дружелюбности.
9. Не используй Markdown-форматирование (**, ##, и т.д.) — пиши обычным текстом.

Вот информация о компании:

{COMPANY_INFO}
"""

MAX_RETRIES = 3
RETRY_DELAY = 1


def get_ai_response(history: list[dict]) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return (
                    "Извините, сейчас возникли технические сложности. "
                    "Попробуйте через пару минут или свяжитесь с нами:\n"
                    "📞 +7 (777) 292-84-01\n"
                    "📧 info@centr-krasok.kz"
                )
