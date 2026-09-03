from engine.api.config import settings
import math

# El factor estático original se ha movido al módulo SIGMA (ASSET_TUNING) para control dinámico
# FEE_SLIPPAGE_IMPACT = 0.0004 


class RiskManager:
    """
    v11.1 APEX SOVEREIGN (Audited).
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
            # [ROBUST ATR LOOKUP v11.2]
            raw_atr = signal_data.get("atr_value") or signal_data.get("atr")
            atr = float(raw_atr) if raw_atr is not None else 0.0
            asset = str(signal_data.get("asset", "UNKNOWN")).upper()
            interval_mins = int(signal_data.get("interval_minutes", 15))
            
            # [FASE 1.1] Matriz Dinámica de Riesgo (Adaptive R:R)
            if interval_mins < 15:     # Micro-Scalping (1m, 3m, 5m)
                dynamic_min_rr = 1.5   # R:R ágil y realizable bajo fricción
            elif interval_mins <= 60:  # Intraday (15m, 30m, 1h)
                dynamic_min_rr = 2.5   # Sniper clásico estándar
            else:                      # Swing/Macro (2h, 4h, 8h, 1d)
                dynamic_min_rr = 3.5   # R:R premium institucional por holding time
            
            # Fallback Dinámico Profesional: Si el ATR no está disponible o es absurdamente bajo
            # (menor a 0.05% del precio), aplicamos un fallback sano del 0.3% del precio de entrada
            # para evitar bloqueos por fallos de indicadores o inicialización.
            if atr <= 0.0 or atr < (entry * 0.0005):
                atr = entry * 0.003
                logger.warning(f"[RISK_MANAGER] ⚠️ ATR ausente o bajo para {asset}. Aplicando fallback de 0.3% ({atr:.2f})")
            
            # [FASE 1.2] Filtro de Volatilidad Relativa (ATR Múltiplo)
            if atr < (entry * 0.001):
                return {"approved": False, "rr_ratio": 0.0, "trade_quality": "LOW_VOL", "reason": f"Volatility too low: {atr:.2f}"}

            sig_type = str(signal_data.get("signal_type", "LONG")).upper()
            
            # Sniper Projection v6.6.16 (Precision Override)
            risk_dist = atr * 2.0
            sl = entry - risk_dist if "LONG" in sig_type else entry + risk_dist
            tp = entry + (risk_dist * 3.0) if "LONG" in sig_type else entry - (risk_dist * 3.0)
            
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            
            # --- SPREAD WATCHDOG (Fricción Dinámica) ---
            tuning = self.ASSET_TUNING.get(asset, self.DEFAULT_TUNING)
            dynamic_friction_pct = tuning.get("spread_impact", 0.0004)
            
            friction = entry * dynamic_friction_pct
            
            if risk > 0 and friction > (risk * 0.20):
                return {"approved": False, "rr_ratio": 0.0, "trade_quality": "HIGH_SPREAD", "reason": f"Spread Kill Switch: Fricción ({dynamic_friction_pct*100:.3f}%) muy alta para SL."}
            
            if (risk + friction) <= 0:
                 return {"approved": False, "rr_ratio": 0.0, "trade_quality": "ERR", "reason": "Zero risk calculated"}
                 
            rr = round((reward - friction) / (risk + friction), 2)
            
            # Aprobación basada en el R:R Dinámico
            approved = rr >= dynamic_min_rr
            
            return {
                "approved": approved,
                "rr_ratio": rr,
                "trade_quality": "S" if rr >= (dynamic_min_rr + 0.5) else ("A" if approved else "D"),
                "reason": f"R:R Adaptive ({interval_mins}m): {rr} >= {dynamic_min_rr}"
            }
        except Exception as e:
            return {"approved": False, "rr_ratio": 0.0, "trade_quality": "ERROR", "reason": str(e)}

    def calculate_structural_sl_tp(self, current_price, signal_type, key_levels, smc_data, atr_value):
        risk_dist = atr_value * 1.5
        stop_loss = current_price - risk_dist if signal_type == "LONG" else current_price + risk_dist
        take_profit = current_price + (risk_dist * 2.0) if signal_type == "LONG" else current_price - (risk_dist * 2.0)
        return stop_loss, take_profit, 2.0

    # ── PROTOCOLO SOP-21: LIQUIDATION INVARIANCE ENGINE v35.0 ─────────────────
    @staticmethod
    def calculate_safe_leverage(
        entry_price: float,
        sl_price: float,
        mmr: float = 0.015,
        safety_factor: float = 1.50,
        max_cap: int = 20
    ) -> int:
        """
        [SOP-21 LIQUIDATION INVARIANCE]
        Calcula el apalancamiento máximo permitido garantizando que el Precio de Liquidación
        esté estrictamente más lejos que el Stop Loss por al menos un safety_factor (default 1.5x / +50%).
        
        Fórmula:
            sl_dist_pct = |Entry - SL| / Entry
            required_liq_dist = sl_dist_pct * safety_factor + MMR
            safe_leverage = floor(1 / required_liq_dist)
        """
        if entry_price <= 0 or sl_price <= 0 or entry_price == sl_price:
            return min(max_cap, 10)
            
        sl_dist_pct = abs(entry_price - sl_price) / entry_price
        
        # Distancia de liquidación requerida para que el SL nunca colisione con el motor del broker
        required_liq_dist = (sl_dist_pct * safety_factor) + mmr
        if required_liq_dist <= 0:
            return max_cap
            
        raw_leverage = math.floor(1.0 / required_liq_dist)
        # Acotar entre 1x y max_cap (20x)
        safe_lev = max(1, min(int(raw_leverage), max_cap))
        return safe_lev

    @staticmethod
    def verify_liquidation_clearance(
        entry_price: float,
        sl_price: float,
        leverage: int,
        mmr: float = 0.015,
        min_clearance_ratio: float = 1.40
    ) -> tuple[bool, str, float]:
        """
        [SOP-21 PRE-FLIGHT CLEARANCE GUARD]
        Verifica si la orden cumple con el ratio de supervivencia mínimo:
        clearance_ratio = liq_dist_pct / sl_dist_pct >= min_clearance_ratio (1.40x).
        """
        if entry_price <= 0 or sl_price <= 0 or leverage <= 0:
            return False, "Parámetros inválidos para cálculo de liquidación", 0.0
            
        sl_dist_pct = abs(entry_price - sl_price) / entry_price
        liq_dist_pct = max(0.0, (1.0 / leverage) - mmr)
        
        if sl_dist_pct <= 0:
            return True, "SL en punto cero", 99.0
            
        clearance_ratio = liq_dist_pct / sl_dist_pct
        is_safe = clearance_ratio >= min_clearance_ratio
        
        if not is_safe:
            msg = (
                f"🛑 [SOP-21 VETO] Colisión de Liquidación detectada: SL dist {sl_dist_pct*100:.2f}% vs "
                f"Liq dist {liq_dist_pct*100:.2f}% a {leverage}x (Ratio {clearance_ratio:.2f}x < {min_clearance_ratio:.2f}x requerido)."
            )
        else:
            msg = (
                f"✅ [SOP-21 CLEARANCE OK] Buffer de Liquidación {clearance_ratio:.2f}x: "
                f"SL dist {sl_dist_pct*100:.2f}% | Liq dist {liq_dist_pct*100:.2f}% a {leverage}x."
            )
            
        return is_safe, msg, round(clearance_ratio, 2)

    # ── PROTOCOLO SOP-23: FUNDING RATE CIRCUIT BREAKER v36.0 ─────────────────
    @staticmethod
    def check_funding_rate_impact(
        symbol: str,
        side: str,
        funding_rate: float,
        max_adverse_rate: float = 0.0005
    ) -> tuple[bool, str]:
        """
        [SOP-23 FUNDING RATE CIRCUIT BREAKER]
        Veta operaciones si la tasa de financiación por 8h es excesivamente adversa (> +0.05% en LONG o < -0.05% en SHORT),
        evitando que el coste de mantenimiento drene las ganancias del trade.
        """
        is_long = "LONG" in side.upper() or "BUY" in side.upper()
        
        # En LONG: pagamos si funding_rate es positivo
        if is_long and funding_rate > max_adverse_rate:
            return False, f"🛑 [SOP-23 FUNDING VETO] Tasa de financiación excesiva para LONG ({funding_rate*100:.3f}% > {max_adverse_rate*100:.3f}% por 8h)."
            
        # En SHORT: pagamos si funding_rate es negativo
        if not is_long and funding_rate < -max_adverse_rate:
            return False, f"🛑 [SOP-23 FUNDING VETO] Tasa de financiación excesiva para SHORT ({funding_rate*100:.3f}% < -{max_adverse_rate*100:.3f}% por 8h)."
            
        return True, f"✅ [SOP-23 FUNDING OK] Tasa saludable ({funding_rate*100:.3f}% por 8h)."

    # ── PROTOCOLO SOP-25: EARLY STRUCTURAL INVALIDATION v37.0 ─────────────────
    @staticmethod
    def check_early_invalidation_candidate(
        entry_price: float,
        current_price: float,
        sl_price: float,
        side: str
    ) -> tuple[bool, float]:
        """
        [SOP-25 EARLY STRUCTURAL INVALIDATION @ 0.65R]
        Basado en el MAE medio de 0.42R: Si una posición en curso retrocede más allá de -0.65R en contra,
        la probabilidad de terminar en pérdida completa supera el 85%.
        Devuelve (es_candidato, precio_sl_temprano).
        """
        if entry_price <= 0 or sl_price <= 0 or current_price <= 0:
            return False, 0.0
            
        sl_dist = abs(entry_price - sl_price)
        if sl_dist <= 0:
            return False, 0.0
            
        is_long = "LONG" in side.upper() or "BUY" in side.upper()
        r_profit = (current_price - entry_price) / sl_dist if is_long else (entry_price - current_price) / sl_dist
        
        # Si la excursión adversa supera 0.65R (r_profit <= -0.65)
        if r_profit <= -0.65:
            early_sl = entry_price - (sl_dist * 0.65) if is_long else entry_price + (sl_dist * 0.65)
            return True, round(early_sl, 6)
            
        return False, 0.0

    # --- MÓDULO SIGMA: SINTONIZADOR DE ACTIVOS INSTITUCIONAL v17.0 ---
    # Mega-Caps (BTC, ETH, SOL, XRP, AVAX, LINK): 1H OTE Swing -> Colchón SL amplio (0.60x - 2.5x ATR)
    # High-Beta Alts (RENDER, SUI, INJ, NEAR, FET, PAXG): 15M Scalp -> SL Ágil (0.30x - 1.8x ATR)
    ASSET_TUNING = {
        # 🏛️ MEGA-CAPS (Intraday Swing 1H - Colchón de Liquidez Institucional)
        "BTCUSDT":  {"atr_mult": 2.5, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0002, "min_sl_pct": 0.50, "max_sl_pct": 100.0},
        "ETHUSDT":  {"atr_mult": 2.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0003, "min_sl_pct": 0.60, "max_sl_pct": 100.0},
        "SOLUSDT":  {"atr_mult": 2.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0006, "min_sl_pct": 0.70, "max_sl_pct": 100.0},
        "XRPUSDT":  {"atr_mult": 2.5, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0004, "min_sl_pct": 0.60, "max_sl_pct": 100.0},
        "AVAXUSDT": {"atr_mult": 2.6, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0005, "min_sl_pct": 0.60, "max_sl_pct": 100.0},
        "LINKUSDT": {"atr_mult": 2.5, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0005, "min_sl_pct": 0.60, "max_sl_pct": 100.0},
        
        # 🚀 HIGH-BETA ALTCOINS & DEFENSIVE (Hyper-Scalp 15M / Momentum Expansivo)
        "RENDERUSDT":{"atr_mult": 1.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0008, "min_sl_pct": 0.35, "max_sl_pct": 100.0},
        "SUIUSDT":   {"atr_mult": 1.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0008, "min_sl_pct": 0.35, "max_sl_pct": 100.0},
        "INJUSDT":   {"atr_mult": 1.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0008, "min_sl_pct": 0.35, "max_sl_pct": 100.0},
        "NEARUSDT":  {"atr_mult": 1.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0008, "min_sl_pct": 0.35, "max_sl_pct": 100.0},
        "FETUSDT":   {"atr_mult": 1.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0008, "min_sl_pct": 0.35, "max_sl_pct": 100.0},
        "ATOMUSDT":  {"atr_mult": 1.8, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0008, "min_sl_pct": 0.35, "max_sl_pct": 100.0},
        "BNBUSDT":   {"atr_mult": 2.0, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0004, "min_sl_pct": 0.40, "max_sl_pct": 100.0},
        "PAXGUSDT":  {"atr_mult": 2.0, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0012, "min_sl_pct": 0.30, "max_sl_pct": 100.0}, # Oro
    }
    DEFAULT_TUNING = {"atr_mult": 2.0, "tp1_ratio": 1.3, "tp1_vol": 0.50, "spread_impact": 0.0008, "min_sl_pct": 0.40, "max_sl_pct": 100.0}

    def _adaptive_risk(self, confluence_score: int) -> float:
        """
        Escala el riesgo base según la calidad de la señal (Confluence Score).
        v13.0 SOVEREIGN Adaptive Risk.
        - Score < 50: 0.25% (Supervivencia)
        - Score 50-65: 0.5% (Especulativo)
        - Score 66-79: 1.0% (Sólido)
        - Score 80-89: 1.5% (Alta Convicción)
        - Score 90-100: 2.0% (Institucional Apex)
        """
        if confluence_score < 50: return 0.0025
        if confluence_score < 66: return 0.0050
        if confluence_score < 80: return 0.0100
        if confluence_score < 90: return 0.0150
        return 0.0200

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
        fib_data: dict = None,
        confluence_score: int = 50,
        **kwargs
    ) -> dict:
        """
        Cálculo de posición v13.0 (Adaptive Risk Enabled).
        Ajusta dinámicamente el riesgo y los targets según el activo y la confluencia.
        """
        tuning = self.ASSET_TUNING.get(asset.upper(), self.DEFAULT_TUNING)
        
        # Obtener el régimen de mercado al principio para usarlo en SL y OTE
        regime_str = "RANGING"
        if isinstance(market_regime, dict):
            regime_str = market_regime.get("regime", "RANGING")
        elif isinstance(market_regime, str):
            regime_str = market_regime
        regime_upper = regime_str.upper()

        # [ADAPTIVE RISK v13.0]
        actual_risk_pct = self._adaptive_risk(confluence_score)
        risk_amount_usdt = self.account_balance * actual_risk_pct
        
        # 1. Aplicación de Pulmones (SIGMA ATR Mult) adaptados al Régimen de Mercado
        # En rangos sucios (CHOPPY), ampliamos el stop loss un 30% para evitar el ruido de las mechas.
        atr_multiplier = tuning["atr_mult"]
        if regime_upper == "CHOPPY":
            atr_multiplier *= 1.3
        
        fallback_atr = atr_value if atr_value > 0 else (current_price * 0.005)
        risk_dist = fallback_atr * atr_multiplier
        
        # --- [GOD MODE: SALIDAS ESTRUCTURALES v6.1] ---
        sl = current_price - risk_dist if signal_type == "LONG" else current_price + risk_dist
        tp1 = current_price + (risk_dist * tuning["tp1_ratio"]) if signal_type == "LONG" else current_price - (risk_dist * tuning["tp1_ratio"])

        # Intento de SL Estructural Profundo (Protected Low/High)
        if smc_data or key_levels:
            if signal_type == "LONG":
                # Buscar el OB Alcista o Soporte más CERCANO por debajo del precio
                obs = smc_data.get("order_blocks", {}).get("bullish", []) if smc_data else []
                sups = key_levels.get("supports", []) if key_levels else []
                structural_floors = [ob["bottom"] for ob in obs] + [s["price"] for s in sups]
                valid_floors = [f for f in structural_floors if f < current_price]
                if valid_floors:
                    best_floor = max(valid_floors)
                    # Si es contra-tendencia o picado, le damos más aire al SL (0.8 ATR en lugar de 0.5 ATR)
                    is_counter = (regime_upper in ["MARKDOWN", "BEARISH"])
                    # Darle espacio amplio al SL detrás del bloque (1.2 ATR si choppy/counter, 0.8 ATR normal)
                    atr_mult = 1.2 if (regime_upper == "CHOPPY" or is_counter) else 0.8
                    sl_candidate = best_floor - (fallback_atr * atr_mult)
                    # Límite de seguridad para no fundir la cuenta: 3x del riesgo base
                    if sl_candidate > (current_price - risk_dist * 3.0):
                        sl = sl_candidate
            else:
                # Buscar el OB Bajista o Resistencia más CERCANA por arriba del precio
                obs = smc_data.get("order_blocks", {}).get("bearish", []) if smc_data else []
                res = key_levels.get("resistances", []) if key_levels else []
                structural_ceilings = [ob["top"] for ob in obs] + [r["price"] for r in res]
                valid_ceilings = [c for c in structural_ceilings if c > current_price]
                if valid_ceilings:
                    best_ceiling = min(valid_ceilings)
                    # Si es contra-tendencia o picado, le damos más aire al SL (1.2 ATR en lugar de 0.8 ATR)
                    is_counter = (regime_upper in ["MARKUP", "BULLISH"])
                    atr_mult = 1.2 if (regime_upper == "CHOPPY" or is_counter) else 0.8
                    sl_candidate = best_ceiling + (fallback_atr * atr_mult)
                    if sl_candidate < (current_price + risk_dist * 3.0):
                        sl = sl_candidate

        # ── PROTECCIÓN CONTRA LIQUIDACIONES (Stop Hunt Shield) ──
        # Desplazar el SL detrás de clusters de liquidación masiva cercanos para evitar barridos
        try:
            if liquidations:
                # Buscar la liquidación más grande en la zona del SL
                if signal_type == "LONG":
                    # Zonas de liquidación de Longs por debajo de nuestra entrada que estén cerca de nuestro SL
                    long_liqs = [l["price"] for l in liquidations if l["type"] == "LONG_LIQ" and sl <= l["price"] < current_price]
                    if long_liqs:
                        # Si hay liquidaciones sobre o cerca de nuestro stop, colocamos el SL un 0.2% por DEBAJO de esa zona de liquidación
                        max_liq_zone = min(long_liqs)
                        candidate_sl = max_liq_zone - (current_price * 0.002)
                        if candidate_sl < sl:
                            sl = candidate_sl
                else:
                    # Zonas de liquidación de Shorts por encima de nuestra entrada que estén cerca de nuestro SL
                    short_liqs = [l["price"] for l in liquidations if l["type"] == "SHORT_LIQ" and current_price < l["price"] <= sl]
                    if short_liqs:
                        # Colocamos el SL un 0.2% por ENCIMA de la zona de liquidación de shorts
                        max_liq_zone = max(short_liqs)
                        candidate_sl = max_liq_zone + (current_price * 0.002)
                        if candidate_sl > sl:
                            sl = candidate_sl
        except Exception as liq_err:
            pass

        # ── AJUSTE DE SPREAD DINÁMICO ──
        # Sumar/restar spread en vivo para evitar activaciones prematuras en exchanges de futuros
        spread_buffer = current_price * tuning.get("spread_impact", 0.0010)
        if signal_type == "LONG":
            sl -= spread_buffer
        else:
            sl += spread_buffer

        # Recálculo de riesgo inicial
        initial_risk_dist = abs(current_price - sl)
        
        # ── GUARDARRAÍL DINÁMICO DE VOLATILIDAD ──
        # Definimos una distancia mínima de Stop Loss según la clase de activo para evitar barridos de ruido:
        # Altcoins volátiles: mínimo 1.80% del precio de entrada (Protección anti-ruido de mechas)
        # Criptomonedas de alta capitalización (BTC/ETH) y Oro/Plata: mínimo 0.60% del precio de entrada
        asset_upper = asset.upper()
        if any(core_asset in asset_upper for core_asset in ["BTC", "ETH", "PAXG", "XAG"]):
            dynamic_min_sl_pct = 0.0060  # 0.60%
        else:
            dynamic_min_sl_pct = 0.0180  # 1.80% (Límite de seguridad anti-ruido para altcoins)
            
        min_sl_dist = current_price * dynamic_min_sl_pct
        max_sl_dist = current_price * (tuning.get("max_sl_pct", 100.0) / 100.0)
        
        sl_exceeded_max = False
        if initial_risk_dist < min_sl_dist:
            sl = current_price - min_sl_dist if signal_type == "LONG" else current_price + min_sl_dist
            final_risk = min_sl_dist
        elif initial_risk_dist > max_sl_dist:
            sl_exceeded_max = True
            final_risk = initial_risk_dist
        else:
            final_risk = initial_risk_dist

        if final_risk <= 0: final_risk = current_price * 0.01

        # Intento de TP Magnético (FVG, Liquidaciones, HTF External Liquidity)
        tp2, tp3 = tp1, tp1
        all_targets = []
        
        if signal_type == "LONG":
            liq_targets = [l["price"] for l in (liquidations or []) if l["type"] == "SHORT_LIQ" and l["price"] > current_price and l.get("strength", 0) > 50]
            ob_targets = [ob["bottom"] for ob in (smc_data.get("order_blocks", {}).get("bearish", []) if smc_data else []) if ob["bottom"] > current_price]
            fvg_targets = [fvg["bottom"] for fvg in (smc_data.get("fvg", {}).get("bearish", []) if smc_data else []) if fvg["bottom"] > current_price]
            
            htf_targets = []
            if kwargs.get("htf_bias"):
                hb = kwargs.get("htf_bias")
                if getattr(hb, "pdh", 0) > current_price: htf_targets.append(hb.pdh)
                if getattr(hb, "pwh", 0) > current_price: htf_targets.append(hb.pwh)

            fib_targets = []
            if fib_data and "levels" in fib_data:
                # OTE: 0.618, 0.705, 0.786
                for lvl in ["0.618", "0.786"]:
                    price = fib_data["levels"].get(lvl)
                    if price and price > current_price:
                        fib_targets.append(price)

            all_targets = liq_targets + ob_targets + fvg_targets + htf_targets + fib_targets
            if all_targets:
                all_targets.sort() # De más cercano a más lejano
                
                # [APEX DYNAMIC TARGETING]
                # TP1: Primer target estructural que sea al menos 1.5R neto
                for t in all_targets:
                    if (t - current_price) / final_risk >= 1.5:
                        tp1 = t
                        break
                
                # TP2: Punto de equilibrio o FVG medio
                mid_targets = [t for t in all_targets if t > tp1]
                if mid_targets: tp2 = mid_targets[0]
                else: tp2 = tp1 + (final_risk * 1.5)
                
                # TP3: [ULTIMATE TARGET] Liquidez HTF o Cluster más fuerte
                tp3 = all_targets[-1]
                # Si el target más lejano es masivo (>80% fuerza), forzamos TP3 ahí
                strong_liq = [l["price"] for l in (liquidations or []) if l["type"] == "SHORT_LIQ" and l.get("strength", 0) > 85]
                if strong_liq: tp3 = max(tp3, max(strong_liq))
                
                if tp3 <= tp2: tp3 = tp2 + (final_risk * 2.0)

        else: # SHORT
            liq_targets = [l["price"] for l in (liquidations or []) if l["type"] == "LONG_LIQ" and l["price"] < current_price and l.get("strength", 0) > 50]
            ob_targets = [ob["top"] for ob in (smc_data.get("order_blocks", {}).get("bullish", []) if smc_data else []) if ob["top"] < current_price]
            fvg_targets = [fvg["top"] for fvg in (smc_data.get("fvg", {}).get("bullish", []) if smc_data else []) if fvg["top"] < current_price]
            
            htf_targets = []
            if kwargs.get("htf_bias"):
                hb = kwargs.get("htf_bias")
                if getattr(hb, "pdl", float('inf')) < current_price and getattr(hb, "pdl", 0) > 0: htf_targets.append(hb.pdl)
                if getattr(hb, "pwl", float('inf')) < current_price and getattr(hb, "pwl", 0) > 0: htf_targets.append(hb.pwl)

            fib_targets = []
            if fib_data and "levels" in fib_data:
                # OTE: 0.618, 0.705, 0.786
                for lvl in ["0.618", "0.786"]:
                    price = fib_data["levels"].get(lvl)
                    if price and price < current_price:
                        fib_targets.append(price)

            all_targets = liq_targets + ob_targets + fvg_targets + htf_targets + fib_targets
            if all_targets:
                all_targets.sort(reverse=True) # De más cercano a más lejano (hacia abajo)
                
                for t in all_targets:
                    if (current_price - t) / final_risk >= 1.5:
                        tp1 = t
                        break
                
                mid_targets = [t for t in all_targets if t < tp1]
                if mid_targets: tp2 = mid_targets[0]
                else: tp2 = tp1 - (final_risk * 1.5)
                
        # Red de Seguridad y Garantía Geométrica Estricta de R:R
        # [SOP-26 DYNAMIC MFE HARVESTING GRID 40/40/20]
        # Basado en el MFE empírico de +2.41R:
        # TP1: +1.2R (40% volumen - cubre comisiones y asegura +0.48R neto)
        # TP2: +2.0R (40% volumen - captura el pico óptimo antes de retrocesos a BE)
        # TP3: +3.5R (20% runner con trailing ratchet institucional)
        if signal_type == "LONG":
            calc_tp1 = current_price + (final_risk * 1.2)
            calc_tp2 = current_price + (final_risk * 2.0)
            calc_tp3 = current_price + (final_risk * 3.5)
            
            # Si el target magnético no respeta la jerarquía matemática, aplicamos los niveles R:R geométricos
            if tp1 <= current_price or tp1 < calc_tp1: tp1 = calc_tp1
            if tp2 <= tp1 or tp2 < calc_tp2: tp2 = max(tp2, calc_tp2)
            if tp3 <= tp2 or tp3 < calc_tp3: tp3 = max(tp3, calc_tp3)
        else: # SHORT
            calc_tp1 = current_price - (final_risk * 1.2)
            calc_tp2 = current_price - (final_risk * 2.0)
            calc_tp3 = current_price - (final_risk * 3.5)
            
            # Si el target magnético no respeta la jerarquía matemática, aplicamos los niveles R:R geométricos
            if tp1 >= current_price or tp1 > calc_tp1: tp1 = calc_tp1
            if tp2 >= tp1 or tp2 > calc_tp2: tp2 = min(tp2, calc_tp2)
            if tp3 >= tp2 or tp3 > calc_tp3: tp3 = min(tp3, calc_tp3)

        final_reward = abs(tp1 - current_price)
        final_reward_tp3 = abs(tp3 - current_price)

        sl_dist_pct = final_risk / current_price if current_price > 0 else 0.01
        pos_size_nominal = risk_amount_usdt / max(0.001, sl_dist_pct)
        raw_leverage = min(50, math.ceil(pos_size_nominal / self.account_balance))
        # [SOP-21] Asegurar que el apalancamiento nunca exceda el umbral de liquidación segura
        safe_leverage = self.calculate_safe_leverage(current_price, sl, max_cap=20)
        leverage = min(raw_leverage, safe_leverage)
        
        # [SNIPER v10.0] Validación OTE (Optimal Trade Entry) / Premium-Discount Zone (200 IQ Adaptive Entry)
        is_in_ote = False
        ote_key = "0.5" # Default to 0.5 (Equilibrium - standard discount/premium)
        
        # Determinar umbral dinámico basado en régimen, sesgo HTF y score de confluencia
        htf_bias = kwargs.get("htf_bias")

        # 1. Choppy o score de confluencia bajo -> Exigir descuento/premium profundo (0.618)
        if regime_str.upper() in ["CHOPPY"] or confluence_score < 60:
            ote_key = "0.618"
        # 2. Si hay sesgo HTF muy fuerte a favor, permitir entrada más agresiva (0.5 o 0.382)
        elif htf_bias:
            bias_dir = getattr(htf_bias, "direction", "NEUTRAL").upper()
            bias_strength = getattr(htf_bias, "strength", 0.5)
            
            if signal_type == "LONG" and bias_dir == "BULLISH" and bias_strength >= 0.75:
                if bias_strength >= 0.85:
                    ote_key = "0.382"
                else:
                    ote_key = "0.5"
            elif signal_type == "SHORT" and bias_dir == "BEARISH" and bias_strength >= 0.75:
                if bias_strength >= 0.85:
                    ote_key = "0.382"
                else:
                    ote_key = "0.5"
                    
        if fib_data and "levels" in fib_data:
            levels = fib_data.get("levels", {})
            f_val = levels.get(ote_key, 0)
            if f_val > 0:
                if signal_type == "LONG":
                    # Zona de descuento adaptativa
                    is_in_ote = current_price <= f_val
                else:
                    # Zona de premium adaptativa
                    is_in_ote = current_price >= f_val

        final_reward_tp3 = abs(tp3 - current_price)
        # [FAST BREAKEVEN LOCK v17.2] Nivel exacto a +1.0R para blindar la operación a $0 riesgo
        be_price = current_price + (final_risk * 1.0) if signal_type == "LONG" else current_price - (final_risk * 1.0)

        return {
            "entry_price": round(current_price, 5),
            "stop_loss": round(sl, 5),
            "sl_dist_pct": round(sl_dist_pct * 100, 2),
            "be_price": round(be_price, 5), # Nivel de activación de Breakeven (+1.0R)
            "tp1": round(tp1, 5),
            "tp2": round(tp2, 5),
            "tp3": round(tp3, 5),
            "take_profit_3r": round(tp3, 5),  # Corregido: apunta al target final estructural tp3
            "tp1_vol_pct": tuning["tp1_vol"],
            "risk_amount_usdt": round(risk_amount_usdt, 2), # Compatibility fix
            "risk_usd": round(risk_amount_usdt, 2),
            "risk_pct": round(actual_risk_pct * 100, 2),
            "position_size_usdt": round(pos_size_nominal, 2),
            "suggested_position_usdt": round(pos_size_nominal, 2),
            "leverage": leverage,
            "rr_ratio": round(final_reward / final_risk, 2) if final_risk > 0 else 0,
            "rr_ratio_tp3": round(final_reward_tp3 / final_risk, 2) if final_risk > 0 else 0,
            "entry_zone_top": round(current_price * 1.001, 5),
            "entry_zone_bottom": round(current_price * 0.999, 5),
            "asset": asset,
            "fib_ote": {"is_in_ote": is_in_ote},
            "sl_exceeded_max": sl_exceeded_max
        }

    def calculate_scale_in_sizing(
        self,
        base_position_size_usdt: float,
        base_entry_price: float,
        current_sl: float,
        add_on_entry_price: float,
        new_structural_sl: float,
        signal_type: str = "LONG",
        scale_ratio: float = 0.50,
    ) -> dict:
        """
        [SOP-16 ZERO-RISK SCALE-IN ENGINE v28.0]
        Calcula el dimensionamiento exacto y el Stop Loss compuesto de un Add-On de piramidación.
        
        Garantía Matemática de Invarianza:
        1. La posición base DEBE tener su Stop Loss actual asegurado por encima de su entrada en Longs (o por debajo en Shorts).
        2. Al mover el Stop Loss al new_structural_sl:
           PnL_base = base_size * (new_structural_sl - base_entry) / base_entry (en Longs)
           Risk_addon = addon_size * (add_on_entry - new_structural_sl) / add_on_entry (en Longs)
           Net_PnL = PnL_base - Risk_addon
        3. El Add-on solo es aprobado si Net_PnL >= 0.00 USDT.
        """
        is_long = "LONG" in str(signal_type).upper()
        
        # Validación Base: ¿La orden primaria ya está en ganancia asegurada?
        base_is_protected = (current_sl >= base_entry_price) if is_long else (current_sl <= base_entry_price)
        if not base_is_protected:
            return {
                "approved": False,
                "reason": "Base position is not yet protected in Breakeven/Profit",
                "add_on_size_usdt": 0.0,
                "net_pnl_at_sl": 0.0
            }
            
        nominal_addon_size = base_position_size_usdt * scale_ratio
        
        # PnL de la posición base en el nuevo Stop Loss estructural
        if is_long:
            base_pnl_at_new_sl = base_position_size_usdt * ((new_structural_sl - base_entry_price) / base_entry_price) if base_entry_price > 0 else 0
            addon_loss_at_sl = nominal_addon_size * ((add_on_entry_price - new_structural_sl) / add_on_entry_price) if add_on_entry_price > 0 else 0
        else:
            base_pnl_at_new_sl = base_position_size_usdt * ((base_entry_price - new_structural_sl) / base_entry_price) if base_entry_price > 0 else 0
            addon_loss_at_sl = nominal_addon_size * ((new_structural_sl - add_on_entry_price) / add_on_entry_price) if add_on_entry_price > 0 else 0
            
        net_pnl_at_sl = round(base_pnl_at_new_sl - addon_loss_at_sl, 2)
        
        # Si el net_pnl_at_sl es negativo, reducimos el addon_size para garantizar que sea exactamente >= 0.0
        if net_pnl_at_sl < 0:
            if base_pnl_at_new_sl > 0:
                # Ajustar addon_size para que addon_loss == base_pnl_at_new_sl
                loss_fraction = ((add_on_entry_price - new_structural_sl) / add_on_entry_price) if is_long else ((new_structural_sl - add_on_entry_price) / add_on_entry_price)
                if loss_fraction > 0:
                    nominal_addon_size = round(base_pnl_at_new_sl / loss_fraction, 2)
                    net_pnl_at_sl = 0.0
                else:
                    return {"approved": False, "reason": "Invalid structural SL for add-on", "add_on_size_usdt": 0.0, "net_pnl_at_sl": 0.0}
            else:
                return {
                    "approved": False,
                    "reason": f"Insufficient locked base profit (${base_pnl_at_new_sl:.2f}) to cover scale-in risk",
                    "add_on_size_usdt": 0.0,
                    "net_pnl_at_sl": net_pnl_at_sl
                }
                
        return {
            "approved": True,
            "add_on_size_usdt": round(nominal_addon_size, 2),
            "new_composite_sl": round(new_structural_sl, 5),
            "net_pnl_at_sl": net_pnl_at_sl,
            "scale_ratio": scale_ratio,
            "reason": f"Scale-in approved with guaranteed Net PnL >= ${net_pnl_at_sl:.2f} USDT"
        }
