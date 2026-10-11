---
description: Flujo institucional de desarrollo Prompt-to-Push (Dual-Engine) para Slingshot v42.2 Apex Titan
---

# Protocolo Prompt-to-Push — Slingshot v42.2 Apex Titan

Este flujo estandariza el ciclo de vida completo de cualquier cambio o feature en el repositorio **Slingshot Trading**, asegurando cero regresiones, inviolabilidad arquitectónica (FSD), seguridad multi-tenant y sincronización documental.

---

## Modos de Ejecución

1. **Modo Institucional Full (Predeterminado):** Para nuevas features, server actions, endpoints, modificaciones en el motor cuantitativo, bases de datos o integraciones.
2. **Modo Fast-Track:** Exclusivo para hotfixes aislados, ajustes cosméticos de estilos (CSS/Tailwind), micro-animaciones o corrección de textos.

---

## 🏛️ Modo Institucional Full (Paso a Paso)

### Paso 0: Diagnóstico Pre-flight
1. Verificar estado del árbol de trabajo:
   ```powershell
   git status
   ```
2. Confirmar que no existan modificaciones no deseadas o conflictos pendientes.
3. Si la tarea involucra conexiones o APIs externas, verificar salud del entorno con:
   ```powershell
   python scripts/doctor.py
   ```

---

### Paso 1: Arquitectura FSD, Seguridad Multi-Tenant & Invariantes Quant
1. **Jerarquía FSD Unidireccional (`src/`):**
   $$\text{app} \longrightarrow \text{features} \longrightarrow \text{entities} \longrightarrow \text{shared}$$
   - Las capas inferiores **nunca** importan de capas superiores.
   - Dos features hermanas **nunca** se importan entre sí (promover a `entities` o `shared`).
   - Cada slice expone su API pública mediante un barrel export (`index.ts`).
2. **Seguridad Multi-Tenant y Anti-IDOR:**
   - Toda mutación o Server Action debe invocar obligatoriamente `requireUserSession()` desde `src/shared/auth`.
   - Aplicar filtros compuestos en queries Drizzle (`and(eq(table.id, targetId), eq(table.tenantId, session.tenantId))`).
   - Validar todos los inputs con esquemas Zod (`.safeParse()`). Tipos `any` prohibidos.
3. **Invariantes Cuantitativos (SOP-1 al SOP-119):**
   - Respetar estrictamente el Universo Canónico Auditado de 13 activos (`CANONICAL_AUDITED_UNIVERSE`).
   - Cero Ganancia Fantasma: el retorno en R debe coincidir matemáticamente con el nivel ejecutado en exchange.
   - En cierres de Bitunix (`tradeSide: "CLOSE"`), incluir obligatoriamente el campo numérico `positionId`.
   - Colocar Take Profit y Stop Loss nativos simultáneamente en órdenes de entrada (`place_limit_signal`).

---

### Paso 2: Estándares UI/UX, Rendimiento & Accesibilidad
1. **Retícula Base 8:** Todos los paddings, margins y gaps deben ser múltiplos estrictos de 8px (`p-2`, `p-4`, `gap-2`, `gap-4`). Micro-espaciado permitido de 4px (`p-1`).
2. **Touch Targets Ergonómicos:** Controles interactivos con tamaño mínimo de $44 \times 44\text{px}$ (`min-h-[44px] min-w-[44px]`).
3. **Contraste Perceptual WCAG 2.2 Nivel AA:** Mínimo 4.5:1 contra el fondo.
4. **Paleta Cyber Dark:** Uso de Tailwind CSS v4 con variables semánticas institucionales (slate, emerald, rose, amber, cyan).
5. **Thumb Zone Móvil:** Acciones principales en el tercio inferior de la pantalla.

---

### Paso 3: Puerta de Calidad Innegociable (Dual-Engine Quality Gate)
Ningún cambio puede darse por concluido sin pasar con 0 errores:

