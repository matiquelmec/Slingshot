# engine/tests/test_confluence.py
import pytest
import pandas as pd
import numpy as np
from engine.core.confluence import confluence_manager

def test_gold_ath_long_only_veto():
    """Valida que la regla 11.9 bloquee de forma implacable cualquier intento de Short en Oro en ATH."""
    df_dummy = pd.DataFrame({
        'timestamp': [pd.Timestamp.now()],
        'open': [2450.0], 'high': [2460.0], 'low': [2440.0], 'close': [2455.0],
        'volume': [1000.0]
    })

    gold_short_sig = {'asset': 'PAXGUSDT', 'signal_type': 'SHORT', 'price': 2450.0, 'atr_value': 10.0}
    gold_long_sig = {'asset': 'PAXGUSDT', 'signal_type': 'LONG', 'price': 2450.0, 'atr_value': 10.0}
    btc_short_sig = {'asset': 'BTCUSDT', 'signal_type': 'SHORT', 'price': 65000.0, 'atr_value': 500.0}

    res_gold_short = confluence_manager.evaluate_signal(df_dummy, gold_short_sig)
    res_gold_long = confluence_manager.evaluate_signal(df_dummy, gold_long_sig)
    res_btc_short = confluence_manager.evaluate_signal(df_dummy, btc_short_sig)

    # 1. Oro Short DEBE ser vetado al 0%
    assert res_gold_short.get('score') == 0, "El score de Oro Short debe ser 0% debido al veto macro"
    veto_factors = [c['factor'] for c in res_gold_short.get('checklist', []) if 'Veto' in c['factor']]
    assert len(veto_factors) > 0, "Debe incluir el factor explícito de Veto de Oro en el checklist"

    # 2. Oro Long DEBE estar permitido
    assert res_gold_long.get('score', 0) > 0, "Oro Long debe ser evaluado y permitido"

    # 3. BTC Short DEBE estar permitido (Cripto es bidireccional)
    assert res_btc_short.get('score', 0) > 0, "BTC Short debe ser evaluado y permitido"

def test_checklist_structure_compliance():
    """Valida que el checklist contenga todos los factores institucionales requeridos por el frontend."""
    df_dummy = pd.DataFrame({
        'timestamp': [pd.Timestamp.now()],
        'open': [65000.0], 'high': [65500.0], 'low': [64800.0], 'close': [65200.0],
        'volume': [2500.0]
    })
    sig = {'asset': 'BTCUSDT', 'signal_type': 'LONG', 'price': 65000.0, 'atr_value': 400.0}
    res = confluence_manager.evaluate_signal(df_dummy, sig)
    
    checklist = res.get('checklist', [])
    assert len(checklist) > 0, "El checklist de confluencia no debe estar vacío"
    for item in checklist:
        assert 'factor' in item, "Cada elemento del checklist debe tener un 'factor'"
        assert 'status' in item, "Cada elemento del checklist debe tener un 'status'"
        assert isinstance(item['status'], str) and len(item['status']) > 0, f"Status inválido: {item.get('status')}"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
