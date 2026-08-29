"""
=============================================================================
SCIENTIFIC AUDIT: BREAKEVEN STRATEGY COMPARISON (180 DAYS REAL DATA)
=============================================================================
"""
import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from engine.backtest.unified_backtest_engine import DATA_DIR
from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.strategies.smc import SMCInstitutionalStrategy

def run_breakeven_study():
    assets = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT",
        "XRPUSDT", "RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT",
        "FETUSDT", "ATOMUSDT", "TIAUSDT", "DOGEUSDT"
    ]
    
    strategies = [
        ("Variante A: Fast Breakeven @ +1.0R (Actual)", 1.0, False),
        ("Variante B: Fast Breakeven @ +1.2R (Punto de Equilibrio)", 1.2, False),
        ("Variante C: Breakeven al Cobrar TP1 @ +1.5R (60% Asegurado + Holgura Re-Test)", 1.5, True),
        ("Variante D: Sin Breakeven (SL Estructural Completo -1R)", 999.0, False),
    ]
    
    print("\n" + "="*95)
    print("🔬 ESTUDIO COMPARATIVO: ESTRATEGIAS DE BREAKEVEN Y RESPIRACIÓN DE TRADE (180 DÍAS)")
    print("="*95)
    
    for label, be_r_mult, is_tp1_split in strategies:
        all_trades = []
        
        for symbol in assets:
            file_candidates = [
                os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet"),
                os.path.join(DATA_DIR, f"{symbol}_15m_90d.parquet"),
                os.path.join(DATA_DIR, f"{symbol}_15m_audited.parquet")
            ]
            valid_file = next((f for f in file_candidates if os.path.exists(f)), None)
            if not valid_file:
                continue

            raw = pd.read_parquet(valid_file)
            raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
            if not pd.api.types.is_datetime64_any_dtype(raw['timestamp']):
                first_ts = float(raw['timestamp'].iloc[0])
                unit = 's' if first_ts < 1e11 else 'ms'
                raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit=unit)

            df = raw.sort_values('timestamp').reset_index(drop=True)
            if len(df) < 60:
                continue

            df = polars_engine.compute_indicators(df)
            df = identify_order_blocks(df)
            strategy = SMCInstitutionalStrategy()
            df = strategy.analyze(df)

            atr_series = df['atr'] if 'atr' in df.columns else (df['close'] * 0.015)
            n = len(df)

            # Buscar señales de Order Blocks
            for i in range(50, n - 45):
                is_bull = bool(df.iloc[i].get('ob_bullish', False))
                is_bear = bool(df.iloc[i].get('ob_bearish', False))
                
                if not is_bull and not is_bear:
                    continue

                direction = "LONG" if is_bull else "SHORT"
                c = df.iloc[i]
                atr = float(atr_series.iloc[i]) if not pd.isna(atr_series.iloc[i]) else (float(c['close']) * 0.015)
                
                if direction == "LONG":
                    entry = float(c['close'])
                    sl = float(df.iloc[max(0, i-10):i]['low'].min()) - (atr * 0.5)
                    risk = entry - sl
                    if risk <= 0 or (risk / entry) > 0.04 or (risk / entry) < 0.003: continue
                    be_target = entry + (risk * be_r_mult)
                    tp1 = entry + (risk * 1.5)
                    tp2 = entry + (risk * 3.0)
                    tp3 = entry + (risk * 5.0)
                else:
                    entry = float(c['close'])
                    sl = float(df.iloc[max(0, i-10):i]['high'].max()) + (atr * 0.5)
                    risk = sl - entry
                    if risk <= 0 or (risk / entry) > 0.04 or (risk / entry) < 0.003: continue
                    be_target = entry - (risk * be_r_mult)
                    tp1 = entry - (risk * 1.5)
                    tp2 = entry - (risk * 3.0)
                    tp3 = entry - (risk * 5.0)

                be_active = False
                tp1_hit = False
                tp2_hit = False
                tp3_hit = False
                cur_sl = sl
                final_r = None

                for k in range(i + 1, min(i + 40, n)):
                    kh = float(df.iloc[k]['high'])
                    kl = float(df.iloc[k]['low'])

                    # 1. Breakeven Trigger
                    if not be_active and not is_tp1_split:
                        if (direction == "LONG" and kh >= be_target) or (direction == "SHORT" and kl <= be_target):
                            be_active = True
                            cur_sl = entry

                    # 2. Take Profits
                    if not tp1_hit:
                        if (direction == "LONG" and kh >= tp1) or (direction == "SHORT" and kl <= tp1):
                            tp1_hit = True
                            if is_tp1_split:
                                be_active = True
                                cur_sl = entry # Subir SL a BE tras cobrar 60%
                    if not tp2_hit and tp1_hit:
                        if (direction == "LONG" and kh >= tp2) or (direction == "SHORT" and kl <= tp2):
                            tp2_hit = True
                            cur_sl = entry + (risk * 2.0) if direction == "LONG" else entry - (risk * 2.0)
                    if not tp3_hit and tp2_hit:
                        if (direction == "LONG" and kh >= tp3) or (direction == "SHORT" and kl <= tp3):
                            tp3_hit = True

                    # 3. Stop Hit Check
                    if (direction == "LONG" and kl <= cur_sl) or (direction == "SHORT" and kh >= cur_sl):
                        if cur_sl == sl:
                            final_r = -1.0 # SL Completo
                        elif cur_sl == entry:
                            final_r = 0.90 if tp1_hit else 0.0 # 0.60*1.5 si ya cobró TP1, o 0.0
                        else:
                            final_r = (0.60 * 1.5) + (0.20 * 3.0) + (0.20 * 2.0) # +1.90R
                        break

                    if tp3_hit:
                        final_r = (0.60 * 1.5) + (0.20 * 3.0) + (0.10 * 5.0) + (0.10 * 7.0) # +2.70R
                        break

                if final_r is None:
                    final_r = 0.90 if tp1_hit else (0.0 if be_active else -0.5)

                all_trades.append({"r": final_r, "win": final_r > 0.05, "be": abs(final_r) <= 0.05, "symbol": symbol})

        df_t = pd.DataFrame(all_trades)
        if df_t.empty:
            continue

        n_t = len(df_t)
        winners = df_t[df_t['r'] > 0.05]
        losers = df_t[df_t['r'] < -0.05]
        bes = df_t[abs(df_t['r']) <= 0.05]

        total_r = df_t['r'].sum()
        gross_w = winners['r'].sum() if len(winners) > 0 else 0
        gross_l = abs(losers['r'].sum()) if len(losers) > 0 else 1
        pf = gross_w / gross_l if gross_l > 0 else 99.0
        wr = (len(winners) / n_t) * 100
        be_rate = (len(bes) / n_t) * 100

        # Drawdown
        equity = np.cumsum(df_t['r'])
        peak = np.maximum.accumulate(equity)
        max_dd = np.max(peak - equity) if len(equity) > 0 else 0

        print(f"\n📌 {label}")
        print(f"   • Total Trades Evaluados: {n_t}")
        print(f"   • Ganadores (TPs):        {len(winners)} ({wr:.1f}%)")
        print(f"   • Breakevens ($0):        {len(bes)} ({be_rate:.1f}%)")
        print(f"   • Pérdidas (SL):          {len(losers)} ({(len(losers)/n_t)*100:.1f}%)")
        print(f"   • Retorno Total Neto:     +{total_r:.2f} R")
        print(f"   • Profit Factor:          {pf:.2f}")
        print(f"   • Max Drawdown:           -{max_dd:.2f} R")
        print(f"   • Ganancia Promedio/Win:  +{gross_w/len(winners):.2f} R")

    print("\n" + "="*95 + "\n")

if __name__ == "__main__":
    run_breakeven_study()
