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
        logger.info("📡 [TRADFI_SCANNER] Iniciando escáner institucional TradFi (XAUUSD, US100, US30, GBPUSD)...")
        self._task = asyncio.create_task(self._scan_loop())
        
    def stop(self):
        logger.info("📡 [TRADFI_SCANNER] Deteniendo escáner TradFi...")
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
                # [SOP-67 & SOP-154 TIER-A FILTER & PARIDAD 1:1]
                if spec.get("tier") == "EXCLUDED" or not spec.get("enabled", True):
                    continue
                tf = spec.get("optimal_timeframe", self.interval)
                archetype = spec.get("archetype", "IMPULSE_OTE_SMC")
                df_raw, data_source = await tradfi_provider.get_candles_with_meta(symbol, interval=tf, limit=250)
                if df_raw is None or len(df_raw) < 210:
                    continue

                from engine.indicators.tradfi_smc_engine import SISTER_ASSET_MAP, prepare_tradfi_features, evaluate_tradfi_bar, is_tradfi_killzone
                df_1d, _ = await tradfi_provider.get_candles_with_meta(symbol, interval="1d", limit=80)
                sis_sym = SISTER_ASSET_MAP.get(symbol)
                df_sis = None
                if sis_sym:
                    df_sis, _ = await tradfi_provider.get_candles_with_meta(sis_sym, interval=tf, limit=250)
                df = prepare_tradfi_features(df_raw, htf_1d_df=df_1d, sister_df=df_sis)
                if df.empty or len(df) < 210:
                    continue

                cost_rt = float(spec.get("spread_usd", 0.0)) / max(float(df["close"].iloc[-1]), 1e-9)
                setup = evaluate_tradfi_bar(
                    df,
                    idx=len(df) - 1,
                    symbol=symbol,
                    archetype=archetype,
                    long_only=bool(spec.get("long_only", False)),
                    cost_pct_rt=cost_rt,
                    max_spread_to_risk=0.08,
                )
                if setup is None:
                    continue

                direction = setup["direction"]
                optimal_entry = float(setup["price"])
                current_price = float(setup["current_price"])
                stop_loss = float(setup["stop_loss"])
                be_price = float(setup["be_price"])
                tp1 = float(setup["tp1"])
                tp2 = float(setup["tp2"])
                tp3 = float(setup["tp3"])
                score = int(setup["confluence_score"])
                checklist = list(setup["checklist"])
                is_tradfi_killzone = bool(setup["is_killzone"])

                # Cálculo de Lotes MT5 con Tier Weighting (SOP-156)
                tier_w = float(spec.get("tier_weight", 1.0))
                base_risk_usd = ftmo_guardian.current_equity * ftmo_guardian.current_config["risk_pct"] * tier_w
                lot_info = ftmo_guardian.calculate_mt5_lots(symbol, optimal_entry, stop_loss, risk_usd_override=base_risk_usd)
                checklist.append({"factor": "Gestión Acelerada FTMO (+1.0R / +1.3R)", "status": "CUMPLIDO", "detail": f"Lotes recomendados: {lot_info['lots']} Lots (${lot_info['risk_usd']:.0f} USD)"})

                # Precisión dinámica de decimales por activo (SOP-65)
                d_prec = 5 if symbol in ["EURUSD", "GBPUSD"] else 3 if ("JPY" in symbol or symbol == "XAGUSD") else 2
                candidate = {
                    "asset": symbol,
                    "name": spec["name"],
                    "category": spec["category"],
                    "direction": direction,
                    "type": f"TradFi {archetype}",
                    "price": round(optimal_entry, d_prec),
                    "current_price": round(current_price, d_prec),
                    "stop_loss": round(stop_loss, d_prec),
                    "be_price": round(be_price, d_prec),
                    "tp1": round(tp1, d_prec),
                    "tp2": round(tp2, d_prec),
                    "tp3": round(tp3, d_prec),
                    "rr_ratio_tp3": 3.8,
                    "confluence_score": score,
                    "mt5_lots": lot_info["lots"],
                    "risk_usd": lot_info["risk_usd"],
                    "spread_usd": spec["spread_usd"],
                    "checklist": checklist,
                    "session_status": "KILLZONE ACTIVA (EJECUCIÓN PERMITIDA)" if is_tradfi_killzone else "STANDBY (MONITOREO FUERA DE KILLZONE)",
                    "is_killzone": is_tradfi_killzone,
                    "data_source": data_source,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                # [SOP-92 PRE-NEWS PROTECTIVE SHIELD FOR OPEN POSITIONS]
                from engine.indicators.news_interceptor import news_interceptor
                from engine.execution.mt5_bridge import mt5_bridge
                now_utc = datetime.now(timezone.utc)

                # 1. Comprobar si hay evento High-Impact inminente (< 15 min) para proteger posiciones abiertas
                news_threat = news_interceptor.get_upcoming_event_threat(symbol, lookahead_mins=15)
                if news_threat:
                    mt5_bridge.apply_pre_news_protective_shield(symbol, news_threat.get("title", "HighImpactNews"))

                # 2. Comprobar si está activa la ventana post-noticia institucional
                from engine.indicators.post_news_sniper import post_news_sniper
                post_news_info = post_news_sniper.is_post_news_window_active(symbol, now=now_utc)
                if post_news_info:
                    post_setup = post_news_sniper.evaluate_post_news_setup(df, symbol, post_news_info)
                    if post_setup and post_setup.get("confluence_score", 0) >= 80:
                        candidate["type"] = "POST_NEWS_INSTITUTIONAL_SNIPER"
                        candidate["confluence_score"] = post_setup["confluence_score"]
                        candidate["direction"] = post_setup["direction"]
                        candidate["price"] = post_setup["price"]
                        candidate["stop_loss"] = post_setup["stop_loss"]
                        candidate["tp1"] = post_setup["tp1"]
                        candidate["tp2"] = post_setup["tp2"]
                        candidate["tp3"] = post_setup["tp3"]
                        candidate["checklist"].append({
                            "factor": f"Post-News Sniper ({post_news_info['event_title']})",
                            "status": "CUMPLIDO",
                            "detail": f"{post_news_info['elapsed_minutes']}m post-evento | OTE + FVG institucional"
                        })
                        score = post_setup["confluence_score"]

                candidates.append(candidate)
                
                # [SOP-64 & SOP-153 FTMO AUTO-DISPATCHER FAIL-CLOSED]
                # Solo despacha órdenes a MT5 si los datos provienen nativamente de MT5 (nunca Yahoo Finance)
                if (
                    data_source == "MT5_NATIVE"
                    and mt5_bridge.ensure_connected()
                    and score >= 75
                    and is_tradfi_killzone
                    and not ftmo_guardian.is_daily_lockout
                ):
                    if not ftmo_guardian.check_midnight_rollover_risk(now_utc.hour, now_utc.minute):
                        try:
                            import MetaTrader5 as mt5

                            # [SOP-92 DYNAMIC NEWS SLIPPAGE SHIELD]
                            if news_interceptor.is_macro_news_blackout(now_utc, symbol):
                                logger.warning(f"🛡️ [NEWS_SLIPPAGE_SHIELD SOP-92] Orden {symbol} {direction} pospuesta por ventana de noticia macro de alto impacto.")
                                continue

                            sym_mt5 = symbol.replace("USDT", "USD")
                            if ".cash" not in sym_mt5 and any(idx in sym_mt5 for idx in ["US100", "US30", "US500", "GER40"]):
                                sym_mt5 = f"{sym_mt5}.cash"

                            # [ANTI-CHURNING COOLDOWN SENTINEL]
                            # Bloquear reentradas durante 120 min si la última operación cerró en Stop Loss
                            if not hasattr(self, "_symbol_cooldowns"):
                                self._symbol_cooldowns = {}
                            if not hasattr(self, "_daily_loss_counts"):
                                self._daily_loss_counts = {}

                            now_ts = time.time()
                            # 1. Comprobar cooldown activo en memoria
                            if sym_mt5 in self._symbol_cooldowns:
                                cooldown_until = self._symbol_cooldowns[sym_mt5]
                                if now_ts < cooldown_until:
                                    rem_min = int((cooldown_until - now_ts) / 60)
                                    logger.info(f"⏳ [ANTI_CHURNING] {sym_mt5} en cooldown activo ({rem_min} min restantes tras Stop Loss). Orden omitida.")
                                    continue
                                else:
                                    del self._symbol_cooldowns[sym_mt5]

                            # 2. Sincronizar deals recientes desde MT5 para detectar cierres en SL y actualizar FTMO Guardian
                            if mt5_bridge.ensure_connected():
                                from datetime import timedelta
                                recent_deals = mt5.history_deals_get(datetime.now() - timedelta(hours=3), datetime.now()) or []
                                sl_hit_detected = False
                                if not hasattr(self, "_processed_deal_tickets"):
                                    self._processed_deal_tickets = set()

                                for d in reversed(recent_deals):
                                    if d.entry == 1 and d.ticket not in self._processed_deal_tickets:
                                        self._processed_deal_tickets.add(d.ticket)
                                        # Notificar a ftmo_guardian el outcome del deal
                                        ftmo_guardian.register_trade_outcome(is_win=(d.profit >= 0.0), symbol=d.symbol)

                                    if d.symbol == sym_mt5 and d.entry == 1: # Trade Exit de este activo
                                        if d.profit < 0.0:
                                            # Cierre con pérdida reciente
                                            sl_age = (datetime.now().timestamp() - d.time)
                                            if sl_age < 7200: # menos de 2 horas (120 min)
                                                self._symbol_cooldowns[sym_mt5] = now_ts + (7200 - sl_age)
                                                sl_hit_detected = True
                                                rem_min = int((7200 - sl_age) / 60)
                                                logger.warning(f"🛑 [ANTI_CHURNING] Detectado SL reciente en MT5 para {sym_mt5} (hace {int(sl_age/60)}m). Activando cooldown de {rem_min} min.")
                                                break
                                        elif d.profit >= 0.0:
                                            break # Última salida fue positiva, no hay cooldown
                                if sl_hit_detected:
                                    continue

                            # Verificar si FTMO Guardian activó Daily Loss Cap
                            if ftmo_guardian.is_daily_lockout:
                                logger.info(f"🛑 [SOP-70 DAILY LOSS CAP] Emisión de orden {sym_mt5} cancelada: {ftmo_guardian.lockout_reason}")
                                continue

                            # [SOP-156 MUTEX UNIVERSAL DE CLÚSTER: XAUUSD <-> XAGUSD & ÍNDICES]
                            from engine.risk.prop_firm_governor import prop_firm_governor
                            open_pos = mt5_bridge.get_open_positions()
                            unsecured_symbols = [
                                str(p.get("symbol", ""))
                                for p in open_pos
                                if float(p.get("profit", 0.0)) <= 0.0
                            ]
                            if mt5_bridge.ensure_connected() and not mt5_bridge.dry_run:
                                for po in (mt5.orders_get() or []):
                                    unsecured_symbols.append(str(getattr(po, "symbol", "")))
                            cluster_ok, cluster_msg = prop_firm_governor.is_cluster_slot_available(symbol, unsecured_symbols)
                            if not cluster_ok:
                                logger.info(f"🛡️ [CLUSTER_MUTEX SOP-156] Orden {sym_mt5} {direction} bloqueada: {cluster_msg}")
                                continue

                            has_order = False
                            if mt5_bridge.ensure_connected() and not mt5_bridge.dry_run:
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
                                    score=score,
                                    risk_usd_override=candidate["risk_usd"],
                                )
                                if res.get("success"):
                                    if not hasattr(self, "_active_orders"):
                                        self._active_orders = set()
                                    self._active_orders.add(sym_mt5)
                                    logger.info(f"🎯 [TRADFI_AUTOLIMIT] Orden límite colocada en MT5 para {sym_mt5}: {direction} @ {candidate['price']}")
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


