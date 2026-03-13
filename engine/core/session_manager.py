"""
SessionManager — Slingshot Gen 1
==================================
Gestor centralizado del estado de las sesiones de mercado.

CARACTERÍSTICAS:
- Sin base de datos: persiste el estado en engine/data/session_state.json
- DST-Aware: usa pytz para calcular horas reales de NY, Londres y Chile
- Memoria persistente: sobrevive reinicios del servidor
- Auto-rotación: detecta cambio de día UTC y rota PDH/PDL automáticamente
- Tiempo- Global Mastery: Proporciona estado de sesión independiente del símbolo
- Real-time: Actualización por tiempo y por ticks
"""

import json
import pytz
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Rutas de persistencia
# ──────────────────────────────────────────────────────────────────────────────
_STATE_FILE = Path(__file__).parent.parent / "data" / "session_state.json"

# ──────────────────────────────────────────────────────────────────────────────
# Zonas horarias (instancias únicas, no re-crear en cada llamada)
# ──────────────────────────────────────────────────────────────────────────────
_CHILE_TZ  = pytz.timezone("America/Santiago")
_NY_TZ     = pytz.timezone("America/New_York")
_LONDON_TZ = pytz.timezone("Europe/London")
_TOKYO_TZ  = pytz.timezone("Asia/Tokyo")


def _empty_session() -> dict:
    return {
        "high": None, "low": None,
        "swept_high": False, "swept_low": False,
        "prev_high": None, "prev_low": None,
    }


def _empty_state(trading_day: str = "") -> dict:
    return {
        "trading_day": trading_day,
        "asia":   _empty_session(),
        "london": _empty_session(),
        "ny":     _empty_session(),
        "pdh": None,
        "pdl": None,
        "pdh_swept": False,
        "pdl_swept": False,
    }


