import asyncio
import pandas as pd
import numpy as np
from engine.indicators.data_utils import fetch_binance_history
from engine.indicators.market_analyzer import market_analyzer
from engine.indicators.regime import RegimeDetector

# ── LEGACY CALCULATORS FOR COMPARISON ────────────────────────────────────────

def legacy_detect_market_regime(df: pd.DataFrame) -> list:
    """Calcula el régimen usando la fórmula legacy (sin suavizar ni histéresis)."""
    if len(df) < 200:
        return ["UNKNOWN"] * len(df)
        
    close = df['close']
    high = df['high']
    low = df['low']
    
    sma_200 = close.rolling(window=200).mean()
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = tr.rolling(window=14).mean()
    atr_norm = (atr_14 / close) * 100
    
    up_move = high.diff()
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    plus_dm_14 = pd.Series(plus_dm, index=df.index).rolling(window=14).sum()
    minus_dm_14 = pd.Series(minus_dm, index=df.index).rolling(window=14).sum()
    tr_14_sum = tr.rolling(window=14).sum()
    
    plus_di = 100 * (plus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
    minus_di = 100 * (minus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
    dx = 100 * (abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, 1, (plus_di + minus_di)))
    adx_14 = pd.Series(dx, index=df.index).rolling(window=14).mean()
    
    regimes = []
    for idx in range(len(df)):
        if idx < 200:
            regimes.append("UNKNOWN")
            continue
            
        cur_price = close.iloc[idx]
        cur_sma = sma_200.iloc[idx]
        cur_adx = adx_14.iloc[idx]
        cur_plus_di = plus_di.iloc[idx]
        cur_minus_di = minus_di.iloc[idx]
        cur_atr_norm = atr_norm.iloc[idx]
        
        bias = "BULLISH" if cur_price > cur_sma else "BEARISH"
        
        if cur_adx < 20:
            reg = "CHOPPY"
        elif 20 <= cur_adx < 40:
            if bias == "BULLISH" and cur_plus_di > cur_minus_di:
                reg = "TRENDING_BULL"
            elif bias == "BEARISH" and cur_minus_di > cur_plus_di:
                reg = "TRENDING_BEAR"
            else:
                reg = "TRANSITION"
        else:
            reg = "STRONG_BULL" if bias == "BULLISH" else "STRONG_BEAR"
            
        if cur_atr_norm > 1.5:
            reg = "HIGH_VOLATILITY_STRESS"
            
        regimes.append(reg)
    return regimes


def legacy_detect_wyckoff_regime(df: pd.DataFrame) -> list:
    """Calcula el régimen Wyckoff sin suavizado ni persistencia."""
    if len(df) < 50:
        return ["UNKNOWN"] * len(df)
        
    df = df.copy()
    change = abs(df['close'] - df['close'].shift(50))
    volatility = abs(df['close'] - df['close'].shift(1)).rolling(window=50).sum()
    df['efficiency'] = change / (volatility + 1e-9)
    
    rolling_high = df['high'].rolling(window=50).max()
    rolling_low = df['low'].rolling(window=50).min()
    range_size = rolling_high - rolling_low
    df['pos_pct'] = (df['close'] - rolling_low) / (range_size + 1e-9)
    df['mom_long'] = df['close'].diff(50)
    
    df['market_regime'] = 'RANGING'
    mask_markup = (df['mom_long'] > 0) & (df['efficiency'] > 0.3)
    mask_markdown = (df['mom_long'] < 0) & (df['efficiency'] > 0.3)
    mask_accum = (df['efficiency'] <= 0.3) & (df['pos_pct'] < 0.3)
    mask_distrib = (df['efficiency'] <= 0.3) & (df['pos_pct'] > 0.7)
    mask_choppy = (df['efficiency'] < 0.1)
    
    df.loc[mask_markup, 'market_regime'] = 'MARKUP'
    df.loc[mask_markdown, 'market_regime'] = 'MARKDOWN'
    df.loc[mask_accum, 'market_regime'] = 'ACCUMULATION'
    df.loc[mask_distrib, 'market_regime'] = 'DISTRIBUTION'
    df.loc[mask_choppy, 'market_regime'] = 'CHOPPY'
    df['market_regime'] = df['market_regime'].fillna('RANGING')
    
    return df['market_regime'].tolist()


# ── AUDIT RUNNER ─────────────────────────────────────────────────────────────

async def audit_asset(symbol: str, limit: int = 400):
    print(f"\n=======================================================")
    print(f"📊 AUDITANDO ESTABILIZACIÓN DEL RÉGIMEN PARA: {symbol}")
    print(f"=======================================================")
    
    raw_history = await fetch_binance_history(symbol, "5m", limit=limit)
    if not raw_history:
        print(f"❌ Error: No se pudo obtener el historial para {symbol}")
        return
        
    df = pd.DataFrame([i["data"] for i in raw_history])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    
    # 1. Ejecutar Lógica ADX (MarketAnalyzer)
    legacy_adx = legacy_detect_market_regime(df)
    
    # La nueva lógica escribe la serie de regímenes persistentes para auditarla completa
    # Vamos a replicar la lógica de persistencia del nuevo MarketAnalyzer para toda la serie
    # para poder comparar vela a vela:
    close = df['close']
    high = df['high']
    low = df['low']
    sma_200_series = close.rolling(window=200).mean()
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14_series = tr.rolling(window=14).mean()
    atr_norm_series = (atr_14_series / close) * 100 
    up_move = high.diff()
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    plus_dm_14 = pd.Series(plus_dm, index=df.index).rolling(window=14).sum()
    minus_dm_14 = pd.Series(minus_dm, index=df.index).rolling(window=14).sum()
    tr_14_sum = tr.rolling(window=14).sum()
    plus_di = 100 * (plus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
    minus_di = 100 * (minus_dm_14 / np.where(tr_14_sum == 0, 1, tr_14_sum))
    dx = 100 * (abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, 1, (plus_di + minus_di)))
    adx_14_series = pd.Series(dx, index=df.index).rolling(window=14).mean()
    adx_smooth = adx_14_series.ewm(span=5, adjust=False).mean()
    plus_di_smooth = pd.Series(plus_di, index=df.index).ewm(span=5, adjust=False).mean()
    minus_di_smooth = pd.Series(minus_di, index=df.index).ewm(span=5, adjust=False).mean()
    
    new_adx_raw = []
    is_trending = False
    for idx in range(len(df)):
        if idx < 200:
            new_adx_raw.append("UNKNOWN")
            continue
        cur_price = close.iloc[idx]
        cur_sma = sma_200_series.iloc[idx]
        cur_adx = adx_smooth.iloc[idx]
        cur_plus_di = plus_di_smooth.iloc[idx]
        cur_minus_di = minus_di_smooth.iloc[idx]
        cur_atr_norm = atr_norm_series.iloc[idx]
        bias = "BULLISH" if cur_price > cur_sma else "BEARISH"
        if cur_adx > 22:
            is_trending = True
        elif cur_adx < 18:
            is_trending = False
        if not is_trending:
            reg = "CHOPPY"
        elif 20 <= cur_adx < 40:
            if bias == "BULLISH" and cur_plus_di > cur_minus_di:
                reg = "TRENDING_BULL"
            elif bias == "BEARISH" and cur_minus_di > cur_plus_di:
                reg = "TRENDING_BEAR"
            else:
                reg = "TRANSITION"
        else:
            reg = "STRONG_BULL" if bias == "BULLISH" else "STRONG_BEAR"
        if cur_atr_norm > 1.5:
            reg = "HIGH_VOLATILITY_STRESS"
        new_adx_raw.append(reg)
        
    new_adx_persistent = []
    last_p = "UNKNOWN"
    for idx in range(len(df)):
        if idx < 202:
            new_adx_persistent.append(new_adx_raw[idx])
            if new_adx_raw[idx] != "UNKNOWN":
                last_p = new_adx_raw[idx]
            continue
        window = new_adx_raw[idx-2:idx+1]
        if len(set(window)) == 1:
            last_p = window[-1]
        new_adx_persistent.append(last_p)

    # 2. Ejecutar Lógica Wyckoff (RegimeDetector)
    legacy_wyckoff = legacy_detect_wyckoff_regime(df)
    detector = RegimeDetector(window=50)
    df_new_wyckoff = detector.detect_regime(df)
    new_wyckoff = df_new_wyckoff["market_regime"].tolist()

    # ── MÉTRETICAS DE FILTRADO (Flickering Audit) ──
    def count_switches(lst: list) -> int:
        switches = 0
        for i in range(1, len(lst)):
            if lst[i] != lst[i-1] and lst[i] != "UNKNOWN" and lst[i-1] != "UNKNOWN":
                switches += 1
        return switches

    sw_legacy_adx = count_switches(legacy_adx)
    sw_new_adx = count_switches(new_adx_persistent)
    red_adx = ((sw_legacy_adx - sw_new_adx) / sw_legacy_adx * 100) if sw_legacy_adx > 0 else 0
    
    sw_legacy_wyckoff = count_switches(legacy_wyckoff)
    sw_new_wyckoff = count_switches(new_wyckoff)
    red_wyckoff = ((sw_legacy_wyckoff - sw_new_wyckoff) / sw_legacy_wyckoff * 100) if sw_legacy_wyckoff > 0 else 0

    print(f"📈 DETECTOR DE TENDENCIA (MarketAnalyzer - ADX):")
    print(f"   • Cambios de Régimen (Legacy): {sw_legacy_adx}")
    print(f"   • Cambios de Régimen (Optimizado/Filtro): {sw_new_adx}")
    print(f"   • Reducción de Ruido (Flickering): {red_adx:.1f}%")
    
    print(f"🛡️ DETECTOR DE ESTRUCTURA (RegimeDetector - Wyckoff):")
    print(f"   • Cambios de Régimen (Legacy): {sw_legacy_wyckoff}")
    print(f"   • Cambios de Régimen (Optimizado/Filtro): {sw_new_wyckoff}")
    print(f"   • Reducción de Ruido (Flickering): {red_wyckoff:.1f}%")
    
    # Asegurar que el estado actual del analizador sea válido
    current_state = market_analyzer.detect_market_regime(df)
    print(f"⭐ Estado actual en vivo del Analizador: {current_state['regime']} (Confianza: {current_state['confidence']}%)")

async def main():
    await audit_asset("BTCUSDT")
    await audit_asset("SOLUSDT")

if __name__ == '__main__':
    asyncio.run(main())
