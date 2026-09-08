"""
engine/workers/tradfi_scanner.py ?" EscAner Cuantitativo TradFi para FTMO v19.0
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
    """EscAner asA-ncrono para mercados tradicionales en FTMO."""
    
    def __init__(self):
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.interval = "15m"
        
    def start(self):
        logger.info("dY?>,? [TRADFI_SCANNER] Iniciando escAner institucional TradFi (XAUUSD, US100, US30, GBPUSD)...")
        self._task = asyncio.create_task(self._scan_loop())
        
    def stop(self):
        logger.info("dY?>,? [TRADFI_SCANNER] Deteniendo escAner TradFi...")
        self._stop_event.set()
        
    async def _scan_loop(self):
        while not self._stop_event.is_set():
            try:
                await self._perform_scan()
            except Exception as e:
                logger.error(f"?O [TRADFI_SCANNER] Error en ciclo de escaneo: {e}")
            await asyncio.sleep(45) # Escaneo cada 45 segundos
            
    async def _perform_scan(self):
        candidates = []
        
        for symbol, spec in TRADFI_ASSETS_CONFIG.items():
            try:
                # [SOP-67 TIER-A FILTER & PODA INSTITUCIONAL]
                if spec.get("tier") == "EXCLUDED" or not spec.get("enabled", True):
                    continue
                df = await tradfi_provider.get_candles(symbol, interval=self.interval, limit=100)
                if df is None or len(df) < 50:
                    continue
                    
                current_price = float(df["close"].iloc[-1])
                c_high = float(df["high"].iloc[-1])
                c_low = float(df["low"].iloc[-1])
                atr_val = float(df["atr"].iloc[-1]) if "atr" in df.columns else (current_price * 0.002)
                ema50 = float(df["ema50"].iloc[-1])
                ema200 = float(df["ema200"].iloc[-1])
                
                # IdentificaciA3n de Swings OTE (20 velas recientes)
                lookback = df.iloc[-20:]
                swing_high = float(lookback["high"].max())
                swing_low = float(lookback["low"].min())
                swing_range = swing_high - swing_low
                
                if swing_range <= (atr_val * 0.5):
                    continue
                    
                # [SOP-29 SESSION KILLZONE GATE]
                # Indices y Forex TradFi solo operan en Killzones de Alta Liquidez (Londres 07-10 UTC y NY 12-18 UTC)
                now_utc = datetime.now(timezone.utc)
                hour = now_utc.hour
                is_tradfi_killzone = (7 <= hour <= 10) or (12 <= hour <= 18)
                
                # Evaluar Sesgo Institucional
                is_bull = current_price > ema50 and ema50 > ema200
                is_bear = current_price < ema50 and ema50 < ema200
                
                direction = "LONG" if is_bull else "SHORT" if is_bear else ("LONG" if current_price >= ema50 else "SHORT")

                # [SOP-68 VETO INSTITUCIONAL ORO: LONG-ONLY]
                if "XAU" in symbol and direction != "LONG":
                    continue
                    
                if direction == "LONG":
                    optimal_entry = swing_high - (swing_range * 0.618)
                    stop_loss = swing_low - (atr_val * 0.2)
                    dist = abs(optimal_entry - stop_loss)
                    be_price = optimal_entry + (dist * 1.0)
                    tp1 = optimal_entry + (dist * 1.3)
                    tp2 = optimal_entry + (dist * 2.5)
                    tp3 = optimal_entry + (dist * 4.0)
                else:
                    optimal_entry = swing_low + (swing_range * 0.618)
                    stop_loss = swing_high + (atr_val * 0.2)
                    dist = abs(optimal_entry - stop_loss)
                    be_price = optimal_entry - (dist * 1.0)
                    tp1 = optimal_entry - (dist * 1.3)
                    tp2 = optimal_entry - (dist * 2.5)
                    tp3 = optimal_entry - (dist * 4.0)
                    
                # CAlculo de Lotes MT5
                lot_info = ftmo_guardian.calculate_mt5_lots(symbol, optimal_entry, stop_loss)
                
                # Score de Confluencia Institucional
                score = 65
                checklist = []
                
                if (direction == "LONG" and current_price > ema200) or (direction == "SHORT" and current_price < ema200):
                    score += 15
                    checklist.append({"factor": "AlineaciA3n Macro EMA 200", "status": "CUMPLIDO", "detail": "DirecciA3n a favor de la tendencia mayor"})
                    
                if c_low <= optimal_entry <= c_high or abs(current_price - optimal_entry) / optimal_entry < 0.003:
                    score += 15
                    checklist.append({"factor": "Golden Pocket Fibonacci (61.8%)", "status": "CUMPLIDO", "detail": "Precio en zona OTE de alta probabilidad"})
                    
                checklist.append({"factor": "GestiA3n Acelerada FTMO (+1.0R / +1.3R)", "status": "CUMPLIDO", "detail": f"Lotes recomendados: {lot_info['lots']} Lots ($750 USD)"})
                
                # Precision dinamica de decimales por activo (SOP-65)
                d_prec = 5 if symbol in ["EURUSD", "GBPUSD"] else 3 if "JPY" in symbol else 2
                candidate = {
                    "asset": symbol,
                    "name": spec["name"],
                    "category": spec["category"],
                    "direction": direction,
                    "type": "TradFi SMC Setup",
                    "price": round(optimal_entry, d_prec),
                    "current_price": round(current_price, d_prec),
                    "stop_loss": round(stop_loss, d_prec),
                    "be_price": round(be_price, d_prec),
                    "tp1": round(tp1, d_prec),
                    "tp2": round(tp2, d_prec),
                    "tp3": round(tp3, d_prec),
                    "rr_ratio_tp3": 4.0,
                    "confluence_score": score,
                    "mt5_lots": lot_info["lots"],
                    "risk_usd": lot_info["risk_usd"],
                    "spread_usd": spec["spread_usd"],
                    "checklist": checklist,
                    "session_status": "KILLZONE ACTIVA (EJECUCIÓN PERMITIDA)" if is_tradfi_killzone else "STANDBY (MONITOREO FUERA DE KILLZONE)",
                    "is_killzone": is_tradfi_killzone,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                candidates.append(candidate)
                
                # [SOP-64 FTMO AUTO-DISPATCHER] Disparo Automatico a MT5 EXCLUSIVO dentro de Killzone para confluencia >= 75%
                if score >= 75 and is_tradfi_killzone and not ftmo_guardian.is_daily_lockout:
                    now_utc = datetime.now(timezone.utc)
                    if not ftmo_guardian.check_midnight_rollover_risk(now_utc.hour, now_utc.minute):
                        try:
                            from engine.execution.mt5_bridge import mt5_bridge
                            import MetaTrader5 as mt5
                            
                                                        # [SOP-19 / SWING NEWS SLIPPAGE SHIELD]
                            from engine.indicators.news_interceptor import news_interceptor
                            if news_interceptor.is_macro_news_blackout(now_utc, symbol):
                                logger.warning(f"dY>` [NEWS_SLIPPAGE_SHIELD] Orden {symbol} {direction} pospuesta por spread ensanchado de noticia macro.")
                                continue

                            sym_mt5 = symbol.replace("USDT", "USD")
                            if ".cash" not in sym_mt5 and any(idx in sym_mt5 for idx in ["US100", "US30", "US500", "GER40"]):
                                sym_mt5 = f"{sym_mt5}.cash"

                            # [CORRELATION GOVERNOR US100 / US30]
                            # Prevenir duplicaciA3n de riesgo direccional a 1.50% ($1,500 USD) en A-ndices correlacionados > 85%
                            if "US100" in sym_mt5 or "US30" in sym_mt5:
                                other_idx = "US30.cash" if "US100" in sym_mt5 else "US100.cash"
                                other_orders = mt5.orders_get(symbol=other_idx) or [] if mt5_bridge.connected else []
                                other_pos = mt5.positions_get(symbol=other_idx) or [] if mt5_bridge.connected else []
                                has_corr_conflict = False
                                for op in list(other_orders) + list(other_pos):
                                    op_type = getattr(op, "type", None)
                                    op_is_long = op_type in (0, 2) if op_type is not None else True
                                    if (direction == "LONG" and op_is_long) or (direction == "SHORT" and not op_is_long):
                                        has_corr_conflict = True
                                        break
                                if has_corr_conflict:
                                    logger.info(f"dY>` [CORRELATION_GOVERNOR] Veto de orden {sym_mt5} {direction}: ya existe exposiciA3n activa en {other_idx} en la misma direcciA3n. Riesgo protegido al 0.75%.")
                                    continue
                            has_order = False
                            if mt5_bridge.connected and not mt5_bridge.dry_run:
                                ex_orders = mt5.orders_get(symbol=sym_mt5) or []
                                ex_pos = mt5.positions_get(symbol=sym_mt5) or []
                                if len(ex_orders) > 0 or len(ex_pos) > 0:
                                    has_order = True
                            elif hasattr(self, "_active_orders") and sym_mt5 in self._active_orders:
                                has_order = True
                                    
                            open_pos = mt5_bridge.get_open_positions()
                            unprotected_symbols = set(p.get("symbol") for p in open_pos if float(p.get("profit", 0.0)) <= 0.0)
                            
                            if not has_order and len(unprotected_symbols) < 2:
                                res = mt5_bridge.place_limit_order(
                                    symbol=symbol,
                                    direction=direction,
                                    entry_price=candidate["price"],
                                    stop_loss=candidate["stop_loss"],
                                    tp1=candidate["tp1"],
                                    tp2=candidate["tp2"],
                                    tp3=candidate["tp3"],
                                    score=score
                                )
                                if res.get("success"):
                                    if not hasattr(self, "_active_orders"):
                                        self._active_orders = set()
                                    self._active_orders.add(sym_mt5)
                                    logger.info(f"s [TRADFI_AUTOLIMIT] Orden limite colocada en MT5 para {sym_mt5}: {direction} @ {candidate['price']}")
                                    try:
                                        from engine.router.telegram_dispatcher import telegram_dispatcher
                                        tele_sig = {
                                            "asset": symbol,
                                            "symbol": symbol,
                                            "direction": direction,
                                            "signal_type": direction,
                                            "type": direction,
                                            "price": candidate["price"],
                                            "stop_loss": candidate["stop_loss"],
                                            "tp1": candidate["tp1"],
                                            "tp2": candidate["tp2"],
                                            "tp3": candidate["tp3"],
                                            "confluence_score": score,
                                            "lots": candidate["mt5_lots"],
                                            "risk_usd": candidate["risk_usd"],
                                            "action": "AUTO_LIMIT_PLACED_MT5"
                                        }
                                        asyncio.create_task(telegram_dispatcher.send_signal_alert(tele_sig, account_profile="FTMO_100K"))
                                    except Exception:
                                        pass
                        except Exception as exec_err:
                            logger.error(f"[TRADFI_AUTOLIMIT] Error en auto-limite MT5 para {symbol}: {exec_err}")
                
            except Exception as e:
                logger.error(f"[TRADFI_SCANNER] Error procesando {symbol}: {e}")
                
        # Guardar en Store
        await store.save_scanner_opportunities("tradfi", candidates)
        logger.info(f"dY?>,? [TRADFI_SCANNER] {len(candidates)} setups TradFi FTMO actualizados en memoria.")

tradfi_scanner = TradFiScanner()


