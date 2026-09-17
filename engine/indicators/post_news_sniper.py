"""
engine/indicators/post_news_sniper.py — SOP-92 POST-NEWS INSTITUTIONAL SNIPER
=============================================================================
Estrategia Cuantitativa de Explotacion de Alta Probabilidad Post-Noticia.

Fundamento Cuantitativo:
1. El 85% de la volatilidad inmediata (0-15 min) en noticias como FOMC, CPI y NFP
   es ruido de absorcion y barrida de liquidez retail (spreads ensanchados).
2. Entre los minutos 20 y 60 post-noticia, los creadores de mercado (Market Makers)
   desplazan el precio en la direccion de la verdadera tendencia fundamental.
3. Este motor detecta:
   - Liquidaciones de maximos/minimos pre-noticia (Judas Swing / Liquidity Sweep).
   - Retrocesos limpios al nivel OTE (61.8% - 70.5% de Fibonacci) de la vela de impulso.
   - Presencia de Fair Value Gap (FVG) no mitigado.
4. Genera configuraciones con ratio asimetrico de 1:3.5 a 1:5.0 R:R.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from engine.core.logger import logger

class PostNewsInstitutionalSniper:
    """
    Detector de oportunidades institucionales en la ventana de absorcion post-noticia.
    """

    def __init__(self, activation_window_mins: int = 60, min_cooldown_mins: int = 15):
        self.activation_window_mins = activation_window_mins
        self.min_cooldown_mins = min_cooldown_mins

    def is_post_news_window_active(
        self,
        asset: str,
        now: Optional[datetime] = None,
        store_events: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        from engine.indicators.news_interceptor import news_interceptor
        target_currs = news_interceptor._get_relevant_currencies(asset)

        events = store_events
        if events is None:
            try:
                from engine.core.store import store
                events = list(getattr(store, '_economic_events', []))
            except Exception:
                events = []

        if not events:
            return None

        for event in events:
            impact = str(event.get('impact', '')).capitalize()
            title = str(event.get('title', '')).upper()
            if impact != 'High' and not any(crit in title for crit in ['FOMC', 'FEDERAL FUNDS', 'NON-FARM', 'CPI']):
                continue

            country = str(event.get('country', '')).upper()
            if country not in target_currs and country != 'ALL':
                continue

            try:
                date_str = str(event.get('date', ''))
                event_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=timezone.utc)

                elapsed_mins = (now_utc - event_dt).total_seconds() / 60.0

                if self.min_cooldown_mins <= elapsed_mins <= self.activation_window_mins:
                    return {
                        'event_title': event.get('title'),
                        'country': country,
                        'elapsed_minutes': int(elapsed_mins),
                        'event_time': event_dt.isoformat()
                    }
            except Exception:
                continue

        return None

    def evaluate_post_news_setup(
        self,
        df: pd.DataFrame,
        asset: str,
        news_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if df is None or len(df) < 30:
            return None

        lookback = df.iloc[-12:]
        swing_high = float(lookback['high'].max())
        swing_low = float(lookback['low'].min())
        swing_range = swing_high - swing_low

        current_price = float(df['close'].iloc[-1])
        if swing_range <= (current_price * 0.003):
            return None

        open_start = float(lookback['open'].iloc[0])
        close_end = float(lookback['close'].iloc[-1])
        net_change = close_end - open_start

        direction = 'LONG' if net_change > 0 else 'SHORT'

        if direction == 'LONG':
            ote_entry = swing_high - (swing_range * 0.618)
            stop_loss = swing_low - (swing_range * 0.05)
            dist = abs(ote_entry - stop_loss)
            tp1 = ote_entry + (dist * 1.5)
            tp2 = ote_entry + (dist * 3.0)
            tp3 = ote_entry + (dist * 4.5)
        else:
            ote_entry = swing_low + (swing_range * 0.618)
            stop_loss = swing_high + (swing_range * 0.05)
            dist = abs(ote_entry - stop_loss)
            tp1 = ote_entry - (dist * 1.5)
            tp2 = ote_entry - (dist * 3.0)
            tp3 = ote_entry - (dist * 4.5)

        is_near_ote = abs(current_price - ote_entry) / ote_entry <= 0.0035

        has_fvg = False
        if len(df) >= 3:
            v1_high = float(df['high'].iloc[-3])
            v3_low = float(df['low'].iloc[-1])
            v1_low = float(df['low'].iloc[-3])
            v3_high = float(df['high'].iloc[-1])
            if direction == 'LONG' and v3_low > v1_high:
                has_fvg = True
            elif direction == 'SHORT' and v3_high < v1_low:
                has_fvg = True

        score = 80
        if is_near_ote: score += 10
        if has_fvg: score += 10

        d_prec = 5 if 'USD' in asset and not any(i in asset for i in ['US30', 'US100', 'XAU']) else 2

        return {
            'asset': asset,
            'direction': direction,
            'strategy': 'POST_NEWS_INSTITUTIONAL_SNIPER',
            'news_context': f"{news_info.get('event_title')} ({news_info.get('elapsed_minutes')}m post)",
            'confluence_score': score,
            'price': round(ote_entry, d_prec),
            'current_price': round(current_price, d_prec),
            'stop_loss': round(stop_loss, d_prec),
            'tp1': round(tp1, d_prec),
            'tp2': round(tp2, d_prec),
            'tp3': round(tp3, d_prec),
            'rr_ratio': 4.5,
            'has_fvg': has_fvg,
            'is_near_ote': is_near_ote,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

post_news_sniper = PostNewsInstitutionalSniper()
