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
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple
from pathlib import Path

# Importaciones de Dominio
from engine.indicators.macro import MacroState, get_macro_context

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
_api_lock = asyncio.Lock()


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
                valid_fields = {k: v for k, v in data.items() if k in GhostState.__dataclass_fields__}
                _cache = GhostState(**valid_fields)
                logger.info(f"[GHOST] 💾 Estado local cargado (F&G={_cache.fear_greed_value} | BTCD={_cache.btc_dominance}%)")
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
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{FNG_BASE}/fng/?limit=1&format=json")
            r.raise_for_status()
            data = r.json()["data"][0]
            return int(data["value"]), data["value_classification"]
    except Exception as e:
        logger.error(f"[GHOST] ⚠️  Fear & Greed fetch error: {e}")
        return _cache.fear_greed_value, _cache.fear_greed_label


async def _fetch_btc_dominance() -> float:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{COINGECKO_BASE}/global")
            r.raise_for_status()
            pct = r.json()["data"]["market_cap_percentage"]["btc"]
            return round(float(pct), 2)
    except Exception as e:
        logger.error(f"[GHOST] ⚠️  BTC Dominance fetch error: {e}")
        return _cache.btc_dominance


async def fetch_funding_rate(symbol: str = "BTCUSDT") -> float:
    if symbol.upper() in ["USDCUSDT", "EURUSDT"]:
        return 0.0
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
                        rate = float(data[-1].get("fundingRate", 0)) * 100
                        return rate
        except:
            continue
    return 0.0


# ── Lógica de filtrado macro ──────────────────────────────────────────────────
def _compute_bias(
    symbol: str, fng: int, btcd: float, funding: float, 
    dxy: str = "NEUTRAL", nasdaq: str = "NEUTRAL",
    news_sentiment: float = 0.5, active_event: str = ""
) -> tuple[str, bool, bool, str]:
    reasons = []
    block_longs = False
    block_shorts = False
    
    IS_METAL = any(m in symbol.upper() for m in ["PAXG", "XAG", "GOLD", "SILVER"])

    if IS_METAL:
        if dxy == "BULLISH":
            reasons.append("DXY Alcista: Presión técnica en Metales")
            if news_sentiment < 0.4: block_longs = True
        if nasdaq == "BEARISH":
            reasons.append("NASDAQ Bajista: Posible flujo hacia Safe Havens")
            block_shorts = True 
    else:
        if dxy == "BULLISH":
            reasons.append("DXY Alcista: Presión vendedora en Risk-Assets")
            if fng < 40: block_longs = True
        if nasdaq == "BEARISH":
            reasons.append("NASDAQ Bajista: Correlación Risk-Off")
            if fng < 30: block_longs = True
        if btcd > 55 and symbol.upper() != "BTCUSDT":
            reasons.append("BTC Dominance Alta: Alts bajo presión")
            if news_sentiment < 0.5: block_longs = True

    if active_event:
        if news_sentiment < 0.35:
            block_longs = True
            reasons.append(f"SENTIMIENTO BAJISTA: {active_event}")
        elif news_sentiment > 0.65:
            block_shorts = True
            reasons.append(f"SENTIMIENTO ALCISTA: {active_event}")

    if block_longs and not block_shorts: bias = "BLOCK_LONGS"
    elif block_shorts and not block_longs: bias = "BLOCK_SHORTS"
    elif block_longs and block_shorts: bias = "CONFLICTED"
    else:
        if IS_METAL:
            if dxy == "BEARISH" or nasdaq == "BEARISH": bias = "BULLISH"
            elif dxy == "BULLISH": bias = "BEARISH"
            else: bias = "NEUTRAL"
        else:
            if dxy == "BEARISH" and nasdaq == "BULLISH" and fng > 45: bias = "BULLISH"
            elif fng <= 35 or dxy == "BULLISH": bias = "BEARISH"
            else: bias = "NEUTRAL"

    return bias, block_longs, block_shorts, " | ".join(reasons) if reasons else "Condiciones estables."


