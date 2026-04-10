"""
engine/scripts/backtest_engine.py — v6.7.2 (Mathematical Integrity)
==================================================================
Lógica de comisiones realista y Protección Inmediata (BE al TP1).
"""
import os
import sys
import pandas as pd
import numpy as np
import time
from pathlib import Path
from types import SimpleNamespace

# Añadir el root del proyecto al path
root_path = Path(__file__).parent.parent.parent
sys.path.append(str(root_path))

from engine.main_router import SlingshotRouter
from engine.core.logger import logger
from engine.router.gatekeeper import GatekeeperContext

class SlingshotBacktest:
    def __init__(self, parquet_path: str, symbol: str = "BTCUSDT"):
        self.parquet_path = parquet_path
        self.symbol = symbol.upper()
        self.router = SlingshotRouter()
        self.balance = 1000.0
        self.active_trade = None
        self.wins = 0
        self.losses = 0
        self.fee_rate = 0.0004 # 0.04% Taker (Binance/FTMO standar)

    def run(self, max_candles: int = None, offset: int = 0):
        if not os.path.exists(self.parquet_path): 
            print(f"ERROR: No se encuentra data en {self.parquet_path}")
            return
        
        df_base = pd.read_parquet(self.parquet_path)
        self.stats = {"tp1_hits": 0, "be_hits": 0, "sl_hits": 0, "tp2_hits": 0, "tp3_hits": 0}
        
        if not pd.api.types.is_datetime64_any_dtype(df_base['timestamp']):
            unit = 's' if df_base['timestamp'].iloc[0] < 2e9 else 'ms'
            df_base['timestamp'] = pd.to_datetime(df_base['timestamp'], unit=unit)
        df_base.set_index('timestamp', inplace=True)
        df_base.sort_index(inplace=True)
        
        ohlc_dict = {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}
        df_1h_htf = df_base.resample('1h').agg(ohlc_dict).dropna()
        df_4h_htf = df_base.resample('4h').agg(ohlc_dict).dropna()
        
        df_15m = df_base.tail(max_candles) if max_candles else df_base
        total = len(df_15m)

        for i in range(200, total):
            current_ts = df_15m.index[i]
            current_candle = df_15m.iloc[i]

            if self.active_trade:
                self._check_exit(current_candle)
            
            if not self.active_trade:
                hist_1h = df_1h_htf[df_1h_htf.index < current_ts].tail(50)
                hist_4h = df_4h_htf[df_4h_htf.index < current_ts].tail(50)
                
                if not hist_1h.empty and not hist_4h.empty:
                    bias_1h = "LONG" if hist_1h['close'].iloc[-1] > hist_1h['close'].iloc[-5] else "SHORT"
                    bias_4h = "LONG" if hist_4h['close'].iloc[-1] > hist_4h['close'].iloc[-5] else "SHORT"
                    htf = SimpleNamespace(
                        direction=bias_1h if bias_1h == bias_4h else "NEUTRAL", 
                        strength=0.8, reason="MTF Confirmed"
                    )

                    df_to_process = df_15m.iloc[i-200:i+1].reset_index()
                    result = self.router.process_market_data(
                        df=df_to_process, asset=self.symbol, interval="15m", htf_bias=htf, silent=True
                    )
                    
                    if result.get("signals"):
                        self._open_trade(result["signals"][0], current_candle, current_ts)

        self._finalize_report()

    def _open_trade(self, signal, candle, ts):
        size = signal["position_size_usdt"]
        # v8.1.0: Usar el precio de entrada del RiskManager para alinear con la grilla TP/SL
        entry = signal.get("entry_price", signal.get("price", float(candle['close'])))
        self.balance -= size * self.fee_rate
        self.active_trade = {
            "symbol": self.symbol, "side": signal["signal_type"], "entry_price": float(entry),
            "stop_loss": signal["stop_loss"], "tp1": signal["tp1"], "tp2": signal["tp2"], "tp3": signal["tp3"],
            "size_usdt": size, "remaining_size": size, "tp_hits": 0,
            "tp1_vol": signal.get("tp1_vol", 0.60) # Recuperar sintonía SIGMA
        }

    def _check_exit(self, candle):
        t = self.active_trade
        high, low = float(candle['high']), float(candle['low'])
        is_long = (t["side"] == "LONG")
        
        # 🎯 Módulo DELTA: Salidas Fragmentadas (60/20/20)
        current_target = t["tp1"] if t["tp_hits"] == 0 else (t["tp2"] if t["tp_hits"] == 1 else t["tp3"])
        hit_tp = (is_long and high >= current_target) or (not is_long and low <= current_target)

        if hit_tp:
            t["tp_hits"] += 1
            if t["tp_hits"] == 1:
                chunk = t["size_usdt"] * t["tp1_vol"]
                pnl = abs(t["tp1"] - t["entry_price"]) / t["entry_price"]
                self.balance += (chunk * pnl) - (chunk * self.fee_rate)
                t["remaining_size"] -= chunk
                t["stop_loss"] = t["entry_price"] # OMEGA: Escudo Total
                self.stats["tp1_hits"] += 1
            elif t["tp_hits"] == 2:
                # El restante se divide a la mitad para TP2/TP3
                chunk = t["remaining_size"] / 2
                pnl = abs(t["tp2"] - t["entry_price"]) / t["entry_price"]
                self.balance += (chunk * pnl) - (chunk * self.fee_rate)
                t["remaining_size"] -= chunk
                t["stop_loss"] = t["tp1"] # OMEGA: Lock Profit
                self.stats["tp2_hits"] += 1
            elif t["tp_hits"] == 3:
                chunk = t["remaining_size"]
                pnl = abs(t["tp3"] - t["entry_price"]) / t["entry_price"]
                self.balance += (chunk * pnl) - (chunk * self.fee_rate)
                self.stats["tp3_hits"] += 1
                self.wins += 1
                self.active_trade = None
                return

        if not self.active_trade: return

        # 🛡️ Módulo OMEGA: Verificación de Stop Loss / Break-Even
        hit_sl = (is_long and low <= t["stop_loss"]) or (not is_long and high >= t["stop_loss"])
        if hit_sl:
            pnl = (t["stop_loss"] - t["entry_price"]) / t["entry_price"] if is_long else (t["entry_price"] - t["stop_loss"]) / t["entry_price"]
            self.balance += (t["remaining_size"] * pnl) - (t["remaining_size"] * self.fee_rate)
            
            if t["tp_hits"] >= 1: 
                self.wins += 1
                self.stats["be_hits"] += 1
            else: 
                self.losses += 1
                self.stats["sl_hits"] += 1
            
            self.active_trade = None

    def _finalize_report(self):
        total = self.wins + self.losses
        winrate = (self.wins / total * 100) if total > 0 else 0
        print(f"\n{'='*40}")
        print(f"AUDITORIA SIGMA: {self.symbol}")
        print(f"{'='*40}")
        print(f"PnL: ${self.balance-1000:.2f} | Winrate: {winrate:.2f}% | Trades: {total}")
        print(f"\nTELEMETRIA OMEGA (Exits):")
        print(f" TP1: {self.stats['tp1_hits']} | TP2: {self.stats['tp2_hits']} | TP3: {self.stats['tp3_hits']}")
        print(f" BE/Lock (Break-Even): {self.stats['be_hits']}")
        print(f" Hard SL (Total Loss): {self.stats['sl_hits']}")
        print(f"{'='*40}\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--candles", type=int, default=5000)
    args = parser.parse_args()
    
    symbol_lower = args.symbol.lower()
    data_file = str(root_path / "tmp" / "data" / f"{symbol_lower}_15m.parquet")
    
    SlingshotBacktest(data_file, symbol=args.symbol).run(max_candles=args.candles)
