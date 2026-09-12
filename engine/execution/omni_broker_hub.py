"""
engine/execution/omni_broker_hub.py — Omni-Broker Prop-Firm Scaling Hub
=======================================================================
Hub unificado de enrutamiento y orquestación multi-broker para Slingshot:
1. Despacha operaciones cripto a Bitunix Futures con margen dinámico (SOP-41/58).
2. Despacha operaciones TradFi a MetaTrader 5 (FTMO Swing 100k) respetando FTMO Guardian.
3. Provee la interfaz abstracta 'BaseBrokerAdapter' para conectar nuevas firmas prop
   (FundedNext, Topstep, Apex Trader) permitiendo escalar de $100k a $1M+ USD.
4. Conecta el optimizador Hierarchical Risk Parity (HRP) para sizing multiactivo.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from engine.core.logger import logger
from engine.risk.ftmo_guardian import ftmo_guardian
from engine.risk.hrp_allocator import hrp_allocator
from engine.execution.bitunix_executor import BitunixExecutor
from engine.execution.mt5_bridge import mt5_bridge


class OmniBrokerHub:
    """
    Orquestador Central Multi-Broker y Multi-Firma Prop.
    """

    def __init__(self):
        self._crypto_executors: Dict[str, BitunixExecutor] = {}
        self._tradfi_bridge = mt5_bridge
        self._hrp_weights: Dict[str, float] = {}

    def register_crypto_executor(self, account_id: str, executor: BitunixExecutor):
        """Registra una instancia de ejecución cripto (ej. cuenta principal o subcuentas)."""
        self._crypto_executors[account_id] = executor
        logger.info(f"🌐 [OMNI-BROKER] Ejecutor cripto registrado: '{account_id}'")

    def update_hrp_weights(self, weights: Dict[str, float]):
        """Actualiza el vector de ponderaciones HRP de la cartera."""
        self._hrp_weights = dict(weights)
        logger.info(f"⚖️ [OMNI-BROKER] Pesos HRP sincronizados ({len(weights)} activos).")

    def get_target_broker(self, symbol: str) -> str:
        """Determina si un activo corresponde al circuito Cripto (Bitunix) o TradFi (FTMO MT5)."""
        sym = symbol.upper().replace("/", "")
        tradfi_symbols = [
            "XAUUSD", "XAGUSD", "GOLD", "SILVER",
            "US100", "US500", "US30", "GER40", "NAS100", "SPX500",
            "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "GBPJPY", "AUDUSD"
        ]
        if any(sym == s or sym.startswith(s) for s in tradfi_symbols):
            return "FTMO_MT5"
        return "BITUNIX_CRYPTO"

    def calculate_allocated_risk(self, symbol: str, account_type: str, base_risk_usd: float) -> float:
        """
        Calcula el riesgo final en dólares modulado por Paridad Jerárquica (HRP)
        y blindado por los límites máximos de FTMO Guardian.
        """
        # 1. Modulación HRP
        risk = hrp_allocator.calculate_trade_risk_usd(symbol, base_risk_usd, self._hrp_weights)

        # 2. Si es FTMO, respetar techo institucional absoluto (0.75% de la cuenta = $750)
        if account_type == "FTMO_MT5":
            max_allowed = getattr(ftmo_guardian, "risk_per_trade_usd", 750.0)
            risk = min(risk, max_allowed)

        return round(risk, 2)

    async def get_consolidated_equity(self) -> Dict[str, Any]:
        """
        Retorna la equidad consolidada de todas las cuentas conectadas (Cripto + TradFi).
        """
        crypto_equity = 0.0
        crypto_details = {}

        for acc_id, executor in self._crypto_executors.items():
            try:
                telem = await executor.get_account_telemetry_summary()
                eq = float(telem.get("equity", 0.0))
                crypto_equity += eq
                crypto_details[acc_id] = eq
            except Exception as e:
                logger.debug(f"[OMNI-BROKER] Error consultando telemetría de {acc_id}: {e}")

        # Equidad TradFi (FTMO MT5)
        tradfi_equity = getattr(ftmo_guardian, "current_equity", 100000.0)
        tradfi_balance = getattr(ftmo_guardian, "account_size", 100000.0)

        total_equity = crypto_equity + tradfi_equity

        return {
            "total_portfolio_equity": round(total_equity, 2),
            "crypto_pool": {
                "total_equity": round(crypto_equity, 2),
                "accounts": crypto_details
            },
            "tradfi_pool": {
                "ftmo_account_login": getattr(self._tradfi_bridge, "account_login", "1514537587"),
                "equity": round(tradfi_equity, 2),
                "balance": round(tradfi_balance, 2),
                "daily_loss_usd": getattr(ftmo_guardian, "daily_loss_usd", 0.0),
                "is_daily_lockout": getattr(ftmo_guardian, "is_daily_lockout", False)
            },
            "hrp_assets_monitored": len(self._hrp_weights),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


omni_broker_hub = OmniBrokerHub()
