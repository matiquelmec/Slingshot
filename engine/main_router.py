import pandas as pd
from pathlib import Path
import json

# Motores e Indicadores
from engine.indicators.regime import RegimeDetector
from engine.indicators.structure import identify_support_resistance, get_key_levels, identify_order_blocks, extract_smc_coordinates
from engine.indicators.fibonacci import get_current_fibonacci_levels

# Estrategias — todas desde engine/strategies/ (lugar canónico)
from engine.strategies.smc      import PaulPerdicesStrategy     # SMC Francotirador (Distribución/Manipulación)
from engine.strategies.trend    import TrendFollowingStrategy    # Continuación (Markup/Markdown)
from engine.strategies.reversion import ReversionStrategy        # Reversión a la Media (Acumulación/Distribución)

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
        
    def process_market_data(
        self, 
        df: pd.DataFrame, 
        asset: str = "BTCUSDT", 
        interval: str = "15m",
        macro_levels: dict = None
    ) -> dict:
        """
        El pipeline principal. Por aquí pasará cada vela en vivo.
        """
        df = df.copy()
        from engine.indicators.structure import consolidate_mtf_levels
        
        # 1. Mapeo Topográfico Base con ventana dinámica por interval
        df = identify_support_resistance(df, interval=interval)
        
        # 2. Detección de Régimen de Wyckoff
        df = self.regime_detector.detect_regime(df)
        
        # 2.5 Inyección de Momentum Global (Suite Criptodamus: RSI, MACD, BBWP)
        # Esto expone las variables a la UI sin afectar cómo las estrategias las consumen internamente
        from engine.indicators.momentum import apply_criptodamus_suite
        try:
            df = apply_criptodamus_suite(df)
        except Exception as e:
            print(f"[ROUTER] Warning: Fallo al aplicar Suite Criptodamus global: {e}")
        
        current_regime = df['market_regime'].iloc[-1]
        
        # Diccionario de resultados
        result = {
            "asset": asset,
            "interval": interval,
            "timestamp": str(df['timestamp'].iloc[-1]),
            "current_price": float(df['close'].iloc[-1]),
            "market_regime": current_regime,
            "nearest_support": float(df['support_level'].iloc[-1]) if 'support_level' in df.columns and pd.notna(df['support_level'].iloc[-1]) else None,
            "nearest_resistance": float(df['resistance_level'].iloc[-1]) if 'resistance_level' in df.columns and pd.notna(df['resistance_level'].iloc[-1]) else None,
            # Indicadores internos del RegimeDetector (para el panel de diagnóstico)
            "sma_fast": float(df['sma_fast'].iloc[-1]) if 'sma_fast' in df.columns and pd.notna(df['sma_fast'].iloc[-1]) else None,
            "sma_slow": float(df['sma_slow'].iloc[-1]) if 'sma_slow' in df.columns and pd.notna(df['sma_slow'].iloc[-1]) else None,
            "sma_slow_slope": float(df['sma_slow_slope'].iloc[-1]) if 'sma_slow_slope' in df.columns and pd.notna(df['sma_slow_slope'].iloc[-1]) else None,
            "bb_width": float(df['bb_width'].iloc[-1]) if 'bb_width' in df.columns and pd.notna(df['bb_width'].iloc[-1]) else None,
            "bb_width_mean": float(df['bb_width_mean'].iloc[-1]) if 'bb_width_mean' in df.columns and pd.notna(df['bb_width_mean'].iloc[-1]) else None,
            "dist_to_sma200": float(df['dist_to_sma200'].iloc[-1]) if 'dist_to_sma200' in df.columns and pd.notna(df['dist_to_sma200'].iloc[-1]) else None,
            "diagnostic": {
                "rsi": float(df['rsi'].iloc[-1]) if 'rsi' in df.columns and pd.notna(df['rsi'].iloc[-1]) else None,
                "rsi_oversold": bool(df['rsi_oversold'].iloc[-1]) if 'rsi_oversold' in df.columns else False,
                "rsi_overbought": bool(df['rsi_overbought'].iloc[-1]) if 'rsi_overbought' in df.columns else False,
                "macd_line": float(df['macd_line'].iloc[-1]) if 'macd_line' in df.columns and pd.notna(df['macd_line'].iloc[-1]) else None,
                "macd_signal": float(df['macd_signal'].iloc[-1]) if 'macd_signal' in df.columns and pd.notna(df['macd_signal'].iloc[-1]) else None,
                "macd_bullish_cross": bool(df['macd_bullish_cross'].iloc[-1]) if 'macd_bullish_cross' in df.columns else False,
                "bbwp": float(df['bbwp'].iloc[-1]) if 'bbwp' in df.columns and pd.notna(df['bbwp'].iloc[-1]) else None,
                "squeeze_active": bool(df['squeeze_active'].iloc[-1]) if 'squeeze_active' in df.columns else False,
                "volume": float(df['volume'].iloc[-1]) if 'volume' in df.columns and pd.notna(df['volume'].iloc[-1]) else 0.0
            },
            "active_strategy": None,
            "signals": [],
        }

        # 2a. Fusión OB + S/R: detectar confluencias ANTES de serializar key_levels
        try:
            atr_val = df.attrs.get('atr_value', float(df['close'].iloc[-1]) * 0.003)
            df_ob   = identify_order_blocks(df)
            smc     = extract_smc_coordinates(df_ob)
            
            # Separar zonas alcistas y bajistas para confluencia pura
            bullish_zones = (
                [{'top': o['top'], 'bottom': o['bottom']} for o in smc['order_blocks']['bullish']] +
                [{'top': f['top'], 'bottom': f['bottom']} for f in smc['fvgs']['bullish']]
            )
            bearish_zones = (
                [{'top': o['top'], 'bottom': o['bottom']} for o in smc['order_blocks']['bearish']] +
                [{'top': f['top'], 'bottom': f['bottom']} for f in smc['fvgs']['bearish']]
            )

            def has_ob_near(price: float, zones: list) -> bool:
                for z in zones:
                    if z['bottom'] - atr_val <= price <= z['top'] + atr_val:
                        return True
                return False

            for lvl in df.attrs.get('key_resistances', []):
                # Una Resistencia tiene confluencia si se alinea con liquidez bajista (Bearish OB/FVG)
                lvl['ob_confluence'] = has_ob_near(lvl['price'], bearish_zones)
            for lvl in df.attrs.get('key_supports', []):
                # Un Soporte tiene confluencia si se alinea con liquidez alcista (Bullish OB/FVG)
                lvl['ob_confluence'] = has_ob_near(lvl['price'], bullish_zones)
        except Exception:
            pass  # Si la fusión falla, no se bloquea el pipeline

        # 2b. Consolidación MTF si hay datos macro
        base_key_levels = get_key_levels(df)
        if macro_levels:
            base_key_levels = consolidate_mtf_levels(base_key_levels, macro_levels)
            
        result["key_levels"] = base_key_levels

        # 2c. Fibonacci Dinámico (Fractal Swing Detection)
        try:
            result["fibonacci"] = get_current_fibonacci_levels(df)
        except Exception:
            result["fibonacci"] = None
        
        # 3. ENRUTAMIENTO INTELIGENTE (El 'Switch' Maestro)
        if current_regime == 'ACCUMULATION':
            # Buscamos LONGs: RSI sobrevendido en soporte + OBs alcistas
            result["active_strategy"] = "ReversionStrategy (Longs on Floor)"
            analyzed_df = self.strat_reversion.analyze(df)
            opportunities = self.strat_reversion.find_opportunities(analyzed_df)
            
        elif current_regime in ['MARKUP', 'MARKDOWN']:
            # Tendencia clara: seguimos el impulso con pullbacks a EMA + Fibonacci
            result["active_strategy"] = "TrendFollowingStrategy (Pullbacks + Fibo)"
            analyzed_df = self.strat_trend.analyze(df)
            opportunities = self.strat_trend.find_opportunities(analyzed_df)
            
        elif current_regime == 'DISTRIBUTION':
            # FIX: En distribución ejecutamos AMBAS estrategias:
            # → SMC detecta cacerías de liquidez en techos (SHORTs institucionales)
            # → ReversionStrategy detecta RSI sobrecomprado (SHORTs de reversión)
            # Ambas confirman la misma hipótesis bajista desde ángulos distintos.
            result["active_strategy"] = "Dual: SMC (Liquidity Sweeps) + ReversionStrategy (SHORT on Ceiling)"
            
            analyzed_smc = self.strat_smc.analyze(df)
            opps_smc = self.strat_smc.find_opportunities(analyzed_smc)
            
            analyzed_rev = self.strat_reversion.analyze(df)
            opps_rev = self.strat_reversion.find_opportunities(analyzed_rev)
            
            # Combinar y deduplicar (filtrar solo SHORTs de ReversionStrategy en DISTRIBUTION)
            opps_rev_short = [o for o in opps_rev if 'SHORT' in str(o.get('type', '')).upper()]
            opportunities = opps_smc + opps_rev_short
            # Ordenar por timestamp descendente
            try:
                opportunities = sorted(opportunities, key=lambda x: x.get('timestamp', ''), reverse=True)
            except Exception:
                pass

            print(f"[ROUTER] DISTRIBUTION: SMC={len(opps_smc)} opps, Reversion SHORT={len(opps_rev_short)} opps")
            
        elif current_regime == 'RANGING':
            # Rango medio sin extensión extrema — aguardamos ruptura
            result["active_strategy"] = "Standby (Awaiting Breakout)"
            opportunities = []
            
        else:
            # UNKNOWN (Falta historial para medias móviles o comportamiento anómalo)
            result["active_strategy"] = "STANDBY (Calibrating moving averages...)"
            opportunities = []

            
        # Extraer señales recientes (velas dentro del intervalo actual o el anterior)
        # BUG FIX: Comparar como Timestamps, no como strings (la conversión string nunca era igual)
        if opportunities:
            ts_result = pd.Timestamp(result['timestamp'])
            # Mapeamos el intervalo a segundos para la tolerancia de ventana
            _interval_seconds = {
                '1m': 60, '3m': 180, '5m': 300, '15m': 960,
                '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400
            }.get(interval, 960)
            for sig in opportunities[-5:]:  # Revisar las últimas 5 señales
                ts_signal = pd.Timestamp(sig['timestamp'])
                if abs((ts_signal - ts_result).total_seconds()) <= _interval_seconds:
                    result['signals'].append(sig)
                    print(f"[ROUTER] ✅ Señal válida: {sig['type']} @ ${sig['price']:.2f} (Δt={abs((ts_signal-ts_result).total_seconds()):.0f}s)")
            if not result['signals']:
                print(f"[ROUTER] ℹ️ {len(opportunities)} oportunidades históricas, ninguna en la vela actual ({ts_result}).")
                
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
