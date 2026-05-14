'use client';

import React, { useEffect, useRef } from 'react';
import {
    createChart,
    CandlestickSeries,
    HistogramSeries,
    BaselineSeries,
    createSeriesMarkers,
    ColorType,
    CrosshairMode,
    LineStyle,
} from 'lightweight-charts';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { useTelemetryStore } from '../../store/telemetryStore';
import { useIndicatorsStore } from '../../store/indicatorsStore';

/**
 * SLINGSHOT V13.2 — CORRECT lightweight-charts v5.1.0 API
 * API: chart.addSeries(SeriesDefinition, options)
 * Markers: createSeriesMarkers(series, markers)
 */

export default function TradingChart() {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
    const sessionSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const valueAreaSeriesRef = useRef<ISeriesApi<'Baseline'> | null>(null);
    const priceLineRef = useRef<any>(null);
    const pocLineRef = useRef<any>(null);
    const srLinesRef = useRef<{ line: any; series: any }[]>([]);
    const liquidityLinesRef = useRef<any[]>([]);
    const liquidationLinesRef = useRef<any[]>([]);
    const trapMarkersRef = useRef<any[]>([]);
    const smcSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const fvgSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const markersDetachRef = useRef<{ detach: () => void } | null>(null);

    const { candles, isConnected, smcData, liquidityHeatmap, tacticalDecision, sessionData, liquidations, latestPrice } = useTelemetryStore();
    const { indicators } = useIndicatorsStore();
    const isEnabled = (id: string) => indicators.find(i => i.id === id)?.enabled ?? false;

    // ── Chart Init ──
    useEffect(() => {
        if (!chartContainerRef.current) return;
        const chart = createChart(chartContainerRef.current, {
            layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#64748b' },
            grid: { vertLines: { color: 'rgba(255,255,255,0.03)' }, horzLines: { color: 'rgba(255,255,255,0.03)' } },
            crosshair: {
                mode: CrosshairMode.Magnet,
                vertLine: { color: '#00E5FF', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#00E5FF' },
                horzLine: { color: '#00E5FF', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#00E5FF' },
            },
            timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: true, secondsVisible: false },
            rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
            autoSize: true,
        } as any);
        chartRef.current = chart;

        candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
            upColor: '#00FF41', downColor: '#FF003C', borderVisible: false,
            wickUpColor: '#00FF41', wickDownColor: '#FF003C',
        });
        volumeRef.current = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' }, priceScaleId: 'volume',
        });
        chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, borderVisible: false });

        return () => { chart.remove(); };
    }, []);

    // ── Candles & Volume ──
    useEffect(() => {
        if (!candleSeriesRef.current || candles.length === 0) return;
        const sorted = [...candles].sort((a, b) => Number(a.time) - Number(b.time)).filter((c, i, arr) => i === 0 || c.time !== arr[i - 1].time);
        if (sorted.length === 0) return;
        try { candleSeriesRef.current.setData(sorted as any); } catch (e) { console.error("[Chart] setData error:", e); }

        const mainBottom = isEnabled('volume') ? 0.28 : 0.08;
        chartRef.current?.priceScale('right').applyOptions({ scaleMargins: { top: 0.05, bottom: mainBottom } });

        if (volumeRef.current) {
            volumeRef.current.applyOptions({ visible: isEnabled('volume') });
            if (isEnabled('volume')) {
                try {
                    volumeRef.current.setData(sorted.map(c => ({
                        time: c.time, value: c.volume,
                        color: c.close >= c.open ? 'rgba(0,255,65,0.4)' : 'rgba(255,0,60,0.4)',
                    })) as any);
                    chartRef.current?.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 }, visible: true });
                } catch (e) {}
            }
        }
    }, [candles, indicators]);

    // ── Precision & Live Price ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s || !latestPrice || latestPrice <= 0) return;
        let precision = 2, minMove = 0.01;
        if (latestPrice < 0.001) { precision = 8; minMove = 0.00000001; }
        else if (latestPrice < 0.1) { precision = 6; minMove = 0.000001; }
        else if (latestPrice < 10) { precision = 4; minMove = 0.0001; }
        else if (latestPrice < 100) { precision = 3; minMove = 0.001; }
        try { s.applyOptions({ priceFormat: { type: 'price', precision, minMove } }); } catch(e){}

        if (priceLineRef.current) { try { s.removePriceLine(priceLineRef.current); } catch(e){} priceLineRef.current = null; }
        const last = candles.length > 0 ? candles[candles.length - 1] : null;
        const isUp = last ? latestPrice >= last.open : true;
        try {
            priceLineRef.current = s.createPriceLine({
                price: latestPrice, color: isUp ? 'rgba(0,255,65,0.9)' : 'rgba(255,0,60,0.9)',
                lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true, title: '',
            });
        } catch(e){}
    }, [latestPrice]);

    // ── SMC & FVG ──
    useEffect(() => {
        const chart = chartRef.current;
        if (!chart || !smcData || candles.length === 0) return;
        const times = candles.map(c => Number(c.time)).sort((a, b) => a - b);

        smcSeriesRef.current.forEach(s => { try { chart.removeSeries(s); } catch(e){} });
        smcSeriesRef.current = [];
        fvgSeriesRef.current.forEach(s => { try { chart.removeSeries(s); } catch(e){} });
        fvgSeriesRef.current = [];

        const addBaseline = (opts: any, data: any[]) => {
            try {
                const s = chart.addSeries(BaselineSeries, opts);
                s.setData(data as any);
                return s;
            } catch(e) { return null; }
        };

        if (isEnabled('smc')) {
            smcData.order_blocks.bullish.forEach(ob => {
                const s = addBaseline({
                    baseValue: { type: 'price', price: ob.bottom },
                    topFillColor1: 'rgba(0,255,136,0.4)', topFillColor2: 'rgba(0,255,136,0.1)', topLineColor: 'rgba(0,255,136,0.8)',
                    bottomFillColor1: 'transparent', bottomFillColor2: 'transparent', bottomLineColor: 'transparent',
                    lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                }, times.filter(t => t >= ob.time).map(time => ({ time, value: ob.top })));
                if (s) smcSeriesRef.current.push(s);
            });
            smcData.order_blocks.bearish.forEach(ob => {
                const s = addBaseline({
                    baseValue: { type: 'price', price: ob.top },
                    bottomFillColor1: 'rgba(255,0,60,0.4)', bottomFillColor2: 'rgba(255,0,60,0.1)', bottomLineColor: 'rgba(255,0,60,0.8)',
                    topFillColor1: 'transparent', topFillColor2: 'transparent', topLineColor: 'transparent',
                    lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                }, times.filter(t => t >= ob.time).map(time => ({ time, value: ob.bottom })));
                if (s) smcSeriesRef.current.push(s);
            });
        }
        if (isEnabled('fvg')) {
            smcData.fvgs.bullish.forEach(fvg => {
                const s = addBaseline({
                    baseValue: { type: 'price', price: fvg.bottom },
                    topFillColor1: 'rgba(255,204,0,0.2)', topFillColor2: 'rgba(255,204,0,0.05)', topLineColor: 'rgba(255,204,0,0.6)',
                    bottomFillColor1: 'transparent', bottomFillColor2: 'transparent', bottomLineColor: 'transparent',
                    lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                }, times.filter(t => t >= fvg.time).map(time => ({ time, value: fvg.top })));
                if (s) fvgSeriesRef.current.push(s);
            });
            smcData.fvgs.bearish.forEach(fvg => {
                const s = addBaseline({
                    baseValue: { type: 'price', price: fvg.top },
                    bottomFillColor1: 'rgba(255,204,0,0.2)', bottomFillColor2: 'rgba(255,204,0,0.05)', bottomLineColor: 'rgba(255,204,0,0.6)',
                    topFillColor1: 'transparent', topFillColor2: 'transparent', topLineColor: 'transparent',
                    lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                }, times.filter(t => t >= fvg.time).map(time => ({ time, value: fvg.bottom })));
                if (s) fvgSeriesRef.current.push(s);
            });
        }
    }, [smcData, indicators, candles.length]);

    // ── Liquidity Heatmap ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s || !liquidityHeatmap || !isEnabled('heatmap')) {
            liquidityLinesRef.current.forEach(l => { try { s?.removePriceLine(l); } catch(e){} });
            liquidityLinesRef.current = [];
            return;
        }
        liquidityLinesRef.current.forEach(l => { try { s.removePriceLine(l); } catch(e){} });
        liquidityLinesRef.current = [];
        const bids = liquidityHeatmap.bids || (liquidityHeatmap as any).hot_bids || [];
        const asks = liquidityHeatmap.asks || (liquidityHeatmap as any).hot_asks || [];
        if (bids.length === 0 && asks.length === 0) return;
        const maxVol = Math.max(...bids.concat(asks).map((x: any) => x.volume), 1);
        const add = (lvl: any, base: string) => {
            try {
                const intensity = 0.15 + 0.55 * (lvl.volume / maxVol);
                const line = s.createPriceLine({ price: lvl.price, color: `${base}${intensity})`, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: false, title: `WALL: ${lvl.volume?.toFixed(0)}V` });
                if (line) liquidityLinesRef.current.push(line);
            } catch(e){}
        };
        bids.forEach((b: any) => add(b, 'rgba(0,255,65,'));
        asks.forEach((a: any) => add(a, 'rgba(255,0,60,'));
    }, [liquidityHeatmap, indicators]);

    // ── Liquidations ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s || !liquidations) return;
        liquidationLinesRef.current.forEach(l => { try { s.removePriceLine(l); } catch(e){} });
        liquidationLinesRef.current = [];
        if (isEnabled('liquidations')) {
            liquidations.forEach(liq => {
                try {
                    const isShort = liq.type === 'SHORT_LIQ';
                    const opacity = 0.1 + (liq.strength / 100) * 0.4;
                    const color = isShort ? `rgba(0,229,255,${opacity})` : `rgba(192,132,252,${opacity})`;
                    const line = s.createPriceLine({ price: liq.price, color, lineWidth: Math.max(1, Math.floor(liq.strength / 20)) as any, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `REKT: ${liq.strength}%` });
                    if (line) liquidationLinesRef.current.push(line);
                } catch(e){}
            });
        }
    }, [liquidations, indicators]);

    // ── YOSH Value Area ──
    useEffect(() => {
        const chart = chartRef.current; const s = candleSeriesRef.current;
        if (!chart || !s || !smcData?.volume_profile || candles.length === 0) return;
        const vp = smcData.volume_profile;
        const times = candles.map(c => Number(c.time)).sort((a, b) => a - b);
        if (valueAreaSeriesRef.current) { try { chart.removeSeries(valueAreaSeriesRef.current); } catch(e){} }
        if (pocLineRef.current) { try { s.removePriceLine(pocLineRef.current); } catch(e){} }
        valueAreaSeriesRef.current = null; pocLineRef.current = null;
        if (isEnabled('value_area') && vp.vah && vp.val) {
            try {
                const va = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: vp.val },
                    topFillColor1: 'rgba(255,215,0,0.15)', topFillColor2: 'rgba(255,215,0,0.05)', topLineColor: 'rgba(255,215,0,0.8)',
                    bottomFillColor1: 'transparent', lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
                });
                va.setData(times.slice(-Math.min(times.length, 50)).map(time => ({ time, value: vp.vah })) as any);
                valueAreaSeriesRef.current = va;
            } catch(e){}
            try { pocLineRef.current = s.createPriceLine({ price: vp.poc, color: '#FFD700', lineWidth: 3, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: '🏦 YOSH POC' }); } catch(e){}
        }
    }, [smcData, indicators, candles.length]);

    // ── Traps (Markers v5 API) ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s) return;

        // Si traps está desactivado, limpiar marcadores existentes
        if (!isEnabled('traps')) {
            if (markersDetachRef.current) { try { markersDetachRef.current.detach(); } catch(e){} markersDetachRef.current = null; }
            trapMarkersRef.current = [];
            return;
        }

        if (!smcData?.traps) return;
        const last = candles[candles.length - 1];
        if (!last) return;
        let changed = false;
        const newM = [...trapMarkersRef.current];
        if (smcData.traps.laf_bull) { newM.push({ time: last.time, position: 'belowBar', color: '#FF00FF', shape: 'arrowUp', text: 'LBF 🪤' }); changed = true; }
        if (smcData.traps.laf_bear) { newM.push({ time: last.time, position: 'aboveBar', color: '#FF00FF', shape: 'arrowDown', text: 'LAF 🪤' }); changed = true; }
        if (changed) {
            const unique = newM.filter((v, i, a) => a.findIndex(t => t.time === v.time && t.text === v.text) === i).slice(-50);
            trapMarkersRef.current = unique;
            if (markersDetachRef.current) { try { markersDetachRef.current.detach(); } catch(e){} }
            try { markersDetachRef.current = createSeriesMarkers(s, unique); } catch(e){ console.warn("[Chart] createSeriesMarkers failed:", e); }
        }
    }, [smcData, indicators]);

    // ── Key Levels, Sessions & Fibonacci ──
    const killzoneSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);

    useEffect(() => {
        const chart = chartRef.current; const s = candleSeriesRef.current;
        if (!chart || !s) return;

        // Cleanup all previous lines
        srLinesRef.current.forEach(({ line, series: sr }) => { try { sr.removePriceLine(line); } catch(e){} });
        srLinesRef.current = [];

        const addLine = (price: number | null | undefined, color: string, title: string, style: number, width: number = 1) => {
            if (!price || !s) return;
            try {
                const line = s.createPriceLine({ price, color, lineWidth: width as any, lineStyle: style, axisLabelVisible: true, title });
                if (line) srLinesRef.current.push({ line, series: s });
            } catch(e){}
        };

        // ── S/R Enhanced Labels ──
        if (isEnabled('sr')) {
            const { resistances = [], supports = [] } = tacticalDecision?.key_levels || {};

            const touchesToWidth = (lvl: any): number => lvl.mtf_confluence ? 4 : (lvl.ob_confluence ? 3 : lvl.touches >= 4 ? 3 : lvl.touches >= 2 ? 2 : 1);
            const touchesToAlpha = (t: number, mtf: boolean): string => mtf ? '1.0' : t >= 4 ? '0.9' : t >= 2 ? '0.7' : '0.4';
            const getLevelColor = (lvl: any, alpha: string): string => {
                if (lvl.type === 'RESISTANCE' || lvl.origin === 'RESISTANCE') {
                    return lvl.origin === 'ROLE_REVERSAL' ? `rgba(251,146,60,${alpha})` : `rgba(255,0,60,${alpha})`;
                }
                return lvl.origin === 'ROLE_REVERSAL' ? `rgba(250,204,21,${alpha})` : `rgba(0,255,65,${alpha})`;
            };

            resistances.forEach((r: any, i: number) => {
                const rank = i + 1;
                const alpha = touchesToAlpha(r.touches, r.mtf_confluence ?? false);
                const w = touchesToWidth(r);
                const color = getLevelColor({ ...r, type: 'RESISTANCE' }, alpha);
                const mtfTag = r.mtf_confluence ? '◈' : '';
                const obTag = r.ob_confluence ? '★' : '';
                const volTag = (r.volume_score ?? 1) > 1.5 ? '⚡' : '';
                const typeTag = r.origin === 'ROLE_REVERSAL' ? '↩' : '▲';
                const label = `R${rank}${mtfTag}${obTag}${volTag}${typeTag}(${r.touches}t)`;
                const style = r.mtf_confluence ? LineStyle.Solid : (rank === 1 ? LineStyle.Dashed : LineStyle.Dotted);
                addLine(r.price, color, label, style, w);
            });

            supports.forEach((sup: any, i: number) => {
                const rank = i + 1;
                const alpha = touchesToAlpha(sup.touches, sup.mtf_confluence ?? false);
                const w = touchesToWidth(sup);
                const color = getLevelColor({ ...sup, type: 'SUPPORT' }, alpha);
                const mtfTag = sup.mtf_confluence ? '◈' : '';
                const obTag = sup.ob_confluence ? '★' : '';
                const volTag = (sup.volume_score ?? 1) > 1.5 ? '⚡' : '';
                const typeTag = sup.origin === 'ROLE_REVERSAL' ? '↩' : '▼';
                const label = `S${rank}${mtfTag}${obTag}${volTag}${typeTag}(${sup.touches}t)`;
                const style = sup.mtf_confluence ? LineStyle.Solid : (rank === 1 ? LineStyle.Dashed : LineStyle.Dotted);
                addLine(sup.price, color, label, style, w);
            });
        }

        // ── Fibonacci (Autofib) ──
        if (isEnabled('fibonacci') && tacticalDecision?.fibonacci?.levels) {
            const { levels, swing_high, swing_low } = tacticalDecision.fibonacci;
            const isUptrend = (swing_low ?? 0) < (swing_high ?? 0);
            Object.entries(levels).forEach(([label, price]) => {
                const p = price as number;
                if (label === '0.618') addLine(p, 'rgba(0,229,255,1.0)', '0.618 ★GP', LineStyle.Solid, 2);
                else if (label === '0.66') addLine(p, 'rgba(0,229,255,0.7)', '0.66  ★GP', LineStyle.Dashed, 2);
                else if (label === '0.0') addLine(p, 'rgba(255,255,255,0.8)', isUptrend ? 'Swing High' : 'Swing Low', LineStyle.Solid, 2);
                else if (label === '1.0') addLine(p, 'rgba(255,255,255,0.8)', isUptrend ? 'Swing Low' : 'Swing High', LineStyle.Solid, 2);
                else if (label === '0.786') addLine(p, 'rgba(255,80,80,0.6)', 'Fib 0.786', LineStyle.Dotted, 1);
                else addLine(p, 'rgba(255,255,255,0.4)', `Fib ${label}`, LineStyle.Dashed, 1);
            });
        }

        // ── Session Brackets Históricos ──
        sessionSeriesRef.current.forEach(sr => { try { chart.removeSeries(sr); } catch(e){} });
        sessionSeriesRef.current = [];
        killzoneSeriesRef.current.forEach(sr => { try { chart.removeSeries(sr); } catch(e){} });
        killzoneSeriesRef.current = [];

        if (sessionData?.sessions && typeof sessionData.sessions === 'object' && isEnabled('session')) {
            const { sessions } = sessionData;

            const sessionColors: Record<string, { color: string; bg: string; kz: string }> = {
                asia:   { color: 'rgba(251,146,60,0.8)', bg: 'rgba(251,146,60,0.25)', kz: 'rgba(251,146,60,0.40)' },
                london: { color: 'rgba(96,165,250,0.8)',  bg: 'rgba(96,165,250,0.25)',  kz: 'rgba(96,165,250,0.40)' },
                ny:     { color: 'rgba(192,132,252,0.8)', bg: 'rgba(192,132,252,0.25)', kz: 'rgba(192,132,252,0.40)' },
            };

            const sorted = [...candles].sort((a, b) => Number(a.time) - Number(b.time)).filter((c, i, arr) => i === 0 || c.time !== arr[i - 1].time);

            // PDH / PDL / ONH / ONL
            const { pdh, pdl, onh, onl } = sessionData;
            addLine(pdh, '#FF9F00', '🏦 PDH (DAILY HIGH)', LineStyle.Solid, 3);
            addLine(pdl, '#00FF00', '🏦 PDL (DAILY LOW)', LineStyle.Solid, 3);
            if (onh) addLine(onh, '#FF00FF', '🌙 ONH (OVERNIGHT HIGH)', LineStyle.Dashed, 2);
            if (onl) addLine(onl, '#FF00FF', '🌙 ONL (OVERNIGHT LOW)', LineStyle.Dashed, 2);

            // LVN Lines
            const lvns = sessionData?.volume_profile?.lvns || [];
            lvns.forEach((lvn: number, i: number) => {
                addLine(lvn, 'rgba(200,200,200,0.5)', `📉 LVN ${i + 1}`, LineStyle.Dotted, 1);
            });

            if (sorted.length > 0) {
                // Historical Session Boxes
                Object.entries(sessions).forEach(([id, info]: [string, any]) => {
                    if (info.start_utc == null || info.end_utc == null) return;
                    if (!sessionColors[id]) return;

                    let currentBlock: any[] = [];
                    const blocks: any[][] = [];

                    for (let i = 0; i < sorted.length; i++) {
                        const c = sorted[i];
                        const h = new Date(Number(c.time) * 1000).getUTCHours();
                        let inside = false;
                        if (info.start_utc < info.end_utc) inside = h >= info.start_utc && h < info.end_utc;
                        else inside = h >= info.start_utc || h < info.end_utc;

                        if (inside) { currentBlock.push(c); }
                        else { if (currentBlock.length > 0) { blocks.push(currentBlock); currentBlock = []; } }
                    }
                    if (currentBlock.length > 0) blocks.push(currentBlock);

                    blocks.forEach((blockCandles) => {
                        if (blockCandles.length < 2) return;
                        const blockHigh = Math.max(...blockCandles.map(c => c.high));
                        const blockLow = Math.min(...blockCandles.map(c => c.low));

                        try {
                            const bracket = chart.addSeries(BaselineSeries, {
                                baseValue: { type: 'price', price: blockLow },
                                topFillColor1: sessionColors[id].bg, topFillColor2: 'transparent',
                                topLineColor: sessionColors[id].color, lineWidth: 1,
                                bottomFillColor1: 'transparent', bottomFillColor2: 'transparent', bottomLineColor: 'transparent',
                                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                            });
                            bracket.setData(blockCandles.map(c => ({ time: c.time, value: blockHigh })) as any);
                            sessionSeriesRef.current.push(bracket);
                        } catch(e){}

                        // Killzone Glow
                        const kzHours = id === 'asia' ? 4 : 3;
                        const kzStart = info.start_utc;
                        const kzEnd = (info.start_utc + kzHours) % 24;
                        const kzCandles = blockCandles.filter(c => {
                            const hh = new Date(Number(c.time) * 1000).getUTCHours();
                            if (kzStart < kzEnd) return hh >= kzStart && hh < kzEnd;
                            return hh >= kzStart || hh < kzEnd;
                        });

                        if (kzCandles.length > 0) {
                            try {
                                const kzGlow = chart.addSeries(BaselineSeries, {
                                    baseValue: { type: 'price', price: blockLow },
                                    topFillColor1: sessionColors[id].kz, topFillColor2: sessionColors[id].kz,
                                    topLineColor: 'transparent', lineWidth: 1,
                                    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                                });
                                kzGlow.setData(kzCandles.map(c => ({ time: c.time, value: blockHigh })) as any);
                                killzoneSeriesRef.current.push(kzGlow);
                            } catch(e){}
                        }
                    });
                });
            }
        } else if (isEnabled('session') && sessionData) {
            // Fallback: solo líneas fijas si no hay sessions object
            const { pdh, pdl, onh, onl } = sessionData;
            addLine(pdh, '#FF9F00', 'DAILY HIGH', LineStyle.Solid, 3);
            addLine(pdl, '#00FF00', 'DAILY LOW', LineStyle.Solid, 3);
            if (onh) addLine(onh, '#FF00FF', 'OVERNIGHT H', LineStyle.Dashed, 2);
            if (onl) addLine(onl, '#FF00FF', 'OVERNIGHT L', LineStyle.Dashed, 2);
        }
    }, [tacticalDecision, sessionData, indicators, candles.length]);

    return (
        <div className="w-full h-full relative" ref={chartContainerRef}>
            {!isConnected && (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="w-12 h-12 border-2 border-t-neon-cyan border-r-neon-cyan/50 border-b-transparent border-l-transparent rounded-full animate-spin" />
                    <p className="text-neon-cyan/80 text-xs tracking-[0.2em] mt-4 font-bold uppercase">Conectando Telemetría...</p>
                </div>
            )}

            {/* S/R Legend Overlay */}
            {isEnabled('sr') && tacticalDecision?.key_levels && (
                <div className="absolute top-4 left-4 z-20 pointer-events-none bg-[#050B14]/80 backdrop-blur-md border border-white/10 rounded-lg p-3 max-w-[280px] shadow-2xl">
                    <p className="text-[10px] font-bold text-white/80 mb-2 border-b border-white/10 pb-1 flex items-center justify-between">
                        <span>Leyes de S/R Institucional</span>
                        <span className="text-neon-cyan">SMC</span>
                    </p>
                    <ul className="flex flex-col gap-1.5 text-[9px] text-white/60">
                        <li className="flex items-start gap-1"><span className="text-white font-mono mt-0.5 w-8">▲, ▼</span><span>Soporte/Resistencia convencional.</span></li>
                        <li className="flex items-start gap-1"><span className="text-white font-mono mt-0.5 w-8">↩</span><span><span className="text-yellow-400 font-bold">Role Reversal:</span> S/R roto que se invierte.</span></li>
                        <li className="flex items-start gap-1"><span className="text-white font-mono mt-0.5 w-8">(Nt)</span><span>Toques. Mide la validación estructural.</span></li>
                        <li className="flex items-start gap-1"><span className="text-white font-mono mt-0.5 w-8">⚡</span><span><span className="text-neon-cyan font-bold">Volumen:</span> Inyección de capital anómala (&gt;1.5x).</span></li>
                        <li className="flex items-start gap-1"><span className="text-white font-mono mt-0.5 w-8">◈</span><span><span className="text-purple-400 font-bold">MTF:</span> Confluencia con 4H/1D. Líneas Sólidas.</span></li>
                        <li className="flex items-start gap-1"><span className="text-white font-mono mt-0.5 w-8">★</span><span>OB Confluencia: Solapado con Order Block activo.</span></li>
                    </ul>
                </div>
            )}

            {/* Session Legend Overlay */}
            {isEnabled('session') && sessionData && (
                <div className="absolute bottom-4 left-4 z-20 pointer-events-none bg-[#050B14]/80 backdrop-blur-md border border-white/10 rounded-lg p-3 shadow-2xl">
                    <p className="text-[10px] font-bold text-white/80 mb-2 border-b border-white/10 pb-1 text-center">
                        Sesiones Institucionales
                    </p>
                    <ul className="flex flex-col gap-2 text-[9px] text-white/70">
                        <li className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded border border-orange-400 bg-orange-400/50 shadow-[0_0_8px_rgba(251,146,60,0.6)]"></span>
                            <span>Asia <span className="text-white/40 italic">(Acumulación)</span></span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded border border-blue-400 bg-blue-400/50 shadow-[0_0_8px_rgba(96,165,250,0.6)]"></span>
                            <span>Londres <span className="text-white/40 italic">(Manipulación)</span></span>
                        </li>
                        <li className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded border border-purple-400 bg-purple-400/50 shadow-[0_0_8px_rgba(192,132,252,0.6)]"></span>
                            <span>Nueva York <span className="text-white/40 italic">(Expansión)</span></span>
                        </li>
                    </ul>
                    {sessionData.is_killzone && (
                        <div className="mt-2 pt-2 border-t border-white/10 flex items-center justify-center gap-1 text-neon-red animate-pulse font-bold">
                            <span className="text-[9px]">⚠️ KILLZONE EN CURSO</span>
                        </div>
                    )}
                </div>
            )}

            <div className="absolute top-4 right-4 z-20 pointer-events-none opacity-30 flex flex-col items-end">
                <p className="text-[10px] font-black tracking-widest text-white/50">SLINGSHOT V13.2</p>
                <p className="text-[8px] font-bold text-neon-cyan uppercase">Sovereign Intelligence</p>
            </div>
        </div>
    );
}
