import asyncio
import time
from datetime import datetime, timezone
import pandas as pd
from engine.core.logger import logger
from engine.main_router import SlingshotRouter
from engine.indicators.data_utils import fetch_binance_history
from engine.core.store import store
from engine.core.confluence import confluence_manager
from engine.api.registry import registry
from engine.indicators.polars_engine import polars_engine

from engine.api.config import settings
from engine.indicators.data_utils import fetch_binance_history, fetch_top_liquid_tickers

class MarketScanner:
    """
    [APEX MULTI-TEMPORAL SCANNER v21.0 — DYNAMIC RVOL & KER WATCHLIST]
    Escáner profesional de mercado en segundo plano.
    Combina Núcleo Fijo Institucional (Tier 1) con Rotación Dinámica por Volumen y KER (Tier 2).
    """
    def __init__(self):
        self.router = SlingshotRouter()
        # 🚀 Tier 1: Núcleo Fijo Especializado por Perfil Cuantitativo (SOP-36)
        # 7 Activos Core Inmutables + BNBUSDT y SOLUSDT activos en Scalp 15m
        self.core_scalp_assets = ["RENDERUSDT", "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "TIAUSDT"]
        self.core_swing_1h_assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "XRPUSDT", "PAXGUSDT"]
        self.daily_assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT", "RENDERUSDT", "NEARUSDT"]
        
        # Activos activos en Scalp 15m (Core + Campeones BNB y SOL)
        self.scalp_assets = list(set(self.core_scalp_assets + ["BNBUSDT", "SOLUSDT"]))
        self.swing_1h_assets = list(self.core_swing_1h_assets)
        self.assets = list(set(self.scalp_assets + self.swing_1h_assets + self.daily_assets))
        
        self._dynamic_last_refresh = 0
        self._stop_event = asyncio.Event()
        self._task = None
        self._tactical_cache = {}  # Cache táctica en memoria para optimización v16.0

    async def _refresh_dynamic_assets(self):
        """
        [DYNAMIC WATCHLIST ENGINE v21.0]
        Descubre y rota activos líquidos con RVOL >= 1.25 y KER >= 0.25 en tiempo real.
        """
        if not getattr(settings, "ENABLE_DYNAMIC_WATCHLIST", True):
            return
            
        now = time.time()
        if now - self._dynamic_last_refresh < 1800: # Refresco cada 30 minutos
            return
            
        try:
            min_vol = getattr(settings, "DYNAMIC_MIN_24H_VOL_USDT", 30_000_000.0)
            max_dynamic = getattr(settings, "DYNAMIC_MAX_ROTATING_ASSETS", 6)
            excluded_raw = getattr(settings, "EXCLUDED_DYNAMIC_ASSETS", "XAGUSDT,XAGUSD,PAXGUSDT,PAXG")
            excluded_set = {s.strip().upper() for s in excluded_raw.split(",") if s.strip()}
            
            liquid_candidates = await fetch_top_liquid_tickers(min_volume_usdt=min_vol, limit=25)
            new_dynamic = [
                sym for sym in liquid_candidates 
                if sym not in self.core_scalp_assets 
                and sym not in self.core_swing_1h_assets
                and sym.upper() not in excluded_set
            ]
            
            # Tomar los top N candidatos adicionales más líquidos
            selected_dynamic = new_dynamic[:max_dynamic]
            
            self.scalp_assets = list(set(self.core_scalp_assets + selected_dynamic))
            self.assets = list(set(self.scalp_assets + self.swing_1h_assets + self.daily_assets))
            self._dynamic_last_refresh = now
            logger.info(f"✨ [DYNAMIC SCREENER] Universo actualizado: {len(self.core_scalp_assets)} Core + {len(selected_dynamic)} Dinámicos ({', '.join(selected_dynamic)}). Total: {len(self.assets)} activos.")
        except Exception as e:
            logger.debug(f"[DYNAMIC SCREENER] Error actualizando candidatos dinámicos: {e}")

    # ─────────────────────────────────────────────
    # HELPERS DE CONTEXTO
    # ─────────────────────────────────────────────

    def _calculate_ote(self, df: pd.DataFrame) -> dict:
        """
        Calcula el Golden Pocket (OTE) del último swing mayor usando el motor Polars en Rust.
        Usa ventana de 50 velas para detectar swing high/low en microsegundos.
        """
        try:
            from engine.indicators.polars_engine import polars_engine
            return polars_engine.compute_swings_and_ote(df, window=min(50, len(df)))
        except Exception:
            return {}

    def _calculate_session(self, timestamp=None) -> dict:
        """
        Calcula el estado de sesión y ventanas institucionales utilizando
        la Fuente Única de Verdad (SSoT) con soporte DST exacto (SessionManager).
        """
        try:
            from engine.core.session_manager import session_manager
            state = session_manager.get_current_state()
            data = state.get("data", {})
            return {
                "current_session": data.get("current_session", "UNKNOWN"),
                "is_killzone": data.get("is_killzone", False),
                "is_silver_bullet": data.get("is_silver_bullet", False),
                "is_overlap": data.get("is_overlap", False),
                "yosh_window": data.get("yosh_window", False),
                "pdh": data.get("pdh"),
                "pdl": data.get("pdl"),
            }
        except Exception as e:
            logger.debug(f"[MARKET_SCANNER] Error obteniendo session_manager: {e}")
            return {"current_session": "OFF_HOURS", "yosh_window": False}

    async def _get_hft_order_flow(self, symbol: str) -> dict:
        """
        Consulta la caché local del Sidecar Node.js HFT (http://127.0.0.1:8080/ticks)
        para inyectar el Order Flow Delta y Taker Volume en tiempo real.
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=0.25) as client:
                res = await client.get("http://127.0.0.1:8080/ticks")
                if res.status_code == 200:
                    ticks = res.json()
                    sym_upper = symbol.upper()
                    if sym_upper in ticks:
                        return ticks[sym_upper]
        except Exception:
            pass
        return {}

    def _ote_watchdog(self, direction: str, price: float, fib_data: dict) -> tuple:
        """
        OTE Watchdog: detecta si el precio persigue el mercado fuera de la zona de valor.
        LONG válido:  precio en zona Discount (< 50% Fibonacci)
        SHORT válido: precio en zona Premium (> 50% Fibonacci)
        Retorna (is_chasing: bool, warning_label: str).
        """
        try:
            ote_50 = fib_data.get("levels", {}).get("0.5")
            if ote_50 is None or ote_50 == 0:
                return False, ""
            if direction == "LONG" and price > ote_50:
                pct = round((price - ote_50) / ote_50 * 100, 2)
                return True, f"Zona Premium (+{pct}% sobre OTE 50%) — Riesgo de sobrecompra"
            if direction == "SHORT" and price < ote_50:
                pct = round((ote_50 - price) / ote_50 * 100, 2)
                return True, f"Zona Discount (-{pct}% bajo OTE 50%) — Riesgo de sobreventa"
        except Exception:
            pass
        return False, ""

    # ─────────────────────────────────────────────
    # LOOP PRINCIPAL
    # ─────────────────────────────────────────────

    def start(self):
        logger.info("🔍 [MARKET_SCANNER v15] Iniciando escáner OTE Watchdog multitemporal...")
        self._task = asyncio.create_task(self._scan_loop())

    def stop(self):
        logger.info("🔍 [MARKET_SCANNER] Deteniendo escáner...")
        self._stop_event.set()

    async def _scan_loop(self):
        while not self._stop_event.is_set():
            try:
                logger.info("🔍 [MARKET_SCANNER] Iniciando ciclo de escaneo global (Scalp & Swing)...")
                await self._perform_scan()
                logger.info("🔍 [MARKET_SCANNER] Ciclo de escaneo completado.")
            except Exception as e:
                logger.error(f"❌ [MARKET_SCANNER] Error en loop de escaneo: {e}")
            await asyncio.sleep(60) # Refresco cada 60s en vez de 300s para tener datos frescos siempre

    async def _perform_scan(self):
        # Refrescar candidatos dinámicos por volumen 24h
        await self._refresh_dynamic_assets()
        
        tasks = [
            self._scan_timeframe("15m", "scalp"),
            self._scan_timeframe("1h",  "swing"),
            self._scan_timeframe("1d",  "daily")
        ]
        await asyncio.gather(*tasks)

    async def _scan_timeframe(self, interval: str, store_key: str):
        candidates = []
        dfs_dict = {}
        semaphore = asyncio.Semaphore(4)
        
        # Seleccionar la lista especializada de activos según el timeframe
        if store_key == "scalp":
            target_assets = self.scalp_assets
        elif store_key == "swing":
            target_assets = self.swing_1h_assets
        else:
            target_assets = self.daily_assets
        
        async def fetch_and_prep(symbol: str):
            async with semaphore:
                try:
                    history = await fetch_binance_history(symbol, interval, limit=100)
                    if history:
                        df = pd.DataFrame([h["data"] for h in history])
                        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                        # 🦀 POLARS ACCELERATION: Cálculo vectorizado de ATR, EMAs y FVGs según el timeframe real
                        df = polars_engine.compute_indicators(df)
                        dfs_dict[symbol] = df
                except Exception as e:
                    logger.debug(f"[MARKET_SCANNER] Error descargando {symbol}: {e}")

        # Pre-descargar datos en paralelo para permitir SMT Divergence entre activos
        await asyncio.gather(*(fetch_and_prep(sym) for sym in target_assets))

        async def process_asset(symbol: str):
            try:
                df = dfs_dict.get(symbol)
                if df is None or df.empty:
                    return
                
                current_price  = float(df["close"].iloc[-1])
                last_timestamp = df["timestamp"].iloc[-1]
                cache_key = f"{symbol}:{interval}"
                
                # ── OPTIMIZACIÓN v16.0: Throttle por Cierre de Vela ──
                cached = self._tactical_cache.get(cache_key)
                if cached and cached["last_timestamp"] == last_timestamp:
                    result       = cached["result"]
                    fib_data     = cached["fib_data"]
                    session_data = cached["session_data"]
                else:
                    result = await self.router.process_market_data(df, asset=symbol, interval=interval, silent=True)
                    fib_data     = self._calculate_ote(df)
                    session_data = self._calculate_session(last_timestamp)
                    
                    self._tactical_cache[cache_key] = {
                        "last_timestamp": last_timestamp,
                        "result": result,
                        "fib_data": fib_data,
                        "session_data": session_data
                    }
                
                active_signals = result.get("signals", [])
                if active_signals:
                    for sig in active_signals:
                        candidates.append(self._format_opportunity(sig, is_active=True))
                    return
                
                # Calcular clusters de liquidación en vivo para el escáner
                from engine.indicators.liquidations import estimate_liquidation_clusters
                liq_clusters = estimate_liquidation_clusters(df, current_price)
                correlated_df = dfs_dict.get("BTCUSDT") if symbol != "BTCUSDT" else dfs_dict.get("ETHUSDT")
                
                for direction in ["LONG", "SHORT"]:
                    atr_val = float(df["atr"].iloc[-1]) if "atr" in df.columns else float(current_price * 0.002)
                    
                    # ── CÁLCULO DE ENTRADA LÍMITE OPTIMA SMC / OTE ──
                    smc_map = result.get("smc", {})
                    optimal_entry = current_price
                    
                    if direction == "LONG":
                        bull_obs = smc_map.get("order_blocks", {}).get("bullish", []) if smc_map else []
                        valid_obs = [ob for ob in bull_obs if ob.get("top", 0) < current_price]
                        if valid_obs:
                            optimal_entry = max(valid_obs, key=lambda ob: ob["top"])["top"]
                        else:
                            bull_fvgs = smc_map.get("fvgs", {}).get("bullish", []) if smc_map else []
                            valid_fvgs = [fvg for fvg in bull_fvgs if fvg.get("top", 0) < current_price]
                            if valid_fvgs:
                                optimal_entry = max(valid_fvgs, key=lambda fvg: fvg["top"])["top"]
                    else:
                        bear_obs = smc_map.get("order_blocks", {}).get("bearish", []) if smc_map else []
                        valid_obs = [ob for ob in bear_obs if ob.get("bottom", 0) > current_price]
                        if valid_obs:
                            optimal_entry = min(valid_obs, key=lambda ob: ob["bottom"])["bottom"]
                        else:
                            bear_fvgs = smc_map.get("fvgs", {}).get("bearish", []) if smc_map else []
                            valid_fvgs = [fvg for fvg in bear_fvgs if fvg.get("bottom", 0) > current_price]
                            if valid_fvgs:
                                optimal_entry = min(valid_fvgs, key=lambda fvg: fvg["bottom"])["bottom"]

                    # Consulta HFT Sidecar para inyectar Order Flow Delta
                    hft_tick = await self._get_hft_order_flow(symbol)
                    order_flow_delta = float(hft_tick.get("delta_ratio", 0.0))

                    virtual_sig = {
                        "asset":             symbol,
                        "symbol":            symbol,
                        "type":              "Estructura Local",
                        "signal_type":       direction,
                        "price":             optimal_entry,
                        "timestamp":         str(last_timestamp),
                        "atr_value":         atr_val,
                        "order_flow_delta":  order_flow_delta,
                    }
                    
                    risk_data = self.router._risk.calculate_position(
                        current_price=optimal_entry,
                        signal_type=direction,
                        market_regime=result.get("market_regime", "RANGING"),
                        smc_data=result.get("smc", {}),
                        atr_value=atr_val,
                        asset=symbol,
                        liquidations=liq_clusters
                    )

                    is_chasing, chase_label = self._ote_watchdog(direction, current_price, fib_data)

                    # Cálculo de alineación macro con BTC
                    btc_aligned = None
                    btc_df = dfs_dict.get("BTCUSDT") if isinstance(dfs_dict, dict) else None
                    if btc_df is not None and len(btc_df) > 0 and symbol != "BTCUSDT":
                        if "ema200" not in btc_df.columns:
                            btc_df["ema200"] = btc_df["close"].ewm(span=200, adjust=False).mean()
                        btc_price = float(btc_df["close"].iloc[-1])
                        btc_ema200 = float(btc_df["ema200"].iloc[-1])
                        btc_aligned = (direction == "LONG" and btc_price > btc_ema200) or (direction == "SHORT" and btc_price < btc_ema200)

                    conf_res = confluence_manager.evaluate_signal(
                        df,
                        virtual_sig,
                        smc_map=result.get("smc", {}),
                        fib_data=fib_data,
                        session_data=session_data,
                        interval=interval,
                        liquidations=liq_clusters,
                        correlated_df=correlated_df,
                        btc_aligned=btc_aligned
                    )

                    base_score = conf_res.get("score", 0)
                    checklist  = conf_res.get("checklist", [])

                    # ── FILTRO DE TENDENCIA INSTITUCIONAL EMA 200 ──
                    if "ema200" not in df.columns:
                        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
                    
                    ema200_val = float(df["ema200"].iloc[-1])
                    is_trend_aligned = (direction == "LONG" and current_price > ema200_val) or (direction == "SHORT" and current_price < ema200_val)

                    if is_trend_aligned:
                        base_score = min(100, base_score + 10)
                        checklist.append({
                            "factor": "Tendencia Macro EMA 200",
                            "status": "CUMPLIDO",
                            "detail": f"✅ ALINEADO A TENDENCIA (Precio ${current_price:,.2f} vs EMA200 ${ema200_val:,.2f})",
                        })
                    else:
                        base_score = max(0, base_score - 15)
                        checklist.append({
                            "factor": "Tendencia Macro EMA 200",
                            "status": "ALERTA",
                            "detail": f"⚠️ CONTRA TENDENCIA EMA 200 (Precio ${current_price:,.2f} vs EMA200 ${ema200_val:,.2f})",
                        })

                    if is_chasing:
                        base_score = max(0, base_score - 20)
                        checklist.append({
                            "factor": "OTE Watchdog",
                            "status": "ALERTA",
                            "detail": f"⚠️ PERSIGUIENDO PRECIO: {chase_label}",
                        })

                    cand = {
                        "asset":             symbol,
                        "direction":         direction,
                        "type":              "Virtual Setup",
                        "price":             optimal_entry,
                        "stop_loss":         risk_data["stop_loss"],
                        "sl_dist_pct":       risk_data.get("sl_dist_pct", 1.8),
                        "position_size_usdt": risk_data.get("position_size_usdt", 1000.0),
                        "tp1":               risk_data["tp1"],
                        "tp2":               risk_data["tp2"],
                        "tp3":               risk_data["tp3"],
                        "rr_ratio_tp3":      risk_data.get("rr_ratio_tp3", 3.0),
                        "confluence_score":  base_score,
                        "checklist":         checklist,
                        "is_active_trigger": False,
                        "ote_chasing":       is_chasing,
                        "session":           session_data.get("current_session", "UNKNOWN"),
                        "asset_health":      conf_res.get("asset_health", {}),
                    }
                    candidates.append(cand)
                
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"[MARKET_SCANNER] Error procesando {symbol} en {interval}: {e}")

        await asyncio.gather(*(process_asset(sym) for sym in target_assets))
        
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (
                1 if x["is_active_trigger"] else 0,
                0 if x.get("ote_chasing") else 1,  # Setups OTE válidos antes que los que persiguen precio
                x["confluence_score"],
                x["rr_ratio_tp3"]
            ),
            reverse=True
        )
        
        # 🧠 [AI HYPOTHESIS ENRICHMENT v20.0]
        # Generar hipótesis para el Top-3 de oportunidades válidas
        try:
            from engine.api.advisor import generate_scanner_hypotheses_batch
            eligible_for_ai = [c for c in sorted_candidates if c["confluence_score"] >= 60 and not c.get("ote_chasing")]
            if eligible_for_ai:
                hypotheses = await generate_scanner_hypotheses_batch(eligible_for_ai[:3])
                hyp_by_asset = {h.get("asset"): h for h in hypotheses if isinstance(h, dict) and h.get("asset")}
                for cand in sorted_candidates:
                    if cand["asset"] in hyp_by_asset:
                        h_data = hyp_by_asset[cand["asset"]]
                        cand["ai_hypothesis"] = h_data.get("hypothesis", "")
                        cand["ai_verdict"] = h_data.get("verdict", "GO")
                        cand["ai_threat"] = h_data.get("threat", "LOW")
        except Exception as ai_err:
            logger.debug(f"[MARKET_SCANNER] Bypass enriquecimiento IA: {ai_err}")

        # 💎 [PARIDAD TOTAL 1-a-1 v19.1] Guardamos todas las oportunidades válidas
        await store.save_scanner_opportunities(store_key, sorted_candidates)
        logger.info(f"🔍 [MARKET_SCANNER v19.1] Guardados {len(sorted_candidates)} setups de {store_key} en el Escáner de Oportunidades.")

        # 🚀 [TELEGRAM APEX SNIPER DISPATCHER] ──
        # Despacho automático de oportunidades con confluencia >= 60% sin persecución de precio ni cuarentena
        from engine.router.telegram_dispatcher import telegram_dispatcher
        for top_c in sorted_candidates:
            score = top_c.get("confluence_score", 0)
            is_chasing = top_c.get("ote_chasing", False)
            is_quarantined = top_c.get("asset_health", {}).get("is_quarantined", False)
            min_score = 65 if is_quarantined else 60

            if score >= min_score and not is_chasing:
                dist_sl = abs(float(top_c["price"]) - float(top_c["stop_loss"]))
                is_long = "LONG" in top_c["direction"].upper()
                be_val = top_c.get("be_price") or (float(top_c["price"]) + (dist_sl * 1.0) if is_long else float(top_c["price"]) - (dist_sl * 1.0))

                tele_sig = {
                    "asset": top_c["asset"],
                    "symbol": top_c["asset"],
                    "interval": interval,
                    "timeframe": interval,
                    "signal_type": top_c["direction"],
                    "direction": top_c["direction"],
                    "type": "SMC Sniper",
                    "price": float(top_c["price"]),
                    "stop_loss": float(top_c["stop_loss"]),
                    "be_price": round(be_val, 5),
                    "tp1": float(top_c["tp1"]),
                    "tp2": float(top_c["tp2"]),
                    "tp3": float(top_c["tp3"]),
                    "take_profit_3r": float(top_c["tp3"]),
                    "confluence_score": score,
                    "score": score,
                    "session": top_c.get("session", "NEW_YORK"),
                    "asset_health": top_c.get("asset_health", {})
                }
                asyncio.create_task(telegram_dispatcher.send_signal_alert(tele_sig))

                # Auto-colocación automática de la orden límite en Bitunix si el Live Trading está habilitado
                if settings.ENABLE_LIVE_TRADING:
                    from engine.execution.nexus import nexus
                    asyncio.create_task(nexus.process_limit_setup(tele_sig))

    def _format_opportunity(self, sig: dict, is_active: bool) -> dict:
        return {
            "asset":             sig.get("asset", "UNKNOWN"),
            "direction":         sig.get("signal_type", "LONG"),
            "type":              sig.get("type", "SMC Sniper"),
            "price":             float(sig.get("price", 0)),
            "stop_loss":         float(sig.get("stop_loss", 0)),
            "tp1":               float(sig.get("tp1", 0)),
            "tp2":               float(sig.get("tp2", 0)),
            "tp3":               float(sig.get("take_profit_3r", 0)),
            "rr_ratio_tp3":      float(sig.get("rr_ratio_tp3", 3.0)),
            "confluence_score":  int(sig.get("confluence", {}).get("score", 70)),
            "checklist":         sig.get("confluence", {}).get("checklist", []),
            "is_active_trigger": is_active,
            "ote_chasing":       False,
            "session":           "LIVE_SIGNAL",
            "asset_health":      sig.get("confluence", {}).get("asset_health", {}),
        }
