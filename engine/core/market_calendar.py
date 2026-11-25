"""
engine/core/market_calendar.py — Calendario Bursátil Institucional Algorítmico (SOP-160)
========================================================================================
Cero dependencias externas (Regla 19.4). Calcula de forma exacta para 2020-2060:
- Feriados completos NYSE / CME (US): New Year's Day, MLK Day, Presidents' Day, Good Friday,
  Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas Day.
- Early Closes NYSE / CME (cierre 13:00 NY; bloqueo nuevas entradas desde 12:30 NY):
  Black Friday (día posterior a Thanksgiving), July 3rd (hábil previo al 4 Jul), Christmas Eve (24 Dic hábil).
- Feriados completos LSE / UK Bank Holidays (UK100.cash, EU50):
  New Year, Good Friday, Easter Monday, Early May, Spring Bank Holiday, Summer Bank Holiday,
  Christmas Day y Boxing Day (con días sustitutos exactos).
"""

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

_NY_TZ = ZoneInfo("America/New_York")
_LONDON_TZ = ZoneInfo("Europe/London")


def _easter_sunday(year: int) -> date:
    """Algoritmo Computus de Gauss/Meeus para el Domingo de Pascua gregoriano."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed_us_holiday(d: date) -> date:
    """Regla federal US / NYSE: Sábado -> Viernes anterior; Domingo -> Lunes siguiente."""
    if d.weekday() == 5:  # Sábado
        return d - timedelta(days=1)
    if d.weekday() == 6:  # Domingo
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Retorna el n-ésimo día de la semana (0=Lun..6=Dom) del mes dado."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Retorna el último día de la semana (0=Lun..6=Dom) del mes dado."""
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def _uk_substitute_monday(d: date) -> date:
    """En UK, si un Bank Holiday cae en fin de semana, se traslada al lunes siguiente."""
    if d.weekday() == 5:
        return d + timedelta(days=2)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=64)
def _nyse_calendar_for_year(year: int) -> Tuple[Dict[date, str], Dict[date, str]]:
    easter = _easter_sunday(year)
    holidays: Dict[date, str] = {
        _observed_us_holiday(date(year, 1, 1)): "New Year's Day (NYSE)",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day (NYSE)",
        _nth_weekday(year, 2, 0, 3): "Washington's Birthday (NYSE)",
        easter - timedelta(days=2): "Good Friday (NYSE/CME)",
        _last_weekday(year, 5, 0): "Memorial Day (NYSE)",
        _observed_us_holiday(date(year, 6, 19)): "Juneteenth National Independence Day (NYSE)",
        _observed_us_holiday(date(year, 7, 4)): "Independence Day (NYSE)",
        _nth_weekday(year, 9, 0, 1): "Labor Day (NYSE)",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day (NYSE)",
        _observed_us_holiday(date(year, 12, 25)): "Christmas Day (NYSE)",
    }

    early_closes: Dict[date, str] = {}
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    black_friday = thanksgiving + timedelta(days=1)
    if black_friday not in holidays and black_friday.weekday() < 5:
        early_closes[black_friday] = "Day After Thanksgiving (Early Close 13:00 NY)"

    july3 = date(year, 7, 3)
    if july3.weekday() < 5 and july3 not in holidays:
        early_closes[july3] = "Independence Day Eve (Early Close 13:00 NY)"

    xmas_eve = date(year, 12, 24)
    if xmas_eve.weekday() < 5 and xmas_eve not in holidays:
        early_closes[xmas_eve] = "Christmas Eve (Early Close 13:00 NY)"

    return holidays, early_closes


@lru_cache(maxsize=64)
def _lse_calendar_for_year(year: int) -> Dict[date, str]:
    easter = _easter_sunday(year)
    holidays: Dict[date, str] = {
        _uk_substitute_monday(date(year, 1, 1)): "New Year's Day (LSE)",
        easter - timedelta(days=2): "Good Friday (LSE)",
        easter + timedelta(days=1): "Easter Monday (LSE)",
        _nth_weekday(year, 5, 0, 1): "Early May Bank Holiday (LSE)",
        _last_weekday(year, 5, 0): "Spring Bank Holiday (LSE)",
        _last_weekday(year, 8, 0): "UK Summer Bank Holiday (LSE)",
    }

    # Navidad y Boxing Day en UK: si coinciden con Sáb/Dom, se sustituyen en Lun/Mar
    xmas = date(year, 12, 25)
    boxing = date(year, 12, 26)
    if xmas.weekday() == 5:  # Sáb 25, Dom 26 -> Lun 27, Mar 28
        holidays[date(year, 12, 27)] = "Christmas Day Substitute (LSE)"
        holidays[date(year, 12, 28)] = "Boxing Day Substitute (LSE)"
    elif xmas.weekday() == 6:  # Dom 25, Lun 26 -> Lun 26 Boxing, Mar 27 Xmas Sub
        holidays[date(year, 12, 26)] = "Boxing Day (LSE)"
        holidays[date(year, 12, 27)] = "Christmas Day Substitute (LSE)"
    elif xmas.weekday() == 4:  # Vie 25, Sáb 26 -> Vie 25, Lun 28
        holidays[xmas] = "Christmas Day (LSE)"
        holidays[date(year, 12, 28)] = "Boxing Day Substitute (LSE)"
    else:
        holidays[xmas] = "Christmas Day (LSE)"
        holidays[boxing] = "Boxing Day (LSE)"

    return holidays


