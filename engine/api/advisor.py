import asyncio
import httpx
import json
import hashlib
from typing import List, Dict, Optional
from engine.core.logger import logger
from engine.core.store import store
from engine.api.config import settings

import os

# --- AI QUEUE SYSTEM ---
_ai_queue = asyncio.PriorityQueue()
_ai_task_counter = 0
_active_queue_keys = set()
_strategic_memo = {}
_semantic_cache = {}
_symbol_tasks = {} # [v8.5.4] Seguimiento de tareas para cancelación activa

CACHE_FILE = os.path.join("engine", "data", "ai_cache.json")

def _load_persistent_cache():
    global _semantic_cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _semantic_cache = json.load(f)
                logger.info(f"[ADVISOR] 🧠 Caché semántica cargada: {len(_semantic_cache)} entradas.")
    except Exception as e:
        logger.warning(f"[ADVISOR] Error cargando caché persistente: {e}")

_load_persistent_cache()

DEFAULT_MODEL = settings.OLLAMA_MODEL  # Configurable via .env — default: gemma3:4b
OLLAMA_URL   = settings.OLLAMA_URL     # Configurable via .env — default: http://localhost:11434

_ollama_cache = {"status": False, "last_check": 0, "confirmed_online": False}

async def check_ollama_status(force_recheck=False) -> bool:
    """v5.9.4-Resilience: Salto agresivo si ya está confirmado online en la sesión o si se usa Gemini API."""
    global _ollama_cache
    
    # Si tenemos configurado OpenRouter, Groq o Gemini, la IA está activa (cloud)
    if settings.OPENROUTER_API_KEY or settings.GEMINI_API_KEY or settings.GROQ_API_KEY:
        return True
        
    # 1. Bypass total: si ya se confirmó una vez, no volver a preguntar al servidor tags (que se bloquea en heavy load)
    if _ollama_cache["confirmed_online"]:
        return True
        
    now = asyncio.get_event_loop().time()
    if not force_recheck and (now - _ollama_cache["last_check"] < 5.0):
        return _ollama_cache["status"]
        
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            status = (response.status_code == 200)
            if status:
                _ollama_cache["confirmed_online"] = True
            _ollama_cache["status"] = status
            _ollama_cache["last_check"] = now
            return status
    except Exception:
        _ollama_cache["status"] = False
        _ollama_cache["last_check"] = now
        return False


def _deterministic_verdict(symbol: str, tactical_data: dict, session: str = "UNKNOWN") -> str:
    """
    v13.1: Mini-advisor determinístico para cuando Ollama está offline.
    Genera un veredicto JSON válido basado en las mismas reglas del prompt LLM.
    """
    regime = tactical_data.get("regime", tactical_data.get("market_regime", "IDLE"))
    signal = tactical_data.get("signal", "NEUTRAL")
    rvol = (tactical_data.get("diagnostic") or {}).get("rvol", 0)

    # Evaluación de amenaza basada en RVOL y régimen
    if regime in ("CHOPPY", "DISTRIBUTION") and rvol > 2.0:
        threat = "HIGH"
    elif regime in ("RANGING", "IDLE") or session == "OFF_HOURS":
        threat = "MEDIUM"
    else:
        threat = "LOW"

    # Veredicto basado en señal y amenaza
    if threat == "HIGH":
        verdict = "AVOID"
    elif signal != "NEUTRAL":
        verdict = "GO"
    else:
        verdict = "SIDEWAYS"

    logic_map = {
        "MARKUP": "Tendencia alcista activa",
        "MARKDOWN": "Presión bajista activa",
        "ACCUMULATION": "Acumulación institucional",
        "DISTRIBUTION": "Distribución detectada",
        "RANGING": "Mercado en rango",
        "CHOPPY": "Alta volatilidad sin dirección",
    }
    logic = logic_map.get(regime, f"Régimen {regime}")

    return json.dumps({"verdict": verdict, "threat": threat, "logic": logic})


