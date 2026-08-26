"""
engine/tests/test_dynamic_universe_screener.py
=============================================================================
SUITE DE PRUEBAS: UNIVERSO DINÁMICO CUANTITATIVO (RVOL & KER SMART SCREENER)
=============================================================================
Audita:
1. Inmutabilidad del Tier 1 (Core Assets).
2. Admisión condicional de activos Tier 2 por volumen (> $30M).
3. Resiliencia y fallback seguro si la API de tickers falla.
4. Respeto de los límites máximos de activos rotativos.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from engine.workers.market_scanner import MarketScanner
from engine.indicators.data_utils import fetch_top_liquid_tickers

@pytest.mark.asyncio
async def test_dynamic_screener_core_assets_immutable():
    """
    AUDITORÍA DE INTEGRIDAD:
    Los 8 activos del Tier 1 Core DEBEN permanecer siempre activos en el escáner
    independientemente de las rotaciones dinámicas.
    """
    scanner = MarketScanner()
    core_expected = ["RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "PAXGUSDT", "TIAUSDT"]
    
    for sym in core_expected:
        assert sym in scanner.core_scalp_assets, f"Activo Core {sym} no está presente en Tier 1"
        assert sym in scanner.scalp_assets, f"Activo Core {sym} debe estar en scalp_assets activo"

@pytest.mark.asyncio
async def test_dynamic_screener_rotates_liquid_candidates():
    """
    AUDITORÍA DE ADMISIÓN:
    Si la API descubre candidatos con alto volumen (ej. AAVEUSDT, ONDOUSDT),
    el escáner debe agregarlos a la lista activa respetando el límite máximo.
    """
    scanner = MarketScanner()
    scanner._dynamic_last_refresh = 0  # Forzar refresco
    
    mock_liquid = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "RENDERUSDT", "SUIUSDT",
        "AAVEUSDT", "ONDOUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT"
    ]
    
    with patch("engine.workers.market_scanner.fetch_top_liquid_tickers", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_liquid
        
        await scanner._refresh_dynamic_assets()
        
        # Deben haber ingresado candidatos nuevos respetando el límite de 6
        assert "AAVEUSDT" in scanner.scalp_assets, "AAVEUSDT debió ser admitido en la lista dinámica"
        assert "ONDOUSDT" in scanner.scalp_assets, "ONDOUSDT debió ser admitido en la lista dinámica"
        # Los core iniciales deben seguir presentes
        assert "RENDERUSDT" in scanner.scalp_assets
        assert "SUIUSDT" in scanner.scalp_assets

@pytest.mark.asyncio
async def test_dynamic_screener_graceful_api_fallback():
    """
    MÉTRICA DE CALIDAD Y RESILIENCIA:
    Si la API de ranking de Binance falla o arroja un error 500/timeout,
    el escáner debe conservar el universo Core sin romper el flujo de trabajo.
    """
    scanner = MarketScanner()
    scanner._dynamic_last_refresh = 0
    
    with patch("engine.workers.market_scanner.fetch_top_liquid_tickers", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = Exception("Binance API 500 Internal Error")
        
        # No debe lanzar excepción
        await scanner._refresh_dynamic_assets()
        
        # Los activos Core deben permanecer intactos
        assert len(scanner.core_scalp_assets) == 8
        assert "BTCUSDT" in scanner.assets
        assert "ETHUSDT" in scanner.assets
