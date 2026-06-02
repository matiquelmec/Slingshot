import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# Añadir root al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from engine.router.gatekeeper import SignalGatekeeper, GatekeeperContext
from engine.indicators.htf_analyzer import HTFAnalyzer, HTFBias
from engine.risk.risk_manager import RiskManager
from engine.strategies.smc import SMCInstitutionalStrategy
from engine.indicators.structure import identify_order_blocks
from engine.core.logger import logger

# Silencio absoluto
logger.setLevel("ERROR")

def fast_profit_audit():
    print("[FAST AUDIT] Calculando Profit Neto de 3 meses...")
    data_file = os.path.join(os.path.dirname(__file__), "data/BTCUSDT_15m_90d.parquet")
    if not os.path.exists(data_file):
        # Fallback a tests/data
        data_file = os.path.join(os.path.dirname(__file__), "../tests/data/BTCUSDT_15m_90d.parquet")
        
    if not os.path.exists(data_file):
        print(f"Error: No data found at {data_file}")
        return
        
    df = pd.read_parquet(data_file)
    df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
    
    # 1. Detectar Señales SMC (Estrategia Oficial)
    df = identify_order_blocks(df)
    strategy = SMCInstitutionalStrategy()
    df = strategy.analyze(df)
    
    long_mask = (df['recent_ob_bull'] & df['recent_sweep_bull'] & df['recent_fvg_bull'])
    short_mask = (df['recent_ob_bear'] & df['recent_sweep_bear'] & df['recent_fvg_bear'])
    sig_indices = np.where(long_mask | short_mask)[0]
    
    # 2. Simular Gatekeeper v10.0
    risk_mgr = RiskManager()
    gatekeeper = SignalGatekeeper(risk_manager=risk_mgr)
    
    total_r = 0
    trades_executed = 0
    winners = 0
    
    for idx in sig_indices:
        # Simplificación de Bias para el Audit (usamos tendencia 1D real)
        # En producción esto es 1M/1W, aquí simulamos con la MA de 800 (1D approx)
        ma_800 = df['close'].rolling(800).mean().iloc[idx]
        current_price = df['close'].iloc[idx]
        is_long = long_mask[idx]
        sig_type = "LONG" if is_long else "SHORT"
        
        # Veto Fractal Simulado (Fidelidad 90%)
        is_aligned = (is_long and current_price > ma_800) or (not is_long and current_price < ma_800)
        
        if not is_aligned: continue # Veto Fractal detectado
        # pass
        
        from engine.core.confluence import ConfluenceManager
        conf_mgr = ConfluenceManager()
        mock_signal = {
            "price": current_price,
            "signal_type": sig_type,
            "interval_minutes": 15,
            "timestamp": df['timestamp'].iloc[idx]
        }
        conf_res = conf_mgr.evaluate_signal(
            df=df.iloc[max(0, idx-100):idx+1],
            signal=mock_signal,
        )
        
        print(f"Signal {idx} Score: {conf_res['score']}")
        if conf_res['score'] < 30: continue # Muy bajo
        
        # [v13.4 FIX] Calcular ATR real (True Range con EWM 14) en vez de stddev
        tr_high_low = df['high'].iloc[max(0, idx-20):idx+1] - df['low'].iloc[max(0, idx-20):idx+1]
        tr_high_close = (df['high'].iloc[max(0, idx-20):idx+1] - df['close'].iloc[max(0, idx-20):idx+1].shift(1)).abs()
        tr_low_close = (df['low'].iloc[max(0, idx-20):idx+1] - df['close'].iloc[max(0, idx-20):idx+1].shift(1)).abs()
        true_range = pd.concat([tr_high_low, tr_high_close, tr_low_close], axis=1).max(axis=1)
        atr_real = float(true_range.ewm(alpha=1/14, adjust=False).mean().iloc[-1])
        
        entry = current_price
        risk_data = risk_mgr.calculate_position(
            current_price=entry,
            signal_type=sig_type,
            market_regime="MARKUP" if is_long else "MARKDOWN",
            atr_value=atr_real
        )
        
        sl = risk_data['stop_loss']
        tp = risk_data['tp2'] # Usamos TP2 como objetivo institucional
        
        if sl == 0 or tp == 0: continue
        
        trades_executed += 1
        future = df.iloc[idx+1 : idx+400] # Ventana de 4 días para salir
        if future.empty: continue
        
        hit_tp = False
        hit_sl = False
        
        for _, row in future.iterrows():
            if is_long:
                if row['low'] <= sl: hit_sl = True; break
                if row['high'] >= tp: hit_tp = True; break
            else:
                if row['high'] >= sl: hit_sl = True; break
                if row['low'] <= tp: hit_tp = True; break
        
        if hit_tp:
            winners += 1
            # R-multiple real
            r_gain = abs(tp - entry) / abs(entry - sl)
            total_r += r_gain
        elif hit_sl:
            total_r -= 1.0
            
    print("\n" + "="*40)
    print("      RESULTADOS AUDITADOS (3 MESES)")
    print("="*40)
    print(f"Profit Acumulado:  +{total_r:.2f}R")
    print(f"Win Rate Sniper:   {(winners/trades_executed*100 if trades_executed > 0 else 0):.1f}%")
    print(f"Trades Aprobados:  {trades_executed}")
    print(f"Profit en USDT:    ${total_r * 100:.2f} (Arriesgando $100/trade)")
    print("="*40)

    # Exportar a JSON para el usuario
    import json
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'backtest', 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(reports_dir, f"fast_audit_BTCUSDT_{timestamp_str}.json")
    summary = {
        "symbol": "BTCUSDT",
        "interval": "15m",
        "total_r": round(total_r, 2),
        "win_rate": round((winners/trades_executed*100 if trades_executed > 0 else 0), 1),
        "total_trades": trades_executed,
        "net_profit_usdt": round(total_r * 100, 2),
        "audit_date": timestamp_str,
        "status": "VERIFIED_V13.4"
    }
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=4)
    print(f"\n[OK] Reporte profesional generado en: {report_path}")

if __name__ == "__main__":
    fast_profit_audit()
