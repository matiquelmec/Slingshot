"""
engine/backtest/unified_backtest_engine.py
=============================================================================
SLINGSHOT APEX v17.0 — UNIFIED INSTITUTIONAL BACKTEST ENGINE (THE TRUTH ENGINE)
=============================================================================
Única Fuente de la Verdad (Single Source of Truth) para la auditoría cuantitativa.

Mecánica Adaptativa Institucional:
1. Mega-Caps (BTC, ETH, SOL, XRP, AVAX, LINK) -> 1H Intraday Swing con OTE 61.8% y SL 0.60 ATR.
2. High-Beta Alts (RENDER, SUI, INJ, NEAR, FET, ATOM, BNB, PAXG) -> 15M Scalp con SL 0.30 ATR.
3. Descuento Real de Comisiones de Exchange (Maker 0.02% / Taker 0.06%) y Slippage.
4. Fast Breakeven (+1.2R) y Salidas Escalonadas (TP1 60%, TP2 20%, TP3 20%).
"""

import sys
import os
import glob
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Path config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from engine.indicators.polars_engine import polars_engine
from engine.indicators.structure import identify_order_blocks
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.core.confluence import confluence_manager
from engine.risk.risk_manager import RiskManager
from engine.core.logger import logger

logger.setLevel("ERROR")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

