import google.generativeai as genai
import traceback
import asyncio
from engine.api.config import settings

# Limpieza profunda de la Key para evitar caracteres invisibles del .env
GEMINI_API_KEY = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        print("[ADVISOR] 📡 Conectado a Gemini 2.5 Flash.")
    except Exception as e:
        print(f"[ADVISOR] ❌ Error configurando genai: {e}")
        model = None
else:
    model = None
    print("⚠️ [ADVISOR] GEMINI_API_KEY no encontrada.")

async def generate_tactical_advice(asset: str, tactical_data: dict, current_session: str, ml_projection: dict = None) -> str:
    """
    Genera un consejo cuantitativo breve usando Gemini LLM de forma asíncrona.
    """
    if not model:
        return "ADVISOR LOG: SYSTEM_OFFLINE (Missing API Key). Awaiting manual override."

    strategy = tactical_data.get('active_strategy', 'UNKNOWN')
    regime = tactical_data.get('market_regime', 'UNKNOWN')
    
    # Extraer data de la matriz de diagnóstico
    diag = tactical_data.get('diagnostic', {}) or {}
    rsi = diag.get('rsi', 50) or 50
    macd_cross = "BULLISH" if diag.get('macd_bullish_cross') else "BEARISH/NEUTRAL"
    bbwp = diag.get('bbwp', 0)
    squeeze = "ACTIVE" if diag.get('squeeze_active') else "INACTIVE"
    in_killzone = "SÍ (Volumen Institucional Alto)" if diag.get('in_killzone', False) else "NO (Volumen Minorista/Lento)"
    bull_div = "PRESENTE" if diag.get('bullish_divergence') else "NO"
    bear_div = "PRESENTE" if diag.get('bearish_divergence') else "NO"
    
    # Extraer data de Estructura (SMC / Soportes)
    smc = tactical_data.get('smc', {})
    obs_bullish = len(smc.get('order_blocks', {}).get('bullish', []))
    obs_bearish = len(smc.get('order_blocks', {}).get('bearish', []))
    fvgs_bullish = len(smc.get('fvgs', {}).get('bullish', []))
    fvgs_bearish = len(smc.get('fvgs', {}).get('bearish', []))
    def f_p(p):
        if p == 0: return "0.00"
        if isinstance(p, (int, float)): 
            # Precision extrema para monedas micro (PEPE, FLOKI, etc)
            dp = 10 if p < 0.0001 else 8 if p < 0.01 else 2
            return f"{p:.{dp}f}".rstrip('0').rstrip('.')
        return str(p)

    support = f_p(tactical_data.get('nearest_support')) if tactical_data.get('nearest_support') else 'N/A'
    resistance = f_p(tactical_data.get('nearest_resistance')) if tactical_data.get('nearest_resistance') else 'N/A'
    
    # Extraer Proyección Matemático-Mecánica (ML XGBoost)
    ml_projection = ml_projection or {}
    ml_dir = str(ml_projection.get('direction', 'ANALIZANDO')).upper()
    try:
        p_raw = ml_projection.get('probability', 50)
        ml_prob = float(p_raw) if p_raw is not None else 50.0
    except:
        ml_prob = 50.0
    ml_reason = ml_projection.get('reason', 'SIN DATA')
    
    # Extraer Data de Fibonacci
    fibo = tactical_data.get('fibonacci', {}) or {}
    fibo_lvl = fibo.get('current_level') or 'N/A'
    
    # Definir R:R dinámico basado en la estrategia
    # Reversion = Más defensivo (1:2) | Trend/SMC = Más agresivo (1:3 o superior)
    recommended_rr = "1:2" if "REVERSION" in strategy else "1:3"

    prompt = f"""
    Eres el 'Asesor Cuantitativo Institucional' del sistema Slingshot.
    Tu trabajo es leer los datos en crudo de la Matriz de Confluencia HFT y emitir UN (1) resumen táctico analítico de máximo 3 oraciones.
    
    ESTADO ACTUAL DEL MERCADO ({asset}):
    - Sesión Activa: {current_session} | Dentro de KillZone: {in_killzone}
    - Régimen Wyckoff: {regime} | Estrategia Seleccionada: {strategy}
    - RSI: {rsi:.1f} | MACD Estado: {macd_cross} | Volatilidad (BBWP): {bbwp:.1f}% (Squeeze: {squeeze})
    - Divergencias Ocultas: Alcista ({bull_div}) / Bajista ({bear_div})
    
    NIVELES CLAVE Y ESTRUCTURA (SMC):
    - Soporte Más Cercano: ${support} | Resistencia Más Cercana: ${resistance}
    - Nivel Fibonacci Actual: {fibo_lvl}
    - Liquidez Institucional: {obs_bullish + fvgs_bullish} zonas de Demanda (Alcistas) y {obs_bearish + fvgs_bearish} zonas de Oferta (Bajistas).
    
    INTELIGENCIA ARTIFICIAL MECÁNICA (XGBoost):
    - Proyección Algorítmica Probabilística: {ml_dir} ({ml_prob}%)
    
    REGLAS ESTRICTAS PARA TU RESPUESTA:
    1. DEBES devolver ÚNICAMENTE el texto final, ortografía PERFECTA, sin errores tipográficos simulados, sin markdown.
    2. El tono debe ser frío, militar, ultra-preciso, analítico y en MAYÚSCULAS PURAS.
    3. Si las métricas (SMC, RSI, ML) convergen, emite una directiva clara (ej: "DESPLEGAR LARGOS").
    4. Si hay contradicción grave, recomienda "ESPERAR CONFIRMACIÓN" o "MANTENERSE AL MARGEN".
    5. No menciones los nombres de los indicadores si no aportan valor clave.
    6. JAMÁS dejes la frase cortada a medias. Termina tu análisis limpiamente.
    7. AL FINAL de tu mensaje, DEBES incluir obligatoriamente la recomendación de Ratio Riesgo/Beneficio dinámico adjunta en el formato [R:R TGT {recommended_rr}]

    Ejemplo de respuesta ideal:
    MÁXIMA CONFLUENCIA ALCISTA DETECTADA EN LONDRES KILLZONE. PRECIO APOYADO SOBRE DEMANDA INSTITUCIONAL CON IA PROYECTANDO 62% DE PROBABILIDAD. DESPLEGAR ÓRDENES LARGAS APUNTANDO A LA RESISTENCIA MÁS CERCANA. [R:R TGT 1:3]
    """

    try:
        # Usamos la versión síncrona dentro de un thread para evitar colgar el loop de asyncio
        # y asegurar compatibilidad máxima con el SDK GenAI 0.8.x
        import asyncio
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0
            )
        )
        advice = response.text.strip()
        advice = advice.replace('\n', ' ').replace('**', '').replace('ADVISOR LOG:', '').strip()
        print(f"[ADVISOR] ✅ Análisis generado para {asset} ({len(advice)} chars)")
        return advice
    except Exception as e:
        print(f"[ADVISOR] ❌ CRITICAL_ERROR en Gemini Node ({asset}):")
        traceback.print_exc()
        return f"ADVISOR LOG: SENSOR_MALFUNCTION. Node Error: {str(e)[:50]}"
