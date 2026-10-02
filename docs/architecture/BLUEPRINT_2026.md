# BLUEPRINT_2026.md — Arquitectura de Plataforma Institucional

> **Versión del Sistema:** 10.0.0 (FSD Multi-Tenant Dual-Engine Architecture)  
> **Fecha de Actualización:** Octubre 2026  
> **Estado:** Fase 1 — Fundación de Gobernanza y FSD Completada

---

## 1. Visión y Filosofía del Sistema

Este ecosistema combina dos motores de ingeniería de alta precisión:
1. **Frontend / Capa de Aplicación Multi-Tenant (Next.js 15 + React 19 + TypeScript + FSD):** Proporciona la interfaz interactiva en tiempo real, gestión de tenants/organizaciones, telemetría visual de alta frecuencia y Server Actions protegidos contra vulnerabilidades de acceso horizontal (IDOR).
2. **Motor Cuantitativo HFT / IA Institucional (Python 3.12 + FastAPI + Polars + XGBoost/ONNX):** Procesa el flujo de órdenes (Order Flow Delta, CVD), Smart Money Concepts (SMC), confluencias multidimensionales y ejecución algorítmica de baja latencia con Bitunix Futures y TradFi/MT5.

---

## 2. Stack Tecnológico Base

| Capa | Tecnología | Propósito |
| :--- | :--- | :--- |
| **Framework Web** | Next.js 15 (App Router) + React 19 | Server Components, Streaming SSR, Server Actions |
| **Arquitectura Frontend** | Feature-Sliced Design (FSD) v2.1 | Separación estricta de responsabilidades en `src/` |
| **Tipado y Contratos** | TypeScript 5.9 + Zod 4 / 3.23 | Verificación estática estricta y validación en tiempo de ejecución |
| **Estilos & UI** | Tailwind CSS v4 + Framer Motion | Retícula Base-8, paleta Cyber Dark WCAG 2.2 AA |
| **Testing Frontend** | Vitest 5 + @vitejs/plugin-react | Pruebas unitarias de contratos, seguridad y Server Actions |
| **Persistencia Multi-Tenant** | Drizzle ORM + Turso (LibSQL) / PostgreSQL | Aislamiento estricto por `tenant_id` y `user_id` |
| **Motor Cuantitativo** | Python 3.12 + FastAPI + Polars | Cálculo de indicadores de alta frecuencia y endpoints REST/WS |
| **Inferencia Neural** | ONNX Runtime + XGBoost Meta-Labeling | Filtro de confluencia probabilística en tiempo real |
| **Conectividad Exchange** | Bitunix API / WebSocket Sidecar Node.js | Ingestión de ticks en submilisegundos y ejecución de órdenes |

---

## 3. Arquitectura en Capas (Feature-Sliced Design)

El código fuente de la aplicación reside en `src/` respetando el flujo unidireccional estricto:

```
src/
├── app/                  # Enrutador, Layouts, Providers globales (Next.js App Router)
│   ├── (dashboard)/      # Rutas del terminal: overview, bitunix, chart, ftmo, radar, signals
│   ├── api/              # Proxy y endpoints de retransmisión
│   ├── globals.css       # Tokens de diseño CSS y temas
│   └── layout.tsx        # Shell raíz y fuentes
├── features/             # Slices interactivos y Server Actions orientados a usuario
│   ├── order-execution/  # Server Actions con validación Zod y aislamiento multi-tenant
│   ├── radar-scanner/    # Escáner de oportunidades y filtros de mercado
│   └── telemetry-feed/   # Consumo reactivo de métricas de cuenta y WS
├── entities/             # Modelos de datos del dominio, contratos y tipos
│   ├── tenant/           # Esquemas Zod y modelo de organización/tenant
│   └── signal/           # Esquemas Zod y modelo de señal cuantitativa
└── shared/               # Primitivas transversales y utilidades base
    ├── auth/             # Verificación de sesión de usuario (requireUserSession)
    ├── db/               # Helpers de aislamiento multi-tenant (tenantGuard)
    ├── ui/               # Kit de componentes base (Button, etc. en Base 8 y WCAG AA)
    └── lib/              # Utilidades de formato, red y cálculo
```

### Regla de Acoplamiento y Dependencias:
* **`app`** puede consumir `features`, `entities` y `shared`.
* **`features`** puede consumir `entities` y `shared`. Jamás otra feature hermana ni `app`.
* **`entities`** puede consumir únicamente `shared`.
* **`shared`** no depende de ninguna otra capa interna del proyecto.

---

## 4. Diseño del Modelo de Datos Multi-Tenant

Para garantizar la soberanía de los datos entre diferentes usuarios, academias o firmas de prop trading, el esquema de base de datos implementa **Aislamiento Multi-Tenant por Clave Particionada**:

### Esquema Conceptual (Drizzle / Relacional):

```mermaid
erDiagram
    TENANTS ||--o{ USERS : owns
    TENANTS ||--o{ ACCOUNTS : manages
    USERS ||--o{ SIGNALS : tracks
    ACCOUNTS ||--o{ TRADES : executes
    TENANTS ||--o{ TRADES : isolates

    TENANTS {
        uuid id PK
        string name
        string tier "starter | pro | institutional"
        int max_concurrent_positions
        string status
        timestamp created_at
    }

    USERS {
        uuid id PK
        uuid tenant_id FK
        string email
        string role "admin | trader | viewer"
        timestamp created_at
    }

    SIGNALS {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        string asset
        string direction "LONG | SHORT"
        decimal entry_price
        decimal stop_loss
        decimal confluence_score
        decimal ker_value
        string status
    }

    ACCOUNTS {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        string exchange "bitunix | mt5_ftmo"
        string api_key_encrypted
        string secret_encrypted
        decimal current_balance
    }
```

