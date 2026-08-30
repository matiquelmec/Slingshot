#!/usr/bin/env python
# scripts/deep_audit.py
# ─────────────────────────────────────────────────────────────
# Auditoría profunda del backtest: identifica patrones en
# ganadores vs perdedores para tomar decisiones estratégicas.
# ─────────────────────────────────────────────────────────────
import json, sys, os, statistics

REPORT = os.path.join(os.path.dirname(__file__), "..",
    "engine/backtest/reports/backtest_BTCUSDT_20260521_105417.json")

with open(REPORT, "r", encoding="utf-8") as f:
    data = json.load(f)

trades = data["trade_log"]

# ── Clasificación ──
winners  = [t for t in trades if t["r_realized"] > 0]
losers   = [t for t in trades if t["r_realized"] < 0]
be_trades = [t for t in trades if t["r_realized"] == 0]

print("=" * 70)
print(" AUDITORÍA PROFUNDA — BTCUSDT 15m (90 días)")
print("=" * 70)
print(f"Total trades: {len(trades)}  |  Ganadores: {len(winners)}  |  Perdedores: {len(losers)}  |  BE: {len(be_trades)}")
print(f"Win Rate: {len(winners)/len(trades)*100:.1f}%")
print(f"Total R: {sum(t['r_realized'] for t in trades):.2f}R")
print()

# ── 1. SCORE DE CONFLUENCIA ──
print("─" * 70)
print("1. ANÁLISIS POR SCORE DE CONFLUENCIA")
print("─" * 70)
w_scores = [t["score"] for t in winners]
l_scores = [t["score"] for t in losers]
print(f"  Score promedio GANADORES: {statistics.mean(w_scores):.1f}%")
print(f"  Score promedio PERDEDORES: {statistics.mean(l_scores):.1f}%")
print(f"  Score mediana GANADORES:  {statistics.median(w_scores):.1f}%")
print(f"  Score mediana PERDEDORES: {statistics.median(l_scores):.1f}%")

# Distribución por rangos de score
for label, group in [("GANADORES", winners), ("PERDEDORES", losers)]:
    bins = {"50-59": 0, "60-69": 0, "70-79": 0, "80+": 0}
    for t in group:
        s = t["score"]
        if s >= 80: bins["80+"] += 1
        elif s >= 70: bins["70-79"] += 1
        elif s >= 60: bins["60-69"] += 1
        else: bins["50-59"] += 1
    total = len(group)
    print(f"\n  {label} ({total} trades):")
    for rng, cnt in bins.items():
        pct = cnt/total*100 if total else 0
        bar = "█" * int(pct/2)
        print(f"    Score {rng}: {cnt:3d} ({pct:5.1f}%)  {bar}")

# Win rate por rango de score
print("\n  WIN RATE POR RANGO DE SCORE:")
for lo, hi in [(50,59), (60,69), (70,79), (80,100)]:
    in_range = [t for t in trades if lo <= t["score"] <= hi]
    w_in = [t for t in in_range if t["r_realized"] > 0]
    r_total = sum(t["r_realized"] for t in in_range)
    wr = len(w_in)/len(in_range)*100 if in_range else 0
    print(f"    Score {lo}-{hi}: {len(in_range):3d} trades | WR: {wr:5.1f}% | R Total: {r_total:+.2f}R")

# ── 2. TIPO DE TRADE (LONG vs SHORT) ──
print("\n" + "─" * 70)
print("2. ANÁLISIS LONG vs SHORT")
print("─" * 70)
for ttype in ["LONG", "SHORT"]:
    group = [t for t in trades if t["type"] == ttype]
    w = [t for t in group if t["r_realized"] > 0]
    l = [t for t in group if t["r_realized"] < 0]
    r_total = sum(t["r_realized"] for t in group)
    wr = len(w)/len(group)*100 if group else 0
    avg_w = statistics.mean([t["r_realized"] for t in w]) if w else 0
    avg_l = statistics.mean([t["r_realized"] for t in l]) if l else 0
    print(f"  {ttype:5s}: {len(group):3d} trades | WR: {wr:5.1f}% | R: {r_total:+.2f}R | Avg Win: {avg_w:+.2f}R | Avg Loss: {avg_l:+.2f}R")

# ── 3. CLOSE REASON ANALYSIS ──
print("\n" + "─" * 70)
print("3. ANÁLISIS POR RAZÓN DE CIERRE")
print("─" * 70)
reasons = {}
for t in trades:
    r = t.get("close_reason", "UNKNOWN")
    if r not in reasons:
        reasons[r] = {"count": 0, "r_sum": 0, "scores": []}
    reasons[r]["count"] += 1
    reasons[r]["r_sum"] += t["r_realized"]
    reasons[r]["scores"].append(t["score"])

for reason, info in sorted(reasons.items(), key=lambda x: -x[1]["count"]):
    avg_score = statistics.mean(info["scores"])
    print(f"  {reason:20s}: {info['count']:3d} trades | R Total: {info['r_sum']:+.2f}R | Score Prom: {avg_score:.1f}%")

