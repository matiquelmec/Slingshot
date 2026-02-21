import pandas as pd
from engine.indicators.regime import RegimeDetector
from engine.indicators.fibonacci import identify_dynamic_fib_swing
from engine.filters.risk import RiskManager

class TrendFollowingStrategy:
    """
    Estrategia 2: Trend Following (Continuación).
    Operativa en: MARKUP (Alcista Fuerte) y MARKDOWN (Bajista Fuerte).
    Lógica Criptodamus (Mejora Entradas): Retroceso (Pullback) a la EMA 50 
    que confluye con el Golden Pocket 0.618 de Fibonacci.
    """
    
    def __init__(self):
        self.risk_manager = RiskManager()
        
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 1. EMA de Corto/Mediano Plazo (Soporte Dinámico Criptodamus)
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # 2. Fibonacci Swing y Golden Pocket
        df = identify_dynamic_fib_swing(df, window=60) # Ventana un poco más amplia para el swing principal
        
        # 3. Pullback a las EMAs
        # Alcista: Precio cae hacia la EMA 50 desde arriba
        df['pullback_to_ema50_bull'] = (df['low'] <= df['ema_50']) & (df['close'] > df['ema_50'])
        
        # Bajista: Precio sube hacia la EMA 50 desde abajo
        df['pullback_to_ema50_bear'] = (df['high'] >= df['ema_50']) & (df['close'] < df['ema_50'])
        
        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        opportunities = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            
            # --- ESTRATEGIA LONG: Pullback en MARKUP ---
            if current['market_regime'] == 'MARKUP':
                # Confluencia: Toca la EMA 50 y además está en el Golden Pocket de Fib
                if current['pullback_to_ema50_bull'] and current['in_golden_pocket']:
                    
                    entry = current['close']
                    # SL Técnico: Debajo del Swing Low que formó el Fibo
                    stop = current['swing_low'] * 0.99 
                    
                    trade = self.risk_manager.calculate_position(entry, stop)
                    if trade['valid']:
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type": "LONG 🟢 (TREND PULLBACK)",
                            "price": entry,
                            "trigger": "EMA 50 + Fibo 0.618 Confluencia",
                            "risk": trade['risk_usd'],
                            "position": trade['position_size_usd']
                        })
                        
            # --- ESTRATEGIA SHORT: Pullback en MARKDOWN ---
            # (No implementamos Fibonacci Bearish estricto en el indicador aún, 
            # pero podríamos usar solo el rechazo de la EMA en Downtrend)
            elif current['market_regime'] == 'MARKDOWN':
                if current['pullback_to_ema50_bear']:
                    entry = current['close']
                    # SL Técnico: Encima de la EMA 50 + un filtro ATR (simplificado a %)
                    stop = current['ema_50'] * 1.01 
                    
                    trade = self.risk_manager.calculate_position(entry, stop)
                    if trade['valid']:
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type": "SHORT 🔴 (TREND PULLBACK)",
                            "price": entry,
                            "trigger": "Rechazo de EMA 50 en Downtrend",
                            "risk": trade['risk_usd'],
                            "position": trade['position_size_usd']
                        })
                        
        return opportunities
