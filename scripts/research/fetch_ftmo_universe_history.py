"""
scripts/research/fetch_ftmo_universe_history.py — Ingesta Multi-Año FTMO Swing (SOP-154)
======================================================================================
Descarga y normaliza el historial de los 22 instrumentos candidatos de FTMO MT5
en 1h (730 días), 15m (60 días) y 1d (5 años) hacia engine/backtest/data/.
"""

import os
import sys
import time
from typing import Dict, List, Optional
import httpx
import pandas as pd

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "engine", "backtest", "data"))

FTMO_YAHOO_TICKERS: Dict[str, str] = {
    # Metales
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    # Energía y Metales Industriales
    "USOIL": "CL=F",
    "UKOIL": "BZ=F",
    "HGUSD": "HG=F",
    # Índices EE.UU.
    "US100": "NQ=F",
    "US500": "ES=F",
    "US30": "YM=F",
    "US2000": "RTY=F",
    # Índices Globales
    "GER40": "^GDAXI",
    "UK100": "^FTSE",
    "JP225": "^N225",
    "EU50": "^STOXX50E",
    # Forex G10 Majors & Crosses
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCAD": "USDCAD=X",
    "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "EURGBP": "EURGBP=X",
}

INTERVAL_RANGES = {
    "1h": "730d",
    "15m": "60d",
    "1d": "5y",
}


def clean_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
    # Eliminar velas muertas de fin de semana
    dead = (df["high"] == df["low"]) & (df["volume"].fillna(0) == 0)
    df = df[~dead].reset_index(drop=True)
    # Consistencia OHLC
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def fetch_yahoo_ohlcv(ticker: str, interval: str, yf_range: str) -> Optional[pd.DataFrame]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={yf_range}&interval={interval}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        with httpx.Client(timeout=15.0, verify=False) as client:
            res = client.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
            "open": quotes.get("open"),
            "high": quotes.get("high"),
            "low": quotes.get("low"),
            "close": quotes.get("close"),
            "volume": quotes.get("volume") or [0] * len(timestamps),
        })
        df["volume"] = df["volume"].fillna(0)
        return clean_ohlcv_df(df)
    except Exception as exc:
        print(f"  [WARN] Yahoo fallo para {ticker} ({interval}): {exc}")
        return None


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"[SOP-154] Ingesta de {len(FTMO_YAHOO_TICKERS)} activos FTMO hacia {DATA_DIR}")
    ok_count = 0
    for sym, ticker in FTMO_YAHOO_TICKERS.items():
        for tf, yf_range in INTERVAL_RANGES.items():
            out_path = os.path.join(DATA_DIR, f"{sym}_{tf}_audited.parquet")
            # Si ya existe un archivo robusto reciente (> 500 filas en 1h/1d o > 1000 en 15m), conservarlo
            if os.path.exists(out_path):
                try:
                    existing = pd.read_parquet(out_path)
                    min_rows = 1000 if tf == "15m" else 500
                    if len(existing) >= min_rows:
                        ok_count += 1
                        continue
                except Exception:
                    pass
            df = fetch_yahoo_ohlcv(ticker, tf, yf_range)
            if df is not None and len(df) >= 200:
                df.to_parquet(out_path, index=False)
                print(f"  [OK] {sym}_{tf}_audited.parquet -> {len(df)} velas")
                ok_count += 1
            else:
                print(f"  [SKIP] {sym} {tf}: datos insuficientes")
            time.sleep(0.15)
    print(f"[SOP-154] Ingesta finalizada. Datasets listos: {ok_count}/{len(FTMO_YAHOO_TICKERS)*len(INTERVAL_RANGES)}")


if __name__ == "__main__":
    main()
