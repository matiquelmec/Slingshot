import pandas as pd
from engine.indicators.regime import RegimeDetector
from engine.indicators.momentum import apply_criptodamus_suite
from engine.filters.risk import RiskManager

class ReversionStrategy:
    """
    Estrategia 3: Mean Reversion / Reversión a la Media.
    Operativa en: ACCUMULATION (Suelo) y DISTRIBUTION (Techo).
    Lógica Criptodamus: Busca extremos del mercado usando RSI Sobrevendido/Sobrecomprado 
    y cruces del MACD en zonas de compresión (BBWP Squeeze).
    """
    
    def __init__(self):
        self.risk_manager = RiskManager()
        
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Inyectar suite Criptodamus entera (RSI, MACD, BBWP)
        df = apply_criptodamus_suite(df)
        
        # Filtro de Distancia Extrema (Banda de Bollinger o SMA)
        # Una buena reversión a la media ocurre cuando el precio se alejó absurdamente del promedio.
        # Vamos a usar la distancia a la EMA 50 como trigger de "goma estirada"
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['dist_to_ema50'] = (df['close'] - df['ema_50']) / df['ema_50']
        
        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        opportunities = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            
            # --- ESTRATEGIA LONG: Acumulación (Suelo) ---
            if current['market_regime'] == 'ACCUMULATION':
                # Confluencia Criptodamus Clásica: RSI en el suelo + Cruce Alcista del MACD
                if current['rsi_oversold'] and current['macd_bullish_cross']:
                    # Opcional: Que haya un buen nivel de Squeeze
                    entry = current['close']
                    # SL Técnico: Simplemente un stop de emergencia debajo del precio de la vela
                    stop = current['low'] * 0.99
                    
                    trade = self.risk_manager.calculate_position(entry, stop)
                    if trade['valid']:
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type": "LONG 🟢 (REVERSION IN ACCUMULATION)",
                            "price": entry,
                            "trigger": "RSI < 30 + MACD Bull Cross",
                            "risk": trade['risk_usd'],
                            "position": trade['position_size_usd']
                        })
                        
            # --- ESTRATEGIA SHORT: Distribución (Techo) ---
            elif current['market_regime'] == 'DISTRIBUTION':
                # RSI arriba + Caída inminente (no tenemos cross bajista explícito en el código aún, 
                # así que usamos RSI estirado + el hecho de ser un régimen de techo)
                if current['rsi_overbought']:
                    entry = current['close']
                    # SL Técnico: Stop de emergencia encima de la vela
                    stop = current['high'] * 1.01
                    
                    trade = self.risk_manager.calculate_position(entry, stop)
                    if trade['valid']:
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type": "SHORT 🔴 (REVERSION IN DISTRIBUTION)",
                            "price": entry,
                            "trigger": "RSI > 70 in Zone Ceiling",
                            "risk": trade['risk_usd'],
                            "position": trade['position_size_usd']
                        })
                        
        return opportunities
