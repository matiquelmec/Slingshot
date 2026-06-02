import sys
import os
import glob
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from engine.backtest.replay_engine import EventDrivenReplayEngine
import asyncio

# Bypassear el validador de IA local en Ollama para acelerar el backtest offline
from engine.core.validator import validator_agent
async def mock_validate(signal):
    return {
        "approved": True, 
        "ai_reasoning": "MOCK: Aprobación automática en Backtest Offline.",
        "confidence": 1.0,
        "verdict": "VEST"
    }
validator_agent.validate = mock_validate

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
# Buscamos archivos de 15m de 90 dias
files = glob.glob(os.path.join(DATA_DIR, "*_15m_90d.parquet"))

if not files:
    print(f"No se encontraron archivos 15m en {DATA_DIR}. Abortando.")
    sys.exit(1)

print(f"Encontrados {len(files)} activos para el portafolio 15m.")

import subprocess
import json

def run_backtest_for_file(f):
    asset = os.path.basename(f).split("_")[0]
    print(f" Lanzando backtest para {asset}...")
    
    # Ejecutamos el replay_engine como un subproceso
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "replay_engine.py"),
        "--data_path", f,
        "--symbol", asset,
        "--interval", "15m"
    ]
    
    # Capturamos el output para que no se mezcle
    result = subprocess.run(cmd, capture_output=True, text=True)
    return asset, result.stdout, result.stderr

def main():
    import concurrent.futures
    print(f"Encontrados {len(files)} activos para el portafolio 15m.")
    print("Iniciando simulación en paralelo (esto tomará unos minutos)...")
    
    all_trades = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(files)) as executor:
        futures = {executor.submit(run_backtest_for_file, f): f for f in sorted(files)}
        for future in concurrent.futures.as_completed(futures):
            asset, stdout, stderr = future.result()
            print(f"\n========================================")
            print(f" RESULTADOS COMPILADOS: {asset} ")
            print(f"========================================")
            print(stdout)
            if stderr:
                print(f"[{asset} ERRORS]\n", stderr)
            
            # Buscar el reporte JSON generado más reciente para este asset
            reports_dir = os.path.join(os.path.dirname(__file__), "reports")
            report_pattern = os.path.join(reports_dir, f"backtest_{asset}_*.json")
            report_files = glob.glob(report_pattern)
            if report_files:
                latest_report = max(report_files, key=os.path.getmtime)
                try:
                    with open(latest_report, "r") as rf:
                        summary = json.load(rf)
                        trades = summary.get("trade_log", [])
                        for t in trades:
                            t["asset"] = asset
                        all_trades.extend(trades)
                except Exception as e:
                    print(f"Error al leer reporte para {asset}: {e}")
            else:
                print(f"⚠️ No se encontró reporte JSON para {asset} en {reports_dir}")
                
    print("\n" + "#"*60)
    print(" RESULTADO FINAL DEL PORTAFOLIO SLINGSHOT APEX (15m) ")
    print("#"*60)
    print(f"Total Trades Tomados: {len(all_trades)}")

    if all_trades:
        winners = [t for t in all_trades if float(t['r_realized']) > 0]
        losers = [t for t in all_trades if float(t['r_realized']) < 0]
        breakevens = [t for t in all_trades if float(t['r_realized']) == 0 and t['status'] == 'CLOSED']
        
        total_r = sum(float(t['r_realized']) for t in all_trades)
        win_rate = (len(winners) / len(all_trades)) * 100
        
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Ganadores: {len(winners)} | Perdedores: {len(losers)} | BE: {len(breakevens)}")
        print(f"Retorno Acumulado: {total_r:.2f}R")
        
        print("\nDESGLOSE POR ACTIVO:")
        df_trades = pd.DataFrame(all_trades)
        if not df_trades.empty:
            summary = df_trades.groupby('asset')['r_realized'].agg(['count', 'sum'])
            summary.columns = ['Trades', 'Total R']
            print(summary)
            
            # Detalle de tasa de acierto por activo
            print("\nWIN RATE DETALLADO POR ACTIVO:")
            for asset_name, group in df_trades.groupby('asset'):
                asset_winners = [t for t in group.to_dict('records') if float(t['r_realized']) > 0]
                asset_wr = (len(asset_winners) / len(group)) * 100
                print(f" - {asset_name}: {asset_wr:.1f}% WR ({len(group)} trades)")

    print("#"*60)

if __name__ == "__main__":
    main()
