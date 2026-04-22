import httpx
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from engine.core.logger import logger
from engine.api.config import settings

class OnChainSentinel:
    """
    On-Chain Sentinel v5.7.155 Master Gold — The Whale & Liquidity Watcher.
    Monitorea Open Interest, Funding Rates y grandes flujos de capital hacia exchanges.
    """

    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol.upper()

        self._last_oi: Optional[float] = None
        self._oi_delta_pct: float = 0.0
        self._funding_rate: float = 0.0
        self._whale_alerts: List[Dict] = []
        self._onchain_bias: str = "NEUTRAL"
        self._last_check_ts: float = 0.0
        
        # Whale Alert API (Tier Gratuito)
        self.whale_api_url = "https://api.whale-alert.io/v1"
        self.api_key = getattr(settings, "WHALE_ALERT_API_KEY", "")

    async def refresh(self, 
                      current_price: float, 
                      market_regime: str, 
                      avg_tick_volume: float = 10.0,
                      news_sentiment: Optional[str] = "NEUTRAL") -> Dict:
        """
        Refresca métricas on-chain (OI, Funding) y trackea ballenas.
        Se ejecuta idealmente cada 30 segundos (v5.7.15 Force Refresh).
        avg_tick_volume: SMA_20 del volumen por tick para el trigger dinámico.
        news_sentiment: Multiplicador de riesgo basado en [NEWS-WORKER].
        """
        self._news_multiplier = 2.0 if news_sentiment == "BEARISH" else 1.0
        # Dynamic Whale Trigger (300% SMA_20)
        self._whale_threshold = max(avg_tick_volume * 3.0, 1000000.0) # Mínimo $1M institucional
        
        now_ts = datetime.now().timestamp()
        
        # 1. Fetch Open Interest desde Binance Futures REST (v8.5.6 Optimized)
        try:
            # Skip check para activos sin futuros
            if self.symbol in ["PAXGUSDT", "EURUSDT", "USDCUSDT"]:
                raise ValueError("Skip On-Chain: Spot Asset")

            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                oi_resp = await client.get(
                    f"https://fapi.binance.com/fapi/v1/openInterest",
                    params={"symbol": self.symbol}
                )
                fr_resp = await client.get(
                    f"https://fapi.binance.com/fapi/v1/fundingRate",
                    params={"symbol": self.symbol, "limit": 1}
                )

        now_ts = datetime.now().timestamp()
        
        # 1. Fetch Open Interest desde Binance Futures REST (v8.5.6 Optimized)
        try:
            # Skip check para activos sin futuros
            if self.symbol in ["PAXGUSDT", "EURUSDT", "USDCUSDT"]:
                raise ValueError("Skip On-Chain: Spot Asset")

            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                oi_resp = await client.get(
                    f"https://fapi.binance.com/fapi/v1/openInterest",
                    params={"symbol": self.symbol}
                )
                fr_resp = await client.get(
                    f"https://fapi.binance.com/fapi/v1/fundingRate",
                    params={"symbol": self.symbol, "limit": 1}
                )

            current_oi = 0.0
            
            if oi_resp.status_code == 200:
                oi_json = oi_resp.json()
                current_oi = float(oi_json.get("openInterest", 0))

            if fr_resp.status_code == 200:
                fr_json = fr_resp.json()
                if isinstance(fr_json, list) and len(fr_json) > 0:
                    self._funding_rate = float(fr_json[-1].get("fundingRate", 0)) * 100
        except Exception as e:
            logger.debug(f"[ON-CHAIN] Network Error for {self.symbol}: {e}")
            current_oi = self._last_oi if self._last_oi else 0.0

        # --- 2. Hidratación Histórica (SESSIÓN vs TICK) ---
        # [AUDITORIA v8.5.8] Para evitar el "0.000000%" perpetuo al iniciar, 
        # consultamos el historial de 1h de Binance si no tenemos referencia.
        if not hasattr(self, "_reference_oi") or self._reference_oi is None:
            try:
                hist_oi = await self._fetch_historical_oi()
                if hist_oi > 0:
                    self._reference_oi = hist_oi
                    self._reference_ts = now_ts - 3600
                    logger.info(f"[ON-CHAIN] ⚓ Punto de referencia histórico cargado para {self.symbol}: {hist_oi:.0f}")
                else:
                    self._reference_oi = current_oi
                    self._reference_ts = now_ts
            except:
                self._reference_oi = current_oi
                self._reference_ts = now_ts
        
        # Rotación horaria del punto de referencia
        if (now_ts - self._reference_ts > 3600):
            self._reference_oi = current_oi
            self._reference_ts = now_ts
            logger.info(f"[ON-CHAIN] ⚓ Rotación horaria de referencia para {self.symbol}")

        # Delta de la Sesión (mucho más representativo)
        if self._reference_oi > 0:
            self._oi_delta_pct = ((current_oi - self._reference_oi) / self._reference_oi) * 100
        else:
            self._oi_delta_pct = 0.0

        self._last_oi = current_oi
        self._last_check_ts = now_ts

        # 3. Whale Tracker (Dynamic Trigger 300% SMA_20)
        await self._fetch_whale_alerts(min_value=self._whale_threshold)

        # 4. Determinar On-Chain Bias (Lógica Institucional)
        is_ranging = market_regime in ("RANGING", "ACCUMULATION", "CHOPPY")
        oi_rising = self._oi_delta_pct > 0.5 # Sensibilidad ajustada para Delta de Sesión
        
        if oi_rising and is_ranging:
            self._onchain_bias = "INSTITUTIONAL_ACCUMULATION"
        elif any(alert.get('inflow_to_exchange') for alert in self._whale_alerts):
            self._onchain_bias = "BEARISH_INFLOW"
        elif self._funding_rate > 0.01 / self._news_multiplier:
            self._onchain_bias = "OVERLEVERAGED"
        else:
            self._onchain_bias = "NEUTRAL"

        # [ONCHAIN_DEBUG] | Last Data: SYNCED
        debug_time = datetime.fromtimestamp(self._last_check_ts).strftime('%H:%M:%S')
        logger.info(f"[ON-CHAIN] {self.symbol} | OI: {current_oi:.0f} | Δ(Session): {self._oi_delta_pct:.4f}% | FR: {self._funding_rate:.5f}% | Bias: {self._onchain_bias}")
        
        return self.get_summary()

    async def _fetch_historical_oi(self) -> float:
        """Fetch OI de hace 1 hora desde el endpoint de datos de Binance."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = "https://fapi.binance.com/futures/data/openInterestHist"
                params = {"symbol": self.symbol, "period": "1h", "limit": 2}
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if len(data) >= 1:
                        return float(data[0].get("sumOpenInterest", 0))
        except Exception as e:
            logger.debug(f"[ON-CHAIN] Error fetching historical OI: {e}")
        return 0.0
        return self.get_summary()

    async def _fetch_whale_alerts(self, min_value: float = 10000000):
        """Consume la API de Whale Alert o usa un scraper ligero como fallback."""
        if not self.api_key:
            return # Tier gratuito requiere API Key para resultados precisos

        try:
            # Parámetros: movimientos de la última hora, valor > $10M
            start_ts = int(datetime.now().timestamp()) - 3600
            url = f"{self.whale_api_url}/transactions?api_key={self.api_key}&min_value={int(min_value)}&start={start_ts}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    transactions = data.get("transactions", [])
                    
                    self._whale_alerts = []
                    for tx in transactions:
                        inflow = "exchange" in str(tx.get("to", {}).get("owner_type", "")).lower()
                        self._whale_alerts.append({
                            "amount": tx.get("amount_usd"),
                            "symbol": tx.get("symbol"),
                            "from": tx.get("from", {}).get("owner", "unknown"),
                            "to": tx.get("to", {}).get("owner", "unknown"),
                            "inflow_to_exchange": inflow,
                            "timestamp": tx.get("timestamp")
                        })
        except Exception as e:
            logger.warning(f"[ON-CHAIN] Whale Alert API Fallida: {e}")

    def get_summary(self) -> Dict:
        """Retorna el estado consolidado del Centinela On-Chain."""
        return {
            "symbol": self.symbol,
            "oi_delta_pct": round(self._oi_delta_pct, 6),
            "funding_rate": round(self._funding_rate, 5),
            "whale_alerts_count": len(self._whale_alerts),
            "last_whale_alert": self._whale_alerts[0] if self._whale_alerts else None,
            "onchain_bias": self._onchain_bias,
            "news_risk_multiplier": self._news_multiplier,
            "ts": self._last_check_ts
        }

    async def close(self):
        """Placeholder para compatibilidad con el ciclo de vida del broadcaster."""
        pass
