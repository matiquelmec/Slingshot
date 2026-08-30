"""
=============================================================================
SLINGSHOT v23.3 APEX — CLI OFICIAL DE BACKTESTING INSTITUCIONAL (SSoT)
=============================================================================
Punto Único de Verdad (Single Source of Truth) para backtesting cuantitativo.
Ejecuta simulaciones multi-activo con todas las reglas de producción:
• Smart Money Concepts (Order Blocks, FVGs, BOS/CHoCH)
• Entrada Óptima de Retroceso (OTE 61.8% / 70.5% Fibonacci)
• Confluence Manager (Score >= 60) y Mapa Macro de Bitcoin
• Fast Breakeven Adaptativo (+1.0R Alts / +1.2R Megas) con Fee Absorber (+0.08%)
• Salidas Asimétricas (TP1 60%, TP2 20%, TP3 10%, Runner 10%)
=============================================================================
Uso:
  python scripts/run_institutional_backtest.py --portfolio
  python scripts/run_institutional_backtest.py --symbol NEARUSDT --timeframe 15m
  python scripts/run_institutional_backtest.py --symbol BTCUSDT --timeframe 1h
=============================================================================
"""
import os
import sys
import argparse
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR
from engine.api.config import settings

def main():
    parser = argparse.ArgumentParser(
        description="Slingshot v23.3 Apex — Motor Oficial de Backtesting Institucional"
    )
    parser.add_argument(
        "--portfolio",
        action="store_true",
        help="Ejecuta la auditoría completa de la cartera de 14 activos VIP en 180 días"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Símbolo específico a evaluar (ej: NEARUSDT, SUIUSDT, BTCUSDT)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="15m",
        choices=["15m", "1h", "4h", "1d"],
        help="Marco temporal de evaluación (default: 15m)"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Puntuación mínima de confluencia para aprobar entradas (default: 60)"
    )

    args = parser.parse_args()

    engine = UnifiedBacktestEngine(min_confluence_score=args.min_score)

    if args.portfolio or (not args.symbol):
        print("\n🚀 Ejecutando Auditoría Oficial de Cartera Completa (180 Días)...")
        summary = engine.run_adaptive_portfolio_audit()
        return

    # Evaluación de un solo activo
    sym = args.symbol.upper().replace('/', '')
    if not sym.endswith("USDT"):
        sym += "USDT"

    print(f"\n🔍 Evaluando {sym} en temporalidad {args.timeframe} (Confluencia >= {args.min_score})...")
    
    btc_map = engine._load_btc_macro_map() if hasattr(engine, '_load_btc_macro_map') else {}
    
    # Determinar si el activo tiene método dedicado o personalizado
    trades = engine.run_single_asset(sym, interval=args.timeframe, btc_map=btc_map)

    if not trades:
        print(f"❌ No se generaron operaciones para {sym} en {args.timeframe}.")
        return

    tdf = pd.DataFrame(trades)
    total_trades = len(tdf)
    wins = tdf[tdf['outcome_r'] > 0]
    bes = tdf[tdf['outcome_r'] == 0]
    losses = tdf[tdf['outcome_r'] < 0]

    win_rate = (len(wins) / total_trades) * 100
    be_rate = (len(bes) / total_trades) * 100
    loss_rate = (len(losses) / total_trades) * 100
    total_r = tdf['outcome_r'].sum()

    gross_w = wins['outcome_r'].sum() if len(wins) > 0 else 0.0
    gross_l = abs(losses['outcome_r'].sum()) if len(losses) > 0 else 1.0
    profit_factor = (gross_w / gross_l) if gross_l > 0 else 99.0

    print("=" * 85)
    print(f"📊 INFORME INSTITUCIONAL: {sym} ({args.timeframe.upper()})")
    print("=" * 85)
    print(f" • Total Operaciones:         {total_trades}")
    print(f" • Ganadoras (TP1/TP2/TP3):   {len(wins)} ({win_rate:.1f}%)")
    print(f" • Breakevens Salvados ($0):  {len(bes)} ({be_rate:.1f}%)")
    print(f" • Pérdidas en Stop Loss:     {len(losses)} ({loss_rate:.1f}%)")
    print(f" • Tasa de Efectividad:       {win_rate + be_rate:.1f}% (Capital Intacto o Ganancia)")
    print(f" • RETORNO NETO TOTAL:        {total_r:+.2f} R")
    print(f" • PROFIT FACTOR:             {profit_factor:.2f}")
    print(f" • Ganancia Neta ($1,000 Usd):{total_r * 10.0:+.2f} USDT (arriesgando 1% / $10)")
    print("=" * 85)

if __name__ == "__main__":
    main()
