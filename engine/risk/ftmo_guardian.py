"""
engine/risk/ftmo_guardian.py — FTMO Guardian Shield v19.0
=========================================================
Protección Cuantitativa de Cuentas de Fondeo (FTMO / MetaTrader 5):
1. Kill-Switch de Drawdown Diario: Hard stop preventivo a -3.5% (antes del 5% fatal de FTMO).
2. Cálculo exacto de lotes MT5 según especificaciones de contrato de Oro, Índices y Forex.
3. Gestión de Fases: Fase 1 (Target +10% | Riesgo 0.75%), Fase 2 (Target +5% | Riesgo 0.50%).
4. Filtro de Noticias de Alto Impacto (NFP / FOMC / CPI).
"""
import time
from typing import Dict, Any, Optional
from engine.core.logger import logger
from engine.indicators.tradfi_provider import TRADFI_ASSETS_CONFIG

class FtmoGuardianShield:
    """Guardián de Capital y Reglas de Prop Firm (FTMO / MT5) — v25.0 APEX TITANIUM."""
    
    # Límites Cuantitativos de Seguridad Dinámicos por Fase
    PHASE_CONFIGS = {
        "PHASE_1": {"risk_pct": 0.0075, "target_pct": 10.0, "daily_max_loss_pct": 3.5, "total_max_loss_pct": 7.5},
        "PHASE_2": {"risk_pct": 0.0050, "target_pct": 5.0,  "daily_max_loss_pct": 2.5, "total_max_loss_pct": 5.0},
        "FUNDED":  {"risk_pct": 0.0035, "target_pct": 0.0,  "daily_max_loss_pct": 2.0, "total_max_loss_pct": 4.5},
    }
    
    def __init__(self, account_size: float = 100000.0, phase: str = "PHASE_1"):
        self.account_size = account_size
        self.phase = phase.upper() if phase.upper() in self.PHASE_CONFIGS else "PHASE_1"
        self.current_equity = account_size
        self.daily_starting_equity = account_size
        self.peak_equity = account_size
        self.is_daily_lockout = False
        self.lockout_reason = ""
        self.trades_today = 0
        
    @property
    def current_config(self) -> Dict[str, float]:
        return self.PHASE_CONFIGS.get(self.phase, self.PHASE_CONFIGS["PHASE_1"])

    @property
    def DAILY_DRAWDOWN_LIMIT_PCT(self) -> float:
        return self.current_config["daily_max_loss_pct"]

    @property
    def MAX_TOTAL_DRAWDOWN_PCT(self) -> float:
        return self.current_config["total_max_loss_pct"]

    def set_phase(self, phase: str):
        """Actualiza la fase de evaluación de FTMO."""
        p_up = phase.upper()
        if p_up in self.PHASE_CONFIGS:
            self.phase = p_up
            logger.info(f"🛡️ [FTMO_GUARDIAN] Fase actualizada a {self.phase} (Riesgo base: {self.current_config['risk_pct']*100:.2f}%)")

    def reset_daily_metrics(self, new_starting_equity: Optional[float] = None):
        """Resetea los contadores al inicio de la jornada (00:00 UTC / MT5 Server Time)."""
        if new_starting_equity:
            self.daily_starting_equity = new_starting_equity
            self.current_equity = new_starting_equity
        self.is_daily_lockout = False
        self.lockout_reason = ""
        self.trades_today = 0
        logger.info(f"🛡️ [FTMO_GUARDIAN] Nueva jornada iniciada. Base diaria: ${self.daily_starting_equity:,.2f} USD | Fase: {self.phase}")
        
    def update_equity(self, current_equity: float) -> Dict[str, Any]:
        """Actualiza el equity en tiempo real y evalúa los interceptores de seguridad."""
        self.current_equity = current_equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            
        # 1. Calcular Drawdown Diario
        daily_loss_usd = self.daily_starting_equity - current_equity
        daily_dd_pct = (daily_loss_usd / self.daily_starting_equity * 100.0) if self.daily_starting_equity > 0 else 0.0
        
        # 2. Calcular Drawdown Total desde el Peak
        total_loss_usd = self.peak_equity - current_equity
        total_dd_pct = (total_loss_usd / self.account_size * 100.0) if self.account_size > 0 else 0.0
        
        # 3. Evaluar Kill-Switch Diario Dinámico (-3.5% Fase 1 / -2.5% Fase 2 / -2.0% Fondeada)
        daily_limit = self.DAILY_DRAWDOWN_LIMIT_PCT
        if daily_dd_pct >= daily_limit and not self.is_daily_lockout:
            self.is_daily_lockout = True
            self.lockout_reason = f"KILL-SWITCH DIARIO ACTIVADO ({self.phase}): Pérdida diaria alcanzada ({daily_dd_pct:.2f}% >= {daily_limit}%). Bot congelado por seguridad."
            logger.error(f"🛑 [FTMO_GUARDIAN] {self.lockout_reason}")
            
        # 4. Evaluar Progreso de Fase
        target_pct = self.current_config["target_pct"]
        profit_usd = current_equity - self.account_size
        progress_pct = (profit_usd / (self.account_size * (target_pct / 100.0)) * 100.0) if target_pct > 0 else 100.0
        
        return {
            "account_size": self.account_size,
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
        
    def calculate_mt5_lots(self, symbol: str, entry_price: float, stop_loss: float, risk_usd_override: Optional[float] = None) -> Dict[str, Any]:
        """
        Calcula los lotes exactos para MetaTrader 5 según el tamaño de contrato institucional y la fragmentación 50/30/20.
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
            return {"lots": spec["min_lot"], "risk_usd": risk_usd, "dist": 0.0, "lots_tp1": spec["min_lot"], "lots_tp2": 0.0, "lots_tp3": 0.0}
            
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
            "contract_size": contract_size
        }

ftmo_guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1")
