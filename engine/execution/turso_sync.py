"""
turso_sync.py — Sincronización Dual-Engine (FastAPI VPS ↔ Turso Cloud)
====================================================================
Módulo institucional de persistencia serverless para Slingshot v10.0.0.
Sincroniza señales cuantitativas y trades ejecutados en Bitunix y MetaTrader 5
hacia la base de datos Turso Cloud (LibSQL) mediante el Pipeline API HTTP v2.

Diseñado con tolerancia a fallos: cualquier latencia o caída temporal de red
nunca bloquea el hilo crítico de ejecución algorítmica ni el socket de órdenes.
"""

import os
import json
import uuid
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import urllib.request
import urllib.error

from engine.core.logger import logger

class TursoSyncManager:
    DEFAULT_TENANT_ID = "tenant-sovereign-apex"
    DEFAULT_USER_ID = "user-apex-trader"

    def __init__(self):
        self.raw_url = os.getenv("TURSO_DATABASE_URL", "")
        self.token = os.getenv("TURSO_AUTH_TOKEN", "")
        self._http_url: Optional[str] = None
        self._is_enabled = False
        self._initialized = False

        self._configure_endpoints()

    def _configure_endpoints(self):
        if not self.raw_url or not self.token:
            # Intentar recargar desde .env o .env.local
            self._load_from_env_files()

        if self.raw_url and self.token:
            # Convertir libsql://... a https://.../v2/pipeline
            clean_url = self.raw_url.replace("libsql://", "https://").rstrip("/")
            if not clean_url.endswith("/v2/pipeline"):
                self._http_url = f"{clean_url}/v2/pipeline"
            else:
                self._http_url = clean_url
            self._is_enabled = True
            logger.info(f"🗄️ [TURSO SYNC] Dual-Engine Bridge activado -> {self._http_url}")
        else:
            logger.warning("⚠️ [TURSO SYNC] TURSO_DATABASE_URL o TURSO_AUTH_TOKEN ausentes. Modo Dual-Engine en espera.")

    def _load_from_env_files(self):
        env_paths = [".env", ".env.local", "../.env"]
        for p in env_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("TURSO_DATABASE_URL="):
                                self.raw_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                            elif line.startswith("TURSO_AUTH_TOKEN="):
                                self.token = line.split("=", 1)[1].strip().strip('"').strip("'")
                except Exception as e:
                    logger.debug(f"[TURSO SYNC] Error leyendo {p}: {e}")

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled and bool(self._http_url)

    def execute_sql(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Ejecuta una sentencia SQL en Turso Cloud vía HTTP Pipeline de forma síncrona/protegida."""
        if not self.is_enabled:
            return {"success": False, "error": "Turso sync disabled"}

        args = []
        if params:
            for p in params:
                if p is None:
                    args.append({"type": "null"})
                elif isinstance(p, int):
                    args.append({"type": "integer", "value": str(p)})
                elif isinstance(p, float):
                    args.append({"type": "float", "value": p})
                elif isinstance(p, bool):
                    args.append({"type": "integer", "value": "1" if p else "0"})
                else:
                    args.append({"type": "text", "value": str(p)})

        payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": sql,
                        "args": args
                    }
                }
            ]
        }

        try:
            req = urllib.request.Request(
                self._http_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "data": data}
        except Exception as err:
            logger.debug(f"[TURSO HTTP ERROR] Error ejecutando SQL: {err}")
            return {"success": False, "error": str(err)}

    async def execute_sql_async(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Ejecuta SQL de forma asíncrona fuera del bucle de eventos principal."""
        return await asyncio.to_thread(self.execute_sql, sql, params)

    def ensure_default_tenant_and_user(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Garantiza la existencia idempotente de la organización y usuario por defecto en Turso."""
        if not self.is_enabled:
            return False

        t_id = tenant_id or self.DEFAULT_TENANT_ID
        u_id = user_id or self.DEFAULT_USER_ID
        now_ts = int(time.time() * 1000)

        # 1. Upsert Tenant
        sql_tenant = (
            "INSERT OR IGNORE INTO tenants (id, name, tier, max_concurrent_positions, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);"
        )
        self.execute_sql(sql_tenant, [t_id, "Slingshot Apex Sovereign", "institutional", 10, "active", now_ts, now_ts])

        # 2. Upsert User
        sql_user = (
            "INSERT OR IGNORE INTO users (id, tenant_id, email, role, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?);"
        )
        self.execute_sql(sql_user, [u_id, t_id, "trader@slingshot.trade", "admin", now_ts, now_ts])

        self._initialized = True
        return True

    def record_signal(
        self,
        signal: Dict[str, Any],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """Registra una señal cuantitativa generada por el motor analítico."""
        if not self.is_enabled:
            return None

        if not self._initialized:
            self.ensure_default_tenant_and_user(tenant_id, user_id)

        t_id = tenant_id or self.DEFAULT_TENANT_ID
        u_id = user_id or self.DEFAULT_USER_ID
        sig_id = str(signal.get("id") or uuid.uuid4())
        asset = str(signal.get("asset") or signal.get("symbol") or "BTCUSDT").upper()
        direction = str(signal.get("direction") or signal.get("signal_type") or "LONG").upper()
        timeframe = str(signal.get("timeframe") or signal.get("interval") or "15m")
        entry_price = float(signal.get("entry_price") or signal.get("price") or 0.0)
        stop_loss = float(signal.get("stop_loss") or 0.0)
        tp1 = float(signal.get("take_profit_1") or signal.get("tp1") or 0.0) or None
        tp2 = float(signal.get("take_profit_2") or signal.get("tp2") or 0.0) or None
        tp3 = float(signal.get("take_profit_3") or signal.get("tp3") or 0.0) or None
        score = float(signal.get("confluence_score") or signal.get("score") or 0.0)
        ker = float(signal.get("ker_value") or signal.get("ker") or 0.0)
        status = str(signal.get("status") or "PENDING").upper()
        now_ts = int(time.time() * 1000)

        sql = (
            "INSERT INTO signals (id, tenant_id, user_id, asset, direction, timeframe, "
            "entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, "
            "confluence_score, ker_value, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
        )

        res = self.execute_sql(sql, [
            sig_id, t_id, u_id, asset, direction, timeframe,
            entry_price, stop_loss, tp1, tp2, tp3,
            score, ker, status, now_ts
        ])

        if res.get("success"):
            logger.info(f"📡 [TURSO SYNC] Señal {asset} {direction} registrada en nube Turso (ID: {sig_id[:8]})")
            return sig_id
        return None

    def record_trade(
        self,
        trade: Dict[str, Any],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """Registra un trade ejecutado en Bitunix o FTMO en la tabla 'trades' de Turso."""
        if not self.is_enabled:
            return None

        if not self._initialized:
            self.ensure_default_tenant_and_user(tenant_id, user_id)

        t_id = tenant_id or self.DEFAULT_TENANT_ID
        u_id = user_id or self.DEFAULT_USER_ID
        trade_id = str(trade.get("id") or trade.get("order_id") or trade.get("position_id") or uuid.uuid4())
        symbol = str(trade.get("symbol") or "BTCUSDT").upper()
        side = str(trade.get("side") or "BUY").upper()
        if side in ("LONG", "BUY"):
            side = "BUY"
        else:
            side = "SELL"

        entry_price = float(trade.get("entry_price") or trade.get("price") or 0.0)
        exit_price = float(trade["exit_price"]) if trade.get("exit_price") is not None else None
        qty = float(trade.get("quantity") or trade.get("qty") or 0.0)
        pnl = float(trade.get("pnl") or trade.get("unrealized_pnl") or 0.0)
        pnl_pct = float(trade.get("pnl_percent") or trade.get("unrealized_pnl_pct") or 0.0)
        status = str(trade.get("status") or "OPEN").upper()
        now_ts = int(time.time() * 1000)

        sql = (
            "INSERT OR REPLACE INTO trades (id, tenant_id, user_id, symbol, side, entry_price, "
            "exit_price, quantity, pnl, pnl_percent, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
        )

        res = self.execute_sql(sql, [
            trade_id, t_id, u_id, symbol, side, entry_price,
            exit_price, qty, pnl, pnl_pct, status, now_ts
        ])

        if res.get("success"):
            logger.info(f"💎 [TURSO SYNC] Trade {symbol} ({side}) sincronizado en Turso Cloud (ID: {trade_id[:8]})")
            return trade_id
        return None

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Marca un trade como cerrado en Turso con sus métricas finales de PnL."""
        if not self.is_enabled:
            return False

        t_id = tenant_id or self.DEFAULT_TENANT_ID
        now_ts = int(time.time() * 1000)

        sql = (
            "UPDATE trades SET exit_price = ?, pnl = ?, pnl_percent = ?, "
            "status = 'CLOSED', closed_at = ? WHERE id = ? AND tenant_id = ?;"
        )

        res = self.execute_sql(sql, [exit_price, pnl, pnl_percent, now_ts, trade_id, t_id])
        return bool(res.get("success"))

    def dispatch_trade_async(self, trade: Dict[str, Any]):
        """Envía el registro del trade a Turso en segundo plano sin esperar respuesta."""
        if not self.is_enabled:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(asyncio.to_thread(self.record_trade, trade))
        except RuntimeError:
            # Si no hay loop en ejecución, invocar síncrono
            self.record_trade(trade)

# Instancia global singleton para exportación directa
turso_sync = TursoSyncManager()
