"""
engine/execution/ftmo_bridge.py — v5.7.155 Master Gold Titanium
=========================================================
Módulo de Traducción Institucional para el fondeo FTMO ($100,000 USD).
Traduce señales estratégicas filtradas por el Portero de Riesgo en
órdenes operativas directas para MetaTrader 5 (MT5).

Principios:
1. Volatilidad Dinámica: Lotaje basado en la distancia del SL estructural.
2. Protección FTMO: Buffer antimanchas para spread y comisión.
3. Precisión de Activo: Manejo dinámico de Tick Value y Contract Size.
"""

from typing import Dict, Any, Optional, List
import math
from engine.api.config import settings
from engine.core.logger import logger

# ── CONFIGURACIÓN DE CUENTA FTMO ──────────────────────────────────────────
# Según requerimiento: Cuenta de 100k y riesgo por trade (0.5% - 1.0%)
FTMO_ACCOUNT_BALANCE = 100000.0  # $100,000 USD
DEFAULT_RISK_PCT     = 0.01      # 1% de la cuenta ($1,000 USD)
MAX_LOT_SIZE         = 50.0      # Límite de exposición por activo (Seguridad)

# ── DICCIONARIO DE ACTIVOS (MT5 FTMO SPEC) ────────────────────────────────
# Contract Size y Tick Value para el cálculo exacto del punto/pip
# Nota: FTMO usa mayoritariamente cuentas en USD.
ASSET_SPECS = {
    "EURUSD":   {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0,   "type": "FOREX",  "pip_points": 10},
    "GBPUSD":   {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0,   "type": "FOREX",  "pip_points": 10},
    "AUDUSD":   {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0,   "type": "FOREX",  "pip_points": 10},
    "XAUUSD":   {"contract_size": 100,    "tick_size": 0.01,    "tick_value": 1.0,   "type": "METALS", "pip_points": 10}, # 1.00 move = $100
    "BTCUSDT":  {"contract_size": 1,      "tick_size": 0.01,    "tick_value": 0.01,  "type": "CRYPTO", "pip_points": 100}, # $1 move = $1 profit per lot
    "ETHUSDT":  {"contract_size": 1,      "tick_size": 0.01,    "tick_value": 0.01,  "type": "CRYPTO", "pip_points": 100},
    "SOLUSDT":  {"contract_size": 1,      "tick_size": 0.01,    "tick_value": 0.01,  "type": "CRYPTO", "pip_points": 100},
    "US30":     {"contract_size": 1,      "tick_size": 0.1,     "tick_value": 0.1,   "type": "INDEX",  "pip_points": 10},  # FTMO Indices suelen ser $1 por punto por lote
    "NAS100":   {"contract_size": 1,      "tick_size": 0.1,     "tick_value": 0.1,   "type": "INDEX",  "pip_points": 10},
}

DEFAULT_SPEC = {"contract_size": 100, "tick_size": 0.01, "tick_value": 1.0, "type": "GENERIC", "pip_points": 10}

def calculate_dynamic_lots(
    symbol: str, 
    entry: float, 
    sl: float, 
    risk_usd: float,
    apply_buffer: bool = True
) -> float:
    """
    Motor de Sizing Cuántico.
    Calcula el lotaje exacto para arriesgar risk_usd respetando la distancia al SL.
    """
    spec = ASSET_SPECS.get(symbol.upper(), DEFAULT_SPEC)
    
    # ── 1. Buffer de Seguridad (Spread + Comisión FTMO) ───────────────────────
    # Añadimos un pequeño margen al SL para absorber el costo operativo
    # Para evitar que el Slippage nos haga perder más del riesgo planeado.
    actual_sl = sl
    if apply_buffer:
        buffer_pts = spec["tick_size"] * (spec["pip_points"] * 1.5) # Aprox 1.5 pips de buffer
        if entry > sl: # LONG
            actual_sl = sl - buffer_pts
        else: # SHORT
            actual_sl = sl + buffer_pts
            
    # ── 2. Cálculo de Distancia en Puntos ────────────────────────────────────
    # En MT5, el volumen se calcula por 'Points'
    distance_price = abs(entry - actual_sl)
    if distance_price <= 0:
        return 0.01
        
    distance_points = distance_price / spec["tick_size"]
    
    # ── 3. Valor Monetario del Movimiento ────────────────────────────────────
    # ¿Cuánto gano/pierdo en USD por cada punto con 1 lote?
    # LotSize = Risk / (Distance_Points * TickValue)
    raw_lots = risk_usd / (distance_points * spec["tick_value"])
    
    # ── 4. Redondeo y Límites ────────────────────────────────────────────────
    # MT5 suele permitir 2 decimales (0.01 es el lote mínimo)
    lots = round(raw_lots, 2)
    lots = max(0.01, min(lots, MAX_LOT_SIZE))
    
    return lots

