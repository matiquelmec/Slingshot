import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import random
import uuid

from engine.main_router import SlingshotRouter
from engine.core.store import store
from engine.risk.risk_manager import RiskManager

async def run_audit_stress_test():
    """
    Test de Integración Profesional Slingshot v3.3 (Audit Mode).
    Valida: 
    1. Generación de indicadores en crudo.
    2. Detección de Régimen de Mercado.
    3. Filtrado por Riesgo Institucional (Portero).
    4. Persistencia en MemoryStore.
    """
    print("\n🏁 [AUDIT] Iniciando Stress Test de Integración v3.3...")
    
    asset = "BTCUSDT"
    interval = "15m"
    
    # 1. Generar 300 velas de datos sintéticos realistas
    print(f"📊 Generando 300 velas de data sintética para {asset}...")
    data = []
    base_price = 85000.0
    now = datetime.now(timezone.utc).timestamp()
    
    # Simular una tendencia bajista (Bearish Trend) seguida de un Breakout Alcista
    for i in range(300):
        # Primero bajamos, luego consolidamos, luego explotamos
        if i < 200:
            price = base_price - (i * 5) # Bearish
        elif i < 280:
            price = base_price - 1000 + (random.random() * 50) # Range / Accumulation
        else:
            price = base_price - 1000 + ((i - 280) * 100) # Breakout / Markup
            
        data.append({
            "timestamp": now - ((300 - i) * 900),
            "open": price,
            "high": price + 20,
            "low": price - 20,
            "close": price + (random.random() * 10),
            "volume": 1000 + random.random() * 500
        })

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    
    # 2. Inicializar el Router
    router = SlingshotRouter()
    
    # 3. Procesar los datos (Pipeline Completo)
    print("🧠 Procesando datos a través de SlingshotRouter...")
    # Actualizar Macro v4.0 (Primera vez para el test)
    from engine.indicators.macro import update_macro_context
    await update_macro_context()
    
    # 3. Inyectar datos al Router
    result = router.process_market_data(df, asset=asset, interval=interval)
    
    # 4. Validar Resultados
    print("\n🔍 --- RESULTADOS DE AUDITORÍA v4.0 ---")
    diag = result.get('diagnostic', {})
    print(f"Asset       : {result['asset']}")
    print(f"Price       : ${result['current_price']:,.2f}")
    print(f"Regime      : {result['market_regime']}")
    print(f"DXY Trend   : {diag.get('dxy_trend', 'N/A')}")
    print(f"Risk App.   : {diag.get('risk_appetite', 'N/A')}")
    print(f"Macro Bias  : {diag.get('macro_bias', 'NEUTRAL')}")
    
    bias_dir = result.get('htf_bias', {}).get('direction', 'N/A') if result.get('htf_bias') else 'N/A'
    print(f"Bias HTF    : {bias_dir}")
    print(f"Strategy    : {result.get('active_strategy', 'N/A')}")
    
    # 5. Verificar Generación de Señal
    signals = result.get('signals', [])
    print(f"Señales Gen : {len(signals)}")
    for sig in signals:
        print(f"🚀 SEÑAL: {sig['type']} | Gatillo: {sig['trigger']}")
    
    for s in signals:
        print(f"\n📡 SEÑAL DETECTADA: {s['type']}")
        print(f"   Entry: {s['price']} | SL: {s['stop_loss']} | TP: {s['take_profit_3r']}")
        
        # Simular el guardado en el MemoryStore (lo que haría el worker)
        await store.save_signal({
            "asset": asset,
            "signal_type": s['type'],
            "price": s['price'],
            "stop_loss": s['stop_loss'],
            "take_profit": s['take_profit_3r'],
            "status": "APPROVED",
            "confluence": s.get('confluence', {}).get('total_score', 0)
        })
        print("   ✅ Persistido en MemoryStore (RAM).")

    # 6. Auditoría del Store
    stored_signals = await store.get_signals(asset=asset)
    print(f"\n🧱 Estado del MemoryStore: {len(stored_signals)} señales persistidas.")
    
    # 7. Auditoría de Riesgo (RiskManager)
    risk_env = RiskManager(account_balance=1000.0, base_risk_pct=0.01)
    for s in signals:
        # Falsificamos un dict para la validación del portero
        validation = risk_env.validate_signal(s)
        print(f"🛡️ Portero Institucional: {validation['trade_quality']} ({validation['reason']})")

    print("\n✅ [AUDIT] Test de Integración completado exitosamente.")

if __name__ == "__main__":
    asyncio.run(run_audit_stress_test())
