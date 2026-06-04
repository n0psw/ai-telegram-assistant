import json
import logging
import time
import math
import asyncio
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, MAX_TOKENS, TEMPERATURE, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
EMBEDDING_MODEL = "text-embedding-3-small"

# Load vector store
try:
    with open("vector_store.json", "r", encoding="utf-8") as f:
        VECTOR_STORE = json.load(f)
except FileNotFoundError:
    VECTOR_STORE = []
    logger.warning("vector_store.json not found! RAG will not work.")

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

async def get_embedding(text: str) -> list[float]:
    response = await client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding

async def retrieve_context(query: str, top_k: int = 3) -> str:
    if not VECTOR_STORE:
        return ""
    
    query_emb = await get_embedding(query)
    
    # Calculate similarities
    scored_chunks = []
    for chunk in VECTOR_STORE:
        score = cosine_similarity(query_emb, chunk["embedding"])
        scored_chunks.append((score, chunk["text"]))
        
    # Sort by score descending
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # Take top K
    top_chunks = [chunk[1] for chunk in scored_chunks[:top_k]]
    
    return "\n\n---\n\n".join(top_chunks)

async def check_intent(user_query: str) -> dict:
    """
    Guardrail (Intent Router).
    Returns JSON: {"is_relevant": true/false, "search_query": "optimal query for RAG"}
    """
    router_prompt = """Ты — строгий классификатор намерений для магазина красок «Центр Красок #1».
Определи, относится ли запрос пользователя к нашему бизнесу:
- лакокрасочные материалы, инструменты, декор, ремонт
- доставка, оплата, цены, контакты, магазины, адреса, сотрудничество
Если запрос про доставку, адреса или как купить — это СТРОГО РЕЛЕВАНТНО (is_relevant: true).
Если запрос про политику, рецепты еды, программирование, отвлеченные темы — is_relevant: false.
Ответь СТРОГО в формате JSON:
{
  "is_relevant": boolean,
  "search_query": "оптимизированный запрос для поиска в базе (или null если is_relevant=false)"
}"""
    
    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": router_prompt},
                {"role": "user", "content": user_query}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            timeout=OPENAI_TIMEOUT
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        logger.error(f"Intent check failed: {e}")
        return {"is_relevant": True, "search_query": user_query}

SYSTEM_PROMPT_TEMPLATE = """Ты — AI-ассистент компании «Центр Красок #1», интернет-магазина ЛКМ в Казахстане.

Правила:
1. Отвечай ТОЛЬКО на основе предоставленного ниже контекста из базы знаний.
2. Не придумывай цены, бренды или адреса. Если в контексте нет точного ответа — скажи: «У меня нет точной информации по этому вопросу. Уточните по телефону 📞 +7 (777) 292-84-01».
3. Отвечай на языке пользователя. Будь краток и дружелюбен.

Контекст из базы знаний:
{context}"""

async def stream_ai_response(history: list[dict]):
    """
    Асинхронный генератор, который сначала делает RAG, а затем стримит ответ.
    """
    last_user_message = next((msg["content"] for msg in reversed(history) if msg["role"] == "user"), "")
    
    # 1. Intent Router
    intent = await check_intent(last_user_message)
    if not intent.get("is_relevant", True):
        yield "Извините, но я специализируюсь только на вопросах о красках, ремонте и продукции «Центр Красок #1». 🎨 Чем я могу помочь по нашему ассортименту?"
        return
        
    search_query = intent.get("search_query") or last_user_message
    
    # 2. RAG
    context = await retrieve_context(search_query)
    system_content = SYSTEM_PROMPT_TEMPLATE.format(context=context)
    
    messages = [{"role": "system", "content": system_content}] + history

    # 3. Stream Response
    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=True,
            timeout=OPENAI_TIMEOUT,
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield "Извините, произошла техническая ошибка при формировании ответа."
