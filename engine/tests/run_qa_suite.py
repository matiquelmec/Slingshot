# engine/tests/run_qa_suite.py
"""
=============================================================================
SLINGSHOT INSTITUTIONAL QA RUNNER — CERTIFICACIÓN DE CALIDAD v16.0
=============================================================================
Ejecuta la suite completa de pruebas unitarias y emite el sello de certificación
para trading en MetaTrader 5 (FTMO) y Bitunix.
"""
import sys
import os
import subprocess
import time

def run_step(title, command):
    print(f"\n" + "="*70)
    print(f"🚀 INICIANDO: {title}")
    print("="*70)
    start = time.time()
    
    res = subprocess.run(command, shell=True, text=True, capture_output=True)
    duration = time.time() - start
    
    if res.returncode == 0:
        print(f"✅ PASÓ EXITOSAMENTE ({duration:.2f}s)")
        if res.stdout:
            # Imprimir solo las últimas 15 líneas para limpieza
            lines = res.stdout.strip().split('\n')
            print('\n'.join(lines[-15:]))
        return True
    else:
        print(f"[FAIL] FALLO ({duration:.2f}s)")
        print("STDERR:\n", res.stderr)
        print("STDOUT:\n", res.stdout)
        return False

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("""
    ===============================================================
    🛡️  SLINGSHOT APEX QA & PRE-FLIGHT VERIFICATION SUITE
    ===============================================================
    Garante Institucional: OMEGA Firewall
    Stack: NVIDIA Nemotron AI | SMC Platinum | FTMO Risk Manager
    ===============================================================
    """)
    
    env_python = sys.executable
    steps = [
        ("1. Pruebas Unitarias de Riesgo y Fast Breakeven (+1.0R)", f'"{env_python}" -m pytest engine/tests/test_risk_manager.py -v'),
        ("2. Pruebas Unitarias de Confluencia y Veto Long-Only de Oro", f'"{env_python}" -m pytest engine/tests/test_confluence.py -v'),
        ("3. Pruebas Unitarias de IA NVIDIA Nemotron & Inferencia", f'"{env_python}" -m pytest engine/tests/test_ai_advisor.py -v'),
        ("4. Pruebas Unitarias de Motor Polars (Rust) y Telegram Dispatcher", f'"{env_python}" -m pytest engine/tests/test_v17_hyper_velocity.py -v'),
        ("5. Pruebas Unitarias de Ghost Sentinel y Veto Macro", f'"{env_python}" -m pytest engine/tests/test_ghost_sentinel.py -v'),
        ("6. Pruebas Unitarias de Sincronización 1-a-1 Escáner & Signal Store", f'"{env_python}" -m pytest engine/tests/test_scanner_sync.py -v'),
        ("7. Pruebas Unitarias de Veracidad de Señales, Ciclo de Vida y Watchdog", f'"{env_python}" -m pytest engine/tests/test_signal_lifecycle_truth.py -v'),
        ("8. Pruebas Unitarias de Ingestión TradFi y Motor de Backtest 6 Meses", f'"{env_python}" -m pytest engine/tests/test_tradfi_backtest.py -v'),
        ("9. Pruebas Unitarias de FTMO Guardian Shield (Drawdown Killswitch y Lotes MT5)", f'"{env_python}" -m pytest engine/tests/test_ftmo_guardian.py -v'),
    ]
    
    all_passed = True
    for title, cmd in steps:
        passed = run_step(title, cmd)
        if not passed:
            all_passed = False
            break
            
    print("\n" + "="*70)
    if all_passed:
        print("🎉 CERTIFICACIÓN DE CALIDAD: 100% APROBADO (0 ERRORES)")
        print("🛡️ EL SISTEMA ESTÁ LISTO Y BLINDADO PARA TRADING EN FTMO Y BITUNIX.")
        print("="*70)
        sys.exit(0)
    else:
        print("🚨 CERTIFICACIÓN FALLIDA: Corregir errores antes de operar.")
        print("="*70)
        sys.exit(1)

if __name__ == '__main__':
    main()
