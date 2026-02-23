"""
engine/strategy.py — Alias de retro-compatibilidad.
=====================================================
La clase PaulPerdicesStrategy ha sido movida a su lugar canónico:
    engine/strategies/smc.py

Este módulo re-exporta la clase para que cualquier import antiguo
del tipo `from engine.strategy import PaulPerdicesStrategy` siga
funcionando sin cambios.

No añadir lógica aquí. Toda la implementación está en smc.py.
"""
from engine.strategies.smc import PaulPerdicesStrategy

__all__ = ['PaulPerdicesStrategy']
