'use client';

import React, { useEffect, useRef } from 'react';
import {
    createChart,
    ColorType,
    IChartApi,
    ISeriesApi,
    LineStyle,
    CrosshairMode,
    CandlestickSeries,
    LineSeries,
    HistogramSeries,
    BaselineSeries
} from 'lightweight-charts';
import { useTelemetryStore, CandleData } from '../../store/telemetryStore';
import { useIndicatorsStore } from '../../store/indicatorsStore';

// ─── Indicator Math ──────────────────────────────────────────────────────────

function calcEMA(candles: CandleData[], period: number): { time: number | string; value: number }[] {
    if (candles.length < period) return [];
    const k = 2 / (period + 1);
    const result: { time: number | string; value: number }[] = [];
    let ema = candles.slice(0, period).reduce((s, c) => s + c.close, 0) / period;
    result.push({ time: candles[period - 1].time, value: ema });
    for (let i = period; i < candles.length; i++) {
        ema = candles[i].close * k + ema * (1 - k);
        result.push({ time: candles[i].time, value: ema });
    }
    return result;
}

function calcBollinger(candles: CandleData[], period = 20, stdMult = 2) {
    const upper: { time: number | string; value: number }[] = [];
    const middle: { time: number | string; value: number }[] = [];
    const lower: { time: number | string; value: number }[] = [];
    for (let i = period - 1; i < candles.length; i++) {
        const slice = candles.slice(i - period + 1, i + 1);
        const mean = slice.reduce((s, c) => s + c.close, 0) / period;
        const variance = slice.reduce((s, c) => s + Math.pow(c.close - mean, 2), 0) / period;
        const std = Math.sqrt(variance);
        middle.push({ time: candles[i].time, value: mean });
        upper.push({ time: candles[i].time, value: mean + stdMult * std });
        lower.push({ time: candles[i].time, value: mean - stdMult * std });
    }
    return { upper, middle, lower };
}

function calcRSI(candles: CandleData[], period = 14): { time: number | string; value: number }[] {
    if (candles.length < period + 1) return [];
    const result: { time: number | string; value: number }[] = [];
    let avgGain = 0;
    let avgLoss = 0;
    for (let i = 1; i <= period; i++) {
        const change = candles[i].close - candles[i - 1].close;
        if (change > 0) avgGain += change; else avgLoss += Math.abs(change);
    }
    avgGain /= period;
    avgLoss /= period;
    const firstRS = avgLoss === 0 ? 100 : avgGain / avgLoss;
    result.push({ time: candles[period].time, value: 100 - 100 / (1 + firstRS) });
    for (let i = period + 1; i < candles.length; i++) {
        const change = candles[i].close - candles[i - 1].close;
        const gain = change > 0 ? change : 0;
        const loss = change < 0 ? Math.abs(change) : 0;
        avgGain = (avgGain * (period - 1) + gain) / period;
        avgLoss = (avgLoss * (period - 1) + loss) / period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        result.push({ time: candles[i].time, value: 100 - 100 / (1 + rs) });
    }
    return result;
}

