'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Clock, HelpCircle, RefreshCw, WifiOff } from 'lucide-react';
import {
    createChart,
    CandlestickSeries,
    HistogramSeries,
    BaselineSeries,
    LineSeries,
    createSeriesMarkers,
    ColorType,
    CrosshairMode,
    LineStyle,
    PriceScaleMode,
} from 'lightweight-charts';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { useTelemetryStore } from '../../store/telemetryStore';
import { useIndicatorsStore } from '../../store/indicatorsStore';
import {
    buildStructuralFingerprint,
    computeAutoFib,
    computeEMA,
    computeMarketTraps,
    computeSessionAVWAP,
    computeVolumeProfile,
    computeWilliamsOops,
    extractActiveSymbolSetup,
    formatPrice,
    getCandleCountdown,
} from '@/shared';

export interface TradingChartProps {
    isLogScale?: boolean;
    isAutoScale?: boolean;
    fitTrigger?: number;
}

interface CrosshairHudData {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    changePct: number;
    ema200?: number | null;
    avwap?: number | null;
    isHovering: boolean;
}

/**
 * SLINGSHOT V14.0 (SOP-148) — lightweight-charts v5.1.0 Institutional Engine
 * - Incremental .update() diffing (preserves user zoom/pan across 1.5s REST polls)
 * - Structural fingerprint memoization for SMC / FVG / Value Area / Sessions
 * - Interactive Crosshair HUD + UTC Candle Countdown
 * - Native SSoT Overlays: EMA 200, Session AVWAP (UTC), Active Setup R:R Grid
 */
