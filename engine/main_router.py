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
from engine.risk.risk_manager import RiskManager                 # Motor de Riesgo Dinámico y Cuantitativo
from engine.core.confluence import confluence_manager            # Jurado Neural (Institutional Score)

# Configuración centralizada — lee ACCOUNT_BALANCE y MAX_RISK_PCT desde .env
from engine.api.config import settings

class SlingshotRouter:
    """
    El Cerebro Supremo de SLINGSHOT (Capa 2 -> Capa 3).
    Ingiere OHLCV, detecta el Regimen de Wyckoff, mapea Soportes/Resistencias,
    y rutea los datos SOLAMENTE a la estrategia matematicamente correcta.
    """

    @staticmethod
    def fmt_price(p) -> str:
        """Formato inteligente de precio adaptado a la magnitud del activo.
        BTC => $70,123.45  |  ETH => $2,071.33  |  PEPE => $0.000003521"""
        try:
            p = float(p)
            if p == 0:          return "$0.00"
            if p >= 1_000:      return f"${p:,.2f}"
            if p >= 1:          return f"${p:.4f}"
            if p >= 0.01:       return f"${p:.6f}"
            if p >= 0.0001:     return f"${p:.8f}"
            return f"${p:.10f}"
        except:
            return f"${p}"
    
    def __init__(self):
        self.regime_detector = RegimeDetector()
        
        # Instanciar el arsenal estratégico
        self.strat_smc = PaulPerdicesStrategy()
        self.strat_trend = TrendFollowingStrategy()
        self.strat_reversion = ReversionStrategy()
        
        # RiskManager lee balance y riesgo desde .env (ya no hardcodeado)
        self.risk_manager = RiskManager(
            account_balance=settings.ACCOUNT_BALANCE,
            base_risk_pct=settings.MAX_RISK_PCT
        )
        
        # Estado compartido para ConfluenceManager (se actualiza en cada llamada)
        self._last_ml_projection: dict = {}
        self._last_session_data:  dict = {}
        
    def set_context(self, ml_projection: dict = None, session_data: dict = None):
        """Actualiza el contexto externo (ML + Sesiones) para el evaluador de confluencias."""
        if ml_projection:
            self._last_ml_projection = ml_projection
        if session_data:
            self._last_session_data = session_data
        
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
                "bullish_divergence": bool(df['bullish_div'].iloc[-1]) if 'bullish_div' in df.columns else False,
                "bearish_divergence": bool(df['bearish_div'].iloc[-1]) if 'bearish_div' in df.columns else False,
                "macd_line": float(df['macd_line'].iloc[-1]) if 'macd_line' in df.columns and pd.notna(df['macd_line'].iloc[-1]) else None,
                "macd_signal": float(df['macd_signal'].iloc[-1]) if 'macd_signal' in df.columns and pd.notna(df['macd_signal'].iloc[-1]) else None,
                "macd_bullish_cross": bool(df['macd_bullish_cross'].iloc[-1]) if 'macd_bullish_cross' in df.columns else False,
                "bbwp": float(df['bbwp'].iloc[-1]) if 'bbwp' in df.columns and pd.notna(df['bbwp'].iloc[-1]) else None,
                "squeeze_active": bool(df['squeeze_active'].iloc[-1]) if 'squeeze_active' in df.columns else False,
                "volume": float(df['volume'].iloc[-1]) if 'volume' in df.columns and pd.notna(df['volume'].iloc[-1]) else 0.0
            },
            "active_strategy": None,
            "signals": [],
            "invalidated_signals": [], # Nueva lista para auditoría de clase mundial
        }

        # [AUDIT] Telemetría de Régimen
        print(f"[ROUTER-AUDIT] {asset} | Regimen: {current_regime} | Precio: {SlingshotRouter.fmt_price(result['current_price'])}")

        # 2a. Fusión OB + S/R: detectar confluencias ANTES de serializar key_levels
        try:
            atr_val = df.attrs.get('atr_value', float(df['close'].iloc[-1]) * 0.003)
            
            # 💎 SENSIBILIDAD ADAPTIVA: El oro requiere umbrales menores (1.6x cuerpo vs 2.0x en BTC)
            is_metal = asset.upper() in ["PAXGUSDT", "XAGUSDT", "XAUUSDT", "GOLD", "SILVER"]
            smc_threshold = 1.6 if is_metal else 2.0
            
            df_ob   = identify_order_blocks(df, threshold=smc_threshold)
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
            
        # 2d. Inyectar SMC Data para el Asesor y UI
        try:
            result["smc"] = smc # De la linea 118
        except NameError:
            result["smc"] = None
        
        # 3. ENRUTAMIENTO INTELIGENTE (El 'Switch' Maestro)
        is_precious_metal = asset.upper() in ["PAXGUSDT", "XAGUSDT", "XAUUSDT", "GOLD", "SILVER"]
        
        if is_precious_metal:
            # 🪙 RUTEO EXCLUSIVO: Metales Preciosos usan solo Paul Predice
            if current_regime in ['MARKUP', 'MARKDOWN']:
                result["active_strategy"] = "Paul Predice (Metales Preciosos)"
                analyzed_df = self.strat_trend.analyze(df)
                opportunities = self.strat_trend.find_opportunities(analyzed_df)
            else:
                result["active_strategy"] = "Standby (Esperando Tendencia para Paul Predice)"
                opportunities = []
                
        else:
            # 💎 RUTEO CRIPTO: Todo el arsenal disponible
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
                # En distribución ejecutamos AMBAS estrategias
                result["active_strategy"] = "Dual: SMC (Liquidity Sweeps) + ReversionStrategy (SHORT on Ceiling)"
                
                analyzed_smc = self.strat_smc.analyze(df)
                opps_smc = self.strat_smc.find_opportunities(analyzed_smc)
                
                analyzed_rev = self.strat_reversion.analyze(df)
                opps_rev = self.strat_reversion.find_opportunities(analyzed_rev)
                
                # Combinar y deduplicar (filtrar solo SHORTs de ReversionStrategy)
                opps_rev_short = [o for o in opps_rev if 'SHORT' in str(o.get('type', '')).upper()]
                opportunities = opps_smc + opps_rev_short
                
                try:
                    opportunities = sorted(opportunities, key=lambda x: x.get('timestamp', ''), reverse=True)
                except Exception:
                    pass
                
            elif current_regime == 'RANGING':
                # Rango medio sin extensión extrema — aguardamos ruptura
                result["active_strategy"] = "Standby (Awaiting Breakout)"
                opportunities = []
                
            elif current_regime == 'CHOPPY':
                # Alta volatilidad pero sin tendencia clara en las medias móviles
                result["active_strategy"] = "Standby (Market Transition / Choppiness)"
                opportunities = []
                
            else:
                # UNKNOWN (Probablemente la data sea insuficiente < 200 velas)
                result["active_strategy"] = "STANDBY (Calibrating moving averages...)"
                opportunities = []

        # [AUDIT] Telemetría de Oportunidades
        if opportunities:
            print(f"[ROUTER-AUDIT] 🎯 {asset} detectó {len(opportunities)} oportunidades brutas en el historial.")
        else:
            # Si no hay oportunidades, queremos saberlo
            if current_regime not in ['RANGING', 'CHOPPY']:
                print(f"[ROUTER-AUDIT] ⚪ {asset} sin oportunidades para la estrategia {result['active_strategy']}")

            
        # Extraer el backlog de señales históricas recientes para que la UI no se vacíe
        result['signals'] = [] # Reiniciar SIEMPRE la lista de señales exportadas por este tick
        if opportunities:
            
            # PRE-CACHE para mejorar Performance de "Path Traversal"
            try:
                # Asegurar timestamp puro para Vectorización
                df_time_vector = pd.to_datetime(df['timestamp'], utc=True)
                df_low_vector = df['low'].values
                df_high_vector = df['high'].values
                current_time_utc = df_time_vector.iloc[-1]
            except Exception:
                current_time_utc = None
            
            for sig in opportunities[-10:]:  # Mantener las últimas 10 señales históricas
                # ✅ FASE 4: CÁLCULO DE RIESGO GEOGRÁFICO Y CUANTITATIVO
                # Le pasamos al motor el mapa geográfico total: key_levels y df_ob (ya extraídos arriba)
                try:
                    smc_map = smc # Del bloque 2a extract_smc_coordinates
                except NameError:
                    smc_map = {'order_blocks': {'bullish': [], 'bearish': []}, 'fvgs': {'bullish': [], 'bearish': []}}

                risk_data = self.risk_manager.calculate_position(
                    current_price=sig['price'],
                    signal_type=sig.get('signal_type', 'LONG'),
                    market_regime=sig.get('regime', 'RANGING'),
                    key_levels=result.get("key_levels", []),
                    smc_data=smc_map,
                    atr_value=sig.get('atr_value', 0.0)
                )
                
                # Inyectar la matemática pura a la señal antes de despacharla al Frontend
                interval_minutes = {
                    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
                    "1h": 60, "2h": 120, "4h": 240, "8h": 480, "1d": 1440
                }.get(interval, 15)
                
                # Calcular timestamp de expiración (3 velas desde la señal)
                try:
                    sig_ts = pd.Timestamp(sig['timestamp'])
                    expiry_ts = sig_ts + pd.Timedelta(minutes=interval_minutes * risk_data.get("expiry_candles", 3))
                    expiry_timestamp_str = str(expiry_ts)
                except Exception:
                    expiry_timestamp_str = None

                sig.update({
                    "asset":              asset,
                    "risk_usd":           risk_data["risk_amount_usdt"],
                    "risk_pct":           risk_data["risk_pct"],
                    "leverage":           risk_data["leverage"],
                    "position_size":      risk_data["position_size_usdt"],
                    "stop_loss":          risk_data["stop_loss"],
                    "take_profit_3r":     risk_data["take_profit_3r"],
                    "entry_zone_top":     risk_data["entry_zone_top"],
                    "entry_zone_bottom":  risk_data["entry_zone_bottom"],
                    "expiry_candles":     risk_data.get("expiry_candles", 3),
                    "expiry_timestamp":   expiry_timestamp_str,
                    "interval_minutes":   interval_minutes,
                })
                
                # 🧠 CONFLUENCE SCORE — Evaluación institucional en tiempo real
                try:
                    confluence_result = confluence_manager.evaluate_signal(
                        df=df,
                        signal=sig,
                        ml_projection=self._last_ml_projection,
                        session_data=self._last_session_data,
                    )
                    sig["confluence"] = confluence_result
                except Exception as e:
                    print(f"[ROUTER] ConfluenceManager error: {e}")
                    sig["confluence"] = None
                
                # 🧠 REGLA DE CLASE MUNDIAL: Integridad Técnica vs Reloj
                # Una señal profesional no muere por tiempo, muere porque la tesis se invalida.
                is_alive = True
                death_reason = None
                
                if current_time_utc is not None:
                    try:
                        sig_time = pd.to_datetime(sig.get('timestamp'), utc=True)
                        is_long = 'LONG' in str(sig.get('type', '')).upper()
                        sl = float(sig.get('stop_loss', 0))
                        tp = float(sig.get('take_profit_3r', 0))
                        entry_top = float(sig.get('entry_zone_top', sig['price']))
                        entry_bottom = float(sig.get('entry_zone_bottom', sig['price']))
                        
                        # 1. VERIFICACIÓN DE LÍMITES (SL/TP)
                        if sl > 0 and tp > 0:
                            path_mask = df_time_vector >= sig_time
                            if path_mask.any():
                                path_lows = df_low_vector[path_mask]
                                path_highs = df_high_vector[path_mask]
                                
                                if is_long:
                                    if (path_lows <= sl).any():
                                        is_alive = False
                                        death_reason = "STOP LOSS HIT (Estructura Violada)"
                                    elif (path_highs >= tp).any():
                                        is_alive = False
                                        death_reason = "TAKE PROFIT HIT (Objetivo Cumplido)"
                                else: # SHORT
                                    if (path_highs >= sl).any():
                                        is_alive = False
                                        death_reason = "STOP LOSS HIT (Estructura Violada)"
                                    elif (path_lows <= tp).any():
                                        is_alive = False
                                        death_reason = "TAKE PROFIT HIT (Objetivo Cumplido)"

                        # 2. VERIFICACIÓN DE OPORTUNIDAD (Escape de Zona)
                        if is_alive:
                            current_price = result['current_price']
                            # Si el precio se aleja un 1% de la zona de entrada sin haber activado, 
                            # la oportunidad se "escapó" (Chase Prevention).
                            if is_long and current_price > entry_top * 1.01:
                                is_alive = False
                                death_reason = "MISSED (Precio escapó de la zona)"
                            elif not is_long and current_price < entry_bottom * 0.99:
                                is_alive = False
                                death_reason = "MISSED (Precio escapó de la zona)"
                                
                        # 3. VERIFICACIÓN DE RÉGIMEN (Inconsistencia de Tesis)
                        # Si la señal era LONG en MARKUP, pero el régimen cambia a CRASH/DISTRIBUTION,
                        # la tesis de "continuación" ya no es de clase mundial.
                        if is_alive:
                            if is_long and current_regime in ['DISTRIBUTION', 'MARKDOWN']:
                                is_alive = False
                                death_reason = "INVAL_REGIME (Contexto de mercado cambió)"
                            elif not is_long and current_regime in ['ACCUMULATION', 'MARKUP']:
                                is_alive = False
                                death_reason = "INVAL_REGIME (Contexto de mercado cambió)"

                    except Exception as e:
                        print(f"[ROUTER] World-Class Validation Error: {e}")

                if is_alive:
                    result['signals'].append(sig)
                else:
                    sig['death_reason'] = death_reason
                    result['invalidated_signals'].append(sig)
                    print(f"[ROUTER-AUDIT] Senal invalidada: {death_reason} | {asset} @ {SlingshotRouter.fmt_price(sig.get('price', 0))}")
                
            if result['signals']:
                last_sig = result['signals'][-1]
                print(f"[ROUTER] OK Backlog cargado | Ultima Senal: {last_sig['type']} @ {SlingshotRouter.fmt_price(last_sig['price'])} | Leverage: {last_sig.get('leverage')}x")
            else:
                if opportunities:
                    print(f"[ROUTER-AUDIT] ⚠️ {asset}: {len(opportunities)} señales encontradas pero TODAS están muertas/invalidadas.")
            
            # if not result['signals']:
            #     print(f"[ROUTER] ℹ️ {len(opportunities)} oportunidades históricas analizadas, cero válidas al final.")
                
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
