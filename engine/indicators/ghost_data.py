"""
Nivel 1: Filtro Macro & Ghost Data  (Paul Perdices Pipeline)
============================================================
Integra "Datos Fantasma" del ecosistema cripto que los traders retail
ignoran pero que los institucionales monitorizan en tiempo real:

  • Fear & Greed Index   → sentimiento del mercado (alternative.me, gratis)
  • BTC Dominance        → flujo de capital hacia alts (CoinGecko, gratis)
  • Funding Rates        → presión de derivados / shorts vs longs (Binance)
  • Noticias alto impacto → eventos con tokens de CryptoPanic

Filosofía: si el contexto macro es adverso → BLOQUEAR señales en esa dirección.
Nunca entra en LONG si el mercado tiene miedo extremo + funding negativo.
"""

from engine.core.logger import logger
import os
import asyncio
import time
import httpx
import json
import pandas as pd  # v8.5.7: Requerido para pd.to_datetime en eventos económicos
from dataclasses import dataclass
from typing import Optional, List, Tuple

# Importaciones de Dominio (v4.0)
from engine.indicators.macro import MacroState, get_macro_context
from pathlib import Path
from dataclasses import field, asdict

# ── Credenciales ────────────────────────────────────────────────────────────
CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
BINANCE_BASE    = "https://api.binance.com"
COINGECKO_BASE  = "https://api.coingecko.com/api/v3"
FNG_BASE        = "https://api.alternative.me"


# ── Estructuras de datos ─────────────────────────────────────────────────────
@dataclass
class GhostState:
    """Snapshot del estado macro del mercado."""
    # Fear & Greed
    fear_greed_value: int           = 50      # 0=Miedo Extremo, 100=Codicia Extrema
    fear_greed_label: str           = "Neutral"

    # BTC Dominance
    btc_dominance: float            = 50.0    # Porcentaje (%)

    # Funding Rate del activo objetivo (ej: BTCUSDT perpetual)
    funding_rate: float             = 0.0     # Porcentaje ej: 0.01 = 0.01%
    funding_symbol: str             = "BTCUSDT"

    # Señal macro resultante
    macro_bias: str                 = "NEUTRAL"   # BULLISH / BEARISH / NEUTRAL / BLOCK_LONGS / BLOCK_SHORTS
    block_longs: bool               = False
    block_shorts: bool              = False
    reason: str                     = "Sin datos macro disponibles."

    # Capa 1 v4.0: Contexto Global
    dxy_trend: str                  = "NEUTRAL"   # BULLISH / BEARISH / NEUTRAL
    dxy_price: float                = 0.0         # Precio exacto del DXY
    nasdaq_trend: str               = "NEUTRAL"   # BULLISH / BEARISH / NEUTRAL
    nasdaq_change_pct: float        = 0.0         # % cambio del NASDAQ
    risk_appetite: str              = "NEUTRAL"   # RISK_ON / RISK_OFF / NEUTRAL

    # Capa 2 v5.7.155 Master Gold: Narrativa & Sentimiento
    news_sentiment: float           = 0.5         # 0.0 (Bearish) a 1.0 (Bullish)
    active_event: str               = ""          # Nombre del evento macro dominante
    
    # Metadata de frescura del caché
    last_updated: float             = 0.0
    is_stale: bool                  = True


# ── Cache & Persistencia en memoria ──────────────────────────────────────────
_cache: GhostState = GhostState()
_TTL_SECONDS = 300   # 5 minutos (v5.7.156 Optimization)
_STATE_FILE = Path(__file__).parent.parent / "data" / "macro_state.json"


def is_cache_fresh() -> bool:
    """Verifica si el caché en RAM es reciente."""
    return (time.time() - _cache.last_updated) < _TTL_SECONDS


def load_local_state():
    """Carga el último estado guardado en disco al arrancar el motor."""
    global _cache
    if _STATE_FILE.exists():
        try:
            with open(_STATE_FILE, 'r') as f:
                data = json.load(f)
                # Filtrar solo los campos que existen en la dataclass
                valid_fields = {k: v for k, v in data.items() if k in GhostState.__dataclass_fields__}
                _cache = GhostState(**valid_fields)
                logger.info(f"[GHOST] 💾 Estado local cargado (F&G={_cache.fear_greed_value})")
        except Exception as e:
            logger.error(f"[GHOST] ⚠️ Error cargando estado previo: {e}")


