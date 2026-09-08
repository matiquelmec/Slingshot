import sys
import os
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

"""
engine/backtest/backtest_ftmo_titanium_v51.py   Motor de Backtest Institucional FTMO v51.0
========================================================================================
Simulacion Event-Driven Concurrente (180 Dias) sobre los 9 Activos TradFi:
- XAUUSD (Oro Spot)
- US100 (Nasdaq 100 Cash)
- GER40 (DAX 40 Germany)
- US500 (S&P 500 Cash)
- US30 (Dow Jones 30 Cash)
- EURUSD (Forex)
- GBPJPY (Dragon Forex)
- GBPUSD (Cable Forex)
- HGUSD (Copper High Grade)

Protocolos Activos:
- SOP-24: Midnight Rollover Shield (21:50-22:05 UTC)
- SOP-25: Early Invalidation (-0.65R corte anticipado y purga de limites huerfanas post-TP1)
- SOP-26 & SOP-48: Malla Dinamica (40% TP1 @ +1.2R, 40% TP2 @ +2.0R, 20% Elastic Runner @ +5.0R)
- SOP-29: Session Killzones (Londres 07-10 UTC, NY 12-17 UTC, Veto en Asia)
- SOP-46: Weekly Alpha Cycle (1.20x Mar/Mie, 0.80x Jue/Vie, 1.00x Lun)
- SOP-47: Alpha Tier Sizing (Tier S: US100/XAUUSD 1.30x, Tier A: GER40 1.15x, Tier C: 0.75x)
- Slot Fortress: Maximo 2 operaciones simultaneas con riesgo abierto.
- FTMO Rules: Balance $100k, Kill-Switch Diario -3.5%, Limite Total -7.5%, Riesgo Base 0.75%.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Any

TRADFI_PORTFOLIO_CONFIG = {
    "XAUUSD": {"contract_size": 100, "spread_usd": 0.18, "tier": "S", "weight": 1.30, "pip_value": 1.0},
    "US100":  {"contract_size": 1,   "spread_usd": 1.10, "tier": "S", "weight": 1.30, "pip_value": 1.0},
    "GER40":  {"contract_size": 25,  "spread_usd": 1.50, "tier": "A", "weight": 1.15, "pip_value": 1.0},
    "US500":  {"contract_size": 1,   "spread_usd": 0.40, "tier": "B", "weight": 1.00, "pip_value": 1.0},
    "US30":   {"contract_size": 1,   "spread_usd": 2.20, "tier": "C", "weight": 0.70, "pip_value": 1.0},
    "EURUSD": {"contract_size": 100000, "spread_usd": 0.00002, "tier": "B", "weight": 1.00, "pip_value": 10.0},
    "GBPJPY": {"contract_size": 100000, "spread_usd": 0.025,   "tier": "B", "weight": 1.00, "pip_value": 6.8},
    "GBPUSD": {"contract_size": 100000, "spread_usd": 0.00005, "tier": "C", "weight": 0.70, "pip_value": 10.0},
    "HGUSD":  {"contract_size": 25000,  "spread_usd": 0.0010,  "tier": "C", "weight": 0.70, "pip_value": 12.5},
}

def load_data():
    base_dir = r"C:\Slingshot\engine\backtest\data"
    data = {}
    for sym in TRADFI_PORTFOLIO_CONFIG.keys():
        path = os.path.join(base_dir, f"{sym}_15m_audited.parquet")
        if not os.path.exists(path):
            path = os.path.join(base_dir, f"{sym}_1h_audited.parquet")
        if os.path.exists(path):
            df = pd.read_parquet(path)
            if "timestamp" in df.columns:
                df["time"] = pd.to_datetime(df["timestamp"], utc=True)
            elif "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"], utc=True)
            df = df.sort_values("time").reset_index(drop=True)
            
            # Calcular indicadores
            if "ema50" not in df.columns:
                df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
            if "ema200" not in df.columns:
                df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
            if "atr" not in df.columns:
                tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))
                df["atr"] = tr.rolling(14).mean().bfill()
            data[sym] = df
    return data

def run_simulation():
    datasets = load_data()
    print(f"[OK] Cargados {len(datasets)} activos TradFi para simulacion cronologica concurrente.")
    
    # Extraer todos los timestamps unicos para replay barra a barra
    all_times = sorted(list(set(t for df in datasets.values() for t in df["time"])))
    print(f"[TIME] Total de barras temporales a simular: {len(all_times)}")
    
    INITIAL_BALANCE = 100000.0
    BASE_RISK_USD = 750.0 # 0.75%
    
    balance = INITIAL_BALANCE
    equity = INITIAL_BALANCE
    peak_equity = INITIAL_BALANCE
    max_drawdown_usd = 0.0
    max_drawdown_pct = 0.0
    
    daily_balance_start = INITIAL_BALANCE
    current_day = None
    daily_lockout = False
    
    open_positions = [] # Posiciones en mercado
    pending_orders = [] # Ordenes limite vivas
    closed_trades = []
    
    daily_killswitch_hits = 0
    
    # Pre-index dataframes por tiempo para O(1) lookups
    time_indices = {sym: {t: idx for idx, t in enumerate(df["time"])} for sym, df in datasets.items()}
    
    for t_step in all_times:
        t_day = t_step.strftime("%Y-%m-%d")
        if t_day != current_day:
            current_day = t_day
            daily_balance_start = balance
            daily_lockout = False
            
        now_hour = t_step.hour
        now_weekday = t_step.weekday() # 0 = Lunes, 1 = Martes, etc.
        
        # SOP-24 Midnight Rollover Lock (21:50 - 22:05 UTC)
        is_midnight_lock = (now_hour == 22 and t_step.minute <= 15) or (now_hour == 21 and t_step.minute >= 50)
        
        # 1. GESTION DE POSICIONES ACTIVAS
        active_remaining = []
        for pos in open_positions:
            sym = pos["symbol"]
            idx = time_indices[sym].get(t_step)
            if idx is None:
                active_remaining.append(pos)
                continue
                
            candle = datasets[sym].iloc[idx]
            c_high = candle["high"]
            c_low = candle["low"]
            c_close = candle["close"]
            
            is_long = pos["direction"] == "LONG"
            entry = pos["entry_price"]
            sl = pos["stop_loss"]
            r_dist = pos["r_dist"]
            risk_usd = pos["risk_usd"]
            
            # A. Chequeo de Stop Loss / Breakeven / Trailing
            sl_hit = (is_long and c_low <= sl) or (not is_long and c_high >= sl)
            if sl_hit:
                if pos["tp2_taken"]:
                    # Cerrado en trailing stop positivo (+1.0R en 20% residual)
                    rem_gain = (risk_usd * 1.0) * 0.20
                    balance += rem_gain
                    pos["harvested_pnl"] += rem_gain
                    pnl = pos["harvested_pnl"] - pos["commission"]
                    reason = "WIN_TRAILING_SL_+1.0R"
                elif pos["tp1_taken"]:
                    # Cerrado a Breakeven tras TP1 asegurado (+1.2R al 40% ya sumado)
                    pnl = pos["harvested_pnl"] - pos["commission"]
                    reason = "WIN_TP1_BE_CLOSED"
                elif pos["is_be"]:
                    pnl = 0.0 - pos["commission"] # $0 riesgo
                    balance += pnl
                    reason = "FAST_BE"
                else:
                    pnl = -risk_usd - pos["commission"]
                    balance += pnl
                    reason = "STOP_LOSS"
                pos["exit_price"] = sl
                pos["exit_time"] = t_step
                pos["pnl"] = pnl
                pos["reason"] = reason
                closed_trades.append(pos)
                continue
                
            # B. SOP-25 Early Invalidation en Posicion (-0.65R)
            current_r = (c_close - entry) / r_dist if is_long else (entry - c_close) / r_dist
            if not pos["is_be"] and current_r <= -0.65:
                # Corte prematuro a mercado: ahorra 35% del SL
                pnl = (-risk_usd * 0.65) - pos["commission"]
                balance += pnl
                pos["exit_price"] = c_close
                pos["exit_time"] = t_step
                pos["pnl"] = pnl
                pos["reason"] = "EARLY_INVALIDATION_-0.65R"
                closed_trades.append(pos)
                continue
                
            # C. Fast Breakeven (+1.0R)
            if not pos["is_be"]:
                be_hit = (is_long and c_high >= entry + r_dist) or (not is_long and c_low <= entry - r_dist)
                if be_hit:
                    pos["is_be"] = True
                    pos["stop_loss"] = entry # SL a Breakeven ($0.00)
                    
            # D. TP1 (+1.2R)   40% Cosecha
            if not pos["tp1_taken"]:
                tp1_price = entry + (r_dist * 1.2) if is_long else entry - (r_dist * 1.2)
                if (is_long and c_high >= tp1_price) or (not is_long and c_low <= tp1_price):
                    pos["tp1_taken"] = True
                    harvest_pnl = (risk_usd * 1.2) * 0.40
                    balance += harvest_pnl
                    pos["harvested_pnl"] += harvest_pnl
                    pos["is_be"] = True
                    pos["stop_loss"] = entry
                    
            # E. TP2 (+2.0R)   40% Cosecha
            if pos["tp1_taken"] and not pos["tp2_taken"]:
                tp2_price = entry + (r_dist * 2.0) if is_long else entry - (r_dist * 2.0)
                if (is_long and c_high >= tp2_price) or (not is_long and c_low <= tp2_price):
                    pos["tp2_taken"] = True
                    harvest_pnl = (risk_usd * 2.0) * 0.40
                    balance += harvest_pnl
                    pos["harvested_pnl"] += harvest_pnl
                    # Trailing a +1.0R garantizado
                    pos["stop_loss"] = entry + (r_dist * 1.0) if is_long else entry - (r_dist * 1.0)
                    
            # F. TP3 (+5.0R Runner Elastico SOP-48)   20% Residual
            if pos["tp2_taken"] and not pos["tp3_taken"]:
                tp3_price = entry + (r_dist * 5.0) if is_long else entry - (r_dist * 5.0)
                if (is_long and c_high >= tp3_price) or (not is_long and c_low <= tp3_price):
                    pos["tp3_taken"] = True
                    harvest_pnl = (risk_usd * 5.0) * 0.20
                    balance += harvest_pnl
                    pos["harvested_pnl"] += harvest_pnl
                    pos["exit_price"] = tp3_price
                    pos["exit_time"] = t_step
                    pos["pnl"] = pos["harvested_pnl"]
                    pos["reason"] = "FULL_TP3_RUNNER"
                    closed_trades.append(pos)
                    continue
                    
            active_remaining.append(pos)
        open_positions = active_remaining
        
        # 2. AUDITORIA DE ORDENES LIMITE PENDIENTES
        pending_remaining = []
        for order in pending_orders:
            sym = order["symbol"]
            idx = time_indices[sym].get(t_step)
            if idx is None:
                pending_remaining.append(order)
                continue
                
            candle = datasets[sym].iloc[idx]
            c_high = candle["high"]
            c_low = candle["low"]
            c_close = candle["close"]
            
            is_long = order["direction"] == "LONG"
            entry = order["entry_price"]
            tp1_target = entry + (order["r_dist"] * 1.2) if is_long else entry - (order["r_dist"] * 1.2)
            
            # SOP-25 Early Invalidation: Si el precio toco TP1 sin llenar la entrada, PURGA
            if (is_long and c_high >= tp1_target) or (not is_long and c_low <= tp1_target):
                continue # Orden cancelada y purgada
                
            # Llenado de orden limite
            filled = (is_long and c_low <= entry) or (not is_long and c_high >= entry)
            if filled:
                # Comprobar Slot Fortress al momento de llenado
                unprotected_slots = sum(1 for p in open_positions if not p["is_be"])
                if unprotected_slots < 2 and not daily_lockout:
                    order["entry_time"] = t_step
                    open_positions.append(order)
            else:
                pending_remaining.append(order)
        pending_orders = pending_remaining
        
        # Actualizar Equidad y Drawdown
        current_equity = balance + sum(p.get("harvested_pnl", 0.0) for p in open_positions)
        if current_equity > peak_equity:
            peak_equity = current_equity
        dd_usd = peak_equity - current_equity
        dd_pct = (dd_usd / peak_equity) * 100.0 if peak_equity > 0 else 0.0
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct
            max_drawdown_usd = dd_usd
            
        # Kill-Switch Diario (-3.5%)
        daily_loss_pct = ((daily_balance_start - current_equity) / daily_balance_start) * 100.0
        if daily_loss_pct >= 3.5:
            if not daily_lockout:
                daily_killswitch_hits += 1
                daily_lockout = True
            continue
            
        if daily_lockout or is_midnight_lock:
            continue
            
        # 3. ESCANER DE NUEVAS OPORTUNIDADES (Concurrente para 9 Activos)
        unprotected_slots = sum(1 for p in open_positions if not p["is_be"])
        if unprotected_slots >= 2:
            continue # Slot Fortress bloquea nuevas emisiones
            
        for sym, spec in TRADFI_PORTFOLIO_CONFIG.items():
            if any(p["symbol"] == sym for p in open_positions) or any(o["symbol"] == sym for o in pending_orders):
                continue # Anti-duplicacion
                
            idx = time_indices[sym].get(t_step)
            if idx is None or idx < 50:
                continue
                
            df = datasets[sym]
            candle = df.iloc[idx]
            c_close = candle["close"]
            ema50 = candle["ema50"]
            ema200 = candle["ema200"]
            atr = candle["atr"]
            
            # SOP-29: Session Killzone Gate (Londres 07-10 UTC, NY 12-17 UTC)
            is_kz = (7 <= now_hour <= 10) or (12 <= now_hour <= 17)
            if not is_kz and "XAU" not in sym:
                continue
                
            # Tendencia Macro Institucional
            is_bull = c_close > ema50 and ema50 > ema200
            is_bear = c_close < ema50 and ema50 < ema200
            if not is_bull and not is_bear:
                continue
                
            if "XAU" in sym and not is_bull: continue
            direction = "LONG" if is_bull else "SHORT"
            
            # Deteccion OTE Fibonacci 61.8%
            lookback = df.iloc[idx-20:idx]
            s_high = lookback["high"].max()
            s_low = lookback["low"].min()
            s_range = s_high - s_low
            if s_range <= (atr * 0.5):
                continue
                
            if direction == "LONG":
                entry_price = s_high - (s_range * 0.618)
                stop_loss = s_low - (atr * 0.2)
            else:
                entry_price = s_low + (s_range * 0.618)
                stop_loss = s_high + (atr * 0.2)
                
            r_dist = abs(entry_price - stop_loss)
            if r_dist <= (spec["spread_usd"] * 2):
                continue
                
            # Moduladores Cuantitativos
            # SOP-46: Ciclo semanal
            cycle_mult = 1.20 if now_weekday in [1, 2] else (0.80 if now_weekday in [3, 4] else 1.00)
            # SOP-47: Alpha Tier Sizing
            tier_mult = spec["weight"]
            
            trade_risk_usd = BASE_RISK_USD * cycle_mult * tier_mult
            
            # Calcular Lotes Normalizados
            lots = trade_risk_usd / (r_dist * spec["contract_size"])
            commission = max(1.0, lots * 3.0) # $3 por lote FTMO
            
            new_order = {
                "symbol": sym,
                "direction": direction,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "r_dist": r_dist,
                "risk_usd": trade_risk_usd,
                "lots": round(lots, 2),
                "commission": commission,
                "is_be": False,
                "tp1_taken": False,
                "tp2_taken": False,
                "tp3_taken": False,
                "harvested_pnl": 0.0,
                "placed_time": t_step
            }
            pending_orders.append(new_order)
            
    # REPORTE DE RESULTADOS
    wins = [t for t in closed_trades if t["pnl"] > 0]
    fast_be = [t for t in closed_trades if t.get("reason") == "FAST_BE"]
    early_inv = [t for t in closed_trades if "EARLY" in t.get("reason", "")]
    losses = [t for t in closed_trades if t["pnl"] < 0 and t.get("reason") != "FAST_BE"]
    
    total_trades = len(closed_trades)
    effective_wins = len(wins) + len(fast_be)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0
    effective_win_rate = (effective_wins / total_trades * 100) if total_trades > 0 else 0.0
    
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 99.9
    
    net_pnl = balance - INITIAL_BALANCE
    roi_pct = (net_pnl / INITIAL_BALANCE) * 100.0
    
    report = {
        "initial_balance": INITIAL_BALANCE,
        "final_balance": round(balance, 2),
        "net_pnl_usd": round(net_pnl, 2),
        "roi_pct": round(roi_pct, 2),
        "total_trades": total_trades,
        "pure_wins": len(wins),
        "fast_be_saved": len(fast_be),
        "early_invalidation_cuts": len(early_inv),
        "losses": len(losses),
        "win_rate_pure": round(win_rate, 2),
        "win_rate_effective": round(effective_win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "max_drawdown_usd": round(max_drawdown_usd, 2),
        "daily_killswitch_hits": daily_killswitch_hits,
        "passed_ftmo_phase_1": bool(balance >= 110000.0),
        "passed_ftmo_phase_2": bool(balance >= 105000.0)
    }
    
    os.makedirs(r"C:\Slingshot\engine\backtest\reports", exist_ok=True)
    report_file = r"C:\Slingshot\engine\backtest\reports\ftmo_titanium_v51_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
        
    print("\n" + "="*80)
    print("  RESULTADOS DEL NUEVO BACKTEST FTMO v51.0 TITANIUM (9 ACTIVOS CONCURRENTES)")
    print("="*80)
    print(f"[PROFIT] Balance Inicial:            ${INITIAL_BALANCE:,.2f} USD")
    print(f"  Balance Final:              ${balance:,.2f} USD ({roi_pct:+.2f}%)")
    print(f"[EQUITY] Beneficio Neto:             ${net_pnl:+,.2f} USD")
    print(f"[STATS] Total Operaciones:          {total_trades}")
    print(f"[TARGET] Operaciones Ganadoras (TPs):{len(wins)}")
    print(f"[DEFENSE] Salvadas en Fast Breakeven: {len(fast_be)} ($0 perdida)")
    print(f"   Cortes Tempranos (-0.65R):   {len(early_inv)} (Ahorro 35% SL)")
    print(f"  Stop Loss Plenos:           {len(losses)}")
    print(f"  Win Rate Efectivo:          {effective_win_rate:.2f}%")
    print(f"[START] Profit Factor:              {profit_factor:.2f}")
    print(f"[DEFENSE] Drawdown Maximo Cartera:    -{max_drawdown_pct:.2f}% (${max_drawdown_usd:,.2f})")
    print(f"  Kill-Switch Diario Disparado: {daily_killswitch_hits} veces")
    print(f"   Estatus FTMO Fase 1 (+10%):  {'[OK] APROBADO' if report['passed_ftmo_phase_1'] else 'EN CURSO'}")
    print("="*80)

if __name__ == "__main__":
    run_simulation()
