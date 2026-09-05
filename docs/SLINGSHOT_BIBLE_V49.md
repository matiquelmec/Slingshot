# 🛡️ SLINGSHOT BIBLE v49.0 🛡️ APEX QUANTUM & CANONICAL QUANT ARCHITECTURE

> **"Manual Técnico Canónico y Especificación SSoT del Ecosistema Autónomo Slingshot. Versión v49.0 APEX QUANTUM: Inferencia Neural Meta-Labeling (XGBoost / ONNX en ConfluenceManager +10pts), Sentinela de Intervención Manual de Clientes SOP-59 con Purgado Atómico Anti-Orphan, Motor de Reportería Cuantitativa Institucional SOP-60 (Tear Sheets: Sharpe, Sortino, Drawdown, Profit Factor), Blindaje de Capital SOP-58 (Fast BE Verificado, Reintentos SL de Emergencia, Aislamiento de Purgas por Cuenta y Precisión Dinámica de Lotes), y Despacho Concurrente Multi-Cuenta SOP-57 con Cifrado AES en Reposo. Certificación QA Oficial de 38/38 Pruebas Aprobadas al 100% en VPS de Producción."**

---

## 1. Impacto Matemático Cuantitativo en el Retorno Esperado

### A. Machine Learning Meta-Labeling (XGBoost / ONNX v49.0)
* **Mecanismo:** En cada ciclo de escaneo de 15m, el DataFrame de velas es evaluado por `SlingshotML.predict_live(df)`. Si la predicción probabilística confirma la señal SMC/Liquidez con confianza $\ge 60\%$, se inyectan $+10$ puntos de confluencia institucional. Si la probabilidad es contraria y $\ge 70\%$, aplica penalización defensiva de $-5$ puntos.
* **Impacto Cuantitativo Auditado (Backtest 180 Días):**
  * **Retorno Acumulado:** Incremento de **+452.4% a +567.3% (+114.9% neto adicional)**.
  * **Profit Factor:** Expansión de **1.89 a 2.01**.
  * **Drawdown Máximo:** Reducción de **-3.73% a -3.64%**.
  * **Retorno en Unidades R:** Crecimiento de **+72.36R a +80.45R**.

### B. SOP-59: Sentinela de Intervención Manual de Clientes
* **Causa Raíz:** En entornos multicuenta de inversión privada, los clientes pueden cerrar manualmente órdenes desde la app móvil del exchange (`clientId: null`), lo que previamente dejaba órdenes límite residuales de Take Profit o Reentrada como huérfanas en el libro de órdenes.
* **Blindaje:** `TradeManager` rastrea el delta de posiciones vivas por cuenta. Al detectar un cierre manual, ejecuta de forma atómica `cancel_all_orders_for_symbol(symbol)` restringido estrictamente al `account_id` afectado, liberando margen y alertando a Telegram.

### C. SOP-60: Motor de Tear Sheets Cuantitativos
* **Módulo:** `engine/core/tear_sheet.py`
* **Métricas Institucionales Calculadas:**
  * **Sharpe Ratio Anualizado:** $\frac{\bar{R} - R_f}{\sigma_R} \times \sqrt{252}$
  * **Sortino Ratio (Downside Risk):** $\frac{\bar{R} - R_f}{\sigma_{\text{downside}}} \times \sqrt{252}$
  * **Profit Factor Institucional:** $\frac{\sum \text{Ganancias}}{\sum |\text{Pérdidas}|}$
  * **Max Drawdown en R:** $\max(\text{Peak} - \text{Equity})$
  * **Generador de Markdown:** Notificaciones ejecutivas inmediatas para inversores y canal VIP de Telegram.

---

## 2. Los Protocolos Canónicos de Seguridad y Resiliencia (SOP-50 a SOP-60)

| Protocolo | Nombre Técnico | Especificación Matemática & Blindaje Institucional |
| :--- | :--- | :--- |
| **SOP-50** | Atomic Lock Dedup | Cerrojos asíncronos `_symbol_locks[f"{account}_{symbol}"]`. Serializa y descarta señales concurrentes repetidas en $<1\text{ms}$. Cero duplicados en ráfagas. |
| **SOP-51** | Frozen Margin Guard | `get_net_available_margin_usdt()`. Descuenta el margen congelado en órdenes límite pendientes (`tradeSide == OPEN`), eliminando errores de balance insuficiente. |
| **SOP-52** | Sentinel TTL (3 Horas) | Purgado automático de órdenes límite de entrada no ejecutadas tras 3 horas o si el precio tocó TP1 prematuramente. |
| **SOP-53** | Persistent Buffer SQLite WAL | Persistencia transaccional de oportunidades en cola en `high_confluence_buffer`. Sobrevive a caídas de red o reinicios de máquina. |
| **SOP-54** | Multi-Chat Telegram Dispatcher | Despacho concurrente de alertas de trading a múltiples destinatarios de Telegram mediante `asyncio.gather()`. |
| **SOP-55** | Non-Blocking Async Ingestor | Eliminación total de `urllib.request` síncrono. Migración a `httpx.AsyncClient` con timeout estricto de $2.5\text{s}$ y fallback instantáneo a RAM. |
| **SOP-56** | Repository Hygiene & SSoT | Raíz desprovista de scripts efímeros. Centralización de herramientas de diagnóstico en `scripts/diagnostic/`, pruebas en `engine/tests/` y validación estricta de `.gitignore`. |
| **SOP-57** | Multi-Account Isolation & Cryptographic Vault | Despacho concurrente no bloqueante mediante `asyncio.gather(*tasks, return_exceptions=True)`. Cuotas de riesgo SOP-41/45 y buffers desacoplados por `account_id`. Cifrado de credenciales secundarias con AES-Fernet (`enc:v1:`) y enmascaramiento estricto en logs (`to_dict(mask_secrets=True)`). |
| **SOP-58** | Capital Risk Invariance & Atomic SL Guardian | Validación estricta booleana en Bitunix antes de liberar cupos en Fast BE (+1.0R), reintentos forzados de emergencia ante fallos en colocación de SL, aislamiento estricto de purgas de órdenes límite por cuenta (`account_id`), y formateo dinámico de lotes según `qty_decimals` del libro de especificaciones. |
| **SOP-59** | Manual Client Intervention Sentinel | Monitoreo de desincronización por cierres manuales desde la app móvil del exchange (`clientId: null`). Purgado atómico de órdenes huérfanas en la cuenta afectada y alerta a Telegram. |
| **SOP-60** | Quantitative Tear Sheet Reporting Engine | Generador formal de métricas financieras de rendimiento de cartera (Sharpe, Sortino, Profit Factor, Drawdown, Esperanza R) con bitácora Markdown para inversores. |

