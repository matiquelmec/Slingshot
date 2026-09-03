import asyncio
import os
import sys
import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from engine.api.config import settings
from engine.api.ws_manager import fetch_binance_history
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.main_router import SlingshotRouter
from engine.core.store import store
from engine.router.gatekeeper import SignalGatekeeper, GatekeeperContext
from engine.risk.risk_manager import RiskManager

async def run_audit():
    print("==================================================")
    print("SLINGSHOT DIAGNOSTIC & AUDIT: SIGNAL VETOES")
    print("==================================================")

    # Load assets
    assets = settings.MASTER_WATCHLIST
    print(f"Master watchlist: {assets}")
    
    # Initialize components
    strategy = SMCInstitutionalStrategy()
    risk_mgr = RiskManager(account_balance=settings.ACCOUNT_BALANCE, base_risk_pct=settings.MAX_RISK_PCT)
    gatekeeper = SignalGatekeeper(risk_mgr)

    # Let's populate macro contexts so the Gatekeeper doesn't run with empty/default fields
    import engine.indicators.macro as macro
    from engine.indicators.ghost_data import refresh_ghost_data
    try:
        await macro.update_macro_context()
        m_ctx = macro.get_macro_context()
        await refresh_ghost_data(global_only=True, macro_ctx=m_ctx)
        print("Macro/Ghost context hydrated successfully.")
    except Exception as e:
        print(f"Warning hydrating macro context: {e}")

    # For each asset, fetch 15m data and check the last 20 candles for signals
    for symbol in assets:
        print(f"\n--- Analizando {symbol} (15m) ---")
        history = await fetch_binance_history(symbol, "15m", limit=500)
        if not history:
            print(f"Error: No se pudo obtener historial para {symbol}")
            continue
        
        df = pd.DataFrame([i["data"] for i in history])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        
        # Run analyze on the df to generate indicators
        df_analyzed = strategy.analyze(df, interval="15m")
        
        # Let's see: how many candles have long_A, long_B, short_A, short_B triggered in the last 20 candles?
        # We can extract the conditions manually to check history
        df_temp = df_analyzed.copy()
        is_retesting_bull = (df_temp['low'] <= df_temp['ob_bull_top']) & (df_temp['close'] >= df_temp['ob_bull_bottom'])
        is_retesting_bear = (df_temp['high'] >= df_temp['ob_bear_bottom']) & (df_temp['close'] <= df_temp['ob_bear_top'])
        
        long_A = df_temp['recent_ob_bull'] & (df_temp['recent_sweep_bull'] | is_retesting_bull) & df_temp['recent_fvg_bull']
        short_A = df_temp['recent_ob_bear'] & (df_temp['recent_sweep_bear'] | is_retesting_bear) & df_temp['recent_fvg_bear']
        
        long_B = ((df_temp['recent_ob_bull'] & df_temp['recent_sweep_bull']) | (df_temp['recent_sweep_bull'] & df_temp['recent_fvg_bull'])) & ~long_A
        short_B = ((df_temp['recent_ob_bear'] & df_temp['recent_sweep_bear']) | (df_temp['recent_sweep_bear'] & df_temp['recent_fvg_bear'])) & ~short_A
        
        total_long_A = long_A.sum()
        total_short_A = short_A.sum()
        total_long_B = long_B.sum()
        total_short_B = short_B.sum()
        
        print(f"Oportunidades históricas en 500 velas:")
        print(f"  - Tier A Longs: {total_long_A} | Shorts: {total_short_A}")
        print(f"  - Tier B Longs: {total_long_B} | Shorts: {total_short_B}")

        # Let's find index where opportunities occurred and pass them to Gatekeeper to see what happens
        # We can simulate running the process_market_data or gatekeeper for these signals
        router = SlingshotRouter()
        
        # Run process_market_data for the last index
        # Let's see what happens on the live index
        result = await router.process_market_data(df, asset=symbol, interval="15m", silent=True)
        approved = result.get("signals", [])
        blocked = result.get("blocked_signals", [])
        
        print(f"Vela actual (en vivo):")
        print(f"  - Aprobadas: {len(approved)}")
        for s in approved:
            print(f"    [APROBADA] {s.get('type')} {s.get('signal_type')} @ {s.get('price')} | Score: {s.get('confluence', {}).get('score')}%")
        print(f"  - Bloqueadas: {len(blocked)}")
        for s in blocked:
            print(f"    [BLOQUEADA] {s.get('type')} {s.get('signal_type')} @ {s.get('price')} | Razón: {s.get('blocked_reason') or s.get('rejection_reason')}")

if __name__ == "__main__":
    asyncio.run(run_audit())
