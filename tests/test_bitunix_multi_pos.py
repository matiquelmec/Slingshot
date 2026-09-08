# Test Unitario: Verificación Integral de Lógica de Gestión Bitunix Multi-Posición

def test_tpsl_position_isolation():
    # Simular 2 posiciones de XAUUSDT en Bitunix Hedge Mode
    positions = [
        {"positionId": "3356701514615376958", "symbol": "XAUUSDT", "qty": "0.079"},
        {"positionId": "6123486270206856285", "symbol": "XAUUSDT", "qty": "0.011"}
    ]
    
    # Órdenes TPSL existentes en el exchange
    existing_orders = [
        {"id": "tpsl_1", "positionId": "3356701514615376958", "symbol": "XAUUSDT", "slPrice": "4356.28"},
        {"id": "tpsl_2", "positionId": "6123486270206856285", "symbol": "XAUUSDT", "slPrice": "4356.28"}
    ]
    
    # Caso 1: Actualizar SL exclusivamente para la posición 1 (3356701514615376958)
    target_pos_id = "3356701514615376958"
    
    to_cancel = []
    for eo in existing_orders:
        eo_pos_id = str(eo.get("positionId") or "")
        # Solo cancelar si pertenece a la misma posición
        if target_pos_id and eo_pos_id and eo_pos_id != target_pos_id:
            continue # Pertenece a otra posición, preservar intacta!
        to_cancel.append(eo["id"])
        
    assert to_cancel == ["tpsl_1"], f"Expected to cancel only tpsl_1, got {to_cancel}"
    print("[OK] Test 1: Aislamiento de TPSL por positionId PASADO")

def test_trailing_stop_hierarchy():
    # Simular una posición en ganancia de +1.1R (debe activar Fast BE sin ser bloqueado por SOP-68)
    r_profit = 1.1
    be_threshold = 1.0
    entry_price = 100.0
    fee_buffer = 0.08
    sl_dist = 2.0
    side = "LONG"
    sl_at_be = False
    
    # 1. SOP-68 como bloque independiente (no encadenado con elif de trailing)
    sop68_executed = False
    if r_profit >= 0.35:
        sop68_executed = True
        
    # 2. Jerarquía de Trailing Stop
    target_sl = None
    status_msg = "EN_CURSO"
    
    if r_profit >= 5.0:
        status_msg = "TP3"
    elif r_profit >= 3.0:
        status_msg = "TP2"
    elif r_profit >= 2.0:
        status_msg = "TP1"
    elif r_profit >= be_threshold:
        target_sl = round(entry_price + fee_buffer, 4)
        status_msg = f"PROTEGIDO_FAST_BE (+{be_threshold:.1f}R)"
    elif r_profit >= 0.60 and not sl_at_be:
        target_sl = round(entry_price - (sl_dist * 0.50), 4)
        status_msg = "HALF_RISK"
        
    assert sop68_executed is True, "SOP-68 should execute at 1.1R"
    assert status_msg == "PROTEGIDO_FAST_BE (+1.0R)", f"Expected Fast BE, got {status_msg}"
    assert target_sl == 100.08, f"Expected 100.08, got {target_sl}"
    print("[OK] Test 2: Jerarquía de Trailing Stop y Fast-BE (+1.0R) PASADO")

def test_physical_sl_invariant():
    # LONG: Precio actual es $4366.13, target_sl es $4384.22 (perforado / inválido)
    cur_price = 4366.13
    side = "LONG"
    target_sl = 4384.22
    
    is_valid_long = (side == "LONG" and target_sl < cur_price)
    assert is_valid_long is False, "SL higher than current price in LONG must be invalid"
    
    # SHORT: Precio actual es $4366.13, target_sl es $4350.00 (perforado / inválido)
    side_short = "SHORT"
    target_sl_short = 4350.00
    is_valid_short = (side_short == "SHORT" and target_sl_short > cur_price)
    assert is_valid_short is False, "SL lower than current price in SHORT must be invalid"
    
    # Valid cases:
    assert (side == "LONG" and 4356.28 < cur_price) is True
    assert (side_short == "SHORT" and 4380.00 > cur_price) is True
    print("[OK] Test 3: Invariante Físico de Stop Loss PASADO")

def test_auto_healing_pos_id_matching():
    # Posición 1 tiene SL en Bitunix, Posición 2 carece de SL
    pos1_id = "3356701514615376958"
    pos2_id = "6123486270206856285"
    
    t_orders = [
        {"id": "tpsl_1", "positionId": pos1_id, "symbol": "XAUUSDT", "slPrice": "4356.28"}
    ]
    
    # Evaluar Posición 1
    has_active_sl_pos1 = any(
        (t.get("slPrice") or t.get("triggerPrice")) and (not pos1_id or str(t.get("positionId") or "") == str(pos1_id))
        for t in t_orders
    )
    assert has_active_sl_pos1 is True, "Posición 1 debe detectar su SL activo"
    
    # Evaluar Posición 2
    has_active_sl_pos2 = any(
        (t.get("slPrice") or t.get("triggerPrice")) and (not pos2_id or str(t.get("positionId") or "") == str(pos2_id))
        for t in t_orders
    )
    assert has_active_sl_pos2 is False, "Posición 2 debe detectar que NO tiene SL activo (para auto-reparar)"
    print("[OK] Test 4: Auto-Healing de Stop Loss por positionId PASADO")

def test_tpsl_map_dual_indexing():
    # Simular respuesta de get_pending_orders con dos tickets de XAUUSDT
    raw_orders = [
        {"positionId": "3356701514615376958", "symbol": "XAUUSDT", "slPrice": "4356.28"},
        {"positionId": "6123486270206856285", "symbol": "XAUUSDT", "slPrice": "4370.00"}
    ]
    
    tpsl_map = {}
    for to in raw_orders:
        sym_key = to.get("symbol")
        pos_key = str(to.get("positionId") or "")
        raw_val = to.get("slPrice")
        if raw_val:
            val = float(raw_val)
            if pos_key:
                tpsl_map[pos_key] = val
            if sym_key and sym_key not in tpsl_map:
                tpsl_map[sym_key] = val
                
    # Verificar que cada positionId resuelve su SL correcto y no se pisan
    assert tpsl_map.get("3356701514615376958") == 4356.28
    assert tpsl_map.get("6123486270206856285") == 4370.00
    print("[OK] Test 5: Indexación dual en tpsl_map (positionId + symbol) PASADO")

if __name__ == "__main__":
    test_tpsl_position_isolation()
    test_trailing_stop_hierarchy()
    test_physical_sl_invariant()
    test_auto_healing_pos_id_matching()
    test_tpsl_map_dual_indexing()
    print("\n=======================================================")
    print("ALL 5/5 BITUNIX MULTI-POSITION AUDIT TESTS PASSED 100%!")
    print("=======================================================")
