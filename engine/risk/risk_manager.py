from engine.api.config import settings
import math

# El factor estático original se ha movido al módulo SIGMA (ASSET_TUNING) para control dinámico
# FEE_SLIPPAGE_IMPACT = 0.0004 


class RiskManager:
    """
    v6.6.4 Sniper Master Edition.
    """

    def __init__(self, account_balance: float = settings.ACCOUNT_BALANCE, base_risk_pct: float = settings.MAX_RISK_PCT, min_rr: float = settings.MIN_RR):
        self.account_balance = account_balance
        self.base_risk_pct = base_risk_pct
        self.min_rr = min_rr # 2.5R Neto - Disciplina Sniper v6.7 Master Gold
        self.max_leverage = 50.0 
        self.daily_loss_usd = 0.0
        self.is_locked = False

    def validate_signal(self, signal_data: dict) -> dict:
        """ [PORTERO v6.6.7] """
        try:
            entry = float(signal_data.get("price", 0))
            atr   = float(signal_data.get("atr_value", 0))
            asset = str(signal_data.get("asset", "UNKNOWN")).upper()
            
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
            
            # --- SPREAD WATCHDOG (Fricción Dinámica) ---
            tuning = self.ASSET_TUNING.get(asset, self.DEFAULT_TUNING)
            dynamic_friction_pct = tuning.get("spread_impact", 0.0004) # Fallback 0.04%
            
            friction = entry * dynamic_friction_pct
            
            # KILL SWITCH: Si la fricción (spread + fee) representa más del 20% del stop loss, es suicidio matemático
            if risk > 0 and friction > (risk * 0.20):
                return {"approved": False, "rr_ratio": 0.0, "trade_quality": "HIGH_SPREAD", "reason": f"Spread Kill Switch: Fricción ({dynamic_friction_pct*100:.3f}%) muy alta para SL."}
            
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
        "BTCUSDT":  {"atr_mult": 1.5, "tp1_ratio": 2.5, "tp1_vol": 0.60, "spread_impact": 0.0002}, # 0.02% (Alta Liquidez)
        "ETHUSDT":  {"atr_mult": 3.0, "tp1_ratio": 2.5, "tp1_vol": 0.80, "spread_impact": 0.0003}, # 0.03%
        "SOLUSDT":  {"atr_mult": 3.5, "tp1_ratio": 2.5, "tp1_vol": 0.80, "spread_impact": 0.0008}, # 0.08% (Volátil)
        "XRPUSDT":  {"atr_mult": 2.5, "tp1_ratio": 2.5, "tp1_vol": 0.70, "spread_impact": 0.0005}, # 0.05%
        "PAXGUSDT": {"atr_mult": 2.5, "tp1_ratio": 2.5, "tp1_vol": 0.80, "spread_impact": 0.0015}, # 0.15% (Baja Liquidez/Oro)
        "XAGUSDT":  {"atr_mult": 2.5, "tp1_ratio": 2.5, "tp1_vol": 0.80, "spread_impact": 0.0015}, # 0.15% (Plata)
    }
    DEFAULT_TUNING = {"atr_mult": 1.8, "tp1_ratio": 1.5, "tp1_vol": 0.50, "spread_impact": 0.0010} # Default 0.1%

    def calculate_position(
        self,
        current_price: float,
        signal_type: str = "LONG",
        market_regime: str = "RANGING",
        key_levels: list = None,
        smc_data: dict = None,
        atr_value: float = 0.0,
        asset: str = "UNKNOWN",
        liquidations: list = None,
        heatmap: dict = None,
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
        risk_dist = fallback_atr * tuning["atr_mult"]
        
        # --- [GOD MODE: SALIDAS ESTRUCTURALES v6.1] ---
        sl = current_price - risk_dist if signal_type == "LONG" else current_price + risk_dist
        tp1 = current_price + (risk_dist * tuning["tp1_ratio"]) if signal_type == "LONG" else current_price - (risk_dist * tuning["tp1_ratio"])

        # Intento de SL Estructural (Order Blocks / Key Levels)
        if smc_data or key_levels:
            if signal_type == "LONG":
                # Buscar el OB Alcista o Soporte más cercano por debajo del precio
                obs = smc_data.get("order_blocks", {}).get("bullish", []) if smc_data else []
                sups = key_levels.get("supports", []) if key_levels else []
                structural_floors = [ob["bottom"] for ob in obs] + [s["price"] for s in sups]
                valid_floors = [f for f in structural_floors if f < current_price]
                if valid_floors:
                    best_floor = max(valid_floors)
                    # Colocamos SL 0.2 ATR por debajo del piso estructural
                    sl_candidate = best_floor - (fallback_atr * 0.2)
                    # No alejamos el SL más de 2x del riesgo base por seguridad
                    if sl_candidate > (current_price - risk_dist * 1.5):
                        sl = sl_candidate
            else:
                # Buscar el OB Bajista o Resistencia más cercana por arriba del precio
                obs = smc_data.get("order_blocks", {}).get("bearish", []) if smc_data else []
                res = key_levels.get("resistances", []) if key_levels else []
                structural_ceilings = [ob["top"] for ob in obs] + [r["price"] for r in res]
                valid_ceilings = [c for c in structural_ceilings if c > current_price]
                if valid_ceilings:
                    best_ceiling = min(valid_ceilings)
                    sl_candidate = best_ceiling + (fallback_atr * 0.2)
                    if sl_candidate < (current_price + risk_dist * 1.5):
                        sl = sl_candidate

        # Intento de TP Inteligente (Liquidation Clusters / Opposite OBs)
        if liquidations or smc_data:
            if signal_type == "LONG":
                # Target: Liquidaciones de SHORT o OB Bajistas
                liq_targets = [l["price"] for l in (liquidations or []) if l["type"] == "SHORT_LIQ" and l["price"] > current_price]
                ob_targets = [ob["bottom"] for ob in (smc_data.get("order_blocks", {}).get("bearish", []) if smc_data else []) if ob["bottom"] > current_price]
                all_targets = liq_targets + ob_targets
                if all_targets:
                    # Apuntamos al cluster más cercano que nos dé al menos el RR mínimo
                    all_targets.sort()
                    for target in all_targets:
                        potential_rr = (target - current_price) / abs(current_price - sl)
                        if potential_rr >= self.min_rr:
                            tp1 = target
                            break
            else:
                # Target: Liquidaciones de LONG o OB Alcistas
                liq_targets = [l["price"] for l in (liquidations or []) if l["type"] == "LONG_LIQ" and l["price"] < current_price]
                ob_targets = [ob["top"] for ob in (smc_data.get("order_blocks", {}).get("bullish", []) if smc_data else []) if ob["top"] < current_price]
                all_targets = liq_targets + ob_targets
                if all_targets:
                    all_targets.sort(reverse=True)
                    for target in all_targets:
                        potential_rr = (current_price - target) / abs(current_price - sl)
                        if potential_rr >= self.min_rr:
                            tp1 = target
                            break

        # Red de Seguridad: Asegurar RR 2.5 en el setup final
        final_risk = abs(current_price - sl)
        final_reward = abs(tp1 - current_price)
        if final_risk > 0:
            final_rr = final_reward / final_risk
            if final_rr < self.min_rr:
                # Si la estructura no da para el RR, forzamos salida matemática
                tp1 = current_price + (final_risk * self.min_rr) if signal_type == "LONG" else current_price - (final_risk * self.min_rr)

        # Targets Secundarios
        tp2 = tp1 + (abs(tp1 - current_price) * 0.5) if signal_type == "LONG" else tp1 - (abs(tp1 - current_price) * 0.5)
        tp3 = tp2 + (abs(tp2 - tp1) * 0.5) if signal_type == "LONG" else tp2 - (abs(tp2 - tp1) * 0.5)

        sl_dist_pct = final_risk / current_price if current_price > 0 else 0.01
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
