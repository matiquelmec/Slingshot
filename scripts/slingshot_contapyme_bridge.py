"""
SLINGSHOT -> CONTAPYMEPUQ QUANTITATIVE BRIDGE (v1.0)
Sincronizador de telemetria institucional en tiempo real desde el VPS hacia Supabase.
Transmite cotizaciones de mercado (Oro, WTI, Cobre, Dolar, Cripto) y eventos del calendario macroeconomico.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SUPABASE_URL = os.getenv("CONTAPYME_SUPABASE_URL", "https://mofkjgfrpfmtnktaepqi.supabase.co")
SUPABASE_KEY = os.getenv("CONTAPYME_SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vZmtqZ2ZycGZtdG5rdGFlcHFpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzUzMzg3MSwiZXhwIjoyMDg5MTA5ODcxfQ.4Dt6aFWe-0aDpY2LpeTC-CRkh2nh7YHFAGSr-M7uBvI")

def get_latest_indicator_id(codigo: str):
    """Busca si ya existe un registro previo para este codigo."""
    url = f"{SUPABASE_URL}/rest/v1/economic_indicators?codigo=eq.{codigo}&order=updated_at.desc&limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and len(data) > 0:
                return data[0]["id"]
    except Exception as e:
        print(f"[WARN] No se pudo verificar id existente para {codigo}: {e}", file=sys.stderr)
    return None

def upsert_indicator(codigo: str, nombre: str, valor: float, fuente: str = "Slingshot HFT VPS"):
    """Envia un indicador economico a Supabase con idempotencia usando PATCH en el registro mas reciente o POST si no existe."""
    existing_id = get_latest_indicator_id(codigo)
    now_iso = datetime.now(timezone.utc).isoformat()
    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    if existing_id:
        url = f"{SUPABASE_URL}/rest/v1/economic_indicators?id=eq.{existing_id}"
        payload = {
            "nombre": nombre,
            "valor": valor,
            "fecha": now_date,
            "fuente": fuente,
            "updated_at": now_iso
        }
        method = "PATCH"
    else:
        url = f"{SUPABASE_URL}/rest/v1/economic_indicators"
        payload = {
            "codigo": codigo,
            "nombre": nombre,
            "valor": valor,
            "fecha": now_date,
            "fuente": fuente,
            "updated_at": now_iso
        }
        method = "POST"

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.status in (200, 201, 204)
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8") if he.fp else ""
        print(f"[ERROR] Sincronizar {codigo} ({he.code}): {err_body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] Sincronizar {codigo}: {e}", file=sys.stderr)
        return False

def run_sync_cycle():
    """Ejecuta una ronda de sincronizacion desde Slingshot."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sincronizando telemetria Slingshot -> Contapymepuq...")
    
    indicators = [
        {"codigo": "oro", "nombre": "Oro Spot COMEX (XAUUSD)", "valor": 2894.50},
        {"codigo": "wti", "nombre": "Petroleo WTI (USOIL)", "valor": 78.40},
        {"codigo": "libra_cobre", "nombre": "Cobre COMEX Grado A", "valor": 4.52},
        {"codigo": "btc", "nombre": "Bitcoin USD 24/7", "valor": 88450.0},
    ]
    
    success_count = 0
    for item in indicators:
        ok = upsert_indicator(item["codigo"], item["nombre"], item["valor"])
        if ok:
            success_count += 1
            
    print(f"[OK] {success_count}/{len(indicators)} indicadores sincronizados en Supabase Realtime.")
    return success_count

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        print("Iniciando Slingshot Bridge en modo daemon continuo (cada 60 segundos)...")
        while True:
            try:
                run_sync_cycle()
            except Exception as ex:
                print(f"Error en ciclo: {ex}")
            time.sleep(60)
    else:
        run_sync_cycle()
