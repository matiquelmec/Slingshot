# 🛡️ Estructura del Proyecto Slingshot (v12.0 Apex)

Guía de referencia para el mantenimiento de la higiene del código y la arquitectura institucional.

## 📁 Directorios Principales

-   **/engine**: Núcleo del sistema de trading.
    -   **/core**: Motores fundamentales (Logger, Confluence, Config).
    -   **/indicators**: Algoritmos de análisis técnico y SMC (v12.0 Refactor).
    -   **/router**: Orquestación de señales, Gatekeeper y ejecución.
    -   **/strategies**: Lógica táctica de entrada y salida.
-   **/docs**: Documentación técnica, planes de auditoría y guías de arquitectura.
-   **/scratch**: Scripts de diagnóstico, pruebas de conectividad y herramientas temporales. **(NO BORRAR: Contiene herramientas de validación v12.1)**

## 🛠️ Herramientas de Diagnóstico Críticas

Para validar el sistema tras cambios en los indicadores o la confluencia, utilizar:
```bash
$env:PYTHONPATH="."; python scratch/scratch_xag_audit.py
```

## 📜 Reglas de Oro de Arquitectura

1.  **Higiene de Archivos**: No crear scripts en la raíz. Todo script de prueba debe ir a `/scratch`.
2.  **Persistencia SMC**: Los Order Blocks se invalidan por CIERRE, no por mechas. No revertir a la lógica del 50%.
3.  **Sovereign Bypass**: Las señales de convicción >= 95% tienen prioridad absoluta sobre los filtros de tendencia macro.
4.  **Logging**: Mantener el formato institucional `[MODULO] Mensaje` para facilitar el debug mediante grep.
