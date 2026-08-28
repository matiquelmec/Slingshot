import os
import httpx
import pandas as pd
import numpy as np
import asyncio
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.indicators.polars_engine import polars_engine
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

MT5_CANDIDATES = [
    # 🏛️ Índices Europeos y Globales
    ("GER40", "^GDAXI", "Dax 40 (Alemania)", "INDICE_EU", 25.0, 1.5),
    ("UK100", "^FTSE", "FTSE 100 (Reino Unido)", "INDICE_UK", 10.0, 1.2),
    ("JP225", "^N225", "Nikkei 225 (Japón)", "INDICE_ASIA", 5.0, 4.0),
    ("US2000", "^RUT", "Russell 2000 (Small Caps US)", "INDICE_US", 10.0, 0.3),
    
    # 💱 Forex Majors & Cruces
    ("EURUSD", "EURUSD=X", "Euro / US Dollar", "FOREX_MAJOR", 100000.0, 0.0001),
    ("GBPUSD", "GBPUSD=X", "British Pound / US Dollar", "FOREX_MAJOR", 100000.0, 0.00015),
    ("USDJPY", "JPY=X", "US Dollar / Japanese Yen", "FOREX_MAJOR", 100000.0, 0.015),
    ("GBPJPY", "GBPJPY=X", "British Pound / Japanese Yen", "FOREX_CROSS", 100000.0, 0.025),
    ("AUDUSD", "AUDUSD=X", "Australian Dollar / US Dollar", "FOREX_MAJOR", 100000.0, 0.00012),
    ("USDCAD", "CAD=X", "US Dollar / Canadian Dollar", "FOREX_MAJOR", 100000.0, 0.00015),
    
    # ⚡ Commodities y Energías
    ("NATGAS", "NG=F", "Gas Natural (Henry Hub)", "COMMODITY_ENERGY", 10000.0, 0.005)
]

async def download_candidate_httpx(sym, ticker, tf):
    yf_interval = "15m" if tf == "15m" else ("1h" if tf == "1h" else "1d")
    yf_range = "60d" if tf == "15m" else ("730d" if tf == "1h" else "5y")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={yf_range}&interval={yf_interval}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                return None
            data = res.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            
            timestamps = result[0].get("timestamp", [])
            quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
            
            df = pd.DataFrame({
                "timestamp": pd.to_datetime(timestamps, unit="s"),
                "open": quotes.get("open", []),
                "high": quotes.get("high", []),
                "low": quotes.get("low", []),
                "close": quotes.get("close", []),
                "volume": quotes.get("volume", [0] * len(timestamps))
            }).dropna()
            
            if df.empty or len(df) < 50:
                return None

            df['volume'] = df['volume'].fillna(100.0)
            df = df.sort_values('timestamp').reset_index(drop=True)
            out_path = os.path.join(DATA_DIR, f"{sym}_{tf}_audited.parquet")
            df.to_parquet(out_path, index=False)
            return df
    except Exception as e:
        return None

async def run_expanded_audit():
    print("\n" + "="*115)
    print("🌍 AUDITORÍA CUANTITATIVA EXPANDIDA: UNIVERSO METATRADER 5 / FTMO (15m, 1H, 1D)")
    print("="*115)

    engine = UnifiedBacktestEngine(min_confluence_score=50)
    btc_map = engine._load_btc_macro_map()

    results = []

    for sym, ticker, name, cat, c_size, spread in MT5_CANDIDATES:
        for tf in ["15m", "1h", "1d"]:
            df = await download_candidate_httpx(sym, ticker, tf)
            if df is None:
                continue
            try:
                trades = engine.run_single_asset(sym, interval=tf, btc_map=btc_map)
                if not trades or len(trades) < 4:
                    continue

                df_trades = pd.DataFrame(trades)
                n = len(df_trades)
                winners = df_trades[df_trades['outcome_r'] > 0]
                losers = df_trades[df_trades['outcome_r'] < 0]
                be = df_trades[df_trades['outcome_r'] == 0]

                wr = len(winners) / n * 100.0
                total_r = df_trades['outcome_r'].sum()
                gross_w = winners['outcome_r'].sum() if len(winners) > 0 else 0
                gross_l = abs(losers['outcome_r'].sum()) if len(losers) > 0 else 1
                pf = gross_w / gross_l if gross_l > 0 else 99.0

                df_trades['equity'] = 100000.0 + (df_trades['outcome_r'] * 1000.0).cumsum()
                df_trades['dd'] = (df_trades['equity'] - df_trades['equity'].cummax()) / df_trades['equity'].cummax() * 100
                max_dd = abs(df_trades['dd'].min())

                results.append({
                    "Activo MT5": sym,
                    "Nombre": name,
                    "Categoría": cat,
                    "TF": tf,
                    "Trades": n,
                    "Win Rate": f"{wr:.1f}%",
                    "Profit Factor": round(pf, 2),
                    "Retorno Total R": round(total_r, 2),
                    "Max DD": f"-{max_dd:.1f}%"
                })
            except Exception as e:
                pass

    df_res = pd.DataFrame(results)
    if not df_res.empty:
        print("\n📊 RESULTADOS DE TODOS LOS ACTIVOS METATRADER 5 EVALUADOS:\n")
        print(df_res.sort_values(by="Retorno Total R", ascending=False).to_string(index=False))

        print("\n" + "="*115)
        print("🏆 ACTIVOS DESCUBIERTOS CON ALPHA INSTITUCIONAL POSITIVO (PROFIT FACTOR > 1.40):")
        print("="*115)
        positive = df_res[df_res['Profit Factor'] >= 1.40].sort_values(by="Retorno Total R", ascending=False)
        for idx, (_, row) in enumerate(positive.iterrows(), 1):
            print(f"{idx}. ⭐ {row['Activo MT5']} ({row['Nombre']}) en {row['TF']}: Retorno: {row['Retorno Total R']:+.2f} R | Win Rate: {row['Win Rate']} | PF: {row['Profit Factor']} | Max DD: {row['Max DD']}")
    else:
        print("No se generaron resultados.")

if __name__ == "__main__":
    asyncio.run(run_expanded_audit())
