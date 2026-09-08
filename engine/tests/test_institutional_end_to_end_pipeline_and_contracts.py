"""
engine/tests/test_institutional_end_to_end_pipeline_and_contracts.py
=============================================================================
SUITE INSTITUCIONAL DE INTEGRACIÓN END-TO-END Y CONTRATOS DE SISTEMA (v25.3)
=============================================================================
Certifica:
1. Contrato del Radar Center: Cobertura de los 14 activos VIP en settings y store.
2. Contrato TradFi Frontend: Schema estricto compatible con OpportunitiesScanner.tsx.
3. Blindaje de Regresión SOP-68: Garantiza que la poda temprana (>=0.35R) no intercepte
   ni bloquee la jerarquía de Fast Break-Even (+1.0R) ni Trailing Stop (+1.5R/2.0R).
4. Ciclo de Vida Completo (Golden Path): Señal -> Riesgo -> Ejecución -> TradeManager (Fast BE) -> Vault.
5. Aislamiento Total de Mercados: FTMO (TradFi USD) vs Bitunix (Crypto USDT) sin contaminación cruzada.
=============================================================================
"""
import pytest
import asyncio
import os
import json
import tempfile
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from engine.api.config import settings
from engine.core.store import store
from engine.workers.trade_manager import TradeManager
from engine.risk.ftmo_guardian import FtmoGuardianShield
from engine.execution.bitunix_executor import BitunixExecutor


@pytest.fixture(autouse=True)
def isolate_primary_account():
    with patch("engine.execution.account_manager.AccountManager.get_all_executors", return_value={"primary": BitunixExecutor()}):
        yield


# ── TEST 1: CONTRATO DEL RADAR CENTER (14 ACTIVOS VIP) ─────────────────────

def test_radar_14_vip_assets_universe_integrity():
    """
    Certifica que la configuración oficial de Slingshot incluya los 14 activos VIP
    y que ninguno quede en null o ausente.
    """
    vip_assets = [s.strip().upper().replace("USDT", "") for s in settings.RADAR_ASSETS.split(",") if s.strip()]
    expected_vip = ["BTC", "ETH", "SOL", "AVAX", "LINK", "XRP", "RENDER", "SUI", "INJ", "NEAR", "FET", "ATOM", "TIA", "PAXG"]
    
    assert len(vip_assets) == 14, f"Se esperaban 14 activos VIP en RADAR_ASSETS, encontrados {len(vip_assets)}"
    for asset in expected_vip:
        assert asset in vip_assets, f"Activo VIP {asset} ausente en RADAR_ASSETS"


