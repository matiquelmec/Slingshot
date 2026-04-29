from engine.core.logger import logger
import asyncio
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
from datetime import datetime, timedelta, timezone
import re
import hashlib

from engine.core.store import store
from engine.api.advisor import generate_news_sentiment_batch
from engine.api.registry import registry

RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://news.bitcoin.com/feed/",
    "https://cryptopanic.com/news/rss/"
]

# --- INSTITUTIONAL SMART-FLOW TIERING v6.5 (Guerra & Macro Aware) ---
TIER_1_KEYWORDS = {
    "fed", "sec", "cpi", "binance", "halving", "etf", "hack", "fomc", "powell", 
    "blackrock", "trump", "iran", "war", "israel", "geopolitical", "nuclear", "hack", "exploit"
}
TIER_2_KEYWORDS = {
    "adoption", "launch", "partnership", "upgrade", "integration", "exchange", 
    "whale", "grayscale", "fidelity", "outflow", "inflow", "shorts", "longs", "liquidation"
}

def get_news_tier(title: str) -> int:
    """Clasifica la noticia por impacto institucional."""
    t = title.lower()
    if any(k in t for k in TIER_1_KEYWORDS): return 1
    if any(k in t for k in TIER_2_KEYWORDS): return 2
    return 3

def elite_normalize(text):
    """Normalización alfanumérica para deduplicación ultra-precisa."""
    return re.sub(r'[^a-z0-9]', '', text.lower().strip())

