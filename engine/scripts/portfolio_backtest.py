
import os
import sys
from pathlib import Path

# Añadir el root del proyecto al path de Python para imports absolutos
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

import pandas as pd
from engine.scripts.backtest_engine import SlingshotBacktest
from engine.core.logger import logger

def run_portfolio():
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "tmp" / "data"
    
    # Lista de activos a auditar
    assets = [
        {"symbol": "BTCUSDT", "file": "btcusdt_15m_1YEAR.parquet"},
        {"symbol": "ETHUSDT", "file": "ethusdt_15m.parquet"},
        {"symbol": "SOLUSDT", "file": "solusdt_15m.parquet"}
    ]
    
    portfolio_results = []
    
    print("\n" + "!"*60)
    print("   INICIANDO AUDITORIA DE PORTAFOLIO: SNIPER FLOW v6.2.1   ")
    print("!"*60 + "\n")
    
    for asset in assets:
        path = data_dir / asset["file"]
        if not path.exists():
            # Intentar sin el sufijo 1YEAR si no existe
            alt_path = data_dir / f"{asset['symbol'].lower()}_15m.parquet"
            if alt_path.exists():
                path = alt_path
            else:
                print(f"WARNING: Saltando {asset['symbol']}: No se encontro la data en {path}")
                continue
        
        print(f"\nAUDIT: Analizando {asset['symbol']}...")
        backtest = SlingshotBacktest(str(path))
        # Ejecutamos 1000 velas para obtener resultados rápidos y precisos
        backtest.run(max_candles=1000)
        
        portfolio_results.append({
            "Symbol": asset["symbol"],
            "Trades": backtest.wins + backtest.losses,
            "Winrate": (backtest.wins / (backtest.wins + backtest.losses) * 100) if (backtest.wins + backtest.losses) > 0 else 0,
            "Profit": backtest.balance - 1000.0
        })

    # Resumen Final
    print("\n" + "="*60)
    print("   RESUMEN FINAL DE LA AUDITORIA DE PORTAFOLIO   ")
    print("="*60)
    df_results = pd.DataFrame(portfolio_results)
    print(df_results.to_string(index=False))
    print("="*60)
    total_profit = df_results["Profit"].sum()
    print(f" GANANCIA TOTAL DEL PORTAFOLIO: ${total_profit:.2f}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_portfolio()
