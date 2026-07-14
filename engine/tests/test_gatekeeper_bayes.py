"""
Prueba unitaria del BayesianInferenceEngine y de-duplicación en gatekeeper.py
"""
import sys, asyncio, pandas as pd
sys.path.insert(0, '.')
from engine.router.gatekeeper import SignalGatekeeper, BayesianInferenceEngine
from engine.risk.risk_manager import RiskManager
from engine.core.memory import blackbox

async def test_bayes():
    rm = RiskManager()
    gk = SignalGatekeeper(rm)
    
    # ── 1. Simular historial en BlackBox para activar el motor Bayesiano ──
    blackbox.memory.clear()
    
    # Inyectamos 10 registros históricos donde el 70% de las contratendencias en SOL resultaron exitosas (TP)
    for i in range(7):
        blackbox.memory.append({
            "asset": "SOLUSDT",
            "signal_type": "LONG",
            "result": "TAKE_PROFIT",
            "fingerprint": {"regime": "MARKDOWN", "is_in_ote": True}
        })
    for i in range(3):
        blackbox.memory.append({
            "asset": "SOLUSDT",
            "signal_type": "LONG",
            "result": "STOP_LOSS",
            "fingerprint": {"regime": "MARKDOWN", "is_in_ote": True}
        })

    # Instanciamos el motor del Gatekeeper para que refresque su instancia de Bayes
    gk.bayes = BayesianInferenceEngine(blackbox)
    
    # Características del Setup actual (con Veto Fractal activo: LONG en Markdown)
    current_fp = {"regime": "MARKDOWN", "is_in_ote": True}
    prob, reason = gk.bayes.estimate_probability("SOLUSDT", "LONG", current_fp)
    
    print("=== TEST MOTOR BAYESIANO ===")
    print(f"Probabilidad de Win estimada: {prob:.1%}")
    print(f"Razon                       : {reason}")
    print("¿Bypass habilitado? (>=57%) :", "SÍ" if prob >= 0.57 else "NO")
    print()

    # ── 2. Probar la de-duplicación de bloqueos repetitivos ──
    # Limpiamos el historial de de-duplicación
    from engine.router.gatekeeper import SIGNALS_HISTORY
    SIGNALS_HISTORY.clear()
    
    # Simulamos el resultado del proceso de filtrado
    from engine.router.gatekeeper import GatekeeperResult
    result = GatekeeperResult()
    
    dummy_signal = {"asset": "SOLUSDT", "signal_type": "LONG", "price": 100.0}
    
    # Intentamos registrar el primer bloqueo por FRACTAL_VETO
    gk._block(dummy_signal, "FRACTAL_VETO", "Test de bloqueo 1", result)
    print("=== TEST DE-DUPLICADOR ===")
    print("Fila bloqueados (1er intento):", len(result.blocked))
    
    # Intentamos registrar el segundo bloqueo idéntico de forma consecutiva e inmediata
    gk._block(dummy_signal, "FRACTAL_VETO", "Test de bloqueo 2", result)
    print("Fila bloqueados (2do intento):", len(result.blocked))
    print("¿De-duplicacion funcional?   :", "SÍ" if len(result.blocked) == 1 else "NO")

if __name__ == "__main__":
    asyncio.run(test_bayes())
