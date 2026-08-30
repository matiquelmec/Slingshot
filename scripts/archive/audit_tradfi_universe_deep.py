import asyncio
import httpx
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.indicators.polars_engine import polars_engine
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

ASSET_CANDIDATES = {
    "XAUUSD": {"ticker": "GC=F", "name": "Oro Spot (Gold)"},
    "XAGUSD": {"ticker": "SI=F", "name": "Plata Spot (Silver)"},
    "USOIL":  {"ticker": "CL=F", "name": "Petróleo WTI (Crude Oil)"},
    "US100":  {"ticker": "NQ=F", "name": "Nasdaq 100 (Tech Index)"},
    "US30":   {"ticker": "YM=F", "name": "Dow Jones 30 (Industrial)"},
    "US500":  {"ticker": "ES=F", "name": "S&P 500 (Market Cap)"},
    "HGUSD":  {"ticker": "HG=F", "name": "Cobre (Copper High Grade)"},
    "GBPUSD": {"ticker": "GBPUSD=X", "name": "Libra Esterlina / Dólar"},
    "EURUSD": {"ticker": "EURUSD=X", "name": "Euro / Dólar"},
}

async def fetch_and_save_data():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Configuraciones por timeframe
    timeframe_configs = [
        ("15m", "60d"),
        ("1h", "2y"),
        ("1d", "5y")
    ]
    
    saved_matrix = {}
    
    async with httpx.AsyncClient(timeout=20.0, verify=False) as client:
        for sym, meta in ASSET_CANDIDATES.items():
            ticker = meta["ticker"]
            saved_matrix[sym] = {}
            for interval, yf_range in timeframe_configs:
                yf_interval = "1d" if interval == "1d" else interval
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={yf_range}&interval={yf_interval}"
                try:
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
                        
                        if len(df) >= 50:
                            fname = f"{sym}_{interval}_audited.parquet"
                            fpath = os.path.join(DATA_DIR, fname)
                            df.to_parquet(fpath, index=False)
                            saved_matrix[sym][interval] = fpath
                except Exception as e:
                    pass
    return saved_matrix

def run_deep_intelligent_audit():
    print("\n" + "="*110)
    print("🧠 AUDITORÍA INTELIGENTE MULTI-ACTIVO: COMMODITIES, METALES, ÍNDICES Y FOREX (15m, 1h, 1D)")
    print("="*110)
    
    # 1. Descarga y sincronización
    saved_matrix = asyncio.run(fetch_and_save_data())
    
    engine = UnifiedBacktestEngine(min_confluence_score=50)
    btc_map = engine._load_btc_macro_map()
    
    all_results = []
    
    for sym, intervals in saved_matrix.items():
        meta = ASSET_CANDIDATES[sym]
        for interval, fpath in intervals.items():
            try:
                trades = engine.run_single_asset(sym, interval=interval, btc_map=btc_map)
                df_trades = pd.DataFrame(trades)
                if df_trades.empty:
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
                
                # Drawdown
                df_trades['pnl_usd'] = df_trades['outcome_r'] * 1000.0
                df_trades['cum'] = df_trades['pnl_usd'].cumsum()
                df_trades['equity'] = 100000.0 + df_trades['cum']
                df_trades['dd'] = (df_trades['equity'] - df_trades['equity'].cummax()) / df_trades['equity'].cummax() * 100
                max_dd = abs(df_trades['dd'].min())
                
                # Calificación cuantitativa (Score Alpha)
                # Score = (Total R * Profit Factor) / (1 + Max DD)
                alpha_score = (max(0, total_r) * pf) / (1.0 + (max_dd / 10.0))
                
                recommendation = "💎 ELITE ALPHA" if (total_r > 20 and pf >= 1.30 and max_dd < 15) else (
                    "🟢 VIABLE" if (total_r > 0 and pf >= 1.05) else "❌ RECHAZADO / TÓXICO"
                )

                all_results.append({
                    "Activo": sym,
                    "Nombre": meta["name"],
                    "Timeframe": interval,
                    "Trades": n_trades,
                    "Win Rate": f"{wr:.1f}%",
                    "BE Rate": f"{be_rate:.1f}%",
                    "Retorno Total": round(total_r, 2),
                    "Profit Factor": round(pf, 2),
                    "Max DD": f"-{max_dd:.1f}%",
                    "Alpha Score": round(alpha_score, 1),
                    "Veredicto Cuantitativo": recommendation
                })
            except Exception as e:
                pass

    df_res = pd.DataFrame(all_results)
    if not df_res.empty:
        # Ordenar por Retorno Total y Alpha Score
        df_sorted = df_res.sort_values(by=["Retorno Total", "Alpha Score"], ascending=[False, False])
        
        print("\n🏆 RANKING DE ACTIVOS INSTITUCIONALES (DE MAYOR A MENOR RENDIMIENTO):\n")
        cols_display = ["Activo", "Nombre", "Timeframe", "Trades", "Win Rate", "Retorno Total", "Profit Factor", "Max DD", "Veredicto Cuantitativo"]
        print(df_sorted[cols_display].to_string(index=False))
        
        print("\n" + "="*110)
        print("💡 RESUMEN DE LOS MEJORES ACTIVOS DESCUBIERTOS:")
        print("="*110)
        top_elites = df_sorted[df_sorted["Veredicto Cuantitativo"].str.contains("ELITE|VIABLE")].head(6)
        for _, row in top_elites.iterrows():
            print(f"⭐ {row['Activo']} ({row['Nombre']}) en {row['Timeframe']}: Retorno {row['Retorno Total']:+.2f} R | Win Rate {row['Win Rate']} | PF {row['Profit Factor']} | DD {row['Max DD']}")
    else:
        print("No se encontraron resultados.")

if __name__ == "__main__":
    run_deep_intelligent_audit()
