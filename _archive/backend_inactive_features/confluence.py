import pandas as pd
import numpy as np

class ConfluenceManager:
    """
    El Jurado Neural de SLINGSHOT.
    Evalúa cada señal contra el arsenal completo de indicadores.
    Calcula un 'Institutional Score' y genera un 'Diagnostic Report' transparente.
    """
    
    def __init__(self, ghost_data: dict = None, ml_projection: dict = None):
        self.ghost_data = ghost_data or {}
        self.ml_projection = ml_projection or {}
        
    def evaluate_signal(self, df: pd.DataFrame, signal: dict) -> dict:
        """
        Analiza una señal y retorna un reporte detallado de confluencias.
        """
        current = df.iloc[-1]
        sig_type = signal.get('type', '').upper()
        is_long = 'LONG' in sig_type
        
        checklist = []
        score = 0
        total_weight = 0
        
        # --- 1. Régimen de Wyckoff (Peso: 25) ---
        regime = current.get('market_regime', 'UNKNOWN')
        regime_weight = 25
        total_weight += regime_weight
        
        regime_valid = False
        if is_long:
            regime_valid = regime in ('ACCUMULATION', 'MARKUP', 'RANGING')
        else:
            regime_valid = regime in ('DISTRIBUTION', 'MARKDOWN', 'RANGING')
            
        if regime_valid:
            score += regime_weight
            checklist.append({"factor": "Régimen Wyckoff", "status": "CONFIRMADO", "detail": f"Alineado con {regime}"})
        else:
            checklist.append({"factor": "Régimen Wyckoff", "status": "DIVERGENTE", "detail": f"Desajuste en {regime}"})

        # --- 2. Estructura SMC (Order Blocks / Gaps / SR) (Peso: 20) ---
        struct_weight = 20
        total_weight += struct_weight
        has_ob = current.get('ob_bullish' if is_long else 'ob_bearish', False)
        has_fvg = current.get('fvg_bullish' if is_long else 'fvg_bearish', False)
        
        struct_points = 0
        if has_ob: struct_points += 10
        if has_fvg: struct_points += 10
        
        score += struct_points
        if struct_points > 0:
            checklist.append({"factor": "Estructura SMC", "status": "CONFIRMADO", "detail": f"{'OB' if has_ob else ''} {'FVG' if has_fvg else ''} detectado"})
        else:
            checklist.append({"factor": "Estructura SMC", "status": "NEUTRAL", "detail": "Sin zonas institucionales inmediatas"})

        # --- 3. Volumen Institucional (RVOL) (Peso: 15) ---
        vol_weight = 15
        total_weight += vol_weight
        rvol = current.get('rvol', 1.0)
        
        if rvol >= 1.5:
            score += vol_weight
            checklist.append({"factor": "Volumen RVOL", "status": "CONFIRMADO", "detail": f"Interés institucional ({rvol:.2f}x)"})
        else:
            checklist.append({"factor": "Volumen RVOL", "status": "BAJO", "detail": f"Volumen estándar ({rvol:.2f}x)"})

        # --- 4. Momentum (RSI / MACD / BBWP) (Peso: 15) ---
        mom_weight = 15
        total_weight += mom_weight
        
        has_rsi = current.get('rsi_oversold' if is_long else 'rsi_overbought', False)
        has_macd = current.get('macd_bullish_cross' if is_long else 'macd_bearish_cross', False) # Notar: macd_bearish_cross podría no estar, checkeamos
        has_squeeze = current.get('squeeze_active', False)
        
        mom_points = 0
        if has_rsi: mom_points += 5
        if has_macd: mom_points += 5
        if has_squeeze: mom_points += 5
        
        score += mom_points
        if mom_points >= 10:
            checklist.append({"factor": "Momentum", "status": "CONFIRMADO", "detail": "Confluencia de osciladores"})
        elif mom_points > 0:
            checklist.append({"factor": "Momentum", "status": "PARCIAL", "detail": "Confirmación débil de indicadores"})
        else:
            checklist.append({"factor": "Momentum", "status": "NEUTRAL", "detail": "Sin extremos térmicos"})

        # --- 5. Sesión y Liquidez (KillZones / Sweeps) (Peso: 15) ---
        session_weight = 15
        total_weight += session_weight
        
        in_kz = current.get('in_killzone', False)
        has_sweep = any([
            current.get('sweep_asian_low' if is_long else 'sweep_asian_high', False),
            current.get('sweep_london_low' if is_long else 'sweep_london_high', False),
            current.get('sweep_pdl' if is_long else 'sweep_pdh', False)
        ])
        
        session_points = 0
        if in_kz: session_points += 7
        if has_sweep: session_points += 8
        
        score += session_points
        if session_points > 0:
            checklist.append({"factor": "Sesión/Liquidez", "status": "CONFIRMADO", "detail": f"{'KillZone' if in_kz else ''} {'Sweep' if has_sweep else ''}"})
        else:
            checklist.append({"factor": "Sesión/Liquidez", "status": "NEUTRAL", "detail": "Fuera de horarios institucionales"})

        # --- 6. Proyección IA (ML) (Peso: 10) ---
        ml_weight = 10
        total_weight += ml_weight
        
        ml_dir = self.ml_projection.get('direction', 'NEUTRAL')
        ml_prob = self.ml_projection.get('probability', 50)
        
        ml_valid = False
        if is_long:
            ml_valid = ml_dir == 'ALCISTA' and ml_prob > 55
        else:
            ml_valid = ml_dir == 'BAJISTA' and ml_prob > 55
            
        if ml_valid:
            score += ml_weight
            checklist.append({"factor": "Proyección IA", "status": "CONFIRMADO", "detail": f"Probabilidad {ml_prob}% de éxito"})
        else:
            checklist.append({"factor": "Proyección IA", "status": "PRECABER", "detail": f"IA indecisa o divergente ({ml_prob}%)"})

        # --- Cálculo Final ---
        final_score = int((score / total_weight) * 100)
        
        # Razonamiento narrativo
        reasoning = self._generate_reasoning(final_score, is_long, regime, has_ob, rvol, in_kz)
        
        return {
            "score": final_score,
            "checklist": checklist,
            "reasoning": reasoning
        }

    def _generate_reasoning(self, score: int, is_long: bool, regime: str, has_ob: bool, rvol: float, in_kz: bool) -> str:
        sentiment = "ALTA CONVICCIÓN" if score > 75 else "SÓLIDA" if score > 50 else "ESPECULATIVA"
        direction = "COMPRA" if is_long else "VENTA"
        
        msg = f"Entrada de {direction} de naturaleza {sentiment}. "
        msg += f"El mercado se encuentra en fase de {regime}, "
        
        if has_ob:
            msg += "apoyado por un Order Block institucional. "
        else:
            msg += "buscando soporte en niveles estructurales. "
            
        if rvol > 1.5:
            msg += f"Se detecta inyección de capital significativa ({rvol:.1f}x). "
        
        if in_kz:
            msg += "Operación ejecutada dentro de KillZone de alta liquidez."
        else:
            msg += "Precaución: ejecución fuera de volumen institucional primario."
            
        return msg
