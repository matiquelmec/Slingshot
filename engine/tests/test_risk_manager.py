# engine/tests/test_risk_manager.py
import pytest
from engine.risk.risk_manager import RiskManager

def calculate_mt5_lots_py(symbol: str, risk_usd: float, sl_dist: float) -> float:
    contract_sizes = {
        'XAUUSD': 100, 'GOLD': 100, 'PAXGUSDT': 1, 'XAGUSD': 5000,
        'BTCUSD': 1, 'BTCUSDT': 1, 'ETHUSD': 10, 'ETHUSDT': 10,
        'SOLUSD': 10, 'SOLUSDT': 10, 'AVAXUSD': 10, 'AVAXUSDT': 10
    }
    c_size = contract_sizes.get(symbol, 1)
    if sl_dist <= 0 or risk_usd <= 0: return 0.01
    lots = risk_usd / (sl_dist * c_size)
    return max(0.01, round(lots, 2))

def test_risk_manager_fast_be_long():
    """Valida que el disparador de Fast Breakeven (+1.0R) para Longs se calcule con precisión milimétrica (v17.2)."""
    rm = RiskManager(account_balance=100000.0, base_risk_pct=0.005) # 0.50% = $500
    entry = 2500.0 # Oro
    atr = 10.0
    pos = rm.calculate_position(current_price=entry, signal_type='LONG', atr_value=atr, asset='PAXGUSDT')
    
    sl = pos['stop_loss']
    be_price = pos['be_price']
    tp3 = pos['tp3']
    risk_dist = entry - sl
    
    assert risk_dist > 0, "La distancia de riesgo debe ser positiva"
    assert be_price == pytest.approx(entry + (risk_dist * 1.0), rel=1e-3), "El nivel de BE debe ser exactamente Entrada + (Riesgo * 1.0)"
    assert tp3 > be_price, "TP3 debe ser superior al nivel de BE"
    assert pos['tp1_vol_pct'] == 0.70, "El volumen de toma de beneficios en TP1 debe ser 70%"
    assert pos['risk_amount_usdt'] == pytest.approx(500.0, rel=1e-2), "El riesgo en dólares debe ser exactamente $500 USD"

def test_risk_manager_fast_be_short():
    """Valida que el disparador de Fast Breakeven (+1.0R) para Shorts se calcule correctamente (v17.2)."""
    rm = RiskManager(account_balance=100000.0, base_risk_pct=0.005)
    entry = 65000.0 # BTC
    atr = 500.0
    pos = rm.calculate_position(current_price=entry, signal_type='SHORT', atr_value=atr, asset='BTCUSDT')
    
    sl = pos['stop_loss']
    be_price = pos['be_price']
    tp3 = pos['tp3']
    risk_dist = sl - entry
    
    assert risk_dist > 0, "La distancia de riesgo en Short debe ser positiva"
    assert be_price == pytest.approx(entry - (risk_dist * 1.0), rel=1e-3), "El nivel de BE en Short debe ser Entrada - (Riesgo * 1.0)"
    assert tp3 < be_price, "TP3 en Short debe estar por debajo del nivel de BE"
    assert pos['tp1_vol_pct'] == 0.70, "El volumen de toma de beneficios en TP1 debe ser 70%"

def test_mt5_lot_sizing_ftmo():
    """Valida el dimensionamiento de lotes exacto para las especificaciones de FTMO MetaTrader 5."""
    # Caso 1: Oro (XAUUSD) - Contract Size: 100 onzas
    # Riesgo: $500 USD, Distancia SL: $5.00 -> Lotes = 500 / (5.00 * 100) = 1.00 Lote
    risk = 500.0
    sl_dist_gold = 5.0
    lots_gold = calculate_mt5_lots_py('XAUUSD', risk, sl_dist_gold)
    assert lots_gold == 1.00, f"Esperado 1.00 Lote para Oro, obtenido {lots_gold}"
    
    # Caso 2: Bitcoin (BTCUSD) - Contract Size: 1 BTC
    # Riesgo: $500 USD, Distancia SL: $1,000 USD -> Lotes = 500 / (1000 * 1) = 0.50 Lotes
    lots_btc = calculate_mt5_lots_py('BTCUSD', risk, 1000.0)
    assert lots_btc == 0.50, f"Esperado 0.50 Lotes para BTC, obtenido {lots_btc}"
    
    # Caso 3: Ethereum (ETHUSD) - Contract Size: 10 ETH
    # Riesgo: $500 USD, Distancia SL: $50 USD -> Lotes = 500 / (50 * 10) = 1.00 Lote
    lots_eth = calculate_mt5_lots_py('ETHUSD', risk, 50.0)
    assert lots_eth == 1.00, f"Esperado 1.00 Lote para ETH, obtenido {lots_eth}"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
