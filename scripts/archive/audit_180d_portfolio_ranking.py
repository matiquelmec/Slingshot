"""
=============================================================================
AUDITORÍA CUANTITATIVA COMPARATIVA: 14 ACTIVOS VIP (180 DÍAS HISTÓRICOS)
=============================================================================
Evalúa la confiabilidad, liquidez, tasa de acierto y retorno de cada una
de las 14 monedas de la Watchlist bajo el motor Slingshot v23.2 APEX.
=============================================================================
"""
import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from engine.backtest.unified_backtest_engine import DATA_DIR
from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.strategies.smc import SMCInstitutionalStrategy

MASTER_ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "XRPUSDT", "BNBUSDT", "PAXGUSDT",
    "SUIUSDT", "INJUSDT", "RENDERUSDT", "FETUSDT", "NEARUSDT", "ATOMUSDT", "TIAUSDT"
]

def run_180d_portfolio_ranking():
    results = []
    
    for symbol in MASTER_ASSETS:
        # Buscar parquet
        fpath = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
        if not os.path.exists(fpath):
            fpath = os.path.join(DATA_DIR, f"{symbol}_15m.parquet")
            if not os.path.exists(fpath):
                continue

        raw = pd.read_parquet(fpath)
        raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
        if not pd.api.types.is_datetime64_any_dtype(raw['timestamp']):
            first_ts = float(raw['timestamp'].iloc[0])
            unit = 's' if first_ts < 1e11 else 'ms'
            raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit=unit)

        df = raw.sort_values('timestamp').reset_index(drop=True)
        if len(df) < 200:
            continue

        # Indicadores
        df = polars_engine.compute_indicators(df)
        df = identify_order_blocks(df)
        strategy = SMCInstitutionalStrategy()
        df = strategy.analyze(df)

        atr_series = df['atr'] if 'atr' in df.columns else (df['close'] * 0.015)
        n = len(df)

        is_mega = any(m in symbol for m in ["BTC", "ETH", "SOL", "AVAX", "LINK", "XRP", "BNB", "PAXG"])
        be_thresh = 1.2 if is_mega else 1.0

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

        for i in range(40, n - 20):
            c_row = df.iloc[i]
            is_bull = bool(c_row.get('ob_bullish', False))
            is_bear = bool(c_row.get('ob_bearish', False))

            if in_trade:
                kh = float(c_row['high'])
                kl = float(c_row['low'])
                kc = float(c_row['close'])
                
                r_gain = (kh - entry_price)/initial_risk if trade_dir == "LONG" else (entry_price - kl)/initial_risk

                if not be_active and r_gain >= be_thresh:
                    be_active = True
                    fee_buffer = entry_price * 0.0008
                    cur_sl = (entry_price + fee_buffer) if trade_dir == "LONG" else (entry_price - fee_buffer)

                if not tp1_hit and r_gain >= 1.5:
                    tp1_hit = True
                    be_active = True
                    cur_sl = (entry_price + fee_buffer) if trade_dir == "LONG" else (entry_price - fee_buffer)

                if not tp2_hit and r_gain >= 3.0:
                    tp2_hit = True
                    cur_sl = (entry_price + initial_risk * 2.0) if trade_dir == "LONG" else (entry_price - initial_risk * 2.0)

                if not tp3_hit and r_gain >= 5.0:
                    tp3_hit = True
                    cur_sl = (entry_price + initial_risk * (r_gain * 0.70)) if trade_dir == "LONG" else (entry_price - initial_risk * (r_gain * 0.70))

                sl_trig = (trade_dir == "LONG" and kl <= cur_sl) or (trade_dir == "SHORT" and kh >= cur_sl)
                tp_runner = (r_gain >= 8.0)

                if sl_trig or tp_runner or (i - entry_idx >= 48): # 12h hold
                    if tp_runner:
                        r_res = (0.60*1.5) + (0.20*3.0) + (0.10*5.0) + (0.10*8.0)
                    elif tp3_hit:
                        r_res = (0.60*1.5) + (0.20*3.0) + (0.10*5.0) + (0.10*4.0)
                    elif tp2_hit:
                        r_res = (0.60*1.5) + (0.20*3.0) + (0.20*2.0)
                    elif tp1_hit:
                        r_res = (0.60*1.5)
                    elif be_active:
                        r_res = 0.05
                    else:
                        r_res = -1.0

                    trades.append(r_res)
                    in_trade = False
                    continue

            else:
                if not is_bull and not is_bear:
                    continue

                direction = "LONG" if is_bull else "SHORT"
                c_p = float(c_row['close'])
                atr = float(atr_series.iloc[i]) if not pd.isna(atr_series.iloc[i]) else (c_p * 0.015)

                if direction == "LONG":
                    sl = float(df.iloc[max(0, i-8):i]['low'].min()) - (atr * 0.5)
                    risk = c_p - sl
                else:
                    sl = float(df.iloc[max(0, i-8):i]['high'].max()) + (atr * 0.5)
                    risk = sl - c_p

                if risk <= 0 or (risk / c_p) > 0.04 or (risk / c_p) < 0.004:
                    continue

                in_trade = True
                trade_dir = direction
                entry_price = c_p
                initial_risk = risk
                cur_sl = sl
                be_active = False
                tp1_hit = False
                tp2_hit = False
                tp3_hit = False
                entry_idx = i

        if not trades:
            continue

        n_t = len(trades)
        wins = [t for t in trades if t > 0.1]
        bes = [t for t in trades if 0.0 <= t <= 0.1]
        losses = [t for t in trades if t < 0.0]

        total_r = sum(trades)
        gross_w = sum(wins) + sum(bes)
        gross_l = abs(sum(losses))
        pf = (gross_w / gross_l) if gross_l > 0 else 999.0

        wr = (len(wins) / n_t) * 100
        be_r = (len(bes) / n_t) * 100
        eff_r = wr + be_r

        results.append({
            "asset": symbol,
            "category": "MEGA" if is_mega else "ALT",
            "trades": n_t,
            "wins": len(wins),
            "bes": len(bes),
            "losses": len(losses),
            "wr": wr,
            "be_rate": be_r,
            "effective_rate": eff_r,
            "total_r": total_r,
            "pf": pf
        })

    res_df = pd.DataFrame(results).sort_values("total_r", ascending=False).reset_index(drop=True)
    
    print("=" * 95)
    print("🏆 RANKING INSTITUCIONAL DE ACTIVOS (180 DÍAS DE BACKTEST REAL)")
    print("=" * 95)
    print(f"{'#':<3} {'ACTIVO':<10} {'TIPO':<6} {'TRADES':<8} {'WIN RATE':<10} {'BE RATE':<10} {'EFECTIVIDAD':<12} {'RETORNO (R)':<14} {'PROFIT FACTOR':<12}")
    print("-" * 95)
    
    for idx, row in res_df.iterrows():
        print(f"{idx+1:<3} {row['asset']:<10} {row['category']:<6} {row['trades']:<8} {row['wr']:>5.1f}%     {row['be_rate']:>5.1f}%     {row['effective_rate']:>5.1f}%       {row['total_r']:>+7.2f} R       {row['pf']:>5.2f}")
    
    print("=" * 95)
    tot_trades = res_df['trades'].sum()
    tot_r = res_df['total_r'].sum()
    avg_pf = res_df['pf'].mean()
    print(f"📊 TOTAL CARTERA COMBINADA: {tot_trades} trades | Retorno Total: {tot_r:+.2f} R | Profit Factor Medio: {avg_pf:.2f}")
    print("=" * 95)

if __name__ == "__main__":
    run_180d_portfolio_ranking()
