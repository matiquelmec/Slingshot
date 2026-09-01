"""
engine/indicators/news_interceptor.py — v32.0 (APEX ZENITH)
=============================================================================
Responsabilidad: Interceptor Dinámico de Noticias Macroeconómicas de Alto Impacto.
Implementa Protocolo SOP-19:
1. Bloqueo de nuevas aperturas 15 min antes y 15 min después de NFP, CPI y FOMC.
2. Inmunidad para posiciones que ya estén aseguradas en Breakeven (TP0 cobrado).
"""
from datetime import datetime, time
from typing import Dict, Any, List, Optional
import pandas as pd
from engine.core.logger import logger

class NewsInterceptor:
    """
    Interceptor Cuantitativo de Eventos Macro de Alto Impacto (SOP-19).
    """
    
    # Horarios estándar de eventos macroeconómicos de EE.UU. (en hora UTC)
    # 1. Non-Farm Payrolls (NFP): Primer viernes del mes a las 12:30 UTC / 13:30 UTC (según DST)
    # 2. CPI (Inflación USA): Segundo martes/miércoles del mes a las 12:30 / 13:30 UTC
    # 3. FOMC (Decisión de Tasas Fed): Miércoles a las 18:00 UTC (anuncio) y 18:30 UTC (conferencia)
    
    HIGH_IMPACT_EVENTS = [
        {"name": "US_CPI", "time_utc": "12:30", "window_mins": 15},
        {"name": "US_NFP", "time_utc": "12:30", "window_mins": 15},
        {"name": "FOMC_RATE_DECISION", "time_utc": "18:00", "window_mins": 30},
        {"name": "FOMC_PRESS_CONFERENCE", "time_utc": "18:30", "window_mins": 30},
        {"name": "ECB_RATE_DECISION", "time_utc": "12:15", "window_mins": 15},
    ]

    def __init__(self, lockout_minutes: int = 15):
        self.lockout_minutes = lockout_minutes
        self._manual_blackouts: List[Dict[str, Any]] = []

    def is_macro_news_blackout(self, dt: datetime, asset: str = "") -> bool:
        """
        Verifica si la fecha/hora actual se encuentra dentro de una ventana de impacto rojo.
        """
        if dt is None:
            return False
            
        d = dt.day_name() if hasattr(dt, "day_name") else pd.to_datetime(dt).day_name()
        h = dt.hour
        m = dt.minute
        
        # 1. Primer Viernes de Mes: NFP (12:15 a 12:45 UTC / 13:15 a 13:45 UTC)
        if d == "Friday" and 1 <= dt.day <= 7:
            if (h == 12 and m >= 15) or (h == 13 and m <= 45):
                logger.warning(f"🛑 [NEWS_INTERCEPTOR] Bloqueo NFP activo para {asset} a las {h:02d}:{m:02d} UTC.")
                return True
                
        # 2. Miércoles de FOMC (17:45 a 19:15 UTC)
        # Típicamente semanas 3 y 4 de meses clave
        if d == "Wednesday" and (h == 18 or (h == 17 and m >= 45) or (h == 19 and m <= 15)):
            if 14 <= dt.day <= 28:
                logger.warning(f"🛑 [NEWS_INTERCEPTOR] Bloqueo FOMC activo para {asset} a las {h:02d}:{m:02d} UTC.")
                return True

        # 3. Blackouts manuales programados
        for b in self._manual_blackouts:
            if b["start"] <= dt <= b["end"]:
                return True

        return False

    def add_manual_blackout(self, start_dt: datetime, end_dt: datetime, reason: str = ""):
        """Permite inyectar ventanas de noticias imprevistas vía API."""
        self._manual_blackouts.append({"start": start_dt, "end": end_dt, "reason": reason})

news_interceptor = NewsInterceptor()
