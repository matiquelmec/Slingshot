
from engine.core.logger import logger
import asyncio
import httpx
from datetime import datetime, timezone
from engine.core.store import store

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

class CalendarWorker:
    """
    Worker que sincroniza el calendario económico global (Forex Factory).
    Refresca los eventos macro cada 6 horas.
    """
    def __init__(self, interval_seconds: int = 21600): # 6 horas
        self.interval = interval_seconds
        self._stop_event = asyncio.Event()

    async def start(self):
        logger.info("📅 [CALENDAR-WORKER] Iniciando sincronizador de eventos macro...")
        # Ejecución inmediata al arrancar
        await self.fetch_and_process_calendar()
        
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.interval)
                await self.fetch_and_process_calendar()
            except Exception as e:
                logger.error(f"⚠️ [CALENDAR-WORKER] Error en ciclo de calendario: {e}")

    async def fetch_and_process_calendar(self):
        logger.info("🌐 [CALENDAR-WORKER] Sincronizando calendario económico...")
        
        # 1. CARGAR CACHÉ LOCAL PRIMERO (Inyección Prioritaria v8.8.4)
        local_events = []
        try:
            import json, os
            # Path absoluto robusto
            current_file = os.path.abspath(__file__)
            base_dir = os.path.dirname(os.path.dirname(current_file))
            file_path = os.path.join(base_dir, "data", "economic_calendar.json")
            
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    local_events = json.load(f)
                    if local_events:
                        await store.save_economic_events(local_events)
                        logger.info(f"✅ [CALENDAR-WORKER] {len(local_events)} eventos inyectados desde cache local.")
        except Exception as fe:
            logger.error(f"❌ [CALENDAR-WORKER] Error cargando inyección local: {fe}")

        # 2. INTENTAR ACTUALIZAR DESDE API (Si hay internet)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            try:
                response = await client.get(CALENDAR_URL)
                if response.status_code == 200:
                    api_events = response.json()
                    relevant_events = []
                    now = datetime.now(timezone.utc)
                    
                    for event in api_events:
                        # ... lógica de filtrado ...
                        try:
                            event_date = datetime.fromisoformat(event.get("date", "").replace('Z', '+00:00'))
                            diff_hours = (now - event_date).total_seconds() / 3600
                            
                            if diff_hours <= 24: # Mantener solo lo reciente o futuro
                                if event["country"] in ["USD", "EUR", "ALL"] or event["impact"] == "High":
                                    relevant_events.append({
                                        "title": event["title"],
                                        "country": event["country"],
                                        "impact": event["impact"],
                                        "date": event["date"],
                                        "status": "UPCOMING" if event_date > now else "RECENT_PAST",
                                        "forecast": event.get("forecast", ""),
                                        "previous": event.get("previous", ""),
                                    })
                        except: continue

                    if relevant_events:
                        # Mezclar con locales evitando duplicados por título+fecha
                        titles_in_store = {e['title'] + e['date'] for e in local_events}
                        final_events = local_events + [e for e in relevant_events if (e['title'] + e['date']) not in titles_in_store]
                        
                        # Ordenar por cercanía a 'now'
                        final_events.sort(key=lambda x: abs((datetime.fromisoformat(x['date'].replace('Z', '+00:00')) - now).total_seconds()))
                        await store.save_economic_events(final_events)
                        logger.info(f"📡 [CALENDAR-WORKER] Calendario actualizado con {len(relevant_events)} eventos de la API.")
            except Exception as ae:
                logger.debug(f"ℹ️ [CALENDAR-WORKER] API no disponible o timeout ({ae}). Usando solo inyección local.")

    def stop(self):
        self._stop_event.set()
