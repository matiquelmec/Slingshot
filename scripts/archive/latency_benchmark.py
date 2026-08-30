
import asyncio
import time
import json
import logging
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, AsyncMock, patch

# Suprimir todos los logs para no contaminar el benchmark
logging.getLogger('engine').setLevel(logging.CRITICAL)
logging.getLogger('slingshot').setLevel(logging.CRITICAL)

# Inyeccion de dependencias para aislamiento total
import sys
import os

# Asegurar que el path del proyecto este disponible
sys.path.append(os.getcwd())

from engine.api.ws_manager import SymbolBroadcaster
from engine.router.processors import StreamProcessor
from engine.main_router import SlingshotRouter

async def run_latency_benchmark():
    print("RUNNING: Iniciando VALIDACION_LATENCIA_DISPATCHER (Optimizado)...")
    
    # 1. Configuracion del Entorno de Pruebas
    symbol = "BTCUSDT"
    interval = "15m"
    ticks_to_process = 2000 # Reducido para velocidad, mantenemos significancia estadistica
    
    # Mocking de dependencias externas para evitar I/O y red
    with patch('engine.core.store.store') as mock_store, \
         patch('engine.api.registry.registry') as mock_registry, \
         patch('engine.notifications.telegram.send_signal_async') as mock_tg, \
         patch('engine.ml.inference.ml_engine.predict_live') as mock_ml, \
         patch('engine.api.advisor.generate_tactical_advice') as mock_advisor:
        
        # Mocks rapidos
        mock_ml.return_value = {"direction": "ALCISTA", "probability": 65}
        mock_store.get_avg_volume.return_value = 100.0
        
        # Instanciar Broadcaster
        broadcaster = SymbolBroadcaster(symbol, interval)
        
        # Poblar buffer inicial (300 velas ficticias)
        dummy_data = []
        for i in range(300):
            dummy_data.append({
                "timestamp": time.time() - (300 - i) * 60,
                "open": 50000.0 + i,
                "high": 50100.0 + i,
                "low": 49900.0 + i,
                "close": 50050.0 + i,
                "volume": 100.0
            })
        
        # Inicializar estado interno
        broadcaster._live_buffer.extend([{"type": "candle", "data": d} for d in dummy_data])
        broadcaster._last_tactical = {"data": {"market_regime": "TRENDING_BULL"}}
        
        # Bypass del broadcast real
        broadcaster._broadcast = AsyncMock()

        # Generar payloads en memoria
        payloads = []
        base_time = int(time.time() * 1000)
        for i in range(ticks_to_process):
            tick_time = base_time + (i * 100)
            payloads.append({
                "data": {
                    "E": tick_time,
                    "k": {
                        "t": tick_time,
                        "o": "50000.0",
                        "h": "50100.0",
                        "l": "49900.0",
                        "c": str(50050.0 + (i * 0.1)),
                        "v": "10.0",
                        "x": False
                    }
                }
            })

        latencies = []
        print(f"INFO: Procesando {ticks_to_process} rafagas...")
        
        # 2. Ejecucion del Benchmark
        for i in range(ticks_to_process):
            raw_payload = payloads[i]
            candle_payload = {
                "type": "candle",
                "data": {
                    "timestamp": raw_payload["data"]["k"]["t"] / 1000,
                    "open": float(raw_payload["data"]["k"]["o"]),
                    "high": float(raw_payload["data"]["k"]["h"]),
                    "low": float(raw_payload["data"]["k"]["l"]),
                    "close": float(raw_payload["data"]["k"]["c"]),
                    "volume": float(raw_payload["data"]["k"]["v"]),
                }
            }
            
            broadcaster._last_pulse_ts = 0 
            
            start_time = time.perf_counter()
            await broadcaster._execute_fast_path(candle_payload, raw_payload)
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000)

        # 3. Auditoria
        latencies_np = np.array(latencies)
        avg_lat = np.mean(latencies_np)
        max_lat = np.max(latencies_np)
        min_lat = np.min(latencies_np)
        p50 = np.percentile(latencies_np, 50)
        p90 = np.percentile(latencies_np, 90)
        p99 = np.percentile(latencies_np, 99)

        report = {
            "ticks_procesados": ticks_to_process,
            "latencia_promedio_ms": round(float(avg_lat), 4),
            "latencia_maxima_ms": round(float(max_lat), 4),
            "latencia_minima_ms": round(float(min_lat), 4),
            "percentil_50_ms": round(float(p50), 4),
            "percentil_90_ms": round(float(p90), 4),
            "percentil_99_ms": round(float(p99), 4),
            "cuellos_de_botella_detectados": []
        }
        
        if p99 > 1.0:
            report["cuellos_de_botella_detectados"].append("P99 excede el umbral de 1ms.")
        if avg_lat > 0.5:
            report["cuellos_de_botella_detectados"].append("Latencia promedio elevada (>0.5ms).")

        with open("reporte_latencia_v6.json", "w") as f:
            json.dump(report, f, indent=2)

        print("\nREPORT: REPORTE DE LATENCIA v6.1")
        print(f"--------------------------")
        print(f"Promedio: {avg_lat:.4f} ms")
        print(f"P90:      {p90:.4f} ms")
        print(f"P99:      {p99:.4f} ms")
        print(f"Maxima:   {max_lat:.4f} ms")
        print(f"--------------------------")
        print("SUCCESS: Resultado guardado en 'reporte_latencia_v6.json'")

if __name__ == "__main__":
    asyncio.run(run_latency_benchmark())
