# 🔐 Slingshot Institutional Multi-Account Execution Specification (v51.0)
## Multi-Tenant Architecture, Cryptographic Vault & Risk Isolation (SOP-57 / SOP-58 / SOP-59)

Esta especificación describe la arquitectura técnica, controles criptográficos, aislamiento de riesgo, procedimientos de resiliencia y protocolos de operación institucional para la gestión simultánea de múltiples cuentas y subcuentas de clientes en Slingshot Trading Engine.

---

## 1. Arquitectura Multi-Tenant & Concurrencia Asíncrona

El motor Slingshot opera bajo un modelo de desacoplamiento absoluto entre la generación de señales analíticas y la capa de enrutamiento y ejecución por cuenta:

```text
                  ┌───────────────────────────────┐
                  │   Slingshot Alpha Pipeline    │
                  │ (Order Flow, SMC, OTE, ML AI) │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │      Nexus Routing Hub        │
                  │   - Per-Account Risk Check    │
                  │   - Parallel Fan-Out Dispatch │
                  └──────┬─────────────────┬──────┘
                         │                 │
            ┌────────────┴────┐       ┌────┴────────────┐
            ▼                 ▼       ▼                 ▼
     ┌─────────────┐   ┌─────────────┐   ...     ┌─────────────┐
     │  Account 1  │   │  Account 2  │           │  Account N  │
     │  (Primary)  │   │ (Cliente 2) │           │ (Subcuentas)│
     └─────────────┘   └─────────────┘           └─────────────┘
```

### 1.1 Ruteo Paralelo Asíncrono (`asyncio.gather`)
- Las órdenes límite y de mercado se despachan de forma concurrente a todas las cuentas habilitadas mediante `asyncio.gather(*tasks, return_exceptions=True)`.
- Se utiliza un semáforo global de despacho (`asyncio.Semaphore(10)`) para prevenir saturación de ancho de banda o violaciones de *rate limit* contra las APIs de los exchanges.
- **Tolerancia a fallos desacoplada por cuenta**: Cada ejecución está envuelta en bloques de aislamiento individual. Si una cuenta experimenta un error de autenticación (ej. 401 por credenciales revocadas), saldo insuficiente temporal o desconexión de red, las demás cuentas continúan su ciclo de ejecución y monitoreo sin ninguna interrupción.

---

## 2. Bóveda Criptográfica en Reposo (AES-256 Fernet con PBKDF2)

La seguridad de las credenciales de API (API Keys y Secret Keys) de clientes y subcuentas se gestiona de forma transparente en `engine/execution/account_manager.py`:

* **Derivación de Claves Criptográficas (PBKDF2):** La clave maestra de cifrado se genera mediante `PBKDF2HMAC` utilizando `HMAC-SHA256` con **100,000 iteraciones** a partir de la semilla institucional configurada en el entorno seguro (`SECURITY_API_KEY` / `JWT_SECRET`).
* **Formato de Guardado Versionado:** Toda credencial sensible persistida en el almacén de configuración (`engine/data/bitunix_accounts.json`) se almacena cifrada con el prefijo versionado `enc:v1:`.
* **Migración Automática y Transparente:** Al iniciar el motor, si se detectan credenciales legadas en texto plano, el gestor las cifra de forma atómica en disco sin requerir reinicios manuales ni interrumpir el servicio.
* **Memoria Segura & Enmascaramiento:** Las credenciales solo se descifran en memoria volátil en el instante milimétrico del despacho. Toda exportación de datos a bitácoras, telemetría o endpoints API enmascara los secretos de manera estricta (`mask_secrets=True`), mostrando únicamente los primeros 4 y últimos 4 caracteres.

---

## 3. Aislamiento Estricto de Riesgo y Capacidad por Cuenta

A diferencia de sistemas monolíticos donde un límite global bloquea a todos los clientes, Slingshot implementa **Aislamiento de Capacidad y Cuotas de Riesgo Independientes**:

* **Fórmula de Slots Desacoplados:** Cada cuenta dispone de su propio límite de operaciones concurrentes con riesgo abierto (`max_unprotected_risk_slots = 4`).
* **Partición de Estado en Memoria:** Las posiciones activas se identifican unívocamente mediante la clave `{account_id}_{symbol}` (ej. `primary_ETHUSDT` frente a `cliente_2_ETHUSDT`).
* **Cerrojos de Deduplicación Atómica (SOP-50):** `_symbol_locks[f"{account}_{symbol}"]` garantizan que las ráfagas de señales concurrentes no dupliquen órdenes en ninguna cuenta.
* **Reciclaje Dinámico en Breakeven (SOP-12):** Una posición cuyo Stop Loss ha sido trasladado a Breakeven libera automáticamente el slot de riesgo de esa cuenta específica, habilitando la captura de nuevas oportunidades sin exceder el VaR permitido.
* **Guardián de Margen Congelado (SOP-51):** Al computar el balance disponible para una cuenta, el sistema descuenta rigurosamente el margen congelado en órdenes límite pendientes (`tradeSide == OPEN`), eliminando errores de balance insuficiente en el exchange.

