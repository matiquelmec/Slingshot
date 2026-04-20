from engine.api.config import settings
import math

# Factor de Fricción (Ajustado a 0.04% para niveles de volumen institucional)
FEE_SLIPPAGE_IMPACT = 0.0004 


class RiskManager:
    """
    v6.6.4 Sniper Master Edition.
    """

    def __init__(self, account_balance: float = settings.ACCOUNT_BALANCE, base_risk_pct: float = settings.MAX_RISK_PCT, min_rr: float = 1.5):
        self.account_balance = account_balance
        self.base_risk_pct = base_risk_pct
        self.min_rr = min_rr # 1.5R Neto - Disciplina Sniper v6.7
        self.max_leverage = 50.0 
        self.daily_loss_usd = 0.0
        self.is_locked = False

    def validate_signal(self, signal_data: dict) -> dict:
        """ [PORTERO v6.6.7] """
        try:
            entry = float(signal_data.get("price", 0))
            atr   = float(signal_data.get("atr_value", 0))
            
            # Filtro de Volatilidad Relajado (0.1% para 15m)
            if atr < (entry * 0.001):
                return {"approved": False, "rr_ratio": 0.0, "trade_quality": "LOW_VOL", "reason": f"Volatility too low: {atr:.2f}"}

            sig_type = str(signal_data.get("signal_type", "LONG")).upper()
            
            # Sniper Projection v6.6.16 (Precision Override)
            # Forzamos que el SL/TP siempre use la volatilidad ATR real para optimizar R:R
            risk_dist = atr * 2.0 # Stop ajustado de 2 ATR
            sl = entry - risk_dist if "LONG" in sig_type else entry + risk_dist
            tp = entry + (risk_dist * 3.0) if "LONG" in sig_type else entry - (risk_dist * 3.0) # Objetivo de 3.0R
            
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            friction = entry * FEE_SLIPPAGE_IMPACT
            
            if (risk + friction) <= 0:
                 return {"approved": False, "rr_ratio": 0.0, "trade_quality": "ERR", "reason": "Zero risk calculated"}
                 
            rr = round((reward - friction) / (risk + friction), 2)
            # RESTAURADO v6.6.15: Disciplina Institucional
            approved = rr >= self.min_rr
            
            return {
                "approved": approved,
                "rr_ratio": rr,
                "trade_quality": "S" if rr >= 2.0 else ("A" if approved else "D"),
                "reason": f"R:R Sniper: {rr} (Net)"
            }
        except Exception as e:
            return {"approved": False, "rr_ratio": 0.0, "trade_quality": "ERROR", "reason": str(e)}

    def calculate_structural_sl_tp(self, current_price, signal_type, key_levels, smc_data, atr_value):
        risk_dist = atr_value * 1.5
        stop_loss = current_price - risk_dist if signal_type == "LONG" else current_price + risk_dist
        take_profit = current_price + (risk_dist * 2.0) if signal_type == "LONG" else current_price - (risk_dist * 2.0)
        return stop_loss, take_profit, 2.0

    # --- MÓDULO SIGMA: SINTONIZADOR DE ACTIVOS --------------------------------
    ASSET_TUNING = {
        "BTCUSDT":  {"atr_mult": 1.5, "tp1_ratio": 1.5, "tp1_vol": 0.60}, # Regresamos a 1.5R para mayor winrate
        "ETHUSDT":  {"atr_mult": 3.0, "tp1_ratio": 2.0, "tp1_vol": 0.80}, # v7.6.0: Escalado Institucional (Anti-Comisiones)
        "SOLUSDT":  {"atr_mult": 3.5, "tp1_ratio": 1.5, "tp1_vol": 0.80}, # v8.0.0: Sniper (Filtro Ultra + Cobro Rápido)
        "PAXGUSDT": {"atr_mult": 2.5, "tp1_ratio": 2.0, "tp1_vol": 0.80}, # v8.2.0: Gold Standard (Volatilidad Baja)
    }
    DEFAULT_TUNING = {"atr_mult": 1.8, "tp1_ratio": 1.5, "tp1_vol": 0.50}

    def calculate_position(
        self,
        current_price: float,
        signal_type: str = "LONG",
        market_regime: str = "RANGING",
        key_levels: list = None,
        smc_data: dict = None,
        atr_value: float = 0.0,
        asset: str = "UNKNOWN",
        **kwargs
    ) -> dict:
        """
        Cálculo de posición v6.7.5 (SIGMA Enabled).
        Ajusta dinámicamente el riesgo y los targets según el activo.
        """
        tuning = self.ASSET_TUNING.get(asset.upper(), self.DEFAULT_TUNING)
        
        # [SIGMA TELEMETRY v8.2.0] — Silenciado para producción, activo en DEBUG
        import logging
        logging.getLogger("slingshot.risk").debug(
            f"[SIGMA] {asset} | ATR_MULT: {tuning['atr_mult']} | TP_RATIO: {tuning['tp1_ratio']} | TP1_VOL: {tuning['tp1_vol']}"
        )
        
        actual_risk_pct = self.base_risk_pct
        risk_amount_usdt = self.account_balance * actual_risk_pct
        
        # 1. Aplicación de Pulmones (SIGMA ATR Mult)
        fallback_atr = atr_value if atr_value > 0 else (current_price * 0.005)
        risk = fallback_atr * tuning["atr_mult"]
        sl = current_price - risk if signal_type == "LONG" else current_price + risk
        
        # 2. Grilla Asimétrica (DELTA Ready)
        tp1 = current_price + (risk * tuning["tp1_ratio"]) if signal_type == "LONG" else current_price - (risk * tuning["tp1_ratio"])
        tp2 = current_price + (risk * (tuning["tp1_ratio"] + 1.0)) if signal_type == "LONG" else current_price - (risk * (tuning["tp1_ratio"] + 1.0))
        tp3 = current_price + (risk * (tuning["tp1_ratio"] + 2.5)) if signal_type == "LONG" else current_price - (risk * (tuning["tp1_ratio"] + 2.5))

        sl_dist_pct = risk / current_price if current_price > 0 else 0.01
        pos_size_nominal = risk_amount_usdt / max(0.001, sl_dist_pct)
        leverage = min(50, math.ceil(pos_size_nominal / self.account_balance))
        
        return {
            "entry_price": round(current_price, 5),
            "stop_loss": round(sl, 5),
            "tp1": round(tp1, 5),
            "tp2": round(tp2, 5),
            "tp3": round(tp3, 5),
            "tp1_vol_pct": tuning["tp1_vol"],
            "risk_amount_usdt": round(risk_amount_usdt, 2), # Compatibility fix
            "risk_usd": round(risk_amount_usdt, 2),
            "risk_pct": round(actual_risk_pct * 100, 2),
            "position_size_usdt": round(pos_size_nominal, 2),
            "leverage": leverage,
            "entry_zone_top": round(current_price * 1.001, 5),
            "entry_zone_bottom": round(current_price * 0.999, 5),
            "asset": asset
        }