1. **Compilación TypeScript:**
   ```powershell
   npm run typecheck
   ```
2. **Suite de Pruebas Unitarias & Integración (Vitest):**
   ```powershell
   npm test
   ```
3. **Pruebas del Motor Cuantitativo (si se tocó Python / API / Algoritmos):**
   ```powershell
   npm run test:engine
   ```
   *O ejecutar toda la suite unificada:*
   ```powershell
   npm run test:all
   ```

> ⚠️ Si cualquier prueba falla o produce un timeout, debe resolverse de inmediato antes de avanzar al siguiente paso.

---

### Paso 4: Gobernanza Doc-as-Code en Cascada
Sincronizar atómicamente la documentación técnica con el código implementado:
1. `README.md`: Actualizar si se agregaron comandos, scripts, rutas o capacidades del sistema.
2. `docs/architecture/BLUEPRINT_2026.md`: Registrar contratos, diagramas, esquemas o avance de fases.
3. `AGENTS.md`: Actualizar si se crean nuevas reglas de gobernanza o protocolos operativos.

---

### Paso 5: Ciclo Git Completo (Stage, Commit & Push)
1. Indexar únicamente los archivos afectados por la tarea:
   ```powershell
   git add <archivos_modificados>
   ```
2. Crear el commit siguiendo **Conventional Commits v1.0.0**:
   - `feat:` Nueva funcionalidad para el usuario o slice.
   - `fix:` Corrección de bug o brecha de seguridad.
   - `refactor:` Reestructuración interna sin cambio funcional.
   - `test:` Adición o actualización de pruebas.
   - `docs:` Cambios exclusivos en documentación.
   - `perf:` Mejoras de rendimiento o latencia.
   - `chore:` Tareas rutinarias de configuración o dependencias.
3. Enviar a remoto:
   ```powershell
   git push origin <rama_actual>
   ```
4. Confirmar que el working tree quedó limpio:
   ```powershell
   git status
   ```

---

### Paso 5.1: Despliegue y Auditoría Remota de VPS (KRONOS Gate)
> 🚨 **Obligatorio** si el cambio impactó: `engine/`, `scripts/`, `sidecar/`, `entities/`, o dependencias de ejecución.

1. **Despliegue Atómico y Reinicio Remoto:**
   Ejecutar el script automatizado de sincronización y reinicio en el VPS (`80.65.211.99`):
   ```powershell
   powershell -File scripts/deploy/deploy_and_verify_vps.ps1
   ```
2. **Criterios de Aceptación KRONOS (Health Invariant):**
   - Git en VPS sincronizado con el último commit de `origin/main`.
   - Endpoint HTTP responde `[OK] Endpoint Health` o `/docs` con código 200.
   - Tríada de procesos viva: `python.exe` (FastAPI), `node.exe` (Sidecar), `terminal64.exe` (MT5).
   - Ausencia de bucles de reinicio en `sentinel.log`.

---

### Paso 6: Reporte Ejecutivo de Entrega
Entregar al usuario un resumen conciso estructurado:
- **Resumen de Cambios:** Qué se implementó o corrigió.
- **Resultado Quality Gate:** Confirmación de `typecheck` (0 errores) y pruebas en verde (`vitest` / `pytest`).
- **Commit & Push:** Hash del commit y confirmación de sincronización con GitHub.
- **Estado del VPS en Vivo (80.65.211.99):** Confirmación de despliegue, healthcheck HTTP `200 OK` y PIDs de la tríada operativa.

---

## ⚡ Modo Fast-Track (Hotfix & Ajustes UI Directos)

Para cambios cosméticos, copy o micro-ajustes:
1. Aplicar el cambio respetando FSD y Base 8.
2. Ejecutar Quality Gate rápido:
   ```powershell
   npm run typecheck
   npm test
   ```
3. Commit semántico (`fix:` o `refactor:`) y push.
4. Reporte breve al usuario.
