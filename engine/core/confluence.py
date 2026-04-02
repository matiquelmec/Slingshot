"""
engine/core/confluence.py — El Jurado Neural de SLINGSHOT v4.0 (FULL POTENTIAL).
=============================================================================
Evalúa cada señal contra el arsenal puramente institucional completo:
- Estructura de Mercado & POIs
- Liquidez & KillZones
- Huella de Volumen (RVOL)
- Proyección IA (Machine Learning)
- Sentimiento Contextual (News AI)
- Eventos Económicos (Calendario de Impacto)
- Zonas de Liquidación (Clusters de Liquidez)
"""

import pandas as pd
from datetime import datetime, timezone

class ConfluenceManager:
    """
    Analiza señales bajo la óptica SMC integrada con Macro y Liquidez Profunda.
    """

    def evaluate_signal(
        self,
        df: pd.DataFrame,
        signal: dict,
        ml_projection: dict = None,
        session_data: dict = None,
        correlated_df: pd.DataFrame = None, # Activado v4.0: Para SMT Divergence
        **kwargs
    ) -> dict:
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

        sig_type = signal.get('type', '').upper()
        is_long = 'LONG' in sig_type
        checklist = []
        score = 0
        total_weight = 0

        # 1. NARRATIVA ESTRUCTURAL (Peso 20)
        narrative_weight = 20
        total_weight += narrative_weight
        regime = str(current.get('market_regime', signal.get('regime', 'UNKNOWN'))).upper()
        regime_ok = (is_long and regime in ('ACCUMULATION', 'MARKUP', 'RANGING')) or \
                   (not is_long and regime in ('DISTRIBUTION', 'MARKDOWN', 'RANGING'))
        if regime_ok:
            score += narrative_weight
            checklist.append({"factor": "Narrativa SMC", "status": "CONFIRMADO", "detail": f"Alineado con {regime}"})
        else:
            checklist.append({"factor": "Narrativa SMC", "status": "DIVERGENTE", "detail": f"Régimen {regime}"})

        # 2. PUNTOS DE INTERÉS OB/FVG (Peso 20)
        poi_weight = 20
        total_weight += poi_weight
        has_ob = bool(current.get('ob_bullish' if is_long else 'ob_bearish', False))
        has_fvg = bool(current.get('fvg_bullish' if is_long else 'fvg_bearish', False))
        poi_pts = (10 if has_ob else 0) + (10 if has_fvg else 0)
        score += poi_pts
        if poi_pts > 0:
            checklist.append({"factor": "Zonas POI", "status": "CONFIRMADO", "detail": f"{'OB' if has_ob else ''} {'FVG' if has_fvg else ''} detectado"})
        else:
            checklist.append({"factor": "Zonas POI", "status": "NEUTRAL", "detail": "Sin POI inmediato"})

        # 3. LIQUIDEZ Y KILLZONES (Peso 15)
        liq_weight = 15
        total_weight += liq_weight
        current_session = session_data.get('current_session', 'OFF_HOURS')
        in_kz = current_session in ('LONDON', 'NEW_YORK', 'LONDON_NY_OVERLAP', 'ASIA')
        sweep = any((is_long and s.get('swept_low')) or (not is_long and s.get('swept_high')) 
                    for s in session_data.get('sessions', {}).values())
        liq_pts = (7 if in_kz else 0) + (8 if sweep else 0)
        score += liq_pts
        checklist.append({"factor": "Liquidez/KZ", "status": "CONFIRMADO" if liq_pts >= 10 else "PARCIAL" if liq_pts > 0 else "BAJO",
                           "detail": f"{current_session} {'+ Sweep' if sweep else ''}"})

        # 4. HUELLA DE VOLUMEN (RVOL) (Peso 10)
        vol_weight = 10
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

        # 6. CALENDARIO ECONÓMICO Y NARRATIVA RECIENTE (Peso 20) v4.1 Platinum
        econ_weight = 20
        total_weight += econ_weight
        high_impact_near = False
        recent_impact_active = False
        event_name = ""
        now = datetime.now(timezone.utc)
        
        for ev in econ_events:
            ev_date = ev.get('date', ev.get('timestamp'))
            if not ev_date: continue
            # Convert to UTC-aware datetime to prevent subtraction exceptions
            ev_time = pd.to_datetime(ev_date, utc=True)
            diff_hours = (ev_time - now).total_seconds() / 3600
            
            if ev.get('impact') == 'High' or ev.get('impact') == 'HIGH':
                # RIESGO FUTURO (Inmediato)
                if 0 < diff_hours < 1.5:
                    high_impact_near = True
                    event_name = ev.get('title', 'Evento Macro')
                # IMPACTO RECIENTE (Inercia de mercado - 12 horas)
                elif -12 < diff_hours <= 0:
                    recent_impact_active = True
                    event_name = ev.get('title', 'Evento Macro Reciente')

        # 6.1 Cálculo de News Sentiment (Reparado v4.1)
        news_score = 0.5
        if news_items:
            sent_map = {"BULLISH": 1.0, "NEUTRAL": 0.5, "BEARISH": 0.0}
            scores = [sent_map.get(item.get('sentiment', 'NEUTRAL'), 0.5) for item in news_items]
            news_score = sum(scores) / len(scores)

        # APLICAR LEYES DE NARRATIVA
        if high_impact_near:
            checklist.append({"factor": "Contexto Macro", "status": "DENEGADO", "detail": f"Riesgo: {event_name} inminente"})
            score -= 20 # Penalización masiva
        elif recent_impact_active:
            if (is_long and news_score < 0.4) or (not is_long and news_score > 0.6):
                score -= 15
                checklist.append({"factor": "Sesgo Macro", "status": "DIVERGENTE", "detail": f"Contradice Impacto de {event_name}"})
            else:
                score += econ_weight
                checklist.append({"factor": "Sesgo Macro", "status": "CONFIRMADO", "detail": f"Alineado con {event_name}"})
        else:
            score += econ_weight
            checklist.append({"factor": "Sesgo Macro", "status": "CONFIRMADO", "detail": "Sin anomalías macro"})

        # 7. CLUSTERS DE LIQUIDACIÓN (Peso 10) v4.0
        liq_cluster_weight = 10
        total_weight += liq_cluster_weight
        price = float(current.get('close', 0))
        cluster_hit = False
        for cluster in liq_clusters:
            # Si el precio está cerca de un cluster masivo de liquidación en la dirección del trade
            c_price = float(cluster.get('price', 0))
            dist = abs(price - c_price) / price
            # Si el cluster está en la dirección del trade (imán de liquidez)
            if dist < 0.01: # Dentro del 1%
                if (is_long and c_price > price) or (not is_long and c_price < price):
                    cluster_hit = True
                    break
        
        if cluster_hit:
            score += liq_cluster_weight
            checklist.append({"factor": "Liq Clusters", "status": "CONFIRMADO", "detail": "Imán de liquidez detectado"})
        else:
            checklist.append({"factor": "Liq Clusters", "status": "NEUTRAL", "detail": "Sin clusters cercanos"})

        # 8. PUNTUACIÓN DE NOTICIAS
        if news_score >= 0.7: score += 5
        elif news_score <= 0.3: score -= 5

        # 9. SMT DIVERGENCE (Bono 10) v4.0 (Gema Activada)
        smt_weight = 10
        total_weight += smt_weight
        smt_status = "NEUTRAL"
        smt_detail = "Sin activo de comparación"
        
        if correlated_df is not None:
            from engine.indicators.smt import detect_smt_divergence
            smt_result = detect_smt_divergence(df, correlated_df)
            div_type = smt_result.get('divergence', 'NONE')
            
            if (is_long and div_type == 'BULLISH_SMT') or (not is_long and div_type == 'BEARISH_SMT'):
                score += smt_weight
                smt_status = "CONFIRMADO ✅"
                smt_detail = smt_result['reason']
            elif div_type != 'NONE':
                # Divergencia opuesta (Pelotón de advertencia)
                smt_status = "DIVERGENTE ⚠️"
                smt_detail = "El activo correlacionado no acompaña el movimiento"
            else:
                smt_status = "NEUTRAL"
                smt_detail = "Estructura correlacionada en armonía"
                
        checklist.append({"factor": "SMT Divergence", "status": smt_status, "detail": smt_detail})

        # RESULTADO FINAL
        final_score = min(100, int((score / total_weight) * 100)) if total_weight > 0 else 0
        conviction = "ALTA CONVICCIÓN" if final_score >= 70 else "SÓLIDA" if final_score >= 50 else "ESPECULATIVA"
        
        print(f"[CONFLUENCE] Asset: {signal.get('pair') or 'BTC'} | Score: {final_score}% (Score: {score} / Total: {total_weight})")
        print(f"             Regime OK? {regime_ok} | POI? {poi_pts} | Macro Near? {high_impact_near}")

        return {
            "score": final_score,
            "conviction": conviction,
            "checklist": checklist,
            "reasoning": self._build_reasoning(final_score, conviction, is_long, regime, has_ob, rvol, high_impact_near, event_name, cluster_hit),
            "rvol": round(rvol, 2)
        }

    def _build_reasoning(self, score, conviction, is_long, regime, ob, rvol, high_impact, event, cluster):
        msg = f"Señal {'LONG' if is_long else 'SHORT'} ({score}/100). "
        msg += f"Estructura {regime}. "
        if ob: msg += "POI Institucional validado. "
        if rvol >= 1.5: msg += f"Huella de capital activa ({rvol:.1f}x). "
        if cluster: msg += "Atraído por cluster de liquidación masiva. "
        if high_impact: msg += f"⚠️ PRECAUCIÓN: {event} en menos de 2h."
        return msg.strip()

confluence_manager = ConfluenceManager()
