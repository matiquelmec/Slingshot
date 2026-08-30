"""
Diagnostico integral del motor Slingshot v13.0
Prueba cada modulo critico con datos sinteticos realistas.
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def make_trending_df(n=100, start_price=70000.0, trend=1):
    """Genera un DataFrame de velas con tendencia clara."""
    prices = [start_price]
    for _ in range(n - 1):
        move = np.random.uniform(50, 200) * trend
        noise = np.random.uniform(-80, 80)
        prices.append(prices[-1] + move + noise)

    rows = []
    base_ts = datetime(2026, 5, 14, 8, 0, tzinfo=timezone.utc)
    for i, p in enumerate(prices):
        spread = abs(np.random.uniform(50, 300))
        o = p + np.random.uniform(-50, 50)
        h = max(p, o) + spread
        l = min(p, o) - spread
        rows.append({
            "timestamp": (base_ts + timedelta(minutes=15 * i)).timestamp(),
            "open": round(o, 2), "high": round(h, 2),
            "low": round(l, 2), "close": round(p, 2),
            "volume": round(np.random.uniform(100, 2000), 2)
        })
    return pd.DataFrame(rows)

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
results = []

# ═════════════════════════════════════════════════════════════
# TEST 1: Volume — RVOL y Absorcion
# ═════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TEST 1: engine/indicators/volume.py — RVOL + Absorcion")
print("="*60)
try:
    from engine.indicators.volume import calculate_rvol, calculate_absorption_index, confirm_trigger

    df = make_trending_df(150)

    # 1a. RVOL debe calcularse sin errores
    df_rvol = calculate_rvol(df)
    assert "rvol" in df_rvol.columns, "Columna 'rvol' ausente"
    assert not df_rvol["rvol"].isna().all(), "RVOL todo NaN"
    last_rvol = df_rvol["rvol"].iloc[-1]
    print(f"  {PASS} RVOL calculado: ultimo valor = {last_rvol:.2f}x")

    # 1b. Absorcion debe estar entre 0 y 100
    df_abs = calculate_absorption_index(df)
    assert "absorption_score" in df_abs.columns, "Columna 'absorption_score' ausente"
    assert df_abs["absorption_score"].between(0, 100).all(), "Absorcion fuera de rango 0-100"
    last_abs = df_abs["absorption_score"].iloc[-1]
    print(f"  {PASS} Absorcion calculada: ultimo valor = {last_abs:.1f}/100")

    # 1c. confirm_trigger — verifica la logica de combinacion
    df_trig = confirm_trigger(df)
    assert "valid_trigger" in df_trig.columns, "Columna 'valid_trigger' ausente"
    n_triggers = df_trig["valid_trigger"].sum()
    print(f"  {PASS} confirm_trigger OK: {n_triggers} velas con trigger valido en {len(df)} velas")
    results.append(("Volume RVOL + Absorcion", True))

except Exception as e:
    print(f"  {FAIL} Error: {e}")
    import traceback; traceback.print_exc()
    results.append(("Volume RVOL + Absorcion", False))

# ═════════════════════════════════════════════════════════════
# TEST 2: Structure — Order Blocks y FVG
# ═════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TEST 2: engine/indicators/structure.py — OBs y FVGs")
print("="*60)
try:
    from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates

    df = make_trending_df(150)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df_smc = identify_order_blocks(df)

    # Verificar columnas requeridas
    required = ["ob_bullish", "ob_bearish", "fvg_bullish", "fvg_bearish"]
    for col in required:
        assert col in df_smc.columns, f"Columna '{col}' ausente"
    print(f"  {PASS} Columnas OB/FVG presentes")

    n_bull_ob = df_smc["ob_bullish"].sum()
    n_bear_ob = df_smc["ob_bearish"].sum()
    n_bull_fvg = df_smc["fvg_bullish"].sum()
    n_bear_fvg = df_smc["fvg_bearish"].sum()
    print(f"  {PASS} OBs detectados: Bull={n_bull_ob} | Bear={n_bear_ob}")
    print(f"  {PASS} FVGs detectados: Bull={n_bull_fvg} | Bear={n_bear_fvg}")

    # Verificar extract_smc_coordinates
    coords = extract_smc_coordinates(df_smc)
    assert "order_blocks" in coords, "'order_blocks' ausente en SMC coords"
    assert "fvgs" in coords, "'fvgs' ausente en SMC coords"
    n_obs_extracted = len(coords["order_blocks"].get("bullish", [])) + len(coords["order_blocks"].get("bearish", []))
    print(f"  {PASS} extract_smc_coordinates OK: {n_obs_extracted} OBs extraidos como coordenadas")

    # Detectar posible bug: si TODOS son False, algo esta mal
    if n_bull_ob == 0 and n_bear_ob == 0:
        print(f"  {WARN} ALERTA: Cero OBs detectados en 150 velas trending. Revisar umbrales.")
        results.append(("Structure OB/FVG", "WARN"))
    else:
        results.append(("Structure OB/FVG", True))

except Exception as e:
    print(f"  {FAIL} Error: {e}")
    import traceback; traceback.print_exc()
    results.append(("Structure OB/FVG", False))

# ═════════════════════════════════════════════════════════════
# TEST 3: Session Manager — PDH/PDL y KillZones
# ═════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TEST 3: engine/core/session_manager.py — PDH/PDL + Sessions")
print("="*60)
try:
    from engine.core.session_manager import SessionManager

    sm = SessionManager(symbol="BTCUSDT_TEST")

    # Generar historial de 2 dias
    history = []
    base_ts = datetime(2026, 5, 13, 0, 0, tzinfo=timezone.utc)
    for i in range(200):
        ts = base_ts + timedelta(minutes=15 * i)
        p = 70000 + i * 10 + np.random.uniform(-100, 100)
        history.append({"data": {
            "timestamp": ts.timestamp(),
            "open": p, "high": p + 200,
            "low": p - 200, "close": p, "volume": 500
        }})

    sm.bootstrap(history)

    state = sm.get_current_state()
    assert "data" in state, "Payload sin 'data'"
    data = state["data"]

    # PDH/PDL
    pdh = data.get("pdh")
    pdl = data.get("pdl")
    print(f"  {PASS} Bootstrap OK")
    if pdh and pdl:
        print(f"  {PASS} PDH={pdh:.2f} | PDL={pdl:.2f}")
        assert pdh > pdl, "PDH debe ser mayor que PDL"
    else:
        print(f"  {WARN} PDH/PDL no calculados (posible problema con el dia anterior)")

    # KillZone y sesion actual
    current_session = data.get("current_session")
    is_killzone = data.get("is_killzone")
    print(f"  {PASS} Sesion actual: {current_session} | KillZone: {is_killzone}")

    # Sessions info
    sessions = data.get("sessions", {})
    for sess in ["asia", "london", "ny"]:
        assert sess in sessions, f"Sesion '{sess}' ausente"
    print(f"  {PASS} Sesiones presentes: asia, london, ny")
    results.append(("Session Manager PDH/PDL", True))

except Exception as e:
    print(f"  {FAIL} Error: {e}")
    import traceback; traceback.print_exc()
    results.append(("Session Manager PDH/PDL", False))

# ═════════════════════════════════════════════════════════════
# TEST 4: Confluence — Score con todos los factores
# ═════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TEST 4: engine/core/confluence.py — Score de Confluencia")
print("="*60)
try:
    from engine.core.confluence import ConfluenceManager
    from engine.indicators.structure import identify_order_blocks, extract_smc_coordinates

    df = make_trending_df(150)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df_smc = identify_order_blocks(df)
    smc_map = extract_smc_coordinates(df_smc)

    # Anadir columnas que el confluence espera del router
    df_smc["market_regime"] = "MARKUP"
    df_smc["recent_sweep_bull"] = False
    df_smc["recent_sweep_bear"] = False
    df_smc["absorption_score"] = 50.0

    cm = ConfluenceManager()
    current_price = float(df_smc["close"].iloc[-1])

    # Signal mock
    signal = {
        "type": "LONG",
        "signal_type": "LONG",
        "price": current_price,
        "timestamp": df_smc["timestamp"].iloc[-1],
        "asset": "BTCUSDT",
        "regime": "MARKUP"
    }

    result = cm.evaluate_signal(
        df=df_smc,
        signal=signal,
        ml_projection={"direction": "ALCISTA", "probability": 75},
        session_data={"current_session": "NEW_YORK"},
        smc_map=smc_map,
        heatmap={"imbalance": 0.3, "hot_bids": [], "hot_asks": []}
    )

    score = result.get("score", -1)
    checklist = result.get("checklist", [])
    assert score >= 0, "Score negativo inesperado"
    assert len(checklist) > 0, "Checklist vacio"

    # Detectar factores con pesos en cero (bug potencial)
    confirmed = [c for c in checklist if c.get("status") == "CONFIRMADO"]
    divergente = [c for c in checklist if c.get("status") == "DIVERGENTE"]

    print(f"  {PASS} Score calculado: {score}%")
    print(f"  {PASS} Factores en checklist: {len(checklist)}")
    print(f"  {PASS} Confirmados: {len(confirmed)} | Divergentes: {len(divergente)}")
    for item in checklist:
        status_icon = "[OK]" if item["status"] == "CONFIRMADO" else "[--]"
        print(f"         {status_icon} {item['factor']}: {item['status']} — {item.get('detail','')}")

    # Alerta si el score es extremadamente bajo con datos bullish
    if score < 20:
        print(f"  {WARN} Score muy bajo ({score}%) en condiciones alcistas. Revisar pesos.")
        results.append(("Confluence Score", "WARN"))
    else:
        results.append(("Confluence Score", True))

except Exception as e:
    print(f"  {FAIL} Error: {e}")
    import traceback; traceback.print_exc()
    results.append(("Confluence Score", False))

# ═════════════════════════════════════════════════════════════
# TEST 5: Risk Manager — Calculo de Posicion y RR
# ═════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("TEST 5: engine/risk/risk_manager.py — Posicion y RR Ratio")
print("="*60)
try:
    from engine.risk.risk_manager import RiskManager

    rm = RiskManager()
    result = rm.calculate_position(
        current_price=70000.0,
        signal_type="LONG",
        market_regime={"regime": "MARKUP", "bias": "BULLISH"},
        smc_data={"order_blocks": {"bullish": [], "bearish": []}},
        atr_value=500.0,
        asset="BTCUSDT",
        htf_bias=None,
        fib_data=None,
        confluence_score=75
    )

    required_keys = ["stop_loss", "take_profit_3r", "position_size_usdt", "risk_pct", "rr_ratio"]
    for k in required_keys:
        if k not in result:
            print(f"  {FAIL} Clave '{k}' ausente en resultado de RiskManager")
        else:
            print(f"  {PASS} {k}: {result[k]}")

    rr = result.get("rr_ratio", 0)
    sl = result.get("stop_loss", 0)
    tp = result.get("take_profit_3r", 0)

    if sl > 0 and tp > 0:
        assert tp > 70000 > sl, "SL/TP invertidos para LONG"
        print(f"  {PASS} Geometria correcta: SL={sl} < Entry=70000 < TP={tp}")

    if rr < 1.0:
        print(f"  {WARN} RR de {rr:.2f} por debajo del minimo institucional. Revisar ATR/niveles.")
        results.append(("Risk Manager RR", "WARN"))
    else:
        results.append(("Risk Manager RR", True))

except Exception as e:
    print(f"  {FAIL} Error: {e}")
    import traceback; traceback.print_exc()
    results.append(("Risk Manager RR", False))

# ═════════════════════════════════════════════════════════════
# RESUMEN FINAL
# ═════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("RESUMEN DE DIAGNOSTICO — Slingshot v13.0")
print("="*60)
for name, status in results:
    if status is True:
        icon = "[OK]    "
    elif status == "WARN":
        icon = "[WARN]  "
    else:
        icon = "[FALLO] "
    print(f"  {icon} {name}")

passed = sum(1 for _, s in results if s is True)
warned = sum(1 for _, s in results if s == "WARN")
failed = sum(1 for _, s in results if s is False)
print(f"\n  Total: {passed} OK | {warned} ADVERTENCIAS | {failed} FALLOS")
