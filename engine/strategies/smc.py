import pandas as pd
import numpy as np
from engine.core.logger import logger
from engine.inference.volume_pattern import VolumePatternScheduler

class SMCInstitutionalStrategy:
    """
    SMC Institutional Strategy (v5.7.155 Master Gold)
    Repara el pipeline de MainRouter dividiendo el Procesamiento e Identificación.
    """

    def __init__(self):
        self.scheduler = VolumePatternScheduler()

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fase 1: Enriquecimiento de Datos (Cálculo de Indicadores SMC).
        """
        if df.empty or len(df) < 10:
            return df

        # Copia para no mutar el original en el router
        df = df.copy()

        # ── 1. Killzones (Simulación básica si no existen) ──
        if 'in_killzone' not in df.columns:
            # Asumimos Killzone por defecto para demo si no hay cronograma
            df['in_killzone'] = True 

        # ── 2. Order Blocks (Institutional v5.6 Restore) ──
        # Requieren un desplazamiento (Displacement) que rompa la estructura anterior.
        atr = df['high'].rolling(14).max() - df['low'].rolling(14).min()
        body_size = abs(df['close'] - df['open'])
        
        # Bullish OB: Última vela bajista antes de un impulso que rompe el High local
        df['is_ob_bull'] = (df['close'] > df['open']) & \
                          (df['close'].shift(1) < df['open'].shift(1)) & \
                          (body_size > atr.shift(1) * 0.7) & \
                          (df['high'] > df['high'].rolling(10).max().shift(1))
        
        # Bearish OB: Última vela alcista antes de un impulso que rompe el Low local
        df['is_ob_bear'] = (df['close'] < df['open']) & \
                          (df['close'].shift(1) > df['open'].shift(1)) & \
                          (body_size > atr.shift(1) * 0.7) & \
                          (df['low'] < df['low'].rolling(10).min().shift(1))

        # ── 3. Liquidity Sweeps ──
        # Barrido de Liquidez: Precio rompe Low anterior pero cierra dentro (Mecha larga)
        min_prev = df['low'].rolling(window=15).min().shift(1)
        max_prev = df['high'].rolling(window=15).max().shift(1)
        
        df['is_sweep_bull'] = (df['low'] < min_prev) & (df['close'] > min_prev)
        df['is_sweep_bear'] = (df['high'] > max_prev) & (df['close'] < max_prev)

        # ── 4. Robust RVOL ──
        if 'rvol_robust' not in df.columns:
            df['rvol_robust'] = df['volume'] / (df['volume'].rolling(20).mean() + 1e-9)

        return df

    def find_opportunities(self, df: pd.DataFrame, htf_bias: str = "NEUTRAL"):
        """
        Fase 2: Identificación de Señales GGUF-Ready.
        """
        if df.empty or len(df) < 64:
            return []

        # ── 1. Indicadores Base ──
        regime = df.get('regime', pd.Series(['UNKNOWN']*len(df))).values
        kz = df['in_killzone'].values
        rvol = df['rvol_robust'].values
        atr = df.get('atr', pd.Series([0.0]*len(df))).values

        # ── 2. Lógica SMC ──
        ob_bull = df['is_ob_bull'].values
        ob_bear = df['is_ob_bear'].values
        sweeps_bull = df['is_sweep_bull'].values
        sweeps_bear = df['is_sweep_bear'].values
        
        valid_trigger = rvol > 1.2
        in_kz = kz == True

        bias_bull_ok = htf_bias not in ["SHORT_ONLY", "BEARISH"]
        bias_bear_ok = htf_bias not in ["LONG_ONLY", "BULLISH"]

        # Máscaras
        long_signals = (in_kz & ob_bull & sweeps_bull & valid_trigger & bias_bull_ok)
        short_signals = (in_kz & ob_bear & sweeps_bear & valid_trigger & bias_bear_ok)

        # ── 3. Capa GGUF (Modo Híbrido) ──
        try:
            market_tokens = self.scheduler.get_market_tokens(df)
            gguf_high_prob = self.scheduler.predict_liquidity_sweep(market_tokens)
        except Exception as e:
            logger.warning(f"[OMEGA] Error GGUF: {e}")
            gguf_high_prob = False

        # ── 4. Formateo de Salida ──
        opportunities = []
        indices_long = np.where(long_signals)[0]
        indices_short = np.where(short_signals)[0]

        for idx in indices_long:
            signal = self._format_signal(idx, "LONG", df.iloc[idx], atr[idx] if idx < len(atr) else 0)
            if gguf_high_prob:
                signal["type"] = "LONG 🟢 (PLATINUM GGUF)"
                signal["quality_score"] = 0.98
            opportunities.append(signal)
            
        for idx in indices_short:
            signal = self._format_signal(idx, "SHORT", df.iloc[idx], atr[idx] if idx < len(atr) else 0)
            if gguf_high_prob:
                signal["type"] = "SHORT 🔴 (PLATINUM GGUF)"
                signal["quality_score"] = 0.95
            opportunities.append(signal)

        return opportunities

    def _format_signal(self, idx: int, direction: str, row: pd.Series, atr: float):
        if atr <= 0: atr = row['close'] * 0.01 # Fallback 1%
        return {
            "index": int(idx),
            "symbol": row.get('symbol', 'UNKNOWN'),
            "type": f"SMC {direction}",
            "direction": direction,
            "price": float(row['close']),
            "tp": float(row['close'] + (atr * 2.5 if direction == "LONG" else -atr * 2.5)),
            "sl": float(row['close'] - (atr * 1.5 if direction == "LONG" else -atr * 1.5)),
            "quality_score": 0.75,
            "timestamp": row.get('timestamp', '')
        }
