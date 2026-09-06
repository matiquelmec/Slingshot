@echo off
setlocal enabledelayedexpansion

echo ===============================================================================
echo        SLINGSHOT QUANT ENGINE - QUALITY GATE AND SYSTEM HEALTH
echo ===============================================================================

cd /d C:\Slingshot
set PYTHONPATH=C:\Slingshot

echo.
echo [1/4] Ejecutando bateria completa de 44 tests institucionales...
C:\Slingshot\.venv\Scripts\pytest ^
    engine/tests/test_async_feed.py ^
    engine/tests/test_institutional_security_and_hygiene.py ^
    engine/tests/test_dynamic_slot_recycling.py ^
    engine/tests/test_institutional_stress_and_resilience_suite.py ^
    engine/tests/test_apex_infinity_suite.py ^
    engine/tests/test_multi_account_institutional_audit_suite.py ^
    engine/tests/test_multi_account_stress_and_isolation_suite.py ^
    engine/tests/test_maintenance_suite.py ^
    engine/tests/test_tactical_and_telemetry_suite.py ^
    engine/tests/test_institutional_vulnerabilities_and_risk_fixes.py ^
    engine/tests/test_quantum_ai_and_sentinel_suite.py ^
    engine/tests/test_weekly_tear_sheet_and_auto_retrain_suite.py ^
    engine/tests/test_regime_agent_and_adaptive_sizing_suite.py -q
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallaron los tests unitarios. Despliegue abortado.
    exit /b 1
)
echo [OK] 44/44 tests aprobados al 100%%.

echo.
echo [2/4] Verificando higiene de raiz y seguridad (.env)...
C:\Slingshot\.venv\Scripts\python.exe scripts/diagnostic/check_hygiene.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Violacion de higiene de repositorio detectada en raiz.
    exit /b 1
)

echo.
echo [3/4] Comprobando estado del servicio autonomo SlingshotBot...
powershell -Command "Get-ScheduledTask -TaskName 'SlingshotBot' | Select-Object TaskName, State"

echo.
echo [4/4] Telemetria en vivo de cuentas y posiciones en Bitunix...
C:\Slingshot\.venv\Scripts\python.exe scripts/diagnostic/inspect_real_state.py

echo.
echo ===============================================================================
echo [EXITO] Sistema certificado. Operando bajo estandar institucional continuo.
echo ===============================================================================
