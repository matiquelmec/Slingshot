from engine.core.logger import logger
import httpx
import asyncio
import json
import numpy as np
import hashlib
from engine.api.config import settings
from engine.core.session_manager import session_manager

# Configuración de Ollama Local
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "gemma3:4b" 

# Semáforo global para evitar saturación de la CPU (Cola Institucional)
_ai_semaphore = asyncio.Semaphore(1)

# --- SISTEMA DE CACHÉ ESTRATÉGICO v4.6 (SEMANTIC CACHE) ---
# Almacena el último análisis exitoso por activo para evitar redundancia
_strategic_memo = {} 
_semantic_cache = {} # Hash -> Advice mapping

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
    economic_events: list = None,
    onchain_data: dict = None
) -> str:
    """
    Genera un consejo cuantitativo breve usando Ollama Local de forma asíncrona.
    v4.6: Implementa Pre-digested Context y Semantic Caching para latencia mínima.
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
    in_killzone = "SÍ (Volumen Institucional Alto)" if session_manager.is_killzone_active() else "NO (Volumen Minorista/Lento)"
    bull_div = "PRESENTE" if diag.get('bullish_divergence') else "NO"
    bear_div = "PRESENTE" if diag.get('bearish_divergence') else "NO"
    # 📊 VOLUMEN INSTITUCIONAL v5.4.3 (PRODUCCIÓN)
    rvol = diag.get('rvol', 0) or 0
    z_score = diag.get('z_score', 0) or 0
    
    # 🔴 DETECCIÓN DE ANOMALÍAS CRÍTICAS (Z-Score > 5.0)
    # El Z-Score es más preciso que el RVOL para detectar "Flash Pumps" ruidosos.
    is_anomaly = z_score > 5.0 or rvol > 10.0
    rvol_alert = ""
    mandatory_phrase = ""
    
    if is_anomaly and regime in ('RANGING', 'ACCUMULATION', 'DISTRIBUTION', 'UNKNOWN'):
        mandatory_phrase = "ALERTA: ANOMALÍA INSTITUCIONAL (Z-SCORE > 5.0). ABSORCIÓN DETECTADA."
        rvol_alert = f"""
        🚨 [ALERTA DE SEGURIDAD CRÍTICA]
        Z-SCORE RADAR: {z_score:.2f}σ | RVOL: {rvol:.2f}x.
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
    
    # 📐 FIBONACCI GATILLO v4.4
    fibo = tactical_data.get('fibonacci')
    price_in_gp = False
    is_whale = False
    fibo_lvl = 'N/A'
    
    if fibo:
        sh = fibo.get('swing_high', 0)
        sl = fibo.get('swing_low', 0)
        levels = fibo.get('levels', {})
        is_whale = fibo.get('is_whale_leg', False)
        
        # Golden Pocket: 0.618 a 0.66
        gp_top = levels.get('0.618', 0)
        gp_bottom = levels.get('0.66', 0)
        
        # Asegurar orden (en shorts el GP sube)
        low_gp = min(gp_top, gp_bottom)
        high_gp = max(gp_top, gp_bottom)
        
        price_in_gp = (live_price >= low_gp) and (live_price <= high_gp)
        fibo_lvl = f"Swing High: ${f_p(sh)} | Swing Low: ${f_p(sl)} (GP: ${f_p(low_gp)}-${f_p(high_gp)})"
    
    # 🐋 WHALE EXECUTION: Si estamos en GP de una pierna Whale, cambiamos el tono a EXECUTE
    if price_in_gp and is_whale:
        mandatory_phrase = "⚠️ GATILLO DE ENTRADA DETECTADO (GP + WHALE LEG). ACCIÓN: EXECUTE."
    elif price_in_gp:
         mandatory_phrase = "⚠️ ZONA DE INTERÉS (GP). MONITOREAR RECHAZO."
    
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

    # 2. DEFINICIÓN ESTRATÉGICA
    recommended_rr = "1:2" if "REVERSION" in strategy else "1:3"

    # Extraer Sesgo Institucional (HTF)
    htf = tactical_data.get('htf_bias', {}) or {}
    htf_dir = str(htf.get('direction', 'NEUTRAL')).upper()
    htf_reason = htf.get('reason', 'Sin datos institucionales suficientes.')

    # Importar Ghost Data para Capa 1 (Macro)
    from engine.indicators.ghost_data import get_ghost_state
    ghost = get_ghost_state(asset)

    # 💠 LÓGICA DE SMART CACHE (Slingshot v4.6 Semantic)
    current_state = {
        "price": float(tactical_data.get('current_price', 0)),
        "support": support,
        "resistance": resistance,
        "regime": regime,
        "strategy": strategy,
        "ml_prob": ml_prob,
        "dxy": ghost.dxy_trend,
        "nasdaq": ghost.nasdaq_trend,
        "onchain_bias": onchain_data.get("onchain_bias", "NEUTRAL") if onchain_data else "NEUTRAL"
    }
    
    # CÁLCULO DE HASH SEMÁNTICO (Ignoramos pequeñas variaciones de precio < 0.05%)
    state_str = f"{asset}_{regime}_{strategy}_{support}_{resistance}_{ml_dir}_{current_state['onchain_bias']}"
    semantic_hash = hashlib.md5(state_str.encode()).hexdigest()

    if current_state["support"] == "N/A" and current_state["resistance"] == "N/A":
        return "INFORME UNIFICADO v5.4.3: ESTRUCTURA INSTITUCIONAL EN FORMACIÓN. Awaiting data hydration."

    if semantic_hash in _semantic_cache:
        # Validamos si el precio no se ha movido violentamente (>0.1%)
        cached = _semantic_cache[semantic_hash]
        price_diff = abs(current_state["price"] - cached["price"]) / cached["price"] if cached["price"] > 0 else 1.0
        if price_diff < 0.001 and not rvol_is_ultra_high:
            return f"[SEMANTIC CACHE HIT] {cached['advice']}"

    # 🧠 PRE-DIGESTED CONTEXT (Prompt Engineering v4.6)
    # En lugar de enviar todo el historial, enviamos conclusiones procesadas.
    onchain_text = f"Bias On-Chain: {current_state['onchain_bias']} | OI Delta: {onchain_data.get('oi_delta_pct', 0)}%" if onchain_data else "On-Chain: No data."
    
    digest = f"""
    RESUMEN TÁCTICO: {asset} @ ${f_p(live_price)}
    Régimen: {regime} | Estrategia: {strategy} | Killzone: {in_killzone}
    Veredicto Técnico: RSI={rsi}, MACD={macd_cross}, RVOL={rvol:.2f}x, Z-Score={z_score:.2f}σ
    Estructura: S={support}, R={resistance} | Fibo: {fibo_lvl}
    Proyección ML: {ml_dir} ({ml_prob}%)
    Macro: DXY {ghost.dxy_trend}, NASDAQ {ghost.nasdaq_trend}
    On-Chain: {onchain_text}
    """

    prompt = f"""
    Eres el 'Asesor Cuantitativo Institucional' del sistema Slingshot v5.4.3 Unified Platinum. Tu misión es ejecutar el Algoritmo de Decisión SMC de 5 Fases.
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
    {digest}
    
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

    CHECKLIST DE DECISIÓN (ORDEN DE PRIORIDAD):
    [PASO 1] REGLA DE SUPERVIVENCIA (SITREP): SI hay cisne negro (Guerra/Noticias Catastróficas) -> Veredicto: 'DEFCON 1 (DESCARTAR)'.
    
    [PASO 2] GATE DE CANALIZACIÓN (EL MURO): ¿Killzone Activa ({in_killzone})? 
    ⚠️ LEY INQUEBRANTABLE: SI LA KILLZONE ES 'NO', DETÉN TODO ANÁLISIS. TU VEREDICTO DEBE SER 'DESCARTAR' SIN IMPORTAR CUALQUER OTRA MÉTRICA (NI RVOL, NI SMC, NI ML). NO JUSTIFIQUES. SOLO DESCARTA.
    
    [PASO 3] LEY DXY: ¿DXY favorece la dirección? DXY BULLISH = BLOQUEO DE LONGS.
    
    [PASO 4] ABSORCIÓN INSTITUCIONAL: Si llegaste aquí y el RVOL es {rvol:.2f}x (Régimen: {regime}) -> ¿Hay Absorción? Si el RVOL es Ultra-Alto (>10x), prioriza la acumulación.

    [PASO 5] VEREDICTO FINAL: Decisión unificada. 
    ⚠️ RECORDATORIO: Si Killzone es 'NO', el Veredicto es 'DESCARTAR'. Si Killzone es 'SÍ', integra SMC y {f"MANDATORIO USAR FRASE: '{mandatory_phrase}'" if mandatory_phrase else "Veredicto Técnico"}.

    FORMATO DE RESPUESTA:
    1. INICIO: "INFORME UNIFICADO v5.4.3 PLATINUM: [TU VEREDICTO EN 1 PALABRA: DESCARTAR | COMPRAR | VENDER]"
    2. CUERPO: 2 oraciones máximo explicando la confluencia (o la falta de Killzone).
    3. CIERRE: [RIESGO TGT 1:3]
    """


    try:
        logger.info(f"[ADVISOR] ⏳ Reservando motor IA para {asset}...")
        async with _ai_semaphore:
            logger.info(f"[ADVISOR] 🚀 Motor IA activo para {asset}. Llamando a Ollama...")

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

                # Formateo institucional: Limpiar markdown pesado pero mantener estructura
                advice = advice.replace('**', '').replace('###', '').strip()

                # Actualizar Memoria y Semantic Cache
                _strategic_memo[asset] = {**current_state, "advice": advice}
                _semantic_cache[semantic_hash] = {"price": current_state["price"], "advice": advice}

                logger.info(f"[ADVISOR] ✅ Análisis generado para {asset} | Hash: {semantic_hash[:8]}")
                return advice

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
