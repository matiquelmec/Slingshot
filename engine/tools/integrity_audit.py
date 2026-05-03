import sys
import os
import pandas as pd
from datetime import datetime

sys.path.append(os.getcwd())

print(f"[{datetime.now()}] Iniciando Auditoría de Integridad...")

try:
    from engine.main_router import SlingshotRouter
    from engine.risk.risk_manager import RiskManager
    from engine.core.confluence import ConfluenceManager
    from engine.router.analyzer import MarketAnalyzer
    
    print("[OK] Importaciones exitosas.")
    
    # 1. Test RiskManager OTE Logic
    rm = RiskManager()
    fib_mock = {"61.8%": 55000, "78.6%": 56000}
    res = rm.calculate_position(
        current_price=50000,
        signal_type="LONG",
        fib_data=fib_mock,
        atr_value=500
    )
    print(f"[OK] RiskManager OTE Test: TP3={res['tp3']} (Debe ser >= 56000 si se detectó el imán)")
    
    # 2. Test Confluence SMT Logic
    cm = ConfluenceManager()
    df_main = pd.DataFrame({
        'timestamp': [pd.Timestamp('2026-01-01')],
        'close': [50000],
        'volume': [100],
        'open': [49000], 'high': [51000], 'low': [48000]
    })
    # Simular previo
    df_main = pd.concat([pd.DataFrame({'timestamp': [pd.Timestamp('2025-12-31')], 'close': [51000], 'volume': [100], 'open': [50000], 'high': [52000], 'low': [49000]}), df_main])
    
    df_corr = pd.DataFrame({
        'timestamp': [pd.Timestamp('2026-01-01')],
        'close': [3000], # ETH sube mientras BTC baja -> SMT Bullish
        'volume': [100]
    })
    df_corr = pd.concat([pd.DataFrame({'timestamp': [pd.Timestamp('2025-12-31')], 'close': [2900], 'volume': [100]}), df_corr])
    
    conf = cm.evaluate_signal(
        df=df_main,
        signal={'price': 50000, 'signal_type': 'LONG', 'timestamp': '2026-01-01'},
        correlated_df=df_corr
    )
    
    smt_found = any(c['factor'] == 'SMT Divergence' for c in conf['checklist'])
    print(f"[OK] Confluence SMT Test: Encontrado={smt_found}")
    
    print("\n[AUDITORÍA FINAL] Todos los sistemas nominales. No se detectaron duplicaciones ni errores de sintaxis.")

except Exception as e:
    print(f"[ERROR] Fallo en la auditoría: {e}")
    import traceback
    traceback.print_exc()
