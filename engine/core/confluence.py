"""
engine/core/confluence.py — El Jurado Neural de SLINGSHOT.
=============================================================
Evalúa cada señal contra el arsenal completo de indicadores
calculados por el router y retorna un 'Institutional Score'
ponderado (0-100) junto con un checklist de confluencias.

Se integra en main_router.py justo tras el cálculo de riesgo.
"""

import pandas as pd


class ConfluenceManager:
    """
    Analiza señales LONG/SHORT en tiempo real ponderando:
    - Régimen de Wyckoff     (25%)
    - Estructura SMC OB/FVG  (20%)
    - Volumen Relativo RVOL  (15%)
    - Momentum RSI/MACD/BB   (15%)
    - Sesión/KillZone/Sweeps (15%)
    - Proyección IA (ML)     (10%)
    """

    def evaluate_signal(
        self,
        df: pd.DataFrame,
        signal: dict,
        ml_projection: dict = None,
        session_data: dict = None
    ) -> dict:
        """
        :param df:            DataFrame con OHLCV + indicadores ya calculados por el router.
        :param signal:        Señal del router (type, price, trigger, regime...).
        :param ml_projection: Output del modelo XGBoost (direction, probability).
        :param session_data:  Output del SessionManager (current_session, sessions con sweeps).
        :returns: dict con score (0-100), checklist y reasoning.
        """
        ml_projection = ml_projection or {}
        session_data  = session_data  or {}

        current   = df.iloc[-1]
        sig_type  = signal.get('type', '').upper()
        is_long   = 'LONG' in sig_type

        checklist    = []
        score        = 0
        total_weight = 0

        # ─────────────────────────────────────────────────────────────
        # 1. RÉGIMEN WYCKOFF  (peso 25)
        # ─────────────────────────────────────────────────────────────
        regime_weight = 25
        total_weight += regime_weight
        regime = str(current.get('market_regime', signal.get('regime', 'UNKNOWN'))).upper()

        if is_long:
            regime_ok = regime in ('ACCUMULATION', 'MARKUP', 'RANGING')
        else:
            regime_ok = regime in ('DISTRIBUTION', 'MARKDOWN', 'RANGING')

        if regime_ok:
            score += regime_weight
            checklist.append({"factor": "Régimen Wyckoff", "status": "CONFIRMADO",
                               "detail": f"Alineado con {regime}"})
        else:
            checklist.append({"factor": "Régimen Wyckoff", "status": "DIVERGENTE",
                               "detail": f"Régimen {regime} no ideal para esta dirección"})

        # ─────────────────────────────────────────────────────────────
        # 2. ESTRUCTURA SMC — Order Blocks + FVG  (peso 20)
        # ─────────────────────────────────────────────────────────────
        struct_weight = 20
        total_weight += struct_weight

        ob_col  = 'ob_bullish'  if is_long else 'ob_bearish'
        fvg_col = 'fvg_bullish' if is_long else 'fvg_bearish'
        has_ob  = bool(current.get(ob_col,  False))
        has_fvg = bool(current.get(fvg_col, False))

        # También contemplar si el trigger del router menciona OB/FVG directamente
        trigger = signal.get('trigger', '')
        if 'OB' in trigger.upper() or 'ORDER BLOCK' in trigger.upper():
            has_ob = True
        if 'FVG' in trigger.upper():
            has_fvg = True

        struct_pts = (10 if has_ob else 0) + (10 if has_fvg else 0)
        score += struct_pts

        if struct_pts > 0:
            tags = ' + '.join(filter(None, ['OB' if has_ob else '', 'FVG' if has_fvg else '']))
            checklist.append({"factor": "Estructura SMC", "status": "CONFIRMADO",
                               "detail": f"{tags} institucional detectado"})
        else:
            checklist.append({"factor": "Estructura SMC", "status": "NEUTRAL",
                               "detail": "Sin zonas institucionales inmediatas"})

        # ─────────────────────────────────────────────────────────────
        # 3. VOLUMEN RELATIVO — RVOL  (peso 15)
        # ─────────────────────────────────────────────────────────────
        vol_weight = 15
        total_weight += vol_weight

        # Calcular RVOL dinámicamente: vol actual / vol medio (20 velas)
        try:
            vol_series = df['volume']
            vol_mean   = vol_series.iloc[-21:-1].mean()
            rvol       = float(current.get('volume', 0)) / vol_mean if vol_mean > 0 else 1.0
        except Exception:
            rvol = 1.0

        if rvol >= 1.5:
            score += vol_weight
            checklist.append({"factor": "Volumen RVOL", "status": "CONFIRMADO",
                               "detail": f"Capital institucional ({rvol:.2f}x promedio)"})
        elif rvol >= 1.0:
            score += int(vol_weight * 0.5)
            checklist.append({"factor": "Volumen RVOL", "status": "PARCIAL",
                               "detail": f"Volumen elevado ({rvol:.2f}x)"})
        else:
            checklist.append({"factor": "Volumen RVOL", "status": "BAJO",
                               "detail": f"Volumen anémico ({rvol:.2f}x)"})

        # ─────────────────────────────────────────────────────────────
        # 4. MOMENTUM — RSI / MACD / BB Squeeze  (peso 15)
        # ─────────────────────────────────────────────────────────────
        mom_weight = 15
        total_weight += mom_weight

        rsi_ok = bool(current.get('rsi_oversold' if is_long else 'rsi_overbought', False))
        macd_ok = bool(current.get('macd_bullish_cross' if is_long else 'macd_bearish_cross', False))
        squeeze = bool(current.get('squeeze_active', False))

        mom_pts = (5 if rsi_ok else 0) + (5 if macd_ok else 0) + (5 if squeeze else 0)
        score += mom_pts

        tags = ' + '.join(filter(None, [
            'RSI extremo' if rsi_ok else '',
            'MACD cross'  if macd_ok else '',
            'BB Squeeze'  if squeeze else ''
        ]))

        if mom_pts >= 10:
            checklist.append({"factor": "Momentum", "status": "CONFIRMADO",
                               "detail": tags})
        elif mom_pts > 0:
            checklist.append({"factor": "Momentum", "status": "PARCIAL",
                               "detail": tags or "Confirmación débil"})
        else:
            checklist.append({"factor": "Momentum", "status": "NEUTRAL",
                               "detail": "Sin extremos térmicos activos"})

        # ─────────────────────────────────────────────────────────────
        # 5. SESIÓN / KILLZONE / SWEEPS  (peso 15)
        # ─────────────────────────────────────────────────────────────
        session_weight = 15
        total_weight  += session_weight

        # Killzone: sesión activa en horario de liquidez institucional
        current_session = session_data.get('current_session', 'OFF_HOURS')
        in_kz = current_session in ('LONDON', 'NEW_YORK', 'LONDON_NY_OVERLAP', 'ASIA')

        # Sweeps: el SessionManager ya detecta si se barrió la liquidez
        sessions_info = session_data.get('sessions', {})
        sweep_detected = False
        for ses in sessions_info.values():
            if is_long and ses.get('swept_low'):
                sweep_detected = True
            elif not is_long and ses.get('swept_high'):
                sweep_detected = True

        # También detectar desde el trigger del router
        trigger_up = trigger.upper()
        if 'SWEEP' in trigger_up or 'LIQUIDITY' in trigger_up or 'PDL' in trigger_up:
            sweep_detected = True

        ses_pts = (7 if in_kz else 0) + (8 if sweep_detected else 0)
        score += ses_pts

        tags = ' + '.join(filter(None, [current_session if in_kz else '', 'Sweep' if sweep_detected else '']))
        if ses_pts > 0:
            checklist.append({"factor": "Sesión/Liquidez", "status": "CONFIRMADO",
                               "detail": tags})
        else:
            checklist.append({"factor": "Sesión/Liquidez", "status": "NEUTRAL",
                               "detail": f"Fuera de KillZone ({current_session})"})

        # ─────────────────────────────────────────────────────────────
        # 6. PROYECCIÓN IA — XGBoost ML  (peso 10)
        # ─────────────────────────────────────────────────────────────
        ml_weight     = 10
        total_weight += ml_weight

        ml_dir  = str(ml_projection.get('direction', 'NEUTRAL')).upper()
        ml_prob = float(ml_projection.get('probability', 50))

        ml_ok = (is_long and ml_dir == 'ALCISTA' and ml_prob > 55) or \
                (not is_long and ml_dir == 'BAJISTA' and ml_prob > 55)

        if ml_ok:
            score += ml_weight
            checklist.append({"factor": "Proyección IA", "status": "CONFIRMADO",
                               "detail": f"{ml_dir} al {ml_prob:.0f}% de probabilidad"})
        else:
            checklist.append({"factor": "Proyección IA", "status": "PRECAUCIÓN",
                               "detail": f"IA indecisa o divergente ({ml_dir} {ml_prob:.0f}%)"})

        # ─────────────────────────────────────────────────────────────
        # SCORE FINAL
        # ─────────────────────────────────────────────────────────────
        final_score = int((score / total_weight) * 100) if total_weight > 0 else 0
        conviction  = (
            "ALTA CONVICCIÓN" if final_score >= 70 else
            "SÓLIDA"          if final_score >= 50 else
            "ESPECULATIVA"    if final_score >= 30 else
            "ALTO RIESGO"
        )
        reasoning = self._build_reasoning(final_score, conviction, is_long, regime, has_ob, rvol, in_kz, sweep_detected)

        return {
            "score":      final_score,
            "conviction": conviction,
            "checklist":  checklist,
            "reasoning":  reasoning,
            "rvol":       round(rvol, 2),
        }

    def _build_reasoning(
        self, score: int, conviction: str, is_long: bool,
        regime: str, has_ob: bool, rvol: float, in_kz: bool, sweep: bool
    ) -> str:
        direction = "LONG" if is_long else "SHORT"
        msg = f"Señal {direction} de naturaleza {conviction} ({score}/100). "
        msg += f"Régimen actual: {regime}. "
        if has_ob:
            msg += "Respaldada por un Order Block institucional. "
        if rvol >= 1.5:
            msg += f"Flujo de capital significativo detectado ({rvol:.1f}x). "
        if sweep:
            msg += "Barrida de liquidez confirmada previa a la entrada. "
        if in_kz:
            msg += "Ejecución dentro de KillZone institucional."
        else:
            msg += "Precaución: fuera de horario de liquidez primaria."
        return msg.strip()


# Singleton global — se reutiliza entre llamadas del router
confluence_manager = ConfluenceManager()
