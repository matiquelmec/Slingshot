"""
engine/router/analyzer.py — Slingshot v4.1 Platinum
======================================================
Capa de Análisis Puro (sin efectos secundarios).
Responsabilidad: transformar OHLCV bruto en el mapa completo del mercado.
  - Topografía de S/R
  - Régimen de Wyckoff
  - Detección de OBs, FVGs y POIs (SMC)
  - Fibonacci Dinámico
  - Fusión de niveles MTF
"""
from __future__ import annotations
import time
import os
from engine.core.logger import logger

import pandas as pd
import numpy as np
import time
from dataclasses import dataclass, field
from typing import Optional, Any

from engine.indicators.regime import RegimeDetector
from engine.indicators.structure import (
    identify_support_resistance,
    get_key_levels,
    identify_order_blocks,
    extract_smc_coordinates,
)
from engine.indicators.fibonacci import get_current_fibonacci_levels
from engine.indicators.macro import get_macro_context


@dataclass
class MarketMap:
    """Resultado inmutable del análisis de mercado."""
    asset: str
    interval: str
    timestamp: str
    current_price: float
    market_regime: str
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    expansion_ratio: float
    range_pos_pct: float
    key_levels: dict
    smc: dict
    fibonacci: Optional[dict]
    fibonacci_h1: Optional[dict] = None # v4.4 Shadow Mode
    htf_bias: Optional[dict] = None
    diagnostic: dict = field(default_factory=dict)
    htf_alignment: bool = False 
    displacement_valid: bool = False 
    df_analyzed: Any = field(default_factory=dict) 


