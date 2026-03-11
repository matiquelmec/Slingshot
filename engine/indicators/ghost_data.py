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

import os
import asyncio
import time
import httpx
from dataclasses import dataclass, field
from typing import Optional

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

    # Metadata de frescura del caché
    last_updated: float             = 0.0
    is_stale: bool                  = True


# ── Cache en memoria ─────────────────────────────────────────────────────────
# Separamos el macro (global) del funding (por activo) para que al cambiar de moneda
# en el frontend se actualice solo el funding sin re-descargar todo lo macro.
_macro_cache = {
    "fng_val": 50,
    "fng_label": "Neutral",
    "btcd": 50.0,
    "last_updated": 0.0
}
_funding_cache = {} # symbol -> {"rate": float, "last_updated": float}

_refresh_lock = asyncio.Lock()
_TTL_SECONDS = 300   # 5 minutos para mayor dinamismo


def is_cache_fresh(symbol: str = "BTCUSDT") -> bool:
    """Verifica si tanto el macro como el funding del símbolo están frescos."""
    now = time.time()
    macro_ok = (now - _macro_cache["last_updated"]) < _TTL_SECONDS
    
    symbol = symbol.upper()
    funding = _funding_cache.get(symbol)
    funding_ok = funding and (now - funding["last_updated"]) < _TTL_SECONDS
    
    return macro_ok and funding_ok


# ── Fetchers individuales ─────────────────────────────────────────────────────
async def _fetch_fear_greed() -> tuple[int, str]:
    """
    Fear & Greed Index de alternative.me
    API pública, sin key. Límite: ~1 req/minuto.
    Retorna: (valor_0_100, label_texto)
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{FNG_BASE}/fng/?limit=1&format=json")
            r.raise_for_status()
            data = r.json()["data"][0]
            return int(data["value"]), data["value_classification"]
    except Exception as e:
        print(f"[GHOST] ⚠️  Fear & Greed fetch error: {e}")
        return None


async def _fetch_btc_dominance() -> float:
    """
    BTC Dominance desde CoinGecko /global.
    API pública, sin key. Suficiente para uso esporádico.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{COINGECKO_BASE}/global")
            r.raise_for_status()
            pct = r.json()["data"]["market_cap_percentage"]["btc"]
            return round(float(pct), 2)
    except Exception as e:
        print(f"[GHOST] ⚠️  BTC Dominance fetch error: {e}")
        return None


async def _fetch_funding_rate(symbol: str = "BTCUSDT") -> float:
    """
    Última tasa de financiación del perpetual en Binance Futures.
    Endpoint público, sin autenticación.
    Positivo = longs pagan a shorts (mercado alcista agotándose).
    Negativo = shorts pagan a longs (pánico / venta masiva).
    """
    # ── Mapeo de Símbolos Institucionales (Binance 1000x contracts) ──
    # Muchos memes en futuros se transan en lotes de 1000
    MEME_MAP = ["PEPE", "SHIB", "FLOKI", "BONK", "SATS", "RATS", "XEC", "LUNC"]
    
    target_symbol = symbol.upper().replace("USDT", "").replace("USDC", "")
    if target_symbol in MEME_MAP:
        search_symbol = f"1000{target_symbol}USDT"
    else:
        search_symbol = symbol.upper()

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                f"https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": search_symbol}
            )
            r.raise_for_status()
            data = r.json()
            if data and "lastFundingRate" in data:
                return float(data["lastFundingRate"]) * 100  # → porcentaje
            return 0.0
    except Exception as e:
        print(f"[GHOST] ⚠️  Funding Rate fetch error ({symbol}): {e}")
        return None


