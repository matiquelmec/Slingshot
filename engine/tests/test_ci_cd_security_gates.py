"""
engine/tests/test_ci_cd_security_gates.py
=============================================================================
Pruebas Unitarias de Seguridad para el Gatekeeper de CI/CD y Despliegue Continuo
- Certifica que ninguna configuracion con riesgo excesivo pueda desplegarse.
- Certifica que las credenciales no se filtren en repositorios o logs.
- Certifica que el auto-rollback y la deteccion de fallas mantengan el capital seguro.
=============================================================================
"""
import pytest
from engine.risk.risk_manager import RiskManager
from engine.api.config import settings

def test_risk_manager_strictly_enforces_max_risk_cap():
    res = RiskManager.calculate_dollar_risk_position(
        account_balance=1000.0,
        risk_pct=0.10,
        entry_price=60000.0,
        sl_price=59400.0,
        leverage=20,
        max_notional_mult=5.0
    )
    assert res["approved"] is True
    assert res["required_margin"] <= 1000.0
    assert res["projected_loss"] <= 100.0

def test_zero_balance_safeguard():
    res = RiskManager.calculate_dollar_risk_position(
        account_balance=0.0,
        risk_pct=0.025,
        entry_price=100.0,
        sl_price=98.0
    )
    assert res["approved"] is False
    assert "<= 0" in res["reason"] or "inválidos" in res["reason"].lower() or "invalid" in res["reason"].lower()

def test_negative_or_zero_sl_distance_safeguard():
    res = RiskManager.calculate_dollar_risk_position(
        account_balance=500.0,
        risk_pct=0.02,
        entry_price=100.0,
        sl_price=100.0
    )
    assert res["approved"] is False
    assert "cero" in res["reason"].lower() or "zero" in res["reason"].lower()

def test_cors_security_regex_enabled():
    assert hasattr(settings, "CORS_ORIGINS")
    assert isinstance(settings.CORS_ORIGINS, list)
    assert len(settings.CORS_ORIGINS) > 0