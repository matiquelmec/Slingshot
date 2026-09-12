"""
engine/aiq/relational_connector.py — Conector Relacional Multi-Tabla (Kumo Blueprint)
=====================================================================================
Extrae, normaliza y estructura las relaciones multi-tabla de SQLite WAL
(closed_trades ↔ confluence_factor_attribution ↔ regime_history ↔ post_mortem_reports)
para alimentar modelos fundacionales de predicción relacional (Kumo Relational).
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from engine.core.logger import logger
from engine.core.vault import vault


class AIQRelationalConnector:
    """
    Conector de Datos Estructurados Multi-Tabla para Arquitectura NVIDIA AI-Q.
    Genera vistas de grafo relacional y matrices cruzadas de entrenamiento.
    """

    def __init__(self, vault_instance=None):
        self.vault = vault_instance or vault

    def extract_relational_dataset(self, lookback_days: int = 60) -> Dict[str, pd.DataFrame]:
        """
        Extrae las 4 tablas relacionales principales normalizadas con sus claves foráneas.
        """
        tables = {}
        with self.vault._get_connection() as conn:
            # 1. Closed Trades (Tabla de Entidad Principal / Raíz)
            try:
                tables["closed_trades"] = pd.read_sql_query(
                    "SELECT id, account_id, symbol, side, pnl_r, pnl_usd, exit_reason, closed_at FROM closed_trades",
                    conn
                )
            except Exception:
                tables["closed_trades"] = pd.DataFrame(columns=["id", "account_id", "symbol", "side", "pnl_r", "pnl_usd", "exit_reason", "closed_at"])

            # 2. Confluence Factor Attribution (Tabla de Enlace N:M Trade-Factores)
            try:
                tables["factor_attribution"] = pd.read_sql_query(
                    "SELECT id, trade_id, symbol, factor_name, was_confirmed, is_win, pnl_r, timestamp FROM confluence_factor_attribution",
                    conn
                )
            except Exception:
                tables["factor_attribution"] = pd.DataFrame(columns=["id", "trade_id", "symbol", "factor_name", "was_confirmed", "is_win", "pnl_r", "timestamp"])

            # 3. Regime History (Serie Temporal Cuantitativa)
            try:
                tables["regime_history"] = pd.read_sql_query(
                    "SELECT id, regime, risk_multiplier, confidence, evaluated_at FROM regime_history",
                    conn
                )
            except Exception:
                tables["regime_history"] = pd.DataFrame(columns=["id", "regime", "risk_multiplier", "confidence", "evaluated_at"])

            # 4. Post-Mortem Reports (Tabla de Diagnóstico Causal y Síntesis)
            try:
                tables["post_mortem_reports"] = pd.read_sql_query(
                    "SELECT id, trade_id, symbol, side, pnl_usd, loss_category, causal_analysis, preventive_rule, analyzed_at FROM post_mortem_reports",
                    conn
                )
            except Exception:
                tables["post_mortem_reports"] = pd.DataFrame(columns=["id", "trade_id", "symbol", "side", "pnl_usd", "loss_category", "causal_analysis", "preventive_rule", "analyzed_at"])

        return tables

    def build_cross_table_features(self, target_symbol: str, target_regime: str, active_factors: List[str]) -> Dict[str, Any]:
        """
        Construye el tensor de características cruzadas para predecir la probabilidad
        de éxito (Win Probability) según la interacción histórica de las tablas relacionales.
        """
        tables = self.extract_relational_dataset()
        trades_df = tables["closed_trades"]
        factors_df = tables["factor_attribution"]

        # Si el histórico es embrionario, emitir probabilidad previa bayesiana no informativa
        if trades_df.empty or factors_df.empty:
            return {
                "predicted_win_prob": 0.50,
                "sample_size": 0,
                "confidence": 0.50,
                "relational_edge": 0.0,
                "model": "BAYESIAN_PRIOR_FALLBACK"
            }

        # Filtrar trades del activo o de la misma clase
        sym_factors = factors_df[factors_df["symbol"] == target_symbol.upper()]
        if sym_factors.empty:
            sym_factors = factors_df

        # Calcular tasa de éxito ponderada por los factores actualmente activos
        matching_factors = sym_factors[sym_factors["factor_name"].isin(active_factors)]
        if matching_factors.empty:
            win_rate = 0.50
            sample_size = 0
        else:
            wins = int((matching_factors["is_win"] == 1).sum())
            total = len(matching_factors)
            win_rate = (wins + 10.0) / (total + 20.0) # Beta-Binomial Smoothing
            sample_size = total

        relational_edge = round(win_rate - 0.50, 4)
        return {
            "predicted_win_prob": round(win_rate, 4),
            "sample_size": sample_size,
            "confidence": min(0.95, 0.50 + (sample_size / 100.0) * 0.45),
            "relational_edge": relational_edge,
            "model": "KUMO_RELATIONAL_EMULATOR_V1"
        }


aiq_relational_connector = AIQRelationalConnector()
