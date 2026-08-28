import os
import glob
import pandas as pd
import numpy as np
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

def run_multi_timeframe_matrix_audit():
    print("\n" + "="*115)
    print("🔬 AUDITORÍA CUANTITATIVA MULTI-TEMPORALIDAD: 15m vs 1H vs 4H vs 1D")
    print("="*115)

    engine = UnifiedBacktestEngine(min_confluence_score=50)
    btc_map = engine._load_btc_macro_map()

    # 1. Activos representativos por categoría
    test_assets = [
        # Mega-Caps Cripto
        ("BTCUSDT", "Bitcoin", "CRIPTO_MEGA"),
        ("ETHUSDT", "Ethereum", "CRIPTO_MEGA"),
        ("SOLUSDT", "Solana", "CRIPTO_MEGA"),
        ("LINKUSDT", "Chainlink", "CRIPTO_MEGA"),
        ("PAXGUSDT", "PAX Gold (Tokenized)", "CRIPTO_GOLD"),

        # High-Beta Altcoins
        ("SUIUSDT", "Sui Network", "ALTCOIN_HIGH_BETA"),
        ("RENDERUSDT", "Render", "ALTCOIN_HIGH_BETA"),
        ("NEARUSDT", "Near Protocol", "ALTCOIN_HIGH_BETA"),
        ("FETUSDT", "Artificial Superintelligence", "ALTCOIN_HIGH_BETA"),
        ("ATOMUSDT", "Cosmos", "ALTCOIN_HIGH_BETA"),
        ("TIAUSDT", "Celestia", "ALTCOIN_HIGH_BETA"),
        ("DOGEUSDT", "Dogecoin", "ALTCOIN_HIGH_BETA"),
        ("ADAUSDT", "Cardano", "ALTCOIN_HIGH_BETA"),

        # TradFi / FTMO
        ("US100", "Nasdaq 100", "TRADFI_INDICES"),
        ("US30", "Dow Jones 30", "TRADFI_INDICES"),
        ("US500", "S&P 500", "TRADFI_INDICES"),
        ("XAUUSD", "Oro Spot", "TRADFI_METALS"),
        ("HGUSD", "Cobre High Grade", "TRADFI_METALS")
    ]

    timeframes = ["15m", "1h", "4h", "1d"]
    results = []

    for sym, name, cat in test_assets:
        for tf in timeframes:
            try:
                trades = engine.run_single_asset(sym, interval=tf, btc_map=btc_map)
                if not trades or len(trades) < 4:
                    continue

                df_trades = pd.DataFrame(trades)
                n_trades = len(df_trades)
                winners = df_trades[df_trades['outcome_r'] > 0]
                losers = df_trades[df_trades['outcome_r'] < 0]
                be = df_trades[df_trades['outcome_r'] == 0]

                wr = len(winners) / n_trades * 100.0
                be_rate = len(be) / n_trades * 100.0
                total_r = df_trades['outcome_r'].sum()
                gross_w = winners['outcome_r'].sum() if len(winners) > 0 else 0
                gross_l = abs(losers['outcome_r'].sum()) if len(losers) > 0 else 1
                pf = gross_w / gross_l if gross_l > 0 else 99.0

                df_trades['pnl_usd'] = df_trades['outcome_r'] * 1000.0
                df_trades['cum'] = df_trades['pnl_usd'].cumsum()
                df_trades['equity'] = 100000.0 + df_trades['cum']
                df_trades['dd'] = (df_trades['equity'] - df_trades['equity'].cummax()) / df_trades['equity'].cummax() * 100
                max_dd = abs(df_trades['dd'].min())

                results.append({
                    "Activo": sym,
                    "Nombre": name,
                    "Categoría": cat,
                    "TF": tf,
                    "Trades": n_trades,
                    "Win Rate": f"{wr:.1f}%",
                    "Profit Factor": round(pf, 2),
                    "Retorno Total": round(total_r, 2),
                    "Max DD": f"-{max_dd:.1f}%"
                })
            except Exception as e:
                pass

    df_res = pd.DataFrame(results)
    if not df_res.empty:
        print("\n📊 MATRIZ COMPARATIVA DE RENDIMIENTO POR TEMPORALIDAD:\n")
        print(df_res[["Activo", "Categoría", "TF", "Trades", "Win Rate", "Profit Factor", "Retorno Total", "Max DD"]].to_string(index=False))

        print("\n" + "="*115)
        print("🏆 TOP 10 ACTIVOS Y TEMPORALIDADES MÁS RENTABLES DEL SISTEMA:")
        print("="*115)
        top10 = df_res.sort_values(by="Retorno Total", ascending=False).head(10)
        for idx, (_, row) in enumerate(top10.iterrows(), 1):
            print(f"{idx}. ⭐ {row['Activo']} ({row['Nombre']}) en {row['TF']}: {row['Retorno Total']:+.2f} R | Win Rate: {row['Win Rate']} | PF: {row['Profit Factor']} | Max DD: {row['Max DD']}")
    else:
        print("No se generaron resultados.")

if __name__ == "__main__":
    run_multi_timeframe_matrix_audit()
