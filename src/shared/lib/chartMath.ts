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

        const entry = Number(sig.price ?? sig.bitunix_order?.price);
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
    const entry = Number(latest.price ?? latest.bitunix_order?.price);
    const stopLoss = Number(latest.stop_loss ?? latest.bitunix_order?.stopLoss);
    const rawType = String(latest.signal_type || latest.type || '').toUpperCase();
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
