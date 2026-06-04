import asyncio
from ai_service import stream_ai_response

async def main():
    history = [{"role": "user", "content": "Сколько стоит доставка в Алматы?"}]
    print("User: Сколько стоит доставка в Алматы?")
    print("Assistant: ", end="", flush=True)
    async for chunk in stream_ai_response(history):
        print(chunk, end="", flush=True)
    print("\n---")
    
    history2 = [{"role": "user", "content": "Как приготовить плов?"}]
    print("User: Как приготовить плов?")
    print("Assistant: ", end="", flush=True)
    async for chunk in stream_ai_response(history2):
        print(chunk, end="", flush=True)
    print("\n---")

if __name__ == "__main__":
    asyncio.run(main())
