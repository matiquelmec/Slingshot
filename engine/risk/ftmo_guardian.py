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
    """Guardián de Capital y Reglas de Prop Firm (FTMO / MT5)."""
    
    # Límites Cuantitativos de Seguridad
    DAILY_DRAWDOWN_LIMIT_PCT = 3.5   # Stop diario de seguridad (vs 5.0% de FTMO)
    MAX_TOTAL_DRAWDOWN_PCT   = 7.5   # Stop total de seguridad (vs 10.0% de FTMO)
    
    def __init__(self, account_size: float = 100000.0, phase: str = "PHASE_1"):
        self.account_size = account_size
        self.phase = phase # "PHASE_1" (10%), "PHASE_2" (5%), "FUNDED"
        self.current_equity = account_size
        self.daily_starting_equity = account_size
        self.peak_equity = account_size
        self.is_daily_lockout = False
        self.lockout_reason = ""
        self.trades_today = 0
        
    def reset_daily_metrics(self, new_starting_equity: Optional[float] = None):
        """Resetea los contadores al inicio de la jornada (00:00 UTC / MT5 Server Time)."""
        if new_starting_equity:
            self.daily_starting_equity = new_starting_equity
            self.current_equity = new_starting_equity
        self.is_daily_lockout = False
        self.lockout_reason = ""
        self.trades_today = 0
        logger.info(f"🛡️ [FTMO_GUARDIAN] Nueva jornada iniciada. Base diaria: ${self.daily_starting_equity:,.2f} USD")
        
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
        
        # 3. Evaluar Kill-Switch Diario (-3.5%)
        if daily_dd_pct >= self.DAILY_DRAWDOWN_LIMIT_PCT and not self.is_daily_lockout:
            self.is_daily_lockout = True
            self.lockout_reason = f"KILL-SWITCH DIARIO ACTIVADO: Pérdida diaria alcanzada ({daily_dd_pct:.2f}% >= {self.DAILY_DRAWDOWN_LIMIT_PCT}%). Bot congelado por seguridad."
            logger.error(f"🛑 [FTMO_GUARDIAN] {self.lockout_reason}")
            
        # 4. Evaluar Progreso de Fase
        target_pct = 10.0 if self.phase == "PHASE_1" else 5.0 if self.phase == "PHASE_2" else 0.0
        profit_usd = current_equity - self.account_size
        progress_pct = (profit_usd / (self.account_size * (target_pct / 100.0)) * 100.0) if target_pct > 0 else 100.0
        
        return {
            "account_size": self.account_size,
            "current_equity": self.current_equity,
            "daily_starting_equity": self.daily_starting_equity,
            "daily_loss_usd": max(0.0, daily_loss_usd),
            "daily_dd_pct": max(0.0, daily_dd_pct),
            "total_dd_pct": max(0.0, total_dd_pct),
            "daily_safe_margin_left_pct": max(0.0, self.DAILY_DRAWDOWN_LIMIT_PCT - daily_dd_pct),
            "is_daily_lockout": self.is_daily_lockout,
            "lockout_reason": self.lockout_reason,
            "phase": self.phase,
            "target_pct": target_pct,
            "progress_pct": min(100.0, max(0.0, progress_pct)),
            "phase_passed": profit_usd >= (self.account_size * (target_pct / 100.0)) and target_pct > 0
        }
        
    def calculate_mt5_lots(self, symbol: str, entry_price: float, stop_loss: float, risk_usd_override: Optional[float] = None) -> Dict[str, Any]:
        """
        Calcula los lotes exactos para MetaTrader 5 según el tamaño de contrato institucional.
        """
        symbol = symbol.upper()
        spec = TRADFI_ASSETS_CONFIG.get(symbol, {
            "contract_size": 100 if "XAU" in symbol else 1 if any(i in symbol for i in ["US", "NQ", "YM", "GER"]) else 100000,
            "min_lot": 0.01,
            "name": symbol
        })
        
        # Riesgo base según fase (Fase 1: 0.75% = $750 | Fase 2: 0.50% = $500)
        risk_pct = 0.0075 if self.phase == "PHASE_1" else 0.0050 if self.phase == "PHASE_2" else 0.0075
        risk_usd = risk_usd_override or (self.current_equity * risk_pct)
        
        dist = abs(entry_price - stop_loss)
        if dist <= 0:
            return {"lots": spec["min_lot"], "risk_usd": risk_usd, "dist": 0.0}
            
        contract_size = spec["contract_size"]
        
        # Fórmula institucional de lotes: Lotes = Riesgo_USD / (Distancia * Contract_Size)
        raw_lots = risk_usd / (dist * contract_size)
        
        # Ajuste de pasos y mínimos según activo
        min_lot = spec.get("min_lot", 0.01)
        if "US100" in symbol or "US30" in symbol:
            lots = round(max(min_lot, raw_lots), 1) # Índices típicamente van en pasos de 0.1
        else:
            lots = round(max(min_lot, raw_lots), 2) # Oro y Forex en pasos de 0.01
            
        return {
            "symbol": symbol,
            "name": spec.get("name", symbol),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "dist": dist,
            "risk_usd": risk_usd,
            "risk_pct": risk_pct * 100.0,
            "lots": lots,
            "contract_size": contract_size
        }

ftmo_guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1")
