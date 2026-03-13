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
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
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


# ── Cache & Persistencia en memoria ──────────────────────────────────────────
_cache: GhostState = GhostState()
_TTL_SECONDS = 900   # 15 minutos — igual a 1 vela de 15m
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
                print(f"[GHOST] 💾 Estado local cargado (F&G={_cache.fear_greed_value})")
        except Exception as e:
            print(f"[GHOST] ⚠️ Error cargando estado previo: {e}")


def save_local_state(state: GhostState):
    """Persiste el estado en disco para evitar 'fallbacks' al reiniciar."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE_FILE, 'w') as f:
            json.dump(asdict(state), f, indent=2)
    except Exception as e:
        print(f"[GHOST] ⚠️ Error guardando estado en disco: {e}")


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
        return 50, "Neutral"


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
        return 50.0


async def fetch_funding_rate(symbol: str = "BTCUSDT") -> float:
    """
    Última tasa de financiación del perpetual en Binance Futures.
    Endpoint público, sin autenticación.
    Positivo = longs pagan a shorts (mercado alcista agotándose).
    Negativo = shorts pagan a longs (pánico / venta masiva).
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": symbol.upper()}
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "lastFundingRate" in data:
                return float(data["lastFundingRate"]) * 100  # → porcentaje
            return 0.0
    except Exception as e:
        print(f"[GHOST] ⚠️  Funding Rate fetch error for {symbol}: {e}")
        return 0.0


# ── Lógica de filtrado macro ──────────────────────────────────────────────────
def _compute_bias(fng: int, btcd: float, funding: float) -> tuple[str, bool, bool, str]:
    """
    Determina el sesgo macro y si se deben bloquear señales LONG o SHORT.

    Reglas de bloqueo (Paul Perdices "Ghost Filter"):
    ┌──────────────────────────────────────────────────────────────────────────┐
    │  BLOQUEAR LONGS si:                                                      │
    │   → Fear & Greed < 20 (Miedo Extremo) Y Funding < -0.05% (panic shorts) │
    │   → Fear & Greed < 25 Y BTC Dominance > 60% (fuga a BTC, alts sangran)  │
    │                                                                          │
    │  BLOQUEAR SHORTS si:                                                     │
    │   → Fear & Greed > 80 (Codicia Extrema) Y Funding > +0.10% (euforia)    │
    │                                                                          │
    │  Fuera de eso: NEUTRAL / señal contextual                                │
    └──────────────────────────────────────────────────────────────────────────┘
    """
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
            reasons.append(f"Contexto macro favorable: F&G={fng}, Funding={funding:.3f}%, BTCD={btcd}%")
        elif fng <= 35:
            bias = "BEARISH"
            reasons.append(f"Contexto macro pesimista: F&G={fng}")
        else:
            bias = "NEUTRAL"
            reasons.append(f"Contexto macro neutro: F&G={fng}, Funding={funding:.3f}%, BTCD={btcd}%")
    else:
        bias = "CONFLICTED"
        reasons.append("Señales macro contrapuestas — operar con cautela extrema")

    reason_str = " | ".join(reasons) if reasons else "Condiciones macro normales."
    return bias, block_longs, block_shorts, reason_str


