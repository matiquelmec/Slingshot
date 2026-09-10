import os
import json
"""

engine/workers/trade_manager.py A,?? Trailing Stop Estructural Slingshot v1.0

===========================================================================

Gestiona el ciclo de vida de seAAales activas despuAAcs de su activaciAA3n.

Implementa un Trailing Stop inteligente que sigue la estructura del mercado

(swing lows/highs y Order Blocks) en lugar de porcentajes fijos.



Fases del ciclo de vida de una seAAal:

  ACTIVE   A??T Precio entre entrada y TP1. SL fijo en posiciAA3n original.

  BREAKEVENA??T Precio tocAA3 TP1. SL movido a precio de entrada + buffer ATR.

             Se cierra el 40% de la posiciAA3n (parcial TP1).

  TRAILING A??T Precio superAA3 TP2. SL sigue el AAltimo swing estructural.

             Se cierra el 30% adicional de la posiciAA3n (parcial TP2).

  CLOSED   A??T Precio tocAA3 TP3 o SL fue hit. Ciclo completado.

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

    Worker en segundo plano que monitorea las seAAales activas del MemoryStore

    y actualiza el SL de forma estructural segAAn la evoluciAA3n del precio.

    """



    POLL_INTERVAL_SECONDS = 30  # EvalAAa cada 30 segundos

    ATR_BE_BUFFER = 0.3         # 30% del ATR como buffer sobre el precio de entrada en BE



    def __init__(self):
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._last_active_positions: Dict[str, set] = {}
        self._mt5_partial_states: Dict[str, Any] = self._load_mt5_partial_states()

    def _load_mt5_partial_states(self) -> Dict[str, Any]:
        path = r"C:\Slingshot\data\mt5_partial_states.json"
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_mt5_partial_states(self):
        path = r"C:\Slingshot\data\mt5_partial_states.json"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._mt5_partial_states, f, indent=2)
        except Exception as e:
            logger.debug(f"[TRADE_MANAGER] Error guardando mt5_partial_states: {e}")



    def start(self):

        logger.info("[TRADE_MANAGER] Iniciando Trailing Stop Estructural v1.0...")

        self._task = asyncio.create_task(self._management_loop())



    def stop(self):

        logger.info("[TRADE_MANAGER] Deteniendo gestor de trades...")

        self._stop_event.set()



    # A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

    # LOOP PRINCIPAL

    # A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,



    async def _management_loop(self):

        """Ciclo principal: revisa seAAales activas y sincroniza posiciones en Bitunix cada 30 segundos."""

        await asyncio.sleep(10)  # Espera inicial para que el sistema arranque

        while not self._stop_event.is_set():

            try:

                # 1. Procesar seAAales del sistema local

                await self._process_active_signals()

                # 2. Sincronizar y proteger posiciones reales en vivo en Bitunix

                await self.sync_live_bitunix_positions()

                # 3. Auditar e invalidar AA3rdenes lAA-mite huAAcrfanas/riesgosas en Bitunix

                await self.sync_live_bitunix_pending_orders()

                # 4. Sincronizar y proteger posiciones de MetaTrader 5 (FTMO)

                await self.sync_live_mt5_positions()
                await self.sync_live_mt5_pending_orders()

            except Exception as e:

                logger.error(f"[TRADE_MANAGER] Error en loop: {e}")

            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)



    async def _process_active_signals(self):

        """Itera sobre las seAAales y gestiona tanto AA3rdenes PENDING como activas (ACTIVE/BREAKEVEN/TRAILING)."""

        signals = await store.get_signals(status=None)

        

        # 1. Monitoreo e InvalidaciAA3n de AA3rdenes PENDING

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

        EvalAAa si una orden PENDING tocAA3 entrada (pasa a FILLED/ACTIVE) 

        o si el precio se escapAA3 y superAA3 TP1 sin tocar entrada (pasa a EXPIRED_MISSED).

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



        # Caso A: El precio tocAA3 la entrada -> Activar orden

        entry_touched = (is_long and low_price <= entry_price) or (not is_long and high_price >= entry_price)

        if entry_touched:

            signal["status"] = "FILLED"

            signal["filled_at"] = df["timestamp"].iloc[-1]

            signal["trailing_phase"] = "ACTIVE"

            await store.save_signal(signal)

            logger.info(f"AA [TRADE_MANAGER] Orden PENDING {asset} LLENADA (@ ${entry_price:.4f}). Estado -> FILLED.")

            return



        # Caso B: El precio se escapAA3 y alcanzAA3 TP1 sin haber dado entrada -> Invalidar

        missed_tp1 = (is_long and high_price >= tp1_price) or (not is_long and low_price <= tp1_price)

        if missed_tp1:

            signal["status"] = "EXPIRED_MISSED"

            signal["rejection_reason"] = f"El precio alcanzAA3 TP1 (${tp1_price:.4f}) sin retroceder al nivel de entrada (${entry_price:.4f}). Setup descartado."

            await store.save_signal(signal)

            from engine.execution.nexus import nexus

            nexus.remove_pending_limit_symbol(asset)

            logger.info(f"AA?AA_A,A? [TRADE_MANAGER] Orden PENDING {asset} EXPIRADA (Objetivo alcanzado sin dar entrada).")

            return



        # Caso C: El precio rompiAA3 el Stop Loss antes de entrar

        sl_broken = (is_long and low_price < sl_price) or (not is_long and high_price > sl_price)

        if sl_broken:

            signal["status"] = "INVALIDATED_BROKEN"

            signal["rejection_reason"] = f"Estructura invalidada antes de la activaciAA3n (SL ${sl_price:.4f} perforado)."

            await store.save_signal(signal)

            from engine.execution.nexus import nexus

            nexus.remove_pending_limit_symbol(asset)

            logger.info(f"A,??~ [TRADE_MANAGER] Orden PENDING {asset} INVALIDADA (SL roto previo a entrada).")



    def is_megacap(self, symbol: str) -> bool:
        """Determina si un activo es Mega-Cap institucional (BTC, ETH, SOL, XAU, etc.)."""
        s = (symbol or "").upper()
        return any(m in s for m in ["BTC", "ETH", "SOL", "AVAX", "LINK", "XRP", "BNB", "XAU", "XAG"])



    # A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

    # LA?oGICA CENTRAL DE TRAILING

    # A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,



    async def _update_signal_trailing(self, signal: Dict[str, Any]):

        """

        EvalAAa un trade activo y actualiza su SL segAAn la fase actual.

        Descarga las AAltimas velas del activo para calcular la estructura real.

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



        # A??,A??, Fase 1: ACTIVE A??T FAST BREAKEVEN (Adaptativo: 1.2R Megas / 1.0R Alts) A??,A??,

        if phase == "ACTIVE":

            initial_sl = float(signal.get("initial_stop_loss", current_sl))

            risk_dist = abs(entry_price - initial_sl)

            be_multiplier = 1.2 if self.is_megacap(asset) else 1.0

            be_fast_trigger = entry_price + (risk_dist * be_multiplier) if is_long else entry_price - (risk_dist * be_multiplier)



            # CondiciAA3n A: Toca Fast BE (+1.2R Megas / +1.0R Alts)

            fast_be_hit = (is_long and current_price >= be_fast_trigger) or (not is_long and current_price <= be_fast_trigger)

            # CondiciAA3n B: Toca TP1 (+1.5R)

            tp1_hit = (is_long and current_price >= tp1) or (not is_long and current_price <= tp1)



            if fast_be_hit or tp1_hit:

                new_sl = self._calculate_breakeven_sl(entry_price, atr_val, is_long)

                if self._sl_improved(current_sl, new_sl, is_long):

                    trig_label = "TP1" if tp1_hit else f"Fast BE (+{be_multiplier:.1f}R)"

                    await self._apply_sl_update(

                        signal,

                        new_sl,

                        "BREAKEVEN",

                        f"A,A_ {trig_label} alcanzado @ ${current_price:.4f}. SL protegido a entrada con Fee Absorber (${new_sl:.4f})"

                    )

                    logger.info(f"A,?AA_A,A? [TRADE_MANAGER] {asset} -> Fast BE (+{be_multiplier:.1f}R) activado: SL movido a {new_sl:.6f}")

            return



        # A??,A??, Fase 2: BREAKEVEN A??T TRAILING A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

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



        # A??,A??, Fase 3: TRAILING activo A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

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



            # Actualizar trailing: buscar nuevo swing estructural mAAs favorable

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

        Encuentra el SL estructural mAAs favorable usando:

        1. El swing low/high mAAs reciente de las AAltimas `lookback` velas.

        2. Un buffer de 0.5 * ATR debajo/encima del swing para dar espacio.

        """

        try:

            recent = df.iloc[-lookback:]



            if is_long:

                # Para LONG: buscar el swing low mAAs reciente que estAAc por debajo del precio actual

                swing_low = recent["low"].min()

                structural_sl = round(swing_low - (atr * 0.5), 8)

                # Sanity check: el SL estructural no puede estar mAAs del 5% del precio por debajo

                max_dist = current_price * 0.05

                if (current_price - structural_sl) > max_dist:

                    return None

                return structural_sl

            else:

                # Para SHORT: buscar el swing high mAAs reciente que estAAc por encima del precio actual

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

        Verifica que el nuevo SL sea mejor (mAAs favorable) que el anterior.

        El Trailing Stop NUNCA puede retroceder.

        """

        if is_long:

            return new_sl > old_sl   # Para LONG: el SL debe subir

        else:

            return new_sl < old_sl   # Para SHORT: el SL debe bajar



    def _is_move_confirmed(self, df: pd.DataFrame, level: float, is_long: bool) -> tuple:

        """

        Triple confirmaciAA3n institucional antes de mover el SL.

        Requiere las 3 simultAAneamente para evitar reaccionar a mechas falsas.



        1. CIERRE DE VELA: la AAltima vela cerrAA3 mAAs allAA del nivel (no solo lo tocAA3)

        2. VOLUMEN:        el RVOL de esa vela es >= 1.3x el promedio de 20 velas

        3. BOS ESTRUCTURAL: el precio dejAA3 un nuevo High/Low mayor que el anterior



        Retorna (confirmed: bool, reason: str)

        """

        try:

            if len(df) < 3:

                return False, "Datos insuficientes"



            last  = df.iloc[-1]   # Vela mAAs reciente (puede estar abierta)

            prev  = df.iloc[-2]   # Vela anterior cerrada A,?? la que confirma

            prev2 = df.iloc[-3]   # PenAAltima A,?? para comparar BOS



            close_prev = float(prev["close"])

            high_prev  = float(prev["high"])

            low_prev   = float(prev["low"])

            high_prev2 = float(prev2["high"])

            low_prev2  = float(prev2["low"])



            # A??,A??, 1. ConfirmaciAA3n de cierre A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

            if is_long:

                candle_confirmed = close_prev > level

            else:

                candle_confirmed = close_prev < level



            if not candle_confirmed:

                return False, f"Vela cerro en {close_prev:.4f}, nivel {level:.4f} no superado"



            # A??,A??, 2. ConfirmaciAA3n de volumen (RVOL >= 1.3x) A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

            vol_mean = df["volume"].iloc[-21:-1].mean()

            vol_prev = float(prev["volume"])

            rvol = vol_prev / vol_mean if vol_mean > 0 else 1.0



            if rvol < 1.3:

                return False, f"Volumen insuficiente: RVOL {rvol:.2f}x (minimo 1.3x)"



            # A??,A??, 3. BOS Estructural (Higher High / Lower Low) A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

            if is_long:

                bos_confirmed = high_prev > high_prev2   # Nuevo mAAximo mAAs alto

            else:

                bos_confirmed = low_prev < low_prev2     # Nuevo mAA-nimo mAAs bajo



            if not bos_confirmed:

                return False, "Sin Break of Structure confirmado"



            return True, f"Cierre OK + RVOL {rvol:.2f}x + BOS confirmado"



        except Exception as e:

            logger.warning(f"[TRADE_MANAGER] Error en _is_move_confirmed: {e}")

            # En caso de error, permitimos el movimiento para no bloquear el sistema

            return True, "Bypass por error de calculo"



    # A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,

    # PERSISTENCIA & SINCRONIZACIA?oN CON EXCHANGE (BITUNIX)

    # A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,A??,



    async def _apply_sl_update(

        self,

        signal: Dict[str, Any],

        new_sl: float,

        new_phase: str,

        reason: str

    ):

        """Persiste el nuevo SL y fase en el MemoryStore y ejecuta la modificaciAA3n en Bitunix."""

        asset = signal.get("asset", signal.get("symbol", "UNKNOWN"))

        signal["stop_loss"]      = new_sl

        signal["trailing_phase"] = new_phase

        signal["trailing_reason"] = reason

        signal["status"] = "CLOSED" if new_phase == "CLOSED" else signal.get("status", "ACTIVE")



        # AAAadir al historial de trailing para auditorAA-a

        history = signal.get("trailing_history", [])

        history.append({

            "sl": new_sl,

            "phase": new_phase,

            "reason": reason,

        })

        signal["trailing_history"] = history[-10:]  # Altimos 10 movimientos



        await store.save_signal(signal)



        # A,, [BITUNIX LIVE EXCHANGE SYNC] Modificar Stop Loss real en el exchange (Multi-Cuenta SOP-45)

        try:

            from engine.execution.account_manager import AccountManager

            mgr = AccountManager()

            executors = mgr.get_all_executors(enabled_only=True)

            global_pos_id = signal.get("position_id") or signal.get("main_order_id")

            pos_map = signal.get("account_position_ids", {})

            

            for acc_id, ex in executors.items():

                try:

                    # [SSoT ENTITY ISOLATION] Priorizar ID específico de cuenta; si la señal pertenece a una cuenta específica, solo esa cuenta usa el ID global
                    if acc_id in pos_map:
                        local_pos_id = pos_map[acc_id]
                    elif signal.get("account_id"):
                        local_pos_id = global_pos_id if signal.get("account_id") == acc_id else None
                    else:
                        local_pos_id = global_pos_id

                    pos_id_arg = str(local_pos_id) if local_pos_id is not None else None
                    success = await ex.modify_position_tpsl(
                        symbol=asset,
                        position_id=pos_id_arg,
                        sl_price=new_sl
                    )

                    if success:

                        logger.info(f"AA [TRADE_MANAGER -> BITUNIX] [{ex.account_label}] SL de posiciAA3n {asset} actualizado a ${new_sl:.4f} en el exchange.")

                    else:

                        logger.debug(f"[TRADE_MANAGER] [{ex.account_label}] SL no requerido o sin posiciAA3n activa en Bitunix para {asset}")

                except Exception as acc_err:

                    logger.warning(f"[TRADE_MANAGER] [{ex.account_label}] Error al sincronizar SL: {acc_err}")

        except Exception as bitunix_err:

            logger.warning(f"[TRADE_MANAGER] Error al sincronizar SL con Bitunix: {bitunix_err}")



    async def sync_live_bitunix_positions(self) -> List[Dict[str, Any]]:

        """

        Consulta las posiciones reales abiertas en Bitunix para todas las cuentas activas (SOP-45 Multi-Cuenta),

        calcula su avance en R y actualiza automAAticamente a Breakeven aquellas que hayan avanzado >= +1.0R.

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



                # Consultar AA3rdenes TPSL activas en Bitunix para conocer el SL real configurado

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



                    # Buscar si existe una seAAal registrada para recuperar su initial_stop_loss exacto

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

                        price_breached_early_sl = (side == "LONG" and cur_price <= early_sl) or (side == "SHORT" and cur_price >= early_sl)

                        if price_breached_early_sl:

                            logger.info(f"s [SOP-25 FLASH EXIT] [{bitunix.account_label}] {sym} {side} invalidado a -0.65R y precio ya perforA3 umbral (Cur: ${cur_price} vs EarlySL: ${early_sl}). Ejecutando Cierre Inmediato a Mercado...")

                            try:

                                close_res = await bitunix.close_position_market(sym, position_id=pos_id)

                                if close_res:

                                    action_taken = f"SOP25_FLASH_MARKET_EXIT (${cur_price})"

                                    status_msg = f"SOP25_INVALIDADO_CERRADO_MERCADO (-0.65R)"

                                    from engine.execution.nexus import nexus

                                    asyncio.create_task(nexus.on_risk_released(acc_id, reason=f"SOP25_EARLY_EXIT_{sym}"))

                                    try:

                                        from engine.router.telegram_dispatcher import telegram_dispatcher

                                        asyncio.create_task(telegram_dispatcher.send_system_alert(

                                            title=f"s SOP-25: INVALIDACION TEMPRANA ({sym})",

                                            details=f"Cuenta: {bitunix.account_label}\nPosicion liquidada a mercado al -0.65R.\nPrecio Salida: ${cur_price:.4f}\nPnL Controlado.",

                                            severity="INFO"

                                        ))

                                    except Exception:

                                        pass

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

                                    continue

                            except Exception as e:

                                logger.error(f"?O [SOP-25] Error al cerrar a mercado {sym}: {e}")



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

                    elif r_profit >= 0.60 and not sl_at_be:

                        target_sl = round(entry_price - (sl_dist * 0.50), 4) if side == "LONG" else round(entry_price + (sl_dist * 0.50), 4)

                        status_msg = "SOP48_HALF_RISK_MITIGATOR (-0.5R)"



                    # SOP-68: Centinela de Remanentes PART_FILLED huAcrfanos si la posiciA3n ya avanza a favor (+0.35R)

                    if r_profit >= 0.35:

                        try:

                            po_list = await bitunix.get_pending_orders(sym)
                            for o in (po_list or []):

                                if o.get("symbol") == sym and (o.get("tradeSide") == "OPEN" or not o.get("reduceOnly")) and o.get("status") == "PART_FILLED":

                                    logger.info(f"s [SOP-68 PART_FILLED PRUNER] [{bitunix.account_label}] {sym} {side} avanza a +{r_profit:.2f}R. Purgando remanente de orden {o.get('orderId')} para evitar sobreexposicion.")

                                    await bitunix.cancel_limit_order(sym, str(o.get("orderId")))

                        except Exception as pfe:

                            logger.debug(f"[SOP-68] Error verificando remanentes para {sym}: {pfe}")




                    should_update_sl = False

                    if target_sl is not None:

                        if side == "LONG" and (cur_sl <= 0 or target_sl > cur_sl * 1.0005):

                            should_update_sl = True

                        elif side == "SHORT" and (cur_sl <= 0 or target_sl < cur_sl * 0.9995):

                            should_update_sl = True



                    if should_update_sl:

                        success = await bitunix.modify_position_tpsl(symbol=sym, position_id=pos_id, sl_price=target_sl, tp_price=None)

                        if success:

                            action_taken = f"SL_ACTUALIZADO (${target_sl})"

                            logger.info(f"dY>,?  [TRADE_MANAGER] [{bitunix.account_label}] Posicion {sym} {side} (+{r_profit:.2f}R) protegida con SL=${target_sl} ({status_msg}).")

                            if "FAST_BE" in status_msg or "PROTEGIDO" in status_msg:

                                from engine.execution.nexus import nexus

                                asyncio.create_task(nexus.on_risk_released(acc_id, reason=f"FAST_BE_ACTIVADO_{sym}"))

                        else:

                            action_taken = f"ERROR_ACTUALIZANDO_SL (${target_sl})"

                            logger.error(f"?O [TRADE_MANAGER] [{bitunix.account_label}] FallA3 actualizaciA3n de SL para {sym} en Bitunix. Reteniendo cupo de riesgo.")

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

                logger.warning(f"[TRADE_MANAGER] [{bitunix.account_label}] Error en sincronizaciAA3n de posiciones: {acc_err}")



        return managed_results



    async def sync_live_bitunix_pending_orders(self) -> List[Dict[str, Any]]:

        """

        [APEX LIMIT SENTINEL v22.0]

        Audita de forma autAA3noma todas las AA3rdenes lAA-mite pendientes en Bitunix para todas las cuentas activas.

        Ejecuta auto-cancelaciAA3n inteligente por:

          1. Objetivo alcanzado sin activaciAA3n (Missed Target Kill-Switch: precio >= TP1)

          2. InvalidaciAA3n previa de estructura (Pre-Entry SL Breach: precio <= SL)

          3. ExpiraciAA3n de tiempo de vida (TTL > 3h / 10800s desfasado)

          4. Capacidad mAAxima de riesgo (Auto-Purge si 4 posiciones en riesgo)

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

            logger.error(f"AA?' [LIMIT SENTINEL] Error obteniendo ejecutores: {e}")

            return []



        all_opps = store.get_scanner_opportunities("scalp") + store.get_scanner_opportunities("swing")

        now_ms = time.time() * 1000



        for acc_id, bitunix in executors.items():

            try:

                # 1. Regla D: Si la cuenta ya tiene 4 posiciones con riesgo, purgar AA3rdenes lAA-mite de esa cuenta

                unprotected_risk = nexus.get_unprotected_risk_count(account_id=acc_id)

                if unprotected_risk >= nexus.MAX_CONCURRENT_POSITIONS:

                    logger.info(f"dY>` [LIMIT SENTINEL] [{bitunix.account_label}] MAximo de {nexus.MAX_CONCURRENT_POSITIONS} operaciones con riesgo alcanzado ({unprotected_risk} en riesgo). Purgando lA-mites.")

                    await nexus.purge_all_pending_limit_orders(reason=f"MAX_4_RISK_SLOTS_REACHED_{acc_id}", account_id=acc_id)

                    # Protected TPs: only entry limits purged

                    continue



                pending_orders = await bitunix.get_pending_orders()

                if not pending_orders:

                    continue



                # SOP-22: Purga atA3mica de A3rdenes CLOSE huAcrfanas en esta cuenta

                active_symbols = {p.get("symbol") for p in (await bitunix.get_pending_positions() or []) if p.get("symbol")}

                await bitunix.purge_orphaned_close_orders(active_symbols=active_symbols)



                # SOP-59: Sentinela de IntervenciA3n Manual de Cliente (Anti-DesincronizaciA3n)

                prev_active = self._last_active_positions.get(acc_id, set())

                if prev_active:

                    closed_symbols = prev_active - active_symbols

                    for csym in closed_symbols:

                        try:

                            # Auditar si la Altima orden de cierre fue manual (clientId == None)

                            hist_res = await bitunix._request("GET", "/api/v1/futures/trade/get_history_orders", params={"symbol": csym, "pageSize": 3})

                            hist_orders = hist_res.get("data", {}).get("orderList", []) if isinstance(hist_res.get("data"), dict) else []

                            recent_close_time = getattr(bitunix, "_recent_algo_closes", {}).get(csym, 0)

                            is_algo_recent = (time.time() - recent_close_time) < 300

                            is_manual = not is_algo_recent and any(o.get("clientId") is None and o.get("status") == "FILLED" for o in hist_orders[:2])

                            

                            # Registro transaccional en SQLite WAL para Tear Sheets SOP-60

                            from engine.core.vault import vault

                            filled_order = next((o for o in hist_orders if o.get("status") == "FILLED"), {})

                            real_pnl_usd = float(filled_order.get("realizedPnl", 0.0) or 0.0)

                            order_side = str(filled_order.get("side", "SELL")).upper()

                            exit_label = "MANUAL_CLIENT" if is_manual else "EXIT_REACHED"

                            # EstimaciA3n de R asumiendo 2.5% de riesgo base

                            est_r = round(real_pnl_usd / 2.0, 2) if real_pnl_usd != 0 else 0.0

                            vault.record_closed_trade(

                                account_id=acc_id,

                                symbol=csym,

                                side=order_side,

                                pnl_r=est_r,

                                pnl_usd=real_pnl_usd,

                                exit_reason=exit_label

                            )



                            if is_manual:

                                logger.info(f"dY>` [SOP-59 SENTINEL] [{bitunix.account_label}] Cierre manual detectado en {csym}. Purgando A3rdenes pendientes asociadas...")

                                purged_cnt = await bitunix.cancel_all_orders_for_symbol(csym)

                                from engine.router.telegram_dispatcher import telegram_dispatcher

                                asyncio.create_task(telegram_dispatcher.send_system_alert(

                                    title=f"CIERRE MANUAL DETECTADO ({csym})",

                                    details=f"Cuenta: {bitunix.account_label}\nSe detectA3 cierre manual desde la interfaz.\nOrdenes residuales canceladas: {purged_cnt}\nMargen blindado.",

                                    severity="INFO"

                                ))

                        except Exception as manual_err:

                            logger.debug(f"[SOP-59 SENTINEL] Error auditando cierre para {csym}: {manual_err}")

                self._last_active_positions[acc_id] = active_symbols



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

                            cancel_reason = f"MISSED_TARGET (Precio actual ${cur_price:.4f} superAA3 TP1 ${tp1_target:.4f} sin retroceder a entrada ${entry_price:.4f})"

                        elif not is_long and cur_price <= tp1_target:

                            cancel_reason = f"MISSED_TARGET (Precio actual ${cur_price:.4f} perforAA3 TP1 ${tp1_target:.4f} sin retroceder a entrada ${entry_price:.4f})"



                    # Chequeo 2: Pre-Entry SL Breach

                    if not cancel_reason and sl_price > 0:

                        if is_long and cur_price <= (sl_price * 0.9995):

                            cancel_reason = f"PRE_ENTRY_SL_BREACH (Precio actual ${cur_price:.4f} perforAA3 el Stop Loss ${sl_price:.4f} antes de activar entrada)"

                        elif not is_long and cur_price >= (sl_price * 1.0005):

                            cancel_reason = f"PRE_ENTRY_SL_BREACH (Precio actual ${cur_price:.4f} superAA3 el Stop Loss ${sl_price:.4f} antes de activar entrada)"



                    # Chequeo 3: ExpiraciAA3n TTL

                    if not cancel_reason:

                        age_seconds = (now_ms - ctime) / 1000

                        price_drift_pct = abs(cur_price - entry_price) / entry_price

                        if age_seconds > 10800 and price_drift_pct > 0.015:

                            cancel_reason = f"TTL_EXPIRED (Orden con {age_seconds/3600:.1f}h de antigAAedad y precio desfasado {price_drift_pct*100:.1f}%)"



                    if cancel_reason:

                        logger.warning(f"A,A [LIMIT SENTINEL] [{bitunix.account_label}] Auto-cancelando orden lAA-mite {oid} en {sym}: {cancel_reason}")

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

                logger.error(f"AA?' [LIMIT SENTINEL] [{bitunix.account_label}] Error en auditorAA-a de AA3rdenes: {acc_err}")



        return cancelled_results



    async def sync_live_mt5_positions(self) -> List[Dict[str, Any]]:
        """
        [FTMO SENTINEL v25.0 SWING EDITION]
        Gestiona y blinda las posiciones y mActricas de MetaTrader 5 (FTMO):
        1. Ingesta continua de equidad y balance en tiempo real a ftmo_guardian.
        2. SincronizaciA3n automAtica de medianoche (00:00 Praga CE(S)T).
        3. Kill-Switch dinAmico a -3.5% de pAcrdida diaria.
        4. Centinela de fin de semana FTMO SWING (Viernes 21:00 UTC):
           - Purgado de A3rdenes lA-mite no llenadas (spread shield).
           - Auto-BE a +0.8R para protecciA3n de gaps dominicales.
           - PreservaciA3n de operaciones en curso (permitidas en Swing).
        5. Trailing inteligente de 4 fases con precisiA3n decimal adaptativa por activo.
        """
        try:
            from datetime import datetime, timezone
            import MetaTrader5 as mt5
            from engine.execution.mt5_bridge import mt5_bridge
            from engine.risk.ftmo_guardian import ftmo_guardian

            if mt5_bridge.connected:
                # 1. AlimentaciA3n continua de Equidad y Balance a FTMO Guardian
                acc_info = mt5.account_info()
                if acc_info:
                    tick = mt5.symbol_info_tick("EURUSD") or mt5.symbol_info_tick("GBPUSD")
                    server_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc) if (tick and getattr(tick, "time", None)) else datetime.now(timezone.utc)
                    
                    ftmo_guardian.evaluate_broker_day(server_dt, acc_info.balance, acc_info.equity)
                    guard_status = ftmo_guardian.update_equity(acc_info.equity, acc_info.balance)
                    
                    if guard_status.get("is_daily_lockout") and not getattr(self, "_last_lockout_notified", False):
                        self._last_lockout_notified = True
                        logger.critical(f"dY>` [FTMO_SENTINEL] {guard_status.get('lockout_reason')}")
                        try:
                            from engine.router.telegram_dispatcher import telegram_dispatcher
                            asyncio.create_task(telegram_dispatcher.send_system_alert(
                                title="KILL-SWITCH DIARIO FTMO ACTIVADO",
                                details=f"Equidad actual: ${acc_info.equity:,.2f}\nBase diaria: ${guard_status.get('daily_starting_equity'):,.2f}\nPAcrdida diaria: {guard_status.get('daily_dd_pct'):.2f}%\nNuevas A3rdenes bloqueadas por seguridad.",
                                severity="CRITICAL"
                            ))
                        except Exception:
                            pass
                    elif not guard_status.get("is_daily_lockout"):
                        self._last_lockout_notified = False

            # 2. Centinela de Fin de Semana para FTMO SWING
            now_utc = datetime.now(timezone.utc)
            is_weekend_window = (now_utc.weekday() == 4 and now_utc.hour >= 21) or (now_utc.weekday() in (5, 6))
            if is_weekend_window and getattr(ftmo_guardian, "account_type", "SWING") == "SWING" and mt5_bridge.connected:
                # Cancelar A3rdenes lA-mite no ejecutadas para no arriesgar gaps de apertura el domingo
                pending_orders = mt5.orders_get() or []
                for p_ord in pending_orders:
                    mt5_bridge.cancel_order(p_ord.ticket)
                    logger.info(f"dY>,? [SWING_GAP_SHIELD] Orden lA-mite pendiente #{p_ord.ticket} ({p_ord.symbol}) cancelada para fin de semana.")

            positions = mt5_bridge.get_open_positions() if mt5_bridge.connected else []
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

                # PrecisiA3n decimal dinAmica segAn activo
                d_prec = 5 if any(fx in sym for fx in ["GBPUSD", "EURUSD"]) else 3 if "JPY" in sym else 2

                target_sl = None
                status_msg = "EN_CURSO"
                action_taken = "NINGUNA"

                # Trailing Ratchet Estructural
                if r_profit >= 5.0:
                    locked_r = r_profit * 0.70
                    profit_buffer = sl_dist * locked_r
                    target_sl = round(entry_price + profit_buffer, d_prec) if side == "LONG" else round(entry_price - profit_buffer, d_prec)
                    status_msg = f"PROTEGIDO_RUNNER_TP3 (+{locked_r:.1f}R)"
                elif r_profit >= 3.0:
                    profit_buffer = sl_dist * 2.0
                    target_sl = round(entry_price + profit_buffer, d_prec) if side == "LONG" else round(entry_price - profit_buffer, d_prec)
                    status_msg = "PROTEGIDO_TP2 (+2.0R)"
                elif r_profit >= 2.0:
                    profit_buffer = sl_dist * 1.2
                    target_sl = round(entry_price + profit_buffer, d_prec) if side == "LONG" else round(entry_price - profit_buffer, d_prec)
                    status_msg = "PROTEGIDO_TP1 (+1.2R)"
                elif r_profit >= 1.0:
                    target_sl = round(entry_price, d_prec)
                    status_msg = "PROTEGIDO_FAST_BE"

                # ProtecciA3n de Fin de Semana Swing: si flota >= 0.8R en ventana de fin de semana, forzar BE
                if is_weekend_window and r_profit >= 0.8:
                    if target_sl is None or (side == "LONG" and target_sl < entry_price) or (side == "SHORT" and target_sl > entry_price):
                        target_sl = round(entry_price, d_prec)
                        status_msg = "SWING_WEEKEND_GAP_BE_PROTECTED"

                should_update = False
                if target_sl is not None:
                    if side == "LONG" and (cur_sl <= 0 or target_sl > cur_sl * 1.0001):
                        should_update = True
                    elif side == "SHORT" and (cur_sl <= 0 or target_sl < cur_sl * 0.9999):
                        should_update = True

                if should_update:
                    mt5_bridge.modify_position_sl(symbol=sym, ticket=ticket, new_sl=target_sl)
                    action_taken = f"SL_ACTUALIZADO (${target_sl})"
                    logger.info(f"dY>,? [MT5_GUARDIAN] Posicion {sym} {side} (+{r_profit:.2f}R) protegida con SL=${target_sl} ({status_msg}).")

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
            logger.debug(f"[TRADE_MANAGER] Error en sincronizaciA3n MT5: {e}")
            return []


    async def sync_live_mt5_pending_orders(self) -> list:
        """
        [FTMO SENTINEL v25.0 SWING EDITION]
        Audita órdenes pendientes en MetaTrader 5:
        1. Cancela órdenes límite no ejecutadas los viernes a las 21:00 UTC (Weekend Gap Protection).
        """
        try:
            from datetime import datetime, timezone
            import MetaTrader5 as mt5
            from engine.execution.mt5_bridge import mt5_bridge
            from engine.risk.ftmo_guardian import ftmo_guardian

            if not mt5_bridge.connected:
                return []

            orders = mt5.orders_get()
            if not orders:
                return []

            now_utc = datetime.now(timezone.utc)
            is_weekend = (now_utc.weekday() == 4 and now_utc.hour >= 21) or (now_utc.weekday() in (5, 6))

            cancelled = []
            for o in orders:
                ticket = o.ticket
                sym = o.symbol
                if is_weekend and getattr(ftmo_guardian, "account_type", "SWING") == "SWING":
                    success = mt5_bridge.cancel_order(ticket)
                    if success:
                        logger.info(f"🛡️ [SWING_GAP_SHIELD] Orden pendiente #{ticket} ({sym}) cancelada preventivamente para fin de semana.")
                        cancelled.append({"ticket": ticket, "symbol": sym, "reason": "WEEKEND_GAP_PROTECTION"})

            return cancelled
        except Exception as e:
            logger.debug(f"[TRADE_MANAGER] Error en auditoría de órdenes pendientes MT5: {e}")
            return []

# Singleton Global
trade_manager = TradeManager()

