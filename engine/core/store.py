from engine.core.logger import logger
import asyncio
from collections import deque
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import uuid

class MemoryStore:
    """
    Motor de Persistencia Atómica y Efímera Slingshot v3.0.
    Utiliza buffers circulares para garantizar un uso de RAM constante y predecible.
    """
    def __init__(self, max_history: int = 1000, max_signals: int = 200):
        # Estados actuales por activo (Radar)
        self._market_states: Dict[str, Dict[str, Any]] = {}

        # Caché de Sesgo HTF Fractal (v10.0 Sovereign)
        self._htf_biases: Dict[str, Any] = {}

        # Caché de Snapshots Tácticos por Intervalo (v5.9.5 MTF Master)
        self._tactical_snapshots: Dict[str, Dict[str, Any]] = {}
        
        # Buffers circulares para señales (Evita crecimiento infinito)
        self._signal_events = deque(maxlen=max_signals)
        
        # Candlestick Cache (Para hot-start de nuevos suscriptores)
        self._candle_history: Dict[str, deque] = {}
        self._max_history = max_history
        
        # Zonas de Liquidación (Trapped Money)
        self._liquidation_clusters: Dict[str, List[Dict[str, Any]]] = {}
        
        # Buffer circular para noticias
        self._news_items = deque(maxlen=50)

        # Buffer circular para calendario económico
        self._economic_events = deque(maxlen=100)
        
        # Caché de Análisis del Advisor (LLM)
        self._advisor_advice: Dict[str, Dict[str, Any]] = {}
        
        # Lock de concurrencia para evitar condiciones de carrera
        self._lock = asyncio.Lock()

    async def update_market_state(self, asset: str, data: Dict[str, Any]):
        """Actualiza el radar en tiempo real."""
        async with self._lock:
            if asset not in self._market_states:
                self._market_states[asset] = {}
            
            self._market_states[asset].update(data)
            self._market_states[asset]["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._market_states[asset]["asset"] = asset

    async def save_tactical_snapshot(self, asset: str, interval: str, data: Dict[str, Any]):
        """Persiste el estado técnico de un intervalo específico para análisis MTF."""
        key = f"{asset}:{interval}"
        async with self._lock:
            self._tactical_snapshots[key] = data.copy()
            self._tactical_snapshots[key]["last_updated"] = datetime.now(timezone.utc).isoformat()

    async def get_mtf_context(self, asset: str) -> Dict[str, Dict[str, Any]]:
        """Recupera todos los intervalos disponibles para un activo."""
        async with self._lock:
            context = {}
            for interval in ["1m", "5m", "15m", "1h", "4h", "1d"]:
                key = f"{asset}:{interval}"
                if key in self._tactical_snapshots:
                    context[interval] = self._tactical_snapshots[key]
            return context

    async def save_candle(self, asset: str, interval: str, candle_data: Dict[str, Any]):
        """Guarda la vela en un buffer circular específico para el activo."""
        key = f"{asset}:{interval}"
        async with self._lock:
            if key not in self._candle_history:
                self._candle_history[key] = deque(maxlen=self._max_history)
            self._candle_history[key].append(candle_data)

    async def get_history(self, asset: str, interval: str) -> List[Dict[str, Any]]:
        """Recupera el historial circular para sincronización inicial."""
        key = f"{asset}:{interval}"
        async with self._lock:
            history = self._candle_history.get(key)
            return list(history) if history is not None else []

    async def get_market_states(self) -> List[Dict[str, Any]]:
        """Retorna el estado de todos los activos para el Radar."""
        async with self._lock:
            return list(self._market_states.values())

    async def save_signal(self, signal_data: Dict[str, Any]):
        """
        Persiste una señal o la evoluciona si ya existe.
        Mantiene el buffer circular de 200 señales para evitar saturación.
        """
        async with self._lock:
            if "id" not in signal_data:
                signal_data["id"] = str(uuid.uuid4())
                if "created_at" not in signal_data:
                    signal_data["created_at"] = datetime.now(timezone.utc).isoformat()
            
            # Evolución de señal: Desduplicación por "Punto de Interés" (POI)
            existing = None
            new_price = float(signal_data.get("price", 0))
            for s in self._signal_events:
                old_price = float(s.get("price", 0))
                # Consideramos que es la misma señal si es el mismo activo, dirección y el precio de entrada es idéntico o casi idéntico
                if (s["asset"] == signal_data["asset"] and 
                    s.get("signal_type") == signal_data.get("signal_type") and 
                    abs(old_price - new_price) < 0.000001):
                    existing = s
                    break
            
            if existing:
                existing.update(signal_data)
            else:
                self._signal_events.append(signal_data)
        return signal_data

    async def get_signals(self, asset: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Busca señales en el buffer circular con filtros."""
        async with self._lock:
            filtered = list(self._signal_events)
            if asset:
                filtered = [s for s in filtered if s["asset"] == asset]
            if status:
                filtered = [s for s in filtered if s.get("status") == status]
            return filtered

    async def save_news(self, news_item: Dict[str, Any]):
        """Guarda una noticia en el buffer circular con deduplicación estricta v5.9.6."""
        async with self._lock:
            # Normalizar para comparación (lowercase y sin espacios extra)
            new_title = news_item.get("title", "").strip().lower()
            if not new_title: return
            
            # Evitar duplicados por título (Case-Insensitive)
            existing_titles = [n.get("title", "").strip().lower() for n in self._news_items]
            if new_title not in existing_titles:
                self._news_items.append(news_item)

    async def get_news(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Recupera las últimas noticias del buffer."""
        async with self._lock:
            news_list = list(self._news_items)
            news_list = news_list[::-1]
            if limit:
                return news_list[:limit]
            return news_list

    async def save_economic_events(self, events: List[Dict[str, Any]]):
        """Guarda una lista de eventos económicos en el buffer circular."""
        async with self._lock:
            # Reemplazamos los eventos actuales por los nuevos (refresco total de la semana)
            self._economic_events.clear()
            self._economic_events.extend(events)

    async def get_economic_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Recupera los eventos económicos del buffer."""
        async with self._lock:
            events = list(self._economic_events)
            if limit:
                return events[:limit]
            return events

    async def update_liquidation_clusters(self, asset: str, clusters: List[Dict[str, Any]]):
        """Actualiza el mapa de calor de liquidaciones para un activo."""
        async with self._lock:
            self._liquidation_clusters[asset] = clusters

    async def get_liquidation_clusters(self, asset: str) -> List[Dict[str, Any]]:
        """Recupera las zonas de liquidación para un activo."""
        async with self._lock:
            return self._liquidation_clusters.get(asset, [])

    async def save_advisor_advice(self, asset: str, advice_data: Dict[str, Any]):
        """Guarda el análisis del Advisor en el caché local."""
        async with self._lock:
            self._advisor_advice[asset] = advice_data

    async def flush_symbol(self, asset: str):
        """Limpia el estado de un símbolo específico para evitar contaminación cruzada (v5.7.155 Master Gold)."""
        async with self._lock:
            if asset in self._market_states:
                del self._market_states[asset]
            if asset in self._advisor_advice:
                del self._advisor_advice[asset]
            if asset in self._liquidation_clusters:
                del self._liquidation_clusters[asset]
            
            # Limpiar historiales de velas
            keys_to_del = [k for k in self._candle_history.keys() if k.startswith(f"{asset}:")]
            for k in keys_to_del:
                del self._candle_history[k]
                
            logger.info(f"🧹 [MemoryStore] Flush de seguridad completado para {asset}.")

    async def get_advisor_advice(self, asset: str) -> Optional[Dict[str, Any]]:
        """Recupera el último análisis del Advisor para un activo."""
        async with self._lock:
            return self._advisor_advice.get(asset)

    async def save_htf_bias(self, asset: str, bias_data: Any):
        """Guarda el sesgo HTF centralizado."""
        async with self._lock:
            self._htf_biases[asset] = bias_data

    async def get_htf_bias(self, asset: str) -> Optional[Any]:
        """Recupera el sesgo HTF centralizado."""
        async with self._lock:
            return self._htf_biases.get(asset)

    async def clear_all(self):
        """Wipe total (Reseteo de sistema)."""
        async with self._lock:
            self._market_states.clear()
            self._signal_events.clear()
            self._candle_history.clear()
            self._news_items.clear()
            self._liquidation_clusters.clear()
            self._advisor_advice.clear()
            logger.info("🧱 [MemoryStore] RAM Liberada. Estado 100% efímero reiniciado.")

# Singleton Global para todo el proceso
store = MemoryStore()
