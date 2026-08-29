'use client';

import React, { useEffect, useRef } from 'react';
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
    const williamsRRef = useRef<ISeriesApi<'Line'> | null>(null);
    const sessionSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const killzoneSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const valueAreaSeriesRef = useRef<ISeriesApi<'Baseline'> | null>(null);
    const priceLineRef = useRef<any>(null);
    const pocLineRef = useRef<any>(null);
    const vahLineRef = useRef<any>(null);
    const valLineRef = useRef<any>(null);
    const srLinesRef = useRef<{ line: any; series: any }[]>([]);
    const liquidityLinesRef = useRef<any[]>([]);
    const liquidationLinesRef = useRef<any[]>([]);
    const trapMarkersRef = useRef<any[]>([]);
    const smcSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const fvgSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const markersDetachRef = useRef<{ detach: () => void } | null>(null);

    const { candles, isConnected, smcData, liquidityHeatmap, tacticalDecision, sessionData, liquidations, latestPrice, activeSymbol, activeTimeframe, auditedSignals, signalHistory } = useTelemetryStore();
    const { indicators } = useIndicatorsStore();
    const isEnabled = (id: string) => indicators.find(i => i.id === id)?.enabled ?? false;

    const TIMEFRAME_SECONDS: Record<string, number> = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
        '4h': 14400,
        '1d': 86400,
    };

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
        });

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

        if (williamsRRef.current) {
            const isR = isEnabled('williams_r');
            williamsRRef.current.applyOptions({ visible: isR });
            if (isR) {
                try {
                    const rData = sorted.map((c, idx) => {
                        const start = Math.max(0, idx - 13);
                        const slice = sorted.slice(start, idx + 1);
                        const hh = Math.max(...slice.map(x => x.high));
                        const ll = Math.min(...slice.map(x => x.low));
                        const val = hh === ll ? -50 : ((hh - c.close) / (hh - ll + 1e-9)) * -100;
                        return { time: c.time, value: val };
                    });
                    williamsRRef.current.setData(rData as any);
                    chartRef.current?.priceScale('williams_r').applyOptions({ visible: true });
                } catch(e){}
            } else {
                chartRef.current?.priceScale('williams_r').applyOptions({ visible: false });
            }
        }
    }, [candles, indicators]);

    // ── Precision & Live Price ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s || !latestPrice || latestPrice <= 0 || candles.length === 0) return;
        
        // 1. Dynamic Precision
        let precision = 2, minMove = 0.01;
        if (latestPrice < 0.001) { precision = 8; minMove = 0.00000001; }
        else if (latestPrice < 0.1) { precision = 6; minMove = 0.000001; }
        else if (latestPrice < 10) { precision = 4; minMove = 0.0001; }
        else if (latestPrice < 100) { precision = 3; minMove = 0.001; }
        try { s.applyOptions({ priceFormat: { type: 'price', precision, minMove } }); } catch(e){}

        // 2. Real-time Candle Body (Lattice Scanner Style)
        const last = candles[candles.length - 1];
        if (last && last.time) {
            const timeframeDuration = TIMEFRAME_SECONDS[activeTimeframe] || 300;
            const nowSeconds = Date.now() / 1000;
            const isCandleActive = (nowSeconds - Number(last.time)) < timeframeDuration * 1.5;

            if (isCandleActive) {
                try {
                    s.update({
                        ...last,
                        time: Math.floor(Number(last.time)) as any,
                        close: latestPrice,
                        high: Math.max(last.high, latestPrice),
                        low: Math.min(last.low, latestPrice),
                    } as any);
                } catch (e) {}
            }
        }

        // 3. Price Line
        if (priceLineRef.current) { try { s.removePriceLine(priceLineRef.current); } catch(e){} priceLineRef.current = null; }
        const isUp = last ? latestPrice >= last.open : true;
        try {
            priceLineRef.current = s.createPriceLine({
                price: latestPrice, 
                color: isUp ? 'rgba(0,255,65,0.9)' : 'rgba(255,0,60,0.9)',
                lineWidth: 1, 
                lineStyle: LineStyle.Dotted, 
                axisLabelVisible: true, 
                title: '',
            });
        } catch(e){}
    }, [latestPrice, candles]);

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
        const chart = chartRef.current; 
        const s = candleSeriesRef.current;
        if (!chart || !s || !smcData?.volume_profile || candles.length === 0) return;
        
        const vp = smcData.volume_profile;
        const times = candles.map(c => Number(c.time)).sort((a, b) => a - b);
        
        // Limpiar elementos previos
        if (valueAreaSeriesRef.current) { try { chart.removeSeries(valueAreaSeriesRef.current); } catch(e){} }
        if (pocLineRef.current) { try { s.removePriceLine(pocLineRef.current); } catch(e){} }
        if (vahLineRef.current) { try { s.removePriceLine(vahLineRef.current); } catch(e){} }
        if (valLineRef.current) { try { s.removePriceLine(valLineRef.current); } catch(e){} }
        
        valueAreaSeriesRef.current = null; 
        pocLineRef.current = null;
        vahLineRef.current = null;
        valLineRef.current = null;

        if (isEnabled('value_area') && vp.vah && vp.val && vp.poc) {
            // 1. Área sombreada entre VAL y VAH
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
                va.setData(recentTimes.map(time => ({ time, value: vp.vah })) as any);
                valueAreaSeriesRef.current = va;
            } catch(e){}

            // 2. Líneas de Precio Institucionales en el Eje Y
            try { 
                vahLineRef.current = s.createPriceLine({ 
                    price: vp.vah, 
                    color: '#FFD700', 
                    lineWidth: 2, 
                    lineStyle: LineStyle.Dashed, 
                    axisLabelVisible: true, 
                    title: '🏛️ YOSH VAH (70%)' 
                }); 
            } catch(e){}

            try { 
                pocLineRef.current = s.createPriceLine({ 
                    price: vp.poc, 
                    color: '#FFCC00', 
                    lineWidth: 3, 
                    lineStyle: LineStyle.Solid, 
                    axisLabelVisible: true, 
                    title: '🏦 YOSH POC (Max Vol)' 
                }); 
            } catch(e){}

            try { 
                valLineRef.current = s.createPriceLine({ 
                    price: vp.val, 
                    color: '#EAB308', 
                    lineWidth: 2, 
                    lineStyle: LineStyle.Dashed, 
                    axisLabelVisible: true, 
                    title: '🏛️ YOSH VAL (70%)' 
                }); 
            } catch(e){}
        }
    }, [smcData, indicators, candles.length]);

    // ── Markers (Traps & Larry Williams Oops) ──
    useEffect(() => {
        const s = candleSeriesRef.current;
        if (!s) return;

        if (markersDetachRef.current) { try { markersDetachRef.current.detach(); } catch(e){} markersDetachRef.current = null; }

        const markers: any[] = [];

        // 1. Traps Markers (Look Above/Below and Fail)
        if (isEnabled('traps')) {
            // Traps en velas históricas si vienen en smcData o calculadas
            const last = candles[candles.length - 1];
            if (last && smcData?.traps) {
                if (smcData.traps.laf_bull) { 
                    markers.push({ 
                        time: Number(last.time), 
                        position: 'belowBar', 
                        color: '#00E5FF', 
                        shape: 'arrowUp', 
                        text: '🪤 LBF Bull Trap' 
                    }); 
                }
                if (smcData.traps.laf_bear) { 
                    markers.push({ 
                        time: Number(last.time), 
                        position: 'aboveBar', 
                        color: '#FF007A', 
                        shape: 'arrowDown', 
                        text: '🪤 LAF Bear Trap' 
                    }); 
                }
            }

            // También revisamos si hay barridos de liquidez en las últimas velas
            const sweeps = (smcData as any)?.liquidity_sweeps;
            if (candles.length >= 5 && sweeps && Array.isArray(sweeps)) {
                sweeps.forEach((sw: any) => {
                    const swTime = Number(sw.timestamp || sw.time);
                    if (swTime) {
                        markers.push({
                            time: swTime,
                            position: sw.type === 'BULLISH_SWEEP' ? 'belowBar' : 'aboveBar',
                            color: '#FF00FF',
                            shape: sw.type === 'BULLISH_SWEEP' ? 'arrowUp' : 'arrowDown',
                            text: `🪤 ${sw.type === 'BULLISH_SWEEP' ? 'Sweep Low' : 'Sweep High'}`
                        });
                    }
                });
            }
        }

        // 2. Larry Williams / Oops Reversal & SMC Signals
        if (isEnabled('williams_oops')) {
            const allSignals = [
                ...Object.values(auditedSignals || {}),
                ...Object.values(signalHistory || {})
            ];
            
            allSignals.forEach((sig: any) => {
                if (sig.asset?.toUpperCase() !== activeSymbol?.toUpperCase()) return;
                
                const rawTs = Number(sig.timestamp || sig.time);
                if (isNaN(rawTs) || rawTs <= 0) return;
                const ts = rawTs > 10000000000 ? Math.floor(rawTs / 1000) : Math.floor(rawTs);
                
                const isLong = sig.signal_type?.toUpperCase().includes('LONG') || sig.type?.toUpperCase().includes('LONG');
                
                if (sig.type?.includes('Oops') || sig.strategy?.includes('Oops') || sig.type === 'Oops! Reversal') {
                    markers.push({
                        time: ts,
                        position: isLong ? 'belowBar' : 'aboveBar',
                        color: '#E11D48',
                        shape: isLong ? 'arrowUp' : 'arrowDown',
                        text: `Oops! ${isLong ? 'Buy' : 'Sell'}`
                    });
                }
            });
        }

        const unique = markers
            .filter((v, i, a) => a.findIndex(t => t.time === v.time && t.text === v.text) === i)
            .sort((a, b) => Number(a.time) - Number(b.time));

        if (unique.length > 0) {
            try {
                markersDetachRef.current = createSeriesMarkers(s, unique);
            } catch(e) {
                console.warn("[Chart] createSeriesMarkers failed:", e);
            }
        }
    }, [smcData, indicators, candles.length, auditedSignals, signalHistory, activeSymbol]);

    // ── Key Levels, Sessions & Fibonacci ──
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

        const isSessionEnabled = isEnabled('session');
        const isOopsEnabled = isEnabled('williams_oops');

        if (sessionData && (isSessionEnabled || isOopsEnabled)) {
            // PDH / PDL / ONH / ONL
            const { pdh, pdl, onh, onl } = sessionData;
            
            // Dibujar PDH/PDL si cualquiera de los dos está activado
            if (pdh) addLine(pdh, isOopsEnabled ? '#E11D48' : '#FF9F00', isOopsEnabled ? '🏦 PDH (LARRY WILLIAMS)' : '🏦 PDH (DAILY HIGH)', LineStyle.Solid, 2);
            if (pdl) addLine(pdl, isOopsEnabled ? '#10B981' : '#00FF00', isOopsEnabled ? '🏦 PDL (LARRY WILLIAMS)' : '🏦 PDL (DAILY LOW)', LineStyle.Solid, 2);

            if (isSessionEnabled && sessionData.sessions && typeof sessionData.sessions === 'object') {
                const { sessions } = sessionData;

                const sessionColors: Record<string, { color: string; bg: string; kz: string }> = {
                    asia:   { color: 'rgba(251,146,60,0.8)', bg: 'rgba(251,146,60,0.25)', kz: 'rgba(251,146,60,0.40)' },
                    london: { color: 'rgba(96,165,250,0.8)',  bg: 'rgba(96,165,250,0.25)',  kz: 'rgba(96,165,250,0.40)' },
                    ny:     { color: 'rgba(192,132,252,0.8)', bg: 'rgba(192,132,252,0.25)', kz: 'rgba(192,132,252,0.40)' },
                };

                const sorted = [...candles].sort((a, b) => Number(a.time) - Number(b.time)).filter((c, i, arr) => i === 0 || c.time !== arr[i - 1].time);

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
            }
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