def save_local_state(state: GhostState):
    """Persiste el estado en disco para evitar 'fallbacks' al reiniciar."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE_FILE, 'w') as f:
            json.dump(asdict(state), f, indent=2)
    except Exception as e:
        logger.error(f"[GHOST] ⚠️ Error guardando estado en disco: {e}")


# ── Fetchers individuales ─────────────────────────────────────────────────────
async def _fetch_fear_greed() -> tuple[int, str]:
    """
    Fear & Greed Index de alternative.me
    API pública, sin key. Límite: ~1 req/minuto.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{FNG_BASE}/fng/?limit=1&format=json")
            r.raise_for_status()
            data = r.json()["data"][0]
            return int(data["value"]), data["value_classification"]
    except Exception as e:
        logger.error(f"[GHOST] ⚠️  Fear & Greed fetch error: {e}")
        return 50, "Neutral"


async def _fetch_btc_dominance() -> float:
    """
    BTC Dominance desde CoinGecko /global.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{COINGECKO_BASE}/global")
            r.raise_for_status()
            pct = r.json()["data"]["market_cap_percentage"]["btc"]
            return round(float(pct), 2)
    except Exception as e:
        logger.error(f"[GHOST] ⚠️  BTC Dominance fetch error: {e}")
        return 50.0


async def fetch_funding_rate(symbol: str = "BTCUSDT") -> float:
    """
    Última tasa de financiación del perpetual en Binance Futures.
    v8.5.7: Usa /fapi/v1/fundingRate (más estable que premiumIndex) + Mirror Failover.
    """
    if symbol.upper() in ["USDCUSDT", "EURUSDT"]:
        return 0.0

    # Lista de mirrors para máxima resiliencia
    mirrors = [
        "https://fapi.binance.com/fapi/v1/fundingRate",
        "https://fapi1.binance.com/fapi/v1/fundingRate",
        "https://fapi2.binance.com/fapi/v1/fundingRate"
    ]
    
    for url in mirrors:
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                r = await client.get(url, params={"symbol": symbol.upper(), "limit": 1})
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and len(data) > 0:
                        # Usar el último elemento para asegurar que es el más reciente
                        rate = float(data[-1].get("fundingRate", 0)) * 100
                        logger.debug(f"[GHOST] Funding {symbol} fetched: {rate:.6f}% from {url}")
                        return rate
                else:
                    logger.debug(f"[GHOST] Mirror {url} returned status {r.status_code}")
        except Exception as e:
            logger.debug(f"[GHOST] Mirror {url} error: {e}")
            continue
            
    return 0.0


# ── Lógica de filtrado macro ──────────────────────────────────────────────────
def _compute_bias(
    fng: int, 
    btcd: float, 
    funding: float, 
    dxy: str = "NEUTRAL", 
    nasdaq: str = "NEUTRAL",
    news_sentiment: float = 0.5,
    active_event: str = ""
) -> tuple[str, bool, bool, str]:
    """
    Determina el sesgo macro y si se deben bloquear señales LONG o SHORT.
    Incorpora Capa 1: DXY y NASDAQ v4.0.
    """
    reasons = []
    block_longs = False
    block_shorts = False

    # 💠 Reglas Institucionales v4.0 (Capa 1)
    if dxy == "BULLISH":
        reasons.append("DXY Alcista: Presión vendedora global")
        if fng < 40: block_longs = True
    
    if nasdaq == "BEARISH":
        reasons.append("NASDAQ Bajista: Risk-Off")
        if funding > 0.05: block_shorts = False # Permitir shorts si hay euforia en caída

    # 💠 Reglas de Narrativa v5.7.155 Master Gold (Persistence Layer)
    if active_event:
        if news_sentiment < 0.4:
            block_longs = True
            reasons.append(f"SENTIMIENTO BAJISTA RECIENTE: {active_event}")
        elif news_sentiment > 0.6:
            block_shorts = True
            reasons.append(f"SENTIMIENTO ALCISTA RECIENTE: {active_event}")

    # 💠 Determinar Bias Final
    if block_longs and not block_shorts:
        bias = "BLOCK_LONGS"
    elif block_shorts and not block_longs:
        bias = "BLOCK_SHORTS"
    elif block_longs and block_shorts:
        bias = "CONFLICTED"
    elif not block_longs and not block_shorts:
        if dxy == "BEARISH" and nasdaq == "BULLISH":
            bias = "BULLISH"
            reasons.append("Contexto Perfecto: DXY Bajista + NASDAQ Alcista")
        elif fng >= 60 and funding > 0:
            bias = "BULLISH"
        elif fng <= 35 or dxy == "BULLISH":
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
    else:
        bias = "NEUTRAL"

    reason_str = " | ".join(reasons) if reasons else "Condiciones macro estables."
    return bias, block_longs, block_shorts, reason_str


# ── Función principal de actualización ───────────────────────────────────────
async def refresh_ghost_data(symbol: str = "BTCUSDT", macro_ctx: Optional[MacroState] = None) -> GhostState:
    """
    Descarga todos los datos fantasma en paralelo y actualiza el caché global.
    Si macro_ctx es inyectado explícitamente, FUERZA la recalculación (bypass TTL).
    """
    global _cache

    # OPTIMIZACIÓN v8.5.7: El caché macro se respeta, pero el FUNDING debe
    # consultarse siempre por activo (no compartir caché de BTC con ETH)
    if is_cache_fresh() and macro_ctx is not None:
        _cache.dxy_trend = macro_ctx.dxy_trend
        _cache.dxy_price = macro_ctx.dxy_price
        _cache.nasdaq_trend = macro_ctx.nasdaq_trend
        _cache.nasdaq_change_pct = macro_ctx.nas100_change_pct
        
        # Aunque el macro esté fresco, buscamos el funding de este símbolo particular
        local_funding = await fetch_funding_rate(symbol)
        return compute_symbol_ghost(_cache, symbol, local_funding)

    if macro_ctx is None and is_cache_fresh():
        local_funding = await fetch_funding_rate(symbol)
        return compute_symbol_ghost(_cache, symbol, local_funding)

    results = await asyncio.gather(
        _fetch_fear_greed(),
        _fetch_btc_dominance(),
        fetch_funding_rate(symbol),
        return_exceptions=True
    )

    fng_tuple = results[0] if not isinstance(results[0], Exception) else (50, "Neutral")
    btcd      = results[1] if not isinstance(results[1], Exception) else 50.0
    funding   = results[2] if not isinstance(results[2], Exception) else 0.0
    fng_val, fng_label = fng_tuple

    # Integración con Capa 1 y 2 v5.7.155 Master Gold (Narrativa & Store)
    from engine.core.store import MemoryStore
    store = MemoryStore()
    events = await store.get_economic_events(limit=5)
    news = await store.get_news(limit=5)

    # Detectar Evento Reciente Dominante
    active_event_name = ""
    now = time.time()
    for ev in events:
        ev_ts = pd.to_datetime(ev.get('date', ev.get('timestamp'))).timestamp()
        diff = (now - ev_ts) / 3600
        if ev.get('impact') in ('High', 'HIGH') and 0 <= diff <= 12: # Ultimas 12h
            active_event_name = ev.get('title', 'Macro Event')
            break
    
    # Calcular News Sentiment
    n_sent = 0.5
    if news:
        s_map = {"BULLISH": 1.0, "NEUTRAL": 0.5, "BEARISH": 0.0}
        vals = [s_map.get(n.get('sentiment', 'NEUTRAL'), 0.5) for n in news]
        n_sent = sum(vals) / len(vals)

    # Calcular sesgo macro consolidado
    dxy_trend = macro_ctx.dxy_trend if macro_ctx else "NEUTRAL"
    nasdaq_trend = macro_ctx.nasdaq_trend if macro_ctx else "NEUTRAL"
    
    bias, b_longs, b_shorts, reason = _compute_bias(
        fng_val, btcd, funding, 
        dxy=dxy_trend, 
        nasdaq=nasdaq_trend,
        news_sentiment=n_sent,
        active_event=active_event_name
    )

    is_failed = funding == 0.0 and btcd == 50.0 and fng_val == 50
    cache_time = time.time() if not is_failed else time.time() - _TTL_SECONDS + 30

    _cache = GhostState(
        fear_greed_value = fng_val,
        fear_greed_label = fng_label,
        btc_dominance    = btcd,
        funding_rate     = funding,
        funding_symbol   = symbol,
        macro_bias       = bias,
        block_longs      = b_longs,
        block_shorts     = b_shorts,
        reason           = reason,
        last_updated     = cache_time,
        is_stale         = False,
        dxy_trend        = macro_ctx.dxy_trend if macro_ctx else "NEUTRAL",
        dxy_price        = macro_ctx.dxy_price if macro_ctx else 0.0,
        nasdaq_trend     = macro_ctx.nasdaq_trend if macro_ctx else "NEUTRAL",
        nasdaq_change_pct= macro_ctx.nas100_change_pct if macro_ctx else 0.0,
        risk_appetite    = macro_ctx.risk_appetite if macro_ctx else "NEUTRAL",
        news_sentiment   = n_sent,
        active_event     = active_event_name
    )

    save_local_state(_cache)
    return _cache


def get_ghost_state(symbol: Optional[str] = None) -> GhostState:
    """Devuelve el estado macro global."""
    if not symbol or symbol.upper() == _cache.funding_symbol.upper():
        return _cache
    
    # v8.5.7: No forzar 0.0 si el simbolo no coincide. Retornar el cache actual 
    # para evitar parpadeos en 0 en el Radar Macro.
    return _cache


def compute_symbol_ghost(global_cache: GhostState, symbol: str, local_funding: float) -> GhostState:
    """Combina el estado global con datos específicos de un activo."""
    bias, block_long, block_short, reason = _compute_bias(
        global_cache.fear_greed_value, 
        global_cache.btc_dominance, 
        local_funding,
        dxy=global_cache.dxy_trend,
        nasdaq=global_cache.nasdaq_trend,
        news_sentiment=global_cache.news_sentiment,
        active_event=global_cache.active_event
    )
    
    return GhostState(
        fear_greed_value = global_cache.fear_greed_value,
        fear_greed_label = global_cache.fear_greed_label,
        btc_dominance    = global_cache.btc_dominance,
        funding_rate     = local_funding,
        funding_symbol   = symbol,
        macro_bias       = bias,
        block_longs      = block_long,
        block_shorts     = block_short,
        reason           = reason,
        last_updated     = global_cache.last_updated,
        is_stale         = global_cache.is_stale,
        dxy_trend        = global_cache.dxy_trend,
        dxy_price        = global_cache.dxy_price,
        nasdaq_trend     = global_cache.nasdaq_trend,
        nasdaq_change_pct= global_cache.nasdaq_change_pct,
        risk_appetite    = global_cache.risk_appetite
    )


def filter_signals_by_macro(signals: list[dict], ghost: GhostState) -> tuple[list[dict], list[dict]]:
    """Clasifica las señales según el contexto macro."""
    if not signals or ghost.is_stale:
        return signals, []

    approved, blocked = [], []
    for sig in signals:
        sig_type = sig.get("type", "").upper()
        reason = None
        if "LONG" in sig_type and ghost.block_longs:
            reason = f"LONG bloqueada por macro: {ghost.reason}"
        elif "SHORT" in sig_type and ghost.block_shorts:
            reason = f"SHORT bloqueada por macro: {ghost.reason}"

        if reason:
            sig["blocked_reason"] = reason
            blocked.append(sig)
        else:
            approved.append(sig)

    return approved, blocked


if __name__ == "__main__":
    async def _test():
        logger.info("🔮 Testing Ghost Data v4.0...")
        state = await refresh_ghost_data("BTCUSDT")
        logger.info(f"Bias: {state.macro_bias} | DXY: {state.dxy_trend} | NAS: {state.nasdaq_trend}")

    asyncio.run(_test())
