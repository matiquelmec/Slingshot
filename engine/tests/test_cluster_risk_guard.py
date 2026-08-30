"""
engine/tests/test_cluster_risk_guard.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: CLUSTER RISK GUARD & CORRELACIÓN CRUZADA (v26.0)
=============================================================================
Audita:
1. Cálculo de correlación de Pearson y fallback estructural por cluster.
2. Bloqueo de 3er trade en activos correlacionados (ej. SOL, AVAX, NEAR en LONG).
3. Desbloqueo inmediato cuando una posición correlacionada entra a Breakeven.
4. Coexistencia sin restricciones entre clusters independientes (Cripto vs Oro 1H / TradFi).
5. Excepción institucional por Confluencia Élite (>= 88%).
"""
import pytest
import numpy as np
from engine.risk.cluster_risk_guard import ClusterRiskGuard

def test_cluster_assignment():
    guard = ClusterRiskGuard()
    assert guard.get_cluster_name("SOLUSDT") == "CRYPTO_HIGH_BETA"
    assert guard.get_cluster_name("AVAXUSDT") == "CRYPTO_HIGH_BETA"
    assert guard.get_cluster_name("BTCUSDT") == "CRYPTO_MAJORS"
    assert guard.get_cluster_name("PAXGUSDT") == "TRADFI_METALS"
    assert guard.get_cluster_name("XAUUSD") == "TRADFI_METALS"
    assert guard.get_cluster_name("US100") == "TRADFI_INDICES"

def test_pearson_correlation_calculation_with_synthetic_series():
    guard = ClusterRiskGuard()
    
    # Generar 2 series de precios altamente correlacionadas
    np.random.seed(42)
    base_returns = np.random.normal(0.001, 0.02, 50)
    noise_a = np.random.normal(0, 0.002, 50)
    noise_b = np.random.normal(0, 0.002, 50)
    
    p_a = 100 * np.exp(np.cumsum(base_returns + noise_a))
    p_b = 50 * np.exp(np.cumsum(base_returns + noise_b))
    
    guard.update_price_history("SOLUSDT", p_a.tolist())
    guard.update_price_history("AVAXUSDT", p_b.tolist())
    
    corr = guard.calculate_correlation("SOLUSDT", "AVAXUSDT")
    assert corr > 0.80, f"Se esperaba correlación > 0.80, se obtuvo {corr:.2f}"

def test_blocks_third_correlated_position():
    guard = ClusterRiskGuard(correlation_threshold=0.75, max_per_cluster=2)
    
    # 2 posiciones activas con riesgo abierto en el cluster CRYPTO_HIGH_BETA
    active_positions = {
        "SOLUSDT": {
            "signal": {"type": "LONG", "price": 180.0, "stop_loss": 175.0},
            "smart_trailing": {"be_active": False}
        },
        "AVAXUSDT": {
            "signal": {"type": "LONG", "price": 30.0, "stop_loss": 29.0},
            "smart_trailing": {"be_active": False}
        }
    }
    
    # Intentar abrir un 3er trade en NEARUSDT (mismo cluster y dirección, score estándar 75%)
    can_open, reason = guard.can_open_position("NEARUSDT", "LONG", confluence_score=75.0, active_positions=active_positions)
    assert can_open is False
    assert "Límite de cluster alcanzado" in reason

def test_unblocks_when_position_reaches_breakeven():
    guard = ClusterRiskGuard(correlation_threshold=0.75, max_per_cluster=2)
    
    # 2 posiciones activas: SOL está en Breakeven ($0 riesgo) y AVAX tiene riesgo abierto
    active_positions = {
        "SOLUSDT": {
            "signal": {"type": "LONG", "price": 180.0, "stop_loss": 180.1},
            "smart_trailing": {"be_active": True}  # En Breakeven
        },
        "AVAXUSDT": {
            "signal": {"type": "LONG", "price": 30.0, "stop_loss": 29.0},
            "smart_trailing": {"be_active": False}
        }
    }
    
    # NEARUSDT debe ser aprobado porque SOL liberó su slot de riesgo al estar en BE
    can_open, reason = guard.can_open_position("NEARUSDT", "LONG", confluence_score=75.0, active_positions=active_positions)
    assert can_open is True
    assert "Aprobado" in reason

def test_allows_independent_clusters_concurrently():
    guard = ClusterRiskGuard(correlation_threshold=0.75, max_per_cluster=2)
    
    # 2 posiciones activas en Cripto
    active_positions = {
        "SOLUSDT": {"signal": {"type": "LONG", "price": 180.0, "stop_loss": 175.0}, "smart_trailing": {"be_active": False}},
        "AVAXUSDT": {"signal": {"type": "LONG", "price": 30.0, "stop_loss": 29.0}, "smart_trailing": {"be_active": False}}
    }
    
    # PAXGUSDT (Oro) pertenece a TRADFI_METALS -> Debe permitirse sin bloqueo
    can_open, reason = guard.can_open_position("PAXGUSDT", "LONG", confluence_score=72.0, active_positions=active_positions)
    assert can_open is True
    assert "Aprobado" in reason

def test_elite_confluence_override():
    guard = ClusterRiskGuard(correlation_threshold=0.75, max_per_cluster=2)
    
    active_positions = {
        "SOLUSDT": {"signal": {"type": "LONG", "price": 180.0, "stop_loss": 175.0}, "smart_trailing": {"be_active": False}},
        "AVAXUSDT": {"signal": {"type": "LONG", "price": 30.0, "stop_loss": 29.0}, "smart_trailing": {"be_active": False}}
    }
    
    # INJUSDT con confluencia élite (90% >= 88%) debe ser autorizado por excepción institucional
    can_open, reason = guard.can_open_position("INJUSDT", "LONG", confluence_score=90.0, active_positions=active_positions)
    assert can_open is True
    assert "Élite" in reason