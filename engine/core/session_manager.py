"""
SessionManager — Slingshot Gen 1
==================================
Gestor centralizado del estado de las sesiones de mercado.

CARACTERÍSTICAS:
- Sin base de datos: persiste el estado en engine/data/session_state.json
- DST-Aware: usa zoneinfo para calcular horas reales de NY, Londres y Chile
- Memoria persistente: sobrevive reinicios del servidor
- Auto-rotación: detecta cambio de día UTC y rota PDH/PDL automáticamente
- Tiempo- Global Mastery: Proporciona estado de sesión independiente del símbolo
- Real-time: Actualización por tiempo y por ticks
"""

from engine.core.logger import logger
import json
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional, Any


# ──────────────────────────────────────────────────────────────────────────────
# Rutas de persistencia
# ──────────────────────────────────────────────────────────────────────────────
_STATE_FILE = Path(__file__).parent.parent / "data" / "session_state.json"

# ──────────────────────────────────────────────────────────────────────────────
# Zonas horarias (instancias únicas, no re-crear en cada llamada)
# ──────────────────────────────────────────────────────────────────────────────
_CHILE_TZ  = ZoneInfo("America/Santiago")
_NY_TZ     = ZoneInfo("America/New_York")
_LONDON_TZ = ZoneInfo("Europe/London")
_TOKYO_TZ  = ZoneInfo("Asia/Tokyo")
_FRA_TZ    = ZoneInfo("Europe/Berlin") # Frankfurt

# --- GLOBAL SESSION CACHE v5.7.156 (Bootstrap Sync) ---
# Almacena el resultado del bootstrap por símbolo para que se haga solo una vez
# por cada moneda en el arranque, sin importar cuántos intervalos se usen.
_BOOTSTRAP_MEMO = {} # symbol -> state_data_snapshot


def _empty_session() -> dict:
    return {
        "high": None, "low": None,
        "swept_high": False, "swept_low": False,
        "prev_high": None, "prev_low": None,
    }


