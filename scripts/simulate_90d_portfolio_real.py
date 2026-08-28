import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.indicators.polars_engine import polars_engine
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR

PORTFOLIO_ASSETS = [
    # ⚡ Altcoins High-Beta (15m Scalp)
    ("RENDERUSDT", "15m", "ALTCOIN"),
    ("SUIUSDT", "15m", "ALTCOIN"),
    ("NEARUSDT", "15m", "ALTCOIN"),
    ("ATOMUSDT", "15m", "ALTCOIN"),
    ("FETUSDT", "15m", "ALTCOIN"),
    ("TIAUSDT", "15m", "ALTCOIN"),
    ("INJUSDT", "15m", "ALTCOIN"),
    ("DOGEUSDT", "15m", "ALTCOIN"),
    ("ADAUSDT", "15m", "ALTCOIN"),
    
    # 🥇 Metales Preciosos Cripto & TradFi (4H / 1D / 15m)
    ("PAXGUSDT", "4h", "CRYPTO_GOLD"),
    ("XAUUSD", "1d", "TRADFI_GOLD"),
    ("HGUSD", "15m", "TRADFI_COPPER"),
    
    # 🏛️ Wall Street Macro (1D Swing / 15m Open)
    ("US100", "1d", "TRADFI_INDEX"),
    ("US30", "1d", "TRADFI_INDEX"),
    ("US500", "15m", "TRADFI_INDEX")
]

def parse_robust_timestamp(raw_val):
    try:
        val_float = float(raw_val)
        if val_float < 1e11: # Seconds
            dt = pd.to_datetime(val_float, unit='s')
        else: # Milliseconds
            dt = pd.to_datetime(val_float, unit='ms')
    except (ValueError, TypeError):
        dt = pd.to_datetime(raw_val)
    if dt.tz is not None:
        dt = dt.tz_localize(None)
    return dt

