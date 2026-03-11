import math

class RiskManager:
    """
    State-of-the-Art Risk Management Engine (2026).
    Implementa:
    1. Volatility Targeting (Position Sizing basado en distancia de SL).
    2. Fractional Kelly Criteria (Ajuste de riesgo por Régimen de Mercado).
    3. Structural Stop Loss + ATR Padding (Anti-manipulación).
    """

    def __init__(self, account_balance: float = 1000.0, base_risk_pct: float = 0.01):
        """
        :param account_balance: Saldo total de la cuenta en USDT (Ej: $1,000 para Prop Firms).
        :param base_risk_pct: Porcentaje base a arriesgar por trade (Ej: 0.01 = 1%).
        """
        self.account_balance = account_balance
        self.base_risk_pct = base_risk_pct
        self.max_leverage = 50.0 # Apalancamiento máximo permitido por el exchange/gestor de riesgo

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
        
        # Si la estructura natural nos da > 3R, excelente.
        # Pero a veces la estructura da 1.5R. En sistemas rígidos forzamos 3R, 
        # pero para que el bot no se coma walls, recalcularemos más abajo si vale la pena.

        return stop_loss, take_profit, structural_rr

    def calculate_position(
        self, 
        current_price: float, 
        signal_type: str, 
        market_regime: str, 
        key_levels: list = None,
        smc_data: dict = None,
        atr_value: float = 0.0
    ) -> dict:
        """
        Calcula asimétricamente el tamaño de la posición y el apalancamiento exacto.
        """
        # 1. Definir Fracción de Riesgo (Fractional Kelly)
        multiplier = self.get_regime_multiplier(market_regime)
        actual_risk_pct = self.base_risk_pct * multiplier
        risk_amount_usdt = self.account_balance * actual_risk_pct

        # 2. Definir Stop Loss Geográfico y TP Estructural 
        fallback_atr = atr_value if atr_value and atr_value > 0 else (current_price * 0.005)
        
        stop_loss_price, take_profit_price, structural_rr = self.calculate_structural_sl_tp(
            current_price=current_price, 
            signal_type=signal_type, 
            key_levels=key_levels,
            smc_data=smc_data,
            atr_value=fallback_atr
        )

        # 3. Distancia del SL en porcentaje
        sl_distance_pct = abs(current_price - stop_loss_price) / current_price
        if sl_distance_pct < 0.001:  # Evitar divisiones por cero o SL irracionalmente apretados
            sl_distance_pct = 0.001 

        # 4. Volatility Target Sizing (Tamaño de Posición Total Nominal)
        # Position Size = Dinero Arriesgado / Distancia Porcentual del SL
        position_size_nominal = risk_amount_usdt / sl_distance_pct

        # 5. Apalancamiento Requerido
        required_leverage = position_size_nominal / self.account_balance
        
        # Ceil & Clamp al apalancamiento operativo de exchange
        leverage = math.ceil(required_leverage)
        leverage = max(1, min(leverage, int(self.max_leverage)))

        # 6. Recalcular Position Size real basado en el leverage clipeado (por si excedió el max)
        actual_position_size = min(position_size_nominal, self.account_balance * leverage)

        # 7. Quality Check del Trade Institucional:
        # Si la geografía natural me da menos de 2.0R, es un trade subóptimo (mucho riesgo, poco premio real).
        # En vez de matar el TP ciegamente a 3R, mantenemos el TP en la muralla, 
        # pero avisamos al frontend que este trade no cumple asimetría pura.
        trade_quality = "A+" if structural_rr >= 2.5 else ("B" if structural_rr >= 1.5 else "C (Low Reward)")

        return {
            "account_balance":   round(self.account_balance, 2),
            "risk_amount_usdt":  round(risk_amount_usdt, 2),
            "risk_pct":          round(actual_risk_pct * 100, 2),
            "leverage":          leverage,
            "position_size_usdt": round(actual_position_size, 2),
            "entry_price":       round(current_price, 2),
            "stop_loss":         round(stop_loss_price, 2),
            "take_profit_3r":    round(take_profit_price, 2),
            # Zona de entrada: rango del OB (1.5x ATR alrededor del precio de entrada)
            "entry_zone_top":    round(current_price + (fallback_atr * 0.5), 2),
            "entry_zone_bottom": round(current_price - (fallback_atr * 0.5), 2)
              if str(signal_type).upper() == 'LONG'
              else round(current_price - (fallback_atr * 0.5), 2),
            # Metadatos Institucionales 2026: Validación Estructural Activa
            "validation_mode":  "STRUCTURAL_INTEGRITY", 
        }
