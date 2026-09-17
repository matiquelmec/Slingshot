"""
engine/indicators/news_interceptor.py — v33.0 (SOP-92 DYNAMIC HIGH-IMPACT NEWS SENTINEL)
=============================================================================
Responsabilidad: Interceptor Macroeconómico Dinámico de Alta Precisión.
Conectado en tiempo real al SSoT de eventos macroeconómicos (Forex Factory)
sincronizados por calendar_worker en engine.core.store.

Protocolo SOP-92:
1. Bloqueo estricto de nuevas aperturas: 30 minutos antes y 15 minutos después
   de cualquier evento de impacto "High" (Rojo) que afecte la divisa del activo.
2. Mapeo multiactivo institucional:
   - Índices / Metales / Cripto (US30, US100, US500, XAUUSD, BTC, ETH): Divisa base USD.
   - Pares Forex (GBPUSD, EURUSD): Divisas base y cotizada (GBP, EUR, USD).
3. Exposición de métodos para centinelas de blindaje de posiciones abiertas.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
import os
import json
from engine.core.logger import logger

class DynamicNewsInterceptor:
    """
    Interceptor Dinámico Cuantitativo de Eventos Macro de Alto Impacto (SOP-92).
    """

    # Mapeo institucional de activos a sus divisas macroeconómicas determinantes
    CURRENCY_MAPPING: Dict[str, Set[str]] = {
        "US30": {"USD"},
        "US30.CASH": {"USD"},
        "US100": {"USD"},
        "US100.CASH": {"USD"},
        "US500": {"USD"},
        "US500.CASH": {"USD"},
        "GER40": {"EUR"},
        "GER40.CASH": {"EUR"},
        "XAUUSD": {"USD"},
        "GOLD": {"USD"},
        "PAXGUSDT": {"USD"},
        "XAGUSD": {"USD"},
        "GBPUSD": {"GBP", "USD"},
        "EURUSD": {"EUR", "USD"},
        "USDJPY": {"USD", "JPY"},
        "AUDUSD": {"AUD", "USD"},
        "NZDUSD": {"NZD", "USD"},
        "USDCAD": {"USD", "CAD"},
        "USDCHF": {"USD", "CHF"},
        # Criptomonedas mayores: Altamente sensibles a liquidez y tasas de la Fed (USD)
        "BTCUSDT": {"USD"},
        "ETHUSDT": {"USD"},
        "SOLUSDT": {"USD"},
    }

    def __init__(self, default_before_mins: int = 30, default_after_mins: int = 15):
        self.default_before_mins = default_before_mins
        self.default_after_mins = default_after_mins
        self._manual_blackouts: List[Dict[str, Any]] = []

    def _get_relevant_currencies(self, asset: str) -> Set[str]:
        """Obtiene las divisas macroeconómicas que impactan a este activo."""
        clean_asset = asset.replace("/", "").replace(" ", "").upper()
        if clean_asset in self.CURRENCY_MAPPING:
            return self.CURRENCY_MAPPING[clean_asset]

        # Inferencia automática por subcadenas comunes
        currs = set()
        if any(usd_pair in clean_asset for usd_pair in ["US30", "US100", "US500", "XAU", "GOLD", "BTC", "ETH", "SOL", "FET", "NEAR", "TIA", "USDT", "USD"]):
            currs.add("USD")
        if "GBP" in clean_asset:
            currs.add("GBP")
        if "EUR" in clean_asset or "GER" in clean_asset:
            currs.add("EUR")
        if "JPY" in clean_asset:
            currs.add("JPY")
        if "AUD" in clean_asset:
            currs.add("AUD")
        if "NZD" in clean_asset:
            currs.add("NZD")
        if "CAD" in clean_asset:
            currs.add("CAD")

        return currs if currs else {"USD"}

    def is_macro_news_blackout(
        self,
        dt: Optional[datetime] = None,
        asset: str = "",
        buffer_before_mins: Optional[int] = None,
        buffer_after_mins: Optional[int] = None,
        store_events: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Determina si el momento actual (o `dt`) se encuentra en una ventana de blackout
        para el activo especificado frente a eventos de impacto HIGH en Forex Factory.
        """
        now = dt or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        before_delta = timedelta(minutes=buffer_before_mins if buffer_before_mins is not None else self.default_before_mins)
        after_delta = timedelta(minutes=buffer_after_mins if buffer_after_mins is not None else self.default_after_mins)

        # 1. Comprobar blackouts manuales
        for b in self._manual_blackouts:
            start_t = b["start"] if b["start"].tzinfo else b["start"].replace(tzinfo=timezone.utc)
            end_t = b["end"] if b["end"].tzinfo else b["end"].replace(tzinfo=timezone.utc)
            if start_t <= now <= end_t:
                logger.warning(f"🛑 [NEWS_BLACKOUT] Bloqueo manual activo para {asset}: {b.get('reason', 'Intervención manual')}")
                return True

        # 2. Obtener eventos macro desde el almacén de datos (store o parámetro inyectado)
        events = store_events
        if events is None:
            try:
                from engine.core.store import store
                # Store tiene el deque en memoria sincronizado por calendar_worker
                events = list(getattr(store, "_economic_events", []))
            except Exception as e:
                logger.debug(f"[NEWS_INTERCEPTOR] Error accediendo a store: {e}")
                events = []

        # Si el store está vacío, intentar leer archivo de respaldo en disco
        if not events:
            backup_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "economic_calendar.json")
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        events = json.load(f)
                except Exception:
                    events = []

        if not events:
            # Fallback seguro: Si no hay eventos cargados, aplicar reglas estáticas de rescate
            return self._static_emergency_blackout(now, asset)

        target_currencies = self._get_relevant_currencies(asset)

        for event in events:
            # Solo eventos de alto impacto ("High") o eventos globales de la Fed / BCE
            impact = str(event.get("impact", "")).capitalize()
            if impact != "High" and not any(crit in str(event.get("title", "")).upper() for crit in ["FOMC", "FEDERAL FUNDS", "NON-FARM", "CPI"]):
                continue

            event_country = str(event.get("country", "")).upper()
            if event_country not in target_currencies and event_country != "ALL":
                continue

            date_str = event.get("date", "")
            if not date_str:
                continue

            try:
                # Parsear ISO 8601 con zona horaria
                event_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)

                # Ventana de protección: [event_dt - before_delta, event_dt + after_delta]
                window_start = event_dt - before_delta
                window_end = event_dt + after_delta

                if window_start <= now <= window_end:
                    mins_to_event = int((event_dt - now).total_seconds() / 60)
                    time_desc = f"en {mins_to_event} min" if mins_to_event >= 0 else f"hace {abs(mins_to_event)} min"
                    logger.warning(
                        f"🛡️ [NEWS_BLACKOUT SOP-92] Operación bloqueada para {asset}. "
                        f"Evento de ALTO IMPACTO: [{event_country}] {event.get('title')} ({time_desc})."
                    )
                    return True

            except Exception as parse_err:
                logger.debug(f"[NEWS_INTERCEPTOR] Error parseando fecha de evento '{date_str}': {parse_err}")
                continue

        return False

    def get_upcoming_event_threat(
        self,
        asset: str,
        lookahead_mins: int = 45,
        store_events: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retorna los detalles del próximo evento High Impact si ocurrirá dentro de `lookahead_mins`.
        Permite a centinelas de posiciones abiertas actuar defensivamente.
        """
        now = datetime.now(timezone.utc)
        events = store_events
        if events is None:
            try:
                from engine.core.store import store
                events = list(getattr(store, "_economic_events", []))
            except Exception:
                events = []

        if not events:
            return None

        target_currencies = self._get_relevant_currencies(asset)
        horizon = now + timedelta(minutes=lookahead_mins)

        for event in events:
            impact = str(event.get("impact", "")).capitalize()
            if impact != "High" and not any(crit in str(event.get("title", "")).upper() for crit in ["FOMC", "FEDERAL FUNDS", "NON-FARM", "CPI"]):
                continue

            event_country = str(event.get("country", "")).upper()
            if event_country not in target_currencies and event_country != "ALL":
                continue

            try:
                event_dt = datetime.fromisoformat(event.get("date", "").replace("Z", "+00:00"))
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)

                if now <= event_dt <= horizon:
                    mins_left = int((event_dt - now).total_seconds() / 60)
                    return {
                        "title": event.get("title"),
                        "country": event_country,
                        "impact": impact,
                        "event_dt": event_dt.isoformat(),
                        "minutes_remaining": mins_left
                    }
            except Exception:
                continue

        return None

    def _static_emergency_blackout(self, now: datetime, asset: str) -> bool:
        """Reglas heurísticas de emergencia en caso de desconexión WAN completa."""
        d = now.strftime("%A")
        h = now.hour
        m = now.minute

        # 1. Primer viernes del mes (NFP EE.UU.): 12:15 a 13:45 UTC
        if d == "Friday" and 1 <= now.day <= 7:
            if (h == 12 and m >= 15) or (h == 13 and m <= 45):
                logger.warning(f"🛑 [EMERGENCY_NEWS_SHIELD] NFP heurístico activo para {asset}.")
                return True

        # 2. Miércoles de FOMC (17:45 a 19:30 UTC) en semanas clave
        if d == "Wednesday" and (h == 18 or (h == 17 and m >= 45) or (h == 19 and m <= 30)):
            if 14 <= now.day <= 28:
                logger.warning(f"🛑 [EMERGENCY_NEWS_SHIELD] FOMC heurístico activo para {asset}.")
                return True

        return False

    def add_manual_blackout(self, start_dt: datetime, end_dt: datetime, reason: str = ""):
        """Permite inyectar ventanas de noticias imprevistas vía API o intervención externa."""
        self._manual_blackouts.append({"start": start_dt, "end": end_dt, "reason": reason})


# Instancia singleton para uso global
news_interceptor = DynamicNewsInterceptor()