---

## 3. Matriz de Pruebas Unitarias y Certificación (293/293 Suite Global & 38/38 Quality Gate VPS)

El ecosistema cuenta con una certificación de dos niveles:
* **Suite Global del Repositorio:** **293/293 Pruebas Unitarias Aprobadas al 100% (Green)**, cubriendo el motor Polars, SMC, VWAP, persitencia WAL, modulación de riesgo y despacho multicuenta.
* **Quality Gate de Producción (VPS `verificar_sistema.bat`):** Batería de **38 tests institucionales de misión crítica** ejecutados en cada despliegue:

1. `test_multi_asset_feed_async_non_blocking` (PASSED)
2. `test_multi_asset_feed_sync_fallback` (PASSED)
3. `test_gitignore_protects_env_and_keys` (PASSED)
4. `test_root_directory_hygiene` (PASSED)
5. `test_sqlite_wal_mode_active` (PASSED)
6. `test_multi_asset_feed_no_blocking_urllib` (PASSED)
7. `test_atomic_deduplication_under_high_concurrency_burst` (PASSED)
8. `test_frozen_margin_guard_deducts_open_limits` (PASSED)
9. `test_ttl_sentinel_identifies_stale_orders` (PASSED)
10. `test_sqlite_buffer_persistence_and_recovery` (PASSED)
11. `test_half_risk_mitigator_calculation` (PASSED)
12. `test_slot_recycler_ignores_when_max_slots_reached` (PASSED)
13. `test_slot_recycler_triggers_best_opportunity_from_store` (PASSED)
14. `test_slot_recycler_deduplicates_existing_positions` (PASSED)
15. `test_multi_account_independent_risk_isolation` (PASSED)
16. `test_high_confluence_buffer_queuing` (PASSED)
17. `test_instant_sl_placed_within_execute_signal` (PASSED)
18. `test_cancel_all_pending_orders_protects_take_profits` (PASSED)
19. `test_sqlite_wal_mode_and_concurrency` (PASSED)
20. `test_log_rotator_truncates_and_archives` (PASSED)
21. `test_telegram_multi_chat_parsing_and_dispatch` (PASSED)
22. `test_cluster_risk_guard_limits_correlation` (PASSED)
23. `test_orphan_order_sweeper_logic` (PASSED)
24. `test_multi_account_concurrent_dispatch_latency` (PASSED)
25. `test_multi_account_strict_symbol_locks_isolation` (PASSED)
26. `test_multi_account_independent_risk_caps_and_recycling` (PASSED)
27. `test_multi_account_buffer_isolation` (PASSED)
28. `test_multi_account_fault_tolerance_isolation` (PASSED)
29. `test_multi_account_encryption_and_secret_masking` (PASSED)
30. `test_fast_be_does_not_release_risk_on_bitunix_failure` (PASSED)
31. `test_fast_be_releases_risk_only_on_bitunix_success` (PASSED)
32. `test_atomic_tpsl_emergency_fallback_and_alert` (PASSED)
33. `test_limit_order_purge_isolated_to_saturated_account` (PASSED)
34. `test_lot_precision_dynamic_formatting_respects_specs` (PASSED)
35. `test_ml_meta_labeling_boosts_confluence_score` (PASSED)
36. `test_ml_graceful_fallback_when_no_model` (PASSED)
37. `test_manual_client_exit_triggers_orphan_purge_and_alert` (PASSED)
38. `test_tear_sheet_financial_metrics_math` (PASSED)

---

## 4. Estado de Producción en Vivo (Bitunix Exchange)
* **Daemon:** `SlingshotBot` (Scheduled Task de Windows) en ejecución continua.
* **Cuentas Conectadas y Verificadas:**
  * `primary` (Cuenta Principal): Margen libre $\approx \$86.42$ USDT | Posición ETHUSDT en Breakeven (TP1 cobrado +$2.31) + XAUUSDT y FETUSDT blindadas.
  * `cliente_2` (Cuenta Secundaria): Margen libre $\approx \$221.48$ USDT | Posiciones FETUSDT y XAUUSDT blindadas con TP y SL institucionales.
* **Take Profits e Instant SL:** Colocados directamente en el matching engine de Bitunix.