# ── Lógica de filtrado macro ──────────────────────────────────────────────────
def _compute_bias(fng: int, btcd: float, funding: float) -> tuple[str, bool, bool, str]:
    """ Determina el sesgo macro basándose en F&G, BTCD y Funding. """
    reasons = []
    block_longs = False
    block_shorts = False

    # ─── Reglas BLOCK_LONGS ───────────────────────────────────────────────
    if fng < 20 and funding < -0.05:
        block_longs = True
        reasons.append(f"Miedo Extremo (F&G={fng}) + Funding negativo ({funding:.3f}%)")

    if fng < 25 and btcd > 60.0:
        block_longs = True
        reasons.append(f"Dominancia BTC alta ({btcd}%) + pánico en alts (F&G={fng})")

    # ─── Reglas BLOCK_SHORTS ─────────────────────────────────────────────
    if fng > 80 and funding > 0.10:
        block_shorts = True
        reasons.append(f"Codicia Extrema (F&G={fng}) + Funding longs agotados ({funding:.3f}%)")

    # ─── Sesgo macro general ──────────────────────────────────────────────
    if block_longs and not block_shorts:
        bias = "BLOCK_LONGS"
    elif block_shorts and not block_longs:
        bias = "BLOCK_SHORTS"
    elif not block_longs and not block_shorts:
        if fng >= 60 and funding > 0 and btcd < 55:
            bias = "BULLISH"
            reasons.append(f"Contexto macro favorable (F&G={fng}, Funding={funding:.3f}%)")
        elif fng <= 35:
            bias = "BEARISH"
            reasons.append(f"Contexto macro pesimista (F&G={fng})")
        else:
            bias = "NEUTRAL"
            reasons.append(f"Contexto macro neutro (F&G={fng})")
    else:
        bias = "CONFLICTED"
        reasons.append("Señales macro contrapuestas")

    reason_str = " | ".join(reasons) if reasons else "Condiciones normales."
    return bias, block_longs, block_shorts, reason_str


# ── Función principal de actualización ───────────────────────────────────────
async def refresh_ghost_data(symbol: str = "BTCUSDT") -> GhostState:
    """
    Descarga datos macro (global) y funding (específico) en paralelo.
    Solo descarga lo que está vencido.
    """
    global _macro_cache, _funding_cache
    symbol = symbol.upper()

    async with _refresh_lock:
        now = time.time()
        macro_stale = (now - _macro_cache["last_updated"]) >= _TTL_SECONDS
        funding_stale = (now - _funding_cache.get(symbol, {}).get("last_updated", 0)) >= _TTL_SECONDS

        if not macro_stale and not funding_stale:
            return get_ghost_state(symbol)

        # 1. Preparar tareas de fetch
        tasks = []
        if macro_stale:
            tasks.append(_fetch_fear_greed())    # 0
            tasks.append(_fetch_btc_dominance()) # 1
        else:
            tasks.append(asyncio.sleep(0)) # placeholder
            tasks.append(asyncio.sleep(0)) # placeholder

        if funding_stale:
            tasks.append(_fetch_funding_rate(symbol)) # 2
        else:
            tasks.append(asyncio.sleep(0)) # placeholder

        print(f"[GHOST] 🔄 Refresh: Macro={macro_stale}, Funding({symbol})={funding_stale}")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 2. Procesar resultados Macro
        if macro_stale and not isinstance(results[0], Exception) and results[0] is not None:
            _macro_cache["fng_val"], _macro_cache["fng_label"] = results[0]
            _macro_cache["last_updated"] = now
        
        if macro_stale and not isinstance(results[1], Exception) and results[1] is not None:
            _macro_cache["btcd"] = results[1]
            _macro_cache["last_updated"] = now

        # 3. Procesar resultados Funding
        if funding_stale and not isinstance(results[2], Exception) and results[2] is not None:
            _funding_cache[symbol] = {
                "rate": results[2],
                "last_updated": now
            }

        return get_ghost_state(symbol)


