"""
engine/backtest/__init__.py — Módulo de Backtesting Institucional Slingshot v13.4
================================================================================
Centraliza todos los componentes de backtesting:
- replay_engine: Motor event-driven de alta fidelidad (async)
- fast_audit: Auditoría rápida de profit con ConfluenceManager real
- multi_asset: Backtesting de portafolio multi-activo
- stress_audit: Stress test sintético del Gatekeeper
- find_signals: Buscador de setups "Santa Trinidad" (OB + Sweep + FVG)
"""
from engine.backtest.replay_engine import EventDrivenReplayEngine

__all__ = ["EventDrivenReplayEngine"]
