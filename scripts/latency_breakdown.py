
import asyncio
import time
import json
import logging
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, AsyncMock, patch

# Suprimir logs
logging.getLogger('engine').setLevel(logging.CRITICAL)

import sys
import os
sys.path.append(os.getcwd())

from engine.api.ws_manager import SymbolBroadcaster
from engine.router.processors import StreamProcessor
from engine.main_router import SlingshotRouter

async def run_latency_benchmark_v2():
    print("RUNNING: Iniciando AUDITORIA_DETALLADA_LATENCIA...")
    
    symbol = "BTCUSDT"
    interval = "15m"
    ticks_to_process = 500 # Suficiente para perfiles de performance
    
    with patch('engine.core.store.store') as mock_store, \
         patch('engine.ml.inference.ml_engine.predict_live') as mock_ml:
        
        mock_ml.return_value = {"direction": "ALCISTA", "probability": 65}
        mock_store.get_avg_volume.return_value = 100.0
        
        broadcaster = SymbolBroadcaster(symbol, interval)
        dummy_data = [{"timestamp": time.time(), "open": 50000, "high": 50100, "low": 49900, "close": 50050, "volume": 100} for _ in range(300)]
        broadcaster._live_buffer.extend([{"type": "candle", "data": d} for d in dummy_data])
        broadcaster._last_tactical = {"data": {"market_regime": "TRENDING_BULL"}}
        broadcaster._broadcast = AsyncMock()

        payloads = []
        base_time = int(time.time() * 1000)
        for i in range(ticks_to_process):
            tick_time = base_time + (i * 100)
            payloads.append({
                "data": {"E": tick_time, "k": {"t": tick_time, "o": "50000", "h": "50100", "l": "49900", "c": str(50050 + (i*0.1)), "v": "10", "x": False}}
            })

        lat_total = []
        lat_df_creation = []
        lat_fast_path_logic = []
        lat_router_process = []
        
        print(f"INFO: Midiendo {ticks_to_process} rafagas con desglose de micro-componentes...")
        
        for i in range(ticks_to_process):
            raw_payload = payloads[i]
            candle_payload = {"type": "candle", "data": {"timestamp": raw_payload["data"]["k"]["t"]/1000, "open": 50000, "high": 50100, "low": 49900, "close": float(raw_payload["data"]["k"]["c"]), "volume": 10}}
            
            t0 = time.perf_counter()
            
            # --- COMPONENTE 1: CREACION DE DATAFRAME ---
            t_df_0 = time.perf_counter()
            current_buffer = [i["data"] for i in broadcaster._live_buffer] + [candle_payload["data"]]
            df_live = pd.DataFrame(current_buffer)
            t_df_1 = time.perf_counter()
            lat_df_creation.append((t_df_1 - t_df_0) * 1000)
            
            # --- COMPONENTE 2: FAST PATH LOGIC (ML + RVOL) ---
            t_fp_0 = time.perf_counter()
            await StreamProcessor.process_fast_path(
                symbol=symbol, interval=interval,
                candle_payload=candle_payload, ws_data=raw_payload,
                context={"df_live": df_live, "avg_volume": 100.0}
            )
            t_fp_1 = time.perf_counter()
            lat_fast_path_logic.append((t_fp_1 - t_fp_0) * 1000)
            
            # --- COMPONENTE 3: ROUTER PROCESS (TACTICAL) ---
            t_rt_0 = time.perf_counter()
            await asyncio.to_thread(
                broadcaster._router.process_market_data, df_live, asset=symbol, interval=interval,
                macro_levels=[], htf_bias={}, heatmap={}, silent=True
            )
            t_rt_1 = time.perf_counter()
            lat_router_process.append((t_rt_1 - t_rt_0) * 1000)
            
            t1 = time.perf_counter()
            lat_total.append((t1 - t0) * 1000)

        results = {
            "p50_total_ms": round(np.percentile(lat_total, 50), 4),
            "p99_total_ms": round(np.percentile(lat_total, 99), 4),
            "p50_df_creation_ms": round(np.percentile(lat_df_creation, 50), 4),
            "p50_fast_path_logic_ms": round(np.percentile(lat_fast_path_logic, 50), 4),
            "p50_router_process_ms": round(np.percentile(lat_router_process, 50), 4),
        }
        
        with open("reporte_detallado_v6.json", "w") as f:
            json.dump(results, f, indent=2)

        print("\nREPORT: DESGLOSE DE LATENCIA v6.1")
        print(f"---------------------------------")
        print(f"DF Creation:  {results['p50_df_creation_ms']:.4f} ms")
        print(f"Fast Path:    {results['p50_fast_path_logic_ms']:.4f} ms")
        print(f"Router Tactical: {results['p50_router_process_ms']:.4f} ms")
        print(f"TOTAL (P50):  {results['p50_total_ms']:.4f} ms")
        print(f"---------------------------------")

if __name__ == "__main__":
    asyncio.run(run_latency_benchmark_v2())
