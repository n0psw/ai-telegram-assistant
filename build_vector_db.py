import os
import json
import asyncio
from openai import AsyncOpenAI
from config import OPENAI_API_KEY
from company_knowledge import COMPANY_INFO
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
EMBEDDING_MODEL = "text-embedding-3-small"

def chunk_text(text: str) -> list[str]:
    # Сплитим по заголовкам ##
    raw_chunks = text.split("\n## ")
    chunks = [raw_chunks[0].strip()] # Введение
    for c in raw_chunks[1:]:
        chunk = "## " + c.strip()
        chunks.append(chunk)
    
    # Можно дополнительно разбивать слишком длинные чанки (например, Q&A или Глоссарий), 
    # но для MVP такого чанкинга по секциям достаточно.
    return [c for c in chunks if c]

async def generate_embeddings(chunks: list[str]) -> list[dict]:
    logger.info(f"Generating embeddings for {len(chunks)} chunks...")
    db = []
    
    # В проде лучше батчами, но тут чанков мало (~20)
    for i, chunk in enumerate(chunks):
        try:
            response = await client.embeddings.create(
                input=chunk,
                model=EMBEDDING_MODEL
            )
            embedding = response.data[0].embedding
            db.append({
                "id": i,
                "text": chunk,
                "embedding": embedding
            })
            logger.info(f"Processed chunk {i+1}/{len(chunks)}")
        except Exception as e:
            logger.error(f"Error on chunk {i}: {e}")
            
    return db

async def main():
    chunks = chunk_text(COMPANY_INFO)
    db = await generate_embeddings(chunks)
    
    with open("vector_store.json", "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    logger.info("Saved vector_store.json successfully!")

if __name__ == "__main__":
    asyncio.run(main())
