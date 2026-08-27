"""
engine/backtest/verify_exact_5pct_20x_math.py
"""
import sys
import os
import glob
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def run_exact_audit():
    initial_capital = 200.0
    equity = initial_capital
    margin_pct = 0.05      # 5% de la cuenta en cada trade
    leverage = 20          # 20x apalancamiento
    maker_fee = 0.0002     # 0.02% Maker Bitunix
    taker_fee = 0.0006     # 0.06% Taker Bitunix
    slippage = 0.0002      # 0.02% Slippage

    print("\n" + "="*85)
    print("📐 AUDITORÍA MATEMÁTICA EXACTA: MARGEN 5% @ 20x APALANCAMIENTO")
    print("="*85)
    print(f"• Capital Inicial         : ${initial_capital:.2f} USD")
    print(f"• Margen Inicial (5%)     : ${initial_capital * margin_pct:.2f} USD")
    print(f"• Tamaño Nominal Inicial  : ${initial_capital * margin_pct * leverage:.2f} USD ($10 x 20)")
    print("="*85)

    # Cargar datos de los 8 activos estrella (RENDER, SUI, NEAR, INJ, LINK, ETH, ATOM, FET)
    star_assets = ["RENDERUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "LINKUSDT", "ETHUSDT", "ATOMUSDT", "FETUSDT"]
    
    trades = []
    # Simular una secuencia de 50 trades reales del historial de 90 días
    for sym in star_assets:
        f = glob.glob(os.path.join(DATA_DIR, f"{sym}_15m_*.parquet"))
        if not f: continue
        raw = pd.read_parquet(f[0])
        raw.rename(columns={'o':'open','h':'high','l':'low','c':'close','v':'volume','t':'timestamp'}, inplace=True)
        raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit='s' if raw['timestamp'].iloc[0] < 1e11 else 'ms')
        raw.sort_values('timestamp', inplace=True)
        
        # 90 días
        max_dt = raw['timestamp'].max()
        start_dt = max_dt - timedelta(days=90)
        df = raw[raw['timestamp'] >= start_dt].copy().reset_index(drop=True)
        
        # Calcular EMAs y ATR
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['tr'] = np.maximum(df['high'] - df['low'], np.maximum((df['high'] - df['close'].shift(1)).abs(), (df['low'] - df['close'].shift(1)).abs()))
        df['atr'] = df['tr'].rolling(14).mean()
        
        # Detección FVG
        df['fvg_bull'] = (df['low'] > df['high'].shift(2))
        df['fvg_bear'] = (df['high'] < df['low'].shift(2))
        
        for i in range(30, len(df)-20, 10):
            row = df.iloc[i]
            c = float(row['close'])
            ema50 = float(row['ema50'])
            ema200 = float(row['ema200'])
            atr = float(row['atr'])
            if atr <= 0: continue
            
            is_bull = (c > ema200) and (ema50 > ema200) and bool(row['fvg_bull'])
            is_bear = (c < ema200) and (ema50 < ema200) and bool(row['fvg_bear'])
            if not (is_bull or is_bear): continue
            
            direction = "LONG" if is_bull else "SHORT"
            if direction == "LONG":
                entry = float(df.iloc[i-2]['high'])
                sl = float(min(df.iloc[i-1]['low'], df.iloc[i]['low'])) - (atr * 0.35)
                risk = entry - sl
                if risk <= 0 or (risk/entry) > 0.035: continue
                be = entry + (risk * 1.2)
                tp1 = entry + (risk * 1.5)
                tp2 = entry + (risk * 2.5)
                tp3 = entry + (risk * 3.5)
            else:
                entry = float(df.iloc[i-2]['low'])
                sl = float(max(df.iloc[i-1]['high'], df.iloc[i]['high'])) + (atr * 0.35)
                risk = sl - entry
                if risk <= 0 or (risk/entry) > 0.035: continue
                be = entry - (risk * 1.2)
                tp1 = entry - (risk * 1.5)
                tp2 = entry - (risk * 2.5)
                tp3 = entry - (risk * 3.5)
                
            # Buscar llenado en 12 velas
            filled = False
            fill_idx = -1
            for j in range(i+1, min(i+13, len(df))):
                bh = float(df.iloc[j]['high'])
                bl = float(df.iloc[j]['low'])
                if (direction == "LONG" and bl <= entry) or (direction == "SHORT" and bh >= entry):
                    filled = True
                    fill_idx = j
                    break
            if not filled: continue
            
            # Simular trade
            hit_be = False
            hit_tp1 = False
            hit_tp2 = False
            pnl_r = 0.0
            close_reason = ""
            rem = 1.0
            
            for k in range(fill_idx+1, min(fill_idx+40, len(df))):
                bh = float(df.iloc[k]['high'])
                bl = float(df.iloc[k]['low'])
                
                if direction == "LONG":
                    if bl <= sl:
                        if hit_be:
                            close_reason = "BREAKEVEN"
                        else:
                            close_reason = "STOP_LOSS"
                            pnl_r -= (1.0 * rem)
                        break
                    if not hit_be and bh >= be:
                        hit_be = True
                        sl = entry
                    if not hit_tp1 and bh >= tp1:
                        hit_tp1 = True
                        hit_be = True
                        sl = entry
                        pnl_r += (1.5 * 0.60)
                        rem -= 0.60
                    if hit_tp1 and not hit_tp2 and bh >= tp2:
                        hit_tp2 = True
                        sl = tp1
                        pnl_r += (2.5 * 0.20)
                        rem -= 0.20
                    if hit_tp2 and bh >= tp3:
                        pnl_r += (3.5 * 0.20)
                        rem = 0.0
                        close_reason = "TP3"
                        break
                else:
                    if bh >= sl:
                        if hit_be:
                            close_reason = "BREAKEVEN"
                        else:
                            close_reason = "STOP_LOSS"
                            pnl_r -= (1.0 * rem)
                        break
                    if not hit_be and bl <= be:
                        hit_be = True
                        sl = entry
                    if not hit_tp1 and bl <= tp1:
                        hit_tp1 = True
                        hit_be = True
                        sl = entry
                        pnl_r += (1.5 * 0.60)
                        rem -= 0.60
                    if hit_tp1 and not hit_tp2 and bl <= tp2:
                        hit_tp2 = True
                        sl = tp1
                        pnl_r += (2.5 * 0.20)
                        rem -= 0.20
                    if hit_tp2 and bl <= tp3:
                        pnl_r += (3.5 * 0.20)
                        rem = 0.0
                        close_reason = "TP3"
                        break
                        
            trades.append({
                "timestamp": df.iloc[fill_idx]['timestamp'],
                "symbol": sym,
                "direction": direction,
                "entry": entry,
                "risk_pct": (risk/entry)*100,
                "pnl_r": pnl_r,
                "reason": close_reason or ("WIN_PARTIAL" if pnl_r > 0 else "TIME_EXIT")
            })

    trades_df = pd.DataFrame(trades).sort_values('timestamp').reset_index(drop=True)
    
    # Aplicar la gestión de capital exacta con 5% de margen @ 20x apalancamiento
    for idx, t in trades_df.iterrows():
        margin = equity * margin_pct                # $10 USD si equity=$200
        nominal_size = margin * leverage           # $200 USD posición nominal
        risk_dist = t["risk_pct"] / 100.0          # Distancia al SL en % (ej. 0.8%)
        
        # 1R monetario en USD
        one_r_usd = nominal_size * risk_dist       # Ganancia o pérdida por unidad R
        
        trade_pnl_usd = t["pnl_r"] * one_r_usd
        # Descontar comisiones
        fee = nominal_size * (maker_fee * 1.5 if t["pnl_r"] > 0 else taker_fee + slippage)
        net_trade_usd = trade_pnl_usd - fee
        
        equity += net_trade_usd
        trades_df.loc[idx, "margin_usd"] = margin
        trades_df.loc[idx, "nominal_usd"] = nominal_size
        trades_df.loc[idx, "pnl_usd"] = net_trade_usd
        trades_df.loc[idx, "equity_after"] = equity

    total_net = equity - initial_capital
    roi = (total_net / initial_capital) * 100
    wins = trades_df[trades_df["pnl_usd"] > 0]
    losses = trades_df[trades_df["pnl_usd"] < 0]
    
    print(f"📊 Total de Trades Auditados     : {len(trades_df)}")
    print(f"🏆 Trades Ganadores (Wins)       : {len(wins)} ({(len(wins)/len(trades_df))*100:.1f}%)")
    print(f"❌ Trades Perdedores (Losses)    : {len(losses)} ({(len(losses)/len(trades_df))*100:.1f}%)")
    print(f"💰 Capital Inicial               : ${initial_capital:.2f} USD")
    print(f"💎 Capital Final                 : ${equity:.2f} USD")
    print(f"💵 Ganancia Neta Total           : +${total_net:.2f} USD (+{roi:.2f}%)")
    print("="*85)

if __name__ == "__main__":
    run_exact_audit()
