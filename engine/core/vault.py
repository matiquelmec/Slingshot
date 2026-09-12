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
from datetime import datetime, timezone
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

            # 4. Tabla de Rendimiento Transaccional SSoT (Tear Sheets SOP-60)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS closed_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                pnl_r REAL NOT NULL,
                pnl_usd REAL NOT NULL,
                exit_reason TEXT NOT NULL,
                closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_closed_trades_acc_time ON closed_trades(account_id, closed_at);")

            # 5. Tabla de Historial de Régimen Cuantitativo (SOP-63 Regime Agent)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS regime_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                regime TEXT NOT NULL,
                risk_multiplier REAL NOT NULL,
                confidence REAL NOT NULL,
                details_json TEXT NOT NULL,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_regime_eval ON regime_history(evaluated_at);")

            # 6. Tabla de Atribución de Factores de Confluencia (SOP-74 Bayesian Calibrator)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS confluence_factor_attribution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT,
                symbol TEXT,
                factor_name TEXT NOT NULL,
                was_confirmed INTEGER NOT NULL,
                is_win INTEGER NOT NULL,
                pnl_r REAL NOT NULL,
                timestamp REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_factor_ts ON confluence_factor_attribution(factor_name, timestamp);")

            # 7. Tabla de Pesos Bayesianos Calibrados (SOP-74 Bayesian Calibrator)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS confluence_factor_weights (
                factor_name TEXT PRIMARY KEY,
                base_weight REAL NOT NULL,
                calibrated_weight REAL NOT NULL,
                win_rate REAL NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                sample_size INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 8. Tablas de Análisis Post-Mortem y Vetos Tácticos (SOP-76 NVIDIA NIM)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_mortem_vetoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                condition_tag TEXT NOT NULL,
                reason TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_veto_sym_exp ON post_mortem_vetoes(symbol, expires_at);")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_mortem_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                pnl_usd REAL NOT NULL,
                loss_category TEXT NOT NULL,
                causal_analysis TEXT NOT NULL,
                preventive_rule TEXT NOT NULL,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def vacuum_and_purge_maintenance(self, retention_days: int = 7) -> Dict[str, int]:
        """
        [SOP-22 INFINITE RESILIENCE]
        Mantenimiento periódico de ciclo infinito para SQLite WAL:
        1. Purga despachos viejos (> retention_days).
        2. Ejecuta PRAGMA incremental_vacuum / optimize para evitar fragmentación.
        """
        deleted_stats = {"telegram_dispatches": 0}
        try:
            with self._get_connection() as conn:
                cutoff = time.time() - (retention_days * 86400)
                cur = conn.execute("DELETE FROM telegram_dispatches WHERE timestamp < ?", (cutoff,))
                deleted_stats["telegram_dispatches"] = cur.rowcount
                conn.commit()
                # Optimizar índices y compactar espacio WAL
                conn.execute("PRAGMA optimize;")
                conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            logger.info(f"🧹 [VAULT MAINTENANCE] Mantenimiento ejecutado: {deleted_stats['telegram_dispatches']} registros purgados.")
        except Exception as e:
            logger.error(f"❌ [VAULT MAINTENANCE] Error en mantenimiento de SQLite: {e}")
        return deleted_stats

    # ── MÉTODOS DE RENDIMIENTO CUANTITATIVO (SOP-60 TEAR SHEETS) ──────────────

    def record_closed_trade(
        self,
        account_id: str,
        symbol: str,
        side: str,
        pnl_r: float,
        pnl_usd: float = 0.0,
        exit_reason: str = "TP",
        checklist: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """Registra un trade completado en la bóveda transaccional y alimenta la calibración bayesiana."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO closed_trades (account_id, symbol, side, pnl_r, pnl_usd, exit_reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (account_id, symbol.upper(), side.upper(), float(pnl_r), float(pnl_usd), exit_reason))
            trade_id = cursor.lastrowid
            conn.commit()

        if checklist:
            try:
                from engine.core.bayesian_confluence import bayesian_calibrator
                is_win = float(pnl_r) > 0.0
                bayesian_calibrator.record_trade_attribution(
                    trade_id=str(trade_id),
                    symbol=symbol,
                    active_checklist=checklist,
                    is_win=is_win,
                    pnl_r=float(pnl_r)
                )
            except Exception as b_err:
                logger.debug(f"[VAULT] Error actualizando calibrador bayesiano en record_closed_trade: {b_err}")

        return trade_id

    def get_closed_trades(self, account_id: Optional[str] = None, since_timestamp: Optional[float] = None) -> List[Dict[str, Any]]:
        """Recupera los trades cerrados para el cálculo de métricas financieras."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, account_id, symbol, side, pnl_r, pnl_usd, exit_reason, closed_at FROM closed_trades WHERE 1=1"
            params = []
            if account_id:
                query += " AND account_id = ?"
                params.append(account_id)
            if since_timestamp is not None:
                since_iso = datetime.fromtimestamp(since_timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                query += " AND closed_at >= ?"
                params.append(since_iso)
            query += " ORDER BY id ASC"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "account_id": r[1],
                    "symbol": r[2],
                    "side": r[3],
                    "pnl_r": r[4],
                    "pnl_usd": r[5],
                    "exit_reason": r[6],
                    "closed_at": r[7]
                }
                for r in rows
            ]

    # ── MÉTODOS DE RÉGIMEN CUANTITATIVO (SOP-63 REGIME AGENT) ────────────────

    def record_regime_state(self, regime: str, risk_multiplier: float, confidence: float, details: Dict[str, Any]) -> None:
        """Persiste el estado de régimen analizado por SlingshotRegimeAgent."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO regime_history (regime, risk_multiplier, confidence, details_json)
            VALUES (?, ?, ?, ?)
            """, (regime, risk_multiplier, confidence, json.dumps(details)))
            conn.commit()

    def get_latest_regime_state(self) -> Optional[Dict[str, Any]]:
        """Recupera el último régimen evaluado y su multiplicador táctico."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT regime, risk_multiplier, confidence, details_json, evaluated_at
            FROM regime_history
            ORDER BY id DESC
            LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "regime": row[0],
                "risk_multiplier": float(row[1]),
                "confidence": float(row[2]),
                "details": json.loads(row[3]) if row[3] else {},
                "evaluated_at": row[4]
            }

    # ── MÉTODOS DE CALIBRACIÓN BAYESIANA (SOP-74) ─────────────────────────────

    def record_factor_attributions(
        self,
        trade_id: str,
        symbol: str,
        confirmed_factors: List[str],
        unconfirmed_factors: List[str],
        is_win: bool,
        pnl_r: float
    ) -> None:
        """Registra la presencia o ausencia de factores en un trade cerrado."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            win_val = 1 if is_win else 0
            
            for factor in confirmed_factors:
                cursor.execute("""
                INSERT INTO confluence_factor_attribution 
                (trade_id, symbol, factor_name, was_confirmed, is_win, pnl_r, timestamp)
                VALUES (?, ?, ?, 1, ?, ?, ?)
                """, (trade_id, symbol.upper(), factor, win_val, float(pnl_r), now))
                
            for factor in unconfirmed_factors:
                cursor.execute("""
                INSERT INTO confluence_factor_attribution 
                (trade_id, symbol, factor_name, was_confirmed, is_win, pnl_r, timestamp)
                VALUES (?, ?, ?, 0, ?, ?, ?)
                """, (trade_id, symbol.upper(), factor, win_val, float(pnl_r), now))
            conn.commit()

    def get_factor_rolling_stats(self, rolling_window: int = 50) -> Dict[str, Dict[str, Any]]:
        """
        Recupera el recuento de aciertos/fallos para cada factor en los últimos N trades
        donde dicho factor estuvo confirmado.
        """
        stats = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT factor_name FROM confluence_factor_attribution")
            factors = [r[0] for r in cursor.fetchall()]
            
            for factor in factors:
                cursor.execute("""
                SELECT is_win FROM confluence_factor_attribution
                WHERE factor_name = ? AND was_confirmed = 1
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """, (factor, rolling_window))
                rows = cursor.fetchall()
                wins = sum(1 for r in rows if r[0] == 1)
                losses = sum(1 for r in rows if r[0] == 0)
                stats[factor] = {"wins": wins, "losses": losses, "count": len(rows)}
        return stats

    def save_factor_weights(self, weights_data: List[Dict[str, Any]]) -> None:
        """Persiste los pesos calibrados en SQLite WAL."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for item in weights_data:
                cursor.execute("""
                INSERT INTO confluence_factor_weights 
                (factor_name, base_weight, calibrated_weight, win_rate, wins, losses, sample_size, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(factor_name) DO UPDATE SET
                    base_weight = excluded.base_weight,
                    calibrated_weight = excluded.calibrated_weight,
                    win_rate = excluded.win_rate,
                    wins = excluded.wins,
                    losses = excluded.losses,
                    sample_size = excluded.sample_size,
                    updated_at = CURRENT_TIMESTAMP;
                """, (
                    item["factor_name"],
                    float(item["base_weight"]),
                    float(item["calibrated_weight"]),
                    float(item["win_rate"]),
                    int(item["wins"]),
                    int(item["losses"]),
                    int(item["sample_size"])
                ))
            conn.commit()

    def load_factor_weights(self) -> Dict[str, float]:
        """Carga los últimos pesos calibrados guardados."""
        weights = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT factor_name, calibrated_weight FROM confluence_factor_weights")
            for row in cursor.fetchall():
                weights[row[0]] = float(row[1])
        return weights

    # ── MÉTODOS DE VETO POST-MORTEM (SOP-76 NVIDIA NIM) ────────────────────────

    def add_post_mortem_veto(self, symbol: str, condition_tag: str, reason: str, duration_seconds: int = 43200) -> None:
        """Registra un veto temporal para un activo tras análisis causal de pérdida."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            expires = now + duration_seconds
            cursor.execute("""
            INSERT INTO post_mortem_vetoes (symbol, condition_tag, reason, expires_at)
            VALUES (?, ?, ?, ?)
            """, (symbol.upper(), condition_tag.upper(), reason, expires))
            conn.commit()

    def is_symbol_vetoed(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """Verifica si un activo tiene un veto temporal activo."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute("""
            SELECT reason, expires_at FROM post_mortem_vetoes
            WHERE symbol = ? AND expires_at > ?
            ORDER BY expires_at DESC LIMIT 1
            """, (symbol.upper(), now))
            row = cursor.fetchone()
            if row:
                remaining_m = int((row[1] - now) / 60)
                return True, f"{row[0]} (Expira en {remaining_m}m)"
            return False, None

    def record_post_mortem_report(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        pnl_usd: float,
        loss_category: str,
        causal_analysis: str,
        preventive_rule: str
    ) -> None:
        """Almacena el reporte completo del análisis causal de IA."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO post_mortem_reports 
            (trade_id, symbol, side, pnl_usd, loss_category, causal_analysis, preventive_rule)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (trade_id, symbol.upper(), side.upper(), float(pnl_usd), loss_category, causal_analysis, preventive_rule))
            conn.commit()

# Instancia global singleton
vault = SlingshotVault()