def extract_json_from_llm(content: str):
    """Limpia la respuesta de la IA para extraer JSON puro y repara errores comunes de multilínea."""
    # 1. Limpieza básica de Markdown
    content = content.replace("```json", "").replace("```", "").strip()
    
    # 2. Extraer el bloque JSON más grande
    if not (content.startswith("[") or content.startswith("{")):
        start_idx = content.find("[")
        if start_idx == -1: start_idx = content.find("{")
        end_idx = content.rfind("]")
        if end_idx == -1: end_idx = content.rfind("}")
        if start_idx != -1 and end_idx != -1:
            content = content[start_idx:end_idx+1]
        elif start_idx != -1: # Caso especial: JSON truncado al final
            content = content[start_idx:] + ("]" if content[start_idx] == "[" else "}")

    # 3. Reparación de multilínea crítica: 
    # Ollama a veces deja strings sin cerrar si hay un \n real dentro.
    # Reemplazamos newlines literales dentro de lo que parece ser un bloque de texto JSON
    # pero solo si no están seguidos de una estructura de clave JSON
    import re
    # Intentar escapar tímidamente los newlines que rompen strings
    # (Buscamos texto entre comillas que tiene un salto de línea antes de la comilla de cierre)
    # Nota: esto es heurístico.
    lines = content.splitlines()
    repaired_content = ""
    for line in lines:
        repaired_content += line.strip() + " "
    content = repaired_content.strip()

    return content

async def generate_tactical_advice(symbol: str, 
                                 tactical_data: dict, 
                                 current_session: str = "UNKNOWN",
                                 ml_projection: dict = None, 
                                 news: list = None, 
                                 liquidations: list = None, 
                                 economic_events: list = None,
                                 onchain_data: dict = None,
                                 mtf_context: dict = None,
                                 is_absorption_alert: bool = False) -> str:
    """
    v8.5.5-Full: Genera asesoría táctica consolidada multi-temporal con contexto completo.
    """
    global _ai_task_counter, _symbol_tasks, _semantic_cache, _strategic_memo
    signal = tactical_data.get("signal", "NEUTRAL")
    regime = tactical_data.get("regime", "IDLE")
    price = tactical_data.get("price", 0.0)
    
    # [OPTIMIZACIÓN v8.5.3] Filtrado de ruido MTF para estabilidad del Advisor
    # Solo consideramos temporalidades >= 15m para invalidar la caché semántica
    relevant_tfs = ["15m", "1h", "4h", "1d", "1w"]
    mtf_signals = "_".join([f"{k}:{v.get('signal', 'N')}" for k, v in (mtf_context or {}).items() if k in relevant_tfs])
    
    semantic_hash = hashlib.md5(f"{symbol}_{regime}_{signal}_{mtf_signals}_{current_session}".encode()).hexdigest()
    
    if semantic_hash in _semantic_cache:
        cached = _semantic_cache[semantic_hash]
        if abs(cached["price"] - price) / (price or 1) < 0.0005:
            return cached["advice"]

    if not await check_ollama_status():
        return _deterministic_verdict(symbol, tactical_data, current_session)

    # 2. SISTEMA DE UMBRAL POR VOLATILIDAD (0.1% Delta Logic v8.5.3)
    if symbol in _strategic_memo:
        last_p = _strategic_memo[symbol]["price"]
        diff = abs(last_p - price) / (price or 1)
        # Si el precio se mueve < 0.05% y el régimen es el mismo, mantenemos el veredicto
        if diff < 0.0005:
            logger.info(f"[ADVISOR] 🧊 Manteniendo análisis (Precio estable < 0.05% delta).")
            return _strategic_memo[symbol]["advice"]

    if not await check_ollama_status():
        return _deterministic_verdict(symbol, tactical_data, current_session)

    # 3. Construcción de Contexto Multi-Timeframe y SMC (Variables en Vivo)
    mtf_summary = ""
    if mtf_context:
        for tf, data in mtf_context.items():
            sig = data.get('signal', 'NEUTRAL')
            mtf_summary += f"- {tf}: {sig} | Trend: {data.get('trend', 'N/A')}\n"
    else:
        mtf_summary = f"- {tactical_data.get('interval', 'N/A')}: {signal} (Main)"
        
    # Extracción de Métricas SMC Críticas desde tactical_data
    rvol = (tactical_data.get("diagnostic") or {}).get("rvol", 0)
    
    smc_state = tactical_data.get("smc", {})
    obs = smc_state.get("order_blocks", [])
    fvgs = smc_state.get("fvgs", [])
    
    levels = tactical_data.get("key_levels", {})
    resist = levels.get("resistance", "N/A")
    support = levels.get("support", "N/A")

    prompt = f"""[SISTEMA SLINGSHOT v6.0 - PROTOCOLO QUÁNTICO JSON]
ACTIVO: {symbol} | SESIÓN: {current_session} | RÉGIMEN: {regime} | RVOL: {rvol}x
NIVELES CLAVE:  Resistencia: {resist} | Soporte: {support}
SMC STATE: {len(obs)} OBs Activos | {len(fvgs)} FVGs Activos
MTF CONTEXT:
{mtf_summary}
ML/NEWS: {ml_projection.get('prediction', 'N/A') if ml_projection else 'N/A'} | {len(news or [])} items.

TAREA: Emite un veredicto técnico institucional en JSON puro.
REGLAS:
1. VERDICT: "GO" (Hay confluencia real SMC + Liquidez), "AVOID" (Riesgo alto/Veto), "SIDEWAYS" (Rango o Indecisión).
2. THREAT: "LOW", "MEDIUM", "HIGH" (Basado estrictamente en RVOL y News/Régimen).
3. LOGIC: Razón técnica en MAX 5 palabras (ej: "FVG Sweep en 15m").

RESPONDE SOLO EL JSON:
{{"verdict": "...", "threat": "...", "logic": "..."}}"""

    # 3. Gestión de Prioridad y Cola (v5.9.5 MTF Priority)
    
    # Si hay CUALQUIER señal en CUALQUIER temporalidad, subimos prioridad
    has_any_signal = any(d.get('signal', 'NEUTRAL') != 'NEUTRAL' for d in (mtf_context or {}).values()) or signal != "NEUTRAL"
    # [v8.5.4] Gestión de tareas por símbolo: Cancelamos la anterior para evitar atascamiento
    if symbol in _symbol_tasks:
        old_fut = _symbol_tasks[symbol]
        if not old_fut.done():
            old_fut.cancel()
            logger.debug(f"[ADVISOR] 🚫 Cancelada tarea previa de {symbol}")

    priority = 0 # Prioridad máxima para cualquier consulta táctica activa
    
    try:
        # queue_key = f"TACTICAL_{symbol}" # Obsoleto en v8.5.4
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        _ai_task_counter += 1
        _symbol_tasks[symbol] = future # [v8.5.4] Registro de tarea activa para permitir cancelación
        
        await _ai_queue.put((priority, _ai_task_counter, {
            'asset': symbol,
            'prompt': prompt,
            'future': future,
            'format': 'json'
        }))
        
        advice = await future
        _strategic_memo[symbol] = {"price": price, "advice": advice}
        _semantic_cache[semantic_hash] = {"price": price, "advice": advice}
        
        # [OPTIMIZACIÓN v8.5] Persistir en disco
        _save_persistent_cache()
        
        return advice
    except Exception as e:
        logger.error(f"[ADVISOR] ❌ Error en Tactical Advisory ({symbol}): {e}")
        return "ADVISOR LOG: OLLAMA_TIMEOUT. Siguiendo técnica pura."
    finally:
        pass

def _save_persistent_cache():
    try:
        # Limitamos el tamaño de la caché para no saturar el disco (ej: últimas 500 entradas)
        global _semantic_cache
        if len(_semantic_cache) > 500:
            # Eliminar entradas antiguas si es necesario
            keys_to_keep = list(_semantic_cache.keys())[-500:]
            _semantic_cache = {k: _semantic_cache[k] for k in keys_to_keep}

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_semantic_cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[ADVISOR] Error guardando caché en disco: {e}")

async def generate_news_sentiment_batch(headlines: list[str]) -> list[dict]:
    """
    v5.9.3-Batch Master: Analiza múltiples titulares en una sola inferencia.
    NUEVO: Incluye extracción robusta de JSON.
    """
    if not headlines:
        return []
        
    fallback_list = [
        {"sentiment": "NEUTRAL", "score": 0.5, "translated_title": h, "impact": "Análisis pendiente."}
        for h in headlines
    ]
    
    if not await check_ollama_status():
        logger.warning(f"[ADVISOR] ⚠️ News Batch SKIP: Ollama no disponible para {len(headlines)} noticias.")
        return fallback_list

    trinity_context = "Sin datos de mercado recientes."
    try:
        market_states = await store.get_market_states()
        if market_states:
            lines = [f"- {s.get('asset', '?')}: Precio={s.get('current_price', '?')}, Régimen={s.get('regime', 'IDLE')}" for s in market_states]
            trinity_context = "\n".join(lines)
    except Exception as ctx_err:
        logger.warning(f"[ADVISOR] Context fetch error: {ctx_err}")

    headlines_formatted = "\n".join([f"{i+1}. {h}" for i, h in enumerate(headlines)])

    prompt = f"""Eres un Analista Senior de Fondos de Cobertura (Top-Tier Hedge Fund).
Tu objetivo es evaluar el impacto REAL de estas noticias en el precio de las criptomonedas.

ESTADO ACTUAL DEL MERCADO:
{trinity_context}

TITULARES A ANALIZAR:
{headlines_formatted}

INSTRUCCIONES CRÍTICAS:
1. TRADUCCIÓN: Traduce al español de forma impecable y trader.
2. SENTIMIENTO: Escoge BULLISH, BEARISH o NEUTRAL. 
   - EVITA el sentimiento NEUTRAL a menos que la noticia sea Tier 3. 
   - Si la noticia implica dinero, regulaciones, adopción o grandes empresas, DEBE ser Bullish o Bearish.
3. PRICED-IN (v6.5): 
   - Si el precio ya se movió >1% en la dirección de la noticia en los últimos 5 mins, marca IMPACT="BAJO / DESCONTADO".
4. SCORE: 
   - 0.0 - 0.3: Pánico/Bearish fuerte.
   - 0.7 - 1.0: Euforia/Bullish fuerte.
   - 0.4 - 0.6: Solo para noticias burocráticas sin impacto.
5. IMPACTO: Explica POR QUÉ esto moverá el precio hoy. Sé agresivo en tu análisis.

Responde ÚNICAMENTE con un ARRAY JSON de objetos. NO incluyas markdown (```) ni texto extra.
Estructura:
[
  {{"translated_title": "...", "sentiment": "...", "score": 0.5, "impact": "..."}}
]"""

    try:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        global _ai_task_counter
        _ai_task_counter += 1

        await _ai_queue.put((5, _ai_task_counter, {
            'asset': 'NEWS_BATCH',
            'prompt': prompt,
            'future': future,
            'format': 'json'
        }))
        
        raw_content = await future
        clean_content = extract_json_from_llm(raw_content)
        
        try:
            results = json.loads(clean_content)
            
            # Si Ollama devuelve un objeto con una clave "news" o similar
            if isinstance(results, dict):
                for key in ["news", "results", "analysis", "batch"]:
                    if key in results and isinstance(results[key], list):
                        results = results[key]
                        break
            
            if not isinstance(results, list):
                # Caso extremo: si es un dict y no tiene la lista, intentar corregir
                if isinstance(results, dict) and len(results) > 0:
                    results = [results] # Convertir un solo objeto en lista
                else:
                    # Si es {} o algo vacío, no lanzamos error, usamos fallback silenciosamente
                    logger.warning(f"[ADVISOR] ⚠️ News Batch vacío o malformado ({clean_content[:20]}). Usando fallback.")
                    return fallback_list
                
            for i, res in enumerate(results):
                if "sentiment" not in res: res["sentiment"] = "NEUTRAL"
                if "score" not in res: res["score"] = 0.5
                if "impact" not in res: res["impact"] = "Procesado en lote."
                if ("translated_title" not in res or not res["translated_title"]) and i < len(headlines): 
                    res["translated_title"] = headlines[i]
                
            return results
            
        except json.JSONDecodeError as jde:
            logger.error(f"[ADVISOR] ❌ JSON Decode Fail in Batch: {jde} | First 100 chars: {clean_content[:100]}")
            return fallback_list
            
    except Exception as e:
        logger.error(f"[ADVISOR] ❌ News Batch Fatal Error: {e}")
        return fallback_list
        return fallback_list