function calcMACD(candles: CandleData[], fast = 12, slow = 26, signal = 9) {
    const emaFast = calcEMA(candles, fast);
    const emaSlow = calcEMA(candles, slow);
    // Align: slow starts later, so find common candles
    const slowTimes = new Map(emaSlow.map(d => [d.time, d.value]));
    const macdLine = emaFast
        .filter(d => slowTimes.has(d.time))
        .map(d => ({ time: d.time, value: d.value - slowTimes.get(d.time)! }));
    // Compute signal line (EMA of MACD line)
    const syntheticCandles = macdLine.map(d => ({ ...({} as CandleData), time: d.time, close: d.value, open: d.value, high: d.value, low: d.value, volume: 0 }));
    const signalLine = calcEMA(syntheticCandles, signal);
    const signalMap = new Map(signalLine.map(d => [d.time, d.value]));
    const histogram = macdLine
        .filter(d => signalMap.has(d.time))
        .map(d => ({ time: d.time, value: d.value - signalMap.get(d.time)!, color: d.value - signalMap.get(d.time)! >= 0 ? '#26A69A' : '#EF5350' }));
    return { macdLine, signalLine, histogram };
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function TradingChart() {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);

    // Series refs
    const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const ema20Ref = useRef<ISeriesApi<'Line'> | null>(null);
    const ema50Ref = useRef<ISeriesApi<'Line'> | null>(null);
    const ema200Ref = useRef<ISeriesApi<'Line'> | null>(null);
    const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null);
    const bbMidRef = useRef<ISeriesApi<'Line'> | null>(null);
    const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null);
    const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);
    const rsiRef = useRef<ISeriesApi<'Line'> | null>(null);
    const macdLineRef = useRef<ISeriesApi<'Line'> | null>(null);
    const macdSigRef = useRef<ISeriesApi<'Line'> | null>(null);
    const macdHistRef = useRef<ISeriesApi<'Histogram'> | null>(null);

    const { candles, isConnected, smcData } = useTelemetryStore();
    const { indicators } = useIndicatorsStore();

    const isEnabled = (id: string) => indicators.find(i => i.id === id)?.enabled ?? false;

    // ── Chart init ──────────────────────────────────────────────────────────
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#64748b',
            },
            grid: {
                vertLines: { color: 'rgba(255,255,255,0.03)' },
                horzLines: { color: 'rgba(255,255,255,0.03)' },
            },
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

        // Candlesticks
        candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
            upColor: '#00FF41', downColor: '#FF003C',
            borderVisible: false,
            wickUpColor: '#00FF41', wickDownColor: '#FF003C',
        });

        // EMA 20
        ema20Ref.current = chart.addSeries(LineSeries, {
            color: '#00E5FF', lineWidth: 1, lineStyle: LineStyle.Solid,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // EMA 50
        ema50Ref.current = chart.addSeries(LineSeries, {
            color: '#FFC107', lineWidth: 1, lineStyle: LineStyle.Solid,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // EMA 200
        ema200Ref.current = chart.addSeries(LineSeries, {
            color: '#EF5350', lineWidth: 1, lineStyle: LineStyle.Dashed,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // Bollinger Upper
        bbUpperRef.current = chart.addSeries(LineSeries, {
            color: 'rgba(156,39,176,0.6)', lineWidth: 1,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // Bollinger Middle
        bbMidRef.current = chart.addSeries(LineSeries, {
            color: 'rgba(156,39,176,0.4)', lineWidth: 1, lineStyle: LineStyle.Dashed,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // Bollinger Lower
        bbLowerRef.current = chart.addSeries(LineSeries, {
            color: 'rgba(156,39,176,0.6)', lineWidth: 1,
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // Volume  (uses separate price scale)
        volumeRef.current = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });
        chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, borderVisible: false });

        // RSI (separate price scale)
        rsiRef.current = chart.addSeries(LineSeries, {
            color: '#FF7043', lineWidth: 1,
            priceScaleId: 'rsi',
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });
        chart.priceScale('rsi').applyOptions({ scaleMargins: { top: 0.7, bottom: 0.1 }, borderVisible: false });

        // MACD LINE
        macdLineRef.current = chart.addSeries(LineSeries, {
            color: '#26A69A', lineWidth: 1,
            priceScaleId: 'macd',
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // MACD SIGNAL
        macdSigRef.current = chart.addSeries(LineSeries, {
            color: '#FF7043', lineWidth: 1,
            priceScaleId: 'macd',
            crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
        });

        // MACD HISTOGRAM
        macdHistRef.current = chart.addSeries(HistogramSeries, {
            priceScaleId: 'macd',
            lastValueVisible: false, priceLineVisible: false,
        });
        chart.priceScale('macd').applyOptions({ scaleMargins: { top: 0.6, bottom: 0 }, borderVisible: false });

        return () => { chart.remove(); };
    }, []);

    // ── Single unified effect: sync candles to chart AND manage indicator series ──
    useEffect(() => {
        if (!candleSeriesRef.current || candles.length === 0) return;

        // ─ Candlestick series: use setData for full history to keep indicator time alignment correct ─
        candleSeriesRef.current.setData(candles as any);

        if (candles.length < 5) return;

        // ─ Helper ─
        const on = (id: string) => indicators.find(i => i.id === id)?.enabled ?? false;

        // ── Dynamic Subpanels Layout ──
        const rsiOn = on('rsi');
        const macdOn = on('macd');

        let mainBottom = 0.08;
        if (rsiOn && macdOn) {
            mainBottom = 0.45;
            chartRef.current?.priceScale('rsi').applyOptions({ scaleMargins: { top: 0.58, bottom: 0.24 } });
            chartRef.current?.priceScale('macd').applyOptions({ scaleMargins: { top: 0.78, bottom: 0.02 } });
        } else if (rsiOn) {
            mainBottom = 0.25;
            chartRef.current?.priceScale('rsi').applyOptions({ scaleMargins: { top: 0.77, bottom: 0.02 } });
        } else if (macdOn) {
            mainBottom = 0.25;
            chartRef.current?.priceScale('macd').applyOptions({ scaleMargins: { top: 0.77, bottom: 0.02 } });
        }

        // Apply to main chart scale: ends strictly 20% before the volume area
        chartRef.current?.priceScale('right').applyOptions({
            scaleMargins: { top: 0.05, bottom: mainBottom + 0.20 }
        });

        // Volume gets its own exclusive sub-area at the bottom of the main frame
        chartRef.current?.priceScale('volume').applyOptions({
            scaleMargins: { top: 1 - mainBottom - 0.15, bottom: mainBottom }
        });

        // ─ EMA 20 ─
        if (ema20Ref.current) {
            ema20Ref.current.applyOptions({ visible: on('ema20') });
            if (on('ema20')) ema20Ref.current.setData(calcEMA(candles, 20) as any);
        }

        // ─ EMA 50 ─
        if (ema50Ref.current) {
            ema50Ref.current.applyOptions({ visible: on('ema50') });
            if (on('ema50')) ema50Ref.current.setData(calcEMA(candles, 50) as any);
        }

        // ─ EMA 200 (calcEMA returns [] automatically if < 200 candles, which clears the series) ─
        if (ema200Ref.current) {
            const ema200Data = calcEMA(candles, 200);
            ema200Ref.current.applyOptions({ visible: on('ema200') && ema200Data.length > 0 });
            if (on('ema200')) ema200Ref.current.setData(ema200Data as any);
        }

        // ─ Bollinger Bands ─
        const bbOn = on('bb');
        bbUpperRef.current?.applyOptions({ visible: bbOn });
        bbMidRef.current?.applyOptions({ visible: bbOn });
        bbLowerRef.current?.applyOptions({ visible: bbOn });
        if (bbOn && bbUpperRef.current) {
            const bb = calcBollinger(candles);
            bbUpperRef.current.setData(bb.upper as any);
            bbMidRef.current?.setData(bb.middle as any);
            bbLowerRef.current?.setData(bb.lower as any);
        }

        // ─ Volume ─
        if (volumeRef.current) {
            volumeRef.current.applyOptions({ visible: on('volume') });
            if (on('volume')) {
                volumeRef.current.setData(candles.map(c => ({
                    time: c.time, value: c.volume,
                    color: c.close >= c.open ? 'rgba(0,255,65,0.4)' : 'rgba(255,0,60,0.4)',
                })) as any);
            }
        }

        // ─ RSI (needs 15+ candles) ─
        if (rsiRef.current) {
            rsiRef.current.applyOptions({ visible: on('rsi') });
            if (on('rsi') && candles.length > 15) rsiRef.current.setData(calcRSI(candles) as any);
        }

        // ─ MACD ─
        macdLineRef.current?.applyOptions({ visible: macdOn });
        macdSigRef.current?.applyOptions({ visible: macdOn });
        macdHistRef.current?.applyOptions({ visible: macdOn });
        if (macdOn && macdLineRef.current && candles.length > 35) {
            const macd = calcMACD(candles);
            macdLineRef.current.setData(macd.macdLine as any);
            macdSigRef.current?.setData(macd.signalLine as any);
            macdHistRef.current?.setData(macd.histogram as any);
        }

    }, [candles, indicators]);

    // ── SMC & FVG visualization (Creative Transparent Zones) ──
    const smcSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const fvgSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);

    useEffect(() => {
        if (!chartRef.current || !smcData || candles.length === 0) return;

        const chart = chartRef.current;

        // Limpiar Zonas (Series) del renderizado anterior
        smcSeriesRef.current.forEach(series => {
            try { chart.removeSeries(series); } catch (e) { }
        });
        smcSeriesRef.current = [];

        fvgSeriesRef.current.forEach(series => {
            try { chart.removeSeries(series); } catch (e) { }
        });
        fvgSeriesRef.current = [];

        // Formato para llenar el ancho completo de las velas en pantalla
        const times = candles.map(c => c.time);

        if (isEnabled('smc')) {
            // Zonas Verdes (Soportes - Últimos 2)
            smcData.order_blocks.bullish.slice(-2).forEach(ob => {
                const obSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: ob.bottom },
                    topFillColor1: 'rgba(0, 255, 65, 0.15)',
                    topFillColor2: 'rgba(0, 255, 65, 0.15)',
                    topLineColor: 'rgba(0, 255, 65, 0.6)',
                    bottomFillColor1: 'transparent',
                    bottomFillColor2: 'transparent',
                    bottomLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Solid,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                // Piso (Distal Line - Stop Loss) - Línea Gruesa
                obSeries.createPriceLine({
                    price: ob.bottom,
                    color: 'rgba(0, 255, 65, 0.9)',
                    lineWidth: 2,
                    lineStyle: LineStyle.Solid,
                    axisLabelVisible: false,
                    title: ''
                });

                // Trazar el Alto del bloque a lo largo de todo el horizonte del chart
                const data = times.map(time => ({ time, value: ob.top }));
                obSeries.setData(data as any);
                smcSeriesRef.current.push(obSeries);
            });

            // Zonas Rojas (Resistencias - Últimos 2)
            smcData.order_blocks.bearish.slice(-2).forEach(ob => {
                const obSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: ob.top },
                    bottomFillColor1: 'rgba(255, 0, 60, 0.15)',
                    bottomFillColor2: 'rgba(255, 0, 60, 0.15)',
                    bottomLineColor: 'rgba(255, 0, 60, 0.6)',
                    topFillColor1: 'transparent',
                    topFillColor2: 'transparent',
                    topLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Solid,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                // Techo Superior Duro (Distal Line - Stop Loss) - Línea Gruesa
                obSeries.createPriceLine({
                    price: ob.top,
                    color: 'rgba(255, 0, 60, 0.9)',
                    lineWidth: 2,
                    lineStyle: LineStyle.Solid,
                    axisLabelVisible: false,
                    title: ''
                });

                // Trazar el "piso" de la zona y usar el "Techo" como Base
                const data = times.map(time => ({ time, value: ob.bottom }));
                obSeries.setData(data as any);
                smcSeriesRef.current.push(obSeries);
            });
        }

        if (isEnabled('fvg')) {
            // Zonas de Liquidez (FVG Alcistas - Últimos 2)
            smcData.fvgs.bullish.slice(-2).forEach(fvg => {
                const fvgSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: fvg.bottom },
                    topFillColor1: 'rgba(255, 204, 0, 0.12)', // Dorado translúcido
                    topFillColor2: 'rgba(255, 204, 0, 0.05)',
                    topLineColor: 'rgba(255, 204, 0, 0.6)', // Techo del vacío (Dashed)
                    bottomFillColor1: 'transparent',
                    bottomFillColor2: 'transparent',
                    bottomLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                // Piso del vacío (Dashed)
                fvgSeries.createPriceLine({
                    price: fvg.bottom,
                    color: 'rgba(255, 204, 0, 0.6)',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: false,
                    title: ''
                });

                const data = times.map(time => ({ time, value: fvg.top }));
                fvgSeries.setData(data as any);
                fvgSeriesRef.current.push(fvgSeries);
            });

            // Zonas de Liquidez (FVG Bajistas - Últimos 2)
            smcData.fvgs.bearish.slice(-2).forEach(fvg => {
                const fvgSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: fvg.top },
                    bottomFillColor1: 'rgba(255, 204, 0, 0.12)', // Dorado translúcido
                    bottomFillColor2: 'rgba(255, 204, 0, 0.05)',
                    bottomLineColor: 'rgba(255, 204, 0, 0.6)', // Base del vacío
                    topFillColor1: 'transparent',
                    topFillColor2: 'transparent',
                    topLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                // Techo del vacío (Dashed)
                fvgSeries.createPriceLine({
                    price: fvg.top,
                    color: 'rgba(255, 204, 0, 0.6)',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: false,
                    title: ''
                });

                const data = times.map(time => ({ time, value: fvg.bottom }));
                fvgSeries.setData(data as any);
                fvgSeriesRef.current.push(fvgSeries);
            });
        }

    }, [smcData, indicators, candles]);

    return (
        <div className="w-full h-full relative" ref={chartContainerRef}>
            {!isConnected && (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="w-12 h-12 border-2 border-t-neon-cyan border-r-neon-cyan/50 border-b-transparent border-l-transparent rounded-full animate-spin" />
                    <p className="text-neon-cyan/80 text-xs tracking-[0.2em] mt-4 font-bold">CONECTANDO TELEMETRÍA...</p>
                </div>
            )}
        </div>
    );
}
