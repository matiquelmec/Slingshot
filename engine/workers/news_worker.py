from engine.core.logger import logger
import asyncio
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
from datetime import datetime

# --- INSTITUTIONAL NOISE REDUCTION v5.7.156 ---
# Silenciamos la advertencia de BS4 al usar html.parser para feeds XML (Zero-Dependency fallback)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
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
        logger.info("📰 [NEWS-WORKER] Iniciando radar de noticias en tiempo real...")
        while not self._stop_event.is_set():
            try:
                await self.fetch_and_process_news()
            except Exception as e:
                logger.error(f"⚠️ [NEWS-WORKER] Error en ciclo de noticias: {e}")
            
            await asyncio.sleep(self.interval)

    async def fetch_and_process_news(self):
        async with httpx.AsyncClient(timeout=15.0) as client:
            for url in RSS_FEEDS:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        items_data = []
                        try:
                            # v5.7.156 Zero-Dependency Fix: Usar 'html.parser' en lugar de 'lxml-xml' 
                            # para evitar errores de 'tree builder not found' en entornos sin lxml.
                            soup = BeautifulSoup(response.content, 'html.parser')
                            items = soup.find_all('item')[:5]
                            
                            for item in items:
                                title_tag = item.find('title')
                                link_tag = item.find('link')
                                if title_tag and link_tag:
                                    title_text = title_tag.get_text().strip()
                                    link_text = link_tag.get_text().strip()
                                    if title_text and link_text:
                                        items_data.append({"title": title_text, "link": link_text})
                        except Exception as parse_err:
                            logger.warning(f"⚠️ [NEWS-WORKER] BS4 Parse error on {url}: {parse_err}")

                        for item_data in items_data:
                            title = item_data["title"]
                            link = item_data["link"]
                            
                            # Evitar procesar lo que ya tenemos
                            existing_news = await store.get_news()
                            if any(n['title'] == title for n in existing_news):
                                continue

                            logger.info(f"🧠 [NEWS-WORKER] Analizando titular: {title[:50]}...")
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
                    logger.error(f"❌ [NEWS-WORKER] Error rastreando {url}: {e}")

    def stop(self):
        self._stop_event.set()
