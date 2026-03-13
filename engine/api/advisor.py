import httpx
import traceback
import asyncio
import json
from engine.api.config import settings

# Configuración de Ollama Local
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen3:8b" # El "Sweet Spot" para rendimiento y precisión local

# Semáforo global para evitar saturación de la CPU
_ai_semaphore = asyncio.Semaphore(1)

async def check_ollama_status():
    """Verifica si el servidor de Ollama está corriendo."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                print(f"[ADVISOR] 📡 Conectado a Ollama Local (Modelo: {DEFAULT_MODEL}).")
                return True
    except:
        pass
    print("⚠️ [ADVISOR] Ollama no detectado en localhost:11434. Asegúrate de que esté abierto.")
    return False

async def generate_tactical_advice(asset: str, tactical_data: dict, current_session: str, ml_projection: dict = None) -> str:
    """
    Genera un consejo cuantitativo breve usando Ollama Local de forma asíncrona.
    """
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
    
    # Extraer Data de Fibonacci
    fibo = tactical_data.get('fibonacci', {}) or {}
    fibo_lvl = fibo.get('current_level') or 'N/A'
    
    # Definir R:R dinámico basado en la estrategia
    recommended_rr = "1:2" if "REVERSION" in strategy else "1:3"

    # Extraer Sesgo Institucional (HTF)
    htf = tactical_data.get('htf_bias', {}) or {}
    htf_dir = str(htf.get('direction', 'NEUTRAL')).upper()
    htf_reason = htf.get('reason', 'Sin datos institucionales suficientes.')

    prompt = f"""
    Eres el 'Asesor Cuantitativo Institucional' del sistema Slingshot. Operas bajo un modelo MTF (Multi-Timeframe) de 3 capas.
    Tu trabajo es leer los datos en crudo de la Matriz de Confluencia y emitir UN (1) resumen táctico analítico de máximo 3 oraciones.
    
    CONTEXTO INSTITUCIONAL (HIGH TIMEFRAME - 4H/1H):
    - Sesgo Global: {htf_dir}
    - Razón Institucional: {htf_reason}

    ESTADO ACTUAL DEL MERCADO LOCAL ({asset}):
    - Sesión Activa: {current_session} | Dentro de KillZone: {in_killzone}
    - Régimen Wyckoff: {regime} | Estrategia Seleccionada: {strategy}
    - RSI: {rsi:.1f} | MACD Estado: {macd_cross} | Volatilidad (BBWP): {bbwp:.1f}% (Squeeze: {squeeze})
    - Divergencias Ocultas: Alcista ({bull_div}) / Bajista ({bear_div})
    
    NIVELES CLAVE Y ESTRUCTURA (SMC):
    - Soporte Más Cercano: ${support} | Resistencia Más Cercana: ${resistance}
    - Nivel Fibonacci Actual: {fibo_lvl}
    - Liquidez Institucional: {obs_bullish + fvgs_bullish} zonas de Demanda y {obs_bearish + fvgs_bearish} zonas de Oferta.
    
    INTELIGENCIA ARTIFICIAL MECÁNICA (XGBoost):
    - Proyección Algorítmica Probabilística: {ml_dir} ({ml_prob}%)
    
    REGLAS ESTRICTAS PARA TU RESPUESTA:
    1. DEBES devolver ÚNICAMENTE el texto final, ortografía PERFECTA, sin markdown.
    2. El tono debe ser frío, militar, ultra-preciso, analítico y en MAYÚSCULAS PURAS.
    3. PRIORIDAD ESTRATÉGICA: El Sesgo Global (HTF) manda. No recomiendes entrar contra el HTF a menos que el ML sea >85%.
    4. Si hay contradicción grave entre HTF y Local, recomienda "ESPERAR CONFIRMACIÓN" o "MANTENERSE AL MARGEN".
    5. AL FINAL de tu mensaje, DEBES incluir obligatoriamente [R:R TGT {recommended_rr}]
    """

    try:
        async with _ai_semaphore:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "model": DEFAULT_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                }
                
                response = await client.post(OLLAMA_URL, json=payload)
                if response.status_code != 200:
                    return f"ADVISOR LOG: OLLAMA_SERVICER_ERROR ({response.status_code})"
                
                result = response.json()
                advice = result.get("message", {}).get("content", "").strip()
                
                # Limpieza de seguridad
                advice = advice.replace('\n', ' ').replace('**', '').strip()
                
                print(f"[ADVISOR] ✅ Análisis generado localmente para {asset} (Ollama)")
                return advice

    except Exception as e:
        print(f"[ADVISOR] ❌ Error en Ollama Advisor ({asset}): {e}")
        return "ADVISOR LOG: LOCAL_MODEL_OFFLINE. Verifica si Ollama está corriendo."
