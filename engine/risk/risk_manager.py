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

    def calculate_structural_sl(self, current_price: float, signal_type: str, nearest_level: float, atr_value: float) -> float:
        """
        Calcula el Stop Loss geográfico con ATR padding para absorber Wicks corporativos.
        """
        padding = atr_value * 1.5 # Colchón de 1.5x el rango verdadero promedio

        if str(signal_type).upper() == 'LONG':
            # Si es LONG, el SL va por debajo del soporte más cercano menos el padding
            if nearest_level and nearest_level < current_price:
                return nearest_level - padding
            else:
                return current_price - (atr_value * 2) # Fallback rígido

        elif str(signal_type).upper() == 'SHORT':
            # Si es SHORT, el SL va por encima de la resistencia más cercana más el padding
            if nearest_level and nearest_level > current_price:
                return nearest_level + padding
            else:
                return current_price + (atr_value * 2) # Fallback rígido
                
        return current_price * 0.99 # Fallback de emergencia

    def calculate_position(
        self, 
        current_price: float, 
        signal_type: str, 
        market_regime: str, 
        nearest_structural_level: float = None,
        target_level: float = None,
        atr_value: float = 0.0
    ) -> dict:
        """
        Calcula asimétricamente el tamaño de la posición y el apalancamiento exacto.
        """
        # 1. Definir Fracción de Riesgo (Fractional Kelly)
        multiplier = self.get_regime_multiplier(market_regime)
        actual_risk_pct = self.base_risk_pct * multiplier
        risk_amount_usdt = self.account_balance * actual_risk_pct

        # 2. Definir Stop Loss Geográfico (ATR Padding)
        fallback_atr = atr_value if atr_value and atr_value > 0 else (current_price * 0.005)
        stop_loss_price = self.calculate_structural_sl(
            current_price=current_price, 
            signal_type=signal_type, 
            nearest_level=nearest_structural_level, 
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
        # Cuánto de mi cuenta necesito comprometer prestado para alcanzar esa posición nominal
        required_leverage = position_size_nominal / self.account_balance
        
        # Ceil & Clamp al apalancamiento operativo de exchange
        leverage = math.ceil(required_leverage)
        leverage = max(1, min(leverage, int(self.max_leverage)))

        # 6. Recalcular Position Size real basado en el leverage clipeado (por si excedió el max)
        actual_position_size = min(position_size_nominal, self.account_balance * leverage)

        # 7. Take Profit Dinámico (Asimetría)
        # Ratio Riesgo:Beneficio base de 1:2 si no hay un 'target_level'
        risk_distance_abs = abs(current_price - stop_loss_price)
        if str(signal_type).upper() == 'LONG':
            take_profit_price = target_level if target_level and target_level > current_price else current_price + (risk_distance_abs * 2)
        else:
            take_profit_price = target_level if target_level and target_level < current_price else current_price - (risk_distance_abs * 2)

        return {
            "account_balance": round(self.account_balance, 2),
            "risk_amount_usdt": round(risk_amount_usdt, 2),
            "risk_pct": round(actual_risk_pct * 100, 2),
            "leverage": leverage,
            "position_size_usdt": round(actual_position_size, 2),
            "entry_price": round(current_price, 2),
            "stop_loss": round(stop_loss_price, 2),
            "take_profit": round(take_profit_price, 2)
        }
