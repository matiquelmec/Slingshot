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
    "engine/tests/test_dynamic_universe_screener.py",
    "engine/tests/test_auto_healing_and_telemetry.py",
    "engine/tests/test_chart_and_telemetry_pipeline.py",
    "engine/tests/test_confluence_end_to_end_integrity.py",
    "engine/tests/test_backend_performance_and_security.py",
    "engine/tests/test_breathing_room_and_nexus_harmony.py",
    "engine/tests/test_institutional_execution_security_audit.py",
    "engine/tests/test_cluster_risk_guard.py",
    "engine/tests/test_stream_resilience_and_rate_limiting.py",
    "engine/tests/test_apex_shield_and_fault_tolerance.py",
    "engine/tests/test_weekly_seasonality_and_time_gating.py",
    "engine/tests/test_instant_microstructure_hydration.py",
    "engine/tests/test_fullstack_telemetry_and_synapse_stream.py",
    "engine/tests/test_pyramiding_and_free_roll_scale_in.py",
    "engine/tests/test_true_backtest_ssot_parity.py",
    "engine/tests/test_apex_titan_smart_time_gating.py",
    "engine/tests/test_apex_zenith_news_and_post_only.py",
    "engine/tests/test_multi_market_ftmo_and_crypto_harmony.py",
    "engine/tests/test_realtime_candlestick_formation_and_stream.py",
    "engine/tests/test_sop21_liquidation_invariance_and_precision.py",
    "engine/tests/test_apex_infinity_lifecycle_and_orphan_purge.py",
    "engine/tests/test_sop25_sop26_mae_mfe_harvesting.py",
    "engine/tests/test_sop27_vwap_exhaustion_shield.py",
    "engine/tests/test_sop28_to_sop31_sovereign_suite.py",
    "engine/tests/test_sop32_to_sop35_intelligent_leverage.py"
]

def main():
    print("\n" + "="*80)
    print("🧪 SLINGSHOT v40.0 APEX TITAN LEVERAGE — SUITE OFICIAL DE CERTIFICACIÓN QA")
    print("="*80)
    
    cmd = [sys.executable, "-m", "pytest"] + MODERN_TEST_FILES + ["-v", "--tb=short"]
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    
    if result.returncode == 0:
        print("\n" + "="*80)
        print("✅ CERTIFICACIÓN QA EXITOSA: 191/191 PRUEBAS APROBADAS AL 100%")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("❌ FALLO EN LA CERTIFICACIÓN QA")
        print("="*80 + "\n")
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
