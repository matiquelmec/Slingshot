"""
scripts/tests/test_pipeline.py — Slingshot v4.1 Platinum
=========================================================
Test End-to-End del pipeline completo.
Descarga velas reales de Binance y verifica el pipeline SMC íntegro.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import pandas as pd
import httpx
from datetime import datetime


async def fetch_real_data(symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 500) -> pd.DataFrame:
    """Descarga velas reales de Binance REST."""
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        raw = r.json()

    df = pd.DataFrame(raw, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df


def _section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main():
    _section(f"🔬 TEST END-TO-END — SLINGSHOT v4.1 PLATINUM")
    print(f"⏱  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── 1. Datos reales de Binance ────────────────────────────────────────────
    _section("📡 FUENTE DE DATOS")
    df = await fetch_real_data("BTCUSDT", "15m", 500)
    assert len(df) >= 200, "❌ Datos insuficientes para el pipeline"
    print(f"✅ {len(df)} velas recibidas | Último cierre: ${df['close'].iloc[-1]:,.2f}")

    # ── 2. MarketAnalyzer (análisis puro) ────────────────────────────────────
    _section("📊 CAPA 1-3: MarketAnalyzer")
    from engine.router.analyzer import MarketAnalyzer
    analyzer = MarketAnalyzer()
    market_map = analyzer.analyze(df.copy(), asset="BTCUSDT", interval="15m")

    assert market_map.current_price > 0,              "❌ Precio inválido"
    assert market_map.market_regime is not None,      "❌ Régimen no detectado"
    assert isinstance(market_map.smc, dict),          "❌ SMC data inválida"
    assert isinstance(market_map.key_levels, list),   "❌ Key levels inválidos"

    print(f"✅ Régimen actual: {market_map.market_regime}")
    print(f"   OBs Alcistas: {len(market_map.smc.get('order_blocks', {}).get('bullish', []))}")
    print(f"   OBs Bajistas: {len(market_map.smc.get('order_blocks', {}).get('bearish', []))}")
    print(f"   FVGs: {len(market_map.smc.get('fvgs', {}).get('bullish', []))} bull / "
          f"{len(market_map.smc.get('fvgs', {}).get('bearish', []))} bear")
    print(f"   Fibonacci: {'✅' if market_map.fibonacci else '⚠️ No disponible'}")

    # ── 3. SMC Strategy (detección de oportunidades) ─────────────────────────
    _section("🏛️ MOTOR SMC: SMCInstitutionalStrategy")
    from engine.strategies.smc import SMCInstitutionalStrategy
    strategy = SMCInstitutionalStrategy()
    df_analyzed = strategy.analyze(market_map.df_analyzed.copy())
    opportunities = strategy.find_opportunities(df_analyzed)
    print(f"✅ Oportunidades detectadas (sin filtrar): {len(opportunities)}")

    # ── 4. SlingshotRouter (pipeline completo) ────────────────────────────────
    _section("🧠 PIPELINE COMPLETO: SlingshotRouter")
    from engine.main_router import SlingshotRouter
    router = SlingshotRouter()
    result = router.process_market_data(df.copy(), asset="BTCUSDT", interval="15m")

    assert "signals" in result,         "❌ 'signals' no encontrado en resultado"
    assert "blocked_signals" in result, "❌ 'blocked_signals' no encontrado en resultado"
    assert "market_regime" in result,   "❌ 'market_regime' no encontrado en resultado"
    assert "smc" in result,             "❌ 'smc' no encontrado en resultado"

    print(f"✅ Estrategia activa: {result['active_strategy']}")
    print(f"   Señales aprobadas:  {len(result['signals'])}")
    print(f"   Señales bloqueadas: {len(result['blocked_signals'])}")

    if result["signals"]:
        for s in result["signals"]:
            score = s.get("confluence", {}).get("score", "?") if s.get("confluence") else "?"
            print(f"   🎯 {s.get('type')} @ ${s.get('price', 0):,.2f} | Score: {score}% | Leverage: {s.get('leverage')}x")
    else:
        print("   ℹ️  Sin señales aprobadas (normal si no hay confluencia institucional)")

    if result["blocked_signals"]:
        print(f"\n   📋 Muestra de señales bloqueadas (Modo Auditoría):")
        for s in result["blocked_signals"][:3]:
            print(f"   🔴 {s.get('status')} | {s.get('blocked_reason', 'N/A')[:60]}")

    # ── 5. Ghost Data (contexto macro) ───────────────────────────────────────
    _section("👻 CONTEXTO MACRO: GhostData")
    try:
        from engine.indicators.ghost_data import refresh_ghost_data
        ghost = await refresh_ghost_data("BTCUSDT")
        print(f"✅ Fear & Greed: {ghost.fear_greed_value} ({ghost.fear_greed_label})")
        print(f"   BTC Dominance: {ghost.btc_dominance}%")
        print(f"   Funding Rate:  {ghost.funding_rate:.4f}%")
        print(f"   Macro Bias:    {ghost.macro_bias}")
    except Exception as e:
        print(f"⚠️  GhostData no disponible (puede ser normal): {e}")

    _section("✅ TEST COMPLETADO — SLINGSHOT v4.1 PLATINUM")


if __name__ == "__main__":
    asyncio.run(main())
