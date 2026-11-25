/**
 * src/shared/lib/marketCalendar.ts
 * Espejo algorítmico ligero del calendario institucional NYSE / CME / LSE (SOP-160).
 * Cero dependencias externas; paridad 1:1 con engine/core/market_calendar.py.
 */

export interface VenueLiquidityStatus {
    venue: 'NYSE_CME' | 'LSE' | 'CRYPTO_24_7';
    execution_allowed: boolean;
    is_holiday: boolean;
    is_early_close: boolean;
    holiday_name: string | null;
    liquidity_regime: 'NORMAL' | 'EXCHANGE_HOLIDAY' | 'EARLY_CLOSE_THIN' | 'EARLY_CLOSE_ACTIVE' | 'US_BANK_HOLIDAY_THIN';
    early_close_ny_time: string | null;
}

function getTzParts(date: Date, timeZone: string): { year: number; month: number; day: number; hour: number; minute: number; weekday: number } {
    const dtf = new Intl.DateTimeFormat('en-US', {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        weekday: 'short',
    });
    const parts = Object.fromEntries(dtf.formatToParts(date).map((p) => [p.type, p.value]));
    const wdMap: Record<string, number> = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 0 };
    const hr = parseInt(parts.hour, 10);
    return {
        year: parseInt(parts.year, 10),
        month: parseInt(parts.month, 10),
        day: parseInt(parts.day, 10),
        hour: hr === 24 ? 0 : hr,
        minute: parseInt(parts.minute, 10),
        weekday: wdMap[parts.weekday] ?? 0,
    };
}

