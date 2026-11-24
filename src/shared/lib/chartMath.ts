/**
 * Deterministic Chart Math & Structural Memoization Helpers
 * FSD Layer: shared/lib
 *
 * Pure, zero-side-effect primitives used by TradingChart (lightweight-charts v5.1.0).
 */

export interface ChartCandleLike {
    time: number | string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

export interface ChartPoint {
    time: number;
    value: number;
}

export interface ActiveSetupLevels {
    symbol: string;
    direction: 'LONG' | 'SHORT';
    entry: number;
    stopLoss: number;
    bePrice?: number;
    tp1?: number;
    tp2?: number;
    tp3?: number;
    status?: string;
    confluenceScore?: number;
}

const TIMEFRAME_SECONDS: Record<string, number> = {
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    '2h': 7200,
    '4h': 14400,
    '8h': 28800,
    '1d': 86400,
    '1w': 604800,
    '1M': 2592000,
};

/**
 * Computes an Exponential Moving Average (EMA) in O(N) time.
 * Seeds with the SMA of the first `period` candles (or available prefix if fewer candles exist,
 * requiring at least `minPoints` bars to emit values).
 */
export function computeEMA(
    candles: ChartCandleLike[],
    period: number = 200,
    minPoints: number = 20
): ChartPoint[] {
    if (!candles || candles.length < Math.min(period, minPoints) || period <= 0) {
        return [];
    }

    const effectivePeriod = Math.min(period, candles.length);
    const k = 2 / (period + 1);
    const result: ChartPoint[] = [];

    let sum = 0;
    for (let i = 0; i < effectivePeriod; i++) {
        sum += Number(candles[i].close);
    }
    let ema = sum / effectivePeriod;
    result.push({ time: Number(candles[effectivePeriod - 1].time), value: ema });

    for (let i = effectivePeriod; i < candles.length; i++) {
        const close = Number(candles[i].close);
        ema = close * k + ema * (1 - k);
        result.push({ time: Number(candles[i].time), value: ema });
    }

    return result;
}

/**
 * Computes UTC-daily Anchored VWAP (Session AVWAP) in O(N) time.
 * Resets cumulative PV and volume at 00:00 UTC boundary, matching SOP-114 / SOP-134.
 */
export function computeSessionAVWAP(candles: ChartCandleLike[]): ChartPoint[] {
    if (!candles || candles.length === 0) return [];

    const result: ChartPoint[] = [];
    let currentDayKey = -1;
    let cumPV = 0;
    let cumVol = 0;

    for (let i = 0; i < candles.length; i++) {
        const c = candles[i];
        const ts = Number(c.time);
        if (!Number.isFinite(ts) || ts <= 0) continue;

        const dayKey = Math.floor(ts / 86400);
        if (dayKey !== currentDayKey) {
            currentDayKey = dayKey;
            cumPV = 0;
            cumVol = 0;
        }

        const typicalPrice = (Number(c.high) + Number(c.low) + Number(c.close)) / 3;
        const vol = Math.max(Number(c.volume ?? 0), 0);

        if (vol > 0) {
            cumPV += typicalPrice * vol;
            cumVol += vol;
        }

        const vwap = cumVol > 0 ? cumPV / cumVol : typicalPrice;
        result.push({ time: ts, value: vwap });
    }

    return result;
}

/**
 * Returns remaining time until the current UTC candle closes for a given timeframe.
 */
export function getCandleCountdown(
    timeframe: string,
    nowMs: number = Date.now()
): { remainingSeconds: number; formatted: string } {
    const tfSec = TIMEFRAME_SECONDS[timeframe] ?? 900;
    const nowSec = Math.floor(nowMs / 1000);
    const elapsed = nowSec % tfSec;
    const remainingSeconds = elapsed === 0 ? tfSec : tfSec - elapsed;

    const hours = Math.floor(remainingSeconds / 3600);
    const minutes = Math.floor((remainingSeconds % 3600) / 60);
    const seconds = remainingSeconds % 60;

    const pad = (n: number) => String(n).padStart(2, '0');
    const formatted =
        hours > 0
            ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
            : `${pad(minutes)}:${pad(seconds)}`;

    return { remainingSeconds, formatted };
}

/**
 * Builds a lightweight deterministic fingerprint for overlay structures so React effects
 * do not tear down and recreate Lightweight Charts series on identical 1.5s REST polls.
 */
export function buildStructuralFingerprint(payload: unknown): string {
    if (payload == null) return 'null';
    try {
        return JSON.stringify(payload);
    } catch {
        return String(Date.now());
    }
}

/**
 * Extracts the most relevant active setup (Entry, SL, BE, TP1/TP2/TP3) for the active symbol
 * from tacticalDecision.signals, auditedSignals, or signalHistory.
 */
export function extractActiveSymbolSetup(
    activeSymbol: string,
    tacticalSignals?: Array<Record<string, any>>,
    auditedSignals?: Record<string, Record<string, any>>,
    signalHistory?: Record<string, Record<string, any>>
): ActiveSetupLevels | null {
    const cleanTarget = (activeSymbol || '').replace(/[\s/]/g, '').toUpperCase();
    if (!cleanTarget) return null;

    const candidates: Array<Record<string, any>> = [
        ...(Array.isArray(tacticalSignals) ? tacticalSignals : []),
        ...Object.values(auditedSignals || {}),
        ...Object.values(signalHistory || {}),
    ];

    const matching = candidates.filter((sig) => {
        if (!sig) return false;
        const asset = String(sig.asset || sig.symbol || '')
            .replace(/[\s/]/g, '')
            .toUpperCase();
        if (asset !== cleanTarget) return false;

        const entry = Number(sig.price ?? sig.entry_price ?? sig.bitunix_order?.price);
        const sl = Number(sig.stop_loss ?? sig.bitunix_order?.stopLoss);
        if (!Number.isFinite(entry) || entry <= 0 || !Number.isFinite(sl) || sl <= 0) {
            return false;
        }

        const status = String(sig.status || '').toUpperCase();
        if (status === 'CLOSED' || status === 'CANCELLED' || status === 'EXPIRED' || status === 'REJECTED') {
            return false;
        }
        return true;
    });

    if (matching.length === 0) return null;

    // Sort newest first by timestamp / created_at
    matching.sort((a, b) => {
        const ta = new Date(a.timestamp || a.created_at || 0).getTime() || Number(a.timestamp || 0);
        const tb = new Date(b.timestamp || b.created_at || 0).getTime() || Number(b.timestamp || 0);
        return tb - ta;
    });

    const latest = matching[0];
    const entry = Number(latest.price ?? latest.entry_price ?? latest.bitunix_order?.price);
    const stopLoss = Number(latest.stop_loss ?? latest.bitunix_order?.stopLoss);
    const rawType = String(latest.signal_type || latest.direction || latest.type || '').toUpperCase();
    const direction: 'LONG' | 'SHORT' =
        rawType.includes('SHORT') || rawType.includes('SELL') || stopLoss > entry ? 'SHORT' : 'LONG';

    const risk = Math.abs(entry - stopLoss);
    const sign = direction === 'LONG' ? 1 : -1;

    const tp1 = Number(latest.tp1) > 0 ? Number(latest.tp1) : entry + sign * risk * 1.5;
    const tp2 = Number(latest.tp2) > 0 ? Number(latest.tp2) : entry + sign * risk * 2.5;
    const tp3 =
        Number(latest.tp3 ?? latest.take_profit_3r ?? latest.bitunix_order?.takeProfit) > 0
            ? Number(latest.tp3 ?? latest.take_profit_3r ?? latest.bitunix_order?.takeProfit)
            : entry + sign * risk * 3.5;

    const bePrice =
        Number(latest.be_price) > 0 ? Number(latest.be_price) : entry + sign * risk * 1.0;

    return {
        symbol: cleanTarget,
        direction,
        entry,
        stopLoss,
        bePrice,
        tp1,
        tp2,
        tp3,
        status: latest.status ? String(latest.status) : 'ACTIVE',
        confluenceScore:
            typeof latest.confluence_score === 'number'
                ? latest.confluence_score
                : typeof latest.confluence?.score === 'number'
                    ? latest.confluence.score
                    : undefined,
    };
}

export interface VolumeProfileResult {
    poc: number;
    vah: number;
    val: number;
    lvns: number[];
}

export interface MarketTrapMarker {
    time: number;
    type: 'BULL_TRAP' | 'BEAR_TRAP';
    label: string;
}

export interface WilliamsOopsMarker {
    time: number;
    direction: 'LONG' | 'SHORT';
    label: string;
}

export interface AutoFibResult {
    swing_high: number;
    swing_low: number;
    levels: Record<string, number>;
}

/**
 * Computes institutional Volume Profile (POC, 70% VAH/VAL, LVNs) in O(N * bins) time,
 * matching engine/indicators/volume.py:calculate_volume_profile.
 */
export function computeVolumeProfile(
    candles: ChartCandleLike[],
    bins: number = 50
): VolumeProfileResult | null {
    if (!candles || candles.length < 20 || bins < 5) return null;

    let minPrice = Infinity;
    let maxPrice = -Infinity;
    for (const c of candles) {
        const lo = Number(c.low);
        const hi = Number(c.high);
        if (lo < minPrice) minPrice = lo;
        if (hi > maxPrice) maxPrice = hi;
    }

    if (!Number.isFinite(minPrice) || !Number.isFinite(maxPrice) || maxPrice <= minPrice) {
        return null;
    }

    const step = (maxPrice - minPrice) / bins;
    const volAtPrice = new Float64Array(bins);

    for (const c of candles) {
        const lo = Number(c.low);
        const hi = Number(c.high);
        const vol = Math.max(Number(c.volume ?? 0), 0);
        if (vol <= 0) continue;

        const startBin = Math.max(0, Math.min(bins - 1, Math.floor((lo - minPrice) / step)));
        const endBin = Math.max(0, Math.min(bins - 1, Math.floor((hi - minPrice) / step)));
        const count = endBin - startBin + 1;
        const perBin = vol / count;
        for (let b = startBin; b <= endBin; b++) {
            volAtPrice[b] += perBin;
        }
    }

    let totalVol = 0;
    let pocIdx = 0;
    let maxBinVol = -1;
    for (let b = 0; b < bins; b++) {
        totalVol += volAtPrice[b];
        if (volAtPrice[b] > maxBinVol) {
            maxBinVol = volAtPrice[b];
            pocIdx = b;
        }
    }

    if (totalVol <= 0) return null;

    const poc = minPrice + (pocIdx + 0.5) * step;
    const targetVol = totalVol * 0.7;
    let accumulated = volAtPrice[pocIdx];
    let loIdx = pocIdx;
    let hiIdx = pocIdx;

    while (accumulated < targetVol && (loIdx > 0 || hiIdx < bins - 1)) {
        const upVol = hiIdx < bins - 1 ? volAtPrice[hiIdx + 1] : -1;
        const dnVol = loIdx > 0 ? volAtPrice[loIdx - 1] : -1;
        if (upVol >= dnVol) {
            hiIdx++;
            accumulated += Math.max(upVol, 0);
        } else {
            loIdx--;
            accumulated += Math.max(dnVol, 0);
        }
    }

    const vah = minPrice + (hiIdx + 1) * step;
    const val = minPrice + loIdx * step;

    // Low Volume Nodes (local minima below 35% of mean bin volume)
    const meanVol = totalVol / bins;
    const lvns: number[] = [];
    for (let b = 2; b < bins - 2; b++) {
        const v = volAtPrice[b];
        if (v > 0 && v < meanVol * 0.35 && v <= volAtPrice[b - 1] && v <= volAtPrice[b + 1]) {
            lvns.push(minPrice + (b + 0.5) * step);
        }
    }

    return { poc, vah, val, lvns: lvns.slice(0, 3) };
}

/**
 * Detects historical Look Above/Below & Fail (LAF/LBF) institutional liquidity traps
 * over the visible candles, matching engine/indicators/structure.py:identify_look_and_fail.
 */
export function computeMarketTraps(
    candles: ChartCandleLike[],
    sessionLevels?: { pdh?: number | null; pdl?: number | null; onh?: number | null; onl?: number | null } | null,
    lookback: number = 20
): MarketTrapMarker[] {
    if (!candles || candles.length < lookback + 2) return [];

    const markers: MarketTrapMarker[] = [];
    const pdh = sessionLevels?.pdh && sessionLevels.pdh > 0 ? sessionLevels.pdh : null;
    const pdl = sessionLevels?.pdl && sessionLevels.pdl > 0 ? sessionLevels.pdl : null;
    const onh = sessionLevels?.onh && sessionLevels.onh > 0 ? sessionLevels.onh : null;
    const onl = sessionLevels?.onl && sessionLevels.onl > 0 ? sessionLevels.onl : null;

    for (let i = lookback; i < candles.length; i++) {
        const c = candles[i];
        const open = Number(c.open);
        const high = Number(c.high);
        const low = Number(c.low);
        const close = Number(c.close);
        const time = Number(c.time);

        let structHigh = -Infinity;
        let structLow = Infinity;
        for (let j = i - lookback; j < i; j++) {
            const h = Number(candles[j].high);
            const l = Number(candles[j].low);
            if (h > structHigh) structHigh = h;
            if (l < structLow) structLow = l;
        }

        const isBearSweep =
            close < open &&
            ((high > structHigh && close < structHigh) ||
                (pdh !== null && high > pdh && close < pdh) ||
                (onh !== null && high > onh && close < onh));

        const isBullSweep =
            close > open &&
            ((low < structLow && close > structLow) ||
                (pdl !== null && low < pdl && close > pdl) ||
                (onl !== null && low < onl && close > onl));

        if (isBearSweep) {
            markers.push({ time, type: 'BEAR_TRAP', label: 'LAF Bear Trap' });
        } else if (isBullSweep) {
            markers.push({ time, type: 'BULL_TRAP', label: 'LBF Bull Trap' });
        }
    }

    return markers.slice(-12);
}

/**
 * Detects historical Larry Williams Oops! Reversal setups on visible OHLCV bars:
 * sweeps below prior bar low (or PDL) with bullish reclaim close above prior low,
 * or sweeps above prior bar high (or PDH) with bearish reclaim close below prior high.
 */
export function computeWilliamsOops(
    candles: ChartCandleLike[],
    sessionLevels?: { pdh?: number | null; pdl?: number | null } | null
): WilliamsOopsMarker[] {
    if (!candles || candles.length < 5) return [];

    const markers: WilliamsOopsMarker[] = [];
    const pdh = sessionLevels?.pdh && sessionLevels.pdh > 0 ? sessionLevels.pdh : null;
    const pdl = sessionLevels?.pdl && sessionLevels.pdl > 0 ? sessionLevels.pdl : null;

    for (let i = 2; i < candles.length; i++) {
        const prev = candles[i - 1];
        const curr = candles[i];
        const open = Number(curr.open);
        const high = Number(curr.high);
        const low = Number(curr.low);
        const close = Number(curr.close);
        const prevHigh = Number(prev.high);
        const prevLow = Number(prev.low);
        const prevRange = Math.max(prevHigh - prevLow, 1e-9);
        const currBody = Math.abs(close - open);

        // Require meaningful reversal impulse (>= 35% of prior bar range) to avoid micro-noise
        if (currBody < prevRange * 0.35) continue;

        const bullOops =
            close > open &&
            ((low < prevLow && close > prevLow && close > Number(prev.close)) ||
                (pdl !== null && low < pdl && close > pdl));

        const bearOops =
            close < open &&
            ((high > prevHigh && close < prevHigh && close < Number(prev.close)) ||
                (pdh !== null && high > pdh && close < pdh));

        if (bullOops) {
            markers.push({ time: Number(curr.time), direction: 'LONG', label: 'Oops! Buy' });
        } else if (bearOops) {
            markers.push({ time: Number(curr.time), direction: 'SHORT', label: 'Oops! Sell' });
        }
    }

    return markers.slice(-10);
}

/**
 * Deterministic Auto-Fibonacci (OTE) fallback for cold timeframes when backend
 * tacticalDecision.fibonacci has not hydrated yet.
 */
export function computeAutoFib(
    candles: ChartCandleLike[],
    lookback: number = 80
): AutoFibResult | null {
    if (!candles || candles.length < 15) return null;
    const slice = candles.slice(-Math.min(lookback, candles.length));

    let swingHigh = -Infinity;
    let swingLow = Infinity;
    let highIdx = 0;
    let lowIdx = 0;

    for (let i = 0; i < slice.length; i++) {
        const h = Number(slice[i].high);
        const l = Number(slice[i].low);
        if (h > swingHigh) {
            swingHigh = h;
            highIdx = i;
        }
        if (l < swingLow) {
            swingLow = l;
            lowIdx = i;
        }
    }

    const range = swingHigh - swingLow;
    if (!Number.isFinite(range) || range <= 0) return null;

    const isUptrend = lowIdx <= highIdx;
    const ratios = ['0.0', '0.236', '0.382', '0.5', '0.618', '0.66', '0.786', '1.0'];
    const levels: Record<string, number> = {};

    for (const r of ratios) {
        const num = Number(r);
        levels[r] = isUptrend ? swingHigh - range * num : swingLow + range * num;
    }

    return { swing_high: swingHigh, swing_low: swingLow, levels };
}
