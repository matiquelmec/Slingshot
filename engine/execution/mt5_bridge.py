"""
engine/execution/mt5_bridge.py — Conector Local de Ultra Baja Latencia para MetaTrader 5
=======================================================================================
Permite la colocación automatizada de órdenes límite (Buy Limit / Sell Limit)
directamente en MetaTrader 5 para cuentas FTMO / Prop-Firms, eliminando
la latencia humana y manteniendo control estricto de drawdown diario.
"""
import time
import logging
from typing import Dict, Any, Optional
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
    """Puente local para transmisión instantánea de órdenes a MetaTrader 5."""

    MAGIC_NUMBER = 100100 # Identificador único institucional de Slingshot

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
        Calcula lotes exactos con FTMO Guardian y transmite la orden límite.
        """
        # 1. Blindaje de Riesgo FTMO
        lot_info = ftmo_guardian.calculate_mt5_lots(symbol, entry_price, stop_loss)
        lots = float(lot_info.get("lots", 0.01))
        risk_usd = float(lot_info.get("risk_usd", 750.0))

        is_long = "LONG" in direction.upper()
        sym_mt5 = symbol.replace("USDT", "USD")

        # Resolución inteligente de sufijo .cash para brokers FTMO
        if MT5_AVAILABLE and self.connected:
            cash_cand = f"{sym_mt5}.cash"
            try:
                if mt5.symbol_info(cash_cand) is not None:
                    sym_mt5 = cash_cand
            except Exception:
                pass

        # 2. Validación de Kill-Switch de Drawdown
        if ftmo_guardian.is_daily_lockout:
            logger.error(f"🛑 [MT5_BRIDGE] Orden rechazada para {sym_mt5}: Cuenta bloqueada por Kill-Switch de Drawdown Diario.")
            return {
                "success": False,
                "reason": "FTMO_DAILY_DRAWDOWN_LOCKOUT",
                "symbol": sym_mt5,
                "lots": lots
            }

        # 3. Mapeo a símbolo MT5
        order_type_str = "BUY_LIMIT" if is_long else "SELL_LIMIT"

        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            logger.info(f"🛡️ [MT5_BRIDGE:DRY_RUN] Simulación de orden: {order_type_str} {sym_mt5} {lots} Lots @ ${entry_price} | SL: ${stop_loss} | TP1: ${tp1}")
            return {
                "success": True,
                "mode": "DRY_RUN",
                "symbol": sym_mt5,
                "order_type": order_type_str,
                "lots": lots,
                "price": entry_price,
                "stop_loss": stop_loss,
                "tp1": tp1,
                "risk_usd": risk_usd
            }

        # 4. Transmisión Real a MetaTrader 5
        try:
            mt5_order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_long else mt5.ORDER_TYPE_SELL_LIMIT
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": sym_mt5,
                "volume": lots,
                "type": mt5_order_type,
                "price": entry_price,
                "sl": stop_loss,
                "tp": tp1,
                "magic": self.MAGIC_NUMBER,
                "comment": f"Slingshot FTMO [{score}%]",
                "type_time": mt5.ORDER_TIME_DAY,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ [MT5_BRIDGE] Orden Límite colocada exitosamente #{result.order} para {sym_mt5}")
                return {
                    "success": True,
                    "order_id": result.order,
                    "symbol": sym_mt5,
                    "lots": lots,
                    "price": entry_price
                }
            else:
                retcode = result.retcode if result else "UNKNOWN"
                comment = result.comment if result else "Sin respuesta"
                logger.error(f"❌ [MT5_BRIDGE] Fallo al enviar orden a MT5: {retcode} - {comment}")
                return {
                    "success": False,
                    "reason": f"MT5_ERROR_{retcode}",
                    "comment": comment
                }
        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Excepción enviando orden a MT5: {e}")
            return {"success": False, "reason": str(e)}

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
                # Filtrar posiciones creadas por Slingshot (magic number) o todos los activos institucionales
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
                        "magic": p.magic
                    })
            return slingshot_pos
        except Exception as e:
            logger.error(f"❌ [MT5_BRIDGE] Error consultando posiciones en MT5: {e}")
            return []

    def modify_position_sl(self, symbol: str, ticket: int, new_sl: float, new_tp: Optional[float] = None) -> bool:
        """
        Modifica el Stop Loss en MetaTrader 5 respetando la Invarianza Monótona.
        """
        if self.dry_run or not self.connected or not MT5_AVAILABLE:
            logger.info(f"🛡️ [MT5_BRIDGE:DRY_RUN] Modificación simulada de SL para ticket #{ticket} ({symbol}) a ${new_sl}")
            return True
        try:
            # Obtener posición actual para validar invariancia
            pos_info = mt5.positions_get(ticket=ticket)
            if pos_info and len(pos_info) > 0:
                cur_pos = pos_info[0]
                is_long = cur_pos.type == mt5.POSITION_TYPE_BUY
                cur_sl = cur_pos.sl
                # Guardia de Invarianza: no permitir degradación
                if is_long and cur_sl > 0 and new_sl < cur_sl:
                    logger.warning(f"🛑 [MT5_INVARIANZA] Intento de retroceder SL en LONG para {symbol} (#{ticket}) de {cur_sl} a {new_sl} RECHAZADO.")
                    return True
                elif not is_long and cur_sl > 0 and new_sl > cur_sl:
                    logger.warning(f"🛑 [MT5_INVARIANZA] Intento de empeorar SL en SHORT para {symbol} (#{ticket}) de {cur_sl} a {new_sl} RECHAZADO.")
                    return True

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": float(new_sl),
                "tp": float(new_tp) if new_tp else (pos_info[0].tp if pos_info else 0.0),
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

# Instancia singleton
mt5_bridge = MT5Bridge(dry_run=True)