function keyOf(y: number, m: number, d: number): string {
    return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function easterSundayUtc(year: number): Date {
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const month = Math.floor((h + l - 7 * m + 114) / 31);
    const day = ((h + l - 7 * m + 114) % 31) + 1;
    return new Date(Date.UTC(year, month - 1, day));
}

function addDaysUtc(d: Date, days: number): Date {
    return new Date(d.getTime() + days * 86400000);
}

function keyFromUtcDate(d: Date): string {
    return keyOf(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
}

function observedUs(y: number, m: number, d: number): string {
    const dt = new Date(Date.UTC(y, m - 1, d));
    const wd = dt.getUTCDay();
    if (wd === 6) return keyFromUtcDate(addDaysUtc(dt, -1));
    if (wd === 0) return keyFromUtcDate(addDaysUtc(dt, 1));
    return keyFromUtcDate(dt);
}

function nthWeekdayUtc(y: number, m: number, targetWd: number, n: number): Date {
    const first = new Date(Date.UTC(y, m - 1, 1));
    const offset = (targetWd - first.getUTCDay() + 7) % 7;
    return addDaysUtc(first, offset + 7 * (n - 1));
}

function lastWeekdayUtc(y: number, m: number, targetWd: number): Date {
    const last = new Date(Date.UTC(y, m, 0));
    const offset = (last.getUTCDay() - targetWd + 7) % 7;
    return addDaysUtc(last, -offset);
}

function ukSubMonday(y: number, m: number, d: number): string {
    const dt = new Date(Date.UTC(y, m - 1, d));
    const wd = dt.getUTCDay();
    if (wd === 6) return keyFromUtcDate(addDaysUtc(dt, 2));
    if (wd === 0) return keyFromUtcDate(addDaysUtc(dt, 1));
    return keyFromUtcDate(dt);
}

export function getClientVenueLiquidityStatus(nowUtc: Date, symbol: string): VenueLiquidityStatus {
    const s = (symbol || '').toUpperCase().replace('.CASH', '').replace('.SIM', '');
    const venue: VenueLiquidityStatus['venue'] =
        s.includes('UK100') || s.includes('EU50') || s.includes('GER40') || s.includes('FTSE')
            ? 'LSE'
            : s.endsWith('USDT') && s !== 'XAUUSDT'
                ? 'CRYPTO_24_7'
                : 'NYSE_CME';

    const ny = getTzParts(nowUtc, 'America/New_York');
    const lon = getTzParts(nowUtc, 'Europe/London');

    const easterNy = easterSundayUtc(ny.year);
    const thanksgiving = nthWeekdayUtc(ny.year, 11, 4, 4);
    const nyseHolidays: Record<string, string> = {
        [observedUs(ny.year, 1, 1)]: "New Year's Day (NYSE)",
        [keyFromUtcDate(nthWeekdayUtc(ny.year, 1, 1, 3))]: 'Martin Luther King Jr. Day (NYSE)',
        [keyFromUtcDate(nthWeekdayUtc(ny.year, 2, 1, 3))]: "Washington's Birthday (NYSE)",
        [keyFromUtcDate(addDaysUtc(easterNy, -2))]: 'Good Friday (NYSE/CME)',
        [keyFromUtcDate(lastWeekdayUtc(ny.year, 5, 1))]: 'Memorial Day (NYSE)',
        [observedUs(ny.year, 6, 19)]: 'Juneteenth National Independence Day (NYSE)',
        [observedUs(ny.year, 7, 4)]: 'Independence Day (NYSE)',
        [keyFromUtcDate(nthWeekdayUtc(ny.year, 9, 1, 1))]: 'Labor Day (NYSE)',
        [keyFromUtcDate(thanksgiving)]: 'Thanksgiving Day (NYSE)',
        [observedUs(ny.year, 12, 25)]: 'Christmas Day (NYSE)',
    };

    const nyseEarly: Record<string, string> = {};
    const bf = addDaysUtc(thanksgiving, 1);
    const bfKey = keyFromUtcDate(bf);
    if (!nyseHolidays[bfKey]) nyseEarly[bfKey] = 'Day After Thanksgiving (Early Close 13:00 NY)';
    const j3 = new Date(Date.UTC(ny.year, 6, 3));
    if (j3.getUTCDay() >= 1 && j3.getUTCDay() <= 5 && !nyseHolidays[keyFromUtcDate(j3)]) {
        nyseEarly[keyFromUtcDate(j3)] = 'Independence Day Eve (Early Close 13:00 NY)';
    }
    const x24 = new Date(Date.UTC(ny.year, 11, 24));
    if (x24.getUTCDay() >= 1 && x24.getUTCDay() <= 5 && !nyseHolidays[keyFromUtcDate(x24)]) {
        nyseEarly[keyFromUtcDate(x24)] = 'Christmas Eve (Early Close 13:00 NY)';
    }

    if (venue === 'LSE') {
        const easterLon = easterSundayUtc(lon.year);
        const lseHolidays: Record<string, string> = {
            [ukSubMonday(lon.year, 1, 1)]: "New Year's Day (LSE)",
            [keyFromUtcDate(addDaysUtc(easterLon, -2))]: 'Good Friday (LSE)',
            [keyFromUtcDate(addDaysUtc(easterLon, 1))]: 'Easter Monday (LSE)',
            [keyFromUtcDate(nthWeekdayUtc(lon.year, 5, 1, 1))]: 'Early May Bank Holiday (LSE)',
            [keyFromUtcDate(lastWeekdayUtc(lon.year, 5, 1))]: 'Spring Bank Holiday (LSE)',
            [keyFromUtcDate(lastWeekdayUtc(lon.year, 8, 1))]: 'UK Summer Bank Holiday (LSE)',
            [ukSubMonday(lon.year, 12, 25)]: 'Christmas Day (LSE)',
            [ukSubMonday(lon.year, 12, 26)]: 'Boxing Day (LSE)',
        };
        const lonKey = keyOf(lon.year, lon.month, lon.day);
        const hName = lseHolidays[lonKey] ?? null;
        return {
            venue,
            execution_allowed: !hName,
            is_holiday: Boolean(hName),
            is_early_close: false,
            holiday_name: hName,
            liquidity_regime: hName ? 'EXCHANGE_HOLIDAY' : 'NORMAL',
            early_close_ny_time: null,
        };
    }

    const nyKey = keyOf(ny.year, ny.month, ny.day);
    const usHoliday = nyseHolidays[nyKey] ?? null;
    const usEarly = nyseEarly[nyKey] ?? null;

    if (venue === 'CRYPTO_24_7') {
        const thin = Boolean(usHoliday && ny.hour >= 8 && ny.hour < 17);
        return {
            venue,
            execution_allowed: true,
            is_holiday: Boolean(usHoliday),
            is_early_close: Boolean(usEarly),
            holiday_name: usHoliday ?? usEarly,
            liquidity_regime: thin ? 'US_BANK_HOLIDAY_THIN' : 'NORMAL',
            early_close_ny_time: usEarly ? '13:00 NY' : null,
        };
    }

    if (usHoliday) {
        return {
            venue,
            execution_allowed: false,
            is_holiday: true,
            is_early_close: false,
            holiday_name: usHoliday,
            liquidity_regime: 'EXCHANGE_HOLIDAY',
            early_close_ny_time: null,
        };
    }

    if (usEarly) {
        const cutoffReached = ny.hour * 60 + ny.minute >= 12 * 60 + 30;
        return {
            venue,
            execution_allowed: !cutoffReached,
            is_holiday: false,
            is_early_close: true,
            holiday_name: usEarly,
            liquidity_regime: cutoffReached ? 'EARLY_CLOSE_THIN' : 'EARLY_CLOSE_ACTIVE',
            early_close_ny_time: '13:00 NY',
        };
    }

    return {
        venue,
        execution_allowed: true,
        is_holiday: false,
        is_early_close: false,
        holiday_name: null,
        liquidity_regime: 'NORMAL',
        early_close_ny_time: null,
    };
}
