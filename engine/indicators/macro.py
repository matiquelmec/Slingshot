"""
Capa 1: Contexto Macro (DXY & NASDAQ) - Slingshot v4.0
======================================================
Monitoriza los parámetros globales de liquidez y apetito por riesgo:
- DXY (Índice del Dólar): El 'termómetro' de la liquidez global.
- NAS100 (Nasdaq): El 'apetito' por activos de riesgo/tecnología.

Filosofía: No operamos contra el flujo de capital global del sistema.
"""

from engine.core.logger import logger
import os
import sys
import io
import time
import asyncio
import logging
import yfinance as yf
import urllib3
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# Suprimir logs internos de yfinance (HTTP 404, warnings de tickers)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

# ── Configuración ────────────────────────────────────────────────────────────
_STATE_FILE = Path(__file__).parent.parent / "data" / "macro_context.json"

# Tickers validados y ordenados por disponibilidad confirmada (Abril 2026)
# DX-Y.NYB: ICE US Dollar Index (funcional, verificado)
# UUP:      Invesco DB USD Bull ETF (fallback sólido)
# DX=F:     ELIMINADO — Yahoo Finance retornó 404, ticker descontinuado
_DXY_TICKERS = ["DX-Y.NYB", "UUP"]

# ^NDX: Nasdaq-100 Index (funcional, verificado)
# QQQ:  Invesco QQQ Trust ETF (fallback sólido)
_NAS_TICKERS = ["^NDX", "QQQ"]


@dataclass
class MacroState:
    """Snapshot de la situación macroeconómica global."""
    dxy_price: float         = 0.0
    dxy_trend: str           = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL
    nas100_change_pct: float = 0.0
    nasdaq_trend: str        = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL
    risk_appetite: str       = "NEUTRAL"  # RISK_ON / RISK_OFF / NEUTRAL

    # Sesgo Resultante para el Sistema
    global_bias: str         = "NEUTRAL"  # LONG_ONLY / SHORT_ONLY / CAUTIOUS / NEUTRAL
    last_updated: float      = 0.0


# ── Cache Global ──────────────────────────────────────────────────────────────
_macro_cache: MacroState = MacroState()


def get_macro_context() -> MacroState:
    """Retorna el estado macro actual desde el caché."""
    return _macro_cache


def _fetch_ticker_silent(ticker: str, period: str = "2d", interval: str = "1h"):
    """
    Descarga historial de un ticker suprimiendo TODA la salida stderr de yfinance.
    Retorna el DataFrame de historial, o None si falla.
    """
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()  # Capturar y descartar stderr (errores 404 de yfinance)
    try:
        tick = yf.Ticker(ticker)
        hist = tick.history(period=period, interval=interval)
        return hist if not hist.empty else None
    except Exception:
        return None
    finally:
        sys.stderr = old_stderr  # Restaurar stderr siempre


async def update_macro_context():
    """
    Sincroniza los datos de DXY y Nasdaq usando yfinance.
    Utiliza fallback silencioso entre tickers validados.
    """
    global _macro_cache

    # 🔒 Ruta de certificados sin caracteres especiales (bypass Windows encoding)
    CERT_PATH = r"C:\tmp\cacert.pem"
    if os.path.exists(CERT_PATH):
        os.environ['CURL_CA_BUNDLE'] = CERT_PATH
        os.environ['REQUESTS_CA_BUNDLE'] = CERT_PATH
        os.environ['SSL_CERT_FILE'] = CERT_PATH

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.info("[MACRO] 🌐 Actualizando contexto global (DXY/NASDAQ)...")
    try:
        # ── 1. DXY (US Dollar Index) ─────────────────────────────────────
        dxy_hist = None
        dxy_source = None

        for t in _DXY_TICKERS:
            hist = _fetch_ticker_silent(t)
            if hist is not None:
                dxy_hist = hist
                dxy_source = t
                break

        if dxy_hist is not None:
            curr_dxy = dxy_hist['Close'].iloc[-1]
            ma_20 = dxy_hist['Close'].rolling(window=20).mean().iloc[-1]

            _macro_cache.dxy_price = round(float(curr_dxy), 2)
            _macro_cache.dxy_trend = "BULLISH" if curr_dxy > ma_20 else "BEARISH"
            logger.info(f"[MACRO] 💹 DXY={_macro_cache.dxy_price} ({_macro_cache.dxy_trend}) ← {dxy_source}")
        else:
            logger.info(f"[MACRO] ⚠️ DXY inaccesible. Tickers probados: {_DXY_TICKERS}")
            _macro_cache.dxy_trend = "NEUTRAL"

        # ── 2. NASDAQ-100 ────────────────────────────────────────────────
        nas_hist = None
        nas_source = None

        for t in _NAS_TICKERS:
            hist = _fetch_ticker_silent(t)
            if hist is not None:
                nas_hist = hist
                nas_source = t
                break

        if nas_hist is not None:
            curr_nas = nas_hist['Close'].iloc[-1]
            open_nas = nas_hist['Open'].iloc[0]
            change = ((curr_nas - open_nas) / open_nas) * 100

            _macro_cache.nas100_change_pct = round(float(change), 2)
            _macro_cache.nasdaq_trend = "BULLISH" if change > 0 else "BEARISH"
            _macro_cache.risk_appetite = "RISK_ON" if change > 0 else "RISK_OFF"
            logger.info(f"[MACRO] 💹 NAS100={_macro_cache.nas100_change_pct:+.2f}% ({_macro_cache.nasdaq_trend}) ← {nas_source}")
        else:
            logger.info(f"[MACRO] ⚠️ NASDAQ inaccesible. Tickers probados: {_NAS_TICKERS}")
            _macro_cache.nasdaq_trend = "NEUTRAL"
            _macro_cache.risk_appetite = "NEUTRAL"

        # ── 3. Sesgo Global (Plan Maestro SMC) ───────────────────────────
        # DXY Alcista = Presión de venta (SHORT_ONLY / CAUTIOUS)
        # DXY Bajista = Inyección de liquidez (LONG_ONLY)
        if _macro_cache.dxy_trend == "BULLISH":
            _macro_cache.global_bias = "SHORT_ONLY" if _macro_cache.risk_appetite == "RISK_OFF" else "CAUTIOUS"
        else:
            _macro_cache.global_bias = "LONG_ONLY" if _macro_cache.risk_appetite == "RISK_ON" else "NEUTRAL"

        _macro_cache.last_updated = time.time()
        logger.info(f"[MACRO] ✅ Sesgo Global: {_macro_cache.global_bias}")

    except Exception as e:
        logger.error(f"[MACRO] ⚠️ Error en sincronización: {e}")


if __name__ == "__main__":
    async def test():
        await update_macro_context()
        state = get_macro_context()
        logger.info(f"\n{'='*50}")
        logger.info(f"  DXY:  {state.dxy_price} ({state.dxy_trend})")
        logger.info(f"  NAS:  {state.nas100_change_pct:+.2f}% ({state.nasdaq_trend})")
        logger.info(f"  Risk: {state.risk_appetite}")
        logger.info(f"  Bias: {state.global_bias}")
        logger.info(f"{'='*50}")

    asyncio.run(test())
