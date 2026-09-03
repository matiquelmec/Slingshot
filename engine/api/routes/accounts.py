"""
engine/api/routes/accounts.py
=============================================================================
Router REST para Gestión Multi-Cuentas de Bitunix Futures
- GET  /api/v1/accounts: Lista todas las cuentas con balance y riesgo.
- POST /api/v1/accounts: Agrega una nueva cuenta con validación previa en Bitunix.
- POST /api/v1/accounts/validate: Prueba credenciales sin guardarlas.
- POST /api/v1/accounts/{account_id}/toggle: Activa o pausa una cuenta.
- DELETE /api/v1/accounts/{account_id}: Elimina una cuenta secundaria.
=============================================================================
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from engine.execution.account_manager import AccountManager, BitunixAccountConfig
from engine.core.logger import logger

router = APIRouter(prefix="/accounts", tags=["Multi-Account Management"])


class AccountCreateRequest(BaseModel):
    account_id: str = Field(..., description="ID único para la cuenta (ej. client_matias_2)")
    label: str = Field(..., description="Etiqueta legible (ej. Cuenta Secundaria)")
    api_key: str = Field(..., description="Bitunix Futures API Key")
    secret_key: str = Field(..., description="Bitunix Futures Secret Key")
    risk_pct: float = Field(0.025, ge=0.005, le=0.10, description="Riesgo por trade (ej: 0.025 = 2.5%)")
    max_notional_mult: float = Field(5.0, ge=1.0, le=10.0, description="Techo de apalancamiento sobre balance")
    dry_run: bool = Field(False, description="Modo simulación exclusivo para esta cuenta")


class AccountValidateRequest(BaseModel):
    api_key: str
    secret_key: str


class AccountToggleRequest(BaseModel):
    enabled: bool


@router.get("", summary="Listar todas las cuentas de Bitunix y sus saldos en vivo")
async def list_accounts():
    mgr = AccountManager()
    summary = await mgr.get_accounts_summary()
    return {"status": "success", "accounts": summary, "total": len(summary)}


@router.post("/validate", summary="Probar credenciales en Bitunix sin guardar")
async def validate_credentials(req: AccountValidateRequest):
    mgr = AccountManager()
    is_valid, msg, balance = await mgr.test_credentials(req.api_key, req.secret_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Credenciales inválidas o error de Bitunix: {msg}"
        )
    return {
        "status": "success",
        "message": msg,
        "available_balance_usdt": balance
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Registrar una nueva cuenta de Bitunix")
async def create_account(req: AccountCreateRequest):
    mgr = AccountManager()
    cfg = BitunixAccountConfig(
        account_id=req.account_id.strip().lower(),
        label=req.label.strip(),
        api_key=req.api_key.strip(),
        secret_key=req.secret_key.strip(),
        enabled=True,
        risk_pct=req.risk_pct,
        max_notional_mult=req.max_notional_mult,
        dry_run=req.dry_run,
        is_primary=False
    )
    success, msg = await mgr.add_account(cfg, test_first=not req.dry_run)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )
    return {"status": "success", "message": msg, "account": cfg.to_dict(mask_secrets=True)}


@router.post("/{account_id}/toggle", summary="Pausar o reanudar el trading para una cuenta")
async def toggle_account(account_id: str, req: AccountToggleRequest):
    mgr = AccountManager()
    success, msg = mgr.toggle_account(account_id, enabled=req.enabled)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=msg
        )
    return {"status": "success", "message": msg}


@router.delete("/{account_id}", summary="Eliminar una cuenta secundaria")
async def delete_account(account_id: str):
    mgr = AccountManager()
    success, msg = mgr.remove_account(account_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )
    return {"status": "success", "message": msg}