async def generate_scanner_hypotheses_batch(opportunities: list[dict]) -> list[dict]:
    """
    v20.0-Apex: Genera hipótesis narrativas institucionales para el Top 3 de oportunidades
    del escáner en una sola inferencia de alto rendimiento.
    """
    if not opportunities:
        return []

    top_opps = opportunities[:3]
    opp_summaries = []
    for i, o in enumerate(top_opps):
        opp_summaries.append(
            f"{i+1}. {o.get('asset')} ({o.get('direction')}) @ ${o.get('price')} | Score: {o.get('confluence_score')}% | R:R: {o.get('rr_ratio_tp3')}:1 | SL: ${o.get('stop_loss')} | TP1: ${o.get('tp1')}"
        )

    prompt = f"""Eres el Asesor Cuántico Senior de Slingshot Trading.
Analiza las siguientes oportunidades institucionales y genera una hipótesis concisa para cada una.

OPORTUNIDADES DETECTADAS:
{chr(10).join(opp_summaries)}

REGLAS:
1. Genera para cada oportunidad una 'hypothesis' técnica (máximo 2 oraciones) explicando la confluencia institucional.
2. Define un 'verdict' ("GO", "AVOID" o "SIDEWAYS").
3. Define un 'threat' ("LOW", "MEDIUM", "HIGH").

Responde ÚNICAMENTE con un array JSON de objetos:
[
  {{"asset": "...", "hypothesis": "...", "verdict": "GO", "threat": "LOW"}}
]"""

    try:
        if not await check_ollama_status():
            return [
                {
                    "asset": o.get("asset"),
                    "hypothesis": f"Estructura técnica {o.get('direction')} con confluencia {o.get('confluence_score')}%. Soporte en zona OTE institucional.",
                    "verdict": "GO" if o.get("confluence_score", 0) >= 65 else "SIDEWAYS",
                    "threat": "LOW" if o.get("confluence_score", 0) >= 70 else "MEDIUM"
                }
                for o in top_opps
            ]

        # Asegurar que los workers estén corriendo
        start_ai_worker()

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        global _ai_task_counter
        _ai_task_counter += 1

        await _ai_queue.put((2, _ai_task_counter, {
            'asset': 'SCANNER_HYPOTHESIS_BATCH',
            'prompt': prompt,
            'future': future,
            'format': 'json'
        }))

        raw_content = await asyncio.wait_for(future, timeout=2.5)
        clean_content = extract_json_from_llm(raw_content)
        parsed = json.loads(clean_content)

        if isinstance(parsed, dict):
            for k in ["hypotheses", "results", "opportunities", "data"]:
                if k in parsed and isinstance(parsed[k], list):
                    parsed = parsed[k]
                    break
        if not isinstance(parsed, list):
            parsed = [parsed] if isinstance(parsed, dict) else []

        return parsed
    except Exception as e:
        logger.warning(f"[ADVISOR] Fallback en Scanner Hypotheses Batch: {e}")
        return [
            {
                "asset": o.get("asset"),
                "hypothesis": f"Setup {o.get('direction')} validado por confluencia cuantitativa ({o.get('confluence_score')}%).",
                "verdict": "GO" if o.get("confluence_score", 0) >= 60 else "SIDEWAYS",
                "threat": "LOW"
            }
            for o in top_opps
        ]

