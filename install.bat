@echo off
chcp 65001 >nul
title Slingshot v42.0 APEX TITAN COMPOUND -- Instalador Automatico 1-Click
color 0B

echo ===============================================================================
echo       SLINGSHOT v42.0 APEX TITAN COMPOUND -- INSTALADOR UNIVERSAL 1-CLICK          
echo ===============================================================================
echo.
echo [1/4] Comprobando entorno de ejecucion y politicas locales...
echo.

cd /d "%~dp0"

:: Ejecucion robusta de PowerShell con bypass explicito y soporte de codificacion UTF-8
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; & '%~dp0install.ps1' }"

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
echo [EXITO] Slingshot v42.0 ha sido instalado y verificado al 100%%.
echo Presiona cualquier tecla para cerrar esta ventana.
echo ===============================================================================
pause >nul
