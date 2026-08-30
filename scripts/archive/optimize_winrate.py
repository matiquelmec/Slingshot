#!/usr/bin/env python
# scripts/optimize_winrate.py
# --------------------------------------------------------------
# Busca combinaciones de parámetros que alcancen ≥ 60 % win‑rate
# manteniendo R ≥ +3 R (≈ el nivel actual). Usa un CI de 200 backtests.
# --------------------------------------------------------------

import json
import itertools
import subprocess
import pathlib
import datetime
import sys
import os

ROOT = pathlib.Path(__file__).parents[1]  # proyecto raíz
CONFIG_FILE = ROOT / "engine/router/gatekeeper_config.json"
RESULTS_DIR = ROOT / "engine/backtest/opt_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Rangos a explorar (ajustables)
CONFIDENCE_RANGES = [60, 65, 70]            # umbral mínimo % (aplica a todos los regímenes)
RVOL_RANGES       = [0.8, 1.0, 1.2]        # factor relativo mínimo
OTE_TOL_RANGES    = [0.0, 0.3, 0.5]        # % de tolerancia alrededor de la zona OTE

def cargar_config():
    """Carga la configuración base (puede estar vacía)."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def ejecutar_backtest():
    """Ejecuta el backtest y devuelve (win_rate, total_R)."""
    cmd = [sys.executable, "-u", str(ROOT / "engine/backtest/replay_engine.py")]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    # Buscar la última línea que contiene el path del JSON del reporte
    json_path = None
    for line in reversed(proc.stdout.splitlines()):
        if "Reporte guardado en:" in line:
            json_path = line.split("Reporte guardado en:")[1].strip()
            break
    if not json_path:
        raise RuntimeError("No se encontró reporte JSON en la salida del backtest")
    with open(json_path, "r", encoding="utf-8") as jf:
        data = json.load(jf)
    # Compatibilidad con claves en mayúsculas o minúsculas
    win_rate = data.get("win_rate") if data.get("win_rate") is not None else data.get("WIN_RATE")
    total_r = data.get("total_r") if data.get("total_r") is not None else data.get("TOTAL_R")
    if win_rate is None or total_r is None:
        raise RuntimeError("Reporte JSON no contiene win_rate o total_r")
    return win_rate, total_r

def main():
    base_cfg = cargar_config()
    combos = list(itertools.product(CONFIDENCE_RANGES, RVOL_RANGES, OTE_TOL_RANGES))

    max_runs = 200
    run_id = 0

    for conf, rvol, ote_tol in combos:
        if run_id >= max_runs:
            break
        cfg = base_cfg.copy()
        cfg["confidence_thresholds"] = {k: conf for k in cfg.get("confidence_thresholds", {})}
        cfg["rvol_thresholds"] = {
            "STRONG": rvol,
            "CHOPPY": max(rvol, 1.0),   # asegurar valor razonable
            "DEFAULT": rvol
        }
        cfg["ote_tolerance_pct"] = ote_tol
        guardar_config(cfg)

        try:
            win_rate, total_r = ejecutar_backtest()
        except Exception as e:
            print(f"[ERROR] Run {run_id} falló: {e}", file=sys.stderr)
            continue

        result = {
            "run_id": run_id,
            "confidence": conf,
            "rvol": rvol,
            "ote_tolerance": ote_tol,
            "win_rate": win_rate,
            "total_R": total_r,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
        out_file = RESULTS_DIR / f"run_{run_id:03d}.json"
        out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[INFO] Run {run_id:03d}: win_rate={win_rate:.1f}%  total_R={total_r:.2f}")
        run_id += 1

    # ---------- Selección final ----------
    all_runs = [json.loads(p.read_text()) for p in RESULTS_DIR.glob("run_*.json")]
    viable = [r for r in all_runs if r["win_rate"] >= 60 and r["total_R"] >= 3.0]
    if viable:
        best = max(viable, key=lambda x: (x["win_rate"], x["total_R"]))
        print("\n=== Mejor configuración encontrada ===")
        print(json.dumps(best, indent=2))
    else:
        print("\nNo se encontró ninguna combinación que cumpla los criterios.")

if __name__ == "__main__":
    main()
