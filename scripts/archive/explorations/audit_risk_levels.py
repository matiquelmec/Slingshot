import os
import pandas as pd
import numpy as np

# Datos empíricos de trades de los últimos 6 meses (213 trades, WR 38.5%, RR medio 1:2.5)
# Generamos la secuencia real de resultados simulada
trades = []
# 82 trades ganadores (RR 2.5)
for _ in range(82):
    trades.append(2.5)
# 64 trades perdedores (-1.0)
for _ in range(64):
    trades.append(-1.0)
# 67 trades neutros/breakeven (0.0)
for _ in range(67):
    trades.append(0.0)

# Semilla fija para reproducibilidad
np.random.seed(42)
np.random.shuffle(trades)

initial_capital = 1000.0

print("=" * 80)
print("📊 SIMULACIÓN DE RIESGO POR OPERACIÓN (Capital Inicial: $1,000 USD / 6 Meses)")
print("=" * 80)

for risk_pct in [1.0, 2.0, 3.0, 5.0, 8.0, 10.0]:
    capital = initial_capital
    peak = initial_capital
    max_dd_pct = 0.0
    
    for r in trades:
        risk_amount = capital * (risk_pct / 100.0)
        pnl = risk_amount * r
        capital += pnl
        
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak * 100.0
        if dd > max_dd_pct:
            max_dd_pct = dd

    net_profit = capital - initial_capital
    roi_pct = (net_profit / initial_capital) * 100.0
    print(f"🚀 Riesgo {risk_pct:4.1f}% por trade -> Capital Final: ${capital:10,.2f} | Ganancia: ${net_profit:9,.2f} | ROI: {roi_pct:6.1f}% | Max Drawdown: {max_dd_pct:4.1f}%")

print("=" * 80)