def get_ghost_state(symbol: str = "BTCUSDT") -> GhostState:
    """
    Devuelve el estado macro proyectado para un símbolo específico.
    Combina el macro global con el funding rate local.
    """
    symbol = symbol.upper()
    funding = _funding_cache.get(symbol, {"rate": 0.0, "last_updated": 0.0})
    
    bias, b_longs, b_shorts, reason = _compute_bias(
        _macro_cache["fng_val"],
        _macro_cache["btcd"],
        funding["rate"]
    )

    return GhostState(
        fear_greed_value = _macro_cache["fng_val"],
        fear_greed_label = _macro_cache["fng_label"],
        btc_dominance    = _macro_cache["btcd"],
        funding_rate     = funding["rate"],
        funding_symbol   = symbol,
        macro_bias       = bias,
        block_longs      = b_longs,
        block_shorts     = b_shorts,
        reason           = reason,
        last_updated     = max(_macro_cache["last_updated"], funding["last_updated"]),
        is_stale         = (time.time() - _macro_cache["last_updated"]) >= _TTL_SECONDS
    )


def filter_signals_by_macro(signals: list[dict], ghost: GhostState) -> tuple[list[dict], list[dict]]:
    """
    Clasifica las señales según el contexto macro y la fase de Wyckoff.
    Implementa el filtro 'Contrarian' de Warren Buffett / Paul Perdices.
    """
    if not signals or ghost.is_stale:
        return signals, []

    approved = []
    blocked = []
    
    for sig in signals:
        sig_type = sig.get("type", "").upper()
        regime   = sig.get("regime", "UNKNOWN").upper()
        is_long  = "LONG"  in sig_type
        is_short = "SHORT" in sig_type

        # 🚀 REGLA DE TRADER PRO: Miedo Extremo en Acumulación es OPORTUNIDAD, no bloqueo.
        is_contrarian_opportunity = (is_long and regime == "ACCUMULATION") or (is_short and regime == "DISTRIBUTION")

        reason = None
        if is_long and ghost.block_longs:
            if is_contrarian_opportunity:
                print(f"[GHOST] ✅ OPORTUNIDAD CONTRARIAN detectada en {regime} (bypass macro)")
                sig["is_contrarian"] = True
                sig["macro_note"] = "Aprobado por lógica de Acumulación/Suicidio Retail (Buffett Mode)"
            else:
                reason = f"LONG bloqueada por macro (Mercado en caída libre): {ghost.reason}"
                
        elif is_short and ghost.block_shorts:
            if is_contrarian_opportunity:
                print(f"[GHOST] ✅ OPORTUNIDAD CONTRARIAN detectada en {regime} (bypass macro)")
                sig["is_contrarian"] = True
                sig["macro_note"] = "Aprobado por lógica de Distribución / Euforia Iracional"
            else:
                reason = f"SHORT bloqueada por macro (Fase de euforia parabólica): {ghost.reason}"

        if reason:
            print(f"[GHOST] 🚫 {reason}")
            sig["blocked_reason"] = reason
            blocked.append(sig)
            continue

        approved.append(sig)

    return approved, blocked


# ── Test rápido ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def _test():
        print("🔮 Test Ghost Data — Nivel 1 del Blueprint\n")
        state = await refresh_ghost_data("BTCUSDT")
        print(f"\n📊 ESTADO MACRO:")
        print(f"   Fear & Greed : {state.fear_greed_value} ({state.fear_greed_label})")
        print(f"   BTC Dominance: {state.btc_dominance}%")
        print(f"   Funding Rate : {state.funding_rate:.4f}%")
        print(f"   Bias Macro   : {state.macro_bias}")
        print(f"   Block LONGs  : {state.block_longs}")
        print(f"   Block SHORTs : {state.block_shorts}")
        print(f"   Razón        : {state.reason}")

        # Test del filtro
        test_signals = [
            {"type": "LONG 🟢 (TREND PULLBACK)", "price": 95000},
            {"type": "SHORT 🔴 (REVERSION)", "price": 95000},
        ]
        filtered = filter_signals_by_macro(test_signals, state)
        print(f"\n🔍 Señales originales: {len(test_signals)} → Filtradas: {len(filtered)}")

    asyncio.run(_test())
