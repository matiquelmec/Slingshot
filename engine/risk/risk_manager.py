import math

# Ratio Riesgo/Beneficio mínimo NETO (tras comisiones y slippage)
MIN_RR_REQUIRED = 1.8

# Factor de Fricción Operativa (0.1% comisión entrada + 0.1% salida + 0.05% slippage estimado)
FEE_SLIPPAGE_IMPACT = 0.0025 

# Límite de pérdida diaria máxima por cuenta (3.5%)
MAX_DAILY_DRAWDOWN_PCT = 0.035

class RiskManager:
    """
    State-of-the-Art Risk Management Engine v3.0 (Local Master Edition).
    Implementa:
    1. Volatility Targeting (Position Sizing basado en distancia de SL).
    2. Fractional Kelly Criteria (Ajuste de riesgo por Régimen de Mercado).
    3. Structural Stop Loss + ATR Padding (Anti-manipulación).
    4. [NUEVO] Portero Institucional: Rechaza señales con R:R insuficiente.
    """

    def __init__(self, account_balance: float = 1000.0, base_risk_pct: float = 0.01, min_rr: float = MIN_RR_REQUIRED):
        """
        :param account_balance: Saldo total de la cuenta en USDT (Ej: $1,000 para Prop Firms).
        :param base_risk_pct: Porcentaje base a arriesgar por trade (Ej: 0.01 = 1%).
        :param min_rr: Ratio Riesgo/Beneficio mínimo para aprobar una señal (default: 1.8).
        """
        self.account_balance = account_balance
        self.base_risk_pct = base_risk_pct
        self.min_rr = min_rr
        self.max_leverage = 50.0 
        
        # --- ESTADO DE AUDITORÍA DIARIA ---
        self.daily_loss_usd = 0.0
        self.active_sectors = set() # Ejemplo: {'MAJOR-CRYPTO', 'SOL-ECOSYSTEM'}
        self.is_locked = False

    def validate_signal(self, signal_data: dict) -> dict:
        """
        [PORTERO INSTITUCIONAL v4.1 Platinum]
        Evalúa si una señal merece ser publicada al Signal Terminal.
        Inyecta los 'SMC Gates' para validar volumen y alineación HTF.
        """
        try:
            # ⛔ 1. Verificación de Hard-Stop Diario (Pilar 4.1)
            if self.is_locked or self.daily_loss_usd >= (self.account_balance * MAX_DAILY_DRAWDOWN_PCT):
                self.is_locked = True
                return {"approved": False, "rr_ratio": 0.0, "trade_quality": "LOCKED", "reason": "📛 HARD-STOP: Límite de pérdida diaria alcanzado (3.5%)"}

            # ⛔ 2. SMC GATES: Volumen y Alineación (Pilar 2)
            # Solo si la señal contiene estos diagnósticos del MarketAnalyzer
            if signal_data.get("htf_alignment") is False:
                 return {"approved": False, "rr_ratio": 0.0, "trade_quality": "RECHAZADA 🟠", "reason": "TENSIÓN HTF: Contra tendencia mayor detectada."}
            
            if signal_data.get("displacement_valid") is False:
                 rvol = signal_data.get("diagnostic", {}).get("rvol", "N/A")
                 return {"approved": False, "rr_ratio": 0.0, "trade_quality": "RECHAZADA 🔴", "reason": f"SMC DÉBIL: Ruptura sin volumen real (RVOL {rvol} < 1.2)"}

            # ⛔ 3. VALIDACIÓN DE PRECIOS
            entry = float(signal_data.get("price", 0))
            sl    = float(signal_data.get("stop_loss", 0))
            tp    = float(signal_data.get("take_profit_3r", 0))
            asset = signal_data.get("asset", "UNKNOWN")

            if entry <= 0 or sl <= 0 or tp <= 0:
                return {"approved": False, "rr_ratio": 0.0, "trade_quality": "INVALID", "reason": "Precios inválidos"}

            # --- CÁLCULO DE R:R NETO (v4.1 Platinum) ---
            raw_risk   = abs(entry - sl)
            raw_reward = abs(tp - entry)
            friction_cost = entry * FEE_SLIPPAGE_IMPACT
            net_risk   = raw_risk + friction_cost
            net_reward = raw_reward - friction_cost 

            if net_risk < 0.0001:
                return {"approved": False, "rr_ratio": 0.0, "trade_quality": "INVALID", "reason": "Riesgo nulo"}
            
            rr = round(net_reward / net_risk, 2)
            
            # --- DETERMINACIÓN DE CALIDAD ---
            if rr >= 2.5:   quality = "A+ (Institutional)"
            elif rr >= 1.8: quality = "B (Acceptable)"
            else:           quality = "D (RECHAZADA 🔴)"

            # Verificación de Exposición Correlacionada (Beta Management)
            current_risk_multiplier = 1.0
            if asset in ["BTCUSDT", "ETHUSDT"] and len([s for s in self.active_sectors if s == "MAJOR"]) > 0:
                current_risk_multiplier = 0.5 

            # GATE FINAL: R:R Mínimo Neto
            approved = rr >= self.min_rr
            reason = (
                f"R:R NETO {rr:.2f}R (Fricción: {FEE_SLIPPAGE_IMPACT*100:.2f}%) → APROBADA 🟢"
                if approved else
                f"R:R NETO {rr:.2f}R < {self.min_rr}R mínimo → RECHAZADA 🔴"
            )

            return {
                "approved": approved, 
                "rr_ratio": rr, 
                "trade_quality": quality, 
                "reason": reason,
                "risk_multiplier": current_risk_multiplier
            }

        except Exception as e:
            return {"approved": False, "rr_ratio": 0.0, "trade_quality": "ERROR", "reason": str(e)}


    def get_regime_multiplier(self, market_regime: str) -> float:
        """
        Fractional Kelly: Ajusta el acelerador de riesgo en base al terreno.
        """
        regime = str(market_regime).upper()
        if regime in ['MARKUP', 'MARKDOWN']:
            return 1.5   # Tendencia fuerte: Aceleramos el riesgo al 1.5%
        elif regime in ['ACCUMULATION', 'DISTRIBUTION']:
            return 1.0   # Zonas de giro: Riesgo base estricto 1.0%
        elif regime in ['RANGING', 'UNKNOWN']:
            return 0.5   # Ruido de mercado: Riesgo defensivo 0.5%
        return 1.0

    def calculate_structural_sl_tp(
        self, 
        current_price: float, 
        signal_type: str, 
        key_levels: list, 
        smc_data: dict, 
        atr_value: float
    ) -> dict:
        """
        [NIVEL INSTITUCIONAL 2026] 
        Escanea el mapa topográfico de liquidez para ubicar:
        1. Stop Loss: Protegido por Order Blocks defensivos + S/R cercanos + ATR Padding.
        2. Take Profit: Asimétrico, apuntando al siguiente muro de liquidez (mínimo antes de la colisión).
        3. Validación de Risk:Reward: Evalúa si vale la pena tomar el trade geográficamente.
        """
        padding = atr_value * 1.5 # Colchón de seguridad
        
        # 1. Agrupar defensas (lo que protege mi SL) y objetivos (lo que frena mi TP)
        bullish_defenses = [] # Soportes y OBs alcistas
        bearish_defenses = [] # Resistencias y OBs bajistas
        
        if key_levels:
            if isinstance(key_levels, dict):
                # Caso: Diccionario estructurado (Salida directa de get_key_levels)
                bullish_defenses.extend([lvl['price'] for lvl in key_levels.get('supports', [])])
                bearish_defenses.extend([lvl['price'] for lvl in key_levels.get('resistances', [])])
            elif isinstance(key_levels, list):
                # Caso: Lista plana de niveles
                bullish_defenses.extend([lvl['price'] for lvl in key_levels if str(lvl.get('type', '')).upper() == 'SUPPORT'])
                bearish_defenses.extend([lvl['price'] for lvl in key_levels if str(lvl.get('type', '')).upper() == 'RESISTANCE'])
            
        if smc_data:
            if smc_data.get('order_blocks'):
                bullish_defenses.extend([ob['bottom'] for ob in smc_data['order_blocks'].get('bullish', [])])
                bearish_defenses.extend([ob['top'] for ob in smc_data['order_blocks'].get('bearish', [])])
            if smc_data.get('fvgs'):
                bullish_defenses.extend([fvg['bottom'] for fvg in smc_data['fvgs'].get('bullish', [])])
                bearish_defenses.extend([fvg['top'] for fvg in smc_data['fvgs'].get('bearish', [])])
                
        # Ordenar (Soportes de mayor a menor, Resistencias de menor a mayor)
        bullish_defenses = sorted([d for d in bullish_defenses if d < current_price], reverse=True)
        bearish_defenses = sorted([d for d in bearish_defenses if d > current_price])

        if str(signal_type).upper() == 'LONG':
            # --- STOP LOSS LONG ---
            # Busco el soporte u OB Bullish más cercano debajo del precio
            valid_defense = bullish_defenses[0] if bullish_defenses else (current_price - atr_value * 2)
            # Para evitar SL absurdamente pegaditos si el precio es exactamente el soporte
            if (current_price - valid_defense) < (atr_value * 0.5):
                valid_defense = current_price - (atr_value * 1.5)
            stop_loss = valid_defense - padding
            
            # --- TAKE PROFIT LONG ---
            # Busco la resistencia u OB Bearish más cercano arriba del precio
            # Ignoramos muros que estén a menos de 1 ATR de distancia
            valid_targets = [t for t in bearish_defenses if (t - current_price) > atr_value]
            first_wall = valid_targets[0] if valid_targets else (current_price + atr_value * 5)
            
            # El Take Profit se pone "Ligeramente antes" del muro para garantizar lenado (Frontrunning)
            take_profit = first_wall - (atr_value * 0.2)
            
        elif str(signal_type).upper() == 'SHORT':
            # --- STOP LOSS SHORT ---
            # Busco la resistencia u OB Bearish más cercano arriba del precio
            valid_defense = bearish_defenses[0] if bearish_defenses else (current_price + atr_value * 2)
            if (valid_defense - current_price) < (atr_value * 0.5):
                valid_defense = current_price + (atr_value * 1.5)
            stop_loss = valid_defense + padding
            
            # --- TAKE PROFIT SHORT ---
            # Busco el soporte u OB Bullish más cercano debajo del precio
            valid_targets = [t for t in bullish_defenses if (current_price - t) > atr_value]
            first_wall = valid_targets[0] if valid_targets else (current_price - atr_value * 5)
            
            # El TP se pone ligeramente por encima del muro de soporte
            take_profit = first_wall + (atr_value * 0.2)
            
        else:
            stop_loss = current_price * 0.99
            take_profit = current_price * 1.01

        # 3. Validación de Geometría del Trade (Risk:Reward)
        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        
        # Evitar división por cero
        risk = risk if risk > 0 else 0.0001
        structural_rr = reward / risk
        
        return stop_loss, take_profit, structural_rr

    def calculate_position(
        self, 
        current_price: float, 
        signal_type: str, 
        market_regime: str, 
        key_levels: list = None,
        smc_data: dict = None,
        atr_value: float = 0.0,
        smt_strength: float = 0.0
    ) -> dict:
        """
        Calcula asimétricamente el tamaño de la posición y el apalancamiento exacto.
        Implementa modo 'Institutional Run' v4.3 si SMT > 0.8.
        """
        # 1. Fracción de Riesgo (Kelly)
        multiplier = self.get_regime_multiplier(market_regime)
        actual_risk_pct = self.base_risk_pct * multiplier
        risk_amount_usdt = self.account_balance * actual_risk_pct

        # 2. Stop Loss Geográfico y TP Estructural
        fallback_atr = atr_value if atr_value and atr_value > 0 else (current_price * 0.005)
        stop_loss_price, take_profit_price, structural_rr = self.calculate_structural_sl_tp(
            current_price=current_price, signal_type=signal_type, key_levels=key_levels,
            smc_data=smc_data, atr_value=fallback_atr
        )

        # 3. Lógica Institucional de Salida Dinámica (MODO V4.3 TITANIUM)
        exit_strategy = "ESTÁNDAR"
        trailing_stop_logic = "NONE"
        tp1 = take_profit_price
        tp2 = None
        
        if smt_strength >= 0.8:
            exit_strategy = "INSTITUTIONAL RUN 🏃"
            # TP1: Ratio 2.0R (Asegurar 50% de la posición)
            risk = abs(current_price - stop_loss_price)
            tp1_rr = 2.0
            tp1 = current_price + (risk * tp1_rr) if signal_type == "LONG" else current_price - (risk * tp1_rr)
            
            # TP2: Liquidez Externa (Muro Estructural Siguiente)
            # Busco la siguiente barrera más allá de TP1
            tp2 = take_profit_price # En v3.2 ya busca el primer muro
            
            # Trailing Stop Protocol para FTMO
            trailing_stop_logic = "BE+1_THEN_FVG_TRAIL"

        # 4. Cálculo de Sizing
        sl_distance_pct = abs(current_price - stop_loss_price) / current_price
        sl_distance_pct = max(0.001, sl_distance_pct)

        pos_size_nominal = risk_amount_usdt / sl_distance_pct
        leverage = min(int(self.max_leverage), math.ceil(pos_size_nominal / self.account_balance))
        actual_pos_size = min(pos_size_nominal, self.account_balance * leverage)

        return {
            "account_balance":   round(self.account_balance, 2),
            "risk_amount_usdt":  round(risk_amount_usdt, 2),
            "risk_pct":          round(actual_risk_pct * 100, 2),
            "leverage":          leverage,
            "position_size_usdt": round(actual_pos_size, 2),
            "stop_loss":         round(stop_loss_price, 2),
            "tp1":               round(tp1, 2),
            "tp2":               round(tp2, 2) if tp2 else None,
            "take_profit_3r":    round(tp1, 2), # Legacy compatible
            "exit_strategy":     exit_strategy,
            "trailing_stop":     trailing_stop_logic,
            "smt_strength_bonus": smt_strength,
            "expiry_candles":    3,   # La señal es válida por 3 velas (45min en 15m)
        }
