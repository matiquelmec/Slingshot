import sys
sys.path.insert(0, '.')
from engine.risk.risk_manager import RiskManager

def test_risk_logic():
    # Inicializar RiskManager con balance de 1000 USD
    rm = RiskManager(account_balance=1000.0)
    
    # ── Parámetros base del trade ──
    current_price = 100.0
    atr_val = 2.0
    asset = "SOLUSDT"  # Cae en DEFAULT_TUNING: atr_mult = 1.8, spread_impact = 0.0010
    
    # ── ESCENARIO 1: Mercado en Tendencia (RANGING/TREND) sin Liquidaciones cercanas ──
    res_normal = rm.calculate_position(
        current_price=current_price,
        signal_type="LONG",
        market_regime="BULLISH_TREND",
        atr_value=atr_val,
        asset=asset,
        liquidations=[]
    )
    print("=== ESCENARIO 1 (Normal en Tendencia) ===")
    print("SL Normal     :", res_normal["stop_loss"])
    print("Diferencia SL :", current_price - res_normal["stop_loss"])
    print()

    # ── ESCENARIO 2: Mercado Sucio (CHOPPY) - SL debe ensancharse un 30% ──
    res_choppy = rm.calculate_position(
        current_price=current_price,
        signal_type="LONG",
        market_regime="CHOPPY",
        atr_value=atr_val,
        asset=asset,
        liquidations=[]
    )
    print("=== ESCENARIO 2 (Choppy - Rango Sucio) ===")
    print("SL Choppy     :", res_choppy["stop_loss"])
    print("Diferencia SL :", current_price - res_choppy["stop_loss"])
    print("¿Se ensanchó? :", "SÍ" if (current_price - res_choppy["stop_loss"]) > (current_price - res_normal["stop_loss"]) else "NO")
    print()

    # ── ESCENARIO 3: Stop Hunt Shield Activo (Liquidaciones muy cercanas al Stop) ──
    # Si el SL normal es ~92.9, colocamos un cluster de liquidación de Longs a 93.5 (justo arriba del SL)
    # El sistema debería desplazar el SL un 0.2% por debajo de esa liquidación (93.5 - 0.2 = 93.3)
    simulated_liqs = [
        {"price": 93.5, "type": "LONG_LIQ", "strength": 80}
    ]
    res_shield = rm.calculate_position(
        current_price=current_price,
        signal_type="LONG",
        market_regime="BULLISH_TREND",
        atr_value=atr_val,
        asset=asset,
        liquidations=simulated_liqs
    )
    print("=== ESCENARIO 3 (Stop Hunt Shield) ===")
    print("SL Normal                :", res_normal["stop_loss"])
    print("Cluster de Liquidación   : 93.5")
    print("SL Ajustado (Tras Shield):", res_shield["stop_loss"])
    print("¿Se desplazó a 93.3?     :", "SÍ" if res_shield["stop_loss"] <= 93.3 else "NO")
    # ── ESCENARIO 4: Guardarraíl de SL Mínimo Activo (Altcoin con ATR muy comprimido) ──
    # Si ARBUSDT cotiza a $1.00 y el ATR de 15m es absurdamente pequeño ($0.001)
    # El SL normal de 1.8x ATR daría un stop en $0.9982 (0.18% de distancia).
    # El guardarraíl debe forzar el SL al 1.20% de distancia ($0.9880) para absorber mechas de futures.
    res_min_guard = rm.calculate_position(
        current_price=1.00,
        signal_type="LONG",
        market_regime="BULLISH_TREND",
        atr_value=0.001,
        asset="ARBUSDT",
        liquidations=[]
    )
    sl_dist_pct = (1.00 - res_min_guard["stop_loss"]) / 1.00 * 100
    print("=== ESCENARIO 4 (Guardarraíl Dinámico Activo) ===")
    print("Entrada                 : $1.00")
    print("SL con Guardarraíl      :", res_min_guard["stop_loss"])
    print("Distancia SL resultante :", f"{sl_dist_pct:.2f}%")
    print("¿Forzado al 1.2% min?   :", "SÍ" if abs(sl_dist_pct - 1.20) < 0.05 else "NO")
    print("Apalancamiento ajustado :", res_min_guard["leverage"], "x")
    print()

if __name__ == "__main__":
    test_risk_logic()
