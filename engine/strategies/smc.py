"""
engine/strategies/smc.py — v6.0.4 (Institutional Memory Edition)
==============================================================
Estrategia SMC refinada que utiliza memoria de estructura.
No exige que todo ocurra en una sola vela (fallo lógico v5.7).
"""
import pandas as pd
import numpy as np
from engine.core.logger import logger
from engine.inference.volume_pattern import VolumePatternScheduler

class SMCInstitutionalStrategy:
    def __init__(self):
        self.scheduler = VolumePatternScheduler()

    def analyze(self, df: pd.DataFrame, interval: str = "15m") -> pd.DataFrame:
        if df.empty or len(df) < 10:
            return df

        df = df.copy()
        
        # 3. Order Blocks Institucionales y FVG (Calculados en Analyzer)
        # Respetamos el cálculo complejo y NO lo sobrescribimos.
        # Si por alguna razón no llegan, inicializamos en False para proteger capital.
        for col in ['ob_bullish', 'ob_bearish']:
            if col not in df.columns:
                df[col] = False
                
        for col in ['fvg_bullish', 'fvg_bearish']:
            if col not in df.columns:
                df[col] = True # Fallback permisivo si no hay datos de FVG

        # 4. Liquidity Sweeps (Dinamizados)
        lookback_liquidity = 20 
        min_prev = df['low'].rolling(window=lookback_liquidity).min().shift(1)
        max_prev = df['high'].rolling(window=lookback_liquidity).max().shift(1)
        
        df['recent_sweep_bull'] = (df['low'] < min_prev).rolling(window=10).max().astype(bool)
        df['recent_sweep_bear'] = (df['high'] > max_prev).rolling(window=10).max().astype(bool)
        
        # 5. Memoria de Estructura Dinámica [Fase 1.3]
        # Extraer minutos del string de intervalo (ej: "15m" -> 15, "1h" -> 60)
        try:
            val = int("".join(filter(str.isdigit, interval)))
            if "h" in interval.lower(): val *= 60
            elif "d" in interval.lower(): val *= 1440
        except:
            val = 15
            
        # En timeframes macros (>15m) los Order Blocks tardan más en mitigarse
        ob_memory_window = 15 if val > 15 else 5
        
        df['recent_ob_bull'] = df['ob_bullish'].rolling(window=ob_memory_window).max().astype(bool)
        df['recent_ob_bear'] = df['ob_bearish'].rolling(window=ob_memory_window).max().astype(bool)

        # [REFACTOR v12.0] Tracking de Niveles de OB para Retesteo
        # Guardamos el techo y fondo del OB más reciente para validar entradas tácticas
        df['ob_bull_top'] = df['high'].where(df['ob_bullish']).ffill()
        df['ob_bull_bottom'] = df['low'].where(df['ob_bullish']).ffill()
        df['ob_bear_top'] = df['high'].where(df['ob_bearish']).ffill()
        df['ob_bear_bottom'] = df['low'].where(df['ob_bearish']).ffill()

        # [RELAJACIÓN v9.2] FVG Memory para Swing Trading
        fvg_window = 3 if val > 15 else 1
        df['recent_fvg_bull'] = df['fvg_bullish'].rolling(window=fvg_window).max().astype(bool)
        df['recent_fvg_bear'] = df['fvg_bearish'].rolling(window=fvg_window).max().astype(bool)

        df['rvol_robust'] = df['volume'] / (df['volume'].rolling(20).mean() + 1e-9)
        return df

    def find_opportunities(self, df: pd.DataFrame, asset: str = "UNKNOWN", htf_bias: str = "NEUTRAL") -> list[dict]:
        if df.empty or len(df) < 64: return []
        
        # [REFACTOR v13.1] Sistema de Tiers con Conviction Diferenciada
        # TIER A: Setup completo (OB + Trigger + FVG)
        # TIER B: Setup parcial (Sweep + FVG o OB + Sweep)
        
        is_retesting_bull = (df['low'] <= df['ob_bull_top']) & (df['close'] >= df['ob_bull_bottom'])
        is_retesting_bear = (df['high'] >= df['ob_bear_bottom']) & (df['close'] <= df['ob_bear_top'])

        # TIER A: Setup Premium (0.90 Conviction)
        long_A = df['recent_ob_bull'] & (df['recent_sweep_bull'] | is_retesting_bull) & df['recent_fvg_bull']
        short_A = df['recent_ob_bear'] & (df['recent_sweep_bear'] | is_retesting_bear) & df['recent_fvg_bear']

        # TIER B: Setup Táctico (0.65 Conviction) - Solo si no hay Tier A
        long_B = (
            (df['recent_ob_bull'] & df['recent_sweep_bull']) |   # OB + Sweep (sin FVG)
            (df['recent_sweep_bull'] & df['recent_fvg_bull'])    # Sweep + FVG (sin OB)
        ) & ~long_A
        
        short_B = (
            (df['recent_ob_bear'] & df['recent_sweep_bear']) |
            (df['recent_sweep_bear'] & df['recent_fvg_bear'])
        ) & ~short_A

        opportunities = []
        last_idx = len(df) - 1
        
        if last_idx in np.where(long_A | short_A)[0]:
            sig_type = "LONG" if long_A[last_idx] else "SHORT"
            sig = self._format_signal(last_idx, sig_type, df.iloc[last_idx], asset)
            sig["conviction"] = 0.90
            sig["tier"] = "A"
            opportunities.append(sig)
        elif last_idx in np.where(long_B | short_B)[0]:
            sig_type = "LONG" if long_B[last_idx] else "SHORT"
            sig = self._format_signal(last_idx, sig_type, df.iloc[last_idx], asset)
            sig["conviction"] = 0.65
            sig["tier"] = "B"
            opportunities.append(sig)

        return opportunities

    def _format_signal(self, idx: int, signal_type: str, candle: pd.Series, asset: str) -> dict:
        # SNIPER ENTRY v6.6: Entrada en el 50% de la vela (EQUILIBRIUM)
        open_p = float(candle['open'])
        close_p = float(candle['close'])
        entry_p = open_p + (close_p - open_p) * 0.5 # 50% del cuerpo
        
        return {
            "index": int(idx),
            "asset": asset,
            "symbol": asset,
            "type": f"SMC Sniper",
            "signal_type": signal_type,
            "price": entry_p,  # <-- Entramos con descuento
            "stop_loss": 0,    # Lo calcula el RiskManager
            "take_profit_3r": 0,
            "timestamp": str(candle['timestamp']) if 'timestamp' in candle else 0,
            "conviction": 0.85,
            "rvol": float(candle.get('rvol_robust', 1.0)),
            "atr_value": float(candle.get('atr', entry_p * 0.002))
        }
