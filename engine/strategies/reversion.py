import pandas as pd
from engine.indicators.regime import RegimeDetector
from engine.indicators.momentum import apply_criptodamus_suite

class ReversionStrategy:
    """
    Estrategia 3: Mean Reversion / Reversión a la Media.
    Operativa en: ACCUMULATION (Suelo) y DISTRIBUTION (Techo).
    Lógica Criptodamus: Busca extremos del mercado usando RSI Sobrevendido/Sobrecomprado 
    y cruces del MACD en zonas de compresión (BBWP Squeeze).
    """
    
    def __init__(self):
        # RiskManager removed for cleaner logic
        pass
        
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Paso 0: Inyectar régimen si el DataFrame no lo tiene todavía
        # (garantiza que la estrategia funcione tanto desde SlingshotRouter
        # como desde tests directos / scripts externos)
        if 'market_regime' not in df.columns:
            regime_detector = RegimeDetector()
            df = regime_detector.detect_regime(df)

        # Inyectar suite Criptodamus entera (RSI, MACD, BBWP)
        df = apply_criptodamus_suite(df)

        # Distancia extrema a la EMA 50 ("goma estirada")
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['dist_to_ema50'] = (df['close'] - df['ema_50']) / df['ema_50']

        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        opportunities = []
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            
            # --- ESTRATEGIA LONG: Acumulación (Suelo) ---
            if current.get('market_regime') == 'ACCUMULATION':
                if current.get('rsi_oversold') and current.get('macd_bullish_cross'):
                    entry = current['close']
                    stop  = current['low'] * 0.99
                    trade = self.risk_manager.calculate_position(entry, stop)
                    if trade['valid']:
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type":      "LONG 🟢 (REVERSION IN ACCUMULATION)",
                            "price":     entry,
                            "trigger":   "RSI < 30 + MACD Bull Cross",
                            "risk":      trade['risk_usd'],
                            "position":  trade['position_size_usd']
                        })
                        
            # --- ESTRATEGIA SHORT: Distribución (Techo) ---
            elif current.get('market_regime') == 'DISTRIBUTION':
                if current.get('rsi_overbought'):
                    entry = current['close']
                    stop  = current['high'] * 1.01
                    # Mock risk logic
                    trade = {"valid": True, "risk_usd": 10.0, "position_size_usd": 200.0}
                    if trade['valid']:
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type":      "SHORT 🔴 (REVERSION IN DISTRIBUTION)",
                            "price":     entry,
                            "trigger":   "RSI > 70 in Zone Ceiling",
                            "risk":      trade['risk_usd'],
                            "position":  trade['position_size_usd']
                        })
                        
        return opportunities
