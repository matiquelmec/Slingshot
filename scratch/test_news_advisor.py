import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.api.advisor import generate_news_sentiment_batch, check_ollama_status, start_ai_worker

async def main():
    start_ai_worker()
    print("Chequeando status de ollama...")
    status = await check_ollama_status()
    print(f"Ollama Status: {status}")
    
    if status:
        print("Enviando noticia de prueba al LLM...")
        headlines = ["SEC approves first Bitcoin Spot ETF, markets surge over 10%"]
        try:
            # Add a timeout so we don't wait forever
            res = await asyncio.wait_for(generate_news_sentiment_batch(headlines), timeout=30.0)
            print("Respuesta del LLM:", res)
        except asyncio.TimeoutError:
            print("Timeout esperando respuesta del LLM!")

if __name__ == "__main__":
    asyncio.run(main())
