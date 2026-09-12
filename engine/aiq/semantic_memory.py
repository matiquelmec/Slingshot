"""
engine/aiq/semantic_memory.py — Memoria Semántica Vectorial con nemotron-3-embed-1b
===================================================================================
Permite al Consorcio Agéntico indexar eventos de mercado, fallas previas y trampas
institucionales mediante representaciones vectoriales para búsqueda por similitud en milisegundos.
"""

import httpx
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from engine.core.logger import logger
from engine.aiq.config import aiq_settings


class AIQSemanticMemory:
    """
    Gestor de Memoria Semántica Vectorial (NVIDIA nemotron-3-embed-1b).
    """

    def __init__(self):
        self.api_key = aiq_settings.NVIDIA_NIM_API_KEY
        self.endpoint_url = f"{aiq_settings.NVIDIA_NIM_BASE_URL}/embeddings"
        self.model = aiq_settings.MODEL_EMBEDDINGS
        # Cache en memoria para almacenamiento rápido de vectores
        self._memory_entries: List[Dict[str, Any]] = []

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Obtiene el vector de embedding desde el endpoint de NVIDIA NIM.
        Fallback a vector sintético determinístico si no hay conexión externa.
        """
        if not self.api_key or not self.api_key.startswith("nvapi-"):
            return self._deterministic_hash_vector(text)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": [text],
            "model": self.model,
            "encoding_format": "float"
        }

        try:
            async with httpx.AsyncClient(timeout=aiq_settings.TIMEOUT_SECONDS_FAST) as client:
                res = await client.post(self.endpoint_url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["data"][0]["embedding"]
                else:
                    logger.debug(f"[SEMANTIC MEMORY] Status {res.status_code} en embeddings NIM. Usando fallback.")
                    return self._deterministic_hash_vector(text)
        except Exception as e:
            logger.debug(f"[SEMANTIC MEMORY] Error en llamada NIM: {e}. Usando fallback.")
            return self._deterministic_hash_vector(text)

    def _deterministic_hash_vector(self, text: str, dim: int = 128) -> List[float]:
        """Generador determinístico pseudo-aleatorio para pruebas sin conexión."""
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(dim):
            byte_val = h[i % len(h)]
            vec.append((byte_val / 255.0) * 2.0 - 1.0)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = (np.array(vec) / norm).tolist()
        return vec

    async def store_event(self, event_id: str, description: str, metadata: Dict[str, Any]):
        """Almacena un evento o lección aprendida indexado por su vector semántico."""
        vector = await self.generate_embedding(description)
        self._memory_entries.append({
            "id": event_id,
            "description": description,
            "metadata": metadata,
            "vector": vector,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    def find_similar_events(self, query_vector: List[float], top_k: int = 3, min_similarity: float = 0.70) -> List[Dict[str, Any]]:
        """Busca eventos semánticamente análogos mediante similitud coseno."""
        if not self._memory_entries:
            return []

        q_vec = np.array(query_vector)
        results = []
        for entry in self._memory_entries:
            e_vec = np.array(entry["vector"])
            dot = float(np.dot(q_vec, e_vec))
            if dot >= min_similarity:
                results.append({
                    "id": entry["id"],
                    "description": entry["description"],
                    "similarity": round(dot, 4),
                    "metadata": entry["metadata"]
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


aiq_semantic_memory = AIQSemanticMemory()