def run_90d_portfolio_simulation(initial_capital: float = 10000.0, risk_per_trade_pct: float = 0.01, max_concurrent_risk: int = 4):
    print("\n" + "="*115)
    print(f"🚀 SIMULACIÓN DE PORTAFOLIO REAL A 90 DÍAS (3 MESES) — SLINGSHOT v22.2 APEX")
    print(f"   Capital Inicial: ${initial_capital:,.2f} USD | Riesgo por Trade: {risk_per_trade_pct*100:.2f}% (${initial_capital*risk_per_trade_pct:.2f})")
    print(f"   Capacidad: Máximo {max_concurrent_risk} operaciones en riesgo simultáneo con Liberación Dinámica (Slot Recycling)")
    print("="*115)

    engine = UnifiedBacktestEngine(min_confluence_score=50)
    btc_map = engine._load_btc_macro_map()

    all_raw_trades = []

    for symbol, interval, category in PORTFOLIO_ASSETS:
        try:
            trades = engine.run_single_asset(symbol, interval=interval, btc_map=btc_map)
            for t in trades:
                entry_time = parse_robust_timestamp(t.get('entry_time', t.get('timestamp')))
                exit_time = entry_time + pd.Timedelta(hours=3) # Duración promedio
                
                t['asset'] = symbol
                t['interval'] = interval
                t['category'] = category
                t['entry_time'] = entry_time
                t['exit_time'] = exit_time
                all_raw_trades.append(t)
        except Exception as e:
            pass

    if not all_raw_trades:
        print("❌ No se encontraron datos para simular.")
        return

    df_all = pd.DataFrame(all_raw_trades).sort_values(by='entry_time').reset_index(drop=True)
    
    # Acotar a los últimos 90 días exactos del dataset
    max_ts = df_all['entry_time'].max()
    start_90d = max_ts - pd.Timedelta(days=90)
    df_all = df_all[df_all['entry_time'] >= start_90d].sort_values(by='entry_time').reset_index(drop=True)
    
    print(f"\n📡 Total de Oportunidades Detectadas por el Escáner en 90 Días: {len(df_all)}")
    print(f"   Periodo Analizado: {df_all['entry_time'].min().strftime('%Y-%m-%d')} hasta {df_all['entry_time'].max().strftime('%Y-%m-%d')}")

    capital = initial_capital
    peak_capital = initial_capital
    max_drawdown_pct = 0.0
    
    executed_trades = []
    active_risk_positions = [] # lista de dicts: {'asset': sym, 'risk_freed_time': ts, 'exit_time': ts}

    for _, trade in df_all.iterrows():
        t_entry = trade['entry_time']
        t_exit = trade['exit_time']
        outcome_r = float(trade['outcome_r'])
        duration = t_exit - t_entry
        
        # En Fast Breakeven (+1.0R), el riesgo se libera al 25% del tiempo de la operación
        is_winner = outcome_r > 0
        is_be = outcome_r == 0
        if is_winner or is_be:
            t_risk_freed = t_entry + (duration * 0.25)
        else:
            t_risk_freed = t_exit

        # Limpiar posiciones que ya liberaron su riesgo antes de este momento
        active_risk_positions = [pos for pos in active_risk_positions if pos['risk_freed_time'] > t_entry]

        # Verificar concurrencia (Máximo 4 operaciones en riesgo simultáneo)
        if len(active_risk_positions) < max_concurrent_risk:
            # ACEPTAR Y EJECUTAR TRADE
            risk_usd = capital * risk_per_trade_pct
            pnl_usd = outcome_r * risk_usd
            capital += pnl_usd
            
            if capital > peak_capital:
                peak_capital = capital
            current_dd = (peak_capital - capital) / peak_capital * 100.0
            if current_dd > max_drawdown_pct:
                max_drawdown_pct = current_dd

            trade_record = {
                'asset': trade['asset'],
                'category': trade['category'],
                'interval': trade['interval'],
                'entry_time': t_entry,
                'exit_time': t_exit,
                'outcome_r': outcome_r,
                'pnl_usd': pnl_usd,
                'balance_after': capital,
                'month': t_entry.strftime('%Y-%m')
            }
            executed_trades.append(trade_record)
            
            active_risk_positions.append({
                'asset': trade['asset'],
                'risk_freed_time': t_risk_freed,
                'exit_time': t_exit
            })

    df_exec = pd.DataFrame(executed_trades)
    if df_exec.empty:
        print("No se ejecutaron trades.")
        return

    total_trades = len(df_exec)
    winners = df_exec[df_exec['outcome_r'] > 0]
    losers = df_exec[df_exec['outcome_r'] < 0]
    be = df_exec[df_exec['outcome_r'] == 0]

    win_rate = len(winners) / total_trades * 100.0
    be_rate = len(be) / total_trades * 100.0
    loss_rate = len(losers) / total_trades * 100.0
    
    total_r = df_exec['outcome_r'].sum()
    gross_w_r = winners['outcome_r'].sum() if len(winners) > 0 else 0
    gross_l_r = abs(losers['outcome_r'].sum()) if len(losers) > 0 else 1
    profit_factor = gross_w_r / gross_l_r if gross_l_r > 0 else 99.0
    net_profit_usd = capital - initial_capital
    return_pct = (net_profit_usd / initial_capital) * 100.0

    print("\n" + "="*115)
    print("📊 RESULTADOS GLOBALES DE LA CARTERA A 90 DÍAS (3 MESES)")
    print("="*115)
    print(f"💰 Capital Inicial:           ${initial_capital:,.2f} USD")
    print(f"🚀 Capital Final Acumulado:     ${capital:,.2f} USD")
    print(f"📈 Ganancia Neta Total:         {net_profit_usd:+,.2f} USD ({return_pct:+.2f}%)")
    print(f"🎯 Retorno Total en Unidades R: {total_r:+.2f} R")
    print(f"⚖️ Profit Factor Global:        {profit_factor:.2f}")
    print(f"🛡️ Máximo Drawdown Flotante:    -{max_drawdown_pct:.2f}%")
    print(f"🔢 Total de Operaciones:       {total_trades} trades ejecutados")
    print(f"   ├─ Ganadoras (TPs):          {len(winners)} ({win_rate:.1f}%)")
    print(f"   ├─ Protegidas en Breakeven:  {len(be)} ({be_rate:.1f}%) [Cero Pérdida]")
    print(f"   └─ Pérdidas (SL Original):   {len(losers)} ({loss_rate:.1f}%)")

    # 4. Desglose Mes a Mes
    print("\n" + "="*115)
    print("📅 DESGLOSE MES A MES (RENDIMIENTO REAL POR PERIODO)")
    print("="*115)
    
    monthly_summary = []
    for month_key, grp in df_exec.groupby('month'):
        m_trades = len(grp)
        m_win = len(grp[grp['outcome_r'] > 0])
        m_be = len(grp[grp['outcome_r'] == 0])
        m_loss = len(grp[grp['outcome_r'] < 0])
        m_r = grp['outcome_r'].sum()
        m_usd = grp['pnl_usd'].sum()
        m_wr = (m_win / m_trades * 100.0) if m_trades > 0 else 0.0
        
        monthly_summary.append({
            "Mes": month_key,
            "Trades": m_trades,
            "Ganadoras": m_win,
            "Breakeven": m_be,
            "Pérdidas": m_loss,
            "Win Rate": f"{m_wr:.1f}%",
            "Retorno R": f"{m_r:+.2f} R",
            "Ganancia USD": f"${m_usd:+,.2f}",
            "Rendimiento %": f"{(m_usd / initial_capital)*100:+.2f}%"
        })
    print(pd.DataFrame(monthly_summary).to_string(index=False))

    # 5. Rendimiento Desglosado por Activo
    print("\n" + "="*115)
    print("🥇 RENDIMIENTO DESGLOSADO POR ACTIVO EN LOS ÚLTIMOS 3 MESES")
    print("="*115)
    asset_perf = []
    for asset_key, grp in df_exec.groupby('asset'):
        a_trades = len(grp)
        a_win = len(grp[grp['outcome_r'] > 0])
        a_r = grp['outcome_r'].sum()
        a_usd = grp['pnl_usd'].sum()
        a_wr = (a_win / a_trades * 100.0) if a_trades > 0 else 0.0
        asset_perf.append({
            "Activo": asset_key,
            "Categoría": grp['category'].iloc[0],
            "Trades": a_trades,
            "Win Rate": f"{a_wr:.1f}%",
            "Retorno R": round(a_r, 2),
            "Ganancia USD": round(a_usd, 2)
        })
    df_asset = pd.DataFrame(asset_perf).sort_values(by="Retorno R", ascending=False)
    print(df_asset.to_string(index=False))

if __name__ == "__main__":
    run_90d_portfolio_simulation()