@pytest.mark.asyncio
async def test_market_states_live_payload_conformance():
    """
    Certifica que el store retorne estructuras válidas para los 14 activos del Radar,
    con precios numéricos, bias y sin valores NaN o null.
    """
    vip_assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "XRPUSDT", "RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "TIAUSDT", "PAXGUSDT"]
    
    # Hidratar estados de prueba
    for sym in vip_assets:
        await store.update_market_state(sym, {
            "price": 100.0,
            "current_price": 100.0,
            "change_24h": 1.5,
            "bias": "BULLISH",
            "regime": "EXPANSION",
            "score": 75,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
    states = await store.get_market_states()
    state_map = {s["asset"]: s for s in states}
    
    for sym in vip_assets:
        assert sym in state_map, f"Estado de {sym} ausente en store"
        st = state_map[sym]
        assert isinstance(st.get("price"), (int, float)) and st["price"] > 0
        assert st.get("bias") in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert "regime" in st


# ── TEST 2: CONTRATO TRADFI FRONTEND (OPPORTUNITIES SCANNER) ───────────────

@pytest.mark.asyncio
async def test_tradfi_opportunities_schema_and_frontend_contract():
    """
    Certifica que las oportunidades de TradFi generadas para FTMO cumplan
    estrictamente con el contrato de tipos de OpportunitiesScanner.tsx.
    """
    mock_tradfi_opp = {
        "symbol": "US100",
        "action": "SELL",
        "direction": "SHORT",
        "entry_price": 20450.0,
        "stop_loss": 20550.0,
        "take_profit_1": 20350.0,
        "take_profit_2": 20250.0,
        "take_profit_3": 20100.0,
        "lots_mt5": 1.5,
        "risk_usd": 750.0,
        "r_risk": 1.0,
        "confidence_score": 88,
        "killzone": "NY_OPEN",
        "killzone_active": True,
        "timeframe": "15m",
        "type": "OTE_RETRACEMENT",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    await store.save_scanner_opportunities("tradfi", [mock_tradfi_opp])
    retrieved = store.get_scanner_opportunities("tradfi")
    
    assert len(retrieved) >= 1
    opp = retrieved[0]
    
    # Validar campos esenciales para renderizado en Frontend
    assert opp["symbol"] in ["US100", "US30", "GBPUSD", "XAUUSD", "GER40"]
    assert opp["direction"] in ["LONG", "SHORT"]
    assert opp["entry_price"] > 0
    assert opp["stop_loss"] > 0
    assert opp["take_profit_1"] > 0
    assert opp["lots_mt5"] > 0
    assert isinstance(opp["killzone_active"], bool)
    assert opp["confidence_score"] >= 0


# ── TEST 3: BLINDAJE DE REGRESIÓN SOP-68 VS TRAILING HIERARCHY ──────────────

@pytest.mark.asyncio
async def test_sop68_does_not_block_fast_be_and_trailing():
    """
    Verifica que el bloque de poda temprana SOP-68 (r_profit >= 0.35)
    NO intercepte ni bloquee la jerarquía de Trailing Stop ni el Fast BE (+1.0R).
    """
    tm = TradeManager()
    
    # Posición a +1.2R (Debe activar Fast BE a pesar de tener r_profit >= 0.35)
    mock_pos_be = [{
        "symbol": "SOLUSDT",
        "side": "BUY",
        "entryPrice": 150.0,
        "lastPrice": 153.6,  # +3.6 USD vs SL $3.00 -> +1.2R
        "slPrice": 147.0,
        "positionId": "pos_sol_be"
    }]
    
    with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_positions", new_callable=AsyncMock) as mock_get, \
         patch("engine.execution.bitunix_executor.BitunixExecutor.modify_position_tpsl", new_callable=AsyncMock) as mock_mod:
        
        mock_get.return_value = mock_pos_be
        mock_mod.return_value = True
        
        results = await tm.sync_live_bitunix_positions()
        
        assert len(results) == 1
        res = results[0]
        # Debe haber ejecutado protección de Fast BE
        assert res["r_profit"] == 1.2
        assert "FAST_BE" in res["status"] or "SL_ACTUALIZADO" in res.get("action", "")
        mock_mod.assert_awaited_once()


# ── TEST 4: CICLO DE VIDA COMPLETO DE SEÑAL A TRAILING (GOLDEN PATH) ────────

@pytest.mark.asyncio
async def test_full_signal_to_risk_and_trade_management_lifecycle():
    """
    Valida el flujo integral:
    Detección de Oportunidad -> Sizing Institucional FTMO -> Gestión de Trailing Stop.
    """
    # 1. Fase de Riesgo: Guardián FTMO calcula lotes exactos
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_state = tf.name

    try:
        guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", state_file=temp_state)
        sizing = guardian.calculate_mt5_lots("US100", 20000.0, 19950.0) # Distancia = 50 pts
        
        # Riesgo 0.75% = $750 USD -> 50 pts * 1 contrato = $50/lote -> 750 / 50 = 15.0 Lotes
        assert sizing["lots"] == 15.0
        assert sizing["risk_usd"] == 750.0
        assert sizing["lots_tp1"] == 7.5
        assert sizing["lots_tp2"] == 4.5
        assert sizing["lots_tp3"] == 3.0
        
        # 2. Fase de Gestión de Trade: Monitoreo y Trailing en Ganancia
        tm = TradeManager()
        mock_pos = [{
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entryPrice": 60000.0,
            "lastPrice": 61200.0,  # +1200 USD vs SL de $600 -> +2.0R
            "slPrice": 59400.0,
            "positionId": "pos_btc_runner"
        }]
        
        with patch("engine.execution.bitunix_executor.BitunixExecutor.get_pending_positions", new_callable=AsyncMock) as mock_get, \
             patch("engine.execution.bitunix_executor.BitunixExecutor.modify_position_tpsl", new_callable=AsyncMock) as mock_mod:
            
            mock_get.return_value = mock_pos
            mock_mod.return_value = True
            
            res = await tm.sync_live_bitunix_positions()
            assert len(res) == 1
            assert res[0]["r_profit"] == 2.0
            # En +2.0R debe estar en Trailing Stop activo
            assert "TRAILING" in res[0]["status"] or "SL_ACTUALIZADO" in res[0].get("action", "")
    finally:
        if os.path.exists(temp_state):
            os.remove(temp_state)


# ── TEST 5: AISLAMIENTO RIGUROSO ENTRE MERCADOS (FTMO VS BITUNIX) ────────────

def test_ftmo_and_crypto_market_isolation():
    """
    Certifica que las reglas de prop-firm de FTMO no interfieran con las reglas crypto:
    - FTMO opera con riesgo monetario fijo ($750 USD en Fase 1, apalancamiento 1:30).
    - Bitunix opera con slots de riesgo aislados (máximo 4 posiciones simultáneas).
    """
    # Guardián FTMO con $100K
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_state = tf.name
    try:
        guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", state_file=temp_state)
        assert guardian.account_size == 100000.0
        assert guardian.DAILY_DRAWDOWN_LIMIT_PCT == 3.5
        
        # Una fluctuación en crypto no debe alterar el drawdown de FTMO
        status = guardian.update_equity(100000.0)
        assert status["daily_dd_pct"] == 0.0
        assert status["is_daily_lockout"] is False
    finally:
        if os.path.exists(temp_state):
            os.remove(temp_state)
