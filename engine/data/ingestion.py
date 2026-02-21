import asyncio
import pandas as pd
from typing import List
from pathlib import Path
from engine.data.fetcher import fetcher

# Configuraciones Base - Gestión Inteligente de Recursos
MAX_CONCURRENT_ASSETS = 10  # Límite duro para evitar bloqueos por rate limit y sobrecarga de CPU

# Modo Pruebas: Iniciamos solo con BTCUSDT para no gastar recursos aún
TARGET_SYMBOLS = ["BTCUSDT"]  # Más adelante se puede cambiar a ["BTCUSDT", "ETHUSDT", "SOLUSDT", ...]

async def download_and_save(symbol: str, interval: str = "15m", limit: int = 1500):
    """Descarga el historial de un activo y lo guarda en formato hiper-comprimido (.parquet)."""
    print(f"[{symbol}] Iniciando descarga de historial ({limit} velas de {interval})...")
    try:
        # Reutilizamos el fetch_binance actual de nuestro motor
        df = await fetcher.fetch_binance(symbol, interval=interval, limit=limit)
        
        if df is not None and not df.empty:
            # Asegurar directorio de datos
            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # Guardar The Data Lake file (Requiere pyarrow o fastparquet instalado)
            file_path = data_dir / f"{symbol.lower()}_{interval}.parquet"
            # df.to_parquet es muchísimo más rápido y ligero que df.to_csv
            df.to_parquet(file_path, engine="pyarrow", index=False)
            
            print(f"✅ [{symbol}] Guardado exitosamente: {len(df)} registros en {file_path.name}")
            return df
        else:
            print(f"⚠️ [{symbol}] No se obtuvieron datos o el DataFrame está vacío.")
    except Exception as e:
        print(f"❌ [{symbol}] Error en la ingesta: {e}")
        return None

async def ingest_market_data(symbols: List[str], interval: str = "15m", limit: int = 1500):
    """Procesa una lista de activos de forma concurrente, respetando el límite máximo."""
    # Control de seguridad: recorte por eficiencia
    if len(symbols) > MAX_CONCURRENT_ASSETS:
        print(f"⚠️ Límite de seguridad alcanzado. Recortando lista a {MAX_CONCURRENT_ASSETS} activos por eficiencia del sistema.")
        symbols = symbols[:MAX_CONCURRENT_ASSETS]
        
    print(f"🚀 Iniciando Data Lake Ingestion para {len(symbols)} activos concurrentes...")
    
    # Crear tareas asíncronas para descargar todo a la vez (Multiplexing)
    tasks = [download_and_save(sym, interval, limit) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("🏁 Ingesta masiva completada.")
    return results

if __name__ == "__main__":
    # Ejecución principal
    asyncio.run(ingest_market_data(TARGET_SYMBOLS))