# ── Función principal de actualización ───────────────────────────────────────
async def refresh_ghost_data(symbol: str = "BTCUSDT") -> GhostState:
    """
    Descarga todos los datos fantasma en paralelo y actualiza el caché global.
    Solo hace requests si el caché está vencido (TTL = 15 min).
    """
    global _cache

    if is_cache_fresh():
        return _cache  # Devolver caché sin nuevas peticiones

    print(f"[GHOST] 🔄 Actualizando datos fantasma (caché vencido)...")

    # Fetch paralelo de las 3 fuentes independientes
    results = await asyncio.gather(
        _fetch_fear_greed(),
        _fetch_btc_dominance(),
        fetch_funding_rate(symbol),
        return_exceptions=True
    )

    # Manejar posibles errores por fuente con fallbacks seguros
    fng_tuple = results[0] if not isinstance(results[0], Exception) else (50, "Neutral")
    btcd      = results[1] if not isinstance(results[1], Exception) else 50.0
    funding   = results[2] if not isinstance(results[2], Exception) else 0.0

    fng_val, fng_label = fng_tuple

    # Calcular sesgo macro
    bias, block_longs, block_shorts, reason = _compute_bias(fng_val, btcd, funding)

    # Si todo falla horriblemente, permitir un retry rápido (30s) en lugar de 15 min
    is_failed = funding == 0.0 and btcd == 50.0 and fng_val == 50
    cache_time = time.time() if not is_failed else time.time() - _TTL_SECONDS + 30

    # Actualizar caché global
    _cache = GhostState(
        fear_greed_value = fng_val,
        fear_greed_label = fng_label,
        btc_dominance    = btcd,
        funding_rate     = funding,
        funding_symbol   = symbol,
        macro_bias       = bias,
        block_longs      = block_longs,
        block_shorts     = block_shorts,
        reason           = reason,
        last_updated     = cache_time,
        is_stale         = False,
    )

    # Persistir en disco para el próximo inicio
    save_local_state(_cache)

    print(
        f"[GHOST] ✅ F&G={fng_val} ({fng_label}) | BTCD={btcd}% | "
        f"Funding={funding:.4f}% | Bias={bias}"
    )
    if block_longs:
        print(f"[GHOST] 🚫 BLOQUEANDO señales LONG: {reason}")
    if block_shorts:
        print(f"[GHOST] 🚫 BLOQUEANDO señales SHORT: {reason}")

    return _cache



def get_ghost_state(symbol: Optional[str] = None) -> GhostState:
    """
    Devuelve el estado macro global. 
    Si se pide un símbolo específico que no es el del caché global, 
    mantenemos los datos macro (F&G, BTCD) pero reseteamos el funding 
    para que el Broadcaster lo actualice con su valor real.
    """
    if not symbol or symbol.upper() == _cache.funding_symbol.upper():
        return _cache
    
    # Contexto global con funding neutro para el nuevo símbolo
    # El broadcaster se encargará de llamar a refresh_ghost_data(symbol) enseguida
    return GhostState(
        fear_greed_value = _cache.fear_greed_value,
        fear_greed_label = _cache.fear_greed_label,
        btc_dominance    = _cache.btc_dominance,
        funding_rate     = 0.0,
        funding_symbol   = symbol.upper(),
        macro_bias       = _cache.macro_bias,
        block_longs      = _cache.block_longs,
        block_shorts     = _cache.block_shorts,
        reason           = _cache.reason,
        last_updated     = _cache.last_updated,
        is_stale         = _cache.is_stale
    )


def compute_symbol_ghost(global_cache: GhostState, symbol: str, local_funding: float) -> GhostState:
    """Combina el estado global con datos específicos de un activo."""
    bias, block_long, block_short, reason = _compute_bias(
        global_cache.fear_greed_value, 
        global_cache.btc_dominance, 
        local_funding
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
        is_stale         = global_cache.is_stale
    )


def filter_signals_by_macro(signals: list[dict], ghost: GhostState) -> tuple[list[dict], list[dict]]:
    """
    Clasifica las señales según el contexto macro.
    Retorna: (lista_aprobadas, lista_bloqueadas)
    """
    if not signals or ghost.is_stale:
        return signals, []  # Sin datos macro, no bloqueamos nada (fail-open)

    approved = []
    blocked = []
    
    for sig in signals:
        sig_type = sig.get("type", "").upper()
        is_long  = "LONG"  in sig_type
        is_short = "SHORT" in sig_type

        reason = None
        if is_long and ghost.block_longs:
            reason = f"LONG bloqueada por macro: {ghost.reason}"
        elif is_short and ghost.block_shorts:
            reason = f"SHORT bloqueada por macro: {ghost.reason}"

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
