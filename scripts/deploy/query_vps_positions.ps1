$secpasswd = ConvertTo-SecureString "matigol1" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ("Administrator", $secpasswd)
$sopt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck
$session = New-PSSession -ComputerName "80.65.211.99" -Credential $cred -UseSSL -Port 5986 -SessionOption $sopt -Authentication Basic

Invoke-Command -Session $session -ScriptBlock {
    $script = @"
import sys
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3, os, glob, asyncio

paths = [
    r"C:\Slingshot\data\slingshot_vault.db",
    r"C:\Slingshot\slingshot_vault.db"
]
for p in paths:
    if os.path.exists(p):
        print(f"=== VAULT DB: {p} ===")
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print("Tablas:", tables)
        for t in tables:
            cur.execute(f"SELECT count(*) FROM {t}")
            cnt = cur.fetchone()[0]
            print(f"[{t}] Total filas: {cnt}")
            cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 5")
            rows = cur.fetchall()
            for row in rows:
                print("  ", row)

# Consultar posiciones en vivo y ordenes desde Bitunix
async def check_bitunix():
    try:
        from engine.execution.bitunix_executor import BitunixExecutor
        ex = BitunixExecutor()
        print(f"\n=== BITUNIX ACCOUNT: {ex.account_label} (dry_run={ex.dry_run}) ===")
        positions = await ex.get_pending_positions()
        print(f"Posiciones pendientes ({len(positions or [])}):", positions)
        orders = await ex.get_pending_orders()
        print(f"Ordenes pendientes ({len(orders or [])}):", orders)
        
        # Consultar historial reciente de ordenes en Bitunix
        history_res = await ex._request("GET", "/api/v1/futures/trade/get_history_orders", params={"pageSize": 20})
        print("\n=== BITUNIX HISTORIAL RECIENTE DE ORDENES ===")
        if isinstance(history_res, dict):
            hist_list = history_res.get("data", {}).get("orderList", [])
            for ho in hist_list[:10]:
                print(f"  Order: {ho.get('symbol')} {ho.get('side')} {ho.get('tradeSide')} qty={ho.get('qty')} price={ho.get('price')} status={ho.get('status')} type={ho.get('orderType')} created={ho.get('ctime')}")
        else:
            print("  Respuesta:", history_res)

        # Consultar historial de TPSL
        tpsl_hist = await ex._request("GET", "/api/v1/futures/tpsl/get_history_orders", params={"pageSize": 20})
        print("\n=== BITUNIX HISTORIAL RECIENTE TPSL ===")
        if isinstance(tpsl_hist, dict):
            t_list = tpsl_hist.get("data", []) or []
            for to in t_list[:10]:
                print(f"  TPSL: {to.get('symbol')} sl={to.get('slPrice')} tp={to.get('tpPrice')} status={to.get('status')}")
        else:
            print("  Respuesta:", tpsl_hist)
    except Exception as e:
        print("Error al consultar Bitunix:", e)

asyncio.run(check_bitunix())

# Buscar en los logs ocurrencias de colocacion de ordenes y TP
print("\n=== BUSCANDO EN LOGS ULTIMAS APERTURAS Y GESTION DE POSICIONES ===")
import re
target_keywords = ["place_order", "tpsl", "FAST_BE", "TP1", "TP2", "TP3", "SL_ACTUALIZADO", "AUTO-HEALING", "NEXUS SYNC"]
for lf in [r"C:\Slingshot\logs\slingshot.log", r"C:\Slingshot\logs\slingshot.log.1", r"C:\Slingshot\logs\slingshot_service.log"]:
    if not os.path.exists(lf): continue
    matched = []
    with open(lf, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if any(k in line for k in target_keywords):
                matched.append(line.strip())
    print(f"\n--- {lf} (total hits: {len(matched)}) ---")
    for m in matched[-15:]:
        print("  ", m)


"@
    $script | Out-File -FilePath "C:\Slingshot\temp_audit.py" -Encoding utf8
    C:\Slingshot\.venv\Scripts\python.exe C:\Slingshot\temp_audit.py
    Remove-Item "C:\Slingshot\temp_audit.py" -ErrorAction SilentlyContinue

}

Remove-PSSession $session
