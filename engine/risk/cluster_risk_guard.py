"""
engine/risk/cluster_risk_guard.py — v26.0 (CLUSTER FORTRESS)
=============================================================================
Responsabilidad: Gestión de Riesgo por Clusters de Correlación Cruzada.
Previene la sobreexposición sistémica y stopouts simultáneos ante caídas
correlacionadas del mercado cripto o índices TradFi.
"""
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from engine.core.logger import logger

class ClusterRiskGuard:
    """
    Guardián Institucional de Riesgo por Clusters de Correlación.
    
    Reglas Institucionales:
    1. Máximo 2 operaciones con riesgo flotante en el mismo cluster correlacionado (ρ >= 0.75).
    2. Las posiciones en Breakeven (Fast BE / riesgo $0.00) liberan su cupo de cluster.
    3. Activos descorrelacionados (Oro 1H, Forex, Índices) operan en clusters independientes.
    """
    
    DEFAULT_CORRELATION_THRESHOLD = 0.75
    MAX_UNPROTECTED_PER_CLUSTER = 2
    
    # Clusters Estructurales de Fallback (cuando no hay buffer de precios suficiente)
    STRUCTURAL_CLUSTERS = {
        "CRYPTO_MAJORS": ["BTC", "BTCUSDT", "ETH", "ETHUSDT"],
        "CRYPTO_HIGH_BETA": ["SOL", "SOLUSDT", "AVAX", "AVAXUSDT", "NEAR", "NEARUSDT", "INJ", "INJUSDT", "SUI", "SUIUSDT", "LINK", "LINKUSDT", "RENDER", "RENDERUSDT", "4USDT", "HYPEUSDT"],
        "TRADFI_METALS": ["PAXG", "PAXGUSDT", "XAUUSD", "XAGUSD", "GOLD", "SILVER"],
        "TRADFI_INDICES": ["US100", "US500", "US30", "GER40", "NAS100", "SPX500"],
        "FOREX_MAJORS": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "GBPJPY"]
    }
    
    def __init__(self, correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD, max_per_cluster: int = MAX_UNPROTECTED_PER_CLUSTER):
        self.correlation_threshold = correlation_threshold
        self.max_per_cluster = max_per_cluster
        self._price_buffers: Dict[str, List[float]] = {}
        
    def update_price_history(self, asset: str, prices: List[float]):
        """Actualiza el buffer de precios de cierre para el cálculo de covarianza."""
        sym = self._clean_symbol(asset)
        if len(prices) >= 10:
            self._price_buffers[sym] = prices[-50:]  # Mantener últimas 50 velas
            
    def _clean_symbol(self, symbol: str) -> str:
        s = (symbol or "").replace("/", "").upper()
        return s

    def get_cluster_name(self, asset: str) -> str:
        """Determina a qué cluster macroeconómico pertenece el activo."""
        sym = self._clean_symbol(asset)
        for cluster_name, assets in self.STRUCTURAL_CLUSTERS.items():
            if any(sym.startswith(a) or sym == a for a in assets):
                return cluster_name
        return "GENERAL_ALPHA"

    def calculate_correlation(self, asset_a: str, asset_b: str) -> float:
        """Calcula el coeficiente de correlación de Pearson entre dos activos sobre retornos porcentuales."""
        sym_a = self._clean_symbol(asset_a)
        sym_b = self._clean_symbol(asset_b)
        
        if sym_a == sym_b:
            return 1.0
            
        p_a = self._price_buffers.get(sym_a, [])
        p_b = self._price_buffers.get(sym_b, [])
        
        # Si tenemos datos de precios sincronizados suficientes
        if len(p_a) >= 15 and len(p_b) >= 15:
            min_len = min(len(p_a), len(p_b))
            arr_a = np.array(p_a[-min_len:], dtype=np.float64)
            arr_b = np.array(p_b[-min_len:], dtype=np.float64)
            
            # Retornos logarítmicos
            ret_a = np.diff(np.log(arr_a))
            ret_b = np.diff(np.log(arr_b))
            
            std_a = np.std(ret_a)
            std_b = np.std(ret_b)
            
            if std_a > 1e-8 and std_b > 1e-8:
                corr = np.corrcoef(ret_a, ret_b)[0, 1]
                if not np.isnan(corr):
                    return float(corr)
                    
        # Fallback a correlación estructural según mapa de clusters
        cluster_a = self.get_cluster_name(sym_a)
        cluster_b = self.get_cluster_name(sym_b)
        
        if cluster_a == cluster_b and cluster_a != "GENERAL_ALPHA":
            # Alta correlación intra-cluster
            return 0.85 if "CRYPTO" in cluster_a else 0.80
        elif ("CRYPTO" in cluster_a and "CRYPTO" in cluster_b):
            return 0.75
        else:
            return 0.15 # Descorrelacionados (ej. Cripto vs Oro o TradFi)

    def can_open_position(
        self,
        new_asset: str,
        new_direction: str,
        confluence_score: float = 70.0,
        active_positions: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Evalúa si abrir una nueva posición viola la regla de riesgo por cluster.
        
        Retorna:
            (aprobado: bool, motivo: str)
        """
        if not active_positions:
            return True, "Cluster libre (sin posiciones activas)"
            
        new_sym = self._clean_symbol(new_asset)
        new_dir = str(new_direction).upper()
        new_cluster = self.get_cluster_name(new_sym)
        
        correlated_risk_count = 0
        conflicting_assets = []
        
        for active_asset, pos_data in active_positions.items():
            active_sym = self._clean_symbol(active_asset)
            if active_sym == new_sym:
                continue
                
            sig = pos_data.get("signal", {})
            active_dir = str(sig.get("type", sig.get("signal_type", "LONG"))).upper()
            
            # Solo consideramos riesgo en la misma dirección (ej. 2 Longs)
            if active_dir != new_dir:
                continue
                
            # Verificar si la posición activa tiene riesgo real flotante
            be_active = pos_data.get("smart_trailing", {}).get("be_active", False)
            sl = float(sig.get("stop_loss", 0))
            entry = float(sig.get("price", sig.get("entry_price", 0)))
            
            sl_at_be = (active_dir == "LONG" and entry > 0 and sl >= entry * 0.999) or                        (active_dir == "SHORT" and entry > 0 and sl > 0 and sl <= entry * 1.001)
                       
            # Si la posición está en Breakeven, su slot de riesgo queda liberado
            if be_active or sl_at_be:
                continue
                
            # Calcular correlación real entre el nuevo activo y la posición activa
            corr = self.calculate_correlation(new_sym, active_sym)
            if corr >= self.correlation_threshold:
                correlated_risk_count += 1
                conflicting_assets.append(f"{active_sym} (ρ={corr:.2f})")
                
        # ── SOP-30: BETA EXPOSURE LIMITER v39.0 ──
        # Si es un LONG en Cripto, no permitir más de 2 posiciones LONG en cripto simultáneas con riesgo flotante
        if new_dir == "LONG" and "CRYPTO" in new_cluster:
            crypto_longs_count = 0
            crypto_conflicts = []
            for act_asset, p_data in active_positions.items():
                act_sym = self._clean_symbol(act_asset)
                if act_sym == new_sym:
                    continue
                s_data = p_data.get("signal", {})
                s_dir = str(s_data.get("type", s_data.get("signal_type", "LONG"))).upper()
                if s_dir == "LONG" and "CRYPTO" in self.get_cluster_name(act_sym):
                    s_sl = float(s_data.get("stop_loss", 0))
                    s_entry = float(s_data.get("price", s_data.get("entry_price", 0)))
                    s_be = p_data.get("smart_trailing", {}).get("be_active", False)
                    if not (s_be or (s_entry > 0 and s_sl >= s_entry * 0.999)):
                        crypto_longs_count += 1
                        crypto_conflicts.append(act_sym)
                        
            if crypto_longs_count >= self.max_per_cluster:
                if confluence_score >= 88.0:
                    logger.info(f"💎 [SOP-30 BETA GUARD] Confluencia Élite ({confluence_score}%) aprueba 3er LONG en {new_sym}.")
                    return True, f"Aprobado por Confluencia Élite ({confluence_score}% >= 88%)"
                reason = f"Límite de cluster alcanzado (SOP-30 BETA VETO: {crypto_longs_count}/{self.max_per_cluster} en riesgo). Conflicto con: {', '.join(crypto_conflicts)}"
                logger.warning(f"{reason} para {new_sym}")
                return False, reason

        if correlated_risk_count >= self.max_per_cluster:
            # Excepción por confluencia élite si el score es excepcionalmente alto (>= 88%)
            if confluence_score >= 88.0:
                logger.info(f"💎 [CLUSTER RISK GUARD] Confluencia ÉLITE ({confluence_score}%) supera el umbral de cluster para {new_sym}.")
                return True, f"Aprobado por Confluencia Élite ({confluence_score}% >= 88%)"
                
            reason = f"Límite de cluster alcanzado ({correlated_risk_count}/{self.max_per_cluster} en riesgo). Conflicto con: {', '.join(conflicting_assets)}"
            logger.warning(f"🛑 [CLUSTER RISK GUARD] Rechazada entrada en {new_sym} ({new_dir}): {reason}")
            return False, reason
            
        return True, f"Aprobado por Cluster Risk Guard ({correlated_risk_count}/{self.max_per_cluster} en cluster {new_cluster})"

# Instancia global singleton
cluster_risk_guard = ClusterRiskGuard()