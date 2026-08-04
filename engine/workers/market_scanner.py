import asyncio
import pandas as pd
from engine.core.logger import logger
from engine.main_router import SlingshotRouter
from engine.indicators.data_utils import fetch_binance_history
from engine.core.store import store
from engine.core.confluence import confluence_manager

class MarketScanner:
    """
    [APEX MULTI-TEMPORAL SCANNER v15.0 — OTE WATCHDOG]
    Escáner profesional de mercado en segundo plano.
    Analiza 20 activos líderes en temporalidades de Corto Plazo (15m) y Largo Plazo (4h).
    Usa el motor real de SlingshotRouter y ConfluenceManager con contexto enriquecido:
      - Golden Pocket / OTE (Fibonacci 61.8%-78.6%)
      - Sesión de Trading activa (London / New York / Asia / Off-Hours)
      - Filtro OTE Watchdog: penaliza setups que persiguen el precio
    """
    def __init__(self):
        self.router = SlingshotRouter()
        self.assets = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "LTCUSDT", 
            "LINKUSDT", "ADAUSDT", "DOTUSDT", "AVAXUSDT", "NEARUSDT", 
            "FTMUSDT", "ATOMUSDT", "UNIUSDT", "OPUSDT", "ARBUSDT", 
            "INJUSDT", "WIFUSDT", "DOGEUSDT", "APTUSDT", "SUIUSDT"
        ]
        self._stop_event = asyncio.Event()
        self._task = None
        self._tactical_cache = {}  # Cache táctica en memoria para optimización v16.0

    # ─────────────────────────────────────────────
    # HELPERS DE CONTEXTO
    # ─────────────────────────────────────────────

    def _calculate_ote(self, df: pd.DataFrame) -> dict:
        """
        Calcula el Golden Pocket (OTE) del último swing mayor usando Fibonacci.
        Usa ventana de 50 velas para detectar swing high/low.
        Retorna los niveles 0.5, 0.618 y 0.786 requeridos por ConfluenceManager.
        """
        try:
            window = min(50, len(df))
            swing_high = float(df['high'].iloc[-window:].max())
            swing_low  = float(df['low'].iloc[-window:].min())
            leg = swing_high - swing_low
            if leg == 0:
                return {}
            return {
                "levels": {
                    "0.5":   round(swing_high - leg * 0.5,   8),
                    "0.618": round(swing_high - leg * 0.618, 8),
                    "0.786": round(swing_high - leg * 0.786, 8),
                },
                "swing_high": swing_high,
                "swing_low":  swing_low,
                "is_whale_leg": (leg / swing_low) > 0.05,  # >5% = movimiento de ballena
            }
        except Exception:
            return {}

    def _calculate_session(self, timestamp) -> dict:
        """
        Detecta la sesión de trading activa según UTC:
        London:    08:00–12:00 UTC
        New York:  12:00–21:00 UTC (8 AM – 5 PM EST)
        Asia:      00:00–08:00 UTC
        Off-Hours: 21:00–00:00 UTC
        """
        try:
            ts = pd.to_datetime(timestamp, utc=True)
            hour = ts.hour
            if 12 <= hour < 21:
                session = "NEW_YORK"
            elif 8 <= hour < 12:
                session = "LONDON"
            elif 0 <= hour < 8:
                session = "ASIA"
            else:
                session = "OFF_HOURS"
            return {
                "current_session": session,
                "yosh_window": 13 <= hour < 16,  # Golden Window ~10-11:30 AM EST
            }
        except Exception:
            return {"current_session": None, "yosh_window": False}

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
        await asyncio.sleep(10)
        while not self._stop_event.is_set():
            try:
                logger.info("🔍 [MARKET_SCANNER] Iniciando ciclo de escaneo global (Scalp & Swing)...")
                await self._perform_scan()
                logger.info("🔍 [MARKET_SCANNER] Ciclo de escaneo completado.")
            except Exception as e:
                logger.error(f"❌ [MARKET_SCANNER] Error en loop de escaneo: {e}")
            await asyncio.sleep(300)

    async def _perform_scan(self):
        tasks = [
            self._scan_timeframe("15m", "scalp"),
            self._scan_timeframe("4h",  "swing")
        ]
        await asyncio.gather(*tasks)

    async def _scan_timeframe(self, interval: str, store_key: str):
        candidates = []
        dfs_dict = {}
        semaphore = asyncio.Semaphore(4)
        
        async def fetch_and_prep(symbol: str):
            async with semaphore:
                try:
                    history = await fetch_binance_history(symbol, interval, limit=100)
                    if history:
                        df = pd.DataFrame([h["data"] for h in history])
                        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                        dfs_dict[symbol] = df
                except Exception as e:
                    logger.debug(f"[MARKET_SCANNER] Error descargando {symbol}: {e}")

        # Pre-descargar datos en paralelo para permitir SMT Divergence entre activos
        await asyncio.gather(*(fetch_and_prep(sym) for sym in self.assets))

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
                    virtual_sig = {
                        "asset":       symbol,
                        "symbol":      symbol,
                        "type":        "Estructura Local",
                        "signal_type": direction,
                        "price":       current_price,
                        "timestamp":   str(last_timestamp),
                        "atr_value":   atr_val,
                    }
                    
                    risk_data = self.router._risk.calculate_position(
                        current_price=current_price,
                        signal_type=direction,
                        market_regime=result.get("market_regime", "RANGING"),
                        smc_data=result.get("smc", {}),
                        atr_value=atr_val,
                        asset=symbol,
                        liquidations=liq_clusters
                    )

                    is_chasing, chase_label = self._ote_watchdog(direction, current_price, fib_data)

                    conf_res = confluence_manager.evaluate_signal(
                        df,
                        virtual_sig,
                        smc_map=result.get("smc", {}),
                        fib_data=fib_data,
                        session_data=session_data,
                        interval=interval,
                        liquidations=liq_clusters,
                        correlated_df=correlated_df
                    )

                    base_score = conf_res.get("score", 0)
                    checklist  = conf_res.get("checklist", [])

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
                        "price":             current_price,
                        "stop_loss":         risk_data["stop_loss"],
                        "tp1":               risk_data["tp1"],
                        "tp2":               risk_data["tp2"],
                        "tp3":               risk_data["tp3"],
                        "rr_ratio_tp3":      risk_data.get("rr_ratio_tp3", 3.0),
                        "confluence_score":  base_score,
                        "checklist":         checklist,
                        "is_active_trigger": False,
                        "ote_chasing":       is_chasing,
                        "session":           session_data.get("current_session", "UNKNOWN"),
                    }
                    candidates.append(cand)
                
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.debug(f"[MARKET_SCANNER] Error analizando {symbol} ({interval}): {e}")

        await asyncio.gather(*(process_asset(sym) for sym in self.assets))
        
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
        
        top_candidates = sorted_candidates[:6]
        await store.save_scanner_opportunities(store_key, top_candidates)
        logger.info(f"🔍 [MARKET_SCANNER v15] Guardados {len(top_candidates)} setups de {store_key} (OTE Watchdog activo)")

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
        }
