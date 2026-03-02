import pandas as pd
from engine.indicators.regime import RegimeDetector
from engine.indicators.fibonacci import identify_dynamic_fib_swing
from engine.filters.time_filter import TimeFilter
from engine.indicators.volume import confirm_trigger

class TrendFollowingStrategy:
    """
    Estrategia 2: Trend Following (Continuación).
    Operativa en: MARKUP (Alcista Fuerte) y MARKDOWN (Bajista Fuerte).
    Lógica Criptodamus (Mejora Entradas): Retroceso (Pullback) a la EMA 50 
    que confluye con el Golden Pocket 0.618 de Fibonacci.
    """
    
    def __init__(self):
        self.time_filter = TimeFilter()
        
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Paso 0: Inyectar régimen si el DataFrame no lo tiene todavía
        if 'market_regime' not in df.columns:
            from engine.indicators.regime import RegimeDetector
            df = RegimeDetector().detect_regime(df)

        # 1. EMA de Corto/Mediano Plazo (Soporte Dinámico Criptodamus)
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

        # 2. Fibonacci Swing y Golden Pocket
        df = identify_dynamic_fib_swing(df, window=60)

        # 3. Pullback a las EMAs
        df['pullback_to_ema50_bull'] = (df['low'] <= df['ema_50']) & (df['close'] > df['ema_50'])
        df['pullback_to_ema50_bear'] = (df['high'] >= df['ema_50']) & (df['close'] < df['ema_50'])

        # 4. Filtro Temporal (KillZone)
        df['in_killzone'] = df['timestamp'].apply(self.time_filter.is_killzone)

        # 5. Gatillo de Volumen (RVOL)
        df = confirm_trigger(df, min_rvol=1.2) # Menos estricto que SMC (1.5) para continuación

        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        opportunities = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            
            # --- ESTRATEGIA LONG: Pullback en MARKUP ---
            if current.get('market_regime') == 'MARKUP':
                if current.get('pullback_to_ema50_bull') and current.get('in_golden_pocket') and current.get('in_killzone') and current.get('valid_trigger'):
                    entry = current['close']
                    nearest_structural = current.get('swing_low', current['low'])
                    
                    opportunities.append({
                        "timestamp": current['timestamp'],
                        "type":      "LONG 🟢 (TREND PULLBACK)",
                        "signal_type":"LONG",
                        "regime":    current.get('market_regime'),
                        "price":     entry,
                        "nearest_structural_level": nearest_structural,
                        "trigger":   "EMA 50 + Fibo 0.618 Confluencia",
                        "atr_value": current.get('atr_value', 0.0)
                    })
                        
            # --- ESTRATEGIA SHORT: Pullback en MARKDOWN ---
            # (No implementamos Fibonacci Bearish estricto en el indicador aún, 
            # pero podríamos usar solo el rechazo de la EMA en Downtrend)
            elif current.get('market_regime') == 'MARKDOWN':
                if current.get('pullback_to_ema50_bear') and current.get('in_killzone') and current.get('valid_trigger'):
                    entry = current['close']
                    nearest_structural = current.get('ema_50', current['high'])
                    
                    opportunities.append({
                        "timestamp": current['timestamp'],
                        "type":      "SHORT 🔴 (TREND PULLBACK)",
                        "signal_type":"SHORT",
                        "regime":    current.get('market_regime'),
                        "price":     entry,
                        "nearest_structural_level": nearest_structural,
                        "trigger":   "Rechazo de EMA 50 en Downtrend",
                        "atr_value": current.get('atr_value', 0.0)
                    })
                        
        return opportunities
