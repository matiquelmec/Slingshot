import os
import time
import sqlite3
import pytest
import tempfile
import threading
from engine.core.maintenance import setup_sqlite_wal, vacuum_sqlite, rotate_single_log

def test_sqlite_wal_mode_and_concurrency():
    """Valida la activación del modo WAL y la lectura/escritura concurrente sin bloqueos."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db = tf.name
    
    try:
        assert setup_sqlite_wal(temp_db) is True
        
        with sqlite3.connect(temp_db) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            mode = cur.fetchone()[0]
            assert mode.lower() == "wal"
            
            cur.execute("CREATE TABLE test_concurrency (id INTEGER PRIMARY KEY, val TEXT);")
            conn.commit()

        # Simular lectura y escritura concurrente en hilos separados
        def writer():
            c = sqlite3.connect(temp_db)
            for i in range(20):
                c.execute("INSERT INTO test_concurrency (val) VALUES (?)", (f"v_{i}",))
                c.commit()
            c.close()

        def reader():
            c = sqlite3.connect(temp_db)
            for _ in range(20):
                c.execute("SELECT count(*) FROM test_concurrency;").fetchone()
            c.close()

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert vacuum_sqlite(temp_db) is True
    finally:
        for ext in ["", "-wal", "-shm"]:
            p = temp_db + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

def test_log_rotator_truncates_and_archives():
    """Valida que un log que supere el umbral se archive y su archivo activo se trunque limpiamente."""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w", encoding="utf-8") as tf:
        temp_log = tf.name
        # Escribir 100 KB de texto simulado
        tf.write("A" * 102400)
    
    try:
        # Umbral bajo (0.05 MB = ~51 KB) para activar rotación en test
        rotated = rotate_single_log(temp_log, max_size_mb=0.05, max_backups=3)
        assert rotated is True
        
        # Debe existir el archivo de backup .1
        b1 = f"{temp_log}.1"
        assert os.path.exists(b1)
        assert os.path.getsize(b1) >= 102400
        
        # El archivo activo debe ser pequeño tras el truncado
        assert os.path.getsize(temp_log) < 500
        with open(temp_log, "r", encoding="utf-8") as f:
            content = f.read()
            assert "[LOG ROTATOR]" in content
    finally:
        for p in [temp_log, f"{temp_log}.1", f"{temp_log}.2"]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
