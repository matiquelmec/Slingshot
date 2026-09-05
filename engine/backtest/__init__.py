"""
engine/backtest/__init__.py — Módulo de Backtesting Institucional Slingshot SSoT
================================================================================
Centraliza el motor de backtesting canónico:
- UnifiedBacktestEngine: Motor cuantitativo de alta fidelidad SSoT
"""
from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine, DATA_DIR, MEGA_CAPS, HIGH_BETA_ALTS

__all__ = ["UnifiedBacktestEngine", "DATA_DIR", "MEGA_CAPS", "HIGH_BETA_ALTS"]
