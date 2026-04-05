import httpx
import asyncio
from engine.core.logger import logger

class PriceOracleGuard:
    """
    Price Oracle Guard v5.0 (Maturity Level 5).
    Protege el sistema contra anomalías de WebSocket (Flash Crashes locales, lag de sensor o manipulación de datos).
    Valida el precio del WebSocket contra el REST API de Binance en cada ciclo crítico.
    """
    def __init__(self, max_drift_pct: float = 0.005): # 0.5% drift máximo permitido
        self.max_drift_pct = max_drift_pct
        self.client = httpx.AsyncClient(timeout=2.0)

    async def validate(self, symbol: str, ws_price: float) -> tuple[bool, float, float]:
        """
        Compara el precio del WS contra la REST API.
        Retorna (es_valido, drift_pct, rest_price).
        """
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}"
            response = await self.client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"[ORACLE] ⚠️ Fallo al conectar con Binance REST para {symbol}. Saltando validación.")
                return True, 0.0, ws_price # Fail-safe: Si falla el oráculo, confiamos en el WS (para no matar la operativa)

            data = response.json()
            rest_price = float(data.get("price", 0))
            
            if rest_price <= 0:
                return True, 0.0, ws_price

            drift_pct = abs(ws_price - rest_price) / rest_price
            is_valid = drift_pct <= self.max_drift_pct
            
            if not is_valid:
                logger.error(f"[ORACLE] 🚨 ANOMALÍA DETECTADA en {symbol}: WS=${ws_price} vs REST=${rest_price} (Drift: {drift_pct*100:.2f}%)")
            
            return is_valid, drift_pct, rest_price

        except Exception as e:
            logger.error(f"[ORACLE] Error en validación: {e}")
            return True, 0.0, ws_price

# Instancia global
oracle_guard = PriceOracleGuard()
