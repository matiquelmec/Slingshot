import pandas as pd
from pathlib import Path
import json

# Motores e Indicadores
from engine.indicators.regime import RegimeDetector
from engine.indicators.structure import identify_support_resistance

# Estrategias
from engine.strategy import PaulPerdicesStrategy # Estrategia SMC (Distribución/Manipulación)
from engine.strategies.trend import TrendFollowingStrategy # Estrategia Continuación (Markup/Markdown)
from engine.strategies.reversion import ReversionStrategy # Estrategia Reversión (Acumulación)

class SlingshotRouter:
    """
    El Cerebro Supremo de SLINGSHOT (Capa 2 -> Capa 3).
    Ingiere OHLCV, detecta el Régimen de Wyckoff, mapea Soportes/Resistencias,
    y rutea los datos SOLAMENTE a la estrategia matemáticamente correcta.
    """
    
    def __init__(self):
        self.regime_detector = RegimeDetector()
        
        # Instanciar el arsenal estratégico
        self.strat_smc = PaulPerdicesStrategy()
        self.strat_trend = TrendFollowingStrategy()
        self.strat_reversion = ReversionStrategy()
        
    def process_market_data(self, df: pd.DataFrame, asset: str = "BTCUSDT") -> dict:
        """
        El pipeline principal. Por aquí pasará cada vela en vivo.
        """
        df = df.copy()
        
        # 1. Mapeo Topográfico Base (Soportes/Resistencias Horizontales Clásicos)
        df = identify_support_resistance(df)
        
        # 2. Detección de Régimen de Wyckoff
        df = self.regime_detector.detect_regime(df)
        
        current_regime = df['market_regime'].iloc[-1]
        
        # Diccionario de resultados
        result = {
            "asset": asset,
            "timestamp": str(df['timestamp'].iloc[-1]),
            "current_price": df['close'].iloc[-1],
            "market_regime": current_regime,
            "nearest_support": df['support_level'].iloc[-1] if 'support_level' in df.columns else None,
            "nearest_resistance": df['resistance_level'].iloc[-1] if 'resistance_level' in df.columns else None,
            "active_strategy": None,
            "signals": []
        }
        
        # 3. ENRUTAMIENTO INTELIGENTE (El 'Switch' Maestro)
        if current_regime == 'ACCUMULATION':
            result["active_strategy"] = "ReversionStrategy (Longs on Floor)"
            analyzed_df = self.strat_reversion.analyze(df)
            opportunities = self.strat_reversion.find_opportunities(analyzed_df)
            
        elif current_regime in ['MARKUP', 'MARKDOWN']:
            result["active_strategy"] = "TrendFollowingStrategy (Pullbacks + Fibo)"
            analyzed_df = self.strat_trend.analyze(df)
            opportunities = self.strat_trend.find_opportunities(analyzed_df)
            
        elif current_regime == 'DISTRIBUTION':
            # En distribución buscamos manipulaciones de techo o cacerías de liquidez
            result["active_strategy"] = "PaulPerdicesSMC (Liquidity Sweeps & OBs)"
            analyzed_df = self.strat_smc.analyze(df)
            opportunities = self.strat_smc.find_opportunities(analyzed_df)
            
        elif current_regime == 'RANGING':
            # Rango medio (ni sobrecomprado ni sobrevendido)
            result["active_strategy"] = "Standby (Awaiting Breakout)"
            opportunities = []
            
        else:
            # UNKNOWN (Falta historial para medias móviles o comportamiento anómalo)
            result["active_strategy"] = "STANDBY (Calibrating moving averages...)"
            opportunities = []
            
        # Extraer solo la última señal si la hay (ya que estamos procesando vela a vela en vivo idealmente)
        if opportunities:
            # Filtrar solo señales generadas en la vela actual o muy reciente
            latest_signal = opportunities[-1]
            if str(latest_signal['timestamp']) == result['timestamp']:
                result['signals'].append(latest_signal)
                
        return result

if __name__ == "__main__":
    import os
    
    file_path = Path(__file__).parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        
        router = SlingshotRouter()
        
        print("🧠 INICIANDO ENRUTADOR MAESTRO SLINGSHOT...\n")
        
        # Simularemos cómo operaría el bot leyendo las últimas 5 velas históricas
        print("Simulando Pipeline en Tiempo Real (Últimas 5 velas de 15m):")
        print("-" * 60)
        
        for i in range(5, 0, -1):
            # Recortar el dataframe imaginando que estamos en ese punto en el tiempo
            simulated_live_data = data.iloc[:-i]
            
            if len(simulated_live_data) > 200: # Necesitamos 200 para el SMA
                output = router.process_market_data(simulated_live_data)
                
                print(f"🕒 {output['timestamp']} | 💰 Precio: ${output['current_price']}")
                print(f"   🗺️ Régimen: {output['market_regime']} | 🤖 Bot Acitvo: {output['active_strategy']}")
                
                # Mostrar el Soporte/Resistencia más cercano (Calculado algorítmicamente)
                sup = output.get('nearest_support')
                res = output.get('nearest_resistance')
                if pd.notna(sup) and pd.notna(res):
                    print(f"   🧱 S/R Estructural -> Techo: ${round(res, 2)} | Suelo: ${round(sup, 2)}")
                
                if output['signals']:
                    print(f"   🚨 SEÑAL GENERADA: {output['signals'][0]['type']} en ${output['signals'][0]['price']}")
                print("-" * 60)
    else:
        print("Data file no encontrado.")
