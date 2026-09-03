import pytest
import pandas as pd
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.core.confluence import ConfluenceManager

def test_liquidations_v2_volume_weighted():
    """
    Test para validar el motor v2.0 de Rekt Radar.
    Asegura que los clusters de liquidación se ponderen por el volumen
    de los pivotes donde fueron originados.
    """
    # Mock data - simulating a strong volume pivot and a weak one
    data = []
    base_price = 50000
    for i in range(100):
        # Default low volume
        vol = 10.0
        # Pivot 1 at index 20: High (shorts liquidation origin) - WEAK VOLUME
        if i == 20:
            price = 51000
            vol = 5.0
        # Pivot 2 at index 80: Low (longs liquidation origin) - HIGH INSTITUTIONAL VOLUME
        elif i == 80:
            price = 49000
            vol = 500.0 # Massive volume
        else:
            price = base_price + (i % 10) * 10
        
        data.append({
            "timestamp": pd.Timestamp("2026-05-01 12:00:00") + pd.Timedelta(minutes=15*i),
            "open": price,
            "high": price + 50,
            "low": price - 50,
            "close": price,
            "volume": vol
        })
    
    df = pd.DataFrame(data)
    
    clusters = estimate_liquidation_clusters(df, 50000)
    
    # Assertions
    assert len(clusters) > 0, "Debería detectar clusters de liquidación"
    
    # Encontrar el cluster derivado del pivote 2 (aprox 49000, un short liq o long liq dependiento de dirección)
    # Como el pivote 2 es un Low (49000), genera clusters "LONG_LIQ" debajo de él.
    strong_clusters = [c for c in clusters if c["type"] == "LONG_LIQ" and c["strength"] > 50]
    
    # Al menos un cluster debería heredar la fuerza del volumen institucional
    assert len(strong_clusters) > 0, "No se detectó el cluster de alta fuerza institucional"

def test_confluence_magnetic_filter():
    """
    Test para verificar que el ConfluenceManager solo otorga el bono
    de +10 puntos si el cluster de liquidación tiene > 50% de fuerza.
    """
    manager = ConfluenceManager()
    
    # Mock data
    history = pd.DataFrame([{"close": 50000, "high": 50100, "low": 49900, "volume": 1000, "timestamp": "2026-05-01 12:00:00"}] * 10)
    history['timestamp'] = pd.to_datetime(history['timestamp'])
    
    # Escenario 1: Cluster Débil (Retail)
    weak_clusters = [{"price": 50200, "strength": 30, "type": "SHORT_LIQ"}]
    res_weak = manager.evaluate_signal(
        df=history,
        signal={"price": 50000, "type": "LONG_SCALPING", "timestamp": "2026-05-01 12:00:00"},
        liquidation_clusters=weak_clusters,
        smc_map={"order_blocks": {"bullish": [], "bearish": []}, "fvgs": {"bullish": [], "bearish": []}},
    )
    
    # Escenario 2: Cluster Fuerte (Institutional)
    strong_clusters = [{"price": 50200, "strength": 80, "type": "SHORT_LIQ"}]
    res_strong = manager.evaluate_signal(
        df=history,
        signal={"price": 50000, "type": "LONG_SCALPING", "timestamp": "2026-05-01 12:00:00"},
        liquidation_clusters=strong_clusters,
        smc_map={"order_blocks": {"bullish": [], "bearish": []}, "fvgs": {"bullish": [], "bearish": []}},
    )
    
    score_weak = res_weak.get("score", 0)
    score_strong = res_strong.get("score", 0)
    
    assert score_strong > score_weak, "El cluster institucional fuerte no está otorgando un mayor puntaje de confluencia"
    
    # Verificar reasoning para asegurarse de que el mensaje correcto está presente
    reasoning_text = str(res_strong.get("reasoning", ""))
    assert "liquidación masiva" in reasoning_text.lower(), "Falta el mensaje de liquidación masiva en el razonamiento"

def test_risk_manager_magnetic_flow():
    """
    Test de Integridad de Flujo (Phase 2 & 3): 
    Verifica que el RiskManager SÓLO use clusters fuertes (>50%)
    como objetivos magnéticos de Take Profit.
    """
    from engine.risk.risk_manager import RiskManager
    
    risk = RiskManager()
    
    # Escenario: LONG a $50,000. 
    # SL estructural en $49,000. Risk = $1,000. 
    # TP1 mínimo a 2.0R sería $52,000.
    
    current_price = 50000.0
    atr = 500.0
    
    # Liquidaciones: Un cluster DÉBIL antes del TP, y un cluster FUERTE en el TP.
    clusters = [
        {"price": 51000, "type": "SHORT_LIQ", "strength": 30}, # Retail (Ignorar)
        {"price": 52500, "type": "SHORT_LIQ", "strength": 80}  # Institucional (Imán de TP1)
    ]
    
    pos = risk.calculate_position(
        current_price=current_price,
        signal_type="LONG",
        market_regime="MARKUP",
        key_levels={"supports": [{"price": 49000}]},
        atr_value=atr,
        liquidations=clusters
    )
    
    tp1 = pos.get("tp1", 0)
    
    # Si el sistema falla y usa el cluster débil (51000), el TP1 será menor a 52000.
    # Si el sistema es correcto, ignorará el 51000 y el TP1 debería ser jalado hacia 52500 o más arriba.
    # Wait, el TP1 debe ser > 52000.
    assert tp1 >= 52000, "El RiskManager está siendo atraído por clusters débiles de retail"