### Protocolo de Consulta con Aislamiento (Query Guard):
Toda consulta SQL generada en Server Actions o rutas debe incluir obligatoriamente el predicado compuesto:

```typescript
// Consulta segura con protección anti-IDOR
const result = await db
  .select()
  .from(signals)
  .where(
    and(
      eq(signals.id, targetSignalId),
      eq(signals.userId, session.userId),
      eq(signals.tenantId, session.tenantId)
    )
  );
```

---

## 5. Bitácora de Fases de Desarrollo

| Fase | Alcance | Estado | Entregables Principales |
| :---: | :--- | :---: | :--- |
| **Fase 1** | **Fundación Arquitectónica FSD & Gobernanza** | ✅ **Completado** | • Estructura FSD en `src/` (`app`, `features`, `entities`, `shared`)<br>• `AGENTS.md` con reglas innegociables<br>• `BLUEPRINT_2026.md`<br>• Scripts `typecheck` y `test` en `package.json`<br>• Vitest 5 configurado y 13 tests pasando |
| **Fase 2** | **Auditoría Exhaustiva, Higiene y Promoción FSD** | ✅ **Completado** | • Limpieza de 60 MB de logs obsoletos y caches en raíz<br>• Promoción de `formatters` y `apiUrl` a `src/shared/lib/`<br>• Promoción de contratos de dominio a `src/entities/signal/types.ts`<br>• Corrección ergonómica UI/UX: touch targets ≥44px y contraste WCAG 2.2 AA (≥4.5:1)<br>• Guardián arquitectónico automatizado en `tests/unit/fsd-architecture.test.ts`<br>• Suite de Vitest ampliada a 23 tests unitarios (100% pasando) |
| **Fase 3** | **Slices UI & Server Actions Zod (FSD)** | ✅ **Completado** | • Slices `src/features/signals-feed` y `src/features/positions-tracker` creadas y exportadas vía barrel index<br>• Server Actions con validación Zod y protección anti-IDOR (`fetchSignalsAction`, `recordSignalAction`, `fetchTradesAction`, `recordTradeAction`)<br>• Integración reactiva en componentes Radar y History con persistencia Turso y fallback |
| **Fase 4** | **Persistencia Serverless & RLS Multi-Tenant (Turso + Drizzle)** | ✅ **Completado** | • Cliente Drizzle ORM + LibSQL configurado en `src/shared/db/index.ts`<br>• Esquema multi-tenant (`tenants`, `users`, `signals`, `trades`, `risk_configs`, `accounts`) sincronizado en Turso Cloud<br>• Drizzle Kit integrado (`npm run db:push`, `db:studio`)<br>• Tests unitarios de anti-IDOR y DB client pasando al 100% |
| **Fase 5** | **Integración Dual-Engine & Telemetría Segura** | ✅ **Completado** | • Sincronización HTTP Pipeline v2 en segundo plano (`engine/execution/turso_sync.py`) sin latencia en hot-path<br>• Hooking continuo de posiciones y órdenes en `bitunix_executor.py`, `mt5_bridge.py` y `main.py`<br>• Pruebas de regresión dual completadas (100% en verde) |

---

## 6. Verificación Continua y Criterios de Aceptación

Para asegurar la robustez del sistema, los pipelines de CI/CD ejecutan:
1. `npm run typecheck`: Validación estática de tipos TypeScript sin emitir artefactos (0 errores).
2. `npm test`: Suite unitaria de Vitest (33 tests pasando en ~800ms).
3. `npm run test:engine`: Suite de pytest para el motor analítico de Python (426 tests pasando).
4. `npm run build`: Compilación de producción optimizada de Next.js sin errores de build.

---

## 7. Registro de Auditoría de Repositorio e Higiene Institucional

* **Eliminación de Residuos:** Eliminados 60 MB de logs rotados en `tmp/logs/` y limpiados directorios temporales `__pycache__`. Certificado con `scripts/diagnostic/check_hygiene.py`.
* **Desacoplamiento de Utilidades:** `src/shared/lib/formatters.ts` y `src/shared/lib/apiUrl.ts` centralizan las primitivas comunes, manteniendo fachadas transparentes en `src/app/utils/`.
* **Single Source of Truth para Señales:** `src/entities/signal/types.ts` canoniza la estructura de `Signal`, `ConfluenceData` y `AccountProfileConfig`.
* **Accesibilidad Ergonómica:**
  * Modal close button: aumentado a `min-h-[44px] min-w-[44px]` con `aria-label`.
  * Multi-sensor tabs: ajustados a `min-h-[44px]` con contraste optimizado `text-slate-300` (ratio $\ge 4.5:1$).
* **Guardias Automatizadas FSD:** `tests/unit/fsd-architecture.test.ts` analiza estáticamente el AST/imports para bloquear automáticamente en CI cualquier importación descendente indebida.

