"""
engine/execution/delta_executor.py — v10.2.0 (DELTA Orchestrator)
============================================================
Módulo encargado de la fragmentación de órdenes (60/20/20) y envío coordinado.
"""
from typing import Dict, Any, List
from engine.core.logger import logger

class DeltaOrchestrator:
    """
    EL MAESTRO DE ORQUESTACIÓN.
    Transforma una señal simple en una Grilla Asimétrica 60/20/20.
    """
    
    @staticmethod
    def fragment_order(signal: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Divide la posición total en 3 tramos institucionales basándose en la data de riesgo.
        """
        total_size = signal.get("position_size_usdt", signal.get("position_size", 0))
        tp1_vol_pct = signal.get("tp1_vol_pct", 0.50)
        
        # Fragmentación Alpha Maximizer 50/30/20 (v24.0 APEX ALPHA)
        # Tramo 1: 50% (Peaje / BE Trigger @ +1.5R)
        # Tramo 2: 30% (Lock Profit @ +3.0R con SL a +2.0R)
        # Tramo 3: 20% (Moonbag / Home Run @ +5.0R a +8.0R con Trailing Ratchet 70%)
        
        vol_tp1 = total_size * tp1_vol_pct
        remaining = total_size - vol_tp1
        vol_tp2 = remaining * 0.60  # 30% del total
        vol_tp3 = remaining - vol_tp2  # 20% del total (Home Run)
        
        fragments = [
            {
                "id": "TP1_PEAJE",
                "volume_usdt": round(vol_tp1, 2),
                "tp_price": signal.get("tp1"),
                "sl_price": signal.get("stop_loss"),
                "is_entry_risk": True,
                "label": f"Tramo 1 ({int(tp1_vol_pct*100)}%)"
            },
            {
                "id": "TP2_LOCK",
                "volume_usdt": round(vol_tp2, 2),
                "tp_price": signal.get("tp2"),
                "sl_price": signal.get("stop_loss"),
                "is_entry_risk": False,
                "label": "Tramo 2 (30%)"
            },
            {
                "id": "TP3_HOME_RUN",
                "volume_usdt": round(vol_tp3, 2),
                "tp_price": signal.get("tp3"),
                "sl_price": signal.get("stop_loss"),
                "is_entry_risk": False,
                "label": "Tramo 3 (20%)"
            }
        ]
        
        logger.info(f"📐 [DELTA] Grilla {signal.get('asset')} calculada: {fragments[0]['label']} -> {fragments[2]['label']}")
        return fragments
