# 🏗️ AUDITORÍA ARQUITECTÓNICA: SLINGSHOT v1.0
**Fecha:** 26-02-2026
**Analista:** Sentinel AI (Arquitecto Senior)

---

## 🔍 RESUMEN EJECUTIVO

He contrastado el documento fundacional `BLUEPRINT_MAESTRO.md` contra la **realidad física actual** del código en tu repositorio `Slingshot Gen 1`. 

La arquitectura conceptual descrita en el Blueprint es **excelente y de nivel institucional** (patrón de 6 capas, separación de responsabilidades, asincronía). Sin embargo, la implementación actual muestra una **deuda técnica estructural** donde el código real no refleja completamente la visión del documento, especialmente en el Frontend y en los módulos de Riesgo/Backtest.

A continuación, detallo las brechas encontradas y mis recomendaciones como Ingeniero Senior para cerrar estas brechas con eficiencia y calidad profesional.

---

## 🏛️ ANÁLISIS DE CAPAS (Blueprint vs. Realidad)

### 1. Frontend (Next.js 15 App Router)
* **Lo que dice el Blueprint:** Una estructura App Router con sub-rutas anidadas bajo un grupo `(dashboard)`: `/signals`, `/backtest`, `/portfolio`, `/lab`.
* **La realidad:** Tienes un enfoque de **Single Page Application (SPA) masiva**. Todo está inyectado directamente en `app/page.tsx` (32KB de tamaño). No existen las sub-rutas.
* **Diagnóstico:** `page.tsx` se convertirá en un monolito inmanejable pronto. Next.js brilla cuando separas el código en distintas rutas para hacer Code Splitting automático.
* **Recomendación Profesional:** Debemos migrar la lógica monolítica de `page.tsx` hacia la estructura multi-ruta del Blueprint `app/(dashboard)/...`. El dashboard principal debe ser un resumen, y las herramientas pesadas (Terminal, Heatmap) deben ir en sus propias URLs.

### 2. Capa de Riesgo y Backtesting (`engine/risk` y `engine/backtest`)
* **Lo que dice el Blueprint:** Existencia de directorios dedicados para `position_sizer.py`, `portfolio.py`, motor de `vectorbt`, etc.
* **La realidad:** Estas carpetas no existen actualmente en la raíz de `engine/` (se limpiaron previamente porque estaban vacías o rotas). El control de riesgo actualmente está "mockeado" dentro de los archivos de cada estrategia (`smc.py`, `trend.py`).
* **Diagnóstico:** El acoplamiento del cálculo de riesgo dentro de los archivos de estrategia rompe el Principio de Responsabilidad Única (SRP).
* **Recomendación Profesional:** Restablecer la carpeta `engine/risk/` y crear un `risk_manager.py` robusto y global que lea el balance de la cuenta desde `.env` y controle el apalancamiento centralizadamente, para inyectarlo (Dependency Injection) en el `main_router.py`, no dentro de las estrategias.

### 3. Capa de Inteligencia (`engine/ml`)
* **Lo que dice el Blueprint:** Entrenamiento, inferencia ONNX, feature engineering y monitoreo de drift.
* **La realidad:** Tienes la carpeta `engine/ml/` con 5 archivos, lo cual es excelente y se alinea bastante bien con el Blueprint. Sin embargo, en el Frontend el `NeuralOperationsHub` estaba inactivo/desconectado.
* **Diagnóstico:** El backend está listo para ML, pero el pipeline de consumo en el frontend está desconectado.
* **Recomendación Profesional:** Mantener la estructura de Modelos en el backend, pero exponer un microservicio específico en FastAPI (`/api/ml/predict`) y consumirlo con `TanStack Query` en el Frontend de forma asíncrona, sin bloquear el hilo principal de Next.js.

### 4. Capa Core y Estrategias (`engine/strategies` e `indicators`)
* **Lo que dice el Blueprint:** Estrategias puras sin side-effects. Indicadores por dominio (trend, momentum, volume).
* **La realidad:** Estructura **fuerte y bien implementada**. Las carpetas `indicators/` y `strategies/` coinciden perfectamente con el documento. `main_router.py` ejerce bien su labor como "Cerebro".
* **Diagnóstico:** Esta es la zona mejor construida del proyecto actual.
* **Recomendación Profesional:** Mantener esta estructura. Solo se requiere estandarizar que toda estrategia herede de una interfaz/clase abstracta base (`strategy.py`) para garantizar que todas tengan métodos `analyze()` y `find_opportunities()` estandarizados.

---

## 🛠️ PLAN DE ACCIÓN (PRÓXIMOS PASOS)

Si queremos elevar este proyecto a la calidad que exige el **BLUEPRINT MAESTRO**, te sugiero abordar las siguientes refactorizaciones en orden de prioridad:

### Prioridad 1: Desacoplar el Monolito del Frontend
1. Crear el grupo de rutas `app/(dashboard)/`.
2. Mover componentes pesados de `app/page.tsx` a `app/(dashboard)/signals/page.tsx`, etc.
3. Asegurar de que los componentes de la interfaz de usuario usen `use client` solo cuando interactúan con estado de React, apoyándose en Server Components para la carga estática.

### Prioridad 2: Centralizar la Gestión de Riesgos
1. Revivir `engine/risk/risk_manager.py`.
2. Eliminar el riesgo interno (Mocked) de las estrategias.
3. El `main_router.py` debe ser el único encargado de procesar la señal de la estrategia, enviarla al Risk Manager, calcular el Stop Loss/Take Profit, y generar la señal final.

### Prioridad 3: Actualizar el BLUEPRINT_MAESTRO.md
* Hay que marcar el checklist de la **FASE 4: Saneamiento Final / Refactor** en el Blueprint para reflejar que la infraestructura ya está en curso, pero requiere la reconstrucción de las rutas del Frontend.

---
**¿Conclusiones?**
El código base es robusto (FastAPI + Next.js), pero está sufriendo de centralización (todo unificado en pocos archivos grandes en vez de distribuidos por rutas o clases especializadas). Actuar sobre el Frontend será la ganancia más rápida en eficiencia que podemos hacer ahora mismo.
