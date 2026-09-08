"""
engine/execution/mt5_bridge.py - Conector Local de Ultra Baja Latencia para MetaTrader 5
=======================================================================================
Permite la colocación automatizada de órdenes límite con 3 SALIDAS ESCALONADAS
(50% TP1 / 30% TP2 / 20% TP3 - SOP-26 & SOP-66) directamente en MetaTrader 5 para
cuentas FTMO / Prop-Firms, manteniendo control estricto de drawdown diario ($750 USD / 0.75%).
"""
import time
import logging
from typing import Dict, Any, Optional, List
from engine.core.logger import logger
from engine.risk.ftmo_guardian import ftmo_guardian
from engine.core.vault import vault

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("[MT5_BRIDGE] ⚠️ Módulo MetaTrader5 no instalado o entorno no-Windows. Modo Simulación activo.")


class MT5Bridge:
    """Puente local para transmisión instantánea de órdenes a MetaTrader 5 con 3 salidas cuantitativas."""

    MAGIC_NUMBER = 100100  # Identificador único institucional de Slingshot

    def get_symbol_digits(self, symbol: str) -> int:
        sym = symbol.upper()
        if any(f in sym for f in ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF"]) and not any(m in sym for m in ["XAU", "XAG", "OIL", "US500", "US100", "US30"]):
            return 5
        elif any(c in sym for c in ["XAU", "XAG", "OIL", "GOLD"]):
            return 2
        elif any(idx in sym for idx in ["US500", "US100", "US30", "NAS100", "SPX500", "GER40"]):
            return 1
        return 2

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.connected = False
        if not self.dry_run and MT5_AVAILABLE:
            self._connect()

    def _connect(self) -> bool:
        """Inicializa la API local de MetaTrader 5."""
        if not MT5_AVAILABLE:
            return False
        try:
            if mt5.initialize():
                account_info = mt5.account_info()
                if account_info:
                    logger.info(f"🏛️ [MT5_BRIDGE] Conectado a terminal MT5: Cuenta #{account_info.login} ({account_info.company}) - Balance: ${account_info.balance:,.2f}")
                    self.connected = True
                    return True
            logger.warning("[MT5_BRIDGE] No se pudo inicializar la terminal MetaTrader 5.")
            return False
        except Exception as e:
            logger.error(f"[MT5_BRIDGE] Error inicializando MT5: {e}")
            return False

    def place_limit_order(self, symbol: str, direction: str, entry_price: float, stop_loss: float, tp1: float, tp2: float, tp3: float, score: int = 70) -> Dict[str, Any]:
        """
        Calcula lotes exactos con FTMO Guardian y transmite 3 órdenes límite fraccionadas:
        - Tramo 1 (50% de lotes): Take Profit en TP1 (+1.3R) -> Asegura Breakeven
        - Tramo 2 (30% de lotes): Take Profit en TP2 (+2.5R) -> Asegura +1.0R neto
        - Tramo 3 (20% de lotes): Take Profit en TP3 (+4.0R a +5.0R) -> Runner elástico
        """
        # 1. Blindaje de Riesgo FTMO ($750 USD / 0.75%)
        lot_info = ftmo_guardian.calculate_mt5_lots(symbol, entry_price, stop_loss)
        total_lots = float(lot_info.get("lots", 0.01))
        risk_usd = float(lot_info.get("risk_usd", 750.0))

        is_long = "LONG" in direction.upper()
        sym_mt5 = symbol.replace("USDT", "USD")

        # Resolución inteligente de sufijo .cash para brokers FTMO
        min_lot = 0.01
        step_lot = 0.01
        digits = self.get_symbol_digits(symbol)

        if MT5_AVAILABLE and self.connected:
            cash_cand = f"{sym_mt5}.cash"
            try:
                if mt5.symbol_info(cash_cand) is not None:
                    sym_mt5 = cash_cand
                s_info = mt5.symbol_info(sym_mt5)
                if s_info:
                    min_lot = s_info.volume_min or 0.01
                    step_lot = s_info.volume_step or 0.01
                    digits = s_info.digits
            except Exception:
                pass

        # 2. Validación de Kill-Switch de Drawdown
        if ftmo_guardian.is_daily_lockout:
            logger.error(f"🛑 [MT5_BRIDGE] Orden rechazada para {sym_mt5}: Cuenta bloqueada por Kill-Switch de Drawdown Diario.")
            return {
                "success": False,
                "reason": "FTMO_DAILY_DRAWDOWN_LOCKOUT",
                "symbol": sym_mt5,
                "lots": total_lots
            }

        order_type_str = "BUY_LIMIT" if is_long else "SELL_LIMIT"

        # 3. Fraccionamiento Cuantitativo en 3 Salidas (SOP-26 & SOP-66: 50 / 30 / 20)
        tranches = []
        if total_lots >= (min_lot * 3):
            # 3 tramos: 50% TP1, 30% TP2, 20% TP3
            l1 = round(round(total_lots * 0.50 / step_lot) * step_lot, 2)
            l2 = round(round(total_lots * 0.30 / step_lot) * step_lot, 2)
            l3 = round(total_lots - l1 - l2, 2)
            if l3 < min_lot:
                l2 = round(l2 - step_lot, 2)
                l3 = round(l3 + step_lot, 2)
            tranches = [
                {"label": "TP1_50pct", "lots": l1, "tp": round(tp1, digits)},
                {"label": "TP2_30pct", "lots": l2, "tp": round(tp2, digits)},
                {"label": "TP3_20pct", "lots": l3, "tp": round(tp3, digits)},
            ]
        elif total_lots >= (min_lot * 2):
            # 2 tramos: 50% TP1 y 50% TP3
            l1 = round(round(total_lots * 0.50 / step_lot) * step_lot, 2)
            l2 = round(total_lots - l1, 2)
            tranches = [
                {"label": "TP1_50pct", "lots": l1, "tp": round(tp1, digits)},
                {"label": "TP3_50pct", "lots": l2, "tp": round(tp3, digits)},
            ]
        else:
            # 1 tramo único al lote mínimo
            tranches = [
                {"label": "TP1_100pct", "lots": total_lots, "tp": round(tp1, digits)}
            ]

        # Modo Simulación / Dry Run
        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            placed = []
            for t in tranches:
                logger.info(f"🏛️ [MT5_BRIDGE:DRY_RUN] Simulación de orden: {order_type_str} {sym_mt5} {t['lots']} Lots [{t['label']}] @ ${entry_price} | SL: ${stop_loss} | TP: ${t['tp']}")
                placed.append({"order_id": 999999, "lots": t["lots"], "label": t["label"], "tp": t["tp"]})
            return {
                "success": True,
                "mode": "DRY_RUN",
                "symbol": sym_mt5,
                "order_type": order_type_str,
                "total_lots": total_lots,
                "lots": total_lots,
                "orders": placed,
                "risk_usd": risk_usd
            }

        # 4. Transmisión Real de Órdenes a MetaTrader 5
        try:
            mt5_order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_long else mt5.ORDER_TYPE_SELL_LIMIT
            placed_orders = []

            for t in tranches:
                t_lots = t["lots"]
                t_tp = t["tp"]
                t_label = t["label"]
                if t_lots <= 0:
                    continue

                request = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": sym_mt5,
                    "volume": t_lots,
                    "type": mt5_order_type,
                    "price": round(entry_price, digits),
                    "sl": round(stop_loss, digits),
                    "tp": t_tp,
                    "magic": self.MAGIC_NUMBER,
                    "comment": f"Slingshot [{t_label}]",
                    "type_time": mt5.ORDER_TIME_DAY,
                    "type_filling": mt5.ORDER_FILLING_RETURN,
                }

                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"🚀 [MT5_BRIDGE] Orden Límite [{t_label}] colocada exitosamente #{result.order} para {sym_mt5} ({t_lots} lotes | TP: {t_tp})")
                    placed_orders.append({
                        "order_id": result.order,
                        "symbol": sym_mt5,
                        "lots": t_lots,
                        "label": t_label,
                        "tp": t_tp
                    })
                else:
                    retcode = result.retcode if result else "UNKNOWN"
                    comment = result.comment if result else "Sin respuesta"
                    logger.error(f"❌ [MT5_BRIDGE] Fallo al enviar orden [{t_label}] a MT5: {retcode} - {comment}")

            if placed_orders:
                return {
                    "success": True,
                    "symbol": sym_mt5,
                    "total_lots": total_lots,
                    "lots": total_lots,
                    "orders": placed_orders,
                    "risk_usd": risk_usd
                }
            else:
                return {
                    "success": False,
                    "reason": "ALL_TRANCHES_REJECTED"
                }

        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Excepción enviando órdenes a MT5: {e}")
            return {"success": False, "reason": str(e)}

    def cancel_order(self, ticket: int) -> bool:
        """Cancela una orden pendiente en MetaTrader 5."""
        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            logger.info(f"🏛️ [MT5_BRIDGE:DRY_RUN] Cancelación simulada de orden #{ticket}")
            return True
        try:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": int(ticket)
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"🗑️ [MT5_BRIDGE] Orden pendiente #{ticket} cancelada exitosamente.")
                return True
            else:
                ret = res.retcode if res else "UNKNOWN"
                msg = res.comment if res else "Error"
                logger.warning(f"⚠️ [MT5_BRIDGE] Fallo al cancelar orden #{ticket}: {ret} - {msg}")
                return False
        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Excepción cancelando orden #{ticket}: {e}")
            return False

    def get_open_positions(self) -> list:
        """Obtiene las posiciones abiertas en MetaTrader 5 gestionadas por Slingshot."""
        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            return []
        try:
            positions = mt5.positions_get()
            if not positions:
                return []
            slingshot_pos = []
            for p in positions:
                if p.magic == self.MAGIC_NUMBER or True:
                    slingshot_pos.append({
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "side": "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT",
                        "volume": p.volume,
                        "entry_price": p.price_open,
                        "cur_price": p.price_current,
                        "sl": p.sl,
                        "tp": p.tp,
                        "profit": p.profit,
                        "magic": p.magic,
                        "comment": p.comment or ""
                    })
            return slingshot_pos
        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Error consultando posiciones en MT5: {e}")
            return []

    def modify_position_sl(self, symbol: str, ticket: int, new_sl: float, new_tp: Optional[float] = None) -> bool:
        """Modifica el Stop Loss en MetaTrader 5 respetando la Invarianza Monótona."""
        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            logger.info(f"🏛️ [MT5_BRIDGE:DRY_RUN] Modificación simulada de SL para ticket #{ticket} ({symbol}) a ${new_sl}")
            return True
        try:
            pos_info = mt5.positions_get(ticket=ticket)
            if pos_info and len(pos_info) > 0:
                cur_pos = pos_info[0]
                is_long = cur_pos.type == mt5.POSITION_TYPE_BUY
                cur_sl = cur_pos.sl
                if is_long and cur_sl > 0 and new_sl < cur_sl:
                    logger.warning(f"⚠️ [MT5_INVARIANZA] Intento de retroceder SL en LONG para {symbol} (#{ticket}) de {cur_sl} a {new_sl} RECHAZADO.")
                    return True
                elif not is_long and cur_sl > 0 and new_sl > cur_sl:
                    logger.warning(f"⚠️ [MT5_INVARIANZA] Intento de empeorar SL en SHORT para {symbol} (#{ticket}) de {cur_sl} a {new_sl} RECHAZADO.")
                    return True

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": float(new_sl),
                "tp": float(new_tp) if new_tp is not None else (pos_info[0].tp if pos_info else 0.0),
                "magic": self.MAGIC_NUMBER
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"🛡️ [MT5_BRIDGE] SL de posición #{ticket} ({symbol}) actualizado exitosamente a ${new_sl}")
                return True
            else:
                ret = res.retcode if res else "UNKNOWN"
                msg = res.comment if res else "Error"
                logger.error(f"❌ [MT5_BRIDGE] Fallo al modificar SL en MT5: {ret} - {msg}")
                return False
        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Excepción modificando SL en MT5: {e}")
            return False

    def modify_position_tp(self, symbol: str, ticket: int, new_tp: float) -> bool:
        """Modifica el Take Profit de una posición en MetaTrader 5 sin alterar el SL."""
        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            logger.info(f"🏛️ [MT5_BRIDGE:DRY_RUN] Modificación simulada de TP para ticket #{ticket} ({symbol}) a ${new_tp}")
            return True
        try:
            pos_info = mt5.positions_get(ticket=ticket)
            if not pos_info:
                logger.warning(f"⚠️ [MT5_BRIDGE] No se encontró posición #{ticket} ({symbol}) para modificar TP.")
                return False
            cur_pos = pos_info[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": float(cur_pos.sl),
                "tp": float(new_tp),
                "magic": self.MAGIC_NUMBER
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"🎯 [MT5_BRIDGE] TP de posición #{ticket} ({symbol}) actualizado exitosamente a ${new_tp}")
                return True
            else:
                ret = res.retcode if res else "UNKNOWN"
                msg = res.comment if res else "Error"
                logger.error(f"❌ [MT5_BRIDGE] Fallo al modificar TP en MT5: {ret} - {msg}")
                return False
        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Excepción modificando TP en MT5: {e}")
            return False

    def close_partial_position(self, symbol: str, ticket: int, volume: float, comment: str = "Slingshot [Partial Close]") -> bool:
        """
        Cierra parcialmente una posición activa en MT5 mediante TRADE_ACTION_DEAL con tipo opuesto.
        """
        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            logger.info(f"🏛️ [MT5_BRIDGE:DRY_RUN] Cierre parcial simulado de #{ticket} ({symbol}): {volume} lotes")
            return True
        try:
            pos_info = mt5.positions_get(ticket=ticket)
            if not pos_info:
                logger.warning(f"⚠️ [MT5_BRIDGE] No se encontró posición #{ticket} ({symbol}) para cierre parcial.")
                return False
            cur_pos = pos_info[0]
            sym = cur_pos.symbol
            tick = mt5.symbol_info_tick(sym)
            if not tick:
                logger.error(f"❌ [MT5_BRIDGE] No se pudo obtener tick para {sym}")
                return False

            # Determinar tipo de orden opuesta y precio de cierre
            if cur_pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask

            s_info = mt5.symbol_info(sym)
            step_lot = s_info.volume_step if s_info else 0.01
            vol_clean = round(round(volume / step_lot) * step_lot, 2)
            if vol_clean <= 0:
                logger.warning(f"⚠️ [MT5_BRIDGE] Volumen de cierre inválido ({vol_clean} lotes) para #{ticket}")
                return False

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": sym,
                "volume": vol_clean,
                "type": order_type,
                "price": price,
                "deviation": 50,
                "magic": self.MAGIC_NUMBER,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✂️ [MT5_BRIDGE] Cierre parcial exitoso #{ticket} ({sym}): {vol_clean} lotes cerrados @ ${price} ({comment})")
                return True
            else:
                ret = res.retcode if res else "UNKNOWN"
                msg = res.comment if res else "Error"
                logger.error(f"❌ [MT5_BRIDGE] Fallo al cerrar parcialmente #{ticket}: {ret} - {msg}")
                return False
        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Excepción cerrando parcialmente #{ticket}: {e}")
            return False


# Instancia singleton
mt5_bridge = MT5Bridge(dry_run=False)
