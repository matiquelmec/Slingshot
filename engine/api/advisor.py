import os
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Usando gemini-2.5-flash dado el API key asignado
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    print("⚠️ [ADVISOR] GEMINI_API_KEY no encontrada. El Asesor Autónomo estará deshabilitado.")

def generate_tactical_advice(tactical_data: dict, current_session: str) -> str:
    """
    Genera un consejo cuantitativo breve usando Gemini LLM basado en la data de la Matriz de Confluencia.
    """
    if not model:
        return "ADVISOR LOG: SYSTEM_OFFLINE (Missing API Key). Awaiting manual override."

    strategy = tactical_data.get('active_strategy', 'UNKNOWN')
    regime = tactical_data.get('market_regime', 'UNKNOWN')
    
    # Extraer data de la matriz de diagnóstico
    diag = tactical_data.get('diagnostic', {})
    rsi = diag.get('rsi', 50)
    macd_cross = "BULLISH" if diag.get('macd_bullish_cross') else "BEARISH/NEUTRAL"
    bbwp = diag.get('bbwp', 0)
    squeeze = "ACTIVE" if diag.get('squeeze_active') else "INACTIVE"
    in_killzone = "SÍ (Volumen Institucional Alto)" if diag.get('in_killzone', False) else "NO (Volumen Minorista/Lento)"
    
    # Definir R:R dinámico basado en la estrategia
    # Reversion = Más defensivo (1:2) | Trend/SMC = Más agresivo (1:3 o superior)
    recommended_rr = "1:2" if "REVERSION" in strategy else "1:3"

    prompt = f"""
    Eres el 'Asesor Cuantitativo Institucional' del sistema Slingshot.
    Tu trabajo es leer los datos en crudo de la Matriz de Confluencia al cierre de la vela y emitir UN (1) resumen táctico de máximo 2 oraciones.
    
    ESTADO ACTUAL DEL MERCADO:
    - Sesión Activa: {current_session}
    - Dentro de KillZone (Horario Institucional): {in_killzone}
    - Régimen Wyckoff: {regime}
    - Estrategia Seleccionada por el Motor Algorítmico: {strategy}
    - RSI: {rsi:.1f}
    - MACD Estado: {macd_cross}
    - Volatilidad (BBWP): {bbwp:.1f}% (Squeeze: {squeeze})
    
    REGLAS ESTRICTAS PARA TU RESPUESTA:
    1. DEBES devolver ÚNICAMENTE el texto final, sin formato markdown, sin saludos, sin explicaciones, sin el texto "ADVISOR LOG:".
    2. El tono debe ser de un terminal de alta frecuencia: frío, militar, ultra-preciso, analítico y en español capitalizado (MAYÚSCULAS, símil a Bloomberg Terminal).
    3. Si las condiciones son débiles o contradictorias, o estamos FUERA de KillZone, recomienda "ESPERAR CONFIRMACIÓN" o "MANTENERSE AL MARGEN".
    4. Si hay alineación (ej: RSI < 30 y Régimen Accumulation) Y estamos DENTRO de Killzone, sugiere "DESPLEGAR LARGOS" o "DESPLEGAR CORTOS".
    5. AL FINAL de tu mensaje, DEBES incluir obligatoriamente la recomendación de Ratio Riesgo/Beneficio dinámico adjunta en el formato [R:R TGT {recommended_rr}]

    Ejemplo de respuesta ideal:
    CONDICIONES DE SOBREVENTA DETECTADAS DENTRO DE LONDRES KILLZONE (RSI 28). COMPRESIÓN DE VOLATILIDAD (SQUEEZE) ACTIVA. DESPLEGAR ÓRDENES LARGAS EN EL PRÓXIMO BARRIDO DE SOPORTE. [R:R TGT 1:3]
    """

    try:
        response = model.generate_content(prompt)
        advice = response.text.strip()
        # Limpieza básica por si el LLM se pasa de listo
        advice = advice.replace('\n', ' ').replace('**', '').replace('ADVISOR LOG:', '').strip()
        return advice
    except Exception as e:
        print(f"[ADVISOR] Error de red o en la API de Gemini: {e}")
        return f"ADVISOR LOG: SENSOR_MALFUNCTION. Error communicating with LLM Node."