---

## 4. Background Workers Institucionales & Protocolo SOP-59

Dos centinelas autónomos protegen la integridad del capital 24/7 en todas las cuentas conectadas:

### 4.1 Centinela de Órdenes Límite (`TradeManager.sync_live_bitunix_pending_orders`)
Itera por cada cuenta activa e invalida órdenes pendientes bajo 4 reglas deterministas:
1. **Missed Target Kill-Switch (SOP-25):** Si el precio de mercado toca o supera el TP1 antes del llenado (*fill*), la orden límite se cancela en la cuenta para evitar entradas tardías en retrocesos desfavorables.
2. **Pre-Entry Structural Breach:** Si el precio rompe el nivel de Stop Loss planificado antes de la activación de la entrada.
3. **Expiración por TTL (SOP-52):** Cancelación automática de órdenes que superen las 3 horas de antigüedad sin ejecutarse.
4. **Saturación de Capacidad:** Auto-purga de órdenes límite huérfanas si la cuenta alcanza el cupo máximo de riesgo abierto.

### 4.2 Auto-Healing & Trailing Stop Multicuenta (`TradeManager.sync_live_bitunix_positions`)
- Sincroniza periódicamente las posiciones vivas de todas las cuentas registradas.
- Aplica **Fast BE** (+1.2R para Mega-caps como BTC/ETH y +1.0R para Altcoins) directamente en el exchange mediante `modify_position_tpsl`.
- **Auto-Healing de TPSL:** Si un cliente o una reconexión produce una posición en el exchange sin Stop Loss registrado en el libro de órdenes, el daemon detecta la anomalía y coloca el Stop Loss de contingencia de inmediato.

### 4.3 Sentinela de Intervención Manual de Clientes (SOP-59)
* **Problema Resuelto:** Cuando un inversor o cliente cierra manualmente una posición desde la app móvil del exchange (`clientId: null`), anteriormente podían quedar órdenes límite residuales de Take Profit o Reentrada flotando como huérfanas en el libro de órdenes.
* **Blindaje:** `TradeManager` detecta de forma atómica la desaparición de la posición en la cuenta afectada y ejecuta inmediatamente `cancel_all_orders_for_symbol(symbol)` restringido estrictamente a ese `account_id`, liberando el margen y enviando una alerta detallada a Telegram.

---

## 5. Protocolo de Emergencia: Kill-Switch Aislado por Cuenta

Procedimiento de desconexión y apagado de emergencia granular (`emergency_close_account`):

1. **Cancelación Total:** Cancela el 100% de órdenes límite pendientes pertenecientes a la cuenta.
2. **Cierre a Mercado:** Cierra a mercado todas las posiciones abiertas en el exchange correspondientes a la cuenta.
3. **Congelamiento Preventivo:** Deshabilita la cuenta en la configuración (`enabled: false`) impidiendo que el motor asigne nuevas señales a este cliente.
4. **Endpoint Seguro:** Disponible mediante `POST /api/v1/accounts/{account_id}/emergency-close` (protegido por token JWT administrativo).
5. **Aislamiento Total:** El apagado de emergencia de una cuenta (ej. `cliente_2`) no altera bajo ninguna circunstancia las posiciones ni las órdenes de `primary` ni de ningún otro cliente.

---

## 6. Procedimiento de Onboarding de Nuevas Cuentas

Para incorporar un nuevo cliente o subcuenta de forma segura:

1. **Vía API / OnboardingModal:** Enviar solicitud `POST /api/v1/accounts` con `account_id`, `account_label`, `api_key` y `api_secret`.
2. El sistema cifra automáticamente las credenciales con AES-256 Fernet antes de persistirlas en disco.
3. `AccountManager` valida la conectividad llamando a `get_wallet_balance()` contra el exchange.
4. Tras superar la prueba en vivo, la cuenta entra en el pool de despacho concurrente y los centinelas inician su ciclo de supervisión en el siguiente intervalo de 30 segundos.

---

## 7. Certificación QA Oficial (38/38 Pruebas Aprobadas)

Toda la arquitectura multi-cuenta y sus mecanismos de resiliencia están certificados al 100% en el archivo de pruebas:

```powershell
pytest C:\Slingshot\engine\tests\test_multi_account_advanced_security_and_resilience.py -v
```

*Resultado certificado:* **38/38 PASSED (100%)** cubriendo cifrado, rotación de claves, despacho concurrente, aislamiento de riesgo, tolerancia a fallos, deduplicación atómica, purga de órdenes huérfanas y el sentinela SOP-59.
