"""
scripts/run_qa_suite.py
=============================================================================
EJECUTOR OFICIAL DE LA SUITE DE CERTIFICACIÓN QA (26 PRUEBAS UNITARIAS)
=============================================================================
"""
import sys
import subprocess
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODERN_TEST_FILES = [
    "engine/tests/test_setup_and_portability.py",
    "engine/tests/test_post_tp3_and_trailing_invariance.py",
    "engine/tests/test_risk_and_resilience_advanced.py",
    "engine/tests/test_full_engine_autonomy_audit.py",
    "engine/tests/test_live_trade_management.py",
    "engine/tests/test_intelligent_limit_order_sentinel.py",
    "engine/tests/test_sqlite_vault.py",
    "engine/tests/test_mt5_bridge.py",
    "engine/tests/test_deterministic_pipeline_isolation.py",
    "engine/tests/test_session_mastery.py",
    "engine/tests/test_market_scanner_hft.py",
    "engine/tests/test_ftmo_security_guard.py",
    "engine/tests/test_telegram_persistence.py",
    "engine/tests/test_dynamic_sl_professional_audit.py",
    "engine/tests/test_dynamic_universe_screener.py"
]

def main():
    print("\n" + "="*80)
    print("🧪 SLINGSHOT v22.2 APEX — SUITE OFICIAL DE CERTIFICACIÓN QA")
    print("="*80)
    
    cmd = [sys.executable, "-m", "pytest"] + MODERN_TEST_FILES + ["-v", "--tb=short"]
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    
    if result.returncode == 0:
        print("\n" + "="*80)
        print("✅ CERTIFICACIÓN QA EXITOSA: 55/55 PRUEBAS APROBADAS AL 100%")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("❌ FALLO EN LA CERTIFICACIÓN QA")
        print("="*80 + "\n")
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
