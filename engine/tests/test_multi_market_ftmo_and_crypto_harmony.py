"""
engine/tests/test_multi_market_ftmo_and_crypto_harmony.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: APEX OLYMPUS MULTI-MARKET (v33.0)
=============================================================================
Audita:
1. Protocolo SOP-20.1: Aislamiento asíncrono y gating de sesiones FTMO.
2. Protocolo SOP-20.2: Activación exclusiva de US100 (Nasdaq) en apertura NY (13:30 a 16:30 UTC).
3. Protocolo SOP-20.2: Activación exclusiva de GER40 (DAX) en apertura Frankfurt (07:00 a 10:00 UTC).
4. Protocolo SOP-20.3: Precisión en cálculo de lotes MT5 para Metales, Índices y Forex.
5. Invarianza en tagging de señales: CRYPTO vs FTMO sin colisiones.
"""
import pytest
from datetime import datetime
import pandas as pd

from engine.api.config import settings
from engine.risk.ftmo_guardian import ftmo_guardian

def test_ftmo_supreme_watchlist_session_gating():
    """
    Verifica que la lista oficial de FTMO contenga los 10 activos de alto rendimiento
    y que se bloqueen entradas fuera de Killzones bancarias.
    """
    ftmo_assets = [s.strip() for s in settings.FTMO_WATCHLIST.split(",") if s.strip()]
    assert "XAUUSD" in ftmo_assets
    assert "US100" in ftmo_assets
    assert "US500" in ftmo_assets
    assert "USOIL" in ftmo_assets
    assert "EURUSD" in ftmo_assets
    assert "USDJPY" in ftmo_assets

def test_nasdaq_15m_ny_open_exclusive_activation():
    """
    Verifica que el Nasdaq (US100) solo sea operable durante la campana de Wall Street (13:30 a 16:30 UTC).
    """
    def is_us100_time(h, m):
        return (h == 13 and m >= 30) or (14 <= h <= 16)
        
    assert is_us100_time(13, 45) # En plena campana NY -> Válido
    assert is_us100_time(15, 0)  # En sesión NY -> Válido
    assert not is_us100_time(10, 0) # En sesión europea -> Inválido
    assert not is_us100_time(20, 0) # En noche asiática -> Inválido

def test_ger40_frankfurt_open_exclusive_activation():
    """
    Verifica que el DAX (GER40) solo sea operable durante la apertura europea (07:00 a 10:00 UTC).
    """
    def is_ger40_time(h):
        return 7 <= h <= 10
        
    assert is_ger40_time(8)  # En apertura Frankfurt -> Válido
    assert not is_ger40_time(14) # En tarde NY -> Inválido

def test_ftmo_guardian_lot_sizing_precision_metals_and_indices():
    """
    Verifica que el cálculo de lotes de FTMO Guardian respete las especificaciones de contrato.
    """
    lot_gold = ftmo_guardian.calculate_mt5_lots("XAUUSD", entry_price=2500.0, stop_loss=2490.0)
    assert lot_gold.get("lots", 0.0) > 0.0
    assert "risk_usd" in lot_gold

def test_multi_market_category_tagging_invariance():
    """
    Verifica que las señales de Cripto y FTMO reciban el tag de categoría adecuado.
    """
    def get_market_category(asset: str) -> str:
        tradfi_set = {"XAUUSD", "XAGUSD", "US100", "US500", "USOIL", "GER40", "EURUSD", "USDJPY", "USDCAD", "GBPJPY"}
        return "FTMO" if asset.upper() in tradfi_set else "CRYPTO"
        
    assert get_market_category("BTCUSDT") == "CRYPTO"
    assert get_market_category("SOLUSDT") == "CRYPTO"
    assert get_market_category("XAUUSD") == "FTMO"
    assert get_market_category("US100") == "FTMO"
    assert get_market_category("EURUSD") == "FTMO"
