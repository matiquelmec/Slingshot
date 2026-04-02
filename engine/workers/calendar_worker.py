
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
        print("📅 [CALENDAR-WORKER] Iniciando sincronizador de eventos macro...")
        # Ejecución inmediata al arrancar
        await self.fetch_and_process_calendar()
        
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.interval)
                await self.fetch_and_process_calendar()
            except Exception as e:
                print(f"⚠️ [CALENDAR-WORKER] Error en ciclo de calendario: {e}")

    async def fetch_and_process_calendar(self):
        print("🌐 [CALENDAR-WORKER] Descargando calendario económico...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            try:
                response = await client.get(CALENDAR_URL)
                if response.status_code == 200:
                    events = response.json()
                    relevant_events = []
                    now = datetime.now(timezone.utc)
                    now_iso = now.isoformat()
                    
                    for event in events:
                        event_date_str = event.get("date", "")
                        if not event_date_str: continue
                        
                        try:
                            # Parsear fecha del evento (manejando offsets de FF)
                            event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                            diff_hours = (now - event_date).total_seconds() / 3600
                            
                            # LOGICA DE PERSISTENCIA PROFESIONAL:
                            # 1. Todo lo futuro (diff_hours < 0)
                            # 2. Todo lo ocurrido en las últimas 24 horas (0 <= diff_hours <= 24)
                            is_relevant_time = diff_hours <= 24 
                            
                            if is_relevant_time:
                                if event["country"] in ["USD", "EUR", "ALL"] or event["impact"] == "High":
                                    # Añadir flag de estado para el LLM
                                    status = "LIVE" if abs((event_date - now).total_seconds()) < 1800 else \
                                            ("UPCOMING" if event_date > now else "RECENT_PAST")
                                    
                                    relevant_events.append({
                                        "title": event["title"],
                                        "country": event["country"],
                                        "impact": event["impact"],
                                        "date": event["date"],
                                        "status": status,
                                        "forecast": event.get("forecast", ""),
                                        "previous": event.get("previous", ""),
                                    })
                        except Exception as ee:
                            print(f"⚠️ [CALENDAR-WORKER] Error procesando evento {event.get('title')}: {ee}")

                    # Ordenar: Lo más inminente o reciente primero
                    relevant_events.sort(key=lambda x: abs((datetime.fromisoformat(x['date'].replace('Z', '+00:00')) - now).total_seconds()))
                    await store.save_economic_events(relevant_events)
                    print(f"✅ [CALENDAR-WORKER] {len(relevant_events)} eventos macro sincronizados.")
                else:
                    print(f"⚠️ [CALENDAR-WORKER] Error API ({response.status_code}). Usando caché local...")
                    raise Exception("API_ERROR")
                    
            except Exception:
                # Fallback: leer del archivo local
                try:
                    import json, os
                    # Path absoluto para evitar errores
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    file_path = os.path.join(base_dir, "data", "economic_calendar.json")
                    
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8") as f:
                            relevant_events = json.load(f)
                            await store.save_economic_events(relevant_events)
                            print(f"✅ [CALENDAR-WORKER] {len(relevant_events)} eventos cargados desde CACHE LOCAL.")
                    else:
                        print("❌ [CALENDAR-WORKER] No se encontró caché local ni conexión API.")
                except Exception as fe:
                    print(f"❌ [CALENDAR-WORKER] Error en fallback local: {fe}")

    def stop(self):
        self._stop_event.set()