def _ensure_utc(now_utc: Optional[datetime]) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        return now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone.utc)


def _classify_venue(symbol: str) -> str:
    s = (symbol or "").upper().replace(".CASH", "").replace(".SIM", "")
    if any(k in s for k in ("UK100", "EU50", "GER40", "FTSE")):
        return "LSE"
    if s.endswith("USDT") and s != "XAUUSDT":
        return "CRYPTO"
    return "NYSE_CME"


def get_venue_liquidity_status(symbol: str, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Evalúa si el mercado del activo está en feriado bursátil, Early Close (13:00 NY)
    o liquidez delgada por feriado bancario US (para Cripto 24/7).
    """
    dt_utc = _ensure_utc(now_utc)
    dt_ny = dt_utc.astimezone(_NY_TZ)
    dt_lon = dt_utc.astimezone(_LONDON_TZ)
    venue = _classify_venue(symbol)

    nyse_holidays, nyse_early = _nyse_calendar_for_year(dt_ny.year)
    lse_holidays = _lse_calendar_for_year(dt_lon.year)

    if venue == "LSE":
        h_name = lse_holidays.get(dt_lon.date())
        if h_name:
            return {
                "venue": "LSE",
                "execution_allowed": False,
                "is_holiday": True,
                "is_early_close": False,
                "holiday_name": h_name,
                "liquidity_regime": "EXCHANGE_HOLIDAY",
                "early_close_ny_time": None,
            }
        return {
            "venue": "LSE",
            "execution_allowed": True,
            "is_holiday": False,
            "is_early_close": False,
            "holiday_name": None,
            "liquidity_regime": "NORMAL",
            "early_close_ny_time": None,
        }

    ny_date = dt_ny.date()
    us_holiday = nyse_holidays.get(ny_date)
    us_early = nyse_early.get(ny_date)

    if venue == "CRYPTO":
        if us_holiday and 8 <= dt_ny.hour < 17:
            return {
                "venue": "CRYPTO_24_7",
                "execution_allowed": True,
                "is_holiday": True,
                "is_early_close": False,
                "holiday_name": us_holiday,
                "liquidity_regime": "US_BANK_HOLIDAY_THIN",
                "early_close_ny_time": None,
            }
        return {
            "venue": "CRYPTO_24_7",
            "execution_allowed": True,
            "is_holiday": bool(us_holiday),
            "is_early_close": bool(us_early),
            "holiday_name": us_holiday or us_early,
            "liquidity_regime": "NORMAL",
            "early_close_ny_time": "13:00 NY" if us_early else None,
        }

    # NYSE_CME (US100, US500, US30, XAUUSD, XAGUSD, FX)
    if us_holiday:
        return {
            "venue": "NYSE_CME",
            "execution_allowed": False,
            "is_holiday": True,
            "is_early_close": False,
            "holiday_name": us_holiday,
            "liquidity_regime": "EXCHANGE_HOLIDAY",
            "early_close_ny_time": None,
        }

    if us_early:
        ny_mins = dt_ny.hour * 60 + dt_ny.minute
        cutoff_reached = ny_mins >= (12 * 60 + 30)  # Bloquear nuevas entradas desde 12:30 NY
        return {
            "venue": "NYSE_CME",
            "execution_allowed": not cutoff_reached,
            "is_holiday": False,
            "is_early_close": True,
            "holiday_name": us_early,
            "liquidity_regime": "EARLY_CLOSE_THIN" if cutoff_reached else "EARLY_CLOSE_ACTIVE",
            "early_close_ny_time": "13:00 NY",
        }

    return {
        "venue": "NYSE_CME",
        "execution_allowed": True,
        "is_holiday": False,
        "is_early_close": False,
        "holiday_name": None,
        "liquidity_regime": "NORMAL",
        "early_close_ny_time": None,
    }