def prepare_ftmo_order_package(signal_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Versión DELTA v6.7.5.
    Prepara un paquete de 3 órdenes (60/20/20) para ejecución fragmentada.
    """
    symbol = signal_data.get("asset", "EURUSD").upper()
    entry  = float(signal_data.get("entry_price", signal_data.get("price", 0)))
    sl     = float(signal_data.get("stop_loss", 0))
    sig_type = signal_data.get("signal_type", "LONG").upper()
    
    # Niveles SIGMA
    tp1 = float(signal_data.get("tp1", 0))
    tp2 = float(signal_data.get("tp2", 0))
    tp3 = float(signal_data.get("tp3", 0))
    tp1_vol_pct = float(signal_data.get("tp1_vol_pct", 0.60))

    # Riesgo y Lotaje
    risk_usd = signal_data.get("risk_usd", FTMO_ACCOUNT_BALANCE * DEFAULT_RISK_PCT)
    total_lots = calculate_dynamic_lots(symbol, entry, sl, risk_usd)
    
    # Fragmentación de Lotes
    lots_tp1 = total_lots * tp1_vol_pct
    lots_tp2 = total_lots * 0.20
    lots_tp3 = total_lots - lots_tp1 - lots_tp2
    
    fragments = [
        {"id": "TP1", "vol": round(lots_tp1, 2), "tp": tp1},
        {"id": "TP2", "vol": round(lots_tp2, 2), "tp": tp2},
        {"id": "TP3", "vol": round(lots_tp3, 2), "tp": tp3}
    ]
    
    package = []
    for frag in fragments:
        if frag["vol"] <= 0: continue
        package.append({
            "symbol":    symbol,
            "action":    "BUY" if sig_type == "LONG" else "SELL",
            "type":      "ORDER_TYPE_LIMIT",
            "volume":    frag["vol"],
            "price":     entry,
            "sl":        sl,
            "tp":        frag["tp"],
            "comment":   f"DELTA_{frag['id']}_{symbol}",
            "magic":     43000,
        })
        
    logger.info(f"📦 [DELTA_BRIDGE] Paquete de {len(package)} fragmentos preparado para {symbol}")
    return package

def modify_ftmo_order(ticket: int, new_sl: float, new_tp: float = None) -> Dict[str, Any]:
    """
    Función para el Módulo OMEGA.
    Modifica el SL/TP de una orden activa en MT5.
    """
    return {
        "action": "MODIFY",
        "ticket": ticket,
        "sl": round(new_sl, 5),
        "tp": round(new_tp, 5) if new_tp else 0
    }

if __name__ == "__main__":
    # Test Mock Signal
    test_signal = {
        "asset": "EURUSD",
        "price": 1.08500,
        "stop_loss": 1.08400, # 10 pips de riesgo
        "take_profit_3r": 1.08800,
        "signal_type": "LONG",
        "regime": "MARKUP",
        "confluence": {"score": 85}
    }
    
    order = prepare_ftmo_order(test_signal)
    import json
    print(json.dumps(order, indent=2))
