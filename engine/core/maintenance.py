import os
import sys
import time
import glob
import logging
import sqlite3

logger = logging.getLogger("slingshot.maintenance")

DB_PATH = r"C:\Slingshot\data\slingshot.db"
MAX_LOG_SIZE_MB = 15.0
MAX_BACKUP_COUNT = 5

def setup_sqlite_wal(db_path: str = DB_PATH) -> bool:
    """Configura pragmas de alto rendimiento y concurrencia (WAL mode) en SQLite."""
    try:
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode = WAL;")
            res = cur.fetchone()
            cur.execute("PRAGMA synchronous = NORMAL;")
            cur.execute("PRAGMA temp_store = MEMORY;")
            cur.execute("PRAGMA cache_size = -64000;")
            logger.info(f"💾 [SQLITE WAL] Base de datos configurada en modo {res[0]} (synchronous=NORMAL)")
            return True
    except Exception as e:
        logger.error(f"❌ [SQLITE WAL ERROR] No se pudo configurar WAL en {db_path}: {e}")
        return False

def vacuum_sqlite(db_path: str = DB_PATH) -> bool:
    """Ejecuta un checkpoint de WAL y compacta la base de datos."""
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.execute("VACUUM;")
            logger.info("🧹 [SQLITE VACUUM] Base de datos compactada y WAL checkpoint ejecutado con éxito.")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ [SQLITE VACUUM ERROR] Error al compactar SQLite: {e}")
        return False

def rotate_single_log(file_path: str, max_size_mb: float = MAX_LOG_SIZE_MB, max_backups: int = MAX_BACKUP_COUNT) -> bool:
    """Rota y trunca un archivo de log si supera el tamaño máximo sin romper file descriptors abiertos."""
    try:
        if not os.path.exists(file_path):
            return False
            
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb < max_size_mb:
            return False
            
        logger.info(f"🔄 [LOG ROTATOR] Rotando log {file_path} ({size_mb:.2f} MB > {max_size_mb} MB)...")
        
        # Eliminar backup más antiguo si excede max_backups
        oldest_backup = f"{file_path}.{max_backups}"
        if os.path.exists(oldest_backup):
            try:
                os.remove(oldest_backup)
            except Exception:
                pass
                
        # Desplazar backups existentes: .4 -> .5, .3 -> .4, etc.
        for i in range(max_backups - 1, 0, -1):
            s_fn = f"{file_path}.{i}"
            d_fn = f"{file_path}.{i + 1}"
            if os.path.exists(s_fn):
                try:
                    if os.path.exists(d_fn):
                        os.remove(d_fn)
                    os.rename(s_fn, d_fn)
                except Exception:
                    pass
                    
        # Copiar contenido actual a .1
        b1 = f"{file_path}.1"
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as src, \
                 open(b1, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        except Exception:
            pass
            
        # Truncar archivo activo de forma segura en caliente
        with open(file_path, "w", encoding="utf-8") as f:
            f.truncate(0)
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [LOG ROTATOR] Log rotado limpiamente tras alcanzar {size_mb:.2f} MB\n")
            
        logger.info(f"✅ [LOG ROTATOR] Log rotado y truncado exitosamente: {file_path}")
        return True
    except Exception as e:
        logger.error(f"❌ [LOG ROTATOR ERROR] Fallo rotando {file_path}: {e}")
        return False

def rotate_all_slingshot_logs():
    """Escanea y rota todos los logs principales del ecosistema Slingshot."""
    target_logs = [
        r"C:\Slingshot\slingshot_service.log",
        r"C:\Slingshot\tmp\logs\slingshot.log",
        r"C:\Slingshot\slingshot_stderr.log",
        r"C:\Slingshot\slingshot_stdout.log",
    ]
    rotated_count = 0
    for p in target_logs:
        if rotate_single_log(p):
            rotated_count += 1
    return rotated_count