# ── Función principal de actualización ───────────────────────────────────────
async def refresh_ghost_data(symbol: str = "BTCUSDT", macro_ctx: Optional[MacroState] = None, global_only: bool = False) -> GhostState:
    global _cache

    if global_only:
        async with _api_lock:
            if is_cache_fresh() and macro_ctx is None:
                return _cache

            logger.debug(f"[GHOST-SENTINEL] 📡 Refrescando métricas globales...")
            results = await asyncio.gather(_fetch_fear_greed(), _fetch_btc_dominance(), return_exceptions=True)
            fng_val, fng_label = results[0] if not isinstance(results[0], Exception) else (_cache.fear_greed_value, _cache.fear_greed_label)
            btcd = results[1] if not isinstance(results[1], Exception) else _cache.btc_dominance

            _cache.fear_greed_value = fng_val
            _cache.fear_greed_label = fng_label
            _cache.btc_dominance = btcd

            if macro_ctx:
                _cache.dxy_trend = macro_ctx.dxy_trend
                _cache.dxy_price = macro_ctx.dxy_price
                _cache.nasdaq_trend = macro_ctx.nasdaq_trend
                _cache.nasdaq_change_pct = macro_ctx.nas100_change_pct
                _cache.risk_appetite = macro_ctx.risk_appetite

            # Narrativa v8.7.0
            try:
                from engine.core.store import store
                events = await store.get_economic_events(limit=5)
                news = await store.get_news(limit=5)
                
                active_event_name = ""
                now = time.time()
                for ev in events:
                    ev_ts = pd.to_datetime(ev.get('date', ev.get('timestamp'))).timestamp()
                    if (now - ev_ts) / 3600 <= 12 and ev.get('impact') in ('High', 'HIGH'):
                        active_event_name = ev.get('title', 'Macro Event')
                        break
                
                n_sent = 0.5
                if news:
                    s_map = {"BULLISH": 1.0, "NEUTRAL": 0.5, "BEARISH": 0.0}
                    vals = [s_map.get(n.get('sentiment', 'NEUTRAL'), 0.5) for n in news]
                    n_sent = sum(vals) / len(vals)

                _cache.news_sentiment = n_sent
                _cache.active_event = active_event_name
            except: pass

            _cache.last_updated = time.time()
            _cache.is_stale = False
            save_local_state(_cache)
            return _cache

    if not is_cache_fresh() and not macro_ctx:
        await refresh_ghost_data(global_only=True)

    funding = await fetch_funding_rate(symbol)
    return compute_symbol_ghost(_cache, symbol, funding)


def compute_symbol_ghost(global_cache: GhostState, symbol: str, local_funding: float) -> GhostState:
    bias, bl, bs, reason = _compute_bias(
        symbol, global_cache.fear_greed_value, global_cache.btc_dominance, local_funding,
        dxy=global_cache.dxy_trend, nasdaq=global_cache.nasdaq_trend,
        news_sentiment=global_cache.news_sentiment, active_event=global_cache.active_event
    )
    return GhostState(
        fear_greed_value=global_cache.fear_greed_value,
        fear_greed_label=global_cache.fear_greed_label,
        btc_dominance=global_cache.btc_dominance,
        funding_rate=local_funding,
        funding_symbol=symbol,
        macro_bias=bias,
        block_longs=bl,
        block_shorts=bs,
        reason=reason,
        last_updated=global_cache.last_updated,
        is_stale=global_cache.is_stale,
        dxy_trend=global_cache.dxy_trend,
        dxy_price=global_cache.dxy_price,
        nasdaq_trend=global_cache.nasdaq_trend,
        nasdaq_change_pct=global_cache.nasdaq_change_pct,
        risk_appetite=global_cache.risk_appetite,
        news_sentiment=global_cache.news_sentiment,
        active_event=global_cache.active_event
    )


def get_ghost_state() -> GhostState:
    return _cache


def filter_signals_by_macro(signals: list[dict], ghost: GhostState) -> tuple[list[dict], list[dict]]:
    if not signals or ghost.is_stale: return signals, []
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
        else: approved.append(sig)
    return approved, blocked
