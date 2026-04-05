import pandas as pd
import numpy as np
from typing import List

class VolumePatternScheduler:
    """
    SIGMA Estratega: Convertidor de Mercado a Tokens (GGUF-Ready).
    v5.5.3 Platinum - Versión Híbrida (Batch + Single)
    """

    def __init__(self, window_size: int = 64, n_features: int = 16):
        self.window_size = window_size
        self.n_features = n_features

    def get_market_tokens(self, df: pd.DataFrame) -> np.ndarray:
        """Wrapper de compatibilidad para un solo par."""
        return self.get_market_tokens_batch([df])[0]

    def get_market_tokens_batch(self, dfs: List[pd.DataFrame]) -> np.ndarray:
        """
        Versión Vectorizada del Scheduler.
        Procesa N pares en una sola operación de matriz 3D.
        """
        n_pairs = len(dfs)
        valid_dfs = []
        for df in dfs:
            if len(df) < self.window_size:
                pad = pd.DataFrame(0, index=range(self.window_size - len(df)), columns=df.columns)
                valid_dfs.append(pd.concat([pad, df]).tail(self.window_size))
            else:
                valid_dfs.append(df.tail(self.window_size))

        # 1. Empaquetamiento de Tensores
        all_close = np.array([df['close'].values for df in valid_dfs], dtype=np.float32)
        all_vol   = np.array([df['volume'].values for df in valid_dfs], dtype=np.float32)
        
        # 2. FFT Vectorizada
        price_fft = np.fft.fft(all_close, axis=1)
        vol_fft   = np.fft.fft(all_vol, axis=1)
        
        price_power = np.abs(price_fft[:, :self.window_size//2])
        vol_power   = np.abs(vol_fft[:, :self.window_size//2])
        
        # 3. Normalización por Lote
        p_mean = np.mean(price_power, axis=1, keepdims=True)
        p_std = np.std(price_power, axis=1, keepdims=True) + 1e-9
        price_power = (price_power - p_mean) / p_std
        
        v_mean = np.mean(vol_power, axis=1, keepdims=True)
        v_std = np.std(vol_power, axis=1, keepdims=True) + 1e-9
        vol_power = (vol_power - v_mean) / v_std

        # 4. Creación del Tensor de Salida (Batch x Seq x Features)
        tokens_batch = np.zeros((n_pairs, self.window_size, self.n_features), dtype=np.float32)
        
        # Llenar características vectorialmente
        tokens_batch[:, :, 0] = np.mean(price_power, axis=1, keepdims=True)
        tokens_batch[:, :, 1] = np.mean(vol_power, axis=1, keepdims=True)
        
        # Log Returns (evitar shift global, usar shift por axis)
        shifted_close = np.roll(all_close, 1, axis=1)
        shifted_close[:, 0] = all_close[:, 0] # Primera vela sin retorno
        tokens_batch[:, :, 2] = np.log(all_close / (shifted_close + 1e-9))
        
        # Limpieza Final OMEGA
        np.nan_to_num(tokens_batch, copy=False)
        return tokens_batch

    def predict_liquidity_sweep(self, tokens: np.ndarray) -> bool:
        """
        Score de probabilidad Alpha (Proxy).
        Funciona tanto para un token individual como para el último de una serie.
        """
        if tokens.ndim == 2: # (Seq, Features)
            last_token = tokens[-1]
        else: # (Features,)
            last_token = tokens
            
        # Lógica de probabilidad basada en absorción y volumen
        # Índices: 5 (RVOL), 8 (Absorption)
        prob_score = (last_token[8] * 0.6) + (last_token[5] * 0.4)
        return prob_score > 0.85