class SessionManager:
    """
    Fuente de verdad sobre las sesiones de mercado.

    Uso:
        sm = SessionManager()
        sm.bootstrap(history_candles)  # Opcional: cargar historial inicial
        payload = sm.update(candle)    # Llamar en cada tick

    El método update() retorna un dict listo para enviar por WebSocket.
    """

    def __init__(self, symbol: str = "GLOBAL"):
        self._symbol = symbol.upper()
        self._state: dict = self._load_or_init()

    # ──────────────────────────────────────────────────────────────────────
    # PERSISTENCIA
    # ──────────────────────────────────────────────────────────────────────
    @property
    def _state_file(self) -> Path:
        return _STATE_FILE.parent / f"session_state_{self._symbol}.json"

    def _load_or_init(self) -> dict:
        """Carga el estado desde JSON o crea uno nuevo limpio."""
        if self._state_file.exists():
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[SessionManager:{self._symbol}] 📂 Estado cargado: día={data.get('trading_day')}")
                return data
            except Exception as e:
                print(f"[SessionManager:{self._symbol}] ⚠️  No se pudo leer JSON: {e}. Nuevo estado.")
        return _empty_state()

    def _save(self):
        """Persiste el estado actual a disco."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, default=str)
        except Exception as e:
            print(f"[SessionManager:{self._symbol}] ⚠️  Error guardando: {e}")


    # ──────────────────────────────────────────────────────────────────────
    # BOOTSTRAP (Carga Inicial desde Historial)
    # ──────────────────────────────────────────────────────────────────────
    def bootstrap(self, history: list[dict]):
        """
        Procesa velas históricas para reconstruir niveles de sesión.
        Procesa AMBOS días (hoy y ayer) para tener prev_high/prev_low
        disponibles en todos los símbolos desde el primer tick.
        """
        if not history:
            return

        now_utc = datetime.now(timezone.utc)
        today   = now_utc.date()
        from datetime import timedelta
        yesterday = (now_utc - timedelta(days=1)).date()

        # ── Resetear HIGH/LOW del día actual (preservar prev_*) ──────────
        # Si el JSON cargado tiene datos de una sesión anterior en un día
        # distinto, o si queremos recalcular, limpiamos hoy para que
        # el bootstrap sea siempre la fuente de verdad.
        if self._state.get("trading_day") != str(today):
            # Día diferente: rotar prev_* manualmente antes de limpiar
            for key in ["asia", "london", "ny"]:
                old_h = self._state[key].get("high")
                old_l = self._state[key].get("low")
                if old_h is not None:
                    self._state[key]["prev_high"] = old_h
                    self._state[key]["prev_low"]  = old_l
        # Limpiar high/low de HOY para que el bootstrap recalcule desde cero
        for key in ["asia", "london", "ny"]:
            self._state[key]["high"] = None
            self._state[key]["low"]  = None
            self._state[key]["swept_high"] = False
            self._state[key]["swept_low"]  = False
        self._state["trading_day"] = str(today)

        pdh_candidates = []
        pdl_candidates = []

        # Acumuladores para los niveles prev (día anterior por sesión)
        prev = {"asia": {"high": None, "low": None},
                "london": {"high": None, "low": None},
                "ny":     {"high": None, "low": None}}

        for candle in history:
            ts    = datetime.fromtimestamp(candle["timestamp"], tz=timezone.utc)
            day   = ts.date()
            high  = float(candle["high"])
            low   = float(candle["low"])

            ny_hour  = ts.astimezone(_NY_TZ).hour
            lon_hour = ts.astimezone(_LONDON_TZ).hour
            utc_hour = ts.hour

            # Velas de AYER → prev_high/prev_low por sesión + PDH/PDL
            if day == yesterday:
                pdh_candidates.append(high)
                pdl_candidates.append(low)

                if 0 <= utc_hour < 6:
                    p = prev["asia"]
                    p["high"] = max(p["high"], high) if p["high"] is not None else high
                    p["low"]  = min(p["low"],  low)  if p["low"]  is not None else low
                if 8 <= lon_hour < 16:
                    p = prev["london"]
                    p["high"] = max(p["high"], high) if p["high"] is not None else high
                    p["low"]  = min(p["low"],  low)  if p["low"]  is not None else low
                if 8 <= ny_hour < 16:
                    p = prev["ny"]
                    p["high"] = max(p["high"], high) if p["high"] is not None else high
                    p["low"]  = min(p["low"],  low)  if p["low"]  is not None else low

            # Velas de HOY → sesión actual
            if day != today:
                continue

            if 0 <= utc_hour < 6:
                s = self._state["asia"]
                s["high"] = max(s["high"], high) if s["high"] is not None else high
                s["low"]  = min(s["low"],  low)  if s["low"]  is not None else low

            if 8 <= lon_hour < 16:
                s = self._state["london"]
                s["high"] = max(s["high"], high) if s["high"] is not None else high
                s["low"]  = min(s["low"],  low)  if s["low"]  is not None else low

            if 8 <= ny_hour < 16:
                s = self._state["ny"]
                s["high"] = max(s["high"], high) if s["high"] is not None else high
                s["low"]  = min(s["low"],  low)  if s["low"]  is not None else low

        # Aplicar PDH/PDL
        if pdh_candidates:
            self._state["pdh"] = max(pdh_candidates)
            self._state["pdl"] = min(pdl_candidates)

        # Aplicar prev_high/prev_low a cada sesión (referencia del día anterior)
        for key in ["asia", "london", "ny"]:
            if prev[key]["high"] is not None:
                self._state[key]["prev_high"] = prev[key]["high"]
                self._state[key]["prev_low"]  = prev[key]["low"]

        self._state["trading_day"] = str(today)
        self._save()
        print(f"[SessionManager] ✅ Bootstrap OK: día={today} | PDH={self._state['pdh']} | "
              f"London prev={self._state['london'].get('prev_high')} | NY prev={self._state['ny'].get('prev_high')}")

    # ──────────────────────────────────────────────────────────────────────
    # UPDATE (Tick a Tick)
    # ──────────────────────────────────────────────────────────────────────
    def update(self, candle: dict, is_closed: bool = False) -> dict:
        """
        Actualiza el estado de las sesiones con la vela más reciente y
        retorna el payload completo listo para enviar por WebSocket.

        Args:
            candle: dict con {"timestamp": float, "high": float, "low": float, ...}
            is_closed: True si la vela ya cerró (para guardar en disco solo entonces)
        """
        ts      = datetime.fromtimestamp(candle["timestamp"], tz=timezone.utc)
        today   = ts.date()
        high    = float(candle["high"])
        low     = float(candle["low"])

        # ── Rotación de Día ──────────────────────────────────────────────
        if str(today) != self._state.get("trading_day"):
            print(f"[SessionManager] 🗓  Nuevo día: {today}. Rotando PDH/PDL...")
            old_asia   = self._state.get("asia",   {})
            old_london = self._state.get("london", {})
            old_ny     = self._state.get("ny",     {})

            highs = [v for v in [old_asia.get("high"), old_london.get("high"), old_ny.get("high")] if v is not None]
            lows  = [v for v in [old_asia.get("low"),  old_london.get("low"),  old_ny.get("low")]  if v is not None]

            new_state = _empty_state(str(today))
            if highs:
                new_state["pdh"] = max(highs)
                new_state["pdl"] = min(lows)
            # Rotar prev_high/prev_low: lo de hoy pasa a ser el "anterior" del nuevo día
            for key in ["asia", "london", "ny"]:
                old = self._state.get(key, {})
                if old.get("high") is not None:
                    new_state[key]["prev_high"] = old["high"]
                    new_state[key]["prev_low"]  = old["low"]

            self._state = new_state
            self._save()

        # ── Actualizar niveles de la sesión activa ────────────────────────
        ny_hour  = ts.astimezone(_NY_TZ).hour
        lon_hour = ts.astimezone(_LONDON_TZ).hour
        utc_hour = ts.hour

        def _update_session(key: str, is_active: bool):
            if not is_active:
                return
            s = self._state[key]
            h = s.get("high")
            l = s.get("low")
            s["high"] = max(h, high) if h is not None else high
            s["low"]  = min(l, low)  if l is not None else low

        _update_session("asia",   0 <= utc_hour < 6)
        _update_session("london", 8 <= lon_hour < 16)
        _update_session("ny",     8 <= ny_hour < 16)

        # ── Detección de Sweeps ───────────────────────────────────────────
        pdh = self._state.get("pdh")
        pdl = self._state.get("pdl")
        if pdh is not None:
            self._state["pdh_swept"] = bool(high > pdh)
            self._state["pdl_swept"] = bool(low  < pdl)

        for key in ["asia", "london", "ny"]:
            s    = self._state[key]
            kh   = s.get("high")
            kl   = s.get("low")
            s["swept_high"] = bool(kh is not None and high > kh)
            s["swept_low"]  = bool(kl is not None and low  < kl)

        # Guardar en disco solo cuando la vela cierra (no en cada micro-tick)
        if is_closed:
            self._save()

        return self._build_payload(ts)

    # ──────────────────────────────────────────────────────────────────────
    # PAYLOAD PARA WEBSOCKET
    # ──────────────────────────────────────────────────────────────────────
    def _build_payload(self, now_utc: datetime) -> dict:
        """Construye el dict completo de sesiones listo para el FrontEnd."""
        now_chile  = now_utc.astimezone(_CHILE_TZ)
        now_ny     = now_utc.astimezone(_NY_TZ)
        now_lon    = now_utc.astimezone(_LONDON_TZ)
        now_tokyo  = now_utc.astimezone(_TOKYO_TZ)

        utc_hour   = now_utc.hour
        ny_hour    = now_ny.hour
        lon_hour   = now_lon.hour
        tokyo_hour = now_tokyo.hour

        # ── Horarios de apertura/cierre de cada sesión en hora Chile ──────
        def _to_chile_str(utc_h: int, utc_m: int = 0) -> str:
            """Convierte una hora UTC (hoy) a string en hora de Santiago."""
            dt_utc    = now_utc.replace(hour=utc_h % 24, minute=utc_m, second=0, microsecond=0)
            dt_chile  = dt_utc.astimezone(_CHILE_TZ)
            return dt_chile.strftime("%H:%M")

        # Offsets DST reales de cada zona
        tok_off = int(now_tokyo.utcoffset().total_seconds() / 3600)
        lon_off = int(now_lon.utcoffset().total_seconds()   / 3600)
        ny_off  = int(now_ny.utcoffset().total_seconds()    / 3600)

        asia_start_utc = 0          # Siempre medianoche UTC (proxy estable)
        asia_end_utc   = 6
        lon_start_utc  = 8  - lon_off
        lon_end_utc    = 16 - lon_off
        ny_start_utc   = 8  - ny_off
        ny_end_utc     = 16 - ny_off

        sessions_info = {
            "asia": {
                **self._state["asia"],
                "start_utc":   asia_start_utc,
                "end_utc":     asia_end_utc,
                "open_chile":  _to_chile_str(asia_start_utc),
                "close_chile": _to_chile_str(asia_end_utc),
                "status":      "ACTIVE" if asia_start_utc <= utc_hour < asia_end_utc else "CLOSED",
            },
            "london": {
                **self._state["london"],
                "start_utc":   lon_start_utc,
                "end_utc":     lon_end_utc,
                "open_chile":  _to_chile_str(lon_start_utc),
                "close_chile": _to_chile_str(lon_end_utc),
                "status":      "ACTIVE" if lon_start_utc <= utc_hour < lon_end_utc
                               else ("PENDING" if utc_hour < lon_start_utc else "CLOSED"),
            },
            "ny": {
                **self._state["ny"],
                "start_utc":   ny_start_utc,
                "end_utc":     ny_end_utc,
                "open_chile":  _to_chile_str(ny_start_utc),
                "close_chile": _to_chile_str(ny_end_utc),
                "status":      "ACTIVE" if ny_start_utc <= utc_hour < ny_end_utc
                               else ("PENDING" if utc_hour < ny_start_utc else "CLOSED"),
            },
        }

        # ── Sesión activa ─────────────────────────────────────────────────
        if 9 <= tokyo_hour < 15:
            session_name, is_killzone = "ASIA", False
        elif 8 <= lon_hour < 11:
            session_name, is_killzone = "LONDON_KILLZONE", True
        elif 11 <= lon_hour < 16 and ny_hour < 8:
            session_name, is_killzone = "LONDON", False
        elif 8 <= ny_hour < 11:
            session_name, is_killzone = "NY_KILLZONE", True
        elif 11 <= ny_hour < 16:
            session_name, is_killzone = "NEW_YORK", False
        else:
            session_name, is_killzone = "OFF_HOURS", False

        return {
            "type": "session_update",
            "data": {
                "current_session":     session_name,
                "current_session_utc": now_utc.strftime("%H:%M UTC"),
                "local_time":          now_chile.strftime("%H:%M Chile"),
                "is_killzone":         is_killzone,
                "sessions":            sessions_info,
                "pdh":       self._state.get("pdh"),
                "pdl":       self._state.get("pdl"),
                "pdh_swept": self._state.get("pdh_swept", False),
                "pdl_swept": self._state.get("pdl_swept", False),
                "trading_day": self._state.get("trading_day"),
            }
        }

    def get_current_state(self) -> dict:
        """Retorna el estado actual de sesiones sin necesitar un candle nuevo."""
        now_utc = datetime.now(timezone.utc)
        return self._build_payload(now_utc)

    # ──────────────────────────────────────────────────────────────────────
    # GLOBAL SESSION MASTERY (v2)
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_global_session_status() -> dict:
        """
        Calcula el estado de las sesiones basado ÚNICAMENTE en el tiempo.
        Ideal para el Orchestrator para broadcast global.
        """
        now_utc = datetime.now(timezone.utc)
        now_ny  = now_utc.astimezone(_NY_TZ)
        now_lon = now_utc.astimezone(_LONDON_TZ)
        now_tokyo = now_utc.astimezone(_TOKYO_TZ)

        ny_hour  = now_ny.hour
        lon_hour = now_lon.hour
        tok_hour = now_tokyo.hour

        # Detección de sesión activa
        if 9 <= tok_hour < 15:
            session_name, is_killzone = "ASIA", False
        elif 8 <= lon_hour < 11:
            session_name, is_killzone = "LONDON_KILLZONE", True
        elif 11 <= lon_hour < 16 and ny_hour < 8:
            session_name, is_killzone = "LONDON", False
        elif 8 <= ny_hour < 11:
            session_name, is_killzone = "NY_KILLZONE", True
        elif 11 <= ny_hour < 16:
            session_name, is_killzone = "NEW_YORK", False
        else:
            session_name, is_killzone = "OFF_HOURS", False

        return {
            "current_session": session_name,
            "is_killzone": is_killzone,
            "local_time_ny": now_ny.strftime("%H:%M"),
            "local_time_lon": now_lon.strftime("%H:%M"),
            "local_time_chile": now_utc.astimezone(_CHILE_TZ).strftime("%H:%M"),
            "timestamp_utc": now_utc.timestamp()
        }


# ──────────────────────────────────────────────────────────────────────────────
# Instancia global singleton (se importa desde main.py)
# ──────────────────────────────────────────────────────────────────────────────
session_manager = SessionManager()
