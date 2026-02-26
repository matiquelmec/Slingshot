"""
Estrategia 1: PaulPerdices SMC — La entrada de francotirador.
=============================================================
Estrategia Maestra Híbrida (SMC + Wyckoff + Criptodamus).
Orquesta los 5 Niveles del Blueprint para detectar la
"Tormenta Perfecta": una vela institucional, con volumen,
en una KillZone, en el lugar correcto del ciclo de Wyckoff.

Operativa en: MARKUP (LONGs en pullbacks) y DISTRIBUTION (SHORTs en sweeps).
"""

import pandas as pd
from engine.filters.time_filter import TimeFilter
from engine.indicators.sessions import map_sessions_liquidity
from engine.indicators.structure import identify_order_blocks
from engine.indicators.volume import confirm_trigger
from engine.indicators.momentum import apply_criptodamus_suite


class PaulPerdicesStrategy:
    """
    Estrategia Maestra Híbrida (SMC + Wyckoff + Criptodamus).
    Detecta la "Entrada de Francotirador":
      1. Régimen de Mercado favorable (Wyckoff)
      2. KillZone UTC (Londres o NY)
      3. Barrida de liquidez (Sweep de Asian Low, London Low, PDL)
      4. Order Block Alcista o Bajista formado
      5. RVOL alto (confirmación institucional)
      6. [Opcional] RSI Sobrevendido o Squeeze (Criptodamus)
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

        # 4. RVOL Institucional — gatillo de volumen
        df = confirm_trigger(df, min_rvol=1.5)

        # 5. Herencia Criptodamus: RSI, MACD, BB Squeeze
        df = apply_criptodamus_suite(df)

        return df

    def find_opportunities(self, df: pd.DataFrame) -> list:
        """
        Escanea el dataframe procesado buscando la Tormenta Perfecta.
        Solo opera en KillZones con OB + Sweep + RVOL confirmado.
        """
        opportunities = []

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
                if in_killzone and has_ob_bull and swept_liq and has_volume:
                    entry  = current['close']
                    stop   = current['low'] * 0.998
                    # Mock risk logic inline
                    trade  = {"valid": True, "take_profit": entry + abs(entry - stop)*3, "risk_usd": 10.0, "position_size_usd": 200.0}
                    if trade['valid']:
                        opportunities.append({
                            "timestamp":        current['timestamp'],
                            "type":             "LONG 🟢 (SMC FRANCOTIRADOR)",
                            "regime":           current.get('market_regime'),
                            "price":            entry,
                            "stop_loss":        stop,
                            "take_profit_3r":   trade['take_profit'],
                            "risk_usd":         trade['risk_usd'],
                            "position_size":    trade['position_size_usd'],
                            "trigger":          "KillZone + OB Alcista + Sweep Liquidez + RVOL",
                            "rsi":              round(current.get('rsi', 0), 2),
                            "is_squeeze":       current.get('squeeze_active', False),
                        })

            # ── SHORT: DISTRIBUTION con barrida alcista → caída ─────────
            elif current.get('market_regime') == 'DISTRIBUTION':
                has_ob_bear = current.get('ob_bearish', False)
                if in_killzone and has_ob_bear and swept_high and has_volume:
                    entry  = current['close']
                    stop   = current['high'] * 1.002
                    # Mock risk logic inline
                    trade  = {"valid": True, "take_profit": entry - abs(entry - stop)*3, "risk_usd": 10.0, "position_size_usd": 200.0}
                    if trade['valid']:
                        opportunities.append({
                            "timestamp":        current['timestamp'],
                            "type":             "SHORT 🔴 (SMC FRANCOTIRADOR)",
                            "regime":           current.get('market_regime'),
                            "price":            entry,
                            "stop_loss":        stop,
                            "take_profit_3r":   trade['take_profit'],
                            "risk_usd":         trade['risk_usd'],
                            "position_size":    trade['position_size_usd'],
                            "trigger":          "KillZone + OB Bajista + Sweep Liquidez + RVOL",
                            "rsi":              round(current.get('rsi', 0), 2),
                            "is_squeeze":       current.get('squeeze_active', False),
                        })

        return opportunities
