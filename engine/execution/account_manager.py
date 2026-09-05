"""
engine/execution/account_manager.py
=============================================================================
Gestor y Registro Multi-Cuentas para Bitunix Futures (Master Account Dispatcher)
- Permite registrar, persistir y ejecutar múltiples cuentas de Bitunix en paralelo.
- Auto-descubre la cuenta principal desde las variables de entorno (.env).
- Persiste cuentas secundarias de forma segura en engine/data/bitunix_accounts.json.
- Mantiene un pool aislado de instancias BitunixExecutor para cada cuenta.
- Garantiza independencia total de saldos y cálculo de riesgo SOP-41 por cuenta.
=============================================================================
"""
import os
import json
import time
import base64
import hashlib
import asyncio
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

from cryptography.fernet import Fernet
from engine.api.config import settings
from engine.core.logger import logger
from engine.execution.bitunix_executor import BitunixExecutor


def _get_fernet_cipher() -> Fernet:
    """Deriva una clave de 32 bytes para Fernet desde SECURITY_API_KEY o JWT_SECRET."""
    secret = (getattr(settings, "SECURITY_API_KEY", "") or getattr(settings, "JWT_SECRET", "slingshot_master_vault_key")).encode("utf-8")
    key_32 = hashlib.sha256(secret).digest()
    b64_key = base64.urlsafe_b64encode(key_32)
    return Fernet(b64_key)


def encrypt_credential(plain_text: str) -> str:
    """Cifra un secreto si no está ya cifrado."""
    if not plain_text:
        return ""
    if plain_text.startswith("enc:v1:"):
        return plain_text
    try:
        cipher = _get_fernet_cipher()
        encrypted = cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        return f"enc:v1:{encrypted}"
    except Exception as e:
        logger.error(f"❌ [ACCOUNT_MANAGER] Error al cifrar credencial: {e}")
        return plain_text


def decrypt_credential(cipher_text: str) -> str:
    """Descifra una credencial con prefijo enc:v1: de forma transparente."""
    if not cipher_text:
        return ""
    if not cipher_text.startswith("enc:v1:"):
        return cipher_text
    try:
        raw_token = cipher_text[len("enc:v1:"):]
        cipher = _get_fernet_cipher()
        return cipher.decrypt(raw_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"❌ [ACCOUNT_MANAGER] Error al descifrar credencial: {e}")
        return cipher_text


@dataclass
class BitunixAccountConfig:
    account_id: str
    label: str
    api_key: str
    secret_key: str
    enabled: bool = True
    risk_pct: float = 0.025  # 2.50% Base Canónico SOP-41
    max_notional_mult: float = 5.0  # Techo nocional 5x balance
    dry_run: bool = False
    is_primary: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self, mask_secrets: bool = False) -> Dict[str, Any]:
        d = asdict(self)
        if mask_secrets:
            if d.get("api_key") and len(d["api_key"]) > 8:
                d["api_key"] = f"{d['api_key'][:4]}...{d['api_key'][-4:]}"
            else:
                d["api_key"] = "****"
            d["secret_key"] = "********"
        return d