def _empty_state(trading_day: str = "") -> dict:
    return {
        "trading_day": trading_day,
        "trades_today": 0, # CAP DE SESIÓN v5.0 (Máximo 3 trades diarios)
        "asia":   _empty_session(),
        "london": _empty_session(),
        "ny":     _empty_session(),
        "pdh": None,
        "pdl": None,
        "pdh_swept": False,
        "pdl_swept": False,
        "onh": None, # Overnight High (Yosh)
        "onl": None, # Overnight Low (Yosh)
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
                logger.info(f"[SessionManager:{self._symbol}] 📂 Estado cargado: día={data.get('trading_day')}")
                return data
            except Exception as e:
                logger.info(f"[SessionManager:{self._symbol}] ⚠️  No se pudo leer JSON: {e}. Nuevo estado.")
        return _empty_state()

    def _save(self):
        """Persiste el estado actual a disco."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"[SessionManager:{self._symbol}] ⚠️  Error guardando: {e}")


    # ──────────────────────────────────────────────────────────────────────
    # BOOTSTRAP (Carga Inicial desde Historial)
    # ──────────────────────────────────────────────────────────────────────
    def bootstrap(self, history: list[dict]):
        """
        Procesa velas históricas para reconstruir niveles de sesión.
        Optimización v5.7.156: Si otro Broadcaster ya calculó este activo hoy, cargarlo de la memoria global.
        """
        if not history:
            return

        now_utc = datetime.now(timezone.utc)
        today_str = str(now_utc.date())

        # ✅ FAST CACHE: Evitar re-calculo si ya lo hicimos para este símbolo hace menos de 1h
        if self._symbol in _BOOTSTRAP_MEMO:
            cached_day, cached_state = _BOOTSTRAP_MEMO[self._symbol]
            if cached_day == today_str:
                logger.info(f"[SessionManager:{self._symbol}] ♻️  Reutilizando Bootstrap Global (Sincronización v5.7.156)")
                
                # Verificación de integridad: asegurar que el asset en el estado coincide
                for k, v in cached_state.items():
                    if k != "trades_today":
                        self._state[k] = v
                
                self._state["trading_day"] = today_str
                # Asegurar que el asset en el payload sea el correcto
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
        self._state["onh"] = None
        self._state["onl"] = None
        self._state["trading_day"] = str(today)

        pdh_candidates = []
        pdl_candidates = []

        # Acumuladores para los niveles prev (día anterior por sesión)
        prev = {"asia": {"high": None, "low": None},
                "london": {"high": None, "low": None},
                "ny":     {"high": None, "low": None}}

        for item in history:
            candle = item.get("data", item) if isinstance(item, dict) else item
            if not isinstance(candle, dict) or "timestamp" not in candle:
                continue

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
                if 9 <= ny_hour < 16: # NY RTH (Yosh Standard)
                    p = prev["ny"]
                    p["high"] = max(p["high"], high) if p["high"] is not None else high
                    p["low"]  = min(p["low"],  low)  if p["low"]  is not None else low

                # 🌙 YOSH OVERNIGHT (Velas de ayer 21:00 - 23:59)
                if ny_hour >= 21:
                    oh = self._state.get("onh")
                    ol = self._state.get("onl")
                    self._state["onh"] = max(oh, high) if oh is not None else high
                    self._state["onl"] = min(ol, low)  if ol is not None else low

            # Velas de HOY → sesión actual
            if day != today:
                continue

            tok_hour = ts.astimezone(_TOKYO_TZ).hour
            if 9 <= tok_hour < 15: # ASIA (Tokyo Standard)
                s = self._state["asia"]
                s["high"] = max(s["high"], high) if s["high"] is not None else high
                s["low"]  = min(s["low"],  low)  if s["low"]  is not None else low

            if 8 <= lon_hour < 16:
                s = self._state["london"]
                s["high"] = max(s["high"], high) if s["high"] is not None else high
                s["low"]  = min(s["low"],  low)  if s["low"]  is not None else low

            if 9 <= ny_hour < 16: # NY RTH (Yosh Standard)
                s = self._state["ny"]
                s["high"] = max(s["high"], high) if s["high"] is not None else high
                s["low"]  = min(s["low"],  low)  if s["low"]  is not None else low

            # ── 🌙 YOSH OVERNIGHT RANGE (HOY 00:00 - 09:29 EST) ──
            is_overnight = False
            if ny_hour < 9:
                is_overnight = True
            elif ny_hour == 9 and ts.astimezone(_NY_TZ).minute < 30:
                is_overnight = True

            if is_overnight:
                oh = self._state.get("onh")
                ol = self._state.get("onl")
                self._state["onh"] = max(oh, high) if oh is not None else high
                self._state["onl"] = min(ol, low)  if ol is not None else low

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
        
        # ✅ PERSISTIR EN CACHÉ GLOBAL (v5.7.156)
        _BOOTSTRAP_MEMO[self._symbol] = (str(today), self._state.copy())
        
        self._save()
        logger.info(f"[SessionManager:{self._symbol}] ✅ Bootstrap OK: día={today} | PDH={self._state.get('pdh')} | "
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
        # Robustez: soporta {"type": "candle", "data": {...}} o el dict plano
        data = candle.get("data", candle) if isinstance(candle, dict) else candle
        
        ts      = datetime.fromtimestamp(data["timestamp"], tz=timezone.utc)
        today   = ts.date()
        high    = float(data["high"])
        low     = float(data["low"])

        # ── Rotación de Día ──────────────────────────────────────────────
        if str(today) != self._state.get("trading_day"):
            logger.info(f"[SessionManager] 🗓  Nuevo día: {today}. Rotando PDH/PDL...")
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
        tok_hour = ts.astimezone(_TOKYO_TZ).hour
        fra_hour = ts.astimezone(_FRA_TZ).hour

        def _update_session(key: str, is_active: bool):
            if not is_active:
                return
            s = self._state[key]
            h = s.get("high")
            l = s.get("low")
            s["high"] = max(h, high) if h is not None else high
            s["low"]  = min(l, low)  if l is not None else low

        _update_session("asia",   9 <= tok_hour < 15)
        _update_session("london", 8 <= lon_hour < 16)
        _update_session("ny",     9 <= ny_hour < 16) # NY RTH (Yosh Standard)

        # ── 🌙 YOSH OVERNIGHT RANGE UPDATE ──
        ny_time = ts.astimezone(_NY_TZ)
        is_overnight = (ny_time.hour >= 21) or (ny_time.hour < 9) or (ny_time.hour == 9 and ny_time.minute < 30)

        if is_overnight:
            oh = self._state.get("onh")
            ol = self._state.get("onl")
            self._state["onh"] = max(oh, high) if oh is not None else high
            self._state["onl"] = min(ol, low)  if ol is not None else low

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

    # ── GESTIÓN DE CAP DE SESIÓN v5.0 ───────────────────────────────────────────
    def get_trades_today(self) -> int:
        """Retorna el contador de ejecuciones del día actual."""
        return self._state.get("trades_today", 0)

    def increment_trades(self):
        """Aumenta el contador de trades y persiste el cambio."""
        self._state["trades_today"] = self.get_trades_today() + 1
        self._save()
        logger.info(f"[SessionManager] 📊 Trade ejecutado en {self._symbol}. Contador: {self.get_trades_today()}")

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
                "high":        float(self._state["asia"]["high"]) if self._state["asia"]["high"] is not None else None,
                "low":         float(self._state["asia"]["low"]) if self._state["asia"]["low"] is not None else None,
                "prev_high":   float(self._state["asia"]["prev_high"]) if self._state["asia"]["prev_high"] is not None else None,
                "prev_low":    float(self._state["asia"]["prev_low"]) if self._state["asia"]["prev_low"] is not None else None,
                "start_utc":   int(asia_start_utc),
                "end_utc":     int(asia_end_utc),
                "open_chile":  _to_chile_str(asia_start_utc),
                "close_chile": _to_chile_str(asia_end_utc),
                "status":      "ACTIVE" if 9 <= tokyo_hour < 15 else ("PENDING" if tokyo_hour < 9 else "CLOSED"),
            },
            "london": {
                "high":        float(self._state["london"]["high"]) if self._state["london"]["high"] is not None else None,
                "low":         float(self._state["london"]["low"]) if self._state["london"]["low"] is not None else None,
                "prev_high":   float(self._state["london"]["prev_high"]) if self._state["london"]["prev_high"] is not None else None,
                "prev_low":    float(self._state["london"]["prev_low"]) if self._state["london"]["prev_low"] is not None else None,
                "start_utc":   int(lon_start_utc),
                "end_utc":     int(lon_end_utc),
                "open_chile":  _to_chile_str(lon_start_utc),
                "close_chile": _to_chile_str(lon_end_utc),
                "status":      "ACTIVE" if 8 <= lon_hour < 16 else ("PENDING" if lon_hour < 8 else "CLOSED"),
            },
            "ny": {
                "high":        float(self._state["ny"]["high"]) if self._state["ny"]["high"] is not None else None,
                "low":         float(self._state["ny"]["low"]) if self._state["ny"]["low"] is not None else None,
                "prev_high":   float(self._state["ny"]["prev_high"]) if self._state["ny"]["prev_high"] is not None else None,
                "prev_low":    float(self._state["ny"]["prev_low"]) if self._state["ny"]["prev_low"] is not None else None,
                "start_utc":   int(ny_start_utc),
                "end_utc":     int(ny_end_utc),
                "open_chile":  _to_chile_str(ny_start_utc),
                "close_chile": _to_chile_str(ny_end_utc),
                "status":      "ACTIVE" if 8 <= ny_hour < 16 else ("PENDING" if ny_hour < 8 else "CLOSED"),
            },
        }

        # ── Sesión activa (v8.8.0 Institutional Precision) ─────────────────
        is_silver_bullet = False
        is_overlap = False
        is_killzone = False
        
        # 1. Definir Sesión Base
        if 9 <= tokyo_hour < 15:
            session_name = "ASIA"
        elif 8 <= lon_hour < 16 and ny_hour < 8:
            session_name = "LONDON"
        elif 8 <= ny_hour < 16:
            session_name = "NEW_YORK"
        else:
            session_name = "OFF_HOURS"

        # 2. Refinar con Killzones y Overlaps
        if 8 <= lon_hour < 11:
            session_name = "LONDON_KILLZONE"
            is_killzone = True
        
        if 8 <= ny_hour < 11:
            if session_name == "LONDON_KILLZONE" or lon_hour >= 8:
                session_name = "LONDON_NY_OVERLAP"
            else:
                session_name = "NY_KILLZONE"
            is_killzone = True
            is_overlap = True

        # Silver Bullets (SMC Standard)
        if (10 <= ny_hour < 11) or (14 <= ny_hour < 15):
            is_silver_bullet = True
            if ny_hour >= 14: session_name = "NY_SILVER_BULLET_PM"

        # Frankfurt Pre-Open (Berlin TZ Accuracy)
        fra_hour = now_utc.astimezone(_FRA_TZ).hour
        if 7 <= fra_hour < 8:
            session_name = "FRANKFURT_OPEN"
            is_killzone = True

        # ── 🎯 YOSH EXECUTION WINDOW (10:00 - 11:30 AM EST) ──
        # Ventana de máxima probabilidad tras los primeros 30 min de "price discovery"
        yosh_window = False
        if 10 <= ny_hour <= 11:
            if ny_hour == 10:
                yosh_window = True
            elif ny_hour == 11 and now_ny.minute <= 30:
                yosh_window = True

        return {
            "type": "session_update",
            "data": {
                "asset":               str(self._symbol),
                "current_session":     str(session_name),
                "current_session_utc": now_utc.strftime("%H:%M UTC"),
                "local_time":          now_chile.strftime("%H:%M Chile"),
                "local_time_ny":       now_ny.strftime("%H:%M"),
                "local_time_lon":      now_lon.strftime("%H:%M"),
                "is_killzone":         bool(is_killzone),
                "is_silver_bullet":    bool(is_silver_bullet),
                "is_overlap":          bool(is_overlap),
                "sessions":            sessions_info,
                "pdh":       float(self._state.get("pdh")) if self._state.get("pdh") is not None else None,
                "pdl":       float(self._state.get("pdl")) if self._state.get("pdl") is not None else None,
                "pdh_swept": bool(self._state.get("pdh_swept", False)),
                "pdl_swept": bool(self._state.get("pdl_swept", False)),
                "onh":       float(self._state.get("onh")) if self._state.get("onh") is not None else None,
                "onl":       float(self._state.get("onl")) if self._state.get("onl") is not None else None,
                "yosh_window": bool(yosh_window),
                "trading_day": str(self._state.get("trading_day")),
            }
        }

    def get_current_state(self) -> dict:
        """Retorna el estado actual de sesiones sin necesitar un candle nuevo."""
        now_utc = datetime.now(timezone.utc)
        return self._build_payload(now_utc)

    def is_killzone_active(self) -> bool:
        """Sincronía Maestro: Verifica si el tiempo actual gatilla una Killzone Institucional."""
        now_utc = datetime.now(timezone.utc)
        ny_hour  = now_utc.astimezone(_NY_TZ).hour
        lon_hour = now_utc.astimezone(_LONDON_TZ).hour
        # Londres: 8-11 AM | NY: 8-11 AM
        return (8 <= lon_hour < 11) or (8 <= ny_hour < 11)

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

        # Detección de sesión activa (v8.8.0 Sync)
        is_silver_bullet = False
        is_overlap = False
        
        if 9 <= tok_hour < 15:
            session_name, is_killzone = "ASIA", False
        elif 7 <= lon_hour < 8:
            session_name, is_killzone = "FRANKFURT_OPEN", True
        elif 8 <= lon_hour < 11:
            session_name, is_killzone = "LONDON_KILLZONE", True
        elif 8 <= ny_hour < 11:
            session_name, is_killzone = "LONDON_NY_OVERLAP", True
            is_overlap = True
        elif 11 <= ny_hour < 16:
            if 14 <= ny_hour < 15:
                session_name, is_killzone, is_silver_bullet = "NY_SILVER_BULLET_PM", True, True
            else:
                session_name, is_killzone = "NEW_YORK", False
        else:
            session_name, is_killzone = "OFF_HOURS", False

        return {
            "current_session": session_name,
            "is_killzone": is_killzone,
            "is_silver_bullet": is_silver_bullet,
            "is_overlap": is_overlap,
            "local_time_ny": now_ny.strftime("%H:%M"),
            "local_time_lon": now_lon.strftime("%H:%M"),
            "local_time_chile": now_utc.astimezone(_CHILE_TZ).strftime("%H:%M"),
            "timestamp_utc": now_utc.timestamp()
        }


# ──────────────────────────────────────────────────────────────────────────────
# TimeFilter (Helper para estrategias SMC)
# ──────────────────────────────────────────────────────────────────────────────
class TimeFilter:
    """
    Versión simplificada para chequeos rápidos en DataFrames.
    Implementa las KillZones de Londres y Nueva York.
    """
    def is_killzone(self, ts: Any) -> bool:
        # OMEGA FIX: Convertir float/int a datetime si es necesario (Delta Sync)
        if isinstance(ts, (float, int)):
            try:
                ts = datetime.fromtimestamp(ts, tz=timezone.utc)
            except:
                return False
                
        # Guarda contra NaT (Trident Audit v5.7.15)
        try:
            if ts is None or (hasattr(ts, 'year') and str(ts) == 'NaT'):
                return False
        except (ValueError, TypeError):
            return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
            
        ny_hour = ts.astimezone(_NY_TZ).hour
        lon_hour = ts.astimezone(_LONDON_TZ).hour
        
        # LONDON KILLZONE: 08:00 - 11:00 AM Local
        if 8 <= lon_hour < 11:
            return True
        # NY KILLZONE: 08:00 - 11:00 AM Local
        if 8 <= ny_hour < 11:
            return True
        return False

# Instancia global singleton
session_manager = SessionManager()