class NewsWorker:
    """
    Worker que rastrea noticias en tiempo real y realiza análisis de sentimiento local.
    """
    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self._stop_event = asyncio.Event()

    async def start(self):
        logger.info("📰 [NEWS-WORKER] Iniciando radar de noticias en tiempo real...")
        
        # v5.9-Fix: Esperar a que Ollama esté disponible antes del bootstrap
        import engine.api.advisor as advisor_mod
        for i in range(15):
            if await advisor_mod.check_ollama_status():
                logger.info(f"📰 [NEWS-WORKER] Ollama confirmado tras {i}s. Iniciando análisis con IA.")
                break
            await asyncio.sleep(1)
        else:
            logger.warning("📰 [NEWS-WORKER] Ollama no detectado tras 15s. Bootstrap sin IA.")

        # 🚀 BOOTSTRAP FETCH: Carga inicial
        try:
            await self.fetch_and_process_news()
        except Exception as e:
            logger.error(f"⚠️ [NEWS-WORKER] Fallo en carga inicial: {e}")

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.interval)
                await self.fetch_and_process_news()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [NEWS-WORKER] Error en ciclo: {e}")

    async def fetch_and_process_news(self):
        """Rastrea feeds RSS, analiza sentimiento y guarda en el store."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        all_new_items = []
        # Obtener noticias existentes para deduplicación simétrica
        existing_news = await store.get_news()
        existing_titles = {elite_normalize(n.get('title', '')) for n in existing_news}
        existing_urls = {n.get('url', '').lower().rstrip('/').split('?')[0] for n in existing_news}

        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            for url in RSS_FEEDS:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        # Si recibimos HTML en vez de XML (bloqueo Cloudflare/Bot), descartar
                        if "<html" in response.text.lower()[:500]:
                            logger.warning(f"⚠️ [NEWS-WORKER] Feed {url} bloqueado (HTML devuelto). Saltando...")
                            continue
                            
                        try:
                            # Parseo robusto con RegExp en lugar de ET estricto para evitar fallos de entidades XML (&, <, >)
                            # Extraemos los bloques <item>...</item>
                            import re
                            items = re.findall(r'<item.*?</item>', response.text, re.IGNORECASE | re.DOTALL)
                            items = items[:25]
                            
                            for item_xml in items:
                                title_match = re.search(r'<title.*?>(.*?)</title>', item_xml, re.IGNORECASE | re.DOTALL)
                                link_match = re.search(r'<link.*?>(.*?)</link>', item_xml, re.IGNORECASE | re.DOTALL)
                                
                                title = title_match.group(1).replace('<![CDATA[', '').replace(']]>', '').strip() if title_match else ""
                                link = link_match.group(1).replace('<![CDATA[', '').replace(']]>', '').strip() if link_match else ""
                                
                                if not title or not link: continue
                                
                                link_norm = link.lower().rstrip('/').split('?')[0]
                                title_norm = elite_normalize(title)
                                
                                if title_norm in existing_titles or link_norm in existing_urls:
                                    continue
                                        
                                tier = get_news_tier(title)
                                all_new_items.append({
                                    "original_title": title, 
                                    "link": link,
                                    "source": "CryptoPanic" if "cryptopanic" in url else "NewsSource",
                                    "tier": tier
                                })
                                existing_titles.add(title_norm)
                                existing_urls.add(link_norm)
                        except Exception as parse_err:
                            logger.error(f"❌ [NEWS-WORKER] Error de parseo XML en {url}: {parse_err}")
                            continue

                except Exception as track_err:
                    logger.error(f"❌ [NEWS-WORKER] Error rastreando {url}: {track_err}")

        if not all_new_items:
            return

        # Cap de seguridad por batch (Modo Conservador y Limpio)
        if len(all_new_items) > 10:
            all_new_items = all_new_items[:10]

        # Sincronizar, guardar y emitir inmediatamente (Análisis en Segundo Plano)
        base_ts = datetime.now(timezone.utc)
        to_analyze = []

        for j, item in enumerate(all_new_items):
            news_id = hashlib.sha256(item["link"].encode('utf-8')).hexdigest()
            
            is_tier_3 = item["tier"] == 3
            
            # 🚀 PRE-GUARDADO Y BROADCAST (Velocidad Institucional)
            news_item = {
                "id": news_id,
                "title": item["original_title"],
                "url": item["link"],
                "source": item["source"],
                "timestamp": (base_ts + timedelta(milliseconds=j)).isoformat(),
                "sentiment": "NEUTRAL",
                "score": 0.5,
                "impact": "Impacto menor / Ruido de mercado." if is_tier_3 else f"Tier {item['tier']} - Procesando...",
                "tier": item["tier"],
                "weight": 1.0,
                "analyzing": not is_tier_3
            }
            
            await store.save_news(news_item)
            await registry.broadcast_global({"type": "news_update", "data": news_item})

            if not is_tier_3:
                to_analyze.append(news_item)

        # 🧠 ANÁLISIS POR LOTE (Eficiencia v7.0)
        if to_analyze:
            asyncio.create_task(self._analyze_news_batch(to_analyze))

    async def _analyze_news_batch(self, news_items: list[dict]):
        """Analiza un grupo de noticias en una sola ráfaga para optimizar Ollama."""
        try:
            headlines = [n["title"] for n in news_items]
            results = await generate_news_sentiment_batch(headlines)
            
            for i, analysis in enumerate(results):
                if i >= len(news_items): break
                
                item = news_items[i]
                item.update({
                    "title": analysis.get("translated_title", item["title"]),
                    "sentiment": analysis.get("sentiment", "NEUTRAL"),
                    "score": analysis.get("score", 0.5),
                    "impact": analysis.get("impact", "Análisis completado."),
                    "weight": 3.0 if item["tier"] == 1 else 1.5,
                    "analyzing": False
                })
                
                await store.save_news(item)
                await registry.broadcast_global({"type": "news_update", "data": item})
                
            logger.info(f"🧠 [NEWS-BATCH] ✅ {len(news_items)} noticias analizadas eficientemente.")
            
        except Exception as e:
            logger.error(f"❌ [NEWS-BATCH] Error en proceso de lote: {e}")
            for item in news_items:
                item["analyzing"] = False
                item["impact"] = "IA temporalmente ocupada."
                await store.save_news(item)
                await registry.broadcast_global({"type": "news_update", "data": item})

    def stop(self):
        self._stop_event.set()
