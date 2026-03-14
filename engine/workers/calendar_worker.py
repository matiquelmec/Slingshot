
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
                    for event in events:
                        if event["country"] in ["USD", "EUR", "ALL"] or event["impact"] == "High":
                            relevant_events.append({
                                "title": event["title"],
                                "country": event["country"],
                                "impact": event["impact"],
                                "date": event["date"],
                                "forecast": event.get("forecast", ""),
                                "previous": event.get("previous", ""),
                            })

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
