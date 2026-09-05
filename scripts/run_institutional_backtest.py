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
• Métricas Institucionales (Sharpe, Sortino, Calmar, Max Drawdown, Profit Factor)
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
    parser.add_argument(
        "--mode",
        type=str,
        default="chronological",
        choices=["chronological", "isolated"],
        help="Modo de ejecución: 'chronological' (Event-Driven SSoT con límites de slots y macro) o 'isolated' (R plano por activo)"
    )
    parser.add_argument(
        "--max-slots",
        type=int,
        default=2,
        help="Máximo de posiciones LONG simultáneas con riesgo flotante (SOP-30, default: 2)"
    )
    parser.add_argument(
        "--compounding-usd",
        type=float,
        default=1000.0,
        help="Capital inicial para simulación de interés compuesto al 2.5% Bitunix (default: $1,000 USD)"
    )
    parser.add_argument(
        "--enable-alpha-cycle",
        action="store_true",
        help="Activa la modulación de riesgo por días de la semana (SOP-46: Martes/Miércoles 1.20x, Jueves/Viernes 0.80x)"
    )
    parser.add_argument(
        "--enable-trinity-boost",
        action="store_true",
        help="Activa el multiplicador Kelly 1.20x de convicción en la Trinidad del Alfa: BNB, SOL, FET (SOP-47)"
    )
    parser.add_argument(
        "--enable-elastic-runner",
        action="store_true",
        help="Activa el Runner elástico dinámico a 5.0R con KER >= 0.50 y Ratchet Lock (SOP-48)"
    )
    parser.add_argument(
        "--enable-golden-hours",
        action="store_true",
        help="Activa el multiplicador 1.15x en las ventanas horarias 09:00 y 11:00 UTC (SOP-49)"
    )
    parser.add_argument(
        "--all-advanced",
        action="store_true",
        help="Activa simultáneamente todas las innovaciones cuantitativas avanzadas (SOP-46 a SOP-49)"
    )

    args = parser.parse_args()

    alpha_cycle = args.enable_alpha_cycle or args.all_advanced
    trinity_boost = args.enable_trinity_boost or args.all_advanced
    elastic_runner = args.enable_elastic_runner or args.all_advanced
    golden_hours = args.enable_golden_hours or args.all_advanced

    engine = UnifiedBacktestEngine(min_confluence_score=args.min_score)

    if args.portfolio or (not args.symbol):
        if args.mode == "chronological":
            print("\n🚀 Ejecutando Auditoría Oficial Cronológica Unificada (Event-Driven SSoT)...")
            summary = engine.run_chronological_portfolio_replay(
                max_concurrent_longs=args.max_slots,
                compounding_initial_usd=args.compounding_usd,
                enable_alpha_cycle=alpha_cycle,
                enable_trinity_boost=trinity_boost,
                enable_elastic_runner=elastic_runner,
                enable_golden_hours=golden_hours
            )
        else:
            print("\n🚀 Ejecutando Auditoría Oficial de Cartera Aislada por Activo (Legacy SSoT)...")
            summary = engine.run_adaptive_portfolio_audit()
        return

    # Evaluación de un solo activo
    sym = args.symbol.upper().replace('/', '')
    if not sym.endswith("USDT"):
        sym += "USDT"

    print(f"\n🔍 Evaluando {sym} en temporalidad {args.timeframe} (Confluencia >= {args.min_score})...")
    
    btc_map = engine._load_btc_macro_map() if hasattr(engine, '_load_btc_macro_map') else {}
    
    trades = engine.run_single_asset(sym, interval=args.timeframe, btc_map=btc_map, enable_elastic_runner=elastic_runner)

    if not trades:
        print(f"❌ No se generaron operaciones para {sym} en {args.timeframe}.")
        return

    metrics = UnifiedBacktestEngine.calculate_performance_metrics(trades, initial_balance=10_000.0, risk_pct=0.01)

    print("=" * 85)
    print(f"📊 INFORME INSTITUCIONAL SSoT: {sym} ({args.timeframe.upper()})")
    print("=" * 85)
    print(f" • Total Operaciones:         {metrics['total_trades']}")
    print(f" • Win Rate Real (TP1/2/3):   {metrics['win_rate']:.1f}%")
    print(f" • Breakevens Salvados ($0):  {metrics['breakeven_rate']:.1f}%")
    print(f" • Retorno Neto Total:        {metrics['total_r']:>+8.2f} R")
    print(f" • Profit Factor:             {metrics['profit_factor']:.2f}")
    print(f" • Esperanza Matemática:      {metrics['expectancy_r']:>+7.3f} R / trade")
    print(f" • Max Drawdown Histórico:    -{metrics['max_drawdown_pct']:.2f}%")
    print(f" • Sharpe Ratio Anualizado:   {metrics['sharpe_ratio']:.2f}")
    print(f" • Sortino Ratio (Downside):  {metrics['sortino_ratio']:.2f}")
    print(f" • Calmar Ratio (Ret/DD):     {metrics['calmar_ratio']:.2f}")
    print(f" • Beneficio Neto USD ($10k): {metrics['net_profit_usd']:>+11,.2f} USD")
    print("-" * 85)
    print(" • Desglose de Salidas:")
    for reason, count in metrics.get("exit_breakdown", {}).items():
        print(f"     - {reason:<25}: {count:>3} trades")
    print("=" * 85)

if __name__ == "__main__":
    main()
