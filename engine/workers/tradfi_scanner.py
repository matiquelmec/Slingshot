"""
engine/workers/tradfi_scanner.py — Escáner Cuantitativo TradFi para FTMO v19.0
==============================================================================
Vigila y analiza los 4 activos institucionales de FTMO:
- XAUUSD (Gold Spot)
- US100 (Nasdaq 100)
- US30 (Dow Jones 30)
- GBPUSD (Forex)

Aplica el motor de confluencia SMC, OTE Fibonacci y Fast BE a +1.0R / TP1 a +1.3R (70%).
"""
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from engine.core.logger import logger
from engine.core.store import store
from engine.indicators.tradfi_provider import tradfi_provider, TRADFI_ASSETS_CONFIG
from engine.risk.ftmo_guardian import ftmo_guardian

class TradFiScanner:
    """Escáner asíncrono para mercados tradicionales en FTMO."""
    
    def __init__(self):
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.interval = "15m"
        
    def start(self):
        logger.info("🏛️ [TRADFI_SCANNER] Iniciando escáner institucional TradFi (XAUUSD, US100, US30, GBPUSD)...")
        self._task = asyncio.create_task(self._scan_loop())
        
    def stop(self):
        logger.info("🏛️ [TRADFI_SCANNER] Deteniendo escáner TradFi...")
        self._stop_event.set()
        
    async def _scan_loop(self):
        while not self._stop_event.is_set():
            try:
                await self._perform_scan()
            except Exception as e:
                logger.error(f"❌ [TRADFI_SCANNER] Error en ciclo de escaneo: {e}")
            await asyncio.sleep(45) # Escaneo cada 45 segundos
            
    async def _perform_scan(self):
        candidates = []
        
        for symbol, spec in TRADFI_ASSETS_CONFIG.items():
            try:
                df = await tradfi_provider.get_candles(symbol, interval=self.interval, limit=100)
                if df is None or len(df) < 50:
                    continue
                    
                current_price = float(df["close"].iloc[-1])
                c_high = float(df["high"].iloc[-1])
                c_low = float(df["low"].iloc[-1])
                atr_val = float(df["atr"].iloc[-1]) if "atr" in df.columns else (current_price * 0.002)
                ema50 = float(df["ema50"].iloc[-1])
                ema200 = float(df["ema200"].iloc[-1])
                
                # Identificación de Swings OTE (20 velas recientes)
                lookback = df.iloc[-20:]
                swing_high = float(lookback["high"].max())
                swing_low = float(lookback["low"].min())
                swing_range = swing_high - swing_low
                
                if swing_range <= (atr_val * 0.5):
                    continue
                    
                # Evaluar Sesgo Institucional
                is_bull = current_price > ema50 and ema50 > ema200
                is_bear = current_price < ema50 and ema50 < ema200
                
                direction = "LONG" if is_bull else "SHORT" if is_bear else None
                if not direction:
                    continue
                    
                if direction == "LONG":
                    optimal_entry = swing_high - (swing_range * 0.618)
                    stop_loss = swing_low - (atr_val * 0.2)
                    dist = abs(optimal_entry - stop_loss)
                    be_price = optimal_entry + (dist * 1.0)
                    tp1 = optimal_entry + (dist * 1.3)
                    tp2 = optimal_entry + (dist * 2.0)
                    tp3 = optimal_entry + (dist * 3.5)
                else:
                    optimal_entry = swing_low + (swing_range * 0.618)
                    stop_loss = swing_high + (atr_val * 0.2)
                    dist = abs(optimal_entry - stop_loss)
                    be_price = optimal_entry - (dist * 1.0)
                    tp1 = optimal_entry - (dist * 1.3)
                    tp2 = optimal_entry - (dist * 2.0)
                    tp3 = optimal_entry - (dist * 3.5)
                    
                # Cálculo de Lotes MT5
                lot_info = ftmo_guardian.calculate_mt5_lots(symbol, optimal_entry, stop_loss)
                
                # Score de Confluencia Institucional
                score = 65
                checklist = []
                
                if (direction == "LONG" and current_price > ema200) or (direction == "SHORT" and current_price < ema200):
                    score += 15
                    checklist.append({"factor": "Alineación Macro EMA 200", "status": "CUMPLIDO", "detail": "Dirección a favor de la tendencia mayor"})
                    
                if c_low <= optimal_entry <= c_high or abs(current_price - optimal_entry) / optimal_entry < 0.003:
                    score += 15
                    checklist.append({"factor": "Golden Pocket Fibonacci (61.8%)", "status": "CUMPLIDO", "detail": "Precio en zona OTE de alta probabilidad"})
                    
                checklist.append({"factor": "Gestión Acelerada FTMO (+1.0R / +1.3R)", "status": "CUMPLIDO", "detail": f"Lotes recomendados: {lot_info['lots']} Lots ($750 USD)"})
                
                candidate = {
                    "asset": symbol,
                    "name": spec["name"],
                    "category": spec["category"],
                    "direction": direction,
                    "type": "TradFi SMC Setup",
                    "price": round(optimal_entry, 4 if "GBP" in symbol else 2),
                    "current_price": round(current_price, 4 if "GBP" in symbol else 2),
                    "stop_loss": round(stop_loss, 4 if "GBP" in symbol else 2),
                    "be_price": round(be_price, 4 if "GBP" in symbol else 2),
                    "tp1": round(tp1, 4 if "GBP" in symbol else 2),
                    "tp2": round(tp2, 4 if "GBP" in symbol else 2),
                    "tp3": round(tp3, 4 if "GBP" in symbol else 2),
                    "rr_ratio_tp3": 3.5,
                    "confluence_score": score,
                    "mt5_lots": lot_info["lots"],
                    "risk_usd": lot_info["risk_usd"],
                    "spread_usd": spec["spread_usd"],
                    "checklist": checklist,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                candidates.append(candidate)
                
            except Exception as e:
                logger.error(f"[TRADFI_SCANNER] Error procesando {symbol}: {e}")
                
        # Guardar en Store
        await store.save_scanner_opportunities("tradfi", candidates)
        logger.info(f"🏛️ [TRADFI_SCANNER] {len(candidates)} setups TradFi FTMO actualizados en memoria.")

tradfi_scanner = TradFiScanner()
