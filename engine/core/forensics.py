import json
import os
from datetime import datetime, timezone
from engine.core.logger import logger

def save_forensic_snapshot(asset: str, signal: dict, full_context: dict):
    """
    Automated Forensics v5.0 (Nivel de Madurez 5).
    Genera un snapshot completo del estado de la RAM y confluencias en el momento de la señal.
    Permite auditoría posterior 'frame by frame' de por qué se tomó una decisión.
    """
    try:
        # 1. Preparar directorio de auditoría
        base_dir = "forensics"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        # 2. Construir Snapshot
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        direction = str(signal.get("signal_type", signal.get("type", "UNKNOWN"))).upper()
        filename = f"{timestamp}_{asset}_{direction}.json"
        filepath = os.path.join(base_dir, filename)

        snapshot = {
            "metadata": {
                "asset": asset,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "system_version": "Slingshot v4.7.1 Platinum",
                "maturity_level": 5
            },
            "signal": signal,
            "context": full_context
        }

        # 3. Persistir a disco
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, default=str)

        logger.info(f"📁 [FORENSICS] Snapshot de auditoría generado: {filename}")
        
    except Exception as e:
        logger.error(f"❌ [FORENSICS] Error guardando snapshot: {e}")
