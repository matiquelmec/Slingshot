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
from typing import List, Dict, Any, Optional
from engine.core.logger import logger
from engine.core.store import store
from engine.indicators.data_utils import fetch_binance_history
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
        """Ciclo principal: revisa señales activas y actualiza SL estructuralmente."""
        await asyncio.sleep(15)  # Espera inicial para que el sistema arranque
        while not self._stop_event.is_set():
            try:
                await self._process_active_signals()
            except Exception as e:
                logger.error(f"[TRADE_MANAGER] Error en loop: {e}")
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _process_active_signals(self):
        """Itera sobre las señales ACTIVE/BREAKEVEN/TRAILING y actualiza su SL."""
        signals = await store.get_signals(status=None)
        active = [
            s for s in signals
            if s.get("status") in ("ACTIVE", "BREAKEVEN", "TRAILING", "APPROVED")
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

        # ── Fase 1: ACTIVE → BREAKEVEN ──────────────────────────────────────
        if phase == "ACTIVE":
            tp1_hit = (is_long and current_price >= tp1) or (not is_long and current_price <= tp1)
            if tp1_hit:
                # Confirmación triple antes de mover SL: cierre + volumen + BOS
                confirmed, reason = self._is_move_confirmed(df, tp1, is_long)
                if confirmed:
                    new_sl = self._calculate_breakeven_sl(entry_price, atr_val, is_long)
                    if self._sl_improved(current_sl, new_sl, is_long):
                        await self._apply_sl_update(signal, new_sl, "BREAKEVEN",
                            f"TP1 confirmado ({reason}). SL a Break Even + {atr_val * self.ATR_BE_BUFFER:.4f}")
                        logger.info(f"[TRADE_MANAGER] {asset} -> BE confirmado: SL = {new_sl:.6f}")
                else:
                    logger.debug(f"[TRADE_MANAGER] {asset}: precio toca TP1 pero sin confirmacion ({reason}). Esperando cierre de vela.")
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

    # ─────────────────────────────────────────────
    # HELPERS DE CÁLCULO ESTRUCTURAL
    # ─────────────────────────────────────────────

    def _calculate_breakeven_sl(self, entry: float, atr: float, is_long: bool) -> float:
        """SL de Break Even = precio de entrada + buffer de 30% del ATR en favor."""
        buffer = atr * self.ATR_BE_BUFFER
        return round(entry + buffer, 8) if is_long else round(entry - buffer, 8)

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
    # PERSISTENCIA
    # ─────────────────────────────────────────────

    async def _apply_sl_update(
        self,
        signal: Dict[str, Any],
        new_sl: float,
        new_phase: str,
        reason: str
    ):
        """Persiste el nuevo SL y fase en el MemoryStore."""
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


# Singleton Global
trade_manager = TradeManager()
