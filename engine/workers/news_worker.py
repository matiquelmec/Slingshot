from engine.core.logger import logger
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
                            root = ET.fromstring(response.content)
                            for item in root.findall('.//item')[:5]:
                                title = item.find('title')
                                link = item.find('link')
                                if title is not None and link is not None and title.text and link.text:
                                    items_data.append({"title": title.text.strip(), "link": link.text.strip()})
                        except ET.ParseError as xml_err:
                            logger.warning(f"⚠️ [NEWS-WORKER] XML Parse error on {url} (usando regex fallback): {xml_err}")
                            import re
                            # Fallback extractor para RSS malformados
                            content_str = response.text
                            item_blocks = re.findall(r'<item>([\s\S]*?)</item>', content_str, re.IGNORECASE)
                            for block in item_blocks[:5]:
                                title_match = re.search(r'<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>', block, re.IGNORECASE)
                                link_match = re.search(r'<link>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</link>', block, re.IGNORECASE)
                                if title_match and link_match:
                                    items_data.append({"title": title_match.group(1).strip(), "link": link_match.group(1).strip()})

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
