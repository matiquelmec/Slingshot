import asyncio
import httpx
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.indicators.polars_engine import polars_engine
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

async def download_and_backtest_oil():
    print("🛢️ Descargando datos históricos de Petróleo Crudo WTI (CL=F / USOIL)...")
    ticker = "CL=F"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Descargar 15m (60 días) y 1h (730 días)
    configs = [
        ("15m", "60d", "USOIL_15m_60d.parquet"),
        ("1h", "2y", "USOIL_1h_2y.parquet")
    ]
    
    saved_files = {}
    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        for interval, yf_range, filename in configs:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={yf_range}&interval={interval}"
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                result = res.json()["chart"]["result"][0]
                timestamps = result["timestamp"]
                quotes = result["indicators"]["quote"][0]
                
                df = pd.DataFrame({
                    "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
                    "open": quotes["open"],
                    "high": quotes["high"],
                    "low": quotes["low"],
                    "close": quotes["close"],
                    "volume": quotes.get("volume", [1000]*len(timestamps))
                }).dropna().sort_values("timestamp").reset_index(drop=True)
                
                file_path = os.path.join(DATA_DIR, filename)
                df.to_parquet(file_path, index=False)
                saved_files[interval] = (file_path, len(df))
                print(f"✅ Guardado {filename}: {len(df)} velas.")
            else:
                print(f"❌ Error descargando {interval}: {res.status_code}")

    # 2. Ejecutar Backtest con Unified Truth Engine
    engine = UnifiedBacktestEngine(min_confluence_score=50)
    btc_map = engine._load_btc_macro_map()
    
    results_summary = []
    
    for interval in ["15m", "1h"]:
        if interval not in saved_files:
            continue
        file_path, count = saved_files[interval]
        
        # Correr simulación con run_single_asset
        trades = engine.run_single_asset("USOIL", interval=interval, btc_map=btc_map)
        df_trades = pd.DataFrame(trades)
        
        if df_trades.empty:
            print(f"⚠️ No se generaron trades para USOIL en {interval}")
            continue
            
        n_trades = len(df_trades)
        winners = df_trades[df_trades['outcome_r'] > 0]
        losers = df_trades[df_trades['outcome_r'] < 0]
        be = df_trades[df_trades['outcome_r'] == 0]
        
        wr = len(winners) / n_trades * 100
        be_rate = len(be) / n_trades * 100
        total_r = df_trades['outcome_r'].sum()
        gross_w = winners['outcome_r'].sum() if len(winners) > 0 else 0
        gross_l = abs(losers['outcome_r'].sum()) if len(losers) > 0 else 1
        pf = gross_w / gross_l if gross_l > 0 else 99.0
        
        df_trades['pnl_usd'] = df_trades['outcome_r'] * 1000.0
        df_trades['cum'] = df_trades['pnl_usd'].cumsum()
        df_trades['equity'] = 100000.0 + df_trades['cum']
        df_trades['dd'] = (df_trades['equity'] - df_trades['equity'].cummax()) / df_trades['equity'].cummax() * 100
        max_dd = abs(df_trades['dd'].min())
        
        results_summary.append({
            "Activo": "USOIL (WTI Crude Oil)",
            "Timeframe": interval,
            "Velas Analizadas": count,
            "Total Trades": n_trades,
            "Win Rate": f"{wr:.1f}%",
            "BE Rate": f"{be_rate:.1f}%",
            "Retorno Neto": f"{total_r:+.2f} R",
            "Profit Factor": f"{pf:.2f}",
            "Max Drawdown": f"-{max_dd:.2f}%"
        })

    print("\n" + "="*95)
    print("🛢️ REPORTE DE AUDITORÍA Y RENDIMIENTO: PETRÓLEO CRUDO WTI (USOIL) CON SLINGSHOT")
    print("="*95)
    if results_summary:
        print(pd.DataFrame(results_summary).to_string(index=False))
    else:
        print("Sin resultados.")

if __name__ == "__main__":
    asyncio.run(download_and_backtest_oil())
