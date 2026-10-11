import winrm
import json

session = winrm.Session('https://80.65.211.99:5986', auth=('Administrator', 'matigol1'), transport='basic', server_cert_validation='ignore')

remote_code = """
import json
import asyncio
from engine.execution.account_manager import AccountManager
from engine.execution.bitunix_executor import BitunixExecutor

async def main():
    mgr = AccountManager()
    executors = mgr.get_all_executors()
    print(f"Executors found: {list(executors.keys())}")
    
    for acc_id, be in executors.items():
        print(f"\\n================ ACCOUNT: {acc_id} ================")
        try:
            pos = await be.get_pending_positions()
            print("--- POSITIONS ---")
            print(json.dumps(pos, indent=2))
        except Exception as e:
            print("Error pos:", e)
            
        try:
            pend = await be.get_pending_orders("XRPUSDT")
            print("--- PENDING LIMIT ORDERS (XRPUSDT) ---")
            print(json.dumps(pend, indent=2))
        except Exception as e:
            print("Error pend:", e)

        try:
            tpsl = await be.get_tpsl_orders("XRPUSDT")
            print("--- TPSL ORDERS (XRPUSDT) ---")
            print(json.dumps(tpsl, indent=2))
        except Exception as e:
            print("Error tpsl:", e)

        try:
            raw_tpsl = await be._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": "XRPUSDT"})
            print("--- RAW TPSL ORDERS (XRPUSDT) ---")
            print(json.dumps(raw_tpsl, indent=2))
        except Exception as e:
            print("Error raw tpsl:", e)

        try:
            plan = await be._request("GET", "/api/v1/futures/order/get_plan_orders", params={"symbol": "XRPUSDT"})
            print("--- PLAN / TRIGGER ORDERS (XRPUSDT) ---")
            print(json.dumps(plan, indent=2))
        except Exception as e:
            print("Error plan:", e)

asyncio.run(main())
"""

r_write = session.run_ps("$code = @'\n" + remote_code + "\n'@\n$code | Out-File -Encoding utf8 C:\\Slingshot\\vps_audit_run.py")

r_run = session.run_ps("cd C:\\Slingshot; & .venv\\Scripts\\python.exe C:\\Slingshot\\vps_audit_run.py")
print("STDOUT:\n" + r_run.std_out.decode('utf-8', errors='replace'))
if r_run.std_err:
    print("STDERR:\n" + r_run.std_err.decode('utf-8', errors='replace'))