class MarketAnalyzer:
    """
    Módulo de análisis puro. No filtra señales ni calcula riesgo.
    Solo transforma OHLCV → MarketMap institucional.
    """

    def __init__(self):
        self._regime_detector = RegimeDetector()

    def analyze(
        self,
        df: pd.DataFrame,
        asset: str = "BTCUSDT",
        interval: str = "15m",
        macro_levels=None,
        htf_bias=None,
    ) -> MarketMap:
        """
        Pipeline de análisis completo.
        Retorna un MarketMap con toda la topografía institucional.
        """
        df = df.copy()

        # ── Paso 0: Normalización de Tipos (v5.4.2) ─────────────────────────
        # Aseguramos que OHLCV sea numérico para evitar fallos en cálculos vectorizados
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # ── Paso 1: Soporte / Resistencia Topográfico ────────────────────────
        df = identify_support_resistance(df, interval=interval)
        # PRESERVACIÓN CRÍTICA: Salvar attrs antes de que df.copy() los borre en pasos siguientes
        saved_attrs = df.attrs.copy()

        # ── Paso 2: Régimen de Wyckoff ───────────────────────────────────────
        df = self._regime_detector.detect_regime(df)
        df.attrs.update(saved_attrs) # Restaurar tras detección
        current_regime = df["market_regime"].iloc[-1]

        # ── Paso 3: SMC — OBs, FVGs y confluencia con S/R ───────────────────
        # _extract_smc requiere los S/R en df.attrs para calcular 'ob_confluence'
        smc_data = self._extract_smc(df)
        df.attrs.update(saved_attrs) # Asegurar persistencia para el siguiente paso
        key_levels = get_key_levels(df) 

        # ── Paso 4: Niveles Clave con fusión MTF opcional ────────────────────
        from engine.indicators.structure import consolidate_mtf_levels
        if macro_levels:
            key_levels = consolidate_mtf_levels(key_levels, macro_levels)

        # ── Paso 5: Fibonacci Dinámico (v4.4 MTF Shadow Mode) ─────────────────
        fibonacci = self._get_fibonacci(df)
        
        # 🟢 SHADOW MODE: El Fib de 1H se proyecta si hay data estructurada (v4.4.1)
        fibonacci_h1 = None
        # Pendiente de inyectar macro_df en dispatcher.py para activar la sombra h1 completa

        # ── Paso 6: HTF Bias (serializado para JSON) ─────────────────────────
        htf_payload = None
        if htf_bias:
            htf_payload = {
                "direction": htf_bias.direction,
                "strength": htf_bias.strength,
                "reason": htf_bias.reason,
                "h4_regime": htf_bias.h4_regime,
                "h1_regime": htf_bias.h1_regime,
            }

        # ── Paso 7: Diagnóstico Macro y Validación de Gates (v4.7 Platinum) ────
        macro = get_macro_context()
        
        # RVOL v4.7: Re-Ingeniería de Proyección Temporal para evitar picos falsos
        # Fórmula: RVOL = (Current_Vol / (Seconds_Elapsed / 900)) / max(SMA_20, VOL_FLOOR)
        current_vol = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0.0
        
        # 1. Definir Base Temporal Dinámica (Protocolo Generalización v4.7.1)
        time_map = {
            '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800, 
            '1h': 3600, '2h': 7200, '4h': 14400, '1d': 86400
        }
        tf_seconds = time_map.get(interval, 900)
        
        # 2. Calcular tiempo transcurrido en la vela actual
        try:
            # Si el DF tiene timestamp, calculamos el drift real
            last_ts = df["timestamp"].iloc[-1].timestamp()
            secs_elapsed = max(time.time() - last_ts, 1) # Mínimo 1s
            # Limitar secs_elapsed al máximo del timeframe para evitar ratios invertidos
            secs_elapsed = min(secs_elapsed, tf_seconds)
        except Exception:
            secs_elapsed = tf_seconds # Fallback: velas cerradas
            
        # 3. Proyectar volumen actual al cierre de la vela (Normalization)
        # 🔴 v4.7.2 Optimization: Projection Damping (Anti-Outlier Shield)
        # Si la vela acaba de empezar (< 2% de progreso), la proyección matemática es inestable.
        # Implementamos un amortiguador (Damping) para evitar que el primer tick distorsione el Radar.
        progress_ratio = secs_elapsed / tf_seconds
        
        # 4. Adaptive Floor (Pilar 4.8: Resiliencia Multi-Asset)
        vol_history_20 = df["volume"].rolling(window=min(len(df), 20), min_periods=1).mean()
        vol_mean_20 = float(vol_history_20.iloc[-1]) if not vol_history_20.empty else 1.0
        
        # Calculamos SMA200 para el suelo adaptativo
        vol_history_200 = df["volume"].rolling(window=min(len(df), 200), min_periods=1).mean()
        vol_sma200 = float(vol_history_200.iloc[-1]) if not vol_history_200.empty else 1.0
        vol_floor = 0.1 * vol_sma200
        
        baseline = max(vol_mean_20, vol_floor)
        
        if progress_ratio < 0.02: # Primeros 18s en 15m
            # En el arranque, el volumen proyectado tiende al promedio histórico para evitar ruido.
            projected_vol = (vol_mean_20 * 0.9) + (current_vol / max(progress_ratio, 0.001) * 0.1)
        else:
            projected_vol = current_vol / progress_ratio
            
        rvol = projected_vol / baseline

        # 6. [HARDENING] Z-Score Outlier Detection (v5.2 Platinum)
        from engine.indicators.volume import calculate_zscore_filter
        z_scores = calculate_zscore_filter(df, threshold=5.0)
        z_score = float(z_scores.iloc[-1]) if len(df) > 1 else 0.0
        is_soft_outlier = bool(calculate_zscore_filter(df, threshold=4.0).iloc[-1]) if len(df) > 1 else False
        is_hard_outlier = bool(z_scores.iloc[-1] > 5.0) if len(df) > 1 else False
        
        # [ANOMALY LOGGING]
        # [RVOL_DEBUG] | Secs_Elapsed: {s}s | Vol_Crudo: {v} | Vol_Proyectado: {vp} | SMA_Baseline: {b} | RESULT: {r}x
        debug_log = f"[RVOL_DEBUG] | Secs_Elapsed: {int(secs_elapsed)}s | Vol_Crudo: {round(current_vol, 2)} | Vol_Proyectado: {round(projected_vol, 2)} | SMA_Baseline: {round(baseline, 2)} | RESULT: {rvol:.2f}x"
        print(debug_log) # Consola real para el usuario

        if is_hard_outlier:
            logger.warning(f"🛑 [HARD_OUTLIER] Anomalía detectada en {asset} ({current_vol}). Capped to 5.0x")
            # Registro Institucional de Anomalías
            try:
                os.makedirs("logs", exist_ok=True)
                with open("logs/anomalies.log", "a") as f:
                    f.write(f"[{pd.Timestamp.now()}] ASSET: {asset} | RAW_VOL: {current_vol} | PROJ_VOL: {projected_vol} | Z-SCORE ALERT | ACTION: CAP 5.0x\n")
            except Exception as e:
                logger.error(f"Error escribiendo en anomalies.log: {e}")
            
            rvol = min(rvol, 5.0)

        # Verificación de Gates
        # Gate 1: Alignment (Si hay HTF, debe coincidir con el sesgo local de Wyckoff)
        htf_align = False
        if htf_bias:
            is_local_bullish = current_regime in ['MARKUP', 'ACCUMULATION']
            is_htf_bullish = str(htf_bias.direction).upper() in ['BULLISH', 'STRONG_BULLISH']
            is_local_bearish = current_regime in ['MARKDOWN', 'DISTRIBUTION']
            is_htf_bearish = str(htf_bias.direction).upper() in ['BEARISH', 'STRONG_BEARISH']
            htf_align = (is_local_bullish == is_htf_bullish) or (is_local_bearish == is_htf_bearish)

        # Gate 2: Displacement (Exigimos RVOL > 1.2 para validar el movimiento)
        displacement_active = rvol >= 1.2

        diagnostic = {
            "volume": current_vol,
            "projected_volume": round(projected_vol, 2),
            "volume_24h": float(df['volume'].sum()), 
            "volume_mean": vol_mean_20,
            "rvol": round(rvol, 2),  # SSOT: This is the value sent to Radar
            "is_outlier": is_soft_outlier,
            "is_hard_outlier": is_hard_outlier,
            "secs_elapsed": int(secs_elapsed),
            "progress_ratio": round(progress_ratio, 4),
            "macro_bias": macro.global_bias,
            "dxy_trend": macro.dxy_trend,
            "risk_appetite": macro.risk_appetite,
            "htf_align": htf_align,
            "displacement_active": displacement_active
        }
        
        # DIAGNÓSTICO FINAL DE SALIDA
        s_val = df["support_level"].iloc[-1] if "support_level" in df.columns else "MISSING_COL"
        logger.info(f"🛠️  [ANALYZER] {asset} | S_Level={s_val} | KL={len(key_levels.get('supports', []))}")

        return MarketMap(
            asset=asset,
            interval=interval,
            timestamp=str(df["timestamp"].iloc[-1]),
            current_price=float(df["close"].iloc[-1]),
            market_regime=current_regime,
            nearest_support=(
                float(df["support_level"].iloc[-1])
                if "support_level" in df.columns and pd.notna(df["support_level"].iloc[-1])
                else None
            ),
            nearest_resistance=(
                float(df["resistance_level"].iloc[-1])
                if "resistance_level" in df.columns and pd.notna(df["resistance_level"].iloc[-1])
                else None
            ),
            expansion_ratio=float(df["expansion_ratio"].iloc[-1]) if "expansion_ratio" in df.columns else 1.0,
            range_pos_pct=float(df["range_pos_pct"].iloc[-1]) if "range_pos_pct" in df.columns else 0.5,
            key_levels=key_levels,
            smc=smc_data,
            fibonacci=fibonacci,
            fibonacci_h1=fibonacci_h1,
            htf_bias=htf_payload,
            diagnostic=diagnostic,
            htf_alignment=htf_align,
            displacement_valid=displacement_active,
            df_analyzed=df,
        )

    # ── Helpers privados ─────────────────────────────────────────────────────

    def _extract_smc(self, df: pd.DataFrame) -> dict:
        """Extrae OBs y FVGs, y funde su confluencia con S/R."""
        try:
            atr_val = df.attrs.get("atr_value", float(df["close"].iloc[-1]) * 0.003)
            df_ob = identify_order_blocks(df)
            smc = extract_smc_coordinates(df_ob)

            bullish_zones = (
                [{"top": o["top"], "bottom": o["bottom"]} for o in smc["order_blocks"]["bullish"]]
                + [{"top": f["top"], "bottom": f["bottom"]} for f in smc["fvgs"]["bullish"]]
            )
            bearish_zones = (
                [{"top": o["top"], "bottom": o["bottom"]} for o in smc["order_blocks"]["bearish"]]
                + [{"top": f["top"], "bottom": f["bottom"]} for f in smc["fvgs"]["bearish"]]
            )

            def _near(price: float, zones: list) -> bool:
                return any(z["bottom"] - atr_val <= price <= z["top"] + atr_val for z in zones)

            for lvl in df.attrs.get("key_resistances", []):
                lvl["ob_confluence"] = _near(lvl["price"], bearish_zones)
            for lvl in df.attrs.get("key_supports", []):
                lvl["ob_confluence"] = _near(lvl["price"], bullish_zones)

            smc["key_supports"] = df.attrs.get("key_supports", [])
            smc["key_resistances"] = df.attrs.get("key_resistances", [])
            return smc
        except Exception as e:
            logger.error(f"[ANALYZER] SMC Error: {e}")
            return {"order_blocks": {"bullish": [], "bearish": []}, "fvgs": {"bullish": [], "bearish": []}}

    def _get_fibonacci(self, df: pd.DataFrame) -> Optional[dict]:
        try:
            return get_current_fibonacci_levels(df)
        except Exception:
            return None
