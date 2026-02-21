import pandas as pd
import numpy as np
from pathlib import Path

# Importar nuestros módulos institucionales (Los 5 Niveles + Router)
from engine.indicators.regime import RegimeDetector
from engine.filters.time_filter import TimeFilter
from engine.indicators.sessions import map_sessions_liquidity
from engine.indicators.structure import identify_order_blocks
from engine.indicators.volume import confirm_trigger
from engine.indicators.momentum import apply_criptodamus_suite
from engine.filters.risk import RiskManager

class PaulPerdicesStrategy:
    """
    Estrategia Maestra Híbrida (SMC + Wyckoff + Criptodamus).
    Orquesta los 5 Niveles para detectar la "Entrada de Francotirador".
    """
    
    def __init__(self):
        self.regime_router = RegimeDetector()
        self.time_filter = TimeFilter()
        self.risk_manager = RiskManager(account_balance=1000.0) # Cuenta $1000
        
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pasa los datos crudos por toda la cadena de montaje institucional."""
        df = df.copy()
        print("⚙️ Iniciando Pipeline de Integración (SMC Francotirador)...")
        
        # 1. Router Wyckoff (Capa 2): Detectar el régimen general
        df = self.regime_router.detect_regime(df)
        
        # 2. SMC Nivel 0: Aplicar Reloj UTC (Ignorar operaciones fuera de sesión)
        # Nota: Calculamos todo primero, pero solo filtramos para 'buscar entradas' en las KillZones.
        df['in_killzone'] = df['timestamp'].apply(self.time_filter.is_killzone)
        
        # 3. SMC Nivel 1.5: Mapear Liquidez por Sesiones (Asian, London, NY) y Sweeps
        df = map_sessions_liquidity(df)
        
        # 4. SMC Nivel 2: Detectar Order Blocks e Imbalances (FVG)
        df = identify_order_blocks(df)
        
        # 5. SMC Nivel 3: El Gatillo (Volumen Institucional RVOL)
        df = confirm_trigger(df, min_rvol=1.5)
        
        # 6. Herencia Criptodamus: Momentum y Squeeze
        df = apply_criptodamus_suite(df)
        
        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        """
        Escanea el dataframe procesado en busca de la 'Tormenta Perfecta'.
        Reglas de la estrategia LONG (Compras):
        1. Régimen de Mercado favorable (Markup o Accumulation)
        2. Estamos dentro de una KillZone UTC (Londres o NY)
        3. El precio acaba de barrer un mínimo importante (Ej: Asian Low o PDL)
        4. Se formó un Order Block Alcista (Vela institucional)
        5. El RVOL es alto (Dinero inyectado)
        6. [Opcional] Criptodamus: RSI Sobrevendido o Squeeze
        """
        opportunities = []
        
        # Iterar sobre las últimas velas (Simulando un escaneo en vivo)
        for i in range(1, len(df)):
            current_candle = df.iloc[i]
            
            # --- FILTROS DE ENTRADA (LONG) ---
            
            # 1. Régimen permitido para comprar
            valid_regime = current_candle['market_regime'] in ['MARKUP', 'ACCUMULATION']
            
            # 2. Timing
            valid_time = current_candle['in_killzone']
            
            # 3. Estructura (Order Block recién formado)
            has_ob = current_candle['ob_bullish']
            
            # 4. Acción de Liquidez Institucional (Robo de Stop Loss)
            # Acaba de barrer Asia Low, London Low o Previous Daily Low
            swept_liquidity = current_candle['sweep_asian_low'] or current_candle['sweep_london_low'] or current_candle['sweep_pdl']
            
            # 5. Gatillo de Volumen
            has_volume = current_candle['valid_trigger']
            
            # Si todas las estrellas se alinean:
            if valid_regime and valid_time and has_ob and swept_liquidity and has_volume:
                
                # --- Nivel 4: Gestión de Riesgo Automática ---
                entry_price = current_candle['close']
                # El Stop Loss técnico va debajo del low de la vela del OB
                stop_loss = current_candle['low'] * 0.998 # 0.2% de holgura
                
                trade_setup = self.risk_manager.calculate_position(entry_price, stop_loss)
                
                if trade_setup['valid']:
                    opportunities.append({
                        "timestamp": current_candle['timestamp'],
                        "regime": current_candle['market_regime'],
                        "type": "LONG 🟢",
                        "price": entry_price,
                        "risk_usd": trade_setup['risk_usd'],
                        "position_size": trade_setup['position_size_usd'],
                        "take_profit_3r": trade_setup['take_profit'],
                        "breakeven_at": trade_setup['breakeven_trigger'],
                        "rsi": round(current_candle['rsi'], 2),
                        "is_squeeze": current_candle['squeeze_active']
                    })
                    
        return opportunities

if __name__ == "__main__":
    import os
    
    file_path = Path(__file__).parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        
        strategy = PaulPerdicesStrategy()
        
        # 1. Integración de todos los cálculos
        analyzed_data = strategy.analyze(data)
        
        # 2. Escáner de la Tormenta Perfecta
        signals = strategy.find_opportunities(analyzed_data)
        
        print("\n" + "="*60)
        print("🎯 INFORME DE INTEGRACIÓN: ESTRATEGIA PAUL PERDICES")
        print("="*60)
        print(f"Total Velas Analizadas: {len(data)}")
        print(f"Oportunidades Doradas encontradas: {len(signals)}\n")
        
        if signals:
            print("Últimas 3 Señales Históricas en esta data:")
            for s in signals[-3:]:
                print("-" * 50)
                print(f"🕒 Fecha UTC: {s['timestamp']}")
                print(f"📍 Estado: {s['regime']} | Señal: {s['type']}")
                print(f"💲 Entrada: ${s['price']} | TP (3:1): ${s['take_profit_3r']}")
                print(f"⚖️ Apalancamiento para Riesgo 1% ($10): ${s['position_size']}")
                print(f"🧬 Extra Criptodamus -> RSI: {s['rsi']} | Squeeze BB: {s['is_squeeze']}")
        else:
            print("El sistema fue tan estricto que no encontró NINGUNA operación con este ratio de exigencia en este periodo.")
            print("(Puedes relajar los filtros en find_opportunities si el mercado está muy seco)")
            
    else:
        print("No se encontró el Data Lake (btcusdt_15m.parquet).")
