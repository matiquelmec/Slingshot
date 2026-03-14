import asyncio
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from engine.core.store import store
from engine.api.advisor import generate_news_sentiment
from engine.api.ws_manager import registry

RSS_FEEDS = [
    "https://cryptopanic.com/news/rss/",
    "https://cointelegraph.com/rss"
]

class NewsWorker:
    """
    Worker que rastrea noticias en tiempo real y realiza análisis de sentimiento local.
    """
    def __init__(self, interval_seconds: int = 300):
        self.interval = interval_seconds
        self._stop_event = asyncio.Event()

    async def start(self):
        print("📰 [NEWS-WORKER] Iniciando radar de noticias en tiempo real...")
        while not self._stop_event.is_set():
            try:
                await self.fetch_and_process_news()
            except Exception as e:
                print(f"⚠️ [NEWS-WORKER] Error en ciclo de noticias: {e}")
            
            await asyncio.sleep(self.interval)

    async def fetch_and_process_news(self):
        async with httpx.AsyncClient(timeout=15.0) as client:
            for url in RSS_FEEDS:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        root = ET.fromstring(response.content)
                        items = root.findall('.//item')
                        
                        for item in items[:5]: # Procesar las 5 más recientes de cada feed
                            title = item.find('title').text
                            link = item.find('link').text
                            
                            # Evitar procesar lo que ya tenemos
                            existing_news = await store.get_news()
                            if any(n['title'] == title for n in existing_news):
                                continue

                            print(f"🧠 [NEWS-WORKER] Analizando titular: {title[:50]}...")
                            analysis = await generate_news_sentiment(title)
                            
                            news_item = {
                                "title": analysis.get("translated_title", title),
                                "url": link,
                                "source": "CryptoPanic" if "cryptopanic" in url else "CoinTelegraph",
                                "timestamp": datetime.now().isoformat(),
                                "sentiment": analysis.get("sentiment", "NEUTRAL"),
                                "score": analysis.get("score", 0.5),
                                "impact": analysis.get("impact", "Sin análisis detallado.")
                            }
                            
                            await store.save_news(news_item)
                            
                            # Broadcast inmediato a través de todos los canales activos
                            payload = {"type": "news_update", "data": news_item}
                            for broadcaster in registry._broadcasters.values():
                                await broadcaster._broadcast(payload)
                                
                except Exception as e:
                    print(f"❌ [NEWS-WORKER] Error rastreando {url}: {e}")

    def stop(self):
        self._stop_event.set()
