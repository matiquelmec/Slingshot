import json
import os
from datetime import datetime

with open('data/blackbox.json', 'r', encoding='utf-8') as f:
    records = json.load(f)

print(f"Total registros auditados en Blackbox: {len(records)}")

by_asset = {}
by_result = {}
zero_conf_stops = []
rapid_closes = []

for idx, r in enumerate(records):
    asset = r.get('asset', 'UNKNOWN')
    res = r.get('result', 'UNKNOWN')
    sig_type = r.get('signal_type', 'UNKNOWN')
    confluence = r.get('confluence_score', 0)
    ts = r.get('timestamp', '')
    
    by_asset[asset] = by_asset.get(asset, 0) + 1
    by_result[res] = by_result.get(res, 0) + 1
    
    if confluence == 0 and res == 'STOP_LOSS':
        zero_conf_stops.append((idx, asset, sig_type, ts, r))

print("\n--- DISTRIBUCIÓN POR RESULTADO HISTÓRICO ---")
for k, v in by_result.items():
    print(f" • {k}: {v} ({v/len(records)*100:.1f}%)")

print("\n--- DISTRIBUCIÓN POR ACTIVO ---")
for k, v in sorted(by_asset.items(), key=lambda x: x[1], reverse=True):
    print(f" • {k}: {v}")

print(f"\n--- SEÑALES CON CIERRE ANÓMALO / CONFLUENCIA CERO: {len(zero_conf_stops)} ---")
for idx, asset, stype, ts, raw in zero_conf_stops:
    print(f" • ID #{idx:03d} | {ts} | {asset:<8} | {stype:<5} | Confluence: {raw.get('confluence_score')} | Regime: {raw.get('fingerprint', {}).get('regime')}")