export default function TradingChart({
    isLogScale = false,
    isAutoScale = true,
    fitTrigger = 0,
}: TradingChartProps) {
    const [showMobileLegends, setShowMobileLegends] = useState(false);
    const [hudData, setHudData] = useState<CrosshairHudData | null>(null);
    const [countdown, setCountdown] = useState<string>('--:--');
    const [syncTimedOut, setSyncTimedOut] = useState(false);

    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
    const ema200Ref = useRef<ISeriesApi<'Line'> | null>(null);
    const avwapRef = useRef<ISeriesApi<'Line'> | null>(null);
    const williamsRRef = useRef<ISeriesApi<'Line'> | null>(null);

    const sessionSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const killzoneSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const valueAreaSeriesRef = useRef<ISeriesApi<'Baseline'> | null>(null);
    const smcSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const fvgSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);

    const priceLineRef = useRef<any>(null);
    const pocLineRef = useRef<any>(null);
    const vahLineRef = useRef<any>(null);
    const valLineRef = useRef<any>(null);
    const srLinesRef = useRef<{ line: any; series: any }[]>([]);
    const liquidityLinesRef = useRef<any[]>([]);
    const liquidationLinesRef = useRef<any[]>([]);
    const setupLinesRef = useRef<any[]>([]);
    const markersDetachRef = useRef<{ detach: () => void } | null>(null);

    const lastFittedAssetRef = useRef<string>('');
    const datasetMetaRef = useRef<{
        assetKey: string;
        firstTime: number;
        length: number;
        lastTime: number;
    } | null>(null);
    const smcFingerprintRef = useRef<string>('');
    const vaFingerprintRef = useRef<string>('');
    const sessionFingerprintRef = useRef<string>('');

    // Lookup maps for O(1) crosshair HUD queries without re-rendering canvas
    const candleByTimeRef = useRef<Map<number, { open: number; high: number; low: number; close: number; volume: number }>>(new Map());
    const emaByTimeRef = useRef<Map<number, number>>(new Map());
    const avwapByTimeRef = useRef<Map<number, number>>(new Map());
    const latestHudFallbackRef = useRef<CrosshairHudData | null>(null);

    const {
        candles,
        connectionStatus,
        smcData,
        liquidityHeatmap,
        tacticalDecision,
        sessionData,
        liquidations,
        latestPrice,
        activeSymbol,
        activeTimeframe,
        auditedSignals,
        signalHistory,
        connect,
    } = useTelemetryStore();

    const { indicators } = useIndicatorsStore();
    const enabledMap = useMemo(() => {
        const map: Record<string, boolean> = {};
        for (const ind of indicators) map[ind.id] = ind.enabled;
        return map;
    }, [indicators]);

    const isEnabled = (id: string) => Boolean(enabledMap[id]);

    // ── Live UTC Candle Countdown (1s) ──
    useEffect(() => {
        const update = () => {
            setCountdown(getCandleCountdown(activeTimeframe, Date.now()).formatted);
        };
        update();
        const timer = setInterval(update, 1000);
        return () => clearInterval(timer);
    }, [activeTimeframe]);

    // ── Empty/Offline Diagnostic Timeout (6s) ──
    useEffect(() => {
        if (candles.length > 0) {
            setSyncTimedOut(false);
            return;
        }
        const timer = setTimeout(() => setSyncTimedOut(true), 6000);
        return () => clearTimeout(timer);
    }, [candles.length, activeSymbol, activeTimeframe]);

    // ── Chart Init (lightweight-charts v5.1.0) ──
    useEffect(() => {
        if (!chartContainerRef.current) return;
        const chart = createChart(chartContainerRef.current, {
            layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#94a3b8' },
            grid: {
                vertLines: { color: 'rgba(255,255,255,0.035)' },
                horzLines: { color: 'rgba(255,255,255,0.035)' },
            },
            crosshair: {
                mode: CrosshairMode.Magnet,
                vertLine: { color: '#00E5FF', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#0f172a' },
                horzLine: { color: '#00E5FF', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#0f172a' },
            },
            timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: true, secondsVisible: false },
            rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
            autoSize: true,
        } as any);
        chartRef.current = chart;

        candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
            upColor: '#00FF41',
            downColor: '#FF003C',
            borderVisible: false,
            wickUpColor: '#00FF41',
            wickDownColor: '#FF003C',
        });

        volumeRef.current = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });
        chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, borderVisible: false });

        ema200Ref.current = chart.addSeries(LineSeries, {
            color: '#38BDF8',
            lineWidth: 2,
            priceLineVisible: false,
            lastValueVisible: true,
            crosshairMarkerVisible: true,
            title: 'EMA 200',
        });

        avwapRef.current = chart.addSeries(LineSeries, {
            color: '#F59E0B',
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            priceLineVisible: false,
            lastValueVisible: true,
            crosshairMarkerVisible: true,
            title: 'AVWAP',
        });

        williamsRRef.current = chart.addSeries(LineSeries, {
            priceScaleId: 'williams_r',
            color: '#8B5CF6',
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        chart.priceScale('williams_r').applyOptions({
            scaleMargins: { top: 0.82, bottom: 0.08 },
            borderVisible: false,
            visible: false,
        });

        // Crosshair HUD Subscription
        chart.subscribeCrosshairMove((param) => {
            if (!param || !param.time) {
                if (latestHudFallbackRef.current) {
                    setHudData(latestHudFallbackRef.current);
                }
                return;
            }
            const t = Number(param.time);
            const bar = candleByTimeRef.current.get(t);
            if (!bar) return;
            const changePct = bar.open > 0 ? ((bar.close - bar.open) / bar.open) * 100 : 0;
            setHudData({
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close,
                volume: bar.volume,
                changePct,
                ema200: emaByTimeRef.current.get(t) ?? null,
                avwap: avwapByTimeRef.current.get(t) ?? null,
                isHovering: true,
            });
        });

        return () => {
            chart.remove();
            chartRef.current = null;
            datasetMetaRef.current = null;
            smcFingerprintRef.current = '';
            vaFingerprintRef.current = '';
            sessionFingerprintRef.current = '';
        };
    }, []);

    // ── Scale Mode (Logarithmic / Auto-Scale) ──
    useEffect(() => {
        if (!chartRef.current) return;
        try {
            chartRef.current.priceScale('right').applyOptions({
                mode: isLogScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
                autoScale: isAutoScale,
            });
        } catch {
            // Ignore scale apply race
        }
    }, [isLogScale, isAutoScale]);

    // ── Explicit Auto-Fit Trigger from Toolbar ──
    useEffect(() => {
        if (fitTrigger <= 0 || !chartRef.current) return;
        try {
            chartRef.current.timeScale().fitContent();
        } catch {
            // Ignore
        }
    }, [fitTrigger]);

    // ── Incremental Candles, Volume, EMA 200, AVWAP & Williams %R ──
    useEffect(() => {
        if (!candleSeriesRef.current) return;
        if (candles.length === 0) {
            try {
                candleSeriesRef.current.setData([]);
                volumeRef.current?.setData([]);
                ema200Ref.current?.setData([]);
                avwapRef.current?.setData([]);
                williamsRRef.current?.setData([]);
            } catch {}
            datasetMetaRef.current = null;
            candleByTimeRef.current.clear();
            emaByTimeRef.current.clear();
            avwapByTimeRef.current.clear();
            latestHudFallbackRef.current = null;
            setHudData(null);
            return;
        }

        const sorted = [...candles]
            .sort((a, b) => Number(a.time) - Number(b.time))
            .filter((c, i, arr) => i === 0 || Number(c.time) !== Number(arr[i - 1].time));
        if (sorted.length === 0) return;

        // Refresh O(1) lookup map
        const cMap = new Map<number, { open: number; high: number; low: number; close: number; volume: number }>();
        for (const c of sorted) {
            cMap.set(Number(c.time), {
                open: Number(c.open),
                high: Number(c.high),
                low: Number(c.low),
                close: Number(c.close),
                volume: Number(c.volume || 0),
            });
        }
        candleByTimeRef.current = cMap;

        const assetKey = `${activeSymbol}-${activeTimeframe}`;
        const firstTime = Number(sorted[0].time);
        const lastBar = sorted[sorted.length - 1];
        const lastTime = Number(lastBar.time);
        const prevMeta = datasetMetaRef.current;

        const canIncrementalUpdate =
            prevMeta !== null &&
            prevMeta.assetKey === assetKey &&
            prevMeta.firstTime === firstTime &&
            (sorted.length === prevMeta.length || sorted.length === prevMeta.length + 1) &&
            lastTime >= prevMeta.lastTime;

        try {
            if (canIncrementalUpdate) {
                candleSeriesRef.current.update({
                    time: lastTime as any,
                    open: Number(lastBar.open),
                    high: Number(lastBar.high),
                    low: Number(lastBar.low),
                    close: Number(lastBar.close),
                });
            } else {
                candleSeriesRef.current.setData(
                    sorted.map((c) => ({
                        time: Number(c.time) as any,
                        open: Number(c.open),
                        high: Number(c.high),
                        low: Number(c.low),
                        close: Number(c.close),
                    }))
                );
            }
            datasetMetaRef.current = { assetKey, firstTime, length: sorted.length, lastTime };
        } catch (e) {
            console.error('[Chart] candle update error:', e);
        }

        // Auto-Fit only on asset/timeframe switch
        if (lastFittedAssetRef.current !== assetKey) {
            lastFittedAssetRef.current = assetKey;
            setTimeout(() => {
                try {
                    chartRef.current?.timeScale().fitContent();
                } catch {}
            }, 50);
        }

        const showVolume = isEnabled('volume');
        const mainBottom = showVolume ? 0.24 : 0.08;
        chartRef.current?.priceScale('right').applyOptions({ scaleMargins: { top: 0.06, bottom: mainBottom } });

        if (volumeRef.current) {
            volumeRef.current.applyOptions({ visible: showVolume });
            if (showVolume) {
                try {
                    if (canIncrementalUpdate) {
                        volumeRef.current.update({
                            time: lastTime as any,
                            value: Number(lastBar.volume || 0),
                            color: Number(lastBar.close) >= Number(lastBar.open) ? 'rgba(0,255,65,0.4)' : 'rgba(255,0,60,0.4)',
                        });
                    } else {
                        volumeRef.current.setData(
                            sorted.map((c) => ({
                                time: Number(c.time) as any,
                                value: Number(c.volume || 0),
                                color: Number(c.close) >= Number(c.open) ? 'rgba(0,255,65,0.4)' : 'rgba(255,0,60,0.4)',
                            }))
                        );
                    }
                    chartRef.current?.priceScale('volume').applyOptions({ scaleMargins: { top: 0.84, bottom: 0 }, visible: true });
                } catch {}
            }
        }

        // EMA 200 (SSoT)
        const emaPoints = computeEMA(sorted, 200);
        const emaMap = new Map<number, number>();
        for (const p of emaPoints) emaMap.set(p.time, p.value);
        emaByTimeRef.current = emaMap;

        if (ema200Ref.current) {
            const showEma = isEnabled('ema200');
            ema200Ref.current.applyOptions({ visible: showEma });
            if (showEma && emaPoints.length > 0) {
                try {
                    ema200Ref.current.setData(emaPoints as any);
                } catch {}
            }
        }

        // Session AVWAP UTC (SSoT SOP-114)
        const avwapPoints = computeSessionAVWAP(sorted);
        const avwapMap = new Map<number, number>();
        for (const p of avwapPoints) avwapMap.set(p.time, p.value);
        avwapByTimeRef.current = avwapMap;

        if (avwapRef.current) {
            const showAvwap = isEnabled('avwap');
            avwapRef.current.applyOptions({ visible: showAvwap });
            if (showAvwap && avwapPoints.length > 0) {
                try {
                    avwapRef.current.setData(avwapPoints as any);
                } catch {}
            }
        }

        // Williams %R
        if (williamsRRef.current) {
            const isR = isEnabled('williams_r');
            williamsRRef.current.applyOptions({ visible: isR });
            if (isR) {
                try {
                    const rData = sorted.map((c, idx) => {
                        const start = Math.max(0, idx - 13);
                        const slice = sorted.slice(start, idx + 1);
                        const hh = Math.max(...slice.map((x) => Number(x.high)));
                        const ll = Math.min(...slice.map((x) => Number(x.low)));
                        const val = hh === ll ? -50 : ((hh - Number(c.close)) / (hh - ll + 1e-9)) * -100;
                        return { time: Number(c.time), value: val };
                    });
                    williamsRRef.current.setData(rData as any);
                    chartRef.current?.priceScale('williams_r').applyOptions({ visible: true });
                } catch {}
            } else {
                chartRef.current?.priceScale('williams_r').applyOptions({ visible: false });
            }
        }

        // Default HUD snapshot to latest candle
        const latestChangePct =
            Number(lastBar.open) > 0 ? ((Number(lastBar.close) - Number(lastBar.open)) / Number(lastBar.open)) * 100 : 0;
        const snapshot: CrosshairHudData = {
            open: Number(lastBar.open),
            high: Number(lastBar.high),
            low: Number(lastBar.low),
            close: Number(lastBar.close),
            volume: Number(lastBar.volume || 0),
            changePct: latestChangePct,
            ema200: emaMap.get(lastTime) ?? null,
            avwap: avwapMap.get(lastTime) ?? null,
            isHovering: false,
        };
        latestHudFallbackRef.current = snapshot;
        setHudData((prev) => (prev?.isHovering ? prev : snapshot));
    }, [candles, enabledMap, activeSymbol, activeTimeframe]);

    // ── Precision & Live Tick Price Line ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s || !latestPrice || latestPrice <= 0 || candles.length === 0) return;

        let precision = 2;
        let minMove = 0.01;
        if (latestPrice < 0.001) {
            precision = 8;
            minMove = 0.00000001;
        } else if (latestPrice < 0.1) {
            precision = 6;
            minMove = 0.000001;
        } else if (latestPrice < 10) {
            precision = 4;
            minMove = 0.0001;
        } else if (latestPrice < 100) {
            precision = 3;
            minMove = 0.001;
        }
        try {
            s.applyOptions({ priceFormat: { type: 'price', precision, minMove } });
        } catch {}

        const last = candles[candles.length - 1];
        if (last && last.time) {
            const t = Math.floor(Number(last.time));
            try {
                s.update({
                    time: t as any,
                    open: Number(last.open),
                    close: latestPrice,
                    high: Math.max(Number(last.high), latestPrice),
                    low: Math.min(Number(last.low), latestPrice),
                });
            } catch {}

            if (volumeRef.current && isEnabled('volume')) {
                try {
                    volumeRef.current.update({
                        time: t as any,
                        value: Number(last.volume || 0),
                        color: latestPrice >= Number(last.open) ? 'rgba(0,255,65,0.4)' : 'rgba(255,0,60,0.4)',
                    });
                } catch {}
            }
        }

        const isUp = last ? latestPrice >= Number(last.open) : true;
        const priceColor = isUp ? 'rgba(0,255,65,0.9)' : 'rgba(255,0,60,0.9)';
        if (priceLineRef.current) {
            try {
                priceLineRef.current.applyOptions({ price: latestPrice, color: priceColor });
            } catch {
                try {
                    s.removePriceLine(priceLineRef.current);
                } catch {}
                priceLineRef.current = s.createPriceLine({
                    price: latestPrice,
                    color: priceColor,
                    lineWidth: 1,
                    lineStyle: LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: '',
                });
            }
        } else {
            try {
                priceLineRef.current = s.createPriceLine({
                    price: latestPrice,
                    color: priceColor,
                    lineWidth: 1,
                    lineStyle: LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: '',
                });
            } catch {}
        }
    }, [latestPrice, candles, enabledMap]);

    // ── Active Setup R:R Projection (Entry / SL / BE / TP1 / TP2 / TP3) ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s) return;

        setupLinesRef.current.forEach((l) => {
            try {
                s.removePriceLine(l);
            } catch {}
        });
        setupLinesRef.current = [];

        if (!isEnabled('active_setup')) return;

        const setup = extractActiveSymbolSetup(
            activeSymbol,
            tacticalDecision?.signals as any,
            auditedSignals as any,
            signalHistory as any
        );
        if (!setup) return;

        const addSetupLine = (price: number | undefined, color: string, title: string, style: number, width: number = 2) => {
            if (!price || !Number.isFinite(price)) return;
            try {
                const line = s.createPriceLine({
                    price,
                    color,
                    lineWidth: width as any,
                    lineStyle: style,
                    axisLabelVisible: true,
                    title,
                });
                if (line) setupLinesRef.current.push(line);
            } catch {}
        };

        const dirTag = setup.direction === 'LONG' ? 'LONG' : 'SHORT';
        addSetupLine(setup.entry, '#38BDF8', `ENTRY ${dirTag}`, LineStyle.Solid, 2);
        addSetupLine(setup.stopLoss, '#FF003C', 'SL (-1.0R)', LineStyle.Solid, 2);
        addSetupLine(setup.bePrice, '#94A3B8', 'FAST BE (+1.0R)', LineStyle.Dotted, 1);
        addSetupLine(setup.tp1, '#10B981', 'TP1 (50%)', LineStyle.Dashed, 2);
        addSetupLine(setup.tp2, '#00FF41', 'TP2 (30%)', LineStyle.Dashed, 2);
        addSetupLine(setup.tp3, '#FACC15', 'TP3 (20% RUNNER)', LineStyle.Solid, 2);
    }, [activeSymbol, tacticalDecision, auditedSignals, signalHistory, enabledMap]);

    // ── SMC & FVG (Fingerprint-Memoized with tacticalDecision.smc fallback) ──
    useEffect(() => {
        const chart = chartRef.current;
        if (!chart || candles.length === 0) return;

        const effectiveSmc = smcData ?? tacticalDecision?.smc ?? null;
        const showSmc = isEnabled('smc');
        const showFvg = isEnabled('fvg');
        const fp = buildStructuralFingerprint({
            showSmc,
            showFvg,
            ob: effectiveSmc?.order_blocks || null,
            fvg: effectiveSmc?.fvgs || null,
            lastTime: candles[candles.length - 1]?.time,
        });
        if (fp === smcFingerprintRef.current) return;
        smcFingerprintRef.current = fp;

        smcSeriesRef.current.forEach((s) => {
            try {
                chart.removeSeries(s);
            } catch {}
        });
        smcSeriesRef.current = [];
        fvgSeriesRef.current.forEach((s) => {
            try {
                chart.removeSeries(s);
            } catch {}
        });
        fvgSeriesRef.current = [];

        if (!effectiveSmc || (!showSmc && !showFvg)) return;

        const times = candles.map((c) => Number(c.time)).sort((a, b) => a - b);
        const addBaseline = (opts: any, data: any[]) => {
            if (data.length === 0) return null;
            try {
                const s = chart.addSeries(BaselineSeries, opts);
                s.setData(data as any);
                return s;
            } catch {
                return null;
            }
        };

        const bullishOBs = effectiveSmc?.order_blocks?.bullish || [];
        const bearishOBs = effectiveSmc?.order_blocks?.bearish || [];
        const bullishFVGs = effectiveSmc?.fvgs?.bullish || [];
        const bearishFVGs = effectiveSmc?.fvgs?.bearish || [];

        if (showSmc) {
            bullishOBs.forEach((ob) => {
                const s = addBaseline(
                    {
                        baseValue: { type: 'price', price: ob.bottom },
                        topFillColor1: 'rgba(0,255,136,0.32)',
                        topFillColor2: 'rgba(0,255,136,0.08)',
                        topLineColor: 'rgba(0,255,136,0.75)',
                        bottomFillColor1: 'transparent',
                        bottomFillColor2: 'transparent',
                        bottomLineColor: 'transparent',
                        lineWidth: 1,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    },
                    times.filter((t) => t >= ob.time).map((time) => ({ time, value: ob.top }))
                );
                if (s) smcSeriesRef.current.push(s);
            });
            bearishOBs.forEach((ob) => {
                const s = addBaseline(
                    {
                        baseValue: { type: 'price', price: ob.top },
                        bottomFillColor1: 'rgba(255,0,60,0.32)',
                        bottomFillColor2: 'rgba(255,0,60,0.08)',
                        bottomLineColor: 'rgba(255,0,60,0.75)',
                        topFillColor1: 'transparent',
                        topFillColor2: 'transparent',
                        topLineColor: 'transparent',
                        lineWidth: 1,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    },
                    times.filter((t) => t >= ob.time).map((time) => ({ time, value: ob.bottom }))
                );
                if (s) smcSeriesRef.current.push(s);
            });
        }
        if (showFvg) {
            bullishFVGs.forEach((fvg) => {
                const s = addBaseline(
                    {
                        baseValue: { type: 'price', price: fvg.bottom },
                        topFillColor1: 'rgba(255,204,0,0.18)',
                        topFillColor2: 'rgba(255,204,0,0.04)',
                        topLineColor: 'rgba(255,204,0,0.55)',
                        bottomFillColor1: 'transparent',
                        bottomFillColor2: 'transparent',
                        bottomLineColor: 'transparent',
                        lineWidth: 1,
                        lineStyle: LineStyle.Dashed,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    },
                    times.filter((t) => t >= fvg.time).map((time) => ({ time, value: fvg.top }))
                );
                if (s) fvgSeriesRef.current.push(s);
            });
            bearishFVGs.forEach((fvg) => {
                const s = addBaseline(
                    {
                        baseValue: { type: 'price', price: fvg.top },
                        bottomFillColor1: 'rgba(255,204,0,0.18)',
                        bottomFillColor2: 'rgba(255,204,0,0.04)',
                        bottomLineColor: 'rgba(255,204,0,0.55)',
                        topFillColor1: 'transparent',
                        topFillColor2: 'transparent',
                        topLineColor: 'transparent',
                        lineWidth: 1,
                        lineStyle: LineStyle.Dashed,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false,
                    },
                    times.filter((t) => t >= fvg.time).map((time) => ({ time, value: fvg.bottom }))
                );
                if (s) fvgSeriesRef.current.push(s);
            });
        }
    }, [smcData, enabledMap, candles.length]);

    // ── Liquidity Heatmap ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s || !liquidityHeatmap || !isEnabled('heatmap')) {
            liquidityLinesRef.current.forEach((l) => {
                try {
                    s?.removePriceLine(l);
                } catch {}
            });
            liquidityLinesRef.current = [];
            return;
        }
        liquidityLinesRef.current.forEach((l) => {
            try {
                s.removePriceLine(l);
            } catch {}
        });
        liquidityLinesRef.current = [];
        const bids = liquidityHeatmap.bids || (liquidityHeatmap as any).hot_bids || [];
        const asks = liquidityHeatmap.asks || (liquidityHeatmap as any).hot_asks || [];
        if (bids.length === 0 && asks.length === 0) return;
        const maxVol = Math.max(...bids.concat(asks).map((x: any) => x.volume), 1);
        const add = (lvl: any, base: string) => {
            try {
                const intensity = 0.15 + 0.55 * (lvl.volume / maxVol);
                const line = s.createPriceLine({
                    price: lvl.price,
                    color: `${base}${intensity})`,
                    lineWidth: 1,
                    lineStyle: LineStyle.Solid,
                    axisLabelVisible: false,
                    title: `WALL: ${lvl.volume?.toFixed(0)}V`,
                });
                if (line) liquidityLinesRef.current.push(line);
            } catch {}
        };
        bids.forEach((b: any) => add(b, 'rgba(0,255,65,'));
        asks.forEach((a: any) => add(a, 'rgba(255,0,60,'));
    }, [liquidityHeatmap, enabledMap]);

    // ── Liquidations ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s || !liquidations) return;
        liquidationLinesRef.current.forEach((l) => {
            try {
                s.removePriceLine(l);
            } catch {}
        });
        liquidationLinesRef.current = [];
        if (isEnabled('liquidations')) {
            liquidations.forEach((liq) => {
                try {
                    const isShort = liq.type === 'SHORT_LIQ';
                    const opacity = 0.1 + (liq.strength / 100) * 0.4;
                    const color = isShort ? `rgba(0,229,255,${opacity})` : `rgba(192,132,252,${opacity})`;
                    const line = s.createPriceLine({
                        price: liq.price,
                        color,
                        lineWidth: Math.max(1, Math.floor(liq.strength / 20)) as any,
                        lineStyle: LineStyle.Dashed,
                        axisLabelVisible: true,
                        title: `REKT: ${liq.strength}%`,
                    });
                    if (line) liquidationLinesRef.current.push(line);
                } catch {}
            });
        }
    }, [liquidations, enabledMap]);

    // ── YOSH Value Area (Fingerprint-Memoized with deterministic 0ms fallback) ──
    useEffect(() => {
        const chart = chartRef.current;
        const s = candleSeriesRef.current;
        if (!chart || !s || candles.length === 0) return;

        const showVa = isEnabled('value_area');
        const backendVp = smcData?.volume_profile;
        const hasBackendVp = Boolean(backendVp?.vah && backendVp?.val && backendVp?.poc);
        const vp = showVa ? (hasBackendVp ? backendVp : computeVolumeProfile(candles, 50)) : null;

        const fp = buildStructuralFingerprint({
            showVa,
            vah: vp?.vah,
            val: vp?.val,
            poc: vp?.poc,
            lastTime: candles[candles.length - 1]?.time,
        });
        if (fp === vaFingerprintRef.current) return;
        vaFingerprintRef.current = fp;

        if (valueAreaSeriesRef.current) {
            try {
                chart.removeSeries(valueAreaSeriesRef.current);
            } catch {}
        }
        if (pocLineRef.current) {
            try {
                s.removePriceLine(pocLineRef.current);
            } catch {}
        }
        if (vahLineRef.current) {
            try {
                s.removePriceLine(vahLineRef.current);
            } catch {}
        }
        if (valLineRef.current) {
            try {
                s.removePriceLine(valLineRef.current);
            } catch {}
        }
        valueAreaSeriesRef.current = null;
        pocLineRef.current = null;
        vahLineRef.current = null;
        valLineRef.current = null;

        if (showVa && vp?.vah && vp?.val && vp?.poc) {
            const times = candles.map((c) => Number(c.time)).sort((a, b) => a - b);
            try {
                const va = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: vp.val },
                    topFillColor1: 'rgba(255, 215, 0, 0.20)',
                    topFillColor2: 'rgba(255, 215, 0, 0.05)',
                    topLineColor: 'rgba(255, 215, 0, 0.90)',
                    bottomFillColor1: 'transparent',
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                const recentTimes = times.slice(-Math.min(times.length, 60));
                va.setData(recentTimes.map((time) => ({ time, value: vp.vah })) as any);
                valueAreaSeriesRef.current = va;
            } catch {}

            try {
                vahLineRef.current = s.createPriceLine({
                    price: vp.vah,
                    color: '#FFD700',
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'YOSH VAH (70%)',
                });
            } catch {}
            try {
                pocLineRef.current = s.createPriceLine({
                    price: vp.poc,
                    color: '#FFCC00',
                    lineWidth: 3,
                    lineStyle: LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'YOSH POC',
                });
            } catch {}
            try {
                valLineRef.current = s.createPriceLine({
                    price: vp.val,
                    color: '#EAB308',
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'YOSH VAL (70%)',
                });
            } catch {}
        }
    }, [smcData, enabledMap, candles.length]);

    // ── Markers (Traps & Larry Williams Oops) ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s) return;

        if (markersDetachRef.current) {
            try {
                markersDetachRef.current.detach();
            } catch {}
            markersDetachRef.current = null;
        }

        const markers: any[] = [];

        if (isEnabled('traps')) {
            const last = candles[candles.length - 1];
            if (last && smcData?.traps) {
                if (smcData.traps.laf_bull) {
                    markers.push({
                        time: Number(last.time),
                        position: 'belowBar',
                        color: '#00E5FF',
                        shape: 'arrowUp',
                        text: 'LBF Bull Trap',
                    });
                }
                if (smcData.traps.laf_bear) {
                    markers.push({
                        time: Number(last.time),
                        position: 'aboveBar',
                        color: '#FF007A',
                        shape: 'arrowDown',
                        text: 'LAF Bear Trap',
                    });
                }
            }

            const sweeps = (smcData as any)?.liquidity_sweeps;
            if (candles.length >= 5 && Array.isArray(sweeps)) {
                sweeps.forEach((sw: any) => {
                    const swTime = Number(sw.timestamp || sw.time);
                    if (swTime) {
                        markers.push({
                            time: swTime,
                            position: sw.type === 'BULLISH_SWEEP' ? 'belowBar' : 'aboveBar',
                            color: '#FF00FF',
                            shape: sw.type === 'BULLISH_SWEEP' ? 'arrowUp' : 'arrowDown',
                            text: sw.type === 'BULLISH_SWEEP' ? 'Sweep Low' : 'Sweep High',
                        });
                    }
                });
            }

            // Historical deterministic LAF/LBF traps across visible candles
            const histTraps = computeMarketTraps(candles, sessionData);
            histTraps.forEach((tr) => {
                markers.push({
                    time: tr.time,
                    position: tr.type === 'BULL_TRAP' ? 'belowBar' : 'aboveBar',
                    color: tr.type === 'BULL_TRAP' ? '#00E5FF' : '#FF007A',
                    shape: tr.type === 'BULL_TRAP' ? 'arrowUp' : 'arrowDown',
                    text: tr.label,
                });
            });
        }

        if (isEnabled('williams_oops')) {
            const allSignals = [...Object.values(auditedSignals || {}), ...Object.values(signalHistory || {})];
            allSignals.forEach((sig: any) => {
                if (sig.asset?.toUpperCase() !== activeSymbol?.toUpperCase()) return;
                const rawTs = Number(sig.timestamp || sig.time);
                if (isNaN(rawTs) || rawTs <= 0) return;
                const ts = rawTs > 10000000000 ? Math.floor(rawTs / 1000) : Math.floor(rawTs);
                const isLong =
                    sig.signal_type?.toUpperCase().includes('LONG') || sig.type?.toUpperCase().includes('LONG');

                if (sig.type?.includes('Oops') || sig.strategy?.includes('Oops') || sig.type === 'Oops! Reversal') {
                    markers.push({
                        time: ts,
                        position: isLong ? 'belowBar' : 'aboveBar',
                        color: '#E11D48',
                        shape: isLong ? 'arrowUp' : 'arrowDown',
                        text: `Oops! ${isLong ? 'Buy' : 'Sell'}`,
                    });
                }
            });

            // Historical deterministic Larry Williams Oops! reversals across visible candles
            const histOops = computeWilliamsOops(candles, sessionData);
            histOops.forEach((op) => {
                markers.push({
                    time: op.time,
                    position: op.direction === 'LONG' ? 'belowBar' : 'aboveBar',
                    color: op.direction === 'LONG' ? '#10B981' : '#E11D48',
                    shape: op.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
                    text: op.label,
                });
            });
        }

        const unique = markers
            .filter((v, i, a) => a.findIndex((t) => t.time === v.time && t.text === v.text) === i)
            .sort((a, b) => Number(a.time) - Number(b.time));

        if (unique.length > 0) {
            try {
                markersDetachRef.current = createSeriesMarkers(s, unique);
            } catch (e) {
                console.warn('[Chart] createSeriesMarkers failed:', e);
            }
        }
    }, [smcData, enabledMap, candles.length, auditedSignals, signalHistory, activeSymbol]);

    // ── Key Levels, Sessions & Fibonacci (Fingerprint-Memoized) ──
    useEffect(() => {
        const chart = chartRef.current;
        const s = candleSeriesRef.current;
        if (!chart || !s) return;

        const showSr = isEnabled('sr');
        const showFib = isEnabled('fibonacci');
        const showSession = isEnabled('session');
        const showOops = isEnabled('williams_oops');

        const fp = buildStructuralFingerprint({
            showSr,
            showFib,
            showSession,
            showOops,
            keyLevels: showSr ? tacticalDecision?.key_levels : null,
            fib: showFib ? tacticalDecision?.fibonacci : null,
            session: showSession || showOops ? sessionData : null,
            len: candles.length,
        });
        if (fp === sessionFingerprintRef.current) return;
        sessionFingerprintRef.current = fp;

        srLinesRef.current.forEach(({ line, series: sr }) => {
            try {
                sr.removePriceLine(line);
            } catch {}
        });
        srLinesRef.current = [];

        const addLine = (
            price: number | null | undefined,
            color: string,
            title: string,
            style: number,
            width: number = 1
        ) => {
            if (!price || !s) return;
            try {
                const line = s.createPriceLine({
                    price,
                    color,
                    lineWidth: width as any,
                    lineStyle: style,
                    axisLabelVisible: true,
                    title,
                });
                if (line) srLinesRef.current.push({ line, series: s });
            } catch {}
        };

        if (showSr) {
            const { resistances = [], supports = [] } = tacticalDecision?.key_levels || {};
            const touchesToWidth = (lvl: any): number =>
                lvl.mtf_confluence ? 4 : lvl.ob_confluence ? 3 : lvl.touches >= 4 ? 3 : lvl.touches >= 2 ? 2 : 1;
            const touchesToAlpha = (t: number, mtf: boolean): string =>
                mtf ? '1.0' : t >= 4 ? '0.9' : t >= 2 ? '0.7' : '0.4';
            const getLevelColor = (lvl: any, alpha: string): string => {
                if (lvl.type === 'RESISTANCE' || lvl.origin === 'RESISTANCE') {
                    return lvl.origin === 'ROLE_REVERSAL'
                        ? `rgba(251,146,60,${alpha})`
                        : `rgba(255,0,60,${alpha})`;
                }
                return lvl.origin === 'ROLE_REVERSAL'
                    ? `rgba(250,204,21,${alpha})`
                    : `rgba(0,255,65,${alpha})`;
            };

            resistances.forEach((r: any, i: number) => {
                const rank = i + 1;
                const alpha = touchesToAlpha(r.touches, r.mtf_confluence ?? false);
                const w = touchesToWidth(r);
                const color = getLevelColor({ ...r, type: 'RESISTANCE' }, alpha);
                const label = `R${rank}${r.mtf_confluence ? '◈' : ''}${r.ob_confluence ? '★' : ''}(${r.touches}t)`;
                const style = r.mtf_confluence ? LineStyle.Solid : rank === 1 ? LineStyle.Dashed : LineStyle.Dotted;
                addLine(r.price, color, label, style, w);
            });

            supports.forEach((sup: any, i: number) => {
                const rank = i + 1;
                const alpha = touchesToAlpha(sup.touches, sup.mtf_confluence ?? false);
                const w = touchesToWidth(sup);
                const color = getLevelColor({ ...sup, type: 'SUPPORT' }, alpha);
                const label = `S${rank}${sup.mtf_confluence ? '◈' : ''}${sup.ob_confluence ? '★' : ''}(${sup.touches}t)`;
                const style = sup.mtf_confluence ? LineStyle.Solid : rank === 1 ? LineStyle.Dashed : LineStyle.Dotted;
                addLine(sup.price, color, label, style, w);
            });
        }

        const effectiveFib = showFib ? (tacticalDecision?.fibonacci?.levels ? tacticalDecision.fibonacci : computeAutoFib(candles)) : null;
        if (showFib && effectiveFib?.levels) {
            const { levels, swing_high, swing_low } = effectiveFib;
            const isUptrend = (swing_low ?? 0) < (swing_high ?? 0);
            Object.entries(levels).forEach(([label, price]) => {
                const p = price as number;
                if (label === '0.618') addLine(p, 'rgba(0,229,255,1.0)', '0.618 GP', LineStyle.Solid, 2);
                else if (label === '0.66') addLine(p, 'rgba(0,229,255,0.7)', '0.66 GP', LineStyle.Dashed, 2);
                else if (label === '0.0')
                    addLine(p, 'rgba(255,255,255,0.8)', isUptrend ? 'Swing High' : 'Swing Low', LineStyle.Solid, 2);
                else if (label === '1.0')
                    addLine(p, 'rgba(255,255,255,0.8)', isUptrend ? 'Swing Low' : 'Swing High', LineStyle.Solid, 2);
                else if (label === '0.786') addLine(p, 'rgba(255,80,80,0.6)', 'Fib 0.786', LineStyle.Dotted, 1);
                else addLine(p, 'rgba(255,255,255,0.4)', `Fib ${label}`, LineStyle.Dashed, 1);
            });
        }

        sessionSeriesRef.current.forEach((sr) => {
            try {
                chart.removeSeries(sr);
            } catch {}
        });
        sessionSeriesRef.current = [];
        killzoneSeriesRef.current.forEach((sr) => {
            try {
                chart.removeSeries(sr);
            } catch {}
        });
        killzoneSeriesRef.current = [];

        if (sessionData && (showSession || showOops)) {
            const { pdh, pdl, onh, onl } = sessionData;
            if (pdh)
                addLine(
                    pdh,
                    showOops ? '#E11D48' : '#FF9F00',
                    showOops ? 'PDH (LARRY WILLIAMS)' : 'PDH',
                    LineStyle.Solid,
                    2
                );
            if (pdl)
                addLine(
                    pdl,
                    showOops ? '#10B981' : '#00FF00',
                    showOops ? 'PDL (LARRY WILLIAMS)' : 'PDL',
                    LineStyle.Solid,
                    2
                );

            if (showSession && sessionData.sessions && typeof sessionData.sessions === 'object') {
                const { sessions } = sessionData;
                const sessionColors: Record<string, { color: string; bg: string; kz: string }> = {
                    asia: { color: 'rgba(251,146,60,0.75)', bg: 'rgba(251,146,60,0.16)', kz: 'rgba(251,146,60,0.28)' },
                    london: { color: 'rgba(96,165,250,0.75)', bg: 'rgba(96,165,250,0.16)', kz: 'rgba(96,165,250,0.28)' },
                    ny: { color: 'rgba(192,132,252,0.75)', bg: 'rgba(192,132,252,0.16)', kz: 'rgba(192,132,252,0.28)' },
                };

                const sorted = [...candles]
                    .sort((a, b) => Number(a.time) - Number(b.time))
                    .filter((c, i, arr) => i === 0 || c.time !== arr[i - 1].time);

                if (onh) addLine(onh, '#FF00FF', 'ONH', LineStyle.Dashed, 1);
                if (onl) addLine(onl, '#FF00FF', 'ONL', LineStyle.Dashed, 1);

                const lvns =
                    sessionData?.volume_profile?.lvns && sessionData.volume_profile.lvns.length > 0
                        ? sessionData.volume_profile.lvns
                        : (computeVolumeProfile(sorted, 50)?.lvns || []);
                lvns.forEach((lvn: number, i: number) => {
                    addLine(lvn, 'rgba(200,200,200,0.45)', `LVN ${i + 1}`, LineStyle.Dotted, 1);
                });

                const isIntradayTf = !['1d', '1w', '1M'].includes(activeTimeframe);
                if (sorted.length > 0 && isIntradayTf) {
                    Object.entries(sessions).forEach(([id, info]: [string, any]) => {
                        if (info.start_utc == null || info.end_utc == null || !sessionColors[id]) return;

                        let currentBlock: any[] = [];
                        const blocks: any[][] = [];
                        for (let i = 0; i < sorted.length; i++) {
                            const c = sorted[i];
                            const h = new Date(Number(c.time) * 1000).getUTCHours();
                            const inside =
                                info.start_utc < info.end_utc
                                    ? h >= info.start_utc && h < info.end_utc
                                    : h >= info.start_utc || h < info.end_utc;
                            if (inside) currentBlock.push(c);
                            else if (currentBlock.length > 0) {
                                blocks.push(currentBlock);
                                currentBlock = [];
                            }
                        }
                        if (currentBlock.length > 0) blocks.push(currentBlock);

                        blocks.forEach((blockCandles) => {
                            if (blockCandles.length < 2) return;
                            const blockHigh = Math.max(...blockCandles.map((c) => Number(c.high)));
                            const blockLow = Math.min(...blockCandles.map((c) => Number(c.low)));

                            try {
                                const bracket = chart.addSeries(BaselineSeries, {
                                    baseValue: { type: 'price', price: blockLow },
                                    topFillColor1: sessionColors[id].bg,
                                    topFillColor2: 'transparent',
                                    topLineColor: sessionColors[id].color,
                                    lineWidth: 1,
                                    bottomFillColor1: 'transparent',
                                    bottomFillColor2: 'transparent',
                                    bottomLineColor: 'transparent',
                                    priceLineVisible: false,
                                    lastValueVisible: false,
                                    crosshairMarkerVisible: false,
                                });
                                bracket.setData(blockCandles.map((c) => ({ time: Number(c.time), value: blockHigh })) as any);
                                sessionSeriesRef.current.push(bracket);
                            } catch {}

                            const kzHours = id === 'asia' ? 4 : 3;
                            const kzStart = info.start_utc;
                            const kzEnd = (info.start_utc + kzHours) % 24;
                            const kzCandles = blockCandles.filter((c) => {
                                const hh = new Date(Number(c.time) * 1000).getUTCHours();
                                return kzStart < kzEnd ? hh >= kzStart && hh < kzEnd : hh >= kzStart || hh < kzEnd;
                            });
                            if (kzCandles.length > 0) {
                                try {
                                    const kzGlow = chart.addSeries(BaselineSeries, {
                                        baseValue: { type: 'price', price: blockLow },
                                        topFillColor1: sessionColors[id].kz,
                                        topFillColor2: sessionColors[id].kz,
                                        topLineColor: 'transparent',
                                        lineWidth: 1,
                                        priceLineVisible: false,
                                        lastValueVisible: false,
                                        crosshairMarkerVisible: false,
                                    });
                                    kzGlow.setData(kzCandles.map((c) => ({ time: Number(c.time), value: blockHigh })) as any);
                                    killzoneSeriesRef.current.push(kzGlow);
                                } catch {}
                            }
                        });
                    });
                }
            }
        }
    }, [tacticalDecision, sessionData, enabledMap, candles.length, activeTimeframe]);

    const isUpBar = hudData ? hudData.close >= hudData.open : true;

    return (
        <div className="w-full h-full relative" ref={chartContainerRef}>
            {/* TradingView-Grade Interactive Crosshair HUD (Top-Left) */}
            {hudData && (
                <div className="absolute top-2 left-2 md:top-4 md:left-4 z-20 pointer-events-none flex flex-col gap-1 max-w-[calc(100%-64px)]">
                    <div className="inline-flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5 rounded-lg bg-[#050B14]/85 backdrop-blur-md border border-white/10 shadow-xl font-mono text-[11px]">
                        <span className="font-bold text-white">{activeSymbol}</span>
                        <span className="text-slate-400">
                            O <span className="text-slate-100">{formatPrice(hudData.open)}</span>
                        </span>
                        <span className="text-slate-400">
                            H <span className="text-slate-100">{formatPrice(hudData.high)}</span>
                        </span>
                        <span className="text-slate-400">
                            L <span className="text-slate-100">{formatPrice(hudData.low)}</span>
                        </span>
                        <span className="text-slate-400">
                            C{' '}
                            <span className={isUpBar ? 'text-neon-green font-bold' : 'text-neon-red font-bold'}>
                                {formatPrice(hudData.close)}
                            </span>
                        </span>
                        <span className={isUpBar ? 'text-neon-green font-bold' : 'text-neon-red font-bold'}>
                            {hudData.changePct >= 0 ? '+' : ''}
                            {hudData.changePct.toFixed(2)}%
                        </span>
                        <span className="hidden sm:inline text-slate-400">
                            Vol <span className="text-slate-200">{hudData.volume.toLocaleString('en-US', { maximumFractionDigits: 1 })}</span>
                        </span>
                        <span className="inline-flex items-center gap-1 text-neon-cyan font-bold pl-1 border-l border-white/15">
                            <Clock size={11} />
                            <span>{countdown}</span>
                        </span>
                    </div>

                    {/* Active Indicator Values Strip */}
                    {(isEnabled('ema200') || isEnabled('avwap')) && (
                        <div className="inline-flex flex-wrap items-center gap-3 px-3 py-1 rounded-md bg-[#050B14]/75 backdrop-blur-sm border border-white/10 font-mono text-[10px] w-fit">
                            {isEnabled('ema200') && (
                                <span className="text-sky-400 font-semibold">
                                    EMA 200:{' '}
                                    <span className="text-slate-100">
                                        {hudData.ema200 != null ? formatPrice(hudData.ema200) : '—'}
                                    </span>
                                </span>
                            )}
                            {isEnabled('avwap') && (
                                <span className="text-amber-400 font-semibold">
                                    AVWAP:{' '}
                                    <span className="text-slate-100">
                                        {hudData.avwap != null ? formatPrice(hudData.avwap) : '—'}
                                    </span>
                                </span>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Empty / Offline Diagnostic Overlay */}
            {candles.length === 0 && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/65 backdrop-blur-sm p-4 text-center">
                    {syncTimedOut || connectionStatus === 'DISCONNECTED' ? (
                        <div className="flex flex-col items-center gap-3 max-w-sm bg-[#06101A]/95 border border-white/15 rounded-xl p-6 shadow-2xl">
                            <WifiOff size={28} className="text-amber-400" />
                            <p className="text-sm font-bold text-white">Sin velas sincronizadas ({activeSymbol})</p>
                            <p className="text-xs text-slate-300">
                                Estado de telemetría: <span className="font-mono text-amber-300">{connectionStatus}</span>. Verifica la conexión con el motor o reintenta la sincronización.
                            </p>
                            <button
                                type="button"
                                onClick={() => {
                                    setSyncTimedOut(false);
                                    connect(activeSymbol || 'BTCUSDT', activeTimeframe);
                                }}
                                className="min-h-[44px] px-4 rounded-lg bg-neon-cyan/20 hover:bg-neon-cyan/30 border border-neon-cyan/50 text-neon-cyan text-xs font-bold flex items-center gap-2 transition-all cursor-pointer"
                            >
                                <RefreshCw size={14} />
                                <span>Reintentar Sincronización</span>
                            </button>
                        </div>
                    ) : (
                        <>
                            <div className="w-12 h-12 border-2 border-t-neon-cyan border-r-neon-cyan/50 border-b-transparent border-l-transparent rounded-full animate-spin" />
                            <p className="text-neon-cyan text-xs tracking-[0.2em] mt-4 font-bold uppercase">
                                Sincronizando Velas ({activeSymbol})...
                            </p>
                        </>
                    )}
                </div>
            )}

            {/* Mobile Toggle Button for Legends */}
            <button
                type="button"
                onClick={() => setShowMobileLegends((prev) => !prev)}
                className="md:hidden absolute top-2 right-2 z-30 min-h-[44px] px-3 bg-black/85 backdrop-blur-md border border-white/15 rounded-lg text-xs font-mono font-bold text-slate-200 hover:text-white flex items-center gap-1.5 cursor-pointer shadow-lg"
            >
                <HelpCircle size={14} className="text-neon-cyan" />
                <span>{showMobileLegends ? 'Cerrar' : 'Leyenda'}</span>
            </button>

            {/* Session Legend Overlay */}
            {isEnabled('session') && sessionData && (
                <div
                    className={`absolute bottom-12 md:bottom-4 left-2 md:left-4 z-20 pointer-events-none bg-[#050B14]/90 backdrop-blur-md border border-white/10 rounded-lg p-3 shadow-2xl ${
                        showMobileLegends ? 'block' : 'hidden md:block'
                    }`}
                >
                    <p className="text-[10px] font-bold text-slate-200 mb-2 border-b border-white/10 pb-1 text-center">
                        Sesiones Institucionales
                    </p>
                    <ul className="flex flex-col gap-1.5 text-[10px] text-slate-300">
                        <li className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded border border-orange-400 bg-orange-400/50" />
                            <span>Asia (Acumulación)</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded border border-blue-400 bg-blue-400/50" />
                            <span>Londres (Manipulación)</span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded border border-purple-400 bg-purple-400/50" />
                            <span>Nueva York (Expansión)</span>
                        </li>
                    </ul>
                    {sessionData.is_killzone && (
                        <div className="mt-2 pt-2 border-t border-white/10 flex items-center justify-center text-neon-red animate-pulse font-bold">
                            <span className="text-[10px]">KILLZONE EN CURSO</span>
                        </div>
                    )}
                </div>
            )}

            <div className="hidden md:flex absolute top-4 right-4 z-20 pointer-events-none opacity-40 flex-col items-end">
                <p className="text-[10px] font-black tracking-widest text-slate-300">SLINGSHOT V14.0</p>
                <p className="text-[9px] font-bold text-neon-cyan uppercase">SOP-148 Institutional</p>
            </div>
        </div>
    );
}
