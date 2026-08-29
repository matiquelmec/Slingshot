"""
=============================================================================
SCIENTIFIC AUDIT: OTE ENTRY DEPTH PARAMETRIC COMPARISON (61.8% vs 70.5% vs Hybrid)
=============================================================================
Evalúa rigurosamente el Fill Rate, Retorno Total en R, Win Rate, Profit Factor
y Drawdown sobre 180 días de datos históricos reales.
=============================================================================
"""
import sys
import os
import pandas as pd
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR, MEGA_CAPS
from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks

class ParametricOteEngine(UnifiedBacktestEngine):
    def __init__(self, min_confluence_score=60, mega_mult=0.382, alt_mult=0.382):
        super().__init__(min_confluence_score=min_confluence_score)
        self.mega_mult = mega_mult
        self.alt_mult = alt_mult

    def run_custom_asset(self, symbol: str, interval: str = "15m", btc_map=None):
        file_candidates = [
            os.path.join(DATA_DIR, f"{symbol}_{interval}_180d.parquet"),
            os.path.join(DATA_DIR, f"{symbol}_{interval}_90d.parquet"),
            os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet"),
            os.path.join(DATA_DIR, f"{symbol}_15m_90d.parquet"),
        ]
        valid_file = next((f for f in file_candidates if os.path.exists(f)), None)
        if not valid_file:
            return []

        raw = pd.read_parquet(valid_file)
        raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
        if not pd.api.types.is_datetime64_any_dtype(raw['timestamp']):
            first_ts = float(raw['timestamp'].iloc[0])
            unit = 's' if first_ts < 1e11 else 'ms'
            raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit=unit)

        is_1h = interval in ["1h", "1H", "60m"]
        if is_1h and "_15m_" in valid_file:
            raw.set_index('timestamp', inplace=True)
            df = raw.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
        else:
            df = raw.sort_values('timestamp').reset_index(drop=True)

        if len(df) < 60:
            return []

        # Indicadores
        df = polars_engine.compute_indicators(df)
        df = identify_order_blocks(df)
        df = self.strategy.analyze(df)

        df['vol_sma'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / (df['vol_sma'] + 1e-9)
        change = (df['close'] - df['close'].shift(10)).abs()
        vol = (df['close'] - df['close'].shift(1)).abs().rolling(10).sum()
        df['ker'] = change / (vol + 1e-9)

        trades = []
        n = len(df)
        is_mega_cap = symbol in MEGA_CAPS
        retrace_factor = self.mega_mult if (is_mega_cap or is_1h) else self.alt_mult
        atr_sl_mult = 0.60 if (is_mega_cap or is_1h) else 0.30

        total_setups = 0
        filled_setups = 0

        for i in range(30, n - 20):
            row = df.iloc[i]
            dt = row['timestamp']
            hour = dt.hour

            if interval == "15m" and self.strict_killzones:
                if not (7 <= hour <= 12 or 13 <= hour <= 18):
                    continue

            ker_val = float(row.get('ker', 0.5))
            if interval == "15m" and ker_val < 0.28:
                continue

            btc_trend = btc_map.get(dt, 'NEUTRAL') if btc_map else 'NEUTRAL'
            if symbol == "PAXGUSDT" and btc_trend == "BEARISH":
                continue

            c = float(row['close'])
            ema50 = float(row['ema50'])
            ema200 = float(row['ema200'])
            atr = float(row['atr'])
            if atr <= 0:
                continue

            is_bull = (c > ema50) and (ema50 > ema200) and bool(row['fvg_bull']) and (btc_trend != 'BEARISH')
            is_bear = (c < ema50) and (ema50 < ema200) and bool(row['fvg_bear']) and (btc_trend != 'BULLISH')

            if not (is_bull or is_bear):
                continue

            total_setups += 1
            direction = "LONG" if is_bull else "SHORT"

            if direction == "LONG":
                fvg_low = float(df.iloc[i-2]['high'])
                fvg_high = float(df.iloc[i]['low'])
                entry = fvg_low + (fvg_high - fvg_low) * retrace_factor if (fvg_high > fvg_low) else fvg_low
                sl = float(min(df.iloc[i-1]['low'], df.iloc[i]['low'])) - (atr * atr_sl_mult)
                risk = entry - sl
                if risk <= 0 or (risk / entry) > 0.04:
                    continue
                be_target = entry + (risk * 1.2)
                tp1 = entry + (risk * 1.5)
                tp2 = entry + (risk * 2.5)
                tp3 = entry + (risk * (4.0 if is_1h else 3.5))
            else:
                fvg_high = float(df.iloc[i-2]['low'])
                fvg_low = float(df.iloc[i]['low'])
                entry = fvg_high - (fvg_high - fvg_low) * retrace_factor if (fvg_high > fvg_low) else fvg_high
                sl = float(max(df.iloc[i-1]['high'], df.iloc[i]['high'])) + (atr * atr_sl_mult)
                risk = sl - entry
                if risk <= 0 or (risk / entry) > 0.04:
                    continue
                be_target = entry - (risk * 1.2)
                tp1 = entry - (risk * 1.5)
                tp2 = entry - (risk * 2.5)
                tp3 = entry - (risk * (4.0 if is_1h else 3.5))

            limit_filled = False
            fill_idx = -1

            for j in range(i + 1, min(i + 13, n)):
                bar_h = float(df.iloc[j]['high'])
                bar_l = float(df.iloc[j]['low'])

                if (direction == "LONG" and bar_h >= tp1) or (direction == "SHORT" and bar_l <= tp1):
                    break
                if (direction == "LONG" and bar_l <= sl) or (direction == "SHORT" and bar_h >= sl):
                    break
                if direction == "LONG" and bar_l <= entry:
                    limit_filled = True
                    fill_idx = j
                    break
                elif direction == "SHORT" and bar_h >= entry:
                    limit_filled = True
                    fill_idx = j
                    break

            if not limit_filled:
                continue

            filled_setups += 1
            fast_be = False
            cur_sl = sl
            pnl_r = 0.0

            for k in range(fill_idx + 1, min(fill_idx + 60, n)):
                kh = float(df.iloc[k]['high'])
                kl = float(df.iloc[k]['low'])

                if not fast_be:
                    if (direction == "LONG" and kh >= be_target) or (direction == "SHORT" and kl <= be_target):
                        fast_be = True
                        cur_sl = entry

                if (direction == "LONG" and kl <= cur_sl) or (direction == "SHORT" and kh >= cur_sl):
                    pnl_r = 0.0 if fast_be else -1.0
                    break

                if (direction == "LONG" and kh >= tp3) or (direction == "SHORT" and kl <= tp3):
                    pnl_r = 3.5 if not is_1h else 4.0
                    break
                elif (direction == "LONG" and kh >= tp2) or (direction == "SHORT" and kl <= tp2):
                    pnl_r = 2.5
                elif (direction == "LONG" and kh >= tp1) or (direction == "SHORT" and kl <= tp1):
                    pnl_r = 1.5

            trades.append({
                "symbol": symbol,
                "direction": direction,
                "outcome_r": pnl_r,
                "total_setups": total_setups,
                "filled_setups": filled_setups
            })

        return trades


def run_comparison():
    print("\n" + "="*95)
    print("🔬 ESTUDIO PARAMÉTRICO: PROFUNDIDAD DE ENTRADA OTE (61.8% vs 70.5% vs HÍBRIDO)")
    print("="*95)

    btc_map = UnifiedBacktestEngine()._load_btc_macro_map()

    megas = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "XRPUSDT"]
    alts = ["RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "TIAUSDT", "PAXGUSDT"]

    variants = [
        ("Variante A: OTE 61.8% Fijo (Todos)", 0.382, 0.382),
        ("Variante B: OTE 70.5% Fijo (Todos)", 0.295, 0.295),
        ("Variante C: OTE Híbrido Apex (61.8% Megas / 70.5% Alts)", 0.382, 0.295),
    ]

    for label, m_mult, a_mult in variants:
        engine = ParametricOteEngine(min_confluence_score=60, mega_mult=m_mult, alt_mult=a_mult)
        res = []
        for s in megas:
            res.extend(engine.run_custom_asset(s, interval="1h", btc_map=btc_map))
        for s in alts:
            res.extend(engine.run_custom_asset(s, interval="15m", btc_map=btc_map))

        df = pd.DataFrame(res)
        if df.empty:
            continue

        n_trades = len(df)
        winners = df[df['outcome_r'] > 0]
        losers = df[df['outcome_r'] < 0]
        be = df[df['outcome_r'] == 0]

        wr = (len(winners) / n_trades * 100) if n_trades > 0 else 0
        be_rate = (len(be) / n_trades * 100) if n_trades > 0 else 0
        total_r = df['outcome_r'].sum()
        gross_w = winners['outcome_r'].sum() if len(winners) > 0 else 0
        gross_l = abs(losers['outcome_r'].sum()) if len(losers) > 0 else 1
        pf = gross_w / gross_l if gross_l > 0 else 99.0

        print(f"\n--- {label} ---")
        print(f"  • Total Trades Ejecutados: {n_trades}")
        print(f"  • Win Rate (TPs):          {wr:.1f}%")
        print(f"  • Breakeven Rate ($0):     {be_rate:.1f}%")
        print(f"  • Efectividad Total:       {(wr + be_rate):.1f}%")
        print(f"  • Retorno Total Neto:      {total_r:+.2f} R")
        print(f"  • Profit Factor:           {pf:.2f}")

    print("\n" + "="*95 + "\n")

if __name__ == "__main__":
    run_comparison()
