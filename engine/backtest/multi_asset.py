import sys
import os
import glob
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from engine.backtest.replay_engine import EventDrivenReplayEngine
import asyncio

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
from engine.api.config import settings

# Buscamos archivos de 4h que acabamos de bajar
all_files = glob.glob(os.path.join(DATA_DIR, "*_4h_90d.parquet"))
vip_assets = [a.replace('/', '').upper() for a in settings.MASTER_WATCHLIST]
files = [f for f in all_files if os.path.basename(f).split("_")[0].upper() in vip_assets]

if not files:
    print(f"No se encontraron archivos 4h para tus activos VIP en {DATA_DIR}. Abortando.")
    sys.exit(1)

print(f"Encontrados {len(files)} activos VIP para el portafolio 4h.")

all_trades = []

for f in files:
    asset = os.path.basename(f).split("_")[0]
    print(f"\n" + "="*40)
    print(f" ANALIZANDO ACTIVO: {asset} ")
    print("="*40)
    
    engine = EventDrivenReplayEngine(data_path=f, interval="4h", symbol=asset)
    asyncio.run(engine.run())
    
    # Marcamos el asset en cada trade para el resumen
    for t in engine.closed_trades + engine.active_trades:
        t['asset'] = asset
        all_trades.append(t)

print("\n" + "#"*60)
print(" RESULTADO FINAL DEL PORTAFOLIO SLINGSHOT APEX (H4) ")
print("#"*60)
print(f"Total Trades Tomados: {len(all_trades)}")

if all_trades:
    winners = [t for t in all_trades if t['r_realized'] > 0]
    losers = [t for t in all_trades if t['r_realized'] < 0]
    breakevens = [t for t in all_trades if t['r_realized'] == 0 and t['status'] == 'CLOSED']
    
    total_r = sum(t['r_realized'] for t in all_trades)
    win_rate = (len(winners) / len(all_trades)) * 100
    
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Ganadores: {len(winners)} | Perdedores: {len(losers)} | BE: {len(breakevens)}")
    print(f"Retorno Acumulado: {total_r:.2f}R")
    
    print("\nDESGLOSE POR ACTIVO:")
    df_trades = pd.DataFrame(all_trades)
    if not df_trades.empty:
        summary = df_trades.groupby('asset')['r_realized'].sum()
        print(summary)

print("#"*60)
