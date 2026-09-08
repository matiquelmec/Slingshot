"""
engine/risk/ftmo_guardian.py — FTMO Guardian Shield v25.0 APEX TITANIUM (SWING EDITION)
========================================================================================
Protección Cuantitativa de Cuentas de Fondeo (FTMO SWING / MetaTrader 5):
1. Kill-Switch de Drawdown Diario: Hard stop preventivo a -3.5% (antes del 5% fatal de FTMO).
2. Sincronización Automática a las 00:00:00 Hora del Servidor MT5 (Praga CE(S)T): Base = max(balance, equity).
3. Gobernanza de Margen 1:30: Verificación de margen libre y apalancamiento efectivo en modalidad SWING.
4. Persistencia Atómica en JSON: Estado inmune a reinicios del bot (data/ftmo_daily_metrics.json).
5. Gestión de Fases: Fase 1 (Target +10% | Riesgo 0.75%), Fase 2 (Target +5% | Riesgo 0.50%), Fondeada (+0.35%).
"""
import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
try:
    from engine.core.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("ftmo_guardian")

try:
    from engine.indicators.tradfi_provider import TRADFI_ASSETS_CONFIG
except ImportError:
    TRADFI_ASSETS_CONFIG = {}

class FtmoGuardianShield:
    """Guardián de Capital y Reglas de Prop Firm (FTMO / MT5) — v25.0 APEX TITANIUM (SWING EDITION)."""
    
    # Límites Cuantitativos de Seguridad Dinámicos por Fase
    PHASE_CONFIGS = {
        "PHASE_1": {"risk_pct": 0.0075, "target_pct": 10.0, "daily_max_loss_pct": 3.5, "total_max_loss_pct": 7.5},
        "PHASE_2": {"risk_pct": 0.0050, "target_pct": 5.0,  "daily_max_loss_pct": 2.5, "total_max_loss_pct": 5.0},
        "FUNDED":  {"risk_pct": 0.0035, "target_pct": 0.0,  "daily_max_loss_pct": 2.0, "total_max_loss_pct": 4.5},
    }
    
    def __init__(self, account_size: float = 100000.0, phase: str = "PHASE_1", account_type: str = "SWING", state_file: Optional[str] = None):
        self.account_size = account_size
        self.phase = phase.upper() if phase.upper() in self.PHASE_CONFIGS else "PHASE_1"
        self.account_type = os.getenv("FTMO_ACCOUNT_TYPE", account_type).upper()
        self.state_file = state_file or os.path.join("C:\\Slingshot\\data", "ftmo_daily_metrics.json")
        self.current_equity = account_size
        self.daily_starting_equity = account_size
        self.peak_equity = account_size
        self.current_broker_date = ""
        self.is_daily_lockout = False
        self.lockout_reason = ""
        self.trades_today = 0
        self._load_state()
        
    @property
    def current_config(self) -> Dict[str, float]:
        return self.PHASE_CONFIGS.get(self.phase, self.PHASE_CONFIGS["PHASE_1"])

    @property
    def DAILY_DRAWDOWN_LIMIT_PCT(self) -> float:
        return self.current_config["daily_max_loss_pct"]

    @property
    def MAX_TOTAL_DRAWDOWN_PCT(self) -> float:
        return self.current_config["total_max_loss_pct"]

    def _load_state(self):
        """Carga el estado persistido de métricas de FTMO para tolerar reinicios."""
        try:
            if self.state_file and os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.daily_starting_equity = float(data.get("daily_starting_equity", self.account_size))
                    self.current_broker_date = str(data.get("current_broker_date", ""))
                    self.is_daily_lockout = bool(data.get("is_daily_lockout", False))
                    self.lockout_reason = str(data.get("lockout_reason", ""))
                    self.peak_equity = float(data.get("peak_equity", self.account_size))
                    logger.info(f"🛡️ [FTMO_GUARDIAN] Estado restaurado desde disco: Base Diaria=${self.daily_starting_equity:,.2f} | Fecha Broker={self.current_broker_date} | Lockout={self.is_daily_lockout}")
        except Exception as e:
            logger.debug(f"[FTMO_GUARDIAN] No se pudo cargar estado previo: {e}")

    def _save_state(self):
        """Guarda el estado en disco de forma atómica."""
        try:
            if self.state_file:
                folder = os.path.dirname(os.path.abspath(self.state_file))
                os.makedirs(folder, exist_ok=True)
                payload = {
                    "account_size": self.account_size,
                    "phase": self.phase,
                    "account_type": self.account_type,
                    "daily_starting_equity": self.daily_starting_equity,
                    "current_broker_date": self.current_broker_date,
                    "current_equity": self.current_equity,
                    "peak_equity": self.peak_equity,
                    "is_daily_lockout": self.is_daily_lockout,
                    "lockout_reason": self.lockout_reason,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
        except Exception as e:
            logger.debug(f"[FTMO_GUARDIAN] Error guardando estado: {e}")

    def set_phase(self, phase: str):
        """Actualiza la fase de evaluación de FTMO."""
        p_up = phase.upper()
        if p_up in self.PHASE_CONFIGS:
            self.phase = p_up
            logger.info(f"🛡️ [FTMO_GUARDIAN] Fase actualizada a {self.phase} (Riesgo base: {self.current_config['risk_pct']*100:.2f}%)")
            self._save_state()

    def evaluate_broker_day(self, server_time: Optional[datetime], live_balance: float, live_equity: float):
        """
        Sincroniza el cambio de jornada bancaria según la hora exacta del broker MT5 (Praga CE(S)T).
        Regla oficial FTMO:
        Al inicio del nuevo día (00:00:00 CE(S)T), la base de pérdida diaria es max(balance, equity).
        """
        if not server_time:
            return
            
        date_str = server_time.strftime("%Y-%m-%d")
        if self.current_broker_date != date_str:
            old_date = self.current_broker_date
            self.current_broker_date = date_str
            # Regla de FTMO: Base de Drawdown Diario = max(balance, equity) al inicio del día
            self.daily_starting_equity = max(live_balance, live_equity)
            self.is_daily_lockout = False
            self.lockout_reason = ""
            self.trades_today = 0
            self._save_state()
            logger.info(f"🌅 [FTMO_GUARDIAN] Rollover de Jornada Broker ({old_date} -> {date_str}). Base diaria fijada en ${self.daily_starting_equity:,.2f} USD (Balance=${live_balance:,.2f}, Equity=${live_equity:,.2f}) | Modo: {self.account_type}")

    def update_equity(self, current_equity: float, current_balance: Optional[float] = None) -> Dict[str, Any]:
        """Actualiza el equity en tiempo real y evalúa los interceptores de seguridad."""
        self.current_equity = current_equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            
        # 1. Calcular Drawdown Diario respecto a la base de las 00:00 CE(S)T
        daily_loss_usd = self.daily_starting_equity - current_equity
        daily_dd_pct = (daily_loss_usd / self.daily_starting_equity * 100.0) if self.daily_starting_equity > 0 else 0.0
        
        # 2. Calcular Drawdown Total desde el Balance Inicial ($100,000 USD)
        total_loss_usd = self.account_size - current_equity
        total_dd_pct = (total_loss_usd / self.account_size * 100.0) if self.account_size > 0 else 0.0
        
        # 3. Evaluar Kill-Switch Diario Dinámico (-3.5% en Fase 1 / -2.5% en Fase 2)
        daily_limit = self.DAILY_DRAWDOWN_LIMIT_PCT
        if daily_dd_pct >= daily_limit and not self.is_daily_lockout:
            self.is_daily_lockout = True
            self.lockout_reason = f"KILL-SWITCH DIARIO ACTIVADO ({self.phase}): Pérdida diaria alcanzada ({daily_dd_pct:.2f}% >= {daily_limit}%). Bot bloqueado por seguridad FTMO."
            logger.error(f"🛑 [FTMO_GUARDIAN] {self.lockout_reason}")
            self._save_state()

        # 4. Evaluar Kill-Switch Total (-7.5% en Fase 1 / -5.0% en Fase 2)
        total_limit = self.MAX_TOTAL_DRAWDOWN_PCT
        if total_dd_pct >= total_limit and not self.is_daily_lockout:
            self.is_daily_lockout = True
            self.lockout_reason = f"KILL-SWITCH TOTAL ACTIVADO ({self.phase}): Drawdown total ({total_dd_pct:.2f}% >= {total_limit}%). Bot congelado."
            logger.error(f"🛑 [FTMO_GUARDIAN] {self.lockout_reason}")
            self._save_state()
            
        # 5. Evaluar Progreso de Fase
        target_pct = self.current_config["target_pct"]
        profit_usd = current_equity - self.account_size
        progress_pct = (profit_usd / (self.account_size * (target_pct / 100.0)) * 100.0) if target_pct > 0 else 100.0
        
        return {
            "account_size": self.account_size,
            "account_type": self.account_type,
            "current_equity": self.current_equity,
            "daily_starting_equity": self.daily_starting_equity,
            "daily_loss_usd": max(0.0, daily_loss_usd),
            "daily_dd_pct": max(0.0, daily_dd_pct),
            "total_dd_pct": max(0.0, total_dd_pct),
            "daily_safe_margin_left_pct": max(0.0, daily_limit - daily_dd_pct),
            "is_daily_lockout": self.is_daily_lockout,
            "lockout_reason": self.lockout_reason,
            "phase": self.phase,
            "target_pct": target_pct,
            "progress_pct": min(100.0, max(0.0, progress_pct)),
            "phase_passed": profit_usd >= (self.account_size * (target_pct / 100.0)) and target_pct > 0
        }

    def check_midnight_rollover_risk(self, hour_utc: int, minute: int) -> bool:
        """
        [SOP-24 MIDNIGHT ROLL-OVER SHIELD]
        Ventana de 15 minutos de corte bancario interbancario (21:50 a 22:05 UTC / 23:50 a 00:05 CE(S)T).
        Durante estos minutos se congelan nuevas órdenes para evitar spreads ensanchados.
        """
        if hour_utc == 21 and minute >= 50:
            return True
        if hour_utc == 22 and minute <= 5:
            return True
        return False
        
    def calculate_mt5_lots(self, symbol: str, entry_price: float, stop_loss: float, risk_usd_override: Optional[float] = None, margin_free: Optional[float] = None) -> Dict[str, Any]:
        """
        Calcula los lotes exactos para MetaTrader 5 según el tamaño de contrato institucional y la fragmentación 50/30/20.
        Incluye gobernador de margen adaptado a apalancamiento 1:30 en FTMO SWING.
        """
        symbol = symbol.upper()
        spec = TRADFI_ASSETS_CONFIG.get(symbol, {
            "contract_size": 100 if "XAU" in symbol else 1 if any(i in symbol for i in ["US", "NQ", "YM", "GER"]) else 100000,
            "min_lot": 0.01,
            "name": symbol
        })
        
        # Riesgo base según fase (Fase 1: 0.75% = $750 | Fase 2: 0.50% = $500 | Fondeada: 0.35% = $350)
        risk_pct = self.current_config["risk_pct"]
        risk_usd = risk_usd_override or (self.current_equity * risk_pct)
        
        dist = abs(entry_price - stop_loss)
        if dist <= 0:
            return {"lots": spec["min_lot"], "risk_usd": risk_usd, "dist": 0.0, "lots_tp1": spec["min_lot"], "lots_tp2": 0.0, "lots_tp3": 0.0, "contract_size": spec["contract_size"], "margin_warning": False}
            
        contract_size = spec["contract_size"]
        
        # Fórmula institucional de lotes: Lotes = Riesgo_USD / (Distancia * Contract_Size)
        raw_lots = risk_usd / (dist * contract_size)
        
        # Ajuste de pasos y mínimos según activo
        min_lot = spec.get("min_lot", 0.01)
        is_index = any(idx in symbol for idx in ["US100", "US30", "US500", "GER40"])
        
        if is_index:
            total_lots = round(max(min_lot, raw_lots), 1)
            lots_tp1 = round(total_lots * 0.50, 1)
            lots_tp2 = round(total_lots * 0.30, 1)
            lots_tp3 = round(total_lots - lots_tp1 - lots_tp2, 1)
        else:
            total_lots = round(max(min_lot, raw_lots), 2)
            lots_tp1 = round(total_lots * 0.50, 2)
            lots_tp2 = round(total_lots * 0.30, 2)
            lots_tp3 = round(total_lots - lots_tp1 - lots_tp2, 2)

        # Gobernador de Margen Libre para FTMO SWING (Apalancamiento 1:30 en Forex, 1:20 en Índices/Metales)
        margin_warning = False
        if margin_free is not None and margin_free > 0 and self.account_type == "SWING":
            leverage = 30.0 if not is_index and "XAU" not in symbol else 20.0
            notional = total_lots * contract_size * entry_price
            est_margin_needed = notional / leverage
            # Si el margen necesario supera el 40% del margen libre remanente, activar advertencia
            if est_margin_needed > (margin_free * 0.40):
                margin_warning = True
                logger.warning(f"⚠️ [FTMO_MARGIN_GOVERNOR] Orden {symbol} de {total_lots} lotes requiere ~${est_margin_needed:,.2f} USD de margen con apalancamiento 1:{int(leverage)} (Margen Libre: ${margin_free:,.2f}).")
            
        return {
            "symbol": symbol,
            "name": spec.get("name", symbol),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "dist": dist,
            "risk_usd": risk_usd,
            "risk_pct": risk_pct * 100.0,
            "lots": total_lots,
            "lots_tp1": lots_tp1,  # 50% TP1 (+1.5R)
            "lots_tp2": lots_tp2,  # 30% TP2 (+3.0R)
            "lots_tp3": lots_tp3,  # 20% TP3 (+5.0R Runner)
            "contract_size": contract_size,
            "margin_warning": margin_warning
        }

ftmo_guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", account_type="SWING")