# ── 4. SL DISTANCE ANALYSIS ──
print("\n" + "─" * 70)
print("4. ANÁLISIS DE DISTANCIA DE STOP LOSS (% del precio)")
print("─" * 70)
for label, group in [("GANADORES", winners), ("PERDEDORES", losers)]:
    sl_pcts = []
    for t in group:
        entry = t["entry"]
        sl = t["sl_initial"]
        sl_pct = abs(entry - sl) / entry * 100
        sl_pcts.append(sl_pct)
    if sl_pcts:
        print(f"  {label}:")
        print(f"    SL Distancia Promedio: {statistics.mean(sl_pcts):.3f}%")
        print(f"    SL Distancia Mediana:  {statistics.median(sl_pcts):.3f}%")
        print(f"    SL Distancia Min:      {min(sl_pcts):.3f}%")
        print(f"    SL Distancia Max:      {max(sl_pcts):.3f}%")

# ── 5. CONSECUTIVE LOSSES ──
print("\n" + "─" * 70)
print("5. RACHAS DE PÉRDIDAS CONSECUTIVAS")
print("─" * 70)
max_streak = 0
current_streak = 0
streaks = []
for t in trades:
    if t["r_realized"] < 0:
        current_streak += 1
    else:
        if current_streak > 0:
            streaks.append(current_streak)
        current_streak = 0
if current_streak > 0:
    streaks.append(current_streak)

print(f"  Racha máxima de pérdidas: {max(streaks) if streaks else 0}")
print(f"  Racha promedio de pérdidas: {statistics.mean(streaks):.1f}" if streaks else "  N/A")
print(f"  Distribución de rachas: {sorted(streaks, reverse=True)}")

# ── 6. TEMPORAL ANALYSIS ──
print("\n" + "─" * 70)
print("6. ANÁLISIS TEMPORAL (Hora del día)")
print("─" * 70)
from collections import defaultdict
hourly = defaultdict(lambda: {"total": 0, "wins": 0, "r_sum": 0.0})
for t in trades:
    ts = t["timestamp"]
    hour = int(ts.split(" ")[1].split(":")[0])
    hourly[hour]["total"] += 1
    if t["r_realized"] > 0:
        hourly[hour]["wins"] += 1
    hourly[hour]["r_sum"] += t["r_realized"]

print(f"  {'Hora':>4s} | {'Trades':>6s} | {'WR':>6s} | {'R Total':>8s}")
print(f"  {'─'*4} | {'─'*6} | {'─'*6} | {'─'*8}")
for h in sorted(hourly.keys()):
    info = hourly[h]
    wr = info["wins"]/info["total"]*100 if info["total"] else 0
    flag = " ⚠️" if wr < 25 and info["total"] >= 3 else (" ✅" if wr >= 50 else "")
    print(f"  {h:4d} | {info['total']:6d} | {wr:5.1f}% | {info['r_sum']:+7.2f}R{flag}")

# ── 7. TRADES CON SCORE ALTO QUE PERDIERON ──
print("\n" + "─" * 70)
print("7. TRADES CON SCORE ALTO (≥75) QUE PERDIERON (Anomalías)")
print("─" * 70)
anomalies = [t for t in losers if t["score"] >= 75]
for t in anomalies:
    sl_pct = abs(t["entry"] - t["sl_initial"]) / t["entry"] * 100
    print(f"  {t['id']} | {t['type']:5s} | Score: {t['score']}% | Entry: {t['entry']:.2f} | SL dist: {sl_pct:.3f}%")

# ── 8. TRADES CON SCORE BAJO QUE GANARON ──
print("\n" + "─" * 70)
print("8. TRADES CON SCORE BAJO (≤60) QUE GANARON (Suerte?)")
print("─" * 70)
lucky = [t for t in winners if t["score"] <= 60]
for t in lucky:
    print(f"  {t['id']} | {t['type']:5s} | Score: {t['score']}% | R: {t['r_realized']:+.2f}R | Cierre: {t['close_reason']}")

# ── 9. PROPUESTA DE FILTRADO ──
print("\n" + "=" * 70)
print(" SIMULACIÓN DE FILTROS MEJORADOS")
print("=" * 70)

for min_score in [65, 70, 75]:
    filtered = [t for t in trades if t["score"] >= min_score]
    fw = [t for t in filtered if t["r_realized"] > 0]
    wr = len(fw)/len(filtered)*100 if filtered else 0
    r_total = sum(t["r_realized"] for t in filtered)
    print(f"  Score ≥ {min_score}: {len(filtered):3d} trades | WR: {wr:5.1f}% | R Total: {r_total:+.2f}R")

# Filtro combinado: score + tipo
print()
for min_score in [67, 71, 75]:
    for ttype in ["LONG", "SHORT", "AMBOS"]:
        if ttype == "AMBOS":
            filtered = [t for t in trades if t["score"] >= min_score]
        else:
            filtered = [t for t in trades if t["score"] >= min_score and t["type"] == ttype]
        fw = [t for t in filtered if t["r_realized"] > 0]
        wr = len(fw)/len(filtered)*100 if filtered else 0
        r_total = sum(t["r_realized"] for t in filtered)
        print(f"  Score ≥ {min_score} + {ttype:5s}: {len(filtered):3d} trades | WR: {wr:5.1f}% | R Total: {r_total:+.2f}R")

print("\n" + "=" * 70)
print(" FIN DE AUDITORÍA")
print("=" * 70)
