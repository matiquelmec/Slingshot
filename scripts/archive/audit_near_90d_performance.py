"""
=============================================================================
AUDITORÍA INSTITUCIONAL DE DESEMPEÑO: NEARUSDT (ÚLTIMOS 90 DÍAS)
=============================================================================
Evalúa el desempeño de NEARUSDT bajo el motor Slingshot v23.0 APEX SOVEREIGN:
• Temporalidad: 15 minutos (Scalp / OTE / SMC)
• Periodo: Últimos 90 días
• Gestión de Salidas: TP1 (60% @ +1.5R), TP2 (20% @ +3.0R), TP3 (10% @ +5.0R), Runner (10%)
• Breakeven: Fast BE @ +1.0R con Fee Absorber Buffer (+0.08%)
• Métricas: Win Rate, BE Rate, Profit Factor, Total R, Max Drawdown, Longs vs Shorts
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

def run_near_90d_audit():
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

    df_full = raw.sort_values('timestamp').reset_index(drop=True)
    
    # Filtrar estrictamente los últimos 90 días
    max_date = df_full['timestamp'].max()
    min_date_90d = max_date - timedelta(days=90)
    
    # Tomamos 100 velas adicionales antes de los 90d para el warm-up de indicadores (EMAs, ATR)
    df = df_full[df_full['timestamp'] >= (min_date_90d - timedelta(days=5))].copy().reset_index(drop=True)
    
    # Calcular indicadores institucionales
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
    sl_price = 0.0
    initial_risk = 0.0
    cur_sl = 0.0
    be_active = False
    tp1_hit = False
    tp2_hit = False
    tp3_hit = False
    entry_time = None
    entry_idx = 0

    # Recorrer velas dentro de la ventana de 90 días
    for i in range(40, n - 20):
        current_row = df.iloc[i]
        c_time = current_row['timestamp']
        
        # Solo abrir trades si estamos dentro de los últimos 90 días
        if c_time < min_date_90d:
            continue

        is_bull = bool(current_row.get('ob_bullish', False))
        is_bear = bool(current_row.get('ob_bearish', False))

        if in_trade:
            kh = float(current_row['high'])
            kl = float(current_row['low'])
            kc = float(current_row['close'])
            
            # Cálculo de avance en R
            r_gain = (kh - entry_price) / initial_risk if trade_dir == "LONG" else (entry_price - kl) / initial_risk

            # 1. Fast Breakeven Trigger (@ +1.0R para Altcoins)
            if not be_active and r_gain >= 1.0:
                be_active = True
                fee_buffer = entry_price * 0.0008 # 0.08% Fee Absorber
                cur_sl = (entry_price + fee_buffer) if trade_dir == "LONG" else (entry_price - fee_buffer)

            # 2. Take Profit 1 (+1.5R - 60% Volumen)
            if not tp1_hit and r_gain >= 1.5:
                tp1_hit = True
                be_active = True
                fee_buffer = entry_price * 0.0008
                cur_sl = (entry_price + fee_buffer) if trade_dir == "LONG" else (entry_price - fee_buffer)

            # 3. Take Profit 2 (+3.0R - 20% Volumen + Trailing a +2.0R)
            if not tp2_hit and r_gain >= 3.0:
                tp2_hit = True
                cur_sl = (entry_price + initial_risk * 2.0) if trade_dir == "LONG" else (entry_price - initial_risk * 2.0)

            # 4. Take Profit 3 (+5.0R - 10% Volumen + Trailing 70%)
            if not tp3_hit and r_gain >= 5.0:
                tp3_hit = True
                locked_r = r_gain * 0.70
                cur_sl = (entry_price + initial_risk * locked_r) if trade_dir == "LONG" else (entry_price - initial_risk * locked_r)

            # Chequeo de Stop Loss / Salida
            sl_triggered = (trade_dir == "LONG" and kl <= cur_sl) or (trade_dir == "SHORT" and kh >= cur_sl)
            tp_runner_max = (r_gain >= 8.0) # Target final ultra-runner

            if sl_triggered or tp_runner_max or (i - entry_idx >= 60): # Max hold 15h
                # Calcular R final capturado
                if tp_runner_max:
                    final_r = (0.60 * 1.5) + (0.20 * 3.0) + (0.10 * 5.0) + (0.10 * 8.0) # +2.80 R
                    outcome = "TP_RUNNER"
                elif tp3_hit:
                    final_r = (0.60 * 1.5) + (0.20 * 3.0) + (0.10 * 5.0) + (0.10 * 4.0) # +2.40 R
                    outcome = "TP3"
                elif tp2_hit:
                    final_r = (0.60 * 1.5) + (0.20 * 3.0) + (0.20 * 2.0) # +1.90 R
                    outcome = "TP2"
                elif tp1_hit:
                    final_r = (0.60 * 1.5) + (0.40 * 0.0) # +0.90 R (TP1 cobrado + 40% restante a BE)
                    outcome = "TP1"
                elif be_active:
                    final_r = 0.05 # Fee buffer neto en verde
                    outcome = "BREAKEVEN"
                else:
                    final_r = -1.0 # Stop Loss inicial
                    outcome = "STOP_LOSS"

                trades.append({
                    "entry_time": entry_time,
                    "exit_time": c_time,
                    "direction": trade_dir,
                    "entry_price": entry_price,
                    "exit_price": cur_sl if sl_triggered else kc,
                    "r": final_r,
                    "outcome": outcome,
                    "duration_bars": i - entry_idx,
                    "duration_mins": (i - entry_idx) * 15
                })

                in_trade = False
                continue

        else:
            # Buscar entrada OTE en Order Block confluente
            if not is_bull and not is_bear:
                continue

            direction = "LONG" if is_bull else "SHORT"
            c_price = float(current_row['close'])
            atr = float(atr_series.iloc[i]) if not pd.isna(atr_series.iloc[i]) else (c_price * 0.015)

            if direction == "LONG":
                sl = float(df.iloc[max(0, i-10):i]['low'].min()) - (atr * 0.5)
                risk = c_price - sl
            else:
                sl = float(df.iloc[max(0, i-10):i]['high'].max()) + (atr * 0.5)
                risk = sl - c_price

            # Filtros de sanidad de riesgo (entre 0.4% y 3.5%)
            if risk <= 0 or (risk / c_price) > 0.035 or (risk / c_price) < 0.004:
                continue

            in_trade = True
            trade_dir = direction
            entry_price = c_price
            sl_price = sl
            initial_risk = risk
            cur_sl = sl
            be_active = False
            tp1_hit = False
            tp2_hit = False
            tp3_hit = False
            entry_time = c_time
            entry_idx = i

    # Procesar resultados estadísticos
    tdf = pd.DataFrame(trades)
    if tdf.empty:
        print("No se generaron trades para NEARUSDT en el periodo.")
        return

    n_total = len(tdf)
    wins = tdf[tdf['r'] > 0.1]
    bes = tdf[(tdf['r'] >= 0.0) & (tdf['r'] <= 0.1)]
    losses = tdf[tdf['r'] < 0.0]

    n_wins = len(wins)
    n_bes = len(bes)
    n_losses = len(losses)

    win_rate = (n_wins / n_total) * 100
    be_rate = (n_bes / n_total) * 100
    loss_rate = (n_losses / n_total) * 100
    effective_rate = win_rate + be_rate

    gross_profit_r = wins['r'].sum() + bes['r'].sum()
    gross_loss_r = abs(losses['r'].sum())
    net_r = gross_profit_r - gross_loss_r
    profit_factor = (gross_profit_r / gross_loss_r) if gross_loss_r > 0 else 999.0

    # Drawdown
    equity = np.cumsum(tdf['r'])
    peak = np.maximum.accumulate(equity)
    drawdowns = peak - equity
    max_dd_r = np.max(drawdowns) if len(drawdowns) > 0 else 0

    # Longs vs Shorts
    longs = tdf[tdf['direction'] == 'LONG']
    shorts = tdf[tdf['direction'] == 'SHORT']
    
    long_net_r = longs['r'].sum() if len(longs) > 0 else 0
    short_net_r = shorts['r'].sum() if len(shorts) > 0 else 0

    long_wr = (len(longs[longs['r'] > 0.1]) / len(longs) * 100) if len(longs) > 0 else 0
    short_wr = (len(shorts[shorts['r'] > 0.1]) / len(shorts) * 100) if len(shorts) > 0 else 0

    # Promedios
    avg_win_r = wins['r'].mean() if n_wins > 0 else 0
    avg_duration_min = tdf['duration_mins'].mean()

    # Breakdown por meses
    tdf['month'] = tdf['entry_time'].dt.strftime('%Y-%m')
    monthly_summary = tdf.groupby('month').agg(
        trades=('r', 'count'),
        wins=('r', lambda x: (x > 0.1).sum()),
        bes=('r', lambda x: ((x >= 0.0) & (x <= 0.1)).sum()),
        losses=('r', lambda x: (x < 0.0).sum()),
        net_r=('r', 'sum')
    ).reset_index()

    # Impresión estructurada del informe
    print("=" * 85)
    print(f"📊 INFORME FORENSE DE DESEMPEÑO: NEARUSDT (ÚLTIMOS 90 DÍAS)")
    print(f"📅 Periodo: {min_date_90d.strftime('%Y-%m-%d')} hasta {max_date.strftime('%Y-%m-%d')} (90 días)")
    print(f"⚙️ Motor: Slingshot v23.0 APEX SOVEREIGN (15M SMC / OTE / Adaptive BE)")
    print("=" * 85)
    print(f"\n📈 1. MÉTRICAS CLAVE DE RENDIMIENTO:")
    print(f" • Total Operaciones:         {n_total}")
    print(f" • Ganadoras (TP1/TP2/TP3):   {n_wins} ({win_rate:.1f}%)")
    print(f" • Breakevens Salvados ($0):  {n_bes} ({be_rate:.1f}%)")
    print(f" • Pérdidas en Stop Loss:     {n_losses} ({loss_rate:.1f}%)")
    print(f" • TASA DE EFECTIVIDAD TOTAL: {effective_rate:.1f}% (Ganancias + Breakeven)")
    print(f" • RETORNO NETO TOTAL:        +{net_r:.2f} R")
    print(f" • PROFIT FACTOR:             {profit_factor:.2f}")
    print(f" • MÁXIMO DRAWDOWN:           -{max_dd_r:.2f} R")
    print(f" • Ganancia Promedio / Win:   +{avg_win_r:.2f} R")
    print(f" • Duración Media por Trade:  {avg_duration_min:.0f} minutos (~{avg_duration_min/60:.1f} horas)")

    print(f"\n⚖️ 2. DESGLOSE LONGS VS SHORTS:")
    print(f" • LONGS:  {len(longs)} trades | Win Rate: {long_wr:.1f}% | Retorno: {long_net_r:+.2f} R")
    print(f" • SHORTS: {len(shorts)} trades | Win Rate: {short_wr:.1f}% | Retorno: {short_net_r:+.2f} R")

    print(f"\n📅 3. RENDIMIENTO MES A MES (ÚLTIMOS 90 DÍAS):")
    for _, row in monthly_summary.iterrows():
        m_wr = (row['wins'] / row['trades']) * 100 if row['trades'] > 0 else 0
        print(f" • Mes {row['month']}: {row['trades']} trades | {row['wins']} Wins ({m_wr:.1f}%) | {row['bes']} BE | {row['losses']} Losses | Retorno: {row['net_r']:+.2f} R")

    print(f"\n🎯 4. DISTRIBUCIÓN DE SALIDAS (OUTCOMES):")
    outcomes = tdf['outcome'].value_counts()
    for out_name, count in outcomes.items():
        pct = (count / n_total) * 100
        print(f" • {out_name:<15}: {count:>3} trades ({pct:.1f}%)")

    print("=" * 85)

if __name__ == "__main__":
    run_near_90d_audit()
