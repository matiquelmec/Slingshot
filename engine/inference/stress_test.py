import time
import random
from engine.inference.volume_pattern import analyze_volume_batch

def run_stress_test():
    print("🚀 Iniciando Benchmark Slingshot v5.5.2 (Vectorizado)...")
    
    # Simular 500 pares de criptomonedas
    mock_data = []
    for i in range(500):
        mock_data.append({
            'close': random.uniform(10.0, 60000.0),
            'volume': random.uniform(100.0, 5000.0),
            'rvol': random.uniform(0.5, 8.0)
        })
        
    start_time = time.perf_counter()
    scores = analyze_volume_batch(mock_data)
    end_time = time.perf_counter()
    
    latency_ms = (end_time - start_time) * 1000.0
    print(f"📊 Tiempo total procesando 500 pares: {latency_ms:.2f} ms")
    print(f"⚡ Latencia por par: {latency_ms/500:.4f} ms")
    
    if latency_ms < 60:
        print("✅ RUPTURA DE BARRERA LOGRADA (Grado Institucional)")
    else:
        print("⚠️ Advertencia: Latencia subóptima. Verifique compilación de la Forja.")

if __name__ == "__main__":
    run_stress_test()
