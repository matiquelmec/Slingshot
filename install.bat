@echo off
chcp 65001 >nul
title Slingshot Apex Sovereign -- Instalador Automatico 1-Click
color 0B

echo ===============================================================================
echo       SLINGSHOT v22.3 APEX SOVEREIGN -- INSTALADOR AUTOMATICO 1-CLICK          
echo ===============================================================================
echo.
echo [1/4] Comprobando politicas de PowerShell y permisos locales...
echo.

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ===============================================================================
    echo [ERROR] La instalacion automatica reporto un inconveniente.
    echo Revisa los mensajes anteriores para mas detalles.
    echo ===============================================================================
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===============================================================================
echo [EXITO] Slingshot Apex Sovereign ha sido instalado y verificado al 100%%.
echo Presiona cualquier tecla para cerrar esta ventana.
echo ===============================================================================
pause >nul
