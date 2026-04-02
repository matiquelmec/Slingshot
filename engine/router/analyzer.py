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
    htf_bias: Optional[dict]
    diagnostic: dict
    df_analyzed: Any = field(default_factory=dict) # Respaldo para el pipeline de estrategia


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

        # ── Paso 5: Fibonacci Dinámico ───────────────────────────────────────
        fibonacci = self._get_fibonacci(df)

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

        # ── Paso 7: Diagóstico Macro ─────────────────────────────────────────
        macro = get_macro_context()
        diagnostic = {
            "volume": float(df["volume"].iloc[-1]) if "volume" in df.columns else 0.0,
            "volume_mean": float(df["volume"].rolling(20).mean().iloc[-1]) if "volume" in df.columns else 0.0,
            "macro_bias": macro.global_bias,
            "dxy_trend": macro.dxy_trend,
            "risk_appetite": macro.risk_appetite,
        }
        
        # DIAGNÓSTICO FINAL DE SALIDA (v4.3.7)
        s_val = df["support_level"].iloc[-1] if "support_level" in df.columns else "MISSING_COL"
        audit_msg = f"[ANALYZER] {asset} | S_Level={s_val} | KL={len(key_levels.get('supports', []))}"
        print(f"🛠️  {audit_msg}")
        
        try:
            with open("c:/tmp/structural_audit.log", "a") as f:
                f.write(f"{time.time()}: {audit_msg}\n")
        except:
            pass

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
            htf_bias=htf_payload,
            diagnostic=diagnostic,
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
            print(f"[ANALYZER] SMC Error: {e}")
            return {"order_blocks": {"bullish": [], "bearish": []}, "fvgs": {"bullish": [], "bearish": []}}

    def _get_fibonacci(self, df: pd.DataFrame) -> Optional[dict]:
        try:
            return get_current_fibonacci_levels(df)
        except Exception:
            return None
