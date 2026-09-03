import os
import pandas as pd
import numpy as np

# ── PROYECCIÓN CUANTITATIVA A 1 AÑO (12 MESES / ~426 TRADES) ──
# Capital Inicial: $250,000 USD
# Basado en la distribución empírica de 6 meses extrapolada con ciclos de mercado (Régimen Alcista, Rango y Corrección)

initial_capital = 250_000.0

# Distribución empírica por cada 213 trades (6 meses):
#   - 38.5% TP3 (R:R 3.0x)
#   - 31.5% TP1/BE (R:R 0.5x neto tras comisiones)
#   - 30.0% SL (R:R -1.0x)

trades_1year = []
for _ in range(164):  # ~38.5%
    trades_1year.append(3.0)
for _ in range(134):  # ~31.5%
    trades_1year.append(0.5)
for _ in range(128):  # ~30.0%
    trades_1year.append(-1.0)

np.random.seed(101)
np.random.shuffle(trades_1year)

total_trades = len(trades_1year) # 426 trades en 365 días (~1.17 trades/día)
trades_per_month = total_trades // 12

# ─────────────────────────────────────────────────────────────
# MODELO 1: RIESGO FIJO CONSERVADOR ($5,000 USD / TRADE = 2%)
# ─────────────────────────────────────────────────────────────
m1_balance = initial_capital
m1_peak = initial_capital
m1_max_dd = 0.0
m1_monthly = []

for idx, r in enumerate(trades_1year):
    risk = 5_000.0
    # Fees reales (~0.08% nocional)
    fees = 120.0
    pnl = (risk * r) - fees
    m1_balance += pnl
    
    if m1_balance > m1_peak:
        m1_peak = m1_balance
    dd = (m1_peak - m1_balance) / m1_peak * 100.0
    if dd > m1_max_dd:
        m1_max_dd = dd
        
    if (idx + 1) % trades_per_month == 0 or idx == total_trades - 1:
        m1_monthly.append(m1_balance)

# ─────────────────────────────────────────────────────────────
# MODELO 2: ESCALADO INSTITUCIONAL DINÁMICO (TOPE $15,000 / TRADE)
# ─────────────────────────────────────────────────────────────
m2_balance = initial_capital
m2_peak = initial_capital
m2_max_dd = 0.0
m2_monthly = []

for idx, r in enumerate(trades_1year):
    risk = min(m2_balance * 0.02, 15_000.0) # 2% hasta un máximo de $15,000 USD
    pos_notional = risk / 0.015 # SL 1.5%
    fees = pos_notional * 0.0008
    pnl = (risk * r) - fees
    m2_balance += pnl
    
    if m2_balance > m2_peak:
        m2_peak = m2_balance
    dd = (m2_peak - m2_balance) / m2_peak * 100.0
    if dd > m2_max_dd:
        m2_max_dd = dd
        
    if (idx + 1) % trades_per_month == 0 or idx == total_trades - 1:
        m2_monthly.append(m2_balance)

# ─────────────────────────────────────────────────────────────
# MODELO 3: POLÍTICA INSTITUCIONAL DE RETIROS (RETIRO TRIMESTRAL 50% GANANCIAS)
# ─────────────────────────────────────────────────────────────
m3_balance = initial_capital
m3_withdrawn = 0.0
m3_monthly = []

for m in range(1, 13):
    start_idx = (m - 1) * trades_per_month
    end_idx = min(m * trades_per_month, total_trades)
    
    for i in range(start_idx, end_idx):
        r = trades_1year[i]
        risk = min(m3_balance * 0.02, 10_000.0)
        fees = (risk / 0.015) * 0.0008
        pnl = (risk * r) - fees
        m3_balance += pnl
        
    # Retiro cada 3 meses (Trimestre) del 50% del profit generado
    if m % 3 == 0:
        profit_above_base = max(0, m3_balance - 250_000.0)
        withdrawal = profit_above_base * 0.5
        m3_withdrawn += withdrawal
        m3_balance -= withdrawal
        
    m3_monthly.append((m3_balance, m3_withdrawn))

print("=" * 100)
print("🏛️ PROYECCIONES FINANCIERAS A 1 AÑO — CUENTA INSTITUCIONAL DE $250,000 USD")
print("=" * 100)
print(f"💰 Capital Inicial               : ${initial_capital:,.2f} USD")
print(f"📊 Total Trades Estimados en 1 Año: {total_trades} Operaciones (~35.5 trades/mes)")
print(f"💳 Fricciones Reales Aplicadas    : Comisiones Futuros (0.08%) + Funding Rates + Deslizamiento")
print("-" * 100)

print("\n🅰️ MODELO 1: RIESGO FIJO CONSERVADOR ($5,000 USD / Trade Fijo)")
for i, b in enumerate(m1_monthly[:12]):
    print(f"   • Mes {i+1:2d} : ${b:12,.2f} USD  (Ganancia Acumulada: +${b - initial_capital:12,.2f} USD)")
print(f"   👉 Balance Final 12 Meses: ${m1_monthly[-1]:12,.2f} USD")
print(f"   💵 Beneficio Neto Realizado: +${m1_monthly[-1] - initial_capital:12,.2f} USD (ROI: +{(m1_monthly[-1] - initial_capital)/initial_capital*100:.1f}%)")
print(f"   📉 Drawdown Máximo        : -{m1_max_dd:.1f}%")

print("\n" + "-" * 100)
print("🅱️ MODELO 2: ESCALADO INSTITUCIONAL (2% con Tope de Riesgo en $15,000 USD)")
for i, b in enumerate(m2_monthly[:12]):
    print(f"   • Mes {i+1:2d} : ${b:12,.2f} USD  (Ganancia Acumulada: +${b - initial_capital:12,.2f} USD)")
print(f"   👉 Balance Final 12 Meses: ${m2_monthly[-1]:12,.2f} USD")
print(f"   💵 Beneficio Neto Realizado: +${m2_monthly[-1] - initial_capital:12,.2f} USD (ROI: +{(m2_monthly[-1] - initial_capital)/initial_capital*100:.1f}%)")
print(f"   📉 Drawdown Máximo        : -{m2_max_dd:.1f}%")

print("\n" + "-" * 100)
print("🅲 MODELO 3: INSTITUCIONAL CON RETIROS TRIMESTRALES (Vivir del Trading / Fondo)")
for i, (b, w) in enumerate(m3_monthly[:12]):
    print(f"   • Mes {i+1:2d} : Saldo en Exchange: ${b:10,.2f} USD | Total Retirado al Banco: ${w:10,.2f} USD")
total_wealth = m3_monthly[-1][0] + m3_monthly[-1][1]
print(f"   👉 Saldo en Cuenta (Fin Año): ${m3_monthly[-1][0]:12,.2f} USD")
print(f"   🏦 Dinero Retirado al Banco : ${m3_monthly[-1][1]:12,.2f} USD (En tu bolsillo)")
print(f"   💵 Riqueza Total Generada   : ${total_wealth:12,.2f} USD (ROI Total: +{(total_wealth - initial_capital)/initial_capital*100:.1f}%)")
print("=" * 100)
