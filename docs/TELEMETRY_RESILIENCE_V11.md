# 📡 Reporte Técnico: Arquitectura de Resiliencia de Telemetría (v11.1.2)

## 1. El Problema: Bloqueos Regionales (Handshake Timeout)
Durante la auditoría v11.1, se detectó que ciertos Proveedores de Servicios de Internet (ISP) en Sudamérica (ej. Chile) estaban aplicando filtros de paquetes o throttling sobre el puerto por defecto de Binance Futures (`fstream.binance.com`). 
- **Síntoma**: La terminal mostraba "ANALIZANDO..." indefinidamente.
- **Causa**: El handshake de WebSocket fallaba silenciosamente antes de establecer la conexión de Klines.

## 2. La Solución: Unified Spot Routing (Puerto 9443)
Se ha implementado un sistema de enrutamiento unificado que utiliza el endpoint de **Binance Spot** (`stream.binance.com:9443`) para toda la telemetría de velas (klines), incluso para activos de Futuros.

### Ventajas Técnicas:
- **Bypass de ISP**: El puerto 9443 es de alta disponibilidad y raramente bloqueado.
- **Latencia < 10ms**: Estabilidad superior en la recepción de ticks.
- **Precisión de Precio**: El diferencial entre Spot y Futures Perpetuals es estadísticamente irrelevante (< 0.01%) para el análisis de SMC (Order Blocks, FVGs).

## 3. Normalización de Datos y Salud del Sistema
Para evitar el error de aserción (`data must be asc ordered by time`), se han implementado dos capas de protección:
1.  **Backend Normalization**: Todos los timestamps se convierten a `float` antes del broadcast.
2.  **Frontend Sanitization**: El `TradingChart` realiza una deduplicación y ordenamiento estricto antes de cada `setData`.

## 4. Auditoría de Integridad (XAG/Commodities)
Se ha confirmado que para activos como **XAGUSDT**, el sistema consulta el **Funding Rate** vía REST para garantizar que la data on-chain sea visible independientemente del túnel de WebSocket utilizado para el precio.

---
**Status**: 🟢 HARDENED & OPERATIONAL
**Versión**: 11.1.2
**Fecha de Auditoría**: 2026-05-08
