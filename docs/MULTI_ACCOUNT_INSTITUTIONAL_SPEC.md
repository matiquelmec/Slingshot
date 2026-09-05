# Slingshot Institutional Multi-Account Execution Specification (v24.0)

Esta especificación describe la arquitectura, controles criptográficos, aislamiento de riesgo, procedimientos de resiliencia y protocolos de operación institucional para la gestión simultánea de múltiples cuentas en Slingshot Trading Engine.

---

## 1. Arquitectura Multi-Tenant & Concurrencia

El motor Slingshot opera bajo un modelo de desacoplamiento total entre la generación de señales analíticas y la capa de ruteo y ejecución por cuenta.

```
                  ┌───────────────────────────────┐
                  │   Slingshot Alpha Pipeline    │
                  │ (Order Flow, Footprint, SMC)  │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │      Nexus Routing Hub        │
                  │   - Per-Account Risk Check    │
                  │   - Parallel Fan-Out Dispatch │
                  └──────┬─────────────────┬──────┘
                         │                 │
           ┌─────────────┴─────┐     ┌─────┴─────────────┐
           ▼                   ▼     ▼                   ▼
    ┌─────────────┐     ┌─────────────┐           ┌─────────────┐
    │  Account 1  │     │  Account 2  │   ...     │  Account N  │
    │  (Primary)  │     │ (Cliente 2) │           │ (Subcuentas)│
    └─────────────┘     └─────────────┘           └─────────────┘
```

### 1.1 Ruteo Paralelo Asíncrono (`asyncio.gather`)
- Las órdenes límite y a mercado se despachan a todas las cuentas habilitadas de manera concurrente.
- Se utiliza un semáforo global de despacho (`asyncio.Semaphore(10)`) para prevenir saturación de ancho de banda o violaciones de rate limit contra la API de Bitunix.
- **Tolerancia a fallos por cuenta**: El despacho está protegido con `return_exceptions=True` y bloques `try/except` individuales. Un error 401 (credenciales inválidas) o desconexión temporal de una cuenta no degrada ni interrumpe la operativa de las demás cuentas.

---

## 2. Bóveda Criptográfica en Reposo (AES-256 Fernet)

La seguridad de las API Keys y Secret Keys de clientes y subcuentas se gestiona de forma transparente en `engine/execution/account_manager.py`:

- **Derivación de Claves (PBKDF2)**: Clave criptográfica generada mediante HMAC-SHA256 con 100,000 iteraciones utilizando la semilla institucional configurada en variables de entorno (`SECURITY_API_KEY` / `JWT_SECRET`).
- **Formato de Guardado**: Toda credencial sensible almacenada en `engine/data/bitunix_accounts.json` se cifra inmediatamente con el prefijo versionado `enc:v1:`.
- **Migración Automática**: Al iniciar el motor, si se detectan credenciales en texto plano (legadas), el gestor las cifra de forma atómica en disco sin interrumpir el servicio.
- **Memoria Segura**: Las claves solo se descifran en memoria volátil en el momento exacto de instanciar o usar el `BitunixExecutor`.

---

## 3. Aislamiento Estricto de Riesgo y Capacidad

A diferencia de modelos monolíticos donde un límite global bloquea a todos los clientes, Slingshot implementa **Aislamiento de Capacidad por Cuenta**:

- **Fórmula de Slots**: Cada cuenta dispone de su propio límite de operaciones concurrentes no protegidas (`max_unprotected_risk_slots = 4`).
- **Partición de Estado**: Las posiciones activas se identifican internamente como `{account_id}_{symbol}` (ej. `primary_XRPUSDT` vs `cliente_2_XRPUSDT`).
- **Reciclaje Dinámico (Breakeven)**: Una posición cuyo SL ha sido movido a Breakeven (+1.0R / +1.2R con Fee Absorber) libera automáticamente el slot de riesgo de esa cuenta específica, permitiendo abrir nuevos setups sin exceder el VaR permitido.

---

## 4. Background Workers Institucionales (Paridad Total)

Dos demonios autónomos protegen la integridad del capital 24/7 en todas las cuentas:

### 4.1 Sentinel de Órdenes Límite (`TradeManager.sync_live_bitunix_pending_orders`)
Itera por cada cuenta activa e invalida órdenes pendientes en el exchange bajo 4 reglas deterministas:
1. **Missed Target Kill-Switch**: Si el precio de mercado toca o supera el TP1 antes del fill, la orden límite se cancela en la cuenta para evitar entradas tardías en retrocesos desfavorables.
2. **Pre-Entry Structural Breach**: Si el precio rompe el Stop Loss planificado antes de la activación.
3. **TTL Expiration**: Órdenes que superen el tiempo de vida máximo (3 horas).
4. **Capacidad Saturada**: Auto-purga de órdenes límite huérfanas si la cuenta alcanza el cupo máximo de riesgo abierto.

### 4.2 Auto-Healing & Trailing Stop Multicuenta (`TradeManager.sync_live_bitunix_positions`)
- Sincroniza periódicamente las posiciones vivas de todas las cuentas registradas.
- Aplica **Fast BE** (+1.2R para Mega-caps como BTC/ETH y +1.0R para Altcoins) directamente en el exchange mediante `modify_position_tpsl`.
- **Auto-Healing de TPSL**: Si un cliente o una reconexión produce una posición en Bitunix sin Stop Loss registrado en el libro de órdenes, el daemon detecta la discrepancia y coloca el SL de contingencia de inmediato.

---

## 5. Protocolo de Emergencia: Kill-Switch por Cuenta

Se implementó un procedimiento de apagado de emergencia aislado (`emergency_close_account`):

- **Acción Inmediata**:
  1. Cancela el 100% de órdenes límite pendientes de la cuenta.
  2. Cierra a mercado todas las posiciones abiertas en Bitunix.
  3. Deshabilita la cuenta en la configuración (`enabled: false`) para evitar nuevas entradas.
- **Endpoint API Rest**:
  `POST /api/v1/accounts/{account_id}/emergency-close` (protegido por token JWT de administración).
- **Aislamiento**: La ejecución del kill-switch en `cliente_2` no altera las posiciones ni las órdenes de `primary` ni de ningún otro cliente.

---

## 6. Procedimiento de Onboarding de Nuevas Cuentas / Clientes

Para incorporar un nuevo cliente o subcuenta de forma segura:

1. **Vía API / Dashboard**: Enviar solicitud `POST /api/v1/accounts` con `account_id`, `account_label`, `api_key` y `api_secret`.
2. El sistema cifra automáticamente las credenciales con AES-256 antes de persistir en `bitunix_accounts.json`.
3. El `AccountManager` valida la conectividad llamando a `get_wallet_balance()`.
4. Si la conexión es válida, la cuenta entra en el pool de despacho concurrente y el Sentinel y Trade Manager comienzan su auditoría en el siguiente ciclo (30s).

---

## 7. Certificación de Calidad y Suite de Pruebas

Toda la lógica multi-cuenta está blindada por la suite de pruebas unitarias y de integración institucional (`scripts/run_qa_suite.py`):
- `engine/tests/test_multi_account_advanced_security_and_resilience.py` (Cifrado, Sync, Sentinel, Aislamiento de Riesgo, Tolerancia a Fallos, Kill-Switch).
- Total de pruebas en suite: **235 pruebas automatizadas (100% PASS)**.
