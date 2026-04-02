"""
engine/router/dispatcher.py — Slingshot v4.1 Platinum
=======================================================
Capa de Despacho y Enriquecimiento de Señales.
Responsabilidad: tomar una oportunidad bruta del Strategy y enriquecerla
con los datos matemáticos de riesgo, timestamps de expiración y metadatos
necesarios para que sea consumible por el ConfluenceManager y la UI.
"""
from __future__ import annotations

import pandas as pd
from typing import Any

# Mapa de timeframe → minutos
_INTERVAL_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "8h": 480, "1d": 1440,
}


def build_base_result(market_map) -> dict:
    """
    Ensambla el dict de resultado base a partir de un MarketMap.
    Esto es lo que el Router devolverá al Gateway.
    """
    from engine.router.analyzer import MarketMap  # import local para evitar circular
    mm: MarketMap = market_map

    return {
        "asset": mm.asset,
        "interval": mm.interval,
        "timestamp": mm.timestamp,
        "current_price": mm.current_price,
        "market_regime": mm.market_regime,
        "nearest_support": mm.nearest_support,
        "nearest_resistance": mm.nearest_resistance,
        "expansion_ratio": mm.expansion_ratio,
        "range_pos_pct": mm.range_pos_pct,
        "bb_width_mean": None,   # Reservado para futuras ampliaciones
        "dist_to_sma200": None,  # Reservado para futuras ampliaciones
        "active_strategy": "SMC v4.1 Platinum (Liquidity & OBs)",
        "key_levels": mm.key_levels,
        "smc": mm.smc,
        "fibonacci": mm.fibonacci,
        "htf_bias": mm.htf_bias,
        "diagnostic": mm.diagnostic,
        "signals": [],
        "blocked_signals": [],
    }


def enrich_signal(signal: dict, risk_data: dict, interval: str) -> dict:
    """
    Inyecta los datos matemáticos de riesgo en una señal bruta.
    Calcula el timestamp de expiración de la operación.
    """
    interval_minutes = _INTERVAL_MINUTES.get(interval, 15)

    # ── Timestamp de expiración ────────────────────────────────────────────
    expiry_timestamp_str = None
    try:
        sig_ts = pd.Timestamp(signal.get("timestamp"))
        expiry_candles = risk_data.get("expiry_candles", 3)
        expiry_ts = sig_ts + pd.Timedelta(minutes=interval_minutes * expiry_candles)
        expiry_timestamp_str = str(expiry_ts)
    except Exception:
        pass

    signal.update({
        "risk_usd":          risk_data["risk_amount_usdt"],
        "risk_pct":          risk_data["risk_pct"],
        "leverage":          risk_data["leverage"],
        "position_size":     risk_data["position_size_usdt"],
        "stop_loss":         risk_data["stop_loss"],
        "take_profit_3r":    risk_data["take_profit_3r"],
        "entry_zone_top":    risk_data["entry_zone_top"],
        "entry_zone_bottom": risk_data["entry_zone_bottom"],
        "expiry_candles":    risk_data.get("expiry_candles", 3),
        "expiry_timestamp":  expiry_timestamp_str,
        "interval_minutes":  interval_minutes,
    })
    return signal
