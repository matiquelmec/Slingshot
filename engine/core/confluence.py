"""
engine/core/confluence.py — El Jurado Neural de SLINGSHOT v10.0 APEX SOVEREIGN.
=============================================================================
Evalúa cada señal contra el arsenal institucional v10.0:
- Veto Fractal (1M/1W Alignment)
- OTE (Optimal Trade Entry) 61.8% - 78.6%
- Estructura de Mercado & POIs (Santa Trinidad SMC)
- Huella de Volumen & Absorción
- Proyección Contextual (Nexus Bridge Enabled)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from engine.api.config import settings
from typing import Dict, Any, Optional
from engine.core.logger import logger

class ConfluenceManager:
    """
    Analiza señales bajo la óptica SMC integrada con Macro y Liquidez Profunda.
    """

    def evaluate_signal(
        self,
        df: pd.DataFrame,
        signal: Dict[str, Any],
        ml_projection: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        correlated_df: Optional[pd.DataFrame] = None, # Activado v4.0: Para SMT Divergence
        **kwargs: Any
    ) -> Dict[str, Any]:
        ml_projection = ml_projection or {}
        session_data  = session_data  or {}
        econ_events   = kwargs.get('economic_events', [])
        liq_clusters  = kwargs.get('liquidation_clusters', kwargs.get('liquidations', []))
        news_items    = kwargs.get('news_items', [])

        try:
            sig_ts = pd.to_datetime(signal.get('timestamp'))
            current_df = df[df['timestamp'] == sig_ts]
            if not current_df.empty:
                current = current_df.iloc[0]
                idx_pos = df.index.get_loc(current_df.index[0])
                vol_mean = df['volume'].iloc[max(0, idx_pos-20):max(1, idx_pos)].mean()
            else:
                current = df.iloc[-1]
                vol_mean = df['volume'].iloc[-21:-1].mean()
        except:
            current = df.iloc[-1]
            vol_mean = df['volume'].iloc[-21:-1].mean()

        # [FIX v6.6.7] Source of Truth Hierarchy
        # 1. signal_type (explícito)
        # 2. type (inferido por string)
        sig_type_raw = str(signal.get('signal_type', signal.get('type', ''))).upper()
        is_long = 'LONG' in sig_type_raw
        
        checklist = []
        score = 0
        total_weight = 0
        smt_strength = 0 # Inicialización para evitar NameError [FIX v11.1]
        cluster_hit = False # Inicialización para evitar NameError [FIX v13.6]

        # 1. NARRATIVA ESTRUCTURAL (Peso 15)
        narrative_weight = 15
        total_weight += narrative_weight
        regime = str(current.get('market_regime', signal.get('regime', 'UNKNOWN'))).upper()
        # En Sigma, permitimos operar en RANGING si la estructura interna es fuerte
        regime_ok = (is_long and regime in ('ACCUMULATION', 'MARKUP', 'RANGING')) or \
                   (not is_long and regime in ('DISTRIBUTION', 'MARKDOWN', 'RANGING'))
        if regime_ok:
            score += narrative_weight
            checklist.append({"factor": "Narrativa SMC", "status": "CONFIRMADO", "detail": f"Alineado con {regime}"})
        else:
            checklist.append({"factor": "Narrativa SMC", "status": "DIVERGENTE", "detail": f"Régimen {regime}"})

        # 2. PUNTOS DE INTERÉS OB/FVG (Peso 40 - EL REY)
        poi_weight = 40
        total_weight += poi_weight
        
        smc_map = kwargs.get('smc_map', {})
        price = float(signal.get('price', current.get('close', 0)))
        
        active_obs = smc_map.get("order_blocks", {}).get("bullish" if is_long else "bearish", [])
        active_fvgs = smc_map.get("fvgs", {}).get("bullish" if is_long else "bearish", [])
        
        mitigating_ob = any(ob['bottom'] <= price <= ob['top'] for ob in active_obs)
        mitigating_fvg = any(fvg['bottom'] <= price <= fvg['top'] for fvg in active_fvgs)
        
        # [SIGMA v9.0] Si es creación fresca (lo que dispara el Sniper), damos 20 pts por cada uno.
        # Esto permite que el disparo inicial sea tan válido como el re-test.
        has_ob_creation = bool(current.get('ob_bullish' if is_long else 'ob_bearish', False))
        has_fvg_creation = bool(current.get('fvg_bullish' if is_long else 'fvg_bearish', False))
        
        has_ob = mitigating_ob or has_ob_creation # FIX BUG-002: required for reasoning builder
        
        poi_pts = 0
        if has_ob: poi_pts += 20
        if mitigating_fvg or has_fvg_creation: poi_pts += 20
        
        score += poi_pts
        if poi_pts >= 40:
            checklist.append({"factor": "Zonas POI", "status": "CONFIRMADO", "detail": "Confluencia OB + FVG (Institucional)"})
        elif poi_pts >= 20:
            checklist.append({"factor": "Zonas POI", "status": "PARCIAL", "detail": "OB o FVG Detectado"})
        else:
            checklist.append({"factor": "Zonas POI", "status": "NEUTRAL", "detail": "Sin POI claro"})

        # 2.1 YOSH LIQUIDITY TRAPS (Bono de Trampas Institucionales Yosh)
        traps = smc_map.get("traps", {}) if isinstance(smc_map, dict) else {}
        has_laf = traps.get("laf_bull" if is_long else "laf_bear", False)
        has_lbf = traps.get("lbf_bull" if is_long else "lbf_bear", False)
        
        if has_laf:
            score += 15
            checklist.append({"factor": "Yosh Order Flow", "status": "ELITE", "detail": "Trampa de Absorción LAF Detectada (+15pts)"})
        elif has_lbf:
            score += 10
            checklist.append({"factor": "Yosh Order Flow", "status": "CONFIRMADO", "detail": "Trampa de Impulso LBF Detectada (+10pts)"})
        else:
            checklist.append({"factor": "Yosh Order Flow", "status": "NEUTRAL", "detail": "Sin trampas extremas de Yosh"})

        # 3. LIQUIDEZ Y SWEEPS (Peso 30)
        # 3. LIQUIDEZ Y SWEEPS (Peso 30 total si hay sesiones)
        current_session = session_data.get('current_session') if session_data else None
        liq_weight = 30 if current_session else 20
        total_weight += liq_weight
        
        # Detección de barrido (Sweep) usando la nueva lógica de memoria en smc.py
        has_sweep = bool(current.get('recent_sweep_bull' if is_long else 'recent_sweep_bear', False))
        
        if current_session:
            liq_pts = (10 if current_session != 'OFF_HOURS' else 0) + (20 if has_sweep else 0)
            detail_str = f"Sweep: {has_sweep} | Session: {current_session}"
        else:
            liq_pts = (20 if has_sweep else 0)
            detail_str = f"Sweep: {has_sweep}"
            
        score += liq_pts
        status = "CONFIRMADO" if liq_pts >= 20 else "PARCIAL" if liq_pts > 0 else "BAJO"
        checklist.append({"factor": "Liquidez", "status": status, "detail": detail_str})

        # 4. VOLUMEN INSTITUCIONAL (RVOL) (Peso 15)
        vol_weight = 15
        total_weight += vol_weight
        rvol = float(current.get('volume', 0)) / vol_mean if vol_mean > 0 else 1.0
        if rvol >= settings.INSTITUTIONAL_VOL_THRESHOLD:
            score += vol_weight
            checklist.append({"factor": "Huella RVOL", "status": "CONFIRMADO", "detail": f"Inyección {rvol:.1f}x"})
        else:
            checklist.append({"factor": "Huella RVOL", "status": "BAJO", "detail": f"Volumen {rvol:.1f}x"})

        # 5. ALGORITMO NEURAL (Peso 10)
        ml_weight = 10
        ml_prob = ml_projection.get('probability') if ml_projection else None
        if ml_prob is not None:
            total_weight += ml_weight
            ml_prob_val = float(ml_prob)
            ml_ok = (is_long and ml_projection.get('direction') == 'ALCISTA' and ml_prob_val > 55) or \
                    (not is_long and ml_projection.get('direction') == 'BAJISTA' and ml_prob_val > 55)
            if ml_ok:
                score += ml_weight
                checklist.append({"factor": "Predicción IA", "status": "CONFIRMADO", "detail": f"Prob: {ml_prob_val:.0f}%"})
            else:
                checklist.append({"factor": "Predicción IA", "status": "NEUTRAL", "detail": "IA Observando"})
        else:
            checklist.append({"factor": "Predicción IA", "status": "CALIBRANDO", "detail": "Datos insuficientes (Bypass)"})

        # [REFACTOR v12.0] APEX OVERRIDE (Bono de Convicción Extrema)
        # Si el motor de absorción detecta actividad institucional masiva, el score recibe un boost.
        absorption_score = float(current.get('absorption_score', 0))
        if absorption_score >= 90:
            score += 20
            checklist.append({"factor": "Apex Override", "status": "ELITE", "detail": f"Absorción {absorption_score}% (Institucional)"})
        elif absorption_score >= 80:
            score += 10
            checklist.append({"factor": "Apex Boost", "status": "ACTIVO", "detail": f"Absorción {absorption_score}%"})
        
        # [REFACTOR v12.0] Multiplicador de Contexto por Noticias
        # Si hay eventos económicos de alto impacto, el volumen es más importante
        high_impact_news = any(e.get('impact') == 'HIGH' for e in econ_events)
        if high_impact_news and rvol >= 1.5:
            score += 10 # Bono por volumen en noticia
            checklist.append({"factor": "Contexto Macro", "status": "VOLÁTIL", "detail": "Volumen validado por Noticia de Alto Impacto"})

        # 6. CALENDARIO ECONÓMICO Y NARRATIVA RECIENTE (Peso 20) v5.7.155 Master Gold
        econ_weight = 20
        total_weight += econ_weight
        high_impact_near = False
        recent_impact_active = False
        event_name = ""
        now = pd.Timestamp.now(tz=timezone.utc)

        # Enforce list of dicts if input is DataFrame/Series
        if hasattr(econ_events, "to_dict"):
            if hasattr(econ_events, "columns"): econ_events = econ_events.to_dict('records')
            else: econ_events = [econ_events.to_dict()]
        
        for ev in econ_events:
            try:
                ev_date = ev.get('date', ev.get('timestamp'))
                if not ev_date: continue

                # Sutura Definitiva (v6.0 - Force Scalar)
                if isinstance(ev_date, (np.ndarray, pd.Series, pd.Index)):
                    ev_date = ev_date.iloc[0] if hasattr(ev_date, 'iloc') else ev_date[0]

                # Convert to UTC-aware datetime to prevent subtraction exceptions (v6.0 Fix)
                # Simulation-aware 'now' for backtesting/live consistency
                now_sim = pd.to_datetime(df['timestamp'].iloc[-1], utc=True)
                
                # Conversión robusta de fecha (v6.6.5 Fix)
                try:
                    ev_time_pd = pd.to_datetime(float(ev_date), unit='s', utc=True)
                except (ValueError, TypeError):
                    ev_time_pd = pd.to_datetime(ev_date, utc=True)
                
                # Convert to single scalar timestamp
                if hasattr(ev_time_pd, "__iter__") and not isinstance(ev_time_pd, (str, bytes)):
                    ev_time_pd = ev_time_pd[0]
                
                # Llegar a "Python Land" sin advertencias de nanosegundos
                ev_time = ev_time_pd.to_pydatetime() if hasattr(ev_time_pd, "to_pydatetime") else ev_time_pd
                now_py = now_sim.floor('us').to_pydatetime() if hasattr(now_sim, "to_pydatetime") else now_sim

                diff_hours = (ev_time - now_py).total_seconds() / 3600
                
                if ev.get('impact') == 'High' or ev.get('impact') == 'HIGH':
                    # RIESGO FUTURO (Inmediato)
                    if 0 < diff_hours < 1.5:
                        high_impact_near = True
                        event_name = ev.get('title', 'Evento Macro')
                    # IMPACTO RECIENTE (Inercia de mercado - 12 horas)
                    elif -12 < diff_hours <= 0:
                        recent_impact_active = True
                        event_name = ev.get('title', 'Evento Macro Reciente')
            except Exception as ev_err:
                logger.warning(f"[CONFLUENCE] Error evaluando Evento Macro: {ev_err}")
                continue

        # 6.1 Cálculo de News Sentiment PONDERADO (v6.5 Master Smart-Flow)
        news_score = 0.5
        if news_items:
            # Enforce list of dicts if input is DataFrame/Series
            if hasattr(news_items, "to_dict"):
                if hasattr(news_items, "columns"): news_items = news_items.to_dict('records')
                else: news_items = [news_items.to_dict()]

            sent_map = {"BULLISH": 1.0, "NEUTRAL": 0.5, "BEARISH": 0.0}
            total_weighted_score = 0
            total_weight_sum = 0
            now_ts = pd.Timestamp.now(tz=timezone.utc)
            
            for item in news_items:
                try:
                    # A. Ponderación de Importancia (Tier 1 = x3, Tier 2 = x1.5)
                    weight = float(item.get('weight', 1.0))
                    
                    # B. Time Decay (Sigma): TTL 5 min, luego decae linealmente durante 10 min
                    # Sutura Definitiva (v6.0 - Force Scalar)
                    ts_raw = item.get('timestamp')
                    if not ts_raw: continue

                    # Protección contra vectorización espontánea de Pandas/NumPy
                    if isinstance(ts_raw, (np.ndarray, pd.Series, pd.Index)):
                        ts_raw = ts_raw.iloc[0] if hasattr(ts_raw, 'iloc') else ts_raw[0]
                    
                    # Convertimos a Timestamp de Python puro para evitar conflictos con Numpy
                    # Garantizar conversión de Unix Timestamp (v6.6.5 Fix)
                    try:
                        item_ts_pd = pd.to_datetime(float(ts_raw), unit='s', utc=True)
                    except (ValueError, TypeError):
                        item_ts_pd = pd.to_datetime(ts_raw, utc=True)
                    
                    if hasattr(item_ts_pd, "__iter__") and not isinstance(item_ts_pd, (str, bytes)):
                        item_ts_pd = item_ts_pd[0] # iloc[0] equivalent
                    
                    # Garantizar "Python Land" sin advertencias de nanosegundos
                    item_ts = item_ts_pd.to_pydatetime() if hasattr(item_ts_pd, "to_pydatetime") else item_ts_pd
                    now_sim = pd.to_datetime(df['timestamp'].iloc[-1], utc=True)
                    now_py = now_sim.floor('us').to_pydatetime() if hasattr(now_sim, "to_pydatetime") else now_sim

                    age_mins = (now_py - item_ts).total_seconds() / 60
                    
                    decay = 1.0
                    if age_mins > 5:
                        decay = max(0, 1.0 - (age_mins - 5) / 10)
                    
                    effective_weight = weight * decay
                    sent_val = sent_map.get(item.get('sentiment', 'NEUTRAL'), 0.5)
                    
                    total_weighted_score += (sent_val * effective_weight)
                    total_weight_sum += effective_weight
                except Exception as news_err:
                    logger.warning(f"[CONFLUENCE] Error calculando Time-Decay (Noticia): {news_err}")
                    continue
                
            if total_weight_sum > 0:
                news_score = total_weighted_score / total_weight_sum

        # [FIX BUG-001] APLICAR LEYES DE NARRATIVA
        if high_impact_near:
            checklist.append({"factor": "Macro", "status": "ALERTA", "detail": "Noticia de alto impacto inminente"})
            score -= 20
        elif recent_impact_active:
            if (is_long and news_score < 0.4) or (not is_long and news_score > 0.6):
                score -= 15
                checklist.append({"factor": "Macro", "status": "DIVERGENTE", "detail": "Noticia en contra de la dirección"})
            else:
                score += econ_weight
                checklist.append({"factor": "Macro", "status": "CONFIRMADO", "detail": "Contexto macro a favor"})
        else:
            # Caso base: Sin anomalías
            score += econ_weight
            checklist.append({"factor": "Macro", "status": "NEUTRAL", "detail": "Sin eventos macro activos"})

        # 7. CLUSTERS DE LIQUIDACIÓN (Peso 10) v4.0 (Enhanced Volume Filtering)
        liq_cluster_weight = 10
        if liq_clusters:
            total_weight += liq_cluster_weight
            price = float(current.get('close', 0))
            cluster_hit = False
            hit_strength = 0
            
            for cluster in liq_clusters:
                # Si el precio está cerca de un cluster masivo de liquidación en la dirección del trade
                c_price = float(cluster.get('price', 0))
                c_strength = int(cluster.get('strength', 0))
                dist = abs(price - c_price) / price
                
                # FILTRO CRÍTICO v2.0: Distancia < 1% Y Fuerza > 50%
                if dist < 0.01 and c_strength > 50:
                    if (is_long and c_price > price) or (not is_long and c_price < price):
                        cluster_hit = True
                        hit_strength = c_strength
                        break
            
            if cluster_hit:
                score += liq_cluster_weight
                checklist.append({"factor": "Liq Clusters", "status": "CONFIRMADO", "detail": f"Imán de liquidez masiva detectado ({hit_strength}%)"})
            else:
                checklist.append({"factor": "Liq Clusters", "status": "NEUTRAL", "detail": "Sin clusters institucionales cercanos"})
        else:
            checklist.append({"factor": "Liq Clusters", "status": "CALIBRANDO", "detail": "Datos de liquidaciones no disponibles (Bypass)"})

        # 8. PUNTUACIÓN DE NOTICIAS
        if news_score >= 0.7: score += 5
        elif news_score <= 0.3: score -= 5

        # 🚀 9.5. NEURAL HEATMAP (Peso 20) v5.7 Platinum
        heatmap_weight = 20
        total_weight += heatmap_weight
        heatmap = kwargs.get('heatmap', {})
        
        if heatmap and heatmap.get('imbalance') is not None:
            imbalance = heatmap.get('imbalance', 0)
            h_bids = heatmap.get('hot_bids', [])
            h_asks = heatmap.get('hot_asks', [])
            
            h_score = 0
            h_detail = "Neutral"
            
            # A. Alineación de Desequilibrio
            if (is_long and imbalance > 0.1) or (not is_long and imbalance < -0.1):
                h_score += 10
                h_detail = "Desequilibrio a favor"
            elif (is_long and imbalance < -0.1) or (not is_long and imbalance > 0.1):
                h_score -= 10
                h_detail = "Advertencia: Contra-flujo"
            
            # B. Alineación con Muros (Proximidad < 0.5%)
            proximity_bonus = False
            for hb in (h_bids if is_long else h_asks):
                if abs(price - hb['price']) / price < 0.005:
                    proximity_bonus = True
                    break
            
            if proximity_bonus:
                h_score += 10
                h_detail += " + Muro cercano"
            
            score += max(-15, min(20, h_score)) # Clamp
            checklist.append({"factor": "Neural Heatmap", "status": "CONFIRMADO" if h_score > 0 else "PELIGRO" if h_score < 0 else "NEUTRAL", "detail": h_detail})
        else:
            checklist.append({"factor": "Neural Heatmap", "status": "CALIBRANDO", "detail": "Datos insuficientes"})

        # 🚀 9.6. SMT DIVERGENCE (Peso 15) v11.1 Restoration
        if correlated_df is not None and len(correlated_df) >= 2:
            try:
                total_weight += 15
                c1_asset, c2_asset = df['close'].iloc[-1], df['close'].iloc[-2]
                c1_corr, c2_corr = correlated_df['close'].iloc[-1], correlated_df['close'].iloc[-2]
                
                # SMT Divergence: Un activo hace un Higher High y el otro un Lower High
                asset_trending_up = c1_asset > c2_asset
                corr_trending_up = c1_corr > c2_corr
                
                if asset_trending_up != corr_trending_up:
                    smt_strength = 0.85
                    score += 15
                    checklist.append({"factor": "SMT Divergence", "status": "CONFIRMADO", "detail": "Divergencia institucional (Smart Money Tool)"})
                else:
                    checklist.append({"factor": "SMT Divergence", "status": "NEUTRAL", "detail": "Correlación en sintonía"})
            except Exception as e:
                logger.warning(f"[CONFLUENCE] Error en SMT: {e}")

        # 🚀 9.7. ORDER FLOW DELTA & TRIGGER CANDLE (Peso 15) v10.0 Sovereign Apex
        delta_weight = 15
        total_weight += delta_weight
        order_flow_delta = float(current.get('order_flow_delta', 0.0))
        
        delta_aligned = (is_long and order_flow_delta > 0.1) or (not is_long and order_flow_delta < -0.1)
        delta_opposed = (is_long and order_flow_delta < -0.5) or (not is_long and order_flow_delta > 0.5)
        
        if delta_aligned:
            score += delta_weight
            checklist.append({"factor": "Order Flow Delta", "status": "CONFIRMADO", "detail": f"Flujo taker a favor (Delta: {order_flow_delta:+.2f})"})
        elif delta_opposed:
            score -= 10
            checklist.append({"factor": "Order Flow Delta", "status": "DIVERGENTE", "detail": f"Presión taker en contra (Delta: {order_flow_delta:+.2f})"})
        else:
            checklist.append({"factor": "Order Flow Delta", "status": "NEUTRAL", "detail": f"Delta equilibrado ({order_flow_delta:+.2f})"})

        # 🚀 9.8. CUMULATIVE VOLUME DELTA (CVD) & L2 IMPALANCE (Peso 15) v37.0 Apex Quantum
        cvd_weight = 15
        total_weight += cvd_weight
        try:
            from engine.indicators.volume import calculate_cvd_divergence
            cvd_res = calculate_cvd_divergence(df)
            cvd_status = cvd_res.get("status", "IN_SYNC")
            
            cvd_aligned = (is_long and cvd_status == "BULLISH_DIVERGENCE") or (not is_long and cvd_status == "BEARISH_DIVERGENCE")
            cvd_divergent = (is_long and cvd_status == "BEARISH_DIVERGENCE") or (not is_long and cvd_status == "BULLISH_DIVERGENCE")
            
            if cvd_aligned:
                score += cvd_weight
                # Bonus de Sinergia Cuántica: Si Delta y CVD están ambos alineados a favor (+5pts)
                if delta_aligned:
                    score += 5
                    checklist.append({"factor": "CVD Divergence", "status": "CONFIRMADO", "detail": f"Ultra-Confluencia: Absorción CVD ({cvd_status}) + Flujo Taker alineado (+20pts)"})
                else:
                    checklist.append({"factor": "CVD Divergence", "status": "CONFIRMADO", "detail": f"Absorción acumulada detectada ({cvd_status}) (+15pts)"})
            elif cvd_divergent:
                score -= 15
                checklist.append({"factor": "CVD Divergence", "status": "DIVERGENTE", "detail": f"Distribución acumulada en contra ({cvd_status}) (-15pts)"})
            else:
                checklist.append({"factor": "CVD Divergence", "status": "NEUTRAL", "detail": "CVD acumulado en sintonía"})
        except Exception as cvd_err:
            checklist.append({"factor": "CVD Divergence", "status": "NEUTRAL", "detail": "CVD en calibración"})

        # 🚀 10. ALINEACIÓN HTF (FRACTAL) — v10.0 Sovereign
        htf_bias = kwargs.get('htf_bias')
        multiplier = 1.0
        if htf_bias:
            # 10.1 Veto por Desalineación Estructural (1M/1W)
            # Ya vetamos en Gatekeeper, pero aquí penalizamos el Score si no hay armonía perfecta
            m1 = getattr(htf_bias, 'm1_regime', 'UNKNOWN')
            w1 = getattr(htf_bias, 'w1_regime', 'UNKNOWN')
            
            if m1 == 'UNKNOWN' or w1 == 'UNKNOWN':
                checklist.append({"factor": "Macro Fractal", "status": "NEUTRAL", "detail": "1M/1W no disponibles en este entorno"})
            else:
                is_macro_aligned = (is_long and m1 == "MARKUP" and w1 == "MARKUP") or \
                                   (not is_long and m1 == "MARKDOWN" and w1 == "MARKDOWN")
                
                if not is_macro_aligned:
                    score -= 20
                    checklist.append({"factor": "Macro Fractal", "status": "DIVERGENTE", "detail": f"1M/1W no alineados (-20pts)"})
                else:
                    score += 10
                    checklist.append({"factor": "Macro Fractal", "status": "CONFIRMADO", "detail": "Armonía 1M + 1W detectada (+10pts)"})

            htf_score = htf_bias.strength * 100
            is_contrary = (is_long and htf_bias.direction == 'BEARISH') or (not is_long and htf_bias.direction == 'BULLISH')
            
            if htf_score < 15 or is_contrary:
                penalty = 15
                score -= penalty
                checklist.append({"factor": "HTF Momentum", "status": "DIVERGENTE", "detail": f"Momentum opuesto (-{penalty}pts)"})
            else:
                score += 5
                checklist.append({"factor": "HTF Momentum", "status": "APROBADO", "detail": f"Fuerza: {htf_score:.0f}%"})

        # 🚀 11. VETO DE VALOR (PREMIUM / DISCOUNT) — v10.0 Sovereign (Consumo Centralizado)
        # El Fibonacci ahora viene inyectado en kwargs['fib_data'] para evitar re-cálculo
        fib_data = kwargs.get('fib_data')
        price = float(current.get('close', 0))
        fib_05 = gp_618 = gp_786 = None
        
        if fib_data and 'levels' in fib_data:
            fib_05 = fib_data['levels'].get('0.5')
            gp_618 = fib_data['levels'].get('0.618')
            gp_786 = fib_data['levels'].get('0.786')
            
            if fib_05:
                invalid_value = (is_long and price > fib_05) or (not is_long and price < fib_05)
                value_zone = "PREMIUM (CARO) 🔴" if is_long else "DISCOUNT (BARATO) 🔴"
                
                if invalid_value:
                    score -= 10
                    checklist.append({"factor": "Zona de Valor", "status": "PRECAUCIÓN", "detail": f"Operando en {value_zone} (-10pts)"})
                else:
                    value_pts = 10
                    score += value_pts
                    value_zone = "DISCOUNT ✅" if is_long else "PREMIUM ✅"
                    checklist.append({"factor": "Zona de Valor", "status": "CONFIRMADO", "detail": f"Operando en {value_zone} (+10pts)"})

        # 🚀 12. METODOLOGÍA YOSH (ORDER FLOW) — v13.1
        # Inyectamos el Perfil de Volumen y Detección de Trampas
        smc_map = kwargs.get('smc_map', {})
        vp = smc_map.get("volume_profile") if smc_map else None
        traps = smc_map.get("traps", {}) if smc_map else {}
        
        if vp and vp.get("vah") and vp.get("val"):
            vah, val, poc = vp["vah"], vp["val"], vp["poc"]
            price = float(current.get("close", 0))
            
            # A. Valor Aceptado
            in_value = val <= price <= vah
            if in_value:
                score += 10
                checklist.append({"factor": "Yosh: Value Area", "status": "CONFIRMADO", "detail": "Precio en zona de valor aceptado (+10pts)"})
            
            # B. Rechazo en Extremos (VAL para Long, VAH para Short)
            proximity_vah = abs(price - vah) / price < 0.002
            proximity_val = abs(price - val) / price < 0.002
            
            if (is_long and proximity_val) or (not is_long and proximity_vah):
                score += 15
                checklist.append({"factor": "Yosh: Extremo VA", "status": "ELITE", "detail": "Rechazo en extremo de área de valor (+15pts)"})

            # D. Defensa en LVN (Low Volume Node)
            lvns = vp.get("lvns", [])
            absorption = vp.get("absorption_score", 0)
            
            near_lvn = any(abs(price - lvn) / price < 0.0015 for lvn in lvns)
            if near_lvn:
                lvn_pts = 10
                if absorption > 60: # Alta absorción en LVN = Defensa Institucional
                    lvn_pts += 15
                    detail = f"Defensa Institucional en LVN con Alta Absorción ({absorption}) (+25pts)"
                    status = "INSTITUCIONAL"
                else:
                    detail = "Precio reaccionando en Nodo de Bajo Volumen (+10pts)"
                    status = "ALINEADO"
                
                score += lvn_pts
                checklist.append({"factor": "Yosh: Defensa LVN", "status": status, "detail": detail})

        # C. Bono por Trampa (Look Above and Fail)
        laf_active = traps.get("laf_bull" if is_long else "laf_bear", False)
        if laf_active:
            lvl_hit = traps.get("level_hit", "Key Level")
            score += 25
            checklist.append({"factor": "Yosh: Trampa LAF", "status": "INSTITUCIONAL", "detail": f"Trampa detectada en {lvl_hit} (+25pts)"})

        # D. Yosh Golden Window (10:00 - 11:30 AM EST)
        in_yosh_window = bool(session_data and session_data.get("yosh_window"))
        if in_yosh_window:
            score += 15
            checklist.append({"factor": "Yosh: Golden Window", "status": "ALINEADO", "detail": "Operando en ventana institucional de alta probabilidad (+15pts)"})

        # E. Golden Pocket — SIEMPRE se evalúa (independiente de ventana horaria)
        if gp_618 and gp_786:
            z_top = max(gp_618, gp_786)
            z_bottom = min(gp_618, gp_786)
            
            if z_bottom <= price <= z_top:
                is_whale = fib_data.get("is_whale_leg", False)
                # Scoring compuesto: GP + Whale + Yosh = máximo puntaje
                gp_pts = 25 if (is_whale and in_yosh_window) else 20 if is_whale else 15 if in_yosh_window else 10
                score += gp_pts
                whale_txt = " (WHALE LEG 🐋)" if is_whale else ""
                yosh_txt = " + YOSH WINDOW" if in_yosh_window else ""
                checklist.append({
                    "factor": "Golden Pocket", 
                    "status": "CONFIRMADO", 
                    "detail": f"Inversión en OTE {gp_pts}pts{whale_txt}{yosh_txt}"
                })


        # 🚀 11.5. GHOST SENTINEL MACRO BIAS (v8.6.0 Institutional)
        context_obj = kwargs.get('context')
        ghost = context_obj.ghost_data.get("data", {}) if context_obj and hasattr(context_obj, 'ghost_data') else {}
        if ghost:
            macro_bias = ghost.get("macro_bias", "NEUTRAL")
            risk_appetite = ghost.get("risk_appetite", "NEUTRAL")
            
            macro_bullish = macro_bias in ("BULLISH", "BLOCK_SHORTS")
            macro_bearish = macro_bias in ("BEARISH", "BLOCK_LONGS")
            
            ghost_pts = 0
            ghost_weight = 20 # Peso específico para el Radar de Confluencia
            total_weight += ghost_weight
            
            if is_long and macro_bullish: ghost_pts = ghost_weight
            elif not is_long and macro_bearish: ghost_pts = ghost_weight
            elif is_long and macro_bearish: ghost_pts = 0 # No sumamos si hay divergencia
            elif not is_long and macro_bullish: ghost_pts = 0
            else: ghost_pts = ghost_weight // 2 # Neutralidad suma la mitad
            
            score += ghost_pts
            checklist.append({
                "factor": "Ghost Sentinel", 
                "status": "CONFIRMADO" if ghost_pts == ghost_weight else "NEUTRAL" if ghost_pts > 0 else "DIVERGENTE", 
                "detail": f"Macro: {macro_bias} ({ghost_pts}/{ghost_weight} pts)"
            })
            
            # Bonus de Apetito de Riesgo
            if (is_long and risk_appetite == "RISK_ON") or (not is_long and risk_appetite == "RISK_OFF"):
                score += 5
                total_weight += 5
                checklist.append({"factor": "Risk Appetite", "status": "FAVORABLE", "detail": f"{risk_appetite} (+5 pts)"})

        # 🚀 11.6. GOLDEN RULES QUANT (v11.2 APEX GOLDEN RULES)
        # Rule 1: Bono por Activos Majores de Liquidez Profunda (BTC, ETH, SOL)
        asset_name = str(signal.get('asset', signal.get('symbol', ''))).upper()
        if any(m in asset_name for m in ["BTC", "ETH", "SOL"]):
            majors_pts = 10
            score += majors_pts
            total_weight += majors_pts
            checklist.append({"factor": "Tier-1 VIP Asset", "status": "CONFIRMADO", "detail": f"Activo Líder de Alta Liquidez ({asset_name}) (+10pts)"})

        # Rule 2: Alineación con Tendencia de Alto Timeframe (HTF 4H Trend Alignment)
        try:
            price_curr = float(current.get('close', 0))
            if 'ema800' not in df.columns and len(df) >= 200:
                df['ema800'] = df['close'].ewm(span=min(800, len(df)), adjust=False).mean()
            
            ema800_val = float(df['ema800'].iloc[-1]) if 'ema800' in df.columns else None
            if ema800_val and ema800_val > 0:
                is_htf_aligned = (is_long and price_curr > ema800_val) or (not is_long and price_curr < ema800_val)
                htf_weight = 15
                total_weight += htf_weight
                if is_htf_aligned:
                    score += htf_weight
                    checklist.append({"factor": "Tendencia 4H HTF", "status": "CONFIRMADO", "detail": "Alineado con la Tendencia Institucional 4H (+15pts)"})
                else:
                    score -= 10
                    checklist.append({"factor": "Tendencia 4H HTF", "status": "DIVERGENTE", "detail": "Operando contra la Tendencia Institucional 4H (-10pts)"})
        except Exception as htf_err:
            logger.debug(f"[CONFLUENCE] Bypass HTF 4H check: {htf_err}")

        # Rule 3: Filtro Temporal de Días de Alta Probabilidad (Exclusión Lunes Pre-NY)
        try:
            now_dt = pd.to_datetime(current.get('timestamp', pd.Timestamp.now(tz=timezone.utc)), utc=True)
            day_wk = now_dt.strftime('%A')
            hr_utc = now_dt.hour
            
            day_weight = 5
            total_weight += day_weight
            if day_wk in ["Tuesday", "Wednesday", "Thursday", "Friday"]:
                score += day_weight
                checklist.append({"factor": "Día Institucional", "status": "CONFIRMADO", "detail": f"{day_wk}: Día de Alta Expansión de Tendencia (+5pts)"})
            elif day_wk == "Monday" and hr_utc < 13:
                score -= 5
                checklist.append({"factor": "Día Institucional", "status": "PRECAUCIÓN", "detail": "Lunes Pre-NY Open: Riesgo de Manipulación / Rango Inicial (-5pts)"})
            else:
                checklist.append({"factor": "Día Institucional", "status": "NEUTRAL", "detail": f"Sesión en {day_wk}"})

            # 🚀 Killzone Timing Gating para Índices TradFi (v25.0 FTMO Titanium)
            # Índices (US100, US30, US500, GER40): Exclusivamente en London Open (07:00-10:00 UTC) o NY Open (13:30-16:30 UTC)
            is_tradfi_index = any(idx in asset_name for idx in ["US100", "US30", "US500", "GER40", "NQ", "YM", "ES"])
            if is_tradfi_index:
                in_london_kz = (7 <= hr_utc < 10)
                in_ny_kz = (13 <= hr_utc < 17)
                if not (in_london_kz or in_ny_kz):
                    multiplier *= 0.0
                    checklist.append({
                        "factor": "Killzone Timing TradFi",
                        "status": "DENEGADO",
                        "detail": f"Veto Horario FTMO: {asset_name} fuera de Killzone de Londres/NY ({hr_utc:02d}:00 UTC). Sin liquidez institucional."
                    })
                else:
                    score += 5
                    checklist.append({
                        "factor": "Killzone Timing TradFi",
                        "status": "CONFIRMADO",
                        "detail": f"Operando en Ventana Institucional {'Londres' if in_london_kz else 'Nueva York'} (+5pts)"
                    })
        except Exception as day_err:
            logger.debug(f"[CONFLUENCE] Bypass Day/Killzone Check: {day_err}")

        # 🚀 11.7. KAUFMAN EFFICIENCY RATIO (KER) & DYNAMIC NOISE QUARANTINE (v11.3 Apex)
        ker_value = 0.50
        is_quarantined = False
        health_status = "OPTIMAL"
        try:
            if len(df) >= 20:
                period_ker = 20
                change_ker = abs(float(df['close'].iloc[-1]) - float(df['close'].iloc[-period_ker]))
                volatility_ker = float(df['close'].diff().abs().tail(period_ker).sum())
                if volatility_ker > 0:
                    ker_value = float(change_ker / volatility_ker)

            if ker_value >= 0.40:
                health_status = "OPTIMAL"
                checklist.append({"factor": "Salud de Activo (KER)", "status": "CONFIRMADO", "detail": f"Estructura Limpia (KER: {ker_value:.2f})"})
            elif ker_value >= 0.22:
                health_status = "MODERATE_NOISE"
                checklist.append({"factor": "Salud de Activo (KER)", "status": "NEUTRAL", "detail": f"Volatilidad Normal (KER: {ker_value:.2f})"})
            else:
                health_status = "QUARANTINED"
                is_quarantined = True
                if score < 65:
                    multiplier *= 0.5
                checklist.append({"factor": "Salud de Activo (KER)", "status": "PRECAUCIÓN", "detail": f"Cuarentena por Mechas (KER: {ker_value:.2f}). Se exige Confluencia ≥ 65%"})
        except Exception as ker_err:
            logger.debug(f"[CONFLUENCE] Bypass KER check: {ker_err}")

        # 🚀 11.8. BTC MACRO ALIGNMENT VETO & ASYMMETRIC ALTCOIN LONG BIAS (v24.0 APEX ALPHA)
        btc_aligned = kwargs.get('btc_aligned', None)
        asset_name = str(signal.get('asset', signal.get('symbol', ''))).upper()
        is_altcoin = asset_name and not any(m in asset_name for m in ["BTC", "ETH", "SOL", "PAXG", "XAU"])
        
        if btc_aligned is False and asset_name and "BTC" not in asset_name:
            multiplier = 0
            checklist.append({
                "factor": "Alineación Macro BTC",
                "status": "DENEGADO",
                "detail": "Veto V12 Sovereign: Altcoin operando contra tendencia macro de BTC"
            })
        elif btc_aligned is True and asset_name and "BTC" not in asset_name:
            score += 10
            checklist.append({
                "factor": "Alineación Macro BTC",
                "status": "CONFIRMADO",
                "detail": "Alineación Macro con Bitcoin validada (+10pts)"
            })

        # Asimetría Cuantitativa: Shorts en Altcoins solo permitidos si Confluencia >= 70
        if is_altcoin and not is_long:
            if score < 70:
                multiplier *= 0.0
                checklist.append({
                    "factor": "Asimetría Direccional Altcoin (Short Gating)",
                    "status": "DENEGADO",
                    "detail": "Veto Alpha v24.0: Shorts en Altcoins exigen Confluencia Institucional >= 70%"
                })
            else:
                checklist.append({
                    "factor": "Asimetría Direccional Altcoin (Short Gating)",
                    "status": "CONFIRMADO",
                    "detail": "Short en Altcoin con Alta Convicción (Score >= 70%)"
                })

        # 🚀 11.9. GOLD ATH LONG-ONLY VETO (v13.7 Sovereign Gold Titanium)
        # El oro en régimen alcista secular rompiendo máximos prohíbe ventas institucionales
        if ("XAU" in asset_name or "PAXG" in asset_name or "GOLD" in asset_name) and not is_long:
            multiplier = 0.0
            logger.info(f"[CONFLUENCE] 🔴 Veto Macro Oro: Prohibido operar Shorts en Oro durante régimen ATH")
            checklist.append({
                "factor": "Veto Oro en Máximos Históricos",
                "status": "DENEGADO",
                "detail": "Veto Cuantitativo: Prohibido vender Oro (XAUUSD) en tendencia macro alcista histórica (Solo Longs)"
            })

        # 🚀 12. VETO DE VOLATILIDAD MACRO (EVENTOS ECONÓMICOS) v5.7.155 Master Gold Titanium
        if high_impact_near:
            # Si el evento es en menos de 30 min (0.5 horas), Veto Total
            is_imminent = False
            for ev in econ_events:
                ev_date = ev.get('date', ev.get('timestamp'))
                if not ev_date: continue
                ev_time = pd.to_datetime(ev_date, utc=True)
                diff_m = (ev_time - now).total_seconds() / 60
                if 0 < diff_m <= 30 and (ev.get('impact') == 'High' or ev.get('impact') == 'HIGH'):
                    is_imminent = True
                    event_name = ev.get('title', 'Evento Crítico')
                    break

            if is_imminent:
                multiplier = 0.0
                logger.info(f"[CONFLUENCE] 🔴 Veto Macro: Evento {event_name} inminente")
                checklist.append({"factor": "Veto Macro News", "status": "DENEGADO", "detail": f"Imminente: {event_name}"})

        # 🚀 13. RELOJ DE OBSOLESCENCIA (TIME-DECAY) v6.6.6 Master Fix
        try:
            def _to_dt(ts):
                if ts is None: return pd.Timestamp.now(tz=timezone.utc).floor('us').tz_localize(None)
                try:
                    # Si es convertible a número, es un Unix Timestamp
                    f_ts = float(ts)
                    unit = 's' if f_ts < 2e9 else 'ms'
                    return pd.to_datetime(f_ts, unit=unit, utc=True).floor('us').tz_localize(None)
                except (ValueError, TypeError):
                    # Si falla, es un string de fecha (ISO, etc.)
                    return pd.to_datetime(str(ts), utc=True).floor('us').tz_localize(None)

            # Sincronización de Relojes con el DF actual
            now_ts = _to_dt(df['timestamp'].iloc[-1])
            sig_ts = _to_dt(signal.get('timestamp'))
            
            # Dinamismo de intervalo para Time-Decay
            interval_str = kwargs.get('interval', '15m')
            interval_map = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400}
            interval_seconds = interval_map.get(interval_str, 900) # SAFE_FALLBACK a 900s (15m)
            
            diff_seconds = abs((now_ts - sig_ts).total_seconds())
            candles_elapsed = diff_seconds / interval_seconds
            
            decay_mult = 1.0
            if candles_elapsed > 10: decay_mult = 0.8
            if candles_elapsed > 30: 
                decay_mult = 0.0 # Veto total por obsolescencia
                v_reason = f"Expirado ({int(candles_elapsed)} velas)"
                
            multiplier *= decay_mult
            
            if decay_mult < 1.0:
                status = "OBSOLETO" if decay_mult == 0.0 else "DECAYENDO"
                checklist.append({"factor": "Time-Decay", "status": status, "detail": f"{int(candles_elapsed)} velas desde origen"})
            else:
                checklist.append({"factor": "Timing", "status": "FRESCO", "detail": "Señal en tiempo real"})
        except Exception as e:
            logger.error(f"[CONFLUENCE] Error crítico en Time-Decay: {e}")
            # Fallback seguro: No vetar por error de sistema
            if 'multiplier' not in locals(): multiplier = 1.0

        # 🚀 10. ALINEACIÓN HTF (Peso 25 — EL ANCLA) v5.7.155 Master Gold
        onchain_weight = 15
        onchain_bias = kwargs.get('onchain_bias')
        
        if onchain_bias and onchain_bias != 'NEUTRAL':
            total_weight += onchain_weight
            onchain_pts = 0
            onchain_status = "NEUTRAL"
            onchain_detail = "Datos On-Chain estables"

            if onchain_bias == "BULLISH_ACCUMULATION":
                if is_long:
                    onchain_pts = onchain_weight
                    onchain_status = "CONFIRMADO"
                    onchain_detail = "Acumulación ballena en rango (Aumento OI)"
                else:
                    onchain_pts = -5
                    onchain_status = "DIVERGENTE"
                    onchain_detail = "Posible trampa de liquidez en Short"
            elif onchain_bias == "BEARISH_WARNING":
                onchain_status = "ALERTA"
                onchain_detail = "Alta entrada de capital a Exchanges (> $10M)"
                if not is_long:
                    onchain_pts = onchain_weight
                else:
                    onchain_pts = -15
                    multiplier *= 0.5 # Reducción drástica por flujo Bearish
            elif onchain_bias == "OVERLEVERAGED_LONGS":
                onchain_status = "PRECAUCIÓN"
                onchain_detail = "Sobreapalancamiento detectado (Funding Alto)"
                if is_long: 
                    multiplier *= 0.7 # Riesgo de Long Squeeze

            score += onchain_pts
            checklist.append({"factor": "On-Chain Sentinel", "status": onchain_status, "detail": onchain_detail})
        else:
            checklist.append({"factor": "On-Chain Sentinel", "status": "CALIBRANDO", "detail": "Datos On-Chain no disponibles (Bypass)"})

        # RESULTADO FINAL CON SANITIZACIÓN ESTRICTA (v25.1 ELITE)
        import math
        base_score = int((score / total_weight) * 100) if total_weight > 0 else 0
        final_score = min(100, max(0, int(base_score * multiplier)))
        
        conviction = "ALTA CONVICCIÓN" if final_score >= 70 else "SÓLIDA" if final_score >= 50 else "ESPECULATIVA"
        
        v_reason = None
        if multiplier == 0 or final_score == 0: 
            conviction = "VETADA"
            # Extraer el motivo del veto del checklist
            veto_entries = [c for c in checklist if c.get('status') in ('DENEGADO', 'OBSOLETO', 'DIVERGENTE')]
            v_reason = veto_entries[-1].get('detail', 'Veto por Confluencia') if veto_entries else 'Veto por Riesgo'
        
        safe_rvol = round(rvol, 2) if isinstance(rvol, (int, float)) and math.isfinite(rvol) else 1.0
        safe_ker = round(ker_value, 2) if isinstance(ker_value, (int, float)) and math.isfinite(ker_value) else 0.35
        safe_smt = round(smt_strength, 2) if isinstance(smt_strength, (int, float)) and math.isfinite(smt_strength) else 0.0

        logger.info(f"[CONFLUENCE] Asset: {signal.get('asset', 'UNKNOWN')} | Score: {final_score}% (Multiplier: {multiplier})")
        logger.info(f"             Regime OK? {regime_ok} | POI? {poi_pts} | Macro Near? {high_impact_near}")

        return {
            "score": final_score,
            "conviction": conviction,
            "is_long": is_long, # [DELTA v6.1] Propagación de polaridad
            "checklist": checklist,
            "reasoning": self._build_reasoning(final_score, conviction, is_long, regime, has_ob, safe_rvol, high_impact_near, event_name, cluster_hit, v_reason),
            "rvol": safe_rvol,
            "smt_strength": safe_smt,
            "veto_reason": v_reason,
            "asset_health": {
                "ker": safe_ker,
                "status": health_status,
                "is_quarantined": is_quarantined
            }
        }

    def _build_reasoning(self, score: int, conviction: str, is_long: bool, regime: str, ob: bool, rvol: float, high_impact: bool, event: str, cluster: bool, veto: str = None) -> str:
        if conviction == "VETADA" and veto:
            return f"⚠️ SEÑAL VETADA: {veto}. Sin confluencia institucional suficiente."

        msg = f"Señal {'LONG' if is_long else 'SHORT'} ({score}/100). "
        msg += f"Estructura {regime}. "
        if ob: msg += "POI Institucional validado. "
        if rvol >= 1.5: msg += f"Huella de capital activa ({rvol:.1f}x). "
        if cluster: msg += "Atraído por cluster de liquidación masiva. "
        if high_impact: msg += f"⚠️ PRECAUCIÓN: {event} en menos de 2h."
        return msg.strip()

confluence_manager = ConfluenceManager()