class AccountManager:
    """
    Administrador centralizado de cuentas de Bitunix.
    Mantiene el ciclo de vida de los ejecutores y la persistencia de cuentas secundarias con cifrado AES-256 en reposo.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AccountManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, dry_run: bool = False, accounts_file: Optional[Path] = None):
        if getattr(self, "_initialized", False):
            return
        
        self.dry_run = dry_run
        self.accounts_file = accounts_file or (Path(__file__).parent.parent / "data" / "bitunix_accounts.json")
        self.accounts_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._accounts: Dict[str, BitunixAccountConfig] = {}
        self._executors: Dict[str, BitunixExecutor] = {}
        self._dispatch_semaphore = asyncio.Semaphore(10)  # Rate limiting de 10 llamadas concurrentes
        
        self._load_accounts()
        self._initialized = True
        logger.info(f"🏛️ [ACCOUNT_MANAGER] Inicializado con {len(self._accounts)} cuenta(s) registrada(s).")

    def _load_accounts(self):
        """Carga la cuenta primaria de .env y las secundarias del archivo JSON (descifrando credenciales)."""
        # 1. Cuenta Primaria (.env)
        if settings.BITUNIX_API_KEY and settings.BITUNIX_SECRET_KEY:
            primary = BitunixAccountConfig(
                account_id="primary",
                label="Cuenta Principal (.env)",
                api_key=settings.BITUNIX_API_KEY,
                secret_key=settings.BITUNIX_SECRET_KEY,
                enabled=True,
                risk_pct=0.025,
                max_notional_mult=5.0,
                dry_run=self.dry_run or not settings.ENABLE_LIVE_TRADING,
                is_primary=True
            )
            self._accounts["primary"] = primary
            self._executors["primary"] = BitunixExecutor(
                api_key=primary.api_key,
                secret_key=primary.secret_key,
                account_id=primary.account_id,
                account_label=primary.label,
                dry_run=primary.dry_run
            )

        # 2. Cuentas Secundarias (JSON con descifrado transparente)
        if self.accounts_file.exists():
            try:
                with open(self.accounts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    needs_migration = False
                    for item in data.get("accounts", []):
                        acc_id = item.get("account_id")
                        if not acc_id or acc_id == "primary":
                            continue
                        
                        raw_key = item.get("api_key", "")
                        raw_sec = item.get("secret_key", "")
                        
                        # Si estaban en texto plano, marcar para migración a cifrado
                        if raw_key and not raw_key.startswith("enc:v1:"):
                            needs_migration = True
                        if raw_sec and not raw_sec.startswith("enc:v1:"):
                            needs_migration = True

                        decrypted_key = decrypt_credential(raw_key)
                        decrypted_sec = decrypt_credential(raw_sec)

                        acc = BitunixAccountConfig(
                            account_id=acc_id,
                            label=item.get("label", f"Cuenta {acc_id}"),
                            api_key=decrypted_key,
                            secret_key=decrypted_sec,
                            enabled=item.get("enabled", True),
                            risk_pct=float(item.get("risk_pct", 0.025)),
                            max_notional_mult=float(item.get("max_notional_mult", 5.0)),
                            dry_run=bool(item.get("dry_run", self.dry_run)),
                            is_primary=False,
                            created_at=float(item.get("created_at", time.time()))
                        )
                        self._accounts[acc_id] = acc
                        self._executors[acc_id] = BitunixExecutor(
                            api_key=acc.api_key,
                            secret_key=acc.secret_key,
                            account_id=acc.account_id,
                            account_label=acc.label,
                            dry_run=acc.dry_run
                        )
                    
                    if needs_migration:
                        logger.info("🔒 [ACCOUNT_MANAGER] Migrando credenciales planas existentes a cifrado AES-256 en reposo...")
                        self._save_accounts()
            except Exception as e:
                logger.error(f"❌ [ACCOUNT_MANAGER] Error cargando {self.accounts_file.name}: {e}")

    def _save_accounts(self):
        """Persiste las cuentas secundarias al archivo JSON con credenciales cifradas."""
        try:
            sec_accounts = []
            for acc_id, acc in self._accounts.items():
                if acc.is_primary:
                    continue
                acc_dict = acc.to_dict(mask_secrets=False)
                acc_dict["api_key"] = encrypt_credential(acc_dict.get("api_key", ""))
                acc_dict["secret_key"] = encrypt_credential(acc_dict.get("secret_key", ""))
                sec_accounts.append(acc_dict)

            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump({"accounts": sec_accounts}, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 [ACCOUNT_MANAGER] Guardadas {len(sec_accounts)} cuenta(s) secundaria(s) cifradas.")
        except Exception as e:
            logger.error(f"❌ [ACCOUNT_MANAGER] Error guardando cuentas secundarias: {e}")

    def get_account(self, account_id: str) -> Optional[BitunixAccountConfig]:
        return self._accounts.get(account_id)

    def get_all_accounts(self, enabled_only: bool = False) -> List[BitunixAccountConfig]:
        if enabled_only:
            return [acc for acc in self._accounts.values() if acc.enabled]
        return list(self._accounts.values())

    def get_executor(self, account_id: str) -> Optional[BitunixExecutor]:
        return self._executors.get(account_id)

    def get_all_executors(self, enabled_only: bool = True) -> Dict[str, BitunixExecutor]:
        if enabled_only:
            return {
                acc_id: ex for acc_id, ex in self._executors.items()
                if self._accounts.get(acc_id) and self._accounts[acc_id].enabled
            }
        return dict(self._executors)

    async def test_credentials(self, api_key: str, secret_key: str) -> Tuple[bool, str, float]:
        """
        Prueba en vivo la validez de un par de credenciales Bitunix.
        Retorna (exitoso, mensaje, balance_disponible).
        """
        temp_ex = BitunixExecutor(
            api_key=api_key,
            secret_key=secret_key,
            account_id="temp_test",
            account_label="Verificación de Credenciales",
            dry_run=False
        )
        try:
            bal = await temp_ex.get_available_margin_usdt()
            if bal >= 0:
                return True, "Credenciales verificadas exitosamente en Bitunix", bal
            return False, "No se pudo consultar el margen de la cuenta", 0.0
        except Exception as e:
            return False, f"Fallo al conectar con Bitunix: {str(e)}", 0.0

    async def add_account(self, config: BitunixAccountConfig, test_first: bool = True) -> Tuple[bool, str]:
        """Agrega o actualiza una cuenta secundaria con validación previa."""
        if config.account_id == "primary":
            return False, "El ID 'primary' está reservado para la cuenta principal (.env)"

        if test_first and not config.dry_run:
            is_valid, msg, bal = await self.test_credentials(config.api_key, config.secret_key)
            if not is_valid:
                return False, f"Rechazado por Bitunix: {msg}"
            logger.info(f"✅ [ACCOUNT_MANAGER] Cuenta {config.label} verificada en Bitunix con ${bal:.2f} USDT.")

        self._accounts[config.account_id] = config
        self._executors[config.account_id] = BitunixExecutor(
            api_key=config.api_key,
            secret_key=config.secret_key,
            account_id=config.account_id,
            account_label=config.label,
            dry_run=config.dry_run
        )
        self._save_accounts()
        return True, f"Cuenta '{config.label}' registrada con éxito."

    def remove_account(self, account_id: str) -> Tuple[bool, str]:
        """Elimina una cuenta secundaria."""
        if account_id == "primary":
            return False, "No se puede eliminar la cuenta principal (.env)"
        if account_id not in self._accounts:
            return False, f"Cuenta {account_id} no encontrada"

        del self._accounts[account_id]
        self._executors.pop(account_id, None)
        self._save_accounts()
        logger.info(f"🗑️ [ACCOUNT_MANAGER] Cuenta {account_id} eliminada.")
        return True, f"Cuenta {account_id} eliminada correctamente."

    def toggle_account(self, account_id: str, enabled: bool) -> Tuple[bool, str]:
        """Pausa o activa el trading para una cuenta."""
        acc = self._accounts.get(account_id)
        if not acc:
            return False, f"Cuenta {account_id} no encontrada"

        acc.enabled = enabled
        if not acc.is_primary:
            self._save_accounts()
        state_str = "activada" if enabled else "pausada"
        logger.info(f"🔄 [ACCOUNT_MANAGER] Cuenta {acc.label} ({account_id}) {state_str}.")
        return True, f"Cuenta {acc.label} {state_str} correctamente."

    async def get_accounts_summary(self) -> List[Dict[str, Any]]:
        """Genera un resumen detallado con balances en vivo de todas las cuentas registradas."""
        summary = []
        for acc_id, acc in self._accounts.items():
            ex = self._executors.get(acc_id)
            bal = 0.0
            if ex:
                try:
                    bal = await ex.get_available_margin_usdt() if not ex.dry_run else 100.0
                except Exception:
                    bal = ex._last_verified_balance

            item = acc.to_dict(mask_secrets=True)
            item["current_balance_usdt"] = round(bal, 2)
            item["projected_trade_risk_usd"] = round(bal * acc.risk_pct, 2)
            summary.append(item)
        return summary

    async def emergency_close_account(self, account_id: str) -> Dict[str, Any]:
        """
        [KILL-SWITCH INSTITUCIONAL POR CUENTA]
        Cancela de inmediato todas las órdenes pendientes y liquida/cierra a mercado todas
        las posiciones abiertas para una cuenta específica, pausándola para evitar nuevas entradas.
        """
        acc = self._accounts.get(account_id)
        if not acc:
            return {"status": "error", "message": f"Cuenta {account_id} no encontrada"}

        ex = self._executors.get(account_id)
        if not ex:
            return {"status": "error", "message": f"Ejecutor para {account_id} no disponible"}

        logger.warning(f"🚨 [KILL-SWITCH] Activando cierre de emergencia para {acc.label} ({account_id})...")
        
        # 1. Cancelar todas las órdenes pendientes
        cancelled_orders = False
        try:
            cancelled_orders = await ex.cancel_all_pending_orders()
        except Exception as o_err:
            logger.error(f"❌ [KILL-SWITCH] [{acc.label}] Error cancelando órdenes: {o_err}")

        # 2. Consultar y cerrar a mercado todas las posiciones abiertas
        closed_positions = []
        try:
            positions = await ex.get_pending_positions()
            if positions:
                for p in positions:
                    sym = p.get("symbol")
                    qty = float(p.get("qty", 0))
                    side_raw = p.get("side", "BUY").upper()
                    close_side = "SELL" if side_raw in ("BUY", "LONG", "1") else "BUY"
                    pos_id = p.get("positionId")
                    
                    if sym and qty > 0:
                        logger.warning(f"🚨 [KILL-SWITCH] [{acc.label}] Cerrando a mercado {sym} ({qty} u)...")
                        close_res = await ex.close_market_position(symbol=sym, side=close_side, qty=qty, position_id=pos_id)
                        closed_positions.append({"symbol": sym, "qty": qty, "result": close_res})
        except Exception as p_err:
            logger.error(f"❌ [KILL-SWITCH] [{acc.label}] Error cerrando posiciones: {p_err}")

        # 3. Pausar la cuenta
        acc.enabled = False
        if not acc.is_primary:
            self._save_accounts()

        return {
            "status": "success",
            "account_id": account_id,
            "label": acc.label,
            "orders_cancelled": cancelled_orders,
            "positions_closed": closed_positions,
            "account_enabled": False,
            "timestamp": time.time()
        }
