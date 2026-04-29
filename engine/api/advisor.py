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
    """v5.9.4-Resilience: Salto agresivo si ya está confirmado online en la sesión."""
    global _ollama_cache
    
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
        return "ADVISOR: OLLAMA_OFFLINE. Operando bajo parámetros técnicos puros."

    # 2. SISTEMA DE UMBRAL POR VOLATILIDAD (0.1% Delta Logic v8.5.3)
    if symbol in _strategic_memo:
        last_p = _strategic_memo[symbol]["price"]
        diff = abs(last_p - price) / (price or 1)
        # Si el precio se mueve < 0.05% y el régimen es el mismo, mantenemos el veredicto
        if diff < 0.0005:
            logger.info(f"[ADVISOR] 🧊 Manteniendo análisis (Precio estable < 0.05% delta).")
            return _strategic_memo[symbol]["advice"]

    if not await check_ollama_status():
        return json.dumps({"verdict": "SIDEWAYS", "logic": "OLLAMA_OFFLINE", "threat": "LOW"})

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
                    raise ValueError(f"LLM response is not a JSON list or valid object. Content: {clean_content[:100]}...")
                
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
        logger.error(f"[ADVISOR] ❌ News Batch Error: {e}")
        return fallback_list


async def generate_news_sentiment(headline: str) -> dict:
    """Wrapper para compatibilidad."""
    batch = await generate_news_sentiment_batch([headline])
    return batch[0] if batch else {"sentiment": "NEUTRAL", "score": 0.5, "translated_title": headline, "impact": "Error en lote."}

async def ai_worker():
    """Worker que procesa la cola de IA."""
    async with httpx.AsyncClient(timeout=90.0) as client:
        while True:
            priority, count, task = await _ai_queue.get()
            if task['future'].cancelled():
                _ai_queue.task_done()
                continue

            try:
                payload = {
                    "model": DEFAULT_MODEL,
                    "prompt": task['prompt'],
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
                if task.get('format') == 'json':
                    payload['format'] = 'json'

                # Petición a Ollama con posibilidad de cancelación
                response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
                
                if task['future'].cancelled():
                    _ai_queue.task_done()
                    continue

                if response.status_code == 200:
                    result = response.json()
                    content = result.get("response", "").strip()
                    if not content:
                        logger.warning(f"[AI_WORKER] Ollama devolvió respuesta vacía para {task.get('asset')}")
                        content = json.dumps({"verdict": "SIDEWAYS", "logic": "EMPTY_RESPONSE", "threat": "LOW"})
                    
                    logger.info(f"[AI_WORKER] ✅ Respuesta recibida para {task.get('asset')} ({len(content)} bytes)")
                    if not task['future'].done():
                        task['future'].set_result(content)
                else:
                    logger.error(f"[AI_WORKER] ❌ Error de Ollama: {response.status_code} para {task.get('asset')}")
                    if not task['future'].done():
                        task['future'].set_exception(Exception(f"Ollama error: {response.status_code}"))
            except Exception as e:
                if not task['future'].done():
                    task['future'].set_exception(e)
            finally:
                # Limpiar rastreador de símbolos si esta era la tarea activa
                asset = task.get('asset')
                if asset in _symbol_tasks and _symbol_tasks[asset] == task['future']:
                    del _symbol_tasks[asset]
                _ai_queue.task_done()

def start_ai_worker():
    global _ai_worker_task
    # [v6.0.1] Paralelización del Advisor: 3 workers para evitar cuellos de botella
    for _ in range(3):
        asyncio.create_task(ai_worker())
    asyncio.create_task(background_ollama_check())

async def background_ollama_check():
    """Mantiene la caché actualizada."""
    while True:
        await check_ollama_status()
        await asyncio.sleep(60)

