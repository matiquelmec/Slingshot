"""
engine/tests/test_hrp_and_omni_broker_suite.py
==============================================
Suite de Pruebas Unitarias para:
1. Hierarchical Risk Parity (HRP) Allocator (Marcos López de Prado).
2. Omni-Broker Prop-Firm Scaling Hub (Bitunix Cripto + FTMO MT5 TradFi).
"""

import pytest
import asyncio
import numpy as np
import pandas as pd

from engine.risk.hrp_allocator import HierarchicalRiskParityAllocator
from engine.execution.omni_broker_hub import OmniBrokerHub


def test_hrp_allocator_weight_calculation():
    """Valida la generación de pesos HRP sobre una matriz sintética multi-activo."""
    allocator = HierarchicalRiskParityAllocator(min_weight=0.05, max_weight=0.50)

    # Generar 60 observaciones de retornos para 4 activos (2 altamente correlacionados, 2 descorrelacionados)
    np.random.seed(42)
    n = 60
    base_crypto = np.random.normal(0, 0.02, n)
    btc_ret = base_crypto + np.random.normal(0, 0.005, n)
    eth_ret = base_crypto + np.random.normal(0, 0.005, n) # Alta correlación con BTC
    gold_ret = np.random.normal(0, 0.008, n) # Baja volatilidad y descorrelacionado
    nasdaq_ret = np.random.normal(0, 0.015, n)

    df_returns = pd.DataFrame({
        "BTCUSDT": btc_ret,
        "ETHUSDT": eth_ret,
        "XAUUSD": gold_ret,
        "US100": nasdaq_ret
    })

    weights = allocator.compute_hrp_weights(df_returns)

    assert len(weights) == 4
    # La suma de pesos debe ser aproximadamente 1.0 (tolerancia 0.01)
    total_w = sum(weights.values())
    assert abs(total_w - 1.0) < 0.01

    # El oro (XAUUSD), al tener menor volatilidad y descorrelación, debe recibir una ponderación saludable
    assert weights["XAUUSD"] >= allocator.min_weight
    assert weights["BTCUSDT"] <= allocator.max_weight
    assert weights["ETHUSDT"] <= allocator.max_weight


def test_hrp_trade_risk_modulation():
    """Verifica que el cálculo de riesgo en dólares modula según el peso HRP."""
    allocator = HierarchicalRiskParityAllocator()
    hrp_weights = {
        "BTCUSDT": 0.35, # Activo con mayor peso relativo (media = 0.25)
        "ETHUSDT": 0.25,
        "SOLUSDT": 0.15  # Activo con menor peso relativo
    }

    base_risk = 100.0
    # Activo sobreponderado recibe multiplicador > 1.0
    risk_btc = allocator.calculate_trade_risk_usd("BTCUSDT", base_risk, hrp_weights)
    assert risk_btc > base_risk

    # Activo subponderado recibe multiplicador < 1.0
    risk_sol = allocator.calculate_trade_risk_usd("SOLUSDT", base_risk, hrp_weights)
    assert risk_sol < base_risk


def test_omni_broker_symbol_routing():
    """Verifica que el hub enrute correctamente entre Bitunix y FTMO MT5."""
    hub = OmniBrokerHub()

    assert hub.get_target_broker("BTCUSDT") == "BITUNIX_CRYPTO"
    assert hub.get_target_broker("SOLUSDT") == "BITUNIX_CRYPTO"
    assert hub.get_target_broker("XAUUSD") == "FTMO_MT5"
    assert hub.get_target_broker("US100") == "FTMO_MT5"
    assert hub.get_target_broker("EURUSD") == "FTMO_MT5"


def test_omni_broker_risk_clamping_for_ftmo():
    """Verifica que el hub aplique el techo de seguridad de FTMO Guardian ($750)."""
    hub = OmniBrokerHub()
    hub.update_hrp_weights({"US100": 0.40, "BTCUSDT": 0.20})

    # Si se pide un riesgo elevado de $1000 para FTMO, debe limitarse al techo de $750
    risk_ftmo = hub.calculate_allocated_risk(symbol="US100", account_type="FTMO_MT5", base_risk_usd=1000.0)
    assert risk_ftmo <= 750.0


@pytest.mark.asyncio
async def test_omni_broker_consolidated_equity():
    """Verifica la generación del resumen consolidado de equidad multi-broker."""
    hub = OmniBrokerHub()
    hub.update_hrp_weights({"BTCUSDT": 0.50, "XAUUSD": 0.50})

    summary = await hub.get_consolidated_equity()
    assert "total_portfolio_equity" in summary
    assert "crypto_pool" in summary
    assert "tradfi_pool" in summary
    assert summary["tradfi_pool"]["equity"] >= 90000.0
    assert summary["hrp_assets_monitored"] == 2
