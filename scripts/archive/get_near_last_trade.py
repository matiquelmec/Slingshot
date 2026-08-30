import os
import json
import sqlite3

print("=== CHECKING BITUNIX VAULT & DB ===")
if os.path.exists("data/vault.db"):
    conn = sqlite3.connect("data/vault.db")
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]
    print("Tables in vault.db:", tables)
    for table in tables:
        print(f"\n--- Table: {table} ---")
        c.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 10")
        rows = c.fetchall()
        for r in rows:
            if "NEAR" in str(r):
                print("NEAR ROW:", r)
    conn.close()

print("\n=== CHECKING BLACKBOX / MEMORY ===")
if os.path.exists("data/blackbox.json"):
    with open("data/blackbox.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            near_items = [d for d in data if "NEAR" in str(d)]
            print(f"Total NEAR records in blackbox: {len(near_items)}")
            for item in near_items[-5:]:
                print(json.dumps(item, indent=2))
        except Exception as e:
            print("Error reading blackbox:", e)

import sys
sys.path.insert(0, os.path.abspath("."))
from engine.execution.bitunix_executor import BitunixExecutor
try:
    executor = BitunixExecutor()
    trades = executor.get_trade_history("NEARUSDT")
    print(f"\n=== BITUNIX API DIRECT TRADE HISTORY (NEARUSDT) ===")
    print("Recent trades count:", len(trades) if trades else 0)
    if trades:
        print(json.dumps(trades[:5], indent=2))
except Exception as e:
    print("Bitunix query note:", e)
