@echo off
title SLINGSHOT VPS - ACTUALIZAR Y ACTIVAR GITOPS 24/7
color 0A
cd /d %~dp0

echo ==============================================================================
echo [1/3] DESCARGANDO ULTIMA VERSION CANONICA DESDE GITHUB (SOP-113 & SOP-114)...
echo ==============================================================================
git fetch origin main
git reset --hard origin/main

echo.
echo ==============================================================================
echo [2/3] GENERANDO LANZADOR AUTONOMO CON AUTO-REINICIO...
echo ==============================================================================
(
echo @echo off
echo title SLINGSHOT TRADING DUAL ENGINE ^(BITUNIX + MT5^) - GITOPS AUTONOMOUS
echo color 0A
echo cd /d %%~dp0
echo.
echo :loop
echo echo [%%date%% %%time%%] Iniciando Slingshot Engine...
echo call .venv\Scripts\activate.bat
echo python -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000
echo echo [%%date%% %%time%%] Motor actualizado o reiniciado. Reiniciando en 3 segundos...
echo timeout /t 3 /nobreak ^>nul
echo goto loop
) > arrancar_slingshot.bat

echo Lanzador arrancar_slingshot.bat actualizado con exito.
echo.
echo ==============================================================================
echo [3/3] REINICIANDO PROCESO PYTHON CON EL CODIGO 100%% NUEVO...
echo ==============================================================================
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
start "" arrancar_slingshot.bat

echo.
echo ==============================================================================
echo EXITO TOTAL: El VPS esta corriendo la version mas reciente y a partir de ahora
echo se actualizara SOLO cada 5 minutos contra GitHub.
echo ==============================================================================
pause
