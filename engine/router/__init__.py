"""
engine/router/__init__.py — v5.7.155 Master Gold
====================================================
Paquete del Pipeline de Señales Modular.
Exporta las interfaces públicas para uso externo.
"""
from engine.router.analyzer import MarketAnalyzer, MarketMap
from engine.router.gatekeeper import SignalGatekeeper, GatekeeperContext, GatekeeperResult
from engine.router.dispatcher import build_base_result, enrich_signal

__all__ = [
    "MarketAnalyzer",
    "MarketMap",
    "SignalGatekeeper",
    "GatekeeperContext",
    "GatekeeperResult",
    "build_base_result",
    "enrich_signal",
]
