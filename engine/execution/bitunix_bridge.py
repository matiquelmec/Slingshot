"""
engine/execution/bitunix_bridge.py — v5.7.155 Master Gold Titanium
===========================================================
Adaptador de Ejecución para Bitunix Futures (USDT-M).
Enfocado en: Maximización de Colateral + Protección de Liquidación.
"""

from typing import Dict, Any
import math
from engine.api.config import settings
from engine.core.logger import logger

# ── PARÁMETROS DE BÓVEDA BITUNIX ──────────────────────────────────────────
BITUNIX_VAULT_BALANCE = 1000.0  # $1,000 USD Base
RISK_PER_TRADE_PCT    = 0.01    # 1% de la bóveda ($10.00 USD)
TAKER_FEE             = 0.0006  # 0.06% (Estándar Bitunix Taker)
MAKER_FEE             = 0.0002  # 0.02% (Estándar Bitunix Maker)

def calculate_crypto_leverage_math(entry: float, sl: float, risk_usd: float) -> Dict[str, Any]:
    """
    Motor de Margin Math para Futuros Perpetuos.
    Calcula Position Size y el Apalancamiento Máximo SEGURO (Liq Price < SL).
    """
    # 1. Distancia Porcentual (Risk Distance)
    distance_pct = abs(entry - sl) / entry
    if distance_pct <= 0: return {"size_tokens": 0, "leverage": 1, "margin": 0}

    # 2. Position Size Nominal (Notional Value)
    # Queremos que: (Size * Distancia%) = RiskUSD
    notional_size_usd = risk_usd / distance_pct
    
    # 3. Cálculo de Apalancamiento Máximo Eficiente (Isolated)
    # Regla de Oro: La liquidación DEBE estar más lejos que el Stop Loss.
    # Liq_Dist ≈ 1 / Leverage. Queremos Leverage < 1 / Distancia_PCT
    theoretical_max_lev = 1 / distance_pct
    # Aplicamos un factor de seguridad del 85% para evitar liquidaciones por mechas de volatilidad
    safe_leverage = math.floor(theoretical_max_lev * 0.85)
    
    # Capamos el apalancamiento según límites razonables de Bitunix (ej. 100x)
    final_leverage = max(1, min(int(safe_leverage), 100))
    
    # 4. Margen Aislado Requerido (Colateral)
    required_margin = notional_size_usd / final_leverage
    
    # 5. Cantidad en Monedas (Tokens)
    # Bitunix requiere la cantidad exacta en la moneda base (BTC, ETH, etc.)
    quantity_tokens = notional_size_usd / entry

    return {
        "notional_size_usd": round(notional_size_usd, 2),
        "leverage":         final_leverage,
        "margin_usd":       round(required_margin, 2),
        "quantity_tokens":  round(quantity_tokens, 6),
        "distance_pct":     round(distance_pct * 100, 4)
    }

def prepare_bitunix_order(signal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Genera el Payload final para la REST API de Bitunix.
    Ajusta el TP para absorber los Taker Fees y garantizar el R:R neto.
    """
    symbol = signal_data.get("asset", "BTCUSDT").upper()
    entry  = float(signal_data.get("price", 0))
    sl     = float(signal_data.get("stop_loss", 0))
    tp_raw = float(signal_data.get("take_profit_3r", 0))
    side_tactical = signal_data.get("signal_type", "LONG").upper()
    
    # ── Ejecutar Calculadora de Margen ────────────────────────────────────────
    risk_usd = BITUNIX_VAULT_BALANCE * RISK_PER_TRADE_PCT
    math_results = calculate_crypto_leverage_math(entry, sl, risk_usd)
    
    # ── Ajuste de Fees en Take Profit (Slippage/Fee Buffer) ───────────────────
    # Sumamos o restamos un 0.05% al TP para cubrir el Taker Fee de salida
    fee_adjustment = entry * 0.0005 
    tp_net = (tp_raw + fee_adjustment) if side_tactical == "LONG" else (tp_raw - fee_adjustment)

    # ── Construcción del Payload Bitunix ──────────────────────────────────────
    return {
        "symbol":       symbol,
        "side":         "Buy" if side_tactical == "LONG" else "Sell",
        "positionSide": "Long" if side_tactical == "LONG" else "Short",
        "type":         "Limit",
        "quantity":     math_results["quantity_tokens"],
        "leverage":     math_results["leverage"],
        "marginType":   "ISOLATED",
        "price":        entry,
        "stopLoss":     round(sl, 2),
        "takeProfit":   round(tp_net, 2),
        "metadata": {
            "notional_value": f"${math_results['notional_size_usd']}",
            "risk_exposure": f"${risk_usd}",
            "margin_reserved": f"${math_results['margin_usd']}"
        }
    }

if __name__ == "__main__":
    mock_signal = {"asset": "BTCUSDT", "price": 65000, "stop_loss": 64350, "signal_type": "LONG", "take_profit_3r": 67000}
    payload = prepare_bitunix_order(mock_signal)
    import json
    print(json.dumps(payload, indent=2))
