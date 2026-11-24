import { describe, it, expect, beforeEach } from 'vitest';
import {
    computeEMA,
    computeSessionAVWAP,
    getCandleCountdown,
    buildStructuralFingerprint,
    extractActiveSymbolSetup,
} from '@/shared';
import {
    useIndicatorsStore,
    CHART_PRESETS,
    INDICATOR_DEFAULTS,
} from '../../src/app/store/indicatorsStore';
import { MASTER_WATCHLIST } from '../../src/app/store/telemetry/constants';

describe('SOP-148 Trading Chart Deterministic Math & Store', () => {
    beforeEach(() => {
        useIndicatorsStore.setState({
            indicators: INDICATOR_DEFAULTS.map((d) => ({ ...d })),
            activePreset: 'SSOT_STRATEGY',
            hydrated: true,
        });
    });

    it('computes EMA deterministically and returns empty when insufficient bars', () => {
        expect(computeEMA([], 200)).toEqual([]);

        const flatCandles = Array.from({ length: 30 }, (_, i) => ({
            time: 1700000000 + i * 900,
            open: 100,
            high: 102,
            low: 98,
            close: 100,
            volume: 10,
        }));
        const emaFlat = computeEMA(flatCandles, 10, 10);
        expect(emaFlat.length).toBe(21);
        expect(emaFlat[emaFlat.length - 1].value).toBeCloseTo(100, 6);
    });

    it('computes UTC-anchored Session AVWAP and resets at 00:00 UTC boundary', () => {
        const day1Base = 1700006400; // exact multiple of 86400 (00:00 UTC)
        const candles = [
            // Day 1: typical = 100, vol = 10 -> AVWAP = 100
            { time: day1Base, open: 100, high: 103, low: 97, close: 100, volume: 10 },
            // Day 1: typical = 110, vol = 10 -> AVWAP = 105
            { time: day1Base + 900, open: 110, high: 113, low: 107, close: 110, volume: 10 },
            // Day 2 (00:00 UTC reset): typical = 200, vol = 5 -> AVWAP = 200
            { time: day1Base + 86400, open: 200, high: 203, low: 197, close: 200, volume: 5 },
        ];

        const avwap = computeSessionAVWAP(candles);
        expect(avwap).toHaveLength(3);
        expect(avwap[0].value).toBeCloseTo(100, 6);
        expect(avwap[1].value).toBeCloseTo(105, 6);
        expect(avwap[2].value).toBeCloseTo(200, 6);
    });

    it('calculates exact UTC candle close countdown for intraday and HTF timeframes', () => {
        // 15m = 900s; at 300s elapsed -> 600s remaining = 10:00
        const res15m = getCandleCountdown('15m', 300 * 1000);
        expect(res15m.remainingSeconds).toBe(600);
        expect(res15m.formatted).toBe('10:00');

        // 4h = 14400s; at 3600s elapsed -> 10800s remaining = 03:00:00
        const res4h = getCandleCountdown('4h', 3600 * 1000);
        expect(res4h.remainingSeconds).toBe(10800);
        expect(res4h.formatted).toBe('03:00:00');
    });

    it('produces stable structural fingerprints for identical payloads and distinct ones on mutation', () => {
        const a = buildStructuralFingerprint({ ob: [{ top: 100, bottom: 99 }], show: true });
        const b = buildStructuralFingerprint({ ob: [{ top: 100, bottom: 99 }], show: true });
        const c = buildStructuralFingerprint({ ob: [{ top: 101, bottom: 99 }], show: true });

        expect(a).toBe(b);
        expect(a).not.toBe(c);
    });

    it('extracts active setup levels (Entry, SL, BE, TP1/TP2/TP3) for the active symbol only', () => {
        const setup = extractActiveSymbolSetup(
            'SOLUSDT',
            [
                {
                    asset: 'BTCUSDT',
                    signal_type: 'LONG',
                    price: 90000,
                    stop_loss: 89000,
                    status: 'ACTIVE',
                    timestamp: '2026-11-23T20:00:00Z',
                },
                {
                    asset: 'SOLUSDT',
                    signal_type: 'LONG',
                    price: 200,
                    stop_loss: 190,
                    tp1: 215,
                    tp2: 225,
                    tp3: 240,
                    status: 'ACTIVE',
                    timestamp: '2026-11-23T21:00:00Z',
                },
            ]
        );

        expect(setup).not.toBeNull();
        expect(setup?.symbol).toBe('SOLUSDT');
        expect(setup?.direction).toBe('LONG');
        expect(setup?.entry).toBe(200);
        expect(setup?.stopLoss).toBe(190);
        expect(setup?.bePrice).toBe(210);
        expect(setup?.tp1).toBe(215);
        expect(setup?.tp2).toBe(225);
        expect(setup?.tp3).toBe(240);
    });

    it('applies institutional presets and toggles indicators cleanly in indicatorsStore', () => {
        const store = useIndicatorsStore.getState();

        store.applyPreset('CLEAN');
        const cleanEnabled = useIndicatorsStore
            .getState()
            .indicators.filter((i) => i.enabled)
            .map((i) => i.id);
        expect(cleanEnabled).toEqual(CHART_PRESETS.CLEAN.enabledIds);
        expect(useIndicatorsStore.getState().activePreset).toBe('CLEAN');

        store.applyPreset('SSOT_STRATEGY');
        const ssotEnabled = useIndicatorsStore
            .getState()
            .indicators.filter((i) => i.enabled)
            .map((i) => i.id);
        expect(ssotEnabled).toContain('ema200');
        expect(ssotEnabled).toContain('avwap');
        expect(ssotEnabled).toContain('active_setup');

        store.toggleIndicator('ema200');
        expect(useIndicatorsStore.getState().activePreset).toBe('CUSTOM');
    });

    it('preserves the exact 13-asset Canonical Audited Universe in MASTER_WATCHLIST', () => {
        expect(MASTER_WATCHLIST).toHaveLength(13);
        expect(MASTER_WATCHLIST).not.toContain('AVAXUSDT');
        expect(MASTER_WATCHLIST).not.toContain('RENDERUSDT');
    });
});
