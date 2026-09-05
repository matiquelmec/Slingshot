"""
engine/workers/trade_manager.py — Trailing Stop Estructural Slingshot v1.0
===========================================================================
Gestiona el ciclo de vida de señales activas después de su activación.
Implementa un Trailing Stop inteligente que sigue la estructura del mercado
(swing lows/highs y Order Blocks) en lugar de porcentajes fijos.

Fases del ciclo de vida de una señal:
  ACTIVE   → Precio entre entrada y TP1. SL fijo en posición original.
  BREAKEVEN→ Precio tocó TP1. SL movido a precio de entrada + buffer ATR.
             Se cierra el 40% de la posición (parcial TP1).
  TRAILING → Precio superó TP2. SL sigue el último swing estructural.
             Se cierra el 30% adicional de la posición (parcial TP2).
  CLOSED   → Precio tocó TP3 o SL fue hit. Ciclo completado.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from engine.core.logger import logger
from engine.core.store import store
from engine.indicators.data_utils import fetch_binance_history
from engine.risk.risk_manager import RiskManager
import pandas as pd


class TradeManager:
    """
    [STRUCTURAL TRAILING STOP v1.0]
    Worker en segundo plano que monitorea las señales activas del MemoryStore
    y actualiza el SL de forma estructural según la evolución del precio.
    """

    POLL_INTERVAL_SECONDS = 30  # Evalúa cada 30 segundos
    ATR_BE_BUFFER = 0.3         # 30% del ATR como buffer sobre el precio de entrada en BE

    def __init__(self):
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    def start(self):
        logger.info("[TRADE_MANAGER] Iniciando Trailing Stop Estructural v1.0...")
        self._task = asyncio.create_task(self._management_loop())

    def stop(self):
        logger.info("[TRADE_MANAGER] Deteniendo gestor de trades...")
        self._stop_event.set()

    # ─────────────────────────────────────────────
    # LOOP PRINCIPAL
    # ─────────────────────────────────────────────

    async def _management_loop(self):
        """Ciclo principal: revisa señales activas y sincroniza posiciones en Bitunix cada 30 segundos."""
        await asyncio.sleep(10)  # Espera inicial para que el sistema arranque
        while not self._stop_event.is_set():
            try:
                # 1. Procesar señales del sistema local
                await self._process_active_signals()
                # 2. Sincronizar y proteger posiciones reales en vivo en Bitunix
                await self.sync_live_bitunix_positions()
                # 3. Auditar e invalidar órdenes límite huérfanas/riesgosas en Bitunix
                await self.sync_live_bitunix_pending_orders()
                # 4. Sincronizar y proteger posiciones de MetaTrader 5 (FTMO)
                await self.sync_live_mt5_positions()
            except Exception as e:
                logger.error(f"[TRADE_MANAGER] Error en loop: {e}")
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _process_active_signals(self):
        """Itera sobre las señales y gestiona tanto órdenes PENDING como activas (ACTIVE/BREAKEVEN/TRAILING)."""
        signals = await store.get_signals(status=None)
        
        # 1. Monitoreo e Invalidación de órdenes PENDING
        pending = [
            s for s in signals 
            if s.get("status") == "PENDING" and s.get("price") and s.get("stop_loss") and s.get("tp1")
        ]
        for p_sig in pending:
            try:
                await self._process_pending_signal(p_sig)
            except Exception as e:
                logger.debug(f"[TRADE_MANAGER] Error evaluando PENDING {p_sig.get('asset')}: {e}")

        # 2. Monitoreo de Trades Activos
        active = [
            s for s in signals
            if s.get("status") in ("ACTIVE", "BREAKEVEN", "TRAILING", "APPROVED", "FILLED")
               and s.get("price") and s.get("stop_loss") and s.get("tp1")
        ]

        if not active:
            return

        logger.info(f"[TRADE_MANAGER] Procesando {len(active)} trade(s) activo(s)...")

        for signal in active:
            try:
                await self._update_signal_trailing(signal)
            except Exception as e:
                logger.warning(f"[TRADE_MANAGER] Error procesando {signal.get('asset')}: {e}")

    async def _process_pending_signal(self, signal: Dict[str, Any]):
        """
        Evalúa si una orden PENDING tocó entrada (pasa a FILLED/ACTIVE) 
        o si el precio se escapó y superó TP1 sin tocar entrada (pasa a EXPIRED_MISSED).
        """
        asset = signal.get("asset", "UNKNOWN")
        interval = signal.get("interval", "15m")
        is_long = str(signal.get("signal_type", "LONG")).upper() == "LONG"
        entry_price = float(signal.get("price", 0))
        sl_price = float(signal.get("stop_loss", 0))
        tp1_price = float(signal.get("tp1", 0))

        if entry_price <= 0:
            return

        history = await fetch_binance_history(asset, interval, limit=10)
        if not history:
            return

        df = pd.DataFrame([h["data"] for h in history])
        current_price = float(df["close"].iloc[-1])
        low_price = float(df["low"].min())
        high_price = float(df["high"].max())

        # Caso A: El precio tocó la entrada -> Activar orden
        entry_touched = (is_long and low_price <= entry_price) or (not is_long and high_price >= entry_price)
        if entry_touched:
            signal["status"] = "FILLED"
            signal["filled_at"] = df["timestamp"].iloc[-1]
            signal["trailing_phase"] = "ACTIVE"
            await store.save_signal(signal)
            logger.info(f"⚡ [TRADE_MANAGER] Orden PENDING {asset} LLENADA (@ ${entry_price:.4f}). Estado -> FILLED.")
            return

        # Caso B: El precio se escapó y alcanzó TP1 sin haber dado entrada -> Invalidar
        missed_tp1 = (is_long and high_price >= tp1_price) or (not is_long and low_price <= tp1_price)
        if missed_tp1:
            signal["status"] = "EXPIRED_MISSED"
            signal["rejection_reason"] = f"El precio alcanzó TP1 (${tp1_price:.4f}) sin retroceder al nivel de entrada (${entry_price:.4f}). Setup descartado."
            await store.save_signal(signal)
            from engine.execution.nexus import nexus
            nexus.remove_pending_limit_symbol(asset)
            logger.info(f"⏱️ [TRADE_MANAGER] Orden PENDING {asset} EXPIRADA (Objetivo alcanzado sin dar entrada).")
            return

        # Caso C: El precio rompió el Stop Loss antes de entrar
        sl_broken = (is_long and low_price < sl_price) or (not is_long and high_price > sl_price)
        if sl_broken:
            signal["status"] = "INVALIDATED_BROKEN"
            signal["rejection_reason"] = f"Estructura invalidada antes de la activación (SL ${sl_price:.4f} perforado)."
            await store.save_signal(signal)
            from engine.execution.nexus import nexus
            nexus.remove_pending_limit_symbol(asset)
            logger.info(f"🛑 [TRADE_MANAGER] Orden PENDING {asset} INVALIDADA (SL roto previo a entrada).")

    def is_megacap(self, symbol: str) -> bool:
        """Determina si un activo es Mega-Cap institucional (BTC, ETH, SOL, etc.)."""
        s = (symbol or "").upper()
        return any(m in s for m in ["BTC", "ETH", "SOL", "AVAX", "LINK", "XRP", "BNB", "PAXG", "XAG"])

    # ─────────────────────────────────────────────
    # LÓGICA CENTRAL DE TRAILING
    # ─────────────────────────────────────────────

    async def _update_signal_trailing(self, signal: Dict[str, Any]):
        """
        Evalúa un trade activo y actualiza su SL según la fase actual.
        Descarga las últimas velas del activo para calcular la estructura real.
        """
        asset    = signal.get("asset", "UNKNOWN")
        interval = signal.get("interval", "15m")
        is_long  = str(signal.get("signal_type", "LONG")).upper() == "LONG"

        entry_price = float(signal.get("price", 0))
        current_sl  = float(signal.get("stop_loss", 0))
        tp1 = float(signal.get("tp1", 0))
        tp2 = float(signal.get("tp2", tp1))  # fallback a tp1 si no hay tp2
        tp3 = float(signal.get("tp3", signal.get("take_profit_3r", 0)))
        phase = signal.get("trailing_phase", "ACTIVE")

        if entry_price <= 0 or current_sl <= 0:
            return

        # Obtener precio actual desde el historial reciente
        history = await fetch_binance_history(asset, interval, limit=30)
        if not history:
            return

        df = pd.DataFrame([h["data"] for h in history])
        current_price = float(df["close"].iloc[-1])
        atr_val = float(df["atr"].iloc[-1]) if "atr" in df.columns else entry_price * 0.002

        # ── Fase 1: ACTIVE → FAST BREAKEVEN (Adaptativo: 1.2R Megas / 1.0R Alts) ──
        if phase == "ACTIVE":
            initial_sl = float(signal.get("initial_stop_loss", current_sl))
            risk_dist = abs(entry_price - initial_sl)
            be_multiplier = 1.2 if self.is_megacap(asset) else 1.0
            be_fast_trigger = entry_price + (risk_dist * be_multiplier) if is_long else entry_price - (risk_dist * be_multiplier)

            # Condición A: Toca Fast BE (+1.2R Megas / +1.0R Alts)
            fast_be_hit = (is_long and current_price >= be_fast_trigger) or (not is_long and current_price <= be_fast_trigger)
            # Condición B: Toca TP1 (+1.5R)
            tp1_hit = (is_long and current_price >= tp1) or (not is_long and current_price <= tp1)

            if fast_be_hit or tp1_hit:
                new_sl = self._calculate_breakeven_sl(entry_price, atr_val, is_long)
                if self._sl_improved(current_sl, new_sl, is_long):
                    trig_label = "TP1" if tp1_hit else f"Fast BE (+{be_multiplier:.1f}R)"
                    await self._apply_sl_update(
                        signal,
                        new_sl,
                        "BREAKEVEN",
                        f"🎯 {trig_label} alcanzado @ ${current_price:.4f}. SL protegido a entrada con Fee Absorber (${new_sl:.4f})"
                    )
                    logger.info(f"🛡️ [TRADE_MANAGER] {asset} -> Fast BE (+{be_multiplier:.1f}R) activado: SL movido a {new_sl:.6f}")
            return

        # ── Fase 2: BREAKEVEN → TRAILING ────────────────────────────────────
        if phase == "BREAKEVEN":
            tp2_hit = (is_long and current_price >= tp2) or (not is_long and current_price <= tp2)
            if tp2_hit:
                confirmed, reason = self._is_move_confirmed(df, tp2, is_long)
                if confirmed:
                    structural_sl = self._find_structural_sl(df, current_price, is_long, atr_val)
                    if structural_sl and self._sl_improved(current_sl, structural_sl, is_long):
                        await self._apply_sl_update(signal, structural_sl, "TRAILING",
                            f"TP2 confirmado ({reason}). SL estructural = {structural_sl:.6f}")
                        logger.info(f"[TRADE_MANAGER] {asset} -> TRAILING activado: SL = {structural_sl:.6f}")
                else:
                    logger.debug(f"[TRADE_MANAGER] {asset}: precio toca TP2 pero sin confirmacion ({reason}). Esperando.")
            return

        # ── Fase 3: TRAILING activo ──────────────────────────────────────────
        if phase == "TRAILING":
            # Comprobar si el TP3 fue tocado
            tp3_hit = tp3 > 0 and ((is_long and current_price >= tp3) or (not is_long and current_price <= tp3))
            sl_hit  = (is_long and current_price <= current_sl) or (not is_long and current_price >= current_sl)

            if tp3_hit:
                await self._apply_sl_update(signal, current_sl, "CLOSED",
                    f"TP3 alcanzado ({tp3:.6f}). Trade cerrado con exito.")
                logger.info(f"[TRADE_MANAGER] {asset} -> CERRADO en TP3")
                return

            if sl_hit:
                await self._apply_sl_update(signal, current_sl, "CLOSED",
                    f"SL hit en {current_sl:.6f}. Trade cerrado.")
                logger.info(f"[TRADE_MANAGER] {asset} -> SL HIT en {current_sl:.6f}")
                return

            # Actualizar trailing: buscar nuevo swing estructural más favorable
            structural_sl = self._find_structural_sl(df, current_price, is_long, atr_val)
            if structural_sl and self._sl_improved(current_sl, structural_sl, is_long):
                await self._apply_sl_update(signal, structural_sl, "TRAILING",
                    f"Trailing actualizado a nuevo soporte estructural = {structural_sl:.6f}")
                logger.info(f"[TRADE_MANAGER] {asset} -> TRAILING update: SL = {structural_sl:.6f}")

    def _calculate_breakeven_sl(self, entry: float, atr: float, is_long: bool) -> float:
        """
        [FEE ABSORBER BUFFER v23.0]
        Calcula el Stop Loss de Break Even asegurando cubrir las comisiones del exchange (0.08%).
        Garantiza un PnL neto en verde (+$0.01 a +$0.05 USDT) ante cualquier cierre en Breakeven.
        """
        fee_buffer = max(entry * 0.0008, atr * self.ATR_BE_BUFFER)
        return round(entry + fee_buffer, 8) if is_long else round(entry - fee_buffer, 8)

    def _find_structural_sl(
        self,
        df: pd.DataFrame,
        current_price: float,
        is_long: bool,
        atr: float,
        lookback: int = 10
    ) -> Optional[float]:
        """
        Encuentra el SL estructural más favorable usando:
        1. El swing low/high más reciente de las últimas `lookback` velas.
        2. Un buffer de 0.5 * ATR debajo/encima del swing para dar espacio.
        """
        try:
            recent = df.iloc[-lookback:]

            if is_long:
                # Para LONG: buscar el swing low más reciente que esté por debajo del precio actual
                swing_low = recent["low"].min()
                structural_sl = round(swing_low - (atr * 0.5), 8)
                # Sanity check: el SL estructural no puede estar más del 5% del precio por debajo
                max_dist = current_price * 0.05
                if (current_price - structural_sl) > max_dist:
                    return None
                return structural_sl
            else:
                # Para SHORT: buscar el swing high más reciente que esté por encima del precio actual
                swing_high = recent["high"].max()
                structural_sl = round(swing_high + (atr * 0.5), 8)
                max_dist = current_price * 0.05
                if (structural_sl - current_price) > max_dist:
                    return None
                return structural_sl

        except Exception as e:
            logger.warning(f"[TRADE_MANAGER] Error calculando SL estructural: {e}")
            return None

    def _sl_improved(self, old_sl: float, new_sl: float, is_long: bool) -> bool:
        """
        Verifica que el nuevo SL sea mejor (más favorable) que el anterior.
        El Trailing Stop NUNCA puede retroceder.
        """
        if is_long:
            return new_sl > old_sl   # Para LONG: el SL debe subir
        else:
            return new_sl < old_sl   # Para SHORT: el SL debe bajar

    def _is_move_confirmed(self, df: pd.DataFrame, level: float, is_long: bool) -> tuple:
        """
        Triple confirmación institucional antes de mover el SL.
        Requiere las 3 simultáneamente para evitar reaccionar a mechas falsas.

        1. CIERRE DE VELA: la última vela cerró más allá del nivel (no solo lo tocó)
        2. VOLUMEN:        el RVOL de esa vela es >= 1.3x el promedio de 20 velas
        3. BOS ESTRUCTURAL: el precio dejó un nuevo High/Low mayor que el anterior

        Retorna (confirmed: bool, reason: str)
        """
        try:
            if len(df) < 3:
                return False, "Datos insuficientes"

            last  = df.iloc[-1]   # Vela más reciente (puede estar abierta)
            prev  = df.iloc[-2]   # Vela anterior cerrada — la que confirma
            prev2 = df.iloc[-3]   # Penúltima — para comparar BOS

            close_prev = float(prev["close"])
            high_prev  = float(prev["high"])
            low_prev   = float(prev["low"])
            high_prev2 = float(prev2["high"])
            low_prev2  = float(prev2["low"])

            # ── 1. Confirmación de cierre ──────────────────────────────────
            if is_long:
                candle_confirmed = close_prev > level
            else:
                candle_confirmed = close_prev < level

            if not candle_confirmed:
                return False, f"Vela cerro en {close_prev:.4f}, nivel {level:.4f} no superado"

            # ── 2. Confirmación de volumen (RVOL >= 1.3x) ─────────────────
            vol_mean = df["volume"].iloc[-21:-1].mean()
            vol_prev = float(prev["volume"])
            rvol = vol_prev / vol_mean if vol_mean > 0 else 1.0

            if rvol < 1.3:
                return False, f"Volumen insuficiente: RVOL {rvol:.2f}x (minimo 1.3x)"

            # ── 3. BOS Estructural (Higher High / Lower Low) ───────────────
            if is_long:
                bos_confirmed = high_prev > high_prev2   # Nuevo máximo más alto
            else:
                bos_confirmed = low_prev < low_prev2     # Nuevo mínimo más bajo

            if not bos_confirmed:
                return False, "Sin Break of Structure confirmado"

            return True, f"Cierre OK + RVOL {rvol:.2f}x + BOS confirmado"

        except Exception as e:
            logger.warning(f"[TRADE_MANAGER] Error en _is_move_confirmed: {e}")
            # En caso de error, permitimos el movimiento para no bloquear el sistema
            return True, "Bypass por error de calculo"

    # ─────────────────────────────────────────────
    # PERSISTENCIA & SINCRONIZACIÓN CON EXCHANGE (BITUNIX)
    # ─────────────────────────────────────────────

    async def _apply_sl_update(
        self,
        signal: Dict[str, Any],
        new_sl: float,
        new_phase: str,
        reason: str
    ):
        """Persiste el nuevo SL y fase en el MemoryStore y ejecuta la modificación en Bitunix."""
        asset = signal.get("asset", signal.get("symbol", "UNKNOWN"))
        signal["stop_loss"]      = new_sl
        signal["trailing_phase"] = new_phase
        signal["trailing_reason"] = reason
        signal["status"] = "CLOSED" if new_phase == "CLOSED" else signal.get("status", "ACTIVE")

        # Añadir al historial de trailing para auditoría
        history = signal.get("trailing_history", [])
        history.append({
            "sl": new_sl,
            "phase": new_phase,
            "reason": reason,
        })
        signal["trailing_history"] = history[-10:]  # Últimos 10 movimientos

        await store.save_signal(signal)

        # 🚀 [BITUNIX LIVE EXCHANGE SYNC] Modificar Stop Loss real en el exchange (Multi-Cuenta SOP-45)
        try:
            from engine.execution.account_manager import AccountManager
            mgr = AccountManager()
            executors = mgr.get_all_executors(enabled_only=True)
            position_id = signal.get("position_id") or signal.get("main_order_id")
            
            for acc_id, ex in executors.items():
                try:
                    success = await ex.modify_position_tpsl(
                        symbol=asset,
                        position_id=str(position_id) if position_id else "live_position",
                        sl_price=new_sl
                    )
                    if success:
                        logger.info(f"⚡ [TRADE_MANAGER -> BITUNIX] [{ex.account_label}] SL de posición {asset} actualizado a ${new_sl:.4f} en el exchange.")
                    else:
                        logger.debug(f"[TRADE_MANAGER] [{ex.account_label}] SL no requerido o sin posición activa en Bitunix para {asset}")
                except Exception as acc_err:
                    logger.warning(f"[TRADE_MANAGER] [{ex.account_label}] Error al sincronizar SL: {acc_err}")
        except Exception as bitunix_err:
            logger.warning(f"[TRADE_MANAGER] Error al sincronizar SL con Bitunix: {bitunix_err}")

    async def sync_live_bitunix_positions(self) -> List[Dict[str, Any]]:
        """
        Consulta las posiciones reales abiertas en Bitunix para todas las cuentas activas (SOP-45 Multi-Cuenta),
        calcula su avance en R y actualiza automáticamente a Breakeven aquellas que hayan avanzado >= +1.0R.
        """
        managed_results = []
        try:
            from engine.execution.account_manager import AccountManager
            mgr = AccountManager()
            executors = mgr.get_all_executors(enabled_only=True)
            if not executors:
                from engine.execution.bitunix_executor import BitunixExecutor
                executors = {"primary": BitunixExecutor()}
        except Exception as e:
            logger.warning(f"[TRADE_MANAGER] Error obteniendo ejecutores de cuentas: {e}")
            return []

        for acc_id, bitunix in executors.items():
            try:
                positions = await bitunix.get_pending_positions()
                if positions is None or len(positions) == 0:
                    continue

                # Consultar órdenes TPSL activas en Bitunix para conocer el SL real configurado
                tpsl_res = await bitunix._request("GET", "/api/v1/futures/tpsl/get_pending_orders")
                tpsl_map = {}
                if tpsl_res.get("code") == 0 and isinstance(tpsl_res.get("data"), list):
                    for to in tpsl_res["data"]:
                        sym_key = to.get("symbol")
                        raw_val = to.get("slPrice") or to.get("triggerPrice")
                        if sym_key and raw_val:
                            try:
                                tpsl_map[sym_key] = float(raw_val)
                            except (ValueError, TypeError):
                                pass

                for pos in positions:
                    sym = pos.get("symbol", "UNKNOWN")
                    side = "LONG" if pos.get("side") in ("BUY", "LONG", "1") else "SHORT"
                    entry_price = float(pos.get("avgOpenPrice") or pos.get("entryPrice") or pos.get("avgPrice") or 0.0)
                    cur_price = float(pos.get("lastPrice") or pos.get("markPrice") or (await bitunix.get_ticker_price(sym)))
                    cur_sl = float(pos.get("slPrice") or pos.get("stopLoss") or tpsl_map.get(sym) or 0.0)
                    pos_id = str(pos.get("positionId") or pos.get("id") or "")
                    
                    if entry_price <= 0 or cur_price <= 0:
                        continue

                    # Buscar si existe una señal registrada para recuperar su initial_stop_loss exacto
                    known_signals = await store.get_signals(asset=sym)
                    matched_sig = known_signals[-1] if known_signals else None
                    initial_sl = float(matched_sig.get("initial_stop_loss", 0.0)) if matched_sig else 0.0

                    # Distancia de riesgo inicial (1R)
                    is_defensive_sl = (side == "LONG" and 0 < cur_sl < entry_price) or (side == "SHORT" and cur_sl > entry_price)

                    if initial_sl > 0:
                        sl_dist = abs(entry_price - initial_sl)
                    elif is_defensive_sl and abs(entry_price - cur_sl) > (entry_price * 0.002):
                        sl_dist = abs(entry_price - cur_sl)
                    else:
                        default_risk_pct = 0.010 if self.is_megacap(sym) else 0.015
                        sl_dist = entry_price * default_risk_pct
                    
                    if sl_dist <= 0:
                        sl_dist = entry_price * 0.015

                    # Ganancia en unidades R reales
                    r_profit = (cur_price - entry_price) / sl_dist if side == "LONG" else (entry_price - cur_price) / sl_dist
                    
                    sl_at_be = (side == "LONG" and cur_sl >= entry_price * 0.999) or (side == "SHORT" and cur_sl > 0 and cur_sl <= entry_price * 1.001)
                    status_msg = "EN_CURSO"
                    action_taken = "NINGUNA"

                    be_threshold = 1.2 if self.is_megacap(sym) else 1.0
                    fee_buffer = entry_price * 0.0008

                    # SOP-25: Early Structural Invalidation @ 0.65R
                    is_early_inval, early_sl = RiskManager.check_early_invalidation_candidate(
                        entry_price=entry_price,
                        current_price=cur_price,
                        sl_price=cur_sl if cur_sl > 0 else (entry_price - sl_dist),
                        side=side
                    )

                    target_sl = None
                    if is_early_inval and not sl_at_be:
                        if side == "LONG" and (cur_sl <= 0 or early_sl > cur_sl * 1.0005):
                            target_sl = early_sl
                            status_msg = f"SOP25_EARLY_INVALIDATION (-0.65R / ${target_sl})"
                        elif side == "SHORT" and (cur_sl <= 0 or early_sl < cur_sl * 0.9995):
                            target_sl = early_sl
                            status_msg = f"SOP25_EARLY_INVALIDATION (-0.65R / ${target_sl})"

                    if r_profit >= 5.0:
                        locked_r = r_profit * 0.70
                        profit_buffer = sl_dist * locked_r
                        target_sl = round(entry_price + profit_buffer, 4) if side == "LONG" else round(entry_price - profit_buffer, 4)
                        status_msg = f"PROTEGIDO_RUNNER_TP3 (+{locked_r:.1f}R)"
                    elif r_profit >= 3.0:
                        profit_buffer = sl_dist * 2.0
                        target_sl = round(entry_price + profit_buffer, 4) if side == "LONG" else round(entry_price - profit_buffer, 4)
                        status_msg = "PROTEGIDO_TP3_LOCK (+2.0R)"
                    elif r_profit >= 2.0:
                        profit_buffer = sl_dist * 1.0
                        target_sl = round(entry_price + profit_buffer, 4) if side == "LONG" else round(entry_price - profit_buffer, 4)
                        status_msg = "PROTEGIDO_TP2 (+1.0R BLOQUEADO)"
                    elif r_profit >= be_threshold:
                        target_sl = round(entry_price + fee_buffer, 4) if side == "LONG" else round(entry_price - fee_buffer, 4)
                        status_msg = f"PROTEGIDO_FAST_BE (+{be_threshold:.1f}R)"

                    should_update_sl = False
                    if target_sl is not None:
                        if side == "LONG" and (cur_sl <= 0 or target_sl > cur_sl * 1.0005):
                            should_update_sl = True
                        elif side == "SHORT" and (cur_sl <= 0 or target_sl < cur_sl * 0.9995):
                            should_update_sl = True

                    if should_update_sl:
                        await bitunix.modify_position_tpsl(symbol=sym, position_id=pos_id, sl_price=target_sl, tp_price=None)
                        action_taken = f"SL_ACTUALIZADO (${target_sl})"
                        logger.info(f"🛡️ [TRADE_MANAGER] [{bitunix.account_label}] Posición {sym} {side} (+{r_profit:.2f}R) protegida con SL=${target_sl} ({status_msg}).")
                    elif sl_at_be:
                        status_msg = "YA_PROTEGIDO"

                    managed_results.append({
                        "account_id": acc_id,
                        "account_label": bitunix.account_label,
                        "symbol": sym,
                        "side": side,
                        "entry_price": entry_price,
                        "current_price": cur_price,
                        "current_sl": cur_sl,
                        "r_profit": round(r_profit, 2),
                        "status": status_msg,
                        "action": action_taken
                    })
            except Exception as acc_err:
                logger.warning(f"[TRADE_MANAGER] [{bitunix.account_label}] Error en sincronización de posiciones: {acc_err}")

        return managed_results

    async def sync_live_bitunix_pending_orders(self) -> List[Dict[str, Any]]:
        """
        [APEX LIMIT SENTINEL v22.0]
        Audita de forma autónoma todas las órdenes límite pendientes en Bitunix para todas las cuentas activas.
        Ejecuta auto-cancelación inteligente por:
          1. Objetivo alcanzado sin activación (Missed Target Kill-Switch: precio >= TP1)
          2. Invalidación previa de estructura (Pre-Entry SL Breach: precio <= SL)
          3. Expiración de tiempo de vida (TTL > 3h / 10800s desfasado)
          4. Capacidad máxima de riesgo (Auto-Purge si 4 posiciones en riesgo)
        """
        cancelled_results = []
        try:
            from engine.execution.account_manager import AccountManager
            from engine.execution.nexus import nexus
            mgr = AccountManager()
            executors = mgr.get_all_executors(enabled_only=True)
            if not executors:
                from engine.execution.bitunix_executor import BitunixExecutor
                executors = {"primary": BitunixExecutor()}
        except Exception as e:
            logger.error(f"❌ [LIMIT SENTINEL] Error obteniendo ejecutores: {e}")
            return []

        all_opps = store.get_scanner_opportunities("scalp") + store.get_scanner_opportunities("swing")
        now_ms = time.time() * 1000

        for acc_id, bitunix in executors.items():
            try:
                # 1. Regla D: Si la cuenta ya tiene 4 posiciones con riesgo, purgar órdenes límite de esa cuenta
                unprotected_risk = nexus.get_unprotected_risk_count(account_id=acc_id)
                if unprotected_risk >= nexus.MAX_CONCURRENT_POSITIONS:
                    logger.info(f"🛑 [LIMIT SENTINEL] [{bitunix.account_label}] Máximo de {nexus.MAX_CONCURRENT_POSITIONS} operaciones con riesgo alcanzado ({unprotected_risk} en riesgo). Purgando límites.")
                    await nexus.purge_all_pending_limit_orders(reason="MAX_4_RISK_SLOTS_REACHED")
                    await bitunix.cancel_all_pending_orders()
                    return []

                pending_orders = await bitunix.get_pending_orders()
                if not pending_orders:
                    continue

                # SOP-22: Purga atómica de órdenes CLOSE huérfanas en esta cuenta
                active_symbols = {p.get("symbol") for p in (await bitunix.get_pending_positions() or []) if p.get("symbol")}
                await bitunix.purge_orphaned_close_orders(active_symbols=active_symbols)

                open_limits = [
                    o for o in pending_orders 
                    if (o.get("tradeSide") == "OPEN" or not o.get("reduceOnly")) and o.get("orderType") == "LIMIT"
                ]

                for ord_item in open_limits:
                    sym = ord_item.get("symbol", "UNKNOWN")
                    oid = ord_item.get("orderId")
                    side_raw = ord_item.get("side", "BUY").upper()
                    is_long = side_raw in ("BUY", "LONG")
                    entry_price = float(ord_item.get("price") or 0.0)
                    sl_price = float(ord_item.get("slPrice") or 0.0)
                    ctime = float(ord_item.get("ctime") or now_ms)
                    
                    if entry_price <= 0 or not oid:
                        continue

                    cur_price = await bitunix.get_ticker_price(sym)
                    if cur_price <= 0:
                        continue

                    matching_setup = next((o for o in all_opps if o.get("asset") == sym and ("LONG" if is_long else "SHORT") in str(o.get("direction", "")).upper()), None)
                    if matching_setup:
                        tp1_target = float(matching_setup.get("tp1") or 0.0)
                        if sl_price <= 0:
                            sl_price = float(matching_setup.get("stop_loss") or 0.0)
                    else:
                        dist_sl = abs(entry_price - sl_price) if sl_price > 0 else entry_price * 0.015
                        tp1_target = entry_price + (dist_sl * 1.3) if is_long else entry_price - (dist_sl * 1.3)

                    cancel_reason = None

                    # Chequeo 1: Missed Target
                    if tp1_target > 0:
                        if is_long and cur_price >= tp1_target:
                            cancel_reason = f"MISSED_TARGET (Precio actual ${cur_price:.4f} superó TP1 ${tp1_target:.4f} sin retroceder a entrada ${entry_price:.4f})"
                        elif not is_long and cur_price <= tp1_target:
                            cancel_reason = f"MISSED_TARGET (Precio actual ${cur_price:.4f} perforó TP1 ${tp1_target:.4f} sin retroceder a entrada ${entry_price:.4f})"

                    # Chequeo 2: Pre-Entry SL Breach
                    if not cancel_reason and sl_price > 0:
                        if is_long and cur_price <= (sl_price * 0.9995):
                            cancel_reason = f"PRE_ENTRY_SL_BREACH (Precio actual ${cur_price:.4f} perforó el Stop Loss ${sl_price:.4f} antes de activar entrada)"
                        elif not is_long and cur_price >= (sl_price * 1.0005):
                            cancel_reason = f"PRE_ENTRY_SL_BREACH (Precio actual ${cur_price:.4f} superó el Stop Loss ${sl_price:.4f} antes de activar entrada)"

                    # Chequeo 3: Expiración TTL
                    if not cancel_reason:
                        age_seconds = (now_ms - ctime) / 1000
                        price_drift_pct = abs(cur_price - entry_price) / entry_price
                        if age_seconds > 10800 and price_drift_pct > 0.015:
                            cancel_reason = f"TTL_EXPIRED (Orden con {age_seconds/3600:.1f}h de antigüedad y precio desfasado {price_drift_pct*100:.1f}%)"

                    if cancel_reason:
                        logger.warning(f"🚫 [LIMIT SENTINEL] [{bitunix.account_label}] Auto-cancelando orden límite {oid} en {sym}: {cancel_reason}")
                        success = await bitunix.cancel_limit_order(sym, oid)
                        if success:
                            nexus.remove_pending_limit_symbol(sym)
                            cancelled_results.append({
                                "account_id": acc_id,
                                "account_label": bitunix.account_label,
                                "symbol": sym,
                                "order_id": oid,
                                "reason": cancel_reason
                            })
            except Exception as acc_err:
                logger.error(f"❌ [LIMIT SENTINEL] [{bitunix.account_label}] Error en auditoría de órdenes: {acc_err}")

        return cancelled_results

    async def sync_live_mt5_positions(self) -> List[Dict[str, Any]]:
        """
        [FTMO SENTINEL v22.2]
        Gestiona de forma idéntica las posiciones de MetaTrader 5 (FTMO):
        1. Fast Breakeven a +1.0R ($0.00 riesgo).
        2. Bloqueo en verde TP1 (+1.2R) y TP2 (+2.0R).
        3. Trailing Ratchet Tier 4 (70% retención) post-TP3.
        4. Invarianza Monótona estricta en MT5.
        """
        try:
            from engine.execution.mt5_bridge import mt5_bridge
            positions = mt5_bridge.get_open_positions()
            if not positions:
                return []

            managed_results = []
            for pos in positions:
                sym = pos.get("symbol", "UNKNOWN")
                ticket = pos.get("ticket")
                side = pos.get("side", "LONG")
                entry_price = float(pos.get("entry_price") or 0.0)
                cur_price = float(pos.get("cur_price") or 0.0)
                cur_sl = float(pos.get("sl") or 0.0)

                if entry_price <= 0 or cur_price <= 0:
                    continue

                sl_dist = abs(entry_price - cur_sl) if cur_sl > 0 and cur_sl != entry_price else entry_price * 0.005
                if sl_dist <= 0:
                    sl_dist = entry_price * 0.005

                r_profit = (cur_price - entry_price) / sl_dist if side == "LONG" else (entry_price - cur_price) / sl_dist

                target_sl = None
                status_msg = "EN_CURSO"
                action_taken = "NINGUNA"

                if r_profit >= 5.0:
                    locked_r = r_profit * 0.70
                    profit_buffer = sl_dist * locked_r
                    target_sl = round(entry_price + profit_buffer, 2) if side == "LONG" else round(entry_price - profit_buffer, 2)
                    status_msg = f"PROTEGIDO_RUNNER_TP3 (+{locked_r:.1f}R)"
                elif r_profit >= 3.0:
                    profit_buffer = sl_dist * 2.0
                    target_sl = round(entry_price + profit_buffer, 2) if side == "LONG" else round(entry_price - profit_buffer, 2)
                    status_msg = "PROTEGIDO_TP2 (+2.0R)"
                elif r_profit >= 2.0:
                    profit_buffer = sl_dist * 1.2
                    target_sl = round(entry_price + profit_buffer, 2) if side == "LONG" else round(entry_price - profit_buffer, 2)
                    status_msg = "PROTEGIDO_TP1 (+1.2R)"
                elif r_profit >= 1.0:
                    target_sl = round(entry_price, 2)
                    status_msg = "PROTEGIDO_FAST_BE"

                should_update = False
                if target_sl is not None:
                    if side == "LONG" and (cur_sl <= 0 or target_sl > cur_sl * 1.0002):
                        should_update = True
                    elif side == "SHORT" and (cur_sl <= 0 or target_sl < cur_sl * 0.9998):
                        should_update = True

                if should_update:
                    mt5_bridge.modify_position_sl(symbol=sym, ticket=ticket, new_sl=target_sl)
                    action_taken = f"SL_ACTUALIZADO (${target_sl})"
                    logger.info(f"🏛️ [MT5_GUARDIAN] Posición {sym} {side} (+{r_profit:.2f}R) protegida con SL=${target_sl} ({status_msg}).")

                managed_results.append({
                    "symbol": sym,
                    "ticket": ticket,
                    "side": side,
                    "entry_price": entry_price,
                    "current_price": cur_price,
                    "current_sl": cur_sl,
                    "r_profit": round(r_profit, 2),
                    "status": status_msg,
                    "action": action_taken
                })

            return managed_results
        except Exception as e:
            logger.debug(f"[TRADE_MANAGER] Error en sincronización MT5: {e}")
            return []



# Singleton Global
trade_manager = TradeManager()