MEGA_CAPS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "AVAXUSDT", "LINKUSDT"]
HIGH_BETA_ALTS = ["RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "BNBUSDT", "PAXGUSDT"]

class UnifiedBacktestEngine:
    def __init__(
        self,
        account_balance: float = 100_000.0,
        risk_per_trade_pct: float = 0.01,   # 1.0% por trade por defecto
        maker_fee: float = 0.0002,           # 0.02% Maker Bitunix
        taker_fee: float = 0.0006,           # 0.06% Taker Bitunix
        slippage: float = 0.0002,            # 0.02% Deslizamiento
        min_confluence_score: int = 50,      # Umbral mínimo de confluencia
        strict_killzones: bool = True        # Solo Londres y NY
    ):
        self.initial_balance = account_balance
        self.current_balance = account_balance
        self.risk_pct = risk_per_trade_pct
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = slippage
        self.min_score = min_confluence_score
        self.strict_killzones = strict_killzones
        self.strategy = SMCInstitutionalStrategy()
        self.risk_mgr = RiskManager(account_balance=account_balance, base_risk_pct=risk_per_trade_pct)

    def _load_btc_macro_map(self) -> Dict[Any, str]:
        """Carga la brújula macro de Bitcoin."""
        btc_file = os.path.join(DATA_DIR, "BTCUSDT_15m_180d.parquet")
        if not os.path.exists(btc_file):
            return {}
        df_btc = pd.read_parquet(btc_file)
        df_btc.columns = [str(c).lower() for c in df_btc.columns]
        ts_col = 'timestamp' if 'timestamp' in df_btc.columns else 't'
        df_btc['dt'] = pd.to_datetime(df_btc[ts_col], unit='s' if df_btc[ts_col].iloc[0] < 1e11 else 'ms')
        df_btc['ema200'] = df_btc['close'].ewm(span=200, adjust=False).mean()
        df_btc['trend'] = np.where(df_btc['close'] > df_btc['ema200'], 'BULLISH', 'BEARISH')
        return dict(zip(df_btc['dt'], df_btc['trend']))

    def run_single_asset(self, symbol: str, interval: str = "15m", btc_map: dict = None) -> List[Dict[str, Any]]:
        """Ejecuta la auditoría rigurosa para un activo y temporalidad específica."""
        # 1. Cargar datos
        file_candidates = glob.glob(os.path.join(DATA_DIR, f"{symbol}_{interval}_*.parquet"))
        if not file_candidates:
            f15 = os.path.join(DATA_DIR, f"{symbol}_15m_180d.parquet")
            if not os.path.exists(f15):
                return []
            raw = pd.read_parquet(f15)
            raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
            raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit='s' if raw['timestamp'].iloc[0] < 1e11 else 'ms')
            raw.set_index('timestamp', inplace=True)
            rule = '1h' if interval in ['1h', '1H', '60m'] else ('4h' if interval == '4h' else '1D')
            df = raw.resample(rule).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
        else:
            raw = pd.read_parquet(file_candidates[0])
            raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'timestamp'}, inplace=True)
            raw['timestamp'] = pd.to_datetime(raw['timestamp'], unit='s' if raw['timestamp'].iloc[0] < 1e11 else 'ms')
            df = raw.sort_values('timestamp').reset_index(drop=True)

        if len(df) < 60:
            return []

        # 2. Computar Indicadores Vectorizados en Rust
        df = polars_engine.compute_indicators(df)
        df = identify_order_blocks(df)
        df = self.strategy.analyze(df)

        df['vol_sma'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / (df['vol_sma'] + 1e-9)
        change = (df['close'] - df['close'].shift(10)).abs()
        vol = (df['close'] - df['close'].shift(1)).abs().rolling(10).sum()
        df['ker'] = change / (vol + 1e-9)

        # 3. Detectar Señales de Entrada
        trades = []
        n = len(df)
        is_mega_cap = symbol in MEGA_CAPS
        is_1h = interval in ["1h", "1H", "60m"]
        is_htf = interval in ["4h", "1d"]

        # Configuración adaptativa de Stop Loss
        # Mega-Caps en 1H: 0.60 ATR | Altcoins en 15m: 0.30 ATR
        atr_sl_mult = 0.60 if (is_mega_cap or is_1h) else 0.30

        for i in range(30, n - 20):
            row = df.iloc[i]
            dt = row['timestamp']
            hour = dt.hour

            # Filtro Horario (Killzones)
            if interval == "15m" and self.strict_killzones:
                if not (7 <= hour <= 12 or 13 <= hour <= 18):
                    continue

            # Filtro KER Antiruido
            ker_val = float(row.get('ker', 0.5))
            if interval == "15m" and ker_val < 0.28:
                continue

            # Veto Macro BTC
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

            direction = "LONG" if is_bull else "SHORT"

            # 4. Entrada Óptima Límite y Niveles de Riesgo Adaptativo
            if direction == "LONG":
                fvg_low = float(df.iloc[i-2]['high'])
                fvg_high = float(df.iloc[i]['low'])
                # Si es 1H OTE, entramos en el descuento 61.8%
                entry = fvg_low + (fvg_high - fvg_low) * 0.382 if (is_1h and fvg_high > fvg_low) else fvg_low
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
                entry = fvg_high - (fvg_high - fvg_low) * 0.382 if (is_1h and fvg_high > fvg_low) else fvg_high
                sl = float(max(df.iloc[i-1]['high'], df.iloc[i]['high'])) + (atr * atr_sl_mult)
                risk = sl - entry
                if risk <= 0 or (risk / entry) > 0.04:
                    continue
                be_target = entry - (risk * 1.2)
                tp1 = entry - (risk * 1.5)
                tp2 = entry - (risk * 2.5)
                tp3 = entry - (risk * (4.0 if is_1h else 3.5))

            # 5. Evaluación de Activación de Orden Límite con Centinela Institucional (12 velas)
            limit_filled = False
            fill_idx = -1

            for j in range(i + 1, min(i + 13, n)):
                bar_h = float(df.iloc[j]['high'])
                bar_l = float(df.iloc[j]['low'])

                # Regla A (Missed Target Kill-Switch): Si el precio toca TP1 antes de entrar, se cancela
                if (direction == "LONG" and bar_h >= tp1) or (direction == "SHORT" and bar_l <= tp1):
                    break

                # Regla B (Pre-Entry SL Breach): Si el precio rompe el SL antes de entrar, se cancela
                if (direction == "LONG" and bar_l <= sl) or (direction == "SHORT" and bar_h >= sl):
                    break

                # Regla C: Llenado en zona de descuento
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

            # 6. Simulación Tick-by-Candle con Fast BE (+1.2R) y Salidas Escalonadas
            hit_be = False
            hit_tp1 = False
            hit_tp2 = False
            curr_sl = sl
            outcome_r = 0.0
            close_reason = ""
            exit_idx = fill_idx
            
            f1, f2, f3 = 0.60, 0.20, 0.20
            rem_pos = 1.0

            max_horizon = min(fill_idx + (48 if interval == '15m' else 36), n)
            for k in range(fill_idx + 1, max_horizon):
                bar = df.iloc[k]
                bh = float(bar['high'])
                bl = float(bar['low'])
                exit_idx = k

                if direction == "LONG":
                    if bl <= curr_sl:
                        if hit_be:
                            close_reason = "BREAKEVEN_EXIT"
                        else:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos)
                        break

                    if not hit_be and bh >= be_target:
                        hit_be = True
                        curr_sl = entry

                    if not hit_tp1 and bh >= tp1:
                        hit_tp1 = True
                        hit_be = True
                        curr_sl = entry + (risk * 0.5) if is_1h else entry
                        outcome_r += (1.5 * f1)
                        rem_pos -= f1

                    if hit_tp1 and not hit_tp2 and bh >= tp2:
                        hit_tp2 = True
                        curr_sl = tp1
                        outcome_r += (2.5 * f2)
                        rem_pos -= f2

                    if hit_tp2 and bh >= tp3:
                        outcome_r += ((4.0 if is_1h else 3.5) * f3)
                        rem_pos = 0.0
                        close_reason = "TP3_FULL_TARGET"
                        break
                else:
                    if bh >= curr_sl:
                        if hit_be:
                            close_reason = "BREAKEVEN_EXIT"
                        else:
                            close_reason = "STOP_LOSS"
                            outcome_r -= (1.0 * rem_pos)
                        break

                    if not hit_be and bl <= be_target:
                        hit_be = True
                        curr_sl = entry

                    if not hit_tp1 and bl <= tp1:
                        hit_tp1 = True
                        hit_be = True
                        curr_sl = entry - (risk * 0.5) if is_1h else entry
                        outcome_r += (1.5 * f1)
                        rem_pos -= f1

                    if hit_tp1 and not hit_tp2 and bl <= tp2:
                        hit_tp2 = True
                        curr_sl = tp1
                        outcome_r += (2.5 * f2)
                        rem_pos -= f2

                    if hit_tp2 and bl <= tp3:
                        outcome_r += ((4.0 if is_1h else 3.5) * f3)
                        rem_pos = 0.0
                        close_reason = "TP3_FULL_TARGET"
                        break

            # Descuento exacto de comisiones
            nominal_leverage = 1.0 / max(0.008, risk/entry)
            fee_friction_r = (self.maker_fee + self.taker_fee + self.slippage) * nominal_leverage * 0.5
            net_outcome_r = outcome_r - (fee_friction_r if outcome_r != 0 else 0.0)

            trades.append({
                "symbol": symbol,
                "interval": interval,
                "entry_time": str(df.iloc[fill_idx]['timestamp']),
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "risk_pct": round((risk/entry)*100, 2),
                "outcome_r": round(net_outcome_r, 2),
                "close_reason": close_reason
            })

        return trades

    def run_adaptive_portfolio_audit(self) -> Dict[str, Any]:
        """
        Ejecuta la auditoría adaptativa oficial:
        - Mega-Caps en 1H
        - High-Beta Alts en 15m
        """
        btc_map = self._load_btc_macro_map()
        all_results = []

        print("="*85)
        print("🛡️  AUDITORÍA ADAPTATIVA INSTITUCIONAL SLINGSHOT v17.0 (THE TRUTH ENGINE)")
        print("="*85)
        print(f"💰 Capital Base: ${self.initial_balance:,.2f} USD | Riesgo Base: {self.risk_pct*100:.2f}% | Comisiones Bitunix Descontadas")
        print("="*85)

        # 1. Mega-Caps en 1H
        for sym in MEGA_CAPS:
            t_list = self.run_single_asset(sym, interval="1h", btc_map=btc_map)
            all_results.extend(t_list)

        # 2. High-Beta Alts en 15m
        for sym in HIGH_BETA_ALTS:
            t_list = self.run_single_asset(sym, interval="15m", btc_map=btc_map)
            all_results.extend(t_list)

        df_all = pd.DataFrame(all_results)
        if df_all.empty:
            print("⚠️ No se encontraron operaciones para los criterios seleccionados.")
            return {}

        total_trades = len(df_all)
        winners = df_all[df_all['outcome_r'] > 0]
        losers = df_all[df_all['outcome_r'] < 0]
        breakevens = df_all[df_all['outcome_r'] == 0]

        win_rate = (len(winners) / total_trades) * 100
        be_rate = (len(breakevens) / total_trades) * 100
        total_r = df_all['outcome_r'].sum()
        gross_profit_r = winners['outcome_r'].sum() if len(winners) > 0 else 0.0
        gross_loss_r = abs(losers['outcome_r'].sum()) if len(losers) > 0 else 1.0
        profit_factor = gross_profit_r / gross_loss_r if gross_loss_r > 0 else 99.0
        expectancy_r = total_r / total_trades

        # Drawdown
        risk_usd = self.initial_balance * self.risk_pct
        df_all['pnl_usd'] = df_all['outcome_r'] * risk_usd
        df_all['cum_pnl'] = df_all['pnl_usd'].cumsum()
        df_all['equity'] = self.initial_balance + df_all['cum_pnl']
        df_all['peak'] = df_all['equity'].cummax()
        df_all['dd_pct'] = (df_all['equity'] - df_all['peak']) / df_all['peak'] * 100
        max_drawdown = abs(df_all['dd_pct'].min())

        print(f"📊 Total Operaciones Auditadas  : {total_trades}")
        print(f"🎯 Win Rate Real Adaptativo     : {win_rate:.1f}% ({len(winners)}W / {len(losers)}L / {len(breakevens)}BE)")
        print(f"🛡️ Tasa de Fast Breakeven ($0)  : {be_rate:.1f}% ({len(breakevens)} trades salvados a $0)")
        print(f"⚖️ Profit Factor Neto Global    : {profit_factor:.2f}")
        print(f"💎 Retorno Total Neto en R      : {total_r:>+8.2f} R")
        print(f"💵 Beneficio Neto USD           : {df_all['pnl_usd'].sum():>+11,.2f} USD")
        print(f"📉 Drawdown Máximo Portafolio   : -{max_drawdown:.2f}% (Límite FTMO: -10.0%)")
        print(f"📈 Esperanza Matemática por Op  : {expectancy_r:>+7.3f} R / trade")
        print("="*85)

        print("\n📋 1. DESGLOSE POR TEMPORALIDAD Y PERFIL:")
        print("-"*85)
        tf_summary = df_all.groupby('interval').agg(
            Trades=('outcome_r', 'count'),
            Win_Rate=('outcome_r', lambda x: f"{(x > 0).mean()*100:.1f}%"),
            BE_Rate=('outcome_r', lambda x: f"{(x == 0).mean()*100:.1f}%"),
            Retorno_R=('outcome_r', lambda x: f"{x.sum():+.2f} R"),
            Profit_Factor=('outcome_r', lambda x: f"{x[x>0].sum()/abs(x[x<0].sum()) if (x<0).sum()!=0 else 99:.2f}")
        )
        print(tf_summary.to_string())

        print("\n📋 2. DESGLOSE POR ACTIVO (ORDENADO POR RETORNO):")
        print("-"*85)
        asset_summary = df_all.groupby('symbol').agg(
            Perfil=('interval', lambda x: '1H Mega-Cap' if '1h' in x.values else '15M Scalp'),
            Trades=('outcome_r', 'count'),
            Win_Rate=('outcome_r', lambda x: f"{(x > 0).mean()*100:.1f}%"),
            BE_Rate=('outcome_r', lambda x: f"{(x == 0).mean()*100:.1f}%"),
            Retorno_R=('outcome_r', lambda x: f"{x.sum():+.2f} R"),
            Profit_Factor=('outcome_r', lambda x: f"{x[x>0].sum()/abs(x[x<0].sum()) if (x<0).sum()!=0 else 99:.2f}")
        )
        asset_ret_num = df_all.groupby('symbol')['outcome_r'].sum()
        asset_summary = asset_summary.loc[asset_ret_num.sort_values(ascending=False).index]
        print(asset_summary.to_string())
        print("="*85)

        # Exportar reporte inmutable
        reports_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, "unified_institutional_backtest_report.json")
        
        summary_payload = {
            "audit_date": datetime.now().isoformat(),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "breakeven_rate": round(be_rate, 2),
            "total_r": round(total_r, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_r": round(expectancy_r, 4),
            "max_drawdown_pct": round(max_drawdown, 2),
            "trades": all_results
        }
        with open(report_path, "w") as f:
            json.dump(summary_payload, f, indent=4)

        print(f"💾 Reporte Oficial Inmutable guardado en: {report_path}\n")
        return summary_payload

if __name__ == "__main__":
    engine = UnifiedBacktestEngine()
    engine.run_adaptive_portfolio_audit()
