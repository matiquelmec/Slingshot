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

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 10:
            return df

        df = df.copy()
        df['body_size'] = abs(df['close'] - df['open'])
        body_ma = df['body_size'].rolling(10).mean()
        
        # v6.6: Bajamos el umbral de 1.5 a 1.2 para capturar el inicio del movimiento
        df['strong_momentum'] = df['body_size'] > (body_ma * 1.2)

        # 3. Order Blocks (v6.6 - Más frecuente)
        df['ob_bullish'] = (df['close'] > df['open']) & (df['strong_momentum'])
        df['ob_bearish'] = (df['close'] < df['open']) & (df['strong_momentum'])

        # 4. Liquidity Sweeps (Dinamizados)
        lookback_liquidity = 20 
        min_prev = df['low'].rolling(window=lookback_liquidity).min().shift(1)
        max_prev = df['high'].rolling(window=lookback_liquidity).max().shift(1)
        
        df['recent_sweep_bull'] = (df['low'] < min_prev).rolling(window=10).max().astype(bool)
        df['recent_sweep_bear'] = (df['high'] > max_prev).rolling(window=10).max().astype(bool)
        
        df['rvol_robust'] = df['volume'] / (df['volume'].rolling(20).mean() + 1e-9)
        return df

    def find_opportunities(self, df: pd.DataFrame, asset: str = "UNKNOWN", htf_bias: str = "NEUTRAL") -> list[dict]:
        if df.empty or len(df) < 64: return []
        
        long_mask = (df['ob_bullish'] & df['recent_sweep_bull'])
        short_mask = (df['ob_bearish'] & df['recent_sweep_bear'])

        opportunities = []
        indices = np.where(long_mask | short_mask)[0]
        
        # Solo velas recientes
        last_indices = range(len(df) - 15, len(df))
        
        for idx in indices:
            if idx in last_indices:
                sig_type = "LONG" if long_mask[idx] else "SHORT"
                opportunities.append(self._format_signal(idx, sig_type, df.iloc[idx], asset))

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