async def generate_news_sentiment(headline: str) -> dict:
    """Wrapper para compatibilidad."""
    batch = await generate_news_sentiment_batch([headline])
    return batch[0] if batch else {"sentiment": "NEUTRAL", "score": 0.5, "translated_title": headline, "impact": "Error en lote."}

_ai_workers_started = False

async def ai_worker():
    """Worker singleton que procesa la cola de IA de forma secuencial y sin rate limits."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            try:
                priority, count, task = await _ai_queue.get()
            except Exception:
                await asyncio.sleep(0.5)
                continue

            if task.get('future') is None or task['future'].cancelled():
                _ai_queue.task_done()
                continue

            try:
                asset_name = task.get('asset', 'UNKNOWN')
                fallback_content = _deterministic_verdict(asset_name, {})

                if settings.OPENROUTER_API_KEY:
                    # RUTA CLOUD DEEP REASONING: OpenRouter
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://slingshot-trading.local",
                        "X-Title": "Slingshot Institutional Trading",
                        "Content-Type": "application/json"
                    }
                    openrouter_payload = {
                        "model": settings.OPENROUTER_MODEL or "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                        "messages": [{"role": "user", "content": task['prompt']}],
                        "temperature": 0.2
                    }
                    if task.get('format') == 'json':
                        openrouter_payload["response_format"] = {"type": "json_object"}
                    
                    response = None
                    try:
                        response = await client.post(url, json=openrouter_payload, headers=headers)
                    except Exception as oe:
                        logger.debug(f"[AI_WORKER] Error de conexión con OpenRouter: {oe}")
                    
                    if task['future'].cancelled():
                        continue
                        
                    if response and response.status_code == 200:
                        result = response.json()
                        if "choices" in result and len(result["choices"]) > 0:
                            content = result["choices"][0]["message"]["content"].strip()
                            logger.info(f"[AI_WORKER] 🧠 Respuesta de OpenRouter para {asset_name} ({len(content)} bytes)")
                            if not task['future'].done():
                                task['future'].set_result(content)
                        else:
                            if not task['future'].done():
                                task['future'].set_result(fallback_content)
                    else:
                        status_code = response.status_code if response else "Timeout"
                        logger.warning(f"[AI_WORKER] ⚠️ OpenRouter {status_code} para {asset_name} — Aplicando veredicto determinístico.")
                        if not task['future'].done():
                            task['future'].set_result(fallback_content)
                    
                    # Espaciado de cortesía para no saturar el Rate Limit del Free Tier
                    await asyncio.sleep(0.4)

                elif settings.GROQ_API_KEY:
                    # RUTA CLOUD: Groq API
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    groq_payload = {
                        "model": "qwen/qwen3.6-27b",
                        "messages": [{"role": "user", "content": task['prompt']}],
                        "temperature": 0.2
                    }
                    if task.get('format') == 'json':
                        groq_payload["response_format"] = {"type": "json_object"}
                    
                    response = None
                    try:
                        response = await client.post(url, json=groq_payload, headers=headers)
                    except Exception as ge:
                        logger.debug(f"[AI_WORKER] Error conectando a Groq: {ge}")
                    
                    if task['future'].cancelled():
                        continue
                        
                    if response and response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"].strip()
                        if not task['future'].done():
                            task['future'].set_result(content)
                    else:
                        if not task['future'].done():
                            task['future'].set_result(fallback_content)
                    await asyncio.sleep(0.2)

                elif settings.GEMINI_API_KEY:
                    # RUTA CLOUD: Gemini API
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                    gemini_payload = {
                        "contents": [{"parts": [{"text": task['prompt']}]}]
                    }
                    if task.get('format') == 'json':
                        gemini_payload['generationConfig'] = {"responseMimeType": "application/json"}
                    
                    response = None
                    try:
                        response = await client.post(url, json=gemini_payload)
                    except Exception as gme:
                        logger.debug(f"[AI_WORKER] Error conectando a Gemini: {gme}")
                    
                    if task['future'].cancelled():
                        continue
                        
                    if response and response.status_code == 200:
                        result = response.json()
                        try:
                            content = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                        except (KeyError, IndexError):
                            content = fallback_content
                        if not task['future'].done():
                            task['future'].set_result(content)
                    else:
                        if not task['future'].done():
                            task['future'].set_result(fallback_content)
                    await asyncio.sleep(0.2)

                else:
                    # RUTA LOCAL: Ollama local
                    payload = {
                        "model": DEFAULT_MODEL,
                        "prompt": task['prompt'],
                        "stream": False,
                        "options": {"temperature": 0.3}
                    }
                    if task.get('format') == 'json':
                        payload['format'] = 'json'

                    response = None
                    try:
                        response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
                    except Exception as ole:
                        logger.debug(f"[AI_WORKER] Error conectando a Ollama: {ole}")
                    
                    if task['future'].cancelled():
                        continue

                    if response and response.status_code == 200:
                        result = response.json()
                        content = result.get("response", "").strip() or fallback_content
                        if not task['future'].done():
                            task['future'].set_result(content)
                    else:
                        if not task['future'].done():
                            task['future'].set_result(fallback_content)

            except Exception as e:
                logger.debug(f"[AI_WORKER] Excepción controlada en worker: {e}")
                if task.get('future') and not task['future'].done() and not task['future'].cancelled():
                    task['future'].set_result(_deterministic_verdict(task.get('asset', 'UNKNOWN'), {}))
            finally:
                asset = task.get('asset')
                if asset in _symbol_tasks and _symbol_tasks[asset] == task.get('future'):
                    del _symbol_tasks[asset]
                _ai_queue.task_done()

def start_ai_worker():
    """Inicia el worker singleton y monitor de salud sin duplicar hilos."""
    global _ai_workers_started
    if _ai_workers_started:
        return
    _ai_workers_started = True
    asyncio.create_task(ai_worker())
    asyncio.create_task(background_ollama_check())

async def background_ollama_check():
    """Mantiene la caché actualizada sin fugas de excepciones."""
    while True:
        try:
            await check_ollama_status()
        except Exception as e:
            logger.debug(f"[OLLAMA_CHECK] Error verificando estado: {e}")
        await asyncio.sleep(60)

