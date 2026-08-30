"""
=============================================================================
AUDITORÍA MULTI-TEMPORALIDAD: NEARUSDT (15M vs 1H vs 4H vs 1D)
=============================================================================
Evalúa el desempeño de NEARUSDT a través de múltiples marcos temporales
bajo el motor cuantitativo Slingshot v23.0 APEX SOVEREIGN (180 Días Históricos).
=============================================================================
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from engine.backtest.unified_backtest_engine import DATA_DIR
from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.strategies.smc import SMCInstitutionalStrategy

def run_near_mtf_audit():
    file_path = os.path.join(DATA_DIR, "NEARUSDT_15m_180d.parquet")
    if not os.path.exists(file_path):
        print(f"Error: No se encontró el archivo de datos {file_path}")
        return

    raw = pd.read_parquet(file_path)
    raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
    if not pd.api.types.is_datetime64_any_dtype(raw['timestamp']):
        first_ts = float(raw['timestamp'].iloc[0])
        unit = 's' if first_ts < 1e11 else 'ms'
        raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit=unit)

    raw.sort_values('timestamp', inplace=True)
    raw.set_index('timestamp', inplace=True)

    timeframes = [
        ("15m (Scalp Hyper-Momentum)", "15min", 1.0, 1.5, 3.0, 5.0, 40),
        ("1h  (Intraday Swing OTE)",   "1h",    1.2, 1.8, 3.5, 6.0, 30),
        ("4h  (Macro Swing Structure)","4h",    1.2, 2.0, 4.0, 7.0, 25),
        ("1d  (Posicional / Tendencial)","1D",  1.5, 2.5, 5.0, 8.0, 20),
    ]

    print("=" * 95)
    print("🔬 AUDITORÍA COMPARATIVA MULTI-TEMPORALIDAD: NEARUSDT (180 DÍAS)")
    print("=" * 95)

    results = []

    for label, tf_rule, be_r, tp1_r, tp2_r, tp3_r, max_bars in timeframes:
        if tf_rule == "15min":
            df = raw.copy().reset_index()
        else:
            df = raw.resample(tf_rule).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna().reset_index()

        if len(df) < 50:
            continue

        df = polars_engine.compute_indicators(df)
        df = identify_order_blocks(df)
        strategy = SMCInstitutionalStrategy()
        df = strategy.analyze(df)

        atr_series = df['atr'] if 'atr' in df.columns else (df['close'] * 0.015)
        n = len(df)

        trades = []
        in_trade = False
        trade_dir = ""
        entry_price = 0.0
        initial_risk = 0.0
        cur_sl = 0.0
        be_active = False
        tp1_hit = False
        tp2_hit = False
        tp3_hit = False
        entry_idx = 0

        for i in range(30, n - 15):
            current_row = df.iloc[i]
            is_bull = bool(current_row.get('ob_bullish', False))
            is_bear = bool(current_row.get('ob_bearish', False))

            if in_trade:
                kh = float(current_row['high'])
                kl = float(current_row['low'])
                kc = float(current_row['close'])
                
                r_gain = (kh - entry_price) / initial_risk if trade_dir == "LONG" else (entry_price - kl) / initial_risk

                # Fast Breakeven
                if not be_active and r_gain >= be_r:
                    be_active = True
                    fee_buffer = entry_price * 0.0008
                    cur_sl = (entry_price + fee_buffer) if trade_dir == "LONG" else (entry_price - fee_buffer)

                # TP1
                if not tp1_hit and r_gain >= tp1_r:
                    tp1_hit = True
                    be_active = True
                    cur_sl = (entry_price + fee_buffer) if trade_dir == "LONG" else (entry_price - fee_buffer)

                # TP2
                if not tp2_hit and r_gain >= tp2_r:
                    tp2_hit = True
                    cur_sl = (entry_price + initial_risk * 1.5) if trade_dir == "LONG" else (entry_price - initial_risk * 1.5)

                # TP3
                if not tp3_hit and r_gain >= tp3_r:
                    tp3_hit = True
                    locked_r = r_gain * 0.70
                    cur_sl = (entry_price + initial_risk * locked_r) if trade_dir == "LONG" else (entry_price - initial_risk * locked_r)

                sl_triggered = (trade_dir == "LONG" and kl <= cur_sl) or (trade_dir == "SHORT" and kh >= cur_sl)
                tp_runner_max = (r_gain >= (tp3_r * 1.5))

                if sl_triggered or tp_runner_max or (i - entry_idx >= max_bars):
                    if tp_runner_max:
                        final_r = (0.60 * tp1_r) + (0.20 * tp2_r) + (0.10 * tp3_r) + (0.10 * tp3_r * 1.5)
                        outcome = "TP_RUNNER"
                    elif tp3_hit:
                        final_r = (0.60 * tp1_r) + (0.20 * tp2_r) + (0.10 * tp3_r) + (0.10 * tp2_r)
                        outcome = "TP3"
                    elif tp2_hit:
                        final_r = (0.60 * tp1_r) + (0.20 * tp2_r) + (0.20 * 1.5)
                        outcome = "TP2"
                    elif tp1_hit:
                        final_r = (0.60 * tp1_r)
                        outcome = "TP1"
                    elif be_active:
                        final_r = 0.05
                        outcome = "BREAKEVEN"
                    else:
                        final_r = -1.0
                        outcome = "STOP_LOSS"

                    trades.append({"r": final_r, "win": final_r > 0.1, "be": abs(final_r) <= 0.1, "dir": trade_dir})
                    in_trade = False
                    continue

            else:
                if not is_bull and not is_bear:
                    continue

                direction = "LONG" if is_bull else "SHORT"
                c_price = float(current_row['close'])
                atr = float(atr_series.iloc[i]) if not pd.isna(atr_series.iloc[i]) else (c_price * 0.015)

                if direction == "LONG":
                    sl = float(df.iloc[max(0, i-8):i]['low'].min()) - (atr * 0.5)
                    risk = c_price - sl
                else:
                    sl = float(df.iloc[max(0, i-8):i]['high'].max()) + (atr * 0.5)
                    risk = sl - c_price

                if risk <= 0 or (risk / c_price) > 0.08 or (risk / c_price) < 0.003:
                    continue

                in_trade = True
                trade_dir = direction
                entry_price = c_price
                initial_risk = risk
                cur_sl = sl
                be_active = False
                tp1_hit = False
                tp2_hit = False
                tp3_hit = False
                entry_idx = i

        tdf = pd.DataFrame(trades)
        if tdf.empty:
            continue

        n_t = len(tdf)
        wins = tdf[tdf['win']]
        bes = tdf[tdf['be']]
        losses = tdf[(~tdf['win']) & (~tdf['be'])]

        total_r = tdf['r'].sum()
        gross_w = tdf[tdf['r'] > 0]['r'].sum()
        gross_l = abs(tdf[tdf['r'] < 0]['r'].sum())
        pf = (gross_w / gross_l) if gross_l > 0 else 999.0

        wr = (len(wins) / n_t) * 100
        be_rate = (len(bes) / n_t) * 100
        loss_rate = (len(losses) / n_t) * 100

        # Longs vs Shorts
        longs_r = tdf[tdf['dir'] == 'LONG']['r'].sum()
        shorts_r = tdf[tdf['dir'] == 'SHORT']['r'].sum()

        results.append({
            "label": label,
            "trades": n_t,
            "wins": len(wins),
            "bes": len(bes),
            "losses": len(losses),
            "wr": wr,
            "be_rate": be_rate,
            "loss_rate": loss_rate,
            "total_r": total_r,
            "pf": pf,
            "longs_r": longs_r,
            "shorts_r": shorts_r
        })

    for r in results:
        print(f"\n⏱️ {r['label']}")
        print(f" • Total Operaciones:     {r['trades']}")
        print(f" • Ganadoras (TPs):       {r['wins']} ({r['wr']:.1f}%)")
        print(f" • Breakevens Salvados:   {r['bes']} ({r['be_rate']:.1f}%)")
        print(f" • Pérdidas en SL:        {r['losses']} ({r['loss_rate']:.1f}%)")
        print(f" • RETORNO TOTAL NETO:    {r['total_r']:+.2f} R")
        print(f" • PROFIT FACTOR:         {r['pf']:.2f}")
        print(f" • Retorno en LONGS:      {r['longs_r']:+.2f} R")
        print(f" • Retorno en SHORTS:     {r['shorts_r']:+.2f} R")
        print("-" * 95)

if __name__ == "__main__":
    run_near_mtf_audit()
