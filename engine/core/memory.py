import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from engine.core.logger import logger
from engine.api.config import settings

class BlackBox:
    """
    v13.0 SOVEREIGN INTELLIGENCE — Black Box (Error Memory).
    Registra huellas digitales de trades y bloquea patrones de pérdida recurrentes.
    """
    
    def __init__(self, storage_path: str = "data/blackbox.json"):
        self.storage_path = storage_path
        self.memory = self._load_memory()
        logger.info(f"🧠 [BLACKBOX] Memoria institucional cargada: {len(self.memory)} registros.")

    def _load_memory(self) -> list:
        """Carga la memoria desde el disco."""
        if not os.path.exists(self.storage_path):
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            return []
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ [BLACKBOX] Error cargando memoria: {e}")
            return []

    def _save_memory(self):
        """Persiste la memoria en el disco."""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logger.error(f"❌ [BLACKBOX] Error guardando memoria: {e}")

    def record_trade(self, signal: dict, result: str):
        """
        Registra un trade completado con su huella digital.
        result: 'STOP_LOSS' o 'TAKE_PROFIT'
        """
        fingerprint = self.extract_fingerprint(signal)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": signal.get("asset", "UNKNOWN"),
            "signal_type": signal.get("signal_type", signal.get("type", "LONG")),
            "result": result,
            "confluence_score": signal.get("confluence", {}).get("score", 0),
            "fingerprint": fingerprint
        }
        self.memory.append(entry)
        
        # Mantener solo los últimos 200 registros para evitar degradación de performance
        if len(self.memory) > 200:
            self.memory = self.memory[-200:]
            
        self._save_memory()
        logger.info(f"📦 [BLACKBOX] Trade registrado ({result}): {entry['asset']} {entry['signal_type']}")

    def extract_fingerprint(self, signal: dict) -> dict:
        """Extrae las características del mercado que definen la huella del trade."""
        conf = signal.get("confluence", {})
        
        # Mapear checklist a booleanos/valores simples
        checklist = conf.get("checklist", [])
        def get_status(factor):
            for item in checklist:
                if item["factor"] == factor:
                    return item["status"]
            return "UNKNOWN"

        return {
            "regime": signal.get("regime", "UNKNOWN"),
            "rvol": float(conf.get("rvol", 1.0)),
            "has_ob": get_status("Zonas POI") in ("CONFIRMADO", "PARCIAL"),
            "has_sweep": "Sweep: True" in str(get_status("Liquidez")),
            "session": "UNKNOWN", # Debería inyectarse desde el contexto
            "absorption_score": float(signal.get("absorption_score", 0)),
            "is_in_ote": signal.get("fib_ote", {}).get("is_in_ote", False)
        }

    def check_setup(self, current_signal: dict) -> dict:
        """
        Compara el setup actual contra la memoria de errores.
        Retorna: {"match": bool, "confidence": float, "reason": str}
        """
        if not self.memory:
            return {"match": False, "confidence": 1.0, "reason": "No hay memoria acumulada"}

        current_fp = self.extract_fingerprint(current_signal)
        asset = current_signal.get("asset", "UNKNOWN")
        sig_type = current_signal.get("signal_type", current_signal.get("type", "LONG"))
        
        # Filtrar solo trades perdedores del mismo activo
        failures = [m for m in self.memory if m["result"] == "STOP_LOSS" and m.get("asset") == asset]
        
        if not failures:
            return {"match": False, "confidence": 1.0, "reason": f"Sin historial de pérdidas para {asset}"}

        max_similarity = 0.0
        worst_match_reason = ""

        for fail in failures:
            similarity = self._calculate_similarity(current_fp, fail["fingerprint"])
            if similarity > max_similarity:
                max_similarity = similarity
                worst_match_reason = f"Patrón similar a pérdida en {fail['timestamp']} (Sim: {similarity:.1%})"

        # Umbral institucional: 85% de similitud para veto
        is_match = max_similarity >= 0.85
        confidence = 1.0 - max_similarity

        return {
            "match": is_match,
            "similarity": max_similarity,
            "confidence": confidence,
            "reason": worst_match_reason if is_match else "Patrón no identificado como error previo"
        }

    def _calculate_similarity(self, fp1: dict, fp2: dict) -> float:
        """Calcula la similitud entre dos huellas (0.0 a 1.0)."""
        weights = {
            "regime": 0.3,
            "has_ob": 0.2,
            "has_sweep": 0.2,
            "is_in_ote": 0.1,
            "rvol": 0.1,
            "absorption_score": 0.1
        }
        
        score = 0.0
        total_weight = sum(weights.values())

        # Categorías exactas
        if fp1.get("regime") == fp2.get("regime"): score += weights["regime"]
        if fp1.get("has_ob") == fp2.get("has_ob"): score += weights["has_ob"]
        if fp1.get("has_sweep") == fp2.get("has_sweep"): score += weights["has_sweep"]
        if fp1.get("is_in_ote") == fp2.get("is_in_ote"): score += weights["is_in_ote"]

        # Numéricos (Similitud relativa)
        def num_sim(v1, v2, max_diff):
            diff = abs(v1 - v2)
            return max(0, 1.0 - diff / max_diff)

        score += weights["rvol"] * num_sim(fp1.get("rvol", 1.0), fp2.get("rvol", 1.0), 2.0)
        score += weights["absorption_score"] * num_sim(fp1.get("absorption_score", 0), fp2.get("absorption_score", 0), 100)

        return score / total_weight

# Instancia global
blackbox = BlackBox()
