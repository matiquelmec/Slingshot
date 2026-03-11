import pandas as pd
from engine.indicators.regime import RegimeDetector
from engine.indicators.momentum import apply_criptodamus_suite
from engine.filters.time_filter import TimeFilter
from engine.indicators.volume import confirm_trigger

class ReversionStrategy:
    """
    Estrategia 3: Mean Reversion / Reversión a la Media.
    Operativa en: ACCUMULATION (Suelo) y DISTRIBUTION (Techo).
    Lógica Criptodamus: Busca extremos del mercado usando RSI Sobrevendido/Sobrecomprado 
    y cruces del MACD en zonas de compresión (BBWP Squeeze).
    """
    
    def __init__(self):
        self.time_filter = TimeFilter()
        
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

        # Filtro Temporal (KillZone)
        df['in_killzone'] = df['timestamp'].apply(self.time_filter.is_killzone)

        # Gatillo de Volumen (RVOL)
        df = confirm_trigger(df, min_rvol=1.3)

        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        opportunities = []
        last_signal_idx = {"LONG": -20, "SHORT": -20}
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            
            # --- ESTRATEGIA LONG: Acumulación ---
            if current.get('market_regime') == 'ACCUMULATION':
                if (current.get('rsi_oversold') and 
                    current.get('macd_bullish_cross') and 
                    current.get('in_killzone') and 
                    current.get('valid_trigger')):
                    
                    if i - last_signal_idx["LONG"] > 10:
                        entry = current['close']
                        has_div = current.get('bullish_div', False)
                        
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type":      "LONG 🟢 (REVERSION IN ACCUMULATION)",
                            "signal_type":"LONG",
                            "regime":    current.get('market_regime'),
                            "price":     entry,
                            "trigger":   "RSI < 30 + MACD Bull Cross" + (" + Divergencia" if has_div else ""),
                            "atr_value": current.get('atr_value', 0.0),
                            "has_divergence": has_div
                        })
                        last_signal_idx["LONG"] = i
                        
            # --- ESTRATEGIA SHORT: Distribución ---
            elif current.get('market_regime') == 'DISTRIBUTION':
                if (current.get('rsi_overbought') and 
                    current.get('in_killzone') and 
                    current.get('valid_trigger')):
                    
                    if i - last_signal_idx["SHORT"] > 10:
                        entry = current['close']
                        has_div = current.get('bearish_div', False)
                        
                        opportunities.append({
                            "timestamp": current['timestamp'],
                            "type":      "SHORT 🔴 (REVERSION IN DISTRIBUTION)",
                            "signal_type":"SHORT",
                            "regime":    current.get('market_regime'),
                            "price":     entry,
                            "trigger":   "RSI > 70 in Zone Ceiling" + (" + Divergencia" if has_div else ""),
                            "atr_value": current.get('atr_value', 0.0),
                            "has_divergence": has_div
                        })
                        last_signal_idx["SHORT"] = i
                        
        return opportunities
