import httpx
import traceback
import asyncio
import json
import numpy as np
from engine.api.config import settings

# Configuración de Ollama Local
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "gemma3:4b" # Ajustado al modelo instalado en el sistema local

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

async def generate_tactical_advice(
    asset: str, 
    tactical_data: dict, 
    current_session: str, 
    ml_projection: dict = None,
    news: list = None,
    liquidations: list = None,
    economic_events: list = None
) -> str:
    """
    Genera un consejo cuantitativo breve usando Ollama Local de forma asíncrona.
    Incorpora sentimiento de noticias y zonas de liquidación para máxima precisión.
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
        try:
            if p is None or (isinstance(p, float) and np.isnan(p)): return "N/A"
            if p == 0: return "0.00"
            if isinstance(p, (int, float)): 
                dp = 10 if p < 0.0001 else 8 if p < 0.01 else 2
                return f"{p:.{dp}f}".rstrip('0').rstrip('.')
            return str(p)
        except:
            return "N/A"

    # 1. SOPORTES Y RESISTENCIAS (Triple Canal de Búsqueda v4.6)
    kl = tactical_data.get('key_levels', {})
    smc_raw = tactical_data.get('smc', {})
    
    # Canal A: Key Levels | Canal B: SMC Backup | Canal C: Nearest Anchors
    sups = kl.get('supports', []) or smc_raw.get('key_supports', [])
    resists = kl.get('resistances', []) or smc_raw.get('key_resistances', [])
    
    support = f_p(sups[0]['price']) if (sups and 'price' in sups[0]) else (f_p(tactical_data.get('nearest_support')) if tactical_data.get('nearest_support') else 'N/A')
    resistance = f_p(resists[0]['price']) if (resists and 'price' in resists[0]) else (f_p(tactical_data.get('nearest_resistance')) if tactical_data.get('nearest_resistance') else 'N/A')
    
    # Extraer Proyección Matemático-Mecánica (ML XGBoost)
    ml_projection = ml_projection or {}
    ml_dir = str(ml_projection.get('direction', 'ANALIZANDO')).upper()
    try:
        p_raw = ml_projection.get('probability', 50)
        ml_prob = float(p_raw) if p_raw is not None else 50.0
    except:
        ml_prob = 50.0
    
    # Extraer Data de Fibonacci
    fibo = tactical_data.get('fibonacci')
    if fibo:
        sh = f_p(fibo.get('swing_high', 0))
        sl = f_p(fibo.get('swing_low', 0))
        fibo_lvl = f"Swing High: ${sh} | Swing Low: ${sl}"
    else:
        fibo_lvl = 'N/A'
    
    # Procesar Noticias Recientes (Sentimiento Híbrido)
    news_text = "SIN NOTICIAS RECIENTES DE ALTO IMPACTO."
    if news:
        top_news = news[:3] # Solo las 3 más frescas
        news_lines = []
        for n in top_news:
            line = f"[{n.get('sentiment', 'NEUTRAL')}] {n.get('title')} -> Impacto: {n.get('impact')}"
            news_lines.append(line)
        news_text = "\n    ".join(news_lines)

    # Procesar Zonas de Liquidación (Magnetismo de Precios)
    liq_text = "ZONAS DE LIQUIDACIÓN NO DETECTADAS O MUY ALEJADAS."
    if liquidations:
        top_liqs = sorted(liquidations, key=lambda x: x.get('strength', 0), reverse=True)[:4]
        liq_lines = []
        for l in top_liqs:
            line = f"Precio: ${f_p(l['price'])} | Tipo: {l['type']} | Fuerza: {l['strength']}% | Apalancamiento: {l['leverage']}x"
            liq_lines.append(line)
        liq_text = "\n    ".join(liq_lines)

    # Procesar Calendario Económico (Eventos Macro con Memoria)
    cal_text = "SIN EVENTOS MACRO INMINENTES RELEVANTES."
    if economic_events:
        cal_lines = []
        for ev in economic_events[:5]:
            status_tag = f"[{ev.get('status', 'UPCOMING')}]"
            date_time = ev.get('date', '').split('T')[1][:5] if 'T' in ev.get('date', '') else ''
            cal_lines.append(f"{status_tag} {ev.get('country')}: {ev.get('title')} ({date_time}) -> Impacto: {ev.get('impact')}")
        cal_text = "\n    ".join(cal_lines)

    # Definir R:R dinámico basado en la estrategia
    recommended_rr = "1:2" if "REVERSION" in strategy else "1:3"

    # Extraer Sesgo Institucional (HTF)
    htf = tactical_data.get('htf_bias', {}) or {}
    htf_dir = str(htf.get('direction', 'NEUTRAL')).upper()
    htf_reason = htf.get('reason', 'Sin datos institucionales suficientes.')

    # Importar Ghost Data para Capa 1 (Macro)
    from engine.indicators.ghost_data import get_ghost_state
    ghost = get_ghost_state(asset)

    prompt = f"""
    Eres el 'Asesor Cuantitativo Institucional' del sistema Slingshot v4.0. Tu misión es ejecutar el Algoritmo de Decisión SMC de 5 Fases.
    ERES UNA MÁQUINA LÓGICA REGLAMENTARIA. DEBES OBEDECER ESTAS LEYES INQUEBRANTABLES:
    LEYES MACRO: 
    - SI DXY ES BULLISH: PROHIBIDO LONG EN CRIPTO. SOLO BUSCAR SHORTS O DESCARTAR (DXY sube = Dólar fuerte = Cripto cae).
    - SI DXY ES BEARISH: BUSCAR LONGS EN CRIPTO (Dólar débil = Cripto sube).
    - SI NASDAQ CAE: PROHIBIDO LONGS EN CRIPTO.
    LEYES DE SESIÓN:
    - ASIA (20:00-03:00): ZONA DE ACUMULACIÓN. PROHIBIDO OPERAR.
    - LONDON (04:00-08:00): ZONA DE TRAMPA/BARRIDO. ESPERAR MANIPULACIÓN.
    - NY (09:30-12:00): ZONA DE EJECUCIÓN (KILLZONE). SÓLO AQUÍ SE OPERA CONTINUACIÓN.
    - OFF_HOURS / AUSENCIA DE KILLZONE: PROHIBIDO OPERAR (Falta de liquidez institucional).
    
    CAPA 1: CONTEXTO GLOBAL MACRO (DXY/NASDAQ)
    - DXY Trend: {ghost.dxy_trend} | NASDAQ Trend: {ghost.nasdaq_trend}
    - HTF Global Bias: {htf_dir} (Razón: {htf_reason})

    CAPA 2: NARRATIVA DIARIA (SESIONES)
    - Sesión Actual: {current_session} | Killzone Activa: {in_killzone}

    CAPA 3: ZONAS INSTITUCIONALES (SMC)
    - Activo: {asset}
    - Zonas de Oferta (Bearish): {obs_bearish + fvgs_bearish} | Zonas de Demanda (Bullish): {obs_bullish + fvgs_bullish}
    - SOPORTE CRÍTICO (SISTEMA DE ANCLAJE): {support}
    - RESISTENCIA CRÍTICA (SISTEMA DE ANCLAJE): {resistance}
    - Fib Level Actual: {fibo_lvl}

    CAPA 4: GATILLO Y MICRO-ESTRUCTURA
    - Proyección Direccional XGBoost (IA): {ml_dir} ({ml_prob}%)

    REKT MAGNETS (Liquidaciones & Noticias):
    {liq_text}
    {news_text}
    
    CALENDARIO ECONÓMICO (Macro Inminente):
    {cal_text}

    EJECUTA ESTE CHECKLIST ESTRICTO PASO A PASO (NIVEL INSTITUCIONAL):
    0. ANALISIS DE NARRATIVA Y CALENDARIO:
       - RIESGO FUTURO: Si hay eventos [UPCOMING] o [LIVE] de ALTO IMPACTO en los próximos 60 min, RECHAZA POR VOLATILIDAD INMINENTE.
       - SENTIMIENTO RECIENTE: Evalúa eventos [RECENT_PAST] de las últimas 12h. Si un evento de ALTO IMPACTO ocurrió recientemente (ejp. Trump, FED), ese sentimiento DOMINA la sesión. Si la noticia fue negativa y buscas LONG, DEBES RECHAZAR O ADVERTIR FUERTE.
       - NEWS FEED: Cruza los titulares de noticias recientes. Si el sentimiento es opuesto a la dirección técnica, la narrativa es FALSA; RECHAZA.
       
    1. LEY DXY: [HARD BLOCK] Si el DXY es BULLISH, cualquier análisis LONG debe ser DENEGADO sin excepción.
    2. LEY SESIÓN: Valida si estamos en NY Killzone. Si es ASIA o LONDON, rechaza por falta de volumen o manipulación.
    3. ESTRUCTURA SMC: Analiza el Soporte y Resistencia enviados. Si están en Discovery (Fallback), menciónalo como 'Zona de Referencia Absoluta'. Si el campo es 'N/A', grita 'ESTRUCTURA NO IDENTIFICADA'.
    4. GATILLO IA (XGBoost): Probabilidad >55% requerida para confirmar.
    5. VEREDICTO FINAL: Si DXY es BULLISH y buscas LONG, el veredicto es DENEGADO por el muro del dólar.

    REGLAS ESTRICTAS PARA TU RESPUESTA:
    1. BREVEDAD NIVEL PENTÁGONO. Sin rodeos.
    2. Tono frío, militar, ultra-profesional. EMPIEZA CON "INFORME SMC V4.1 PLATINUM:".
    3. AL FINAL incluye: [RIESGO DE SISTEMA: TGT 1:3 MINIMO INNEGOCIABLE]
    """

    try:
        print(f"[ADVISOR] ⏳ Reservando motor IA para {asset}...")
        async with _ai_semaphore:
            print(f"[ADVISOR] 🚀 Motor IA activo para {asset}. Llamando a Ollama...")
            
            # DIAGNÓSTICO PROFESIONAL: ¿Qué le llega realmente a la IA?
            try:
                with open("c:/tmp/ai_prompt_sent.log", "w", encoding="utf-8") as f:
                    f.write(f"--- PROMPT PARA {asset} ---\n{prompt}\n---------------------------")
            except:
                pass
                
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "model": DEFAULT_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                }
                
                print(f"--- [DEBUG FULL PROMPT FOR {asset}] ---")
                print(prompt)
                print(f"--- [DEBUG TACTICAL DATA FOR {asset}] ---")
                print(f"Soporte={support} | Resistencia={resistance} | sups={len(sups)} | nearest_s={tactical_data.get('nearest_support')}")
                print("--- [END DEBUG] ---")

                response = await client.post(OLLAMA_URL, json=payload)
                if response.status_code != 200:
                    return f"ADVISOR LOG: OLLAMA_SERVICER_ERROR ({response.status_code})"
                
                result = response.json()
                advice = result.get("message", {}).get("content", "").strip()
                
                # Limpieza de seguridad
                advice = advice.replace('\n', ' ').replace('**', '').strip()
                
                print(f"[ADVISOR] ✅ Análisis generado localmente para {asset} (Ollama)")
                return advice
        # El bloque with libera el semáforo automáticamente

    except Exception as e:
        print(f"[ADVISOR] ❌ Error en Ollama Advisor ({asset}): {e}")
        return "ADVISOR LOG: LOCAL_MODEL_OFFLINE. Verifica si Ollama está corriendo."

async def generate_news_sentiment(headline: str) -> dict:
    """
    Analiza una noticia y devuelve el sentimiento, una breve razón Y la traducción al español.
    """
    prompt = f"""
    Eres un analista de sentimiento cripto experto y traductor técnico. 
    Analiza este titular, tradúcelo perfectamente al español manteniendo el tono financiero, y determina el impacto potencial.
    
    TITULAR ORIGINAL (INGLÉS): "{headline}"
    
    Responde ÚNICAMENTE en formato JSON:
    {{
        "translated_title": "Titular traducido fielmente al español",
        "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
        "score": float, // 0.0 a 1.0 (intensidad)
        "impact": "Breve resumen de 1 oración en español sobre por qué tiene ese impacto."
    }}
    """
    try:
        async with _ai_semaphore:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "model": DEFAULT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json"
                }
                response = await client.post(OLLAMA_URL, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("message", {}).get("content", "{}")
                    return json.loads(content)
    except:
        pass
    return {
        "translated_title": headline, 
        "sentiment": "NEUTRAL", 
        "score": 0.5, 
        "impact": "Análisis y traducción no disponibles actualmente."
    }
