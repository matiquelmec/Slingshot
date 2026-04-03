from engine.core.logger import logger
import httpx
import traceback
import asyncio
import json
import numpy as np
from engine.api.config import settings

# Configuración de Ollama Local
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "gemma3:4b" 

# Semáforo global para evitar saturación de la CPU (Cola Institucional)
_ai_semaphore = asyncio.Semaphore(1)

# --- SISTEMA DE CACHÉ ESTRATÉGICO (v4.2 Platinum) ---
# Almacena el último análisis exitoso por activo para evitar redundancia
_strategic_memo = {} 

async def check_ollama_status():
    """Verifica si el servidor de Ollama está corriendo."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                return True
    except:
        pass
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
    
    # 🔴 PRECIO LIVE v4.3.4: Usar current_price inyectado por _emit_advisor (latest tick del WS)
    live_price = float(tactical_data.get('current_price', 0))
    
    # Extraer data de la matriz de diagnóstico
    diag = tactical_data.get('diagnostic', {}) or {}
    rsi = diag.get('rsi', 50) or 50
    macd_cross = "BULLISH" if diag.get('macd_bullish_cross') else "BEARISH/NEUTRAL"
    bbwp = diag.get('bbwp', 0)
    squeeze = "ACTIVE" if diag.get('squeeze_active') else "INACTIVE"
    in_killzone = "SÍ (Volumen Institucional Alto)" if diag.get('in_killzone', False) else "NO (Volumen Minorista/Lento)"
    bull_div = "PRESENTE" if diag.get('bullish_divergence') else "NO"
    bear_div = "PRESENTE" if diag.get('bearish_divergence') else "NO"
    rvol = diag.get('rvol', 0) or 0
    
    # 🔴 DETECCIÓN DE ABSORCIÓN CRÍTICA v4.3.5 (HARDENED)
    rvol_is_ultra_high = rvol > 10.0
    rvol_alert = ""
    mandatory_phrase = ""
    
    if rvol_is_ultra_high and regime in ('RANGING', 'ACCUMULATION', 'DISTRIBUTION', 'UNKNOWN'):
        mandatory_phrase = "ALERTA: FUEGO INSTITUCIONAL DETECTADO. PREPARAR EXPANSIÓN."
        rvol_alert = f"""
        🚨 [ALERTA DE SEGURIDAD CRÍTICA]
        RVOL DETECTADA POR RADAR: {rvol:.2f}x.
        ESTADO: ABSORCIÓN PROFESIONAL MASIVA.
        INSTRUCCIÓN MANDATORIA: DEBES UTILIZAR LA FRASE EXACTA: '{mandatory_phrase}' EN TU VEREDICTO.
        EXPLICACIÓN: Las instituciones están inyectando volumen sin mover el precio (Absorción). Esto es el precursor de una expansión violenta.
        """
    elif rvol > 5.0:
        rvol_alert = f"⚠️ [VOLUMEN ANORMAL] RVOL de {rvol:.2f}x detectado. Alta probabilidad de manipulación o expansión."

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

    # 💠 LÓGICA DE SMART CACHE (Slingshot v4.2 Platinum)
    current_state = {
        "price": float(tactical_data.get('current_price', 0)),
        "support": support,
        "resistance": resistance,
        "regime": regime,
        "strategy": strategy,
        "ml_prob": ml_prob,
        "dxy": ghost.dxy_trend,
        "nasdaq": ghost.nasdaq_trend
    }
    
    if current_state["support"] == "N/A" and current_state["resistance"] == "N/A":
        return "INFORME SMC V4.1 PLATINUM: ESTRUCTURA INSTITUCIONAL EN FORMACIÓN. Awaiting data hydration."

    prev = _strategic_memo.get(asset)
    if prev:
        price_stable = abs(current_state["price"] - prev["price"]) / prev["price"] < 0.0001 if prev["price"] > 0 else False
        if price_stable and current_state["support"] == prev["support"] and current_state["regime"] == prev["regime"]:
            # Solo reutilizar si el RVOL no ha explotado en el ínterin
            if not rvol_is_ultra_high:
                return f"[CONSISTENTE CON ÚLTIMA LECTURA] {prev['advice']}"

    prompt = f"""
    Eres el 'Asesor Cuantitativo Institucional' del sistema Slingshot v4.3. Tu misión es ejecutar el Algoritmo de Decisión SMC de 5 Fases.
    ERES UNA MÁQUINA LÓGICA REGLAMENTARIA. DEBES OBEDECER ESTAS LEYES INQUEBRANTABLES:

    ═══════════════════════════════════════════
    LEYES DE CONSISTENCIA DE DATOS (MANDATORIAS):
    ═══════════════════════════════════════════
    - SI EL RADAR DICE RVOL > 10x, DEBES REPORTARLO COMO TAL. PROHIBIDO REPORTAR UN RVOL BAJO.
    - SI 'Killzone Activa' es NO, TIENES PROHIBIDO USAR LA KILLZONE COMO ARGUMENTO PARA VALIDAR UNA ENTRADA. SI NO HAY KILLZONE, NO HAY OPERACIÓN.
    - SI EL PRECIO ESTÁ EN 'RANGING' CON RVOL > 10x, EL VEREDICTO DEBE INDICAR ABSORCIÓN.

    ═══════════════════════════════════════════
    LEYES MACRO (CORRELACIÓN DXY-CRIPTO):
    ═══════════════════════════════════════════
    - DXY BULLISH (Dólar fuerte) = PELIGRO PARA LONGS. 
    - DXY BEARISH (Dólar débil) = FAVORABLE PARA LONGS. 
    ⚠️ LEY DXY: DXY BEARISH = FAVORABLE PARA LONGS EN CRIPTO. SI en tu análisis dices "DXY Bearish" y luego prohíbes longs, estás VIOLANDO esta ley.

    ═══════════════════════════════════════════
    DATOS SENSORIZADOS (EL ORÁCULO):
    ═══════════════════════════════════════════
    🔴 PRECIO LIVE: ${f_p(live_price)}
    🔴 RVOL (VOLUMEN RELATIVO): {rvol:.2f}x (LEER ESTE DATO COMO VERDAD ABSOLUTA)
    🔴 KILLZONE ACTIVA: {in_killzone} (SI DICE 'NO', NO HAY KILLZONE. NO ALUCINES.)
    🔴 RÉGIMEN DE MERCADO: {regime}
    
    {rvol_alert}

    CAPA 1: CONTEXTO GLOBAL MACRO
    - DXY Trend: {ghost.dxy_trend} | NASDAQ Trend: {ghost.nasdaq_trend}
    - HTF Global Bias: {htf_dir}
    
    CAPA 2: NARRATIVA DIARIA
    - Sesión Actual: {current_session}
    
    CAPA 3: ZONAS INSTITUCIONALES (SMC)
    - SOPORTE: {support} | RESISTENCIA: {resistance}
    - Zonas: {obs_bullish + fvgs_bullish} Bullish / {obs_bearish + fvgs_bearish} Bearish
    
    CAPA 4: GATILLO NEURONAL (IA)
    - Proyección XGBoost: {ml_dir} ({ml_prob}%)

    CHECKLIST DE DECISIÓN:
    [PASO 1] DEFCON CHECK: SI hay cisne negro (Guerra/Hack) -> Veredicto: DEFCON 1.
    [PASO 2] LEY DXY: ¿DXY favorece o prohíbe la dirección deseada?
    [PASO 3] ABSORCIÓN: Si el RVOL es {rvol:.2f}x y el régimen es {regime} -> ¿Hay Absorción Institucional? 
    [PASO 4] SESIÓN: ¿Killzone Activa ({in_killzone})? SI ES 'NO', EL VEREDICTO DEBE SER 'DESCARTAR'.
    [PASO 5] VEREDICTO FINAL: Decisión unificada. {f"MANDATORIO USAR FRASE: '{mandatory_phrase}'" if mandatory_phrase else ""}

    FORMATO:
    1. EMPIEZA CON "INFORME SMC V4.3.5 TITANIUM:".
    2. BREVEDAD MILITAR. SIN RODEOS.
    3. AL FINAL: [RIESGO DE SISTEMA: TGT 1:3 MINIMO INNEGOCIABLE]
    """


    try:
        logger.info(f"[ADVISOR] ⏳ Reservando motor IA para {asset}...")
        async with _ai_semaphore:
            logger.info(f"[ADVISOR] 🚀 Motor IA activo para {asset}. Llamando a Ollama...")
            
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
                
                logger.info(f"--- [DEBUG FULL PROMPT FOR {asset}] ---")
                logger.info(prompt)
                logger.info(f"--- [DEBUG TACTICAL DATA FOR {asset}] ---")
                logger.info(f"Soporte={support} | Resistencia={resistance} | sups={len(sups)} | nearest_s={tactical_data.get('nearest_support')}")
                logger.info("--- [END DEBUG] ---")

                response = await client.post(OLLAMA_URL, json=payload)
                if response.status_code != 200:
                    return f"ADVISOR LOG: OLLAMA_SERVICER_ERROR ({response.status_code})"
                
                result = response.json()
                advice = result.get("message", {}).get("content", "").strip()
                
                # Limpieza de seguridad y formateo profesional
                advice = advice.replace('\n', ' ').replace('**', '').strip()
                
                # Actualizar Memoria de Corto Plazo
                _strategic_memo[asset] = {**current_state, "advice": advice}
                
                # --- SNAPSHOT FORENSICS POST-TRADE (Nivel Auditoría Black-Box) ---
                try:
                    import time
                    forensics = {
                        "ts_ms": int(time.time() * 1000),
                        "asset": asset,
                        "session": current_session,
                        "state_snapshot": current_state,
                        "raw_ml": ml_dir,
                        "news_feed": news_text,
                        "macro_cal": cal_text,
                        "prompt_sent": prompt,
                        "raw_llm_response": advice
                    }
                    with open(f"c:/tmp/forensics_{asset.lower()}_{int(time.time())}.json", "w", encoding="utf-8") as fb:
                        json.dump(forensics, fb, indent=4, ensure_ascii=False)
                except Exception as fx:
                    logger.error(f"[ADVISOR] Forensics dump failed: {fx}")
                
                logger.info(f"[ADVISOR] ✅ Análisis generado localmente para {asset} (Ollama)")
                return advice
        # El bloque with libera el semáforo automáticamente

    except Exception as e:
        logger.error(f"[ADVISOR] ❌ Error en Ollama Advisor ({asset}): {e}")
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
