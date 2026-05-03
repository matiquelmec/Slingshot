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
        liq_clusters  = kwargs.get('liquidation_clusters', [])
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

        # 3. LIQUIDEZ Y SWEEPS (Peso 30)
        liq_weight = 30
        total_weight += liq_weight
        current_session = session_data.get('current_session', 'OFF_HOURS')
        
        # Detección de barrido (Sweep) usando la nueva lógica de memoria en smc.py
        has_sweep = bool(current.get('recent_sweep_bull' if is_long else 'recent_sweep_bear', False))
        
        liq_pts = (10 if current_session != 'OFF_HOURS' else 0) + (20 if has_sweep else 0)
        score += liq_pts
        
        status = "CONFIRMADO" if liq_pts >= 20 else "PARCIAL" if liq_pts > 0 else "BAJO"
        checklist.append({"factor": "Liquidez", "status": status, "detail": f"Sweep: {has_sweep} | Session: {current_session}"})

        # 4. VOLUMEN INSTITUCIONAL (RVOL) (Peso 15)
        vol_weight = 15
        total_weight += vol_weight
        rvol = float(current.get('volume', 0)) / vol_mean if vol_mean > 0 else 1.0
        if rvol >= 1.5:
            score += vol_weight
            checklist.append({"factor": "Huella RVOL", "status": "CONFIRMADO", "detail": f"Inyección {rvol:.1f}x"})
        else:
            checklist.append({"factor": "Huella RVOL", "status": "BAJO", "detail": f"Volumen {rvol:.1f}x"})

        # 5. ALGORITMO NEURAL (Peso 10)
        ml_weight = 10
        total_weight += ml_weight
        ml_prob = float(ml_projection.get('probability', 50))
        ml_ok = (is_long and ml_projection.get('direction') == 'ALCISTA' and ml_prob > 55) or \
                (not is_long and ml_projection.get('direction') == 'BAJISTA' and ml_prob > 55)
        if ml_ok:
            score += ml_weight
            checklist.append({"factor": "Predicción IA", "status": "CONFIRMADO", "detail": f"Prob: {ml_prob:.0f}%"})
        else:
            checklist.append({"factor": "Predicción IA", "status": "NEUTRAL", "detail": "IA Observando"})

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

        # 8. PUNTUACIÓN DE NOTICIAS
        if news_score >= 0.7: score += 5
        elif news_score <= 0.3: score -= 5

        # 9. SMT DIVERGENCE (Bono 25) v10.0 Sovereign (Consumo Centralizado)
        smt_weight = 25
        total_weight += smt_weight
        smt_status = "NEUTRAL"
        smt_detail = "Sin activo de comparación"
        
        # El SMT ahora viene pre-calculado en kwargs['smt_result']
        smt_result = kwargs.get('smt_result', {})
        if smt_result:
            div_type = smt_result.get('divergence', 'NONE')
            strength = smt_result.get('strength', 0)
            
            if (is_long and div_type == 'BULLISH_SMT') or (not is_long and div_type == 'BEARISH_SMT'):
                smt_pts = int(smt_weight * strength)
                score += smt_pts
                smt_status = "CONFIRMADO ✅"
                smt_detail = f"{smt_result['reason']} (Fuerza: {strength*100:.0f}%)"
            elif div_type != 'NONE':
                smt_status = "DIVERGENTE ⚠️"
                smt_detail = "Divergencia correlacionada opuesta"
            
        checklist.append({"factor": "SMT Divergence", "status": smt_status, "detail": smt_detail})

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

        # 🚀 10. ALINEACIÓN HTF (FRACTAL) — v10.0 Sovereign
        htf_bias = kwargs.get('htf_bias')
        multiplier = 1.0
        if htf_bias:
            # 10.1 Veto por Desalineación Estructural (1M/1W)
            # Ya vetamos en Gatekeeper, pero aquí penalizamos el Score si no hay armonía perfecta
            m1 = getattr(htf_bias, 'm1_regime', 'UNKNOWN')
            w1 = getattr(htf_bias, 'w1_regime', 'UNKNOWN')
            
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
                    checklist.append({"factor": "Zona de Valor", "status": "CONFIRMADO", "detail": f"{value_zone} (+{value_pts}pts)"})

            if gp_618 and gp_786:
                z_top = max(gp_618, gp_786)
                z_bottom = min(gp_618, gp_786)
                
                if z_bottom <= price <= z_top:
                    is_whale = fib_data.get("is_whale_leg", False)
                    gp_pts = 20 if is_whale else 10
                    score += gp_pts
                    whale_txt = " (WHALE LEG 🐋)" if is_whale else ""
                    checklist.append({
                        "factor": "Golden Pocket", 
                        "status": "CONFIRMADO", 
                        "detail": f"Inversión en OTE {gp_pts}pts{whale_txt}"
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

        # 🚀 9. SMT DIVERGENCE (Peso 15) — v4.0 Institutional
        smt_weight = 15
        smt_strength = 0
        if correlated_df is not None and not correlated_df.empty:
            total_weight += smt_weight
            try:
                # SMT: Divergencia entre activos correlacionados (BTC/ETH)
                # Buscamos si el asset correlacionado NO confirmó el Swing High/Low
                c_current = correlated_df.iloc[-1]
                c_prev = correlated_df.iloc[-2]
                
                curr_c = float(current.get('close', 0))
                prev_c = float(df['close'].iloc[-2])
                
                curr_corr_c = float(c_current.get('close', 0))
                prev_corr_c = float(c_prev.get('close', 0))
                
                # SMT BULLISH: BTC hace Lower Low, pero ETH hace Higher Low
                if is_long:
                    if curr_c < prev_c and curr_corr_c > prev_corr_c:
                        smt_strength = 1.0
                        score += smt_weight
                        checklist.append({"factor": "SMT Divergence", "status": "CONFIRMADO", "detail": "Acumulación SMT Detectada (+15pts)"})
                # SMT BEARISH: BTC hace Higher High, pero ETH hace Lower High
                else:
                    if curr_c > prev_c and curr_corr_c < prev_corr_c:
                        smt_strength = 1.0
                        score += smt_weight
                        checklist.append({"factor": "SMT Divergence", "status": "CONFIRMADO", "detail": "Distribución SMT Detectada (+15pts)"})
            except Exception as e:
                logger.error(f"[SMT] Error calculating divergence: {e}")

        # 🚀 10. ALINEACIÓN HTF (Peso 25 — EL ANCLA) v5.7.155 Master Gold
        onchain_weight = 15
        total_weight += onchain_weight
        onchain_bias = kwargs.get('onchain_bias', 'NEUTRAL')
        
        onchain_pts = 0
        onchain_status = "NEUTRAL"
        onchain_detail = "Datos On-Chain estables"

        if onchain_bias == "BULLISH_ACCUMULATION":
            if is_long:
                onchain_pts = onchain_weight
                onchain_status = "CONFIRMADO ✅"
                onchain_detail = "Acumulación ballena en rango (Aumento OI)"
            else:
                onchain_pts = -5
                onchain_status = "DIVERGENTE ⚠️"
                onchain_detail = "Posible trampa de liquidez en Short"
        elif onchain_bias == "BEARISH_WARNING":
            onchain_status = "ALERTA 🔴"
            onchain_detail = "Alta entrada de capital a Exchanges (> $10M)"
            if not is_long:
                onchain_pts = onchain_weight
            else:
                onchain_pts = -15
                multiplier *= 0.5 # Reducción drástica por flujo Bearish
        elif onchain_bias == "OVERLEVERAGED_LONGS":
            onchain_status = "PRECAUCIÓN ⚠️"
            onchain_detail = "Sobreapalancamiento detectado (Funding Alto)"
            if is_long: 
                multiplier *= 0.7 # Riesgo de Long Squeeze

        score += onchain_pts
        checklist.append({"factor": "On-Chain Sentinel", "status": onchain_status, "detail": onchain_detail})

        # RESULTADO FINAL
        base_score = int((score / total_weight) * 100) if total_weight > 0 else 0
        final_score = min(100, int(base_score * multiplier))
        
        conviction = "ALTA CONVICCIÓN" if final_score >= 70 else "SÓLIDA" if final_score >= 50 else "ESPECULATIVA"
        
        v_reason = None
        if multiplier == 0: 
            conviction = "VETADA"
            # Extraer el motivo del veto del checklist
            veto_entries = [c for c in checklist if c.get('status') == 'DENEGADO' or c.get('status') == 'OBSOLETO']
            v_reason = veto_entries[-1].get('detail', 'Veto por Confluencia') if veto_entries else 'Veto por Riesgo'
        
        logger.info(f"[CONFLUENCE] Asset: {signal.get('asset', 'UNKNOWN')} | Score: {final_score}% (Multiplier: {multiplier})")
        logger.info(f"             Regime OK? {regime_ok} | POI? {poi_pts} | Macro Near? {high_impact_near}")

        return {
            "score": final_score,
            "conviction": conviction,
            "is_long": is_long, # [DELTA v6.1] Propagación de polaridad
            "checklist": checklist,
            "reasoning": self._build_reasoning(final_score, conviction, is_long, regime, has_ob, rvol, high_impact_near, event_name, cluster_hit, v_reason),
            "rvol": round(rvol, 2),
            "smt_strength": smt_strength,
            "veto_reason": v_reason
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
