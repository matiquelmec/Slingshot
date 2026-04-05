"""
engine/router/analyzer.py — v5.7.155 Master Gold
======================================================
Capa de Análisis Puro (sin efectos secundarios).
Responsabilidad: transformar OHLCV bruto en el mapa completo del mercado.
"""
from __future__ import annotations
import time
import os
from engine.core.logger import logger

import pandas as pd
import numpy as np
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
from engine.indicators.volume import calculate_rvol, calculate_absorption_index, calculate_zscore_robust


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
    fibonacci_h1: Optional[dict] = None
    htf_bias: Optional[dict] = None
    diagnostic: dict = field(default_factory=dict)
    htf_alignment: bool = False 
    displacement_valid: bool = False 
    df_analyzed: Any = field(default_factory=dict) 


class MarketAnalyzer:
    """
    Módulo de análisis puro v5.4.
    Transforma OHLCV → MarketMap institucional con métricas de absorción.
    """

    def __init__(self, cache_size: int = 100):
        self._regime_detector = RegimeDetector()
        self._cache = {} # LRU Cache: (asset, interval, ts) -> MarketMap
        self._cache_size = cache_size
        # DELTA FIX: Caché de RVOL/Absorption para evitar recalcular rolling medians en cada tick (Trident Audit v5.7.15)
        self._rvol_cache_key: str = ""
        self._rvol_cached_cols: dict = {}  # {"rvol": Series, "vol_median": Series, "absorption_score": Series}

    def _get_cache_key(self, asset: str, interval: str, df: pd.DataFrame) -> str:
        try:
            ts = str(df["timestamp"].iloc[-1])
            return f"{asset}_{interval}_{ts}"
        except:
            return f"{asset}_{interval}_{time.time()}"

    def analyze(
        self,
        df: pd.DataFrame,
        asset: str = "BTCUSDT",
        interval: str = "15m",
        macro_levels=None,
        htf_bias=None,
        heatmap: dict | None = None,
    ) -> MarketMap:
        """Pipeline de análisis completo v5.4 con soporte de Caché LRU."""
        
        # ── Intento de recuperación de Caché (Optimización SIGMA) ─────────────
        cache_key = self._get_cache_key(asset, interval, df)
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = df.copy()

        # ── Paso 0: Normalización de Tipos ─────────────────────────
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # ── Paso 1: Soporte / Resistencia ──────────────────────────
        df = identify_support_resistance(df, interval=interval)
        saved_attrs = df.attrs.copy()

        # ── Paso 2: Régimen de Wyckoff ─────────────────────────────
        df = self._regime_detector.detect_regime(df)
        df.attrs.update(saved_attrs)
        current_regime = df["market_regime"].iloc[-1]

        # ── Paso 3: SMC — Estructura Fractal ───────────────────────
        smc_data = self._extract_smc(df)
        df.attrs.update(saved_attrs)
        key_levels = get_key_levels(df) 

        # ── Paso 4: Fusión MTF ─────────────────────────────────────
        from engine.indicators.structure import consolidate_mtf_levels
        if macro_levels:
            key_levels = consolidate_mtf_levels(key_levels, macro_levels)

        # ── Paso 5: Fibonacci ──────────────────────────────────────
        fibonacci = self._get_fibonacci(df)
        
        # ── Paso 6: HTF Bias ───────────────────────────────────────
        htf_payload = None
        if htf_bias:
            htf_payload = {
                "direction": htf_bias.direction,
                "strength": htf_bias.strength,
                "reason": htf_bias.reason
            }

        # ── Paso 7: Diagnóstico de Volumen v5.7.15 (DELTA FIX: Cached Rolling Medians) ──
        # Solo recalculamos RVOL/Absorption cuando la última vela ha cambiado (cierre real).
        # En el Fast Path (mismo timestamp), reutilizamos las columnas cacheadas.
        vol_cache_key = f"{asset}_{str(df['timestamp'].iloc[-1])}"
        
        if vol_cache_key == self._rvol_cache_key and self._rvol_cached_cols:
            # Hit de caché: inyectar columnas sin recalcular
            for col_name, col_data in self._rvol_cached_cols.items():
                if len(col_data) == len(df):
                    df[col_name] = col_data.values
        else:
            # Miss de caché: recalcular y persistir
            df = calculate_rvol(df)
            df = calculate_absorption_index(df)
            self._rvol_cache_key = vol_cache_key
            self._rvol_cached_cols = {
                "rvol": df["rvol"].copy(),
                "vol_median": df["vol_median"].copy(),
                "absorption_score": df["absorption_score"].copy() if "absorption_score" in df.columns else pd.Series([0.0]*len(df)),
                "absorption_raw": df["absorption_raw"].copy() if "absorption_raw" in df.columns else pd.Series([0.0]*len(df)),
            }
        
        rvol = float(df['rvol'].iloc[-1]) if 'rvol' in df.columns else 0.0
        absorption_score = float(df['absorption_score'].iloc[-1]) if 'absorption_score' in df.columns else 0.0
        is_high_absorption = bool(df.get('is_absorption_elite', pd.Series([False]*len(df))).iloc[-1])
        
        # Verificación de Gates
        htf_align = False
        if htf_bias:
            is_local_bullish = current_regime in ['MARKUP', 'ACCUMULATION']
            is_htf_bullish = str(htf_bias.direction).upper() in ['BULLISH', 'STRONG_BULLISH']
            is_local_bearish = current_regime in ['MARKDOWN', 'DISTRIBUTION']
            is_htf_bearish = str(htf_bias.direction).upper() in ['BEARISH', 'STRONG_BEARISH']
            htf_align = (is_local_bullish == is_htf_bullish) or (is_local_bearish == is_htf_bearish)

        macro = get_macro_context()
        
        diagnostic = {
            "volume": float(df["volume"].iloc[-1]),
            "rvol": round(rvol, 2),
            "absorption_score": round(absorption_score, 2),
            "is_absorption_elite": is_high_absorption,
            "macro_bias": macro.global_bias,
            "htf_align": htf_align,
            "displacement_active": rvol >= 1.5,
            "imbalance_neural": (heatmap or {}).get("imbalance", 0.0)
        }
        
        logger.info(f"🛠️ [ANALYZER] {asset} | RVOL: {rvol:.2f} | Abs: {absorption_score:.2f} | HTF Align: {htf_align}")

        # ── Finalización y Caché ─────────────────────────────────────────────
        m_map = MarketMap(
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
            htf_bias=htf_payload,
            diagnostic=diagnostic,
            htf_alignment=htf_align,
            displacement_valid=rvol >= 1.5,
            df_analyzed=df,
        )

        # ── Guardar en Caché ─────────────────────────────────────────────────
        if len(self._cache) >= self._cache_size:
            # Desalojo simple: limpiar todo para evitar overhead de gestión compleja
            self._cache.clear()
        
        self._cache[cache_key] = m_map

        return m_map

    def _extract_smc(self, df: pd.DataFrame) -> dict:
        """Extrae OBs y FVGs v5.4."""
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
