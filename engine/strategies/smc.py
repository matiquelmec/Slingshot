import pandas as pd
from engine.core.session_manager import TimeFilter
from engine.indicators.sessions import map_sessions_liquidity
from engine.indicators.structure import identify_order_blocks
from engine.indicators.volume import confirm_trigger

class SMCInstitutionalStrategy:
    """
    Estrategia Maestra de Smart Money Concepts (SMC).
    Detecta la "Entrada Institucional de Alta Probabilidad":
      1. Contexto de Mercado (HTF Alignment)
      2. KillZone UTC (Londres o NY)
      3. Barrida de liquidez (Sweep de Asian Low, London Low, PDL)
      4. Order Block (OB) formado
      5. RVOL Intradía (Smart Money Footprint)
      6. Verificación de Desequilibrio (FVG)
    """

    def __init__(self):
        self.time_filter  = TimeFilter()
        # RiskManager dependancy removed

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pasa los datos crudos por toda la cadena de montaje institucional."""
        df = df.copy()

        # 1. Reloj UTC: marcar si estamos en KillZone
        df['in_killzone'] = df['timestamp'].apply(self.time_filter.is_killzone)

        # 2. Mapear sesiones y sweeps de liquidez (Asian, London, NY)
        df = map_sessions_liquidity(df)

        # 3. Order Blocks e Imbalances (FVG)
        df = identify_order_blocks(df)

        # 4. Fibonacci Estructural (Filtro de Descuento v4.0)
        from engine.indicators.fibonacci import get_current_fibonacci_levels
        fib = get_current_fibonacci_levels(df)
        if fib:
            df['fib_05'] = fib['levels']['0.5']
        else:
            df['fib_05'] = None

        # 5. RVOL Institucional — gatillo de volumen
        df = confirm_trigger(df, min_rvol=1.5)

        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        """
        Escanea el dataframe procesado buscando la Tormenta Perfecta.
        Solo opera en KillZones con OB + Sweep + RVOL confirmado.
        """
        opportunities = []
        
        # 0. Filtro Macro Global (Capa 1 v4.0)
        from engine.indicators.macro import get_macro_context
        macro_bias = get_macro_context().global_bias # LONG_ONLY / SHORT_ONLY / CAUTIOUS / NEUTRAL
        
        for i in range(1, len(df)):
            current = df.iloc[i]

            # ── Filtros comunes ───────────────────────────────────────────
            in_killzone = current.get('in_killzone', False)
            has_volume  = current.get('valid_trigger', False)
            swept_liq   = (
                current.get('sweep_asian_low', False) or
                current.get('sweep_london_low', False) or
                current.get('sweep_pdl', False)
            )
            swept_high  = (
                current.get('sweep_asian_high', False) or
                current.get('sweep_london_high', False) or
                current.get('sweep_pdh', False)
            )

            # ── LONG: MARKUP / ACCUMULATION con barrida bajista → rebote ─
            if current.get('market_regime') in ('MARKUP', 'ACCUMULATION'):
                has_ob_bull = current.get('ob_bullish', False)
                
                # REGLA v4.0: No comprar si el sesgo global es SHORT_ONLY
                if macro_bias == "SHORT_ONLY":
                    continue
                    
                # REGLA SMC v4.0: Comprar barato (Discount)
                is_discount = True
                if current.get('fib_05') is not None:
                    is_discount = current['close'] < current['fib_05']
                
                if in_killzone and has_ob_bull and swept_liq and has_volume and is_discount:
                    entry  = current['close']
                    
                    opportunities.append({
                        "timestamp":        current['timestamp'],
                        "type":             "LONG 🟢 (SMC INSTITUTIONAL)",
                        "signal_type":      "LONG",
                        "regime":           current.get('market_regime'),
                        "price":            entry,
                        "trigger":          "KillZone + OB Alcista + Sweep Liquidez + RVOL",
                        "atr_value":        current.get('atr_value', 0.0)
                    })

            # ── SHORT: DISTRIBUTION con barrida alcista → caída ─────────
            elif current.get('market_regime') == 'DISTRIBUTION':
                has_ob_bear = current.get('ob_bearish', False)
                
                # REGLA v4.0: No vender si el sesgo global es LONG_ONLY
                if macro_bias == "LONG_ONLY":
                    continue
                    
                # REGLA SMC v4.0: Vender caro (Premium)
                is_premium = True
                if current.get('fib_05') is not None:
                    is_premium = current['close'] > current['fib_05']
                    
                if in_killzone and has_ob_bear and swept_high and has_volume and is_premium:
                    entry  = current['close']
                    
                    opportunities.append({
                        "timestamp":        current['timestamp'],
                        "type":             "SHORT 🔴 (SMC INSTITUTIONAL)",
                        "signal_type":      "SHORT",
                        "regime":           current.get('market_regime'),
                        "price":            entry,
                        "trigger":          "KillZone + OB Bajista + Sweep Liquidez + RVOL",
                        "atr_value":        current.get('atr_value', 0.0)
                    })

        return opportunities
