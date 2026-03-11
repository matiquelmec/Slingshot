import pandas as pd
from engine.main_router import SlingshotRouter
from pathlib import Path
import os
import sys

# Asegurar que el motor sea importable (usando el directorio actual)
sys.path.append(os.getcwd())

def verify():
    print("🧪 [TEST] Verificando motor en RAÍZ con lógica flexibilizada...")
    
    file_path = Path("data/btcusdt_15m.parquet")
    if not file_path.exists():
        # Intentar con el archivo de 1 año si el pequeño no está
        file_path = Path("data/btcusdt_15m_1YEAR.parquet")
        
    if not file_path.exists():
        print("❌ No se encontró ningún archivo de datos en /data.")
        return

    print(f"📊 Cargando: {file_path}")
    df = pd.read_parquet(file_path)
    router = SlingshotRouter()
    
    # Procesamos los datos
    output = router.process_market_data(df, asset="BTCUSDT", interval="15m")
    
    signals = output.get("signals", [])
    regime = output.get("market_regime", "UNKNOWN")
    
    print(f"\n📊 RESUMEN:")
    print(f"   Régimen Actual: {regime}")
    print(f"   Señales Vivas detectadas: {len(signals)}")
    
    if signals:
        print("\n🚨 SEÑALES ENCONTRADAS (LISTAS PARA FRONTEND):")
        for i, s in enumerate(signals[-5:]): # Ver las últimas 5
            print(f"   {i+1}. {s.get('type')} @ ${s.get('price'):,.2f}")
            print(f"      Trigger: {s.get('trigger')}")
            print(f"      Confluence Score: {s.get('confluence', {}).get('total_score', 0)}%")
            print("-" * 40)
    else:
        print("\n⚠️  No hay señales 'vivas' en el tick actual.")
        print("🔎 Buscando oportunidades históricas en las últimas 48h...")
        
        found_any = False
        # Escaneamos hacia atrás para ver si el motor genera "algo"
        for i in range(max(0, len(df)-200), len(df)):
            win = df.iloc[:i+1]
            out = router.process_market_data(win)
            if out.get("signals"):
                s = out["signals"][-1]
                print(f"🎯 [{i}] OPORTUNIDAD: {s['type']} @ {s['price']}")
                found_any = True
                break
        
        if not found_any:
            print("❌ El motor sigue mudo. Posible sobre-filtrado en indicadores base.")

if __name__ == "__main__":
    verify()
