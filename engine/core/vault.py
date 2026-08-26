"""
engine/core/vault.py — Bóveda de Persistencia Transaccional SQLite WAL (v21.0)
==============================================================================
Provee almacenamiento ACID de ultra-baja latencia para:
- Registro de despachos y deduplicación de Telegram.
- Persistencia de estados de sesiones y rotación de PDH/PDL.
- Registro de auditoría de órdenes y trades.

Utiliza SQLite con modo Write-Ahead Logging (WAL) para permitir lecturas
concurrentes sin bloqueo y escrituras atómicas resistentes a cortes de energía.
"""
import sqlite3
import time
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from engine.core.logger import logger

_DB_PATH = Path(__file__).parent.parent / "data" / "slingshot_vault.db"

class SlingshotVault:
    """Repositorio transaccional embebido thread-safe para Slingshot Trading."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[Path] = None, *args, **kwargs):
        # Si se especifica un db_path custom (ej: en tests), crear instancia independiente
        if db_path is not None:
            instance = super(SlingshotVault, cls).__new__(cls)
            instance._initialized = False
            return instance

        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SlingshotVault, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[Path] = None):
        if getattr(self, "_initialized", False):
            return
        self.db_path = db_path or _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Crea una conexión con timeout y soporte WAL."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        """Inicializa el esquema de tablas transaccionales."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Tabla de Despachos de Telegram (Anti-Spam Multi-Reinicio)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_dispatches (
                dedup_key TEXT PRIMARY KEY,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_ts ON telegram_dispatches(timestamp);")

            # 2. Tabla de Estados de Sesiones (PDH / PDL / ONH / ONL)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_states (
                symbol TEXT PRIMARY KEY,
                trading_day TEXT NOT NULL,
                pdh REAL,
                pdl REAL,
                onh REAL,
                onl REAL,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 3. Tabla de Auditoría de Trades
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_audit_log (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                tp1 REAL NOT NULL,
                tp2 REAL NOT NULL,
                tp3 REAL NOT NULL,
                lots REAL,
                risk_usd REAL,
                score INTEGER,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
            logger.info(f"🏛️ [VAULT] Base de datos SQLite WAL inicializada en {self.db_path.name}")

    # ── MÉTODOS DE TELEGRAM DISPATCHER ────────────────────────────────────────

    def is_signal_in_cooldown(self, dedup_key: str, current_price: float, cooldown_seconds: int = 1800, max_drift_pct: float = 3.0) -> Tuple[bool, int, float]:
        """
        Verifica si una señal ya fue despachada y sigue en cooldown sin drift de precio significativo.
        Retorna: (is_blocked: bool, elapsed_seconds: int, pct_diff: float)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, price FROM telegram_dispatches WHERE dedup_key = ?", (dedup_key,))
            row = cursor.fetchone()
            if not row:
                return False, 0, 0.0

            last_ts, last_price = float(row[0]), float(row[1])
            now = time.time()
            elapsed = int(now - last_ts)
            pct_diff = abs(current_price - last_price) / last_price * 100.0 if last_price > 0 else 0.0

            if elapsed < cooldown_seconds and pct_diff < max_drift_pct:
                return True, elapsed, pct_diff
            return False, elapsed, pct_diff

    def record_signal_dispatch(self, dedup_key: str, asset: str, direction: str, timeframe: str, price: float):
        """Registra un despacho exitoso de señal de forma atómica."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute("""
            INSERT INTO telegram_dispatches (dedup_key, asset, direction, timeframe, price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dedup_key) DO UPDATE SET
                price = excluded.price,
                timestamp = excluded.timestamp,
                created_at = CURRENT_TIMESTAMP;
            """, (dedup_key, asset, direction, timeframe, price, now))
            conn.commit()

    def purge_old_dispatches(self, retention_hours: int = 24):
        """Elimina registros antiguos para mantener la base de datos ultra liviana."""
        with self._get_connection() as conn:
            cutoff = time.time() - (retention_hours * 3600)
            conn.execute("DELETE FROM telegram_dispatches WHERE timestamp < ?", (cutoff,))
            conn.commit()

    # ── MÉTODOS DE SESSION MANAGER ───────────────────────────────────────────

    def save_session_state(self, symbol: str, trading_day: str, pdh: Optional[float], pdl: Optional[float], onh: Optional[float], onl: Optional[float], state_dict: Dict[str, Any]):
        """Persiste el estado de sesión de un símbolo."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            state_json = json.dumps(state_dict, default=str)
            cursor.execute("""
            INSERT INTO session_states (symbol, trading_day, pdh, pdl, onh, onl, state_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol) DO UPDATE SET
                trading_day = excluded.trading_day,
                pdh = excluded.pdh,
                pdl = excluded.pdl,
                onh = excluded.onh,
                onl = excluded.onl,
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP;
            """, (symbol.upper(), trading_day, pdh, pdl, onh, onl, state_json))
            conn.commit()

    def load_session_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Recupera el estado de sesión guardado para un símbolo."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT state_json FROM session_states WHERE symbol = ?", (symbol.upper(),))
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    return None
            return None

# Instancia global singleton
vault = SlingshotVault()
