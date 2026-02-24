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

    const { candles, isConnected, smcData, liquidityHeatmap, tacticalDecision, sessionData } = useTelemetryStore();
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
        if (candles.length === 0) {
            candleSeriesRef.current.setData([]);
            return;
        }

        // Sanitización defensiva: Ordenar por tiempo y eliminar duplicados (última línea de defensa)
        const sortedCandles = [...candles]
            .sort((a, b) => Number(a.time) - Number(b.time))
            .filter((c, i, arr) => i === 0 || c.time !== arr[i - 1].time);

        candleSeriesRef.current.setData(sortedCandles as any);

        if (sortedCandles.length < 5) return;

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

    // Array de tiempos para alinear la serie a través de todo el gráfico horizontal
    // (useMemo evita recrear innecesariamente)
    const times = React.useMemo(() => candles.map(c => c.time), [candles.length]);
    const candleCount = candles.length;

    useEffect(() => {
        if (!chartRef.current || !smcData || times.length === 0) return;

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

        if (isEnabled('smc')) {
            // Zonas Verdes (Demand/Support - Activos sin mitigar)
            smcData.order_blocks.bullish.forEach(ob => {
                const obSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: ob.bottom },
                    topFillColor1: 'rgba(0, 255, 136, 0.20)', // Más opaco según preferencia
                    topFillColor2: 'rgba(0, 255, 136, 0.15)',
                    topLineColor: 'rgba(0, 255, 136, 0.7)',
                    bottomFillColor1: 'transparent',
                    bottomFillColor2: 'transparent',
                    bottomLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Solid,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                // Trazar el Alto del bloque a lo largo del horizonte futuro
                const data = times.filter(t => Number(t) >= ob.time).map(time => ({ time, value: ob.top }));
                obSeries.setData(data as any);
                smcSeriesRef.current.push(obSeries);
            });

            // Zonas Rojas (Resistencias - Activos sin mitigar)
            smcData.order_blocks.bearish.forEach(ob => {
                const obSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: ob.top },
                    bottomFillColor1: 'rgba(255, 0, 60, 0.20)', // Más opaco según preferencia
                    bottomFillColor2: 'rgba(255, 0, 60, 0.15)',
                    bottomLineColor: 'rgba(255, 0, 60, 0.7)',
                    topFillColor1: 'transparent',
                    topFillColor2: 'transparent',
                    topLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Solid,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                // Trazar el "piso" de la zona hacia la derecha
                const data = times.filter(t => Number(t) >= ob.time).map(time => ({ time, value: ob.bottom }));
                obSeries.setData(data as any);
                smcSeriesRef.current.push(obSeries);
            });
        }

        if (isEnabled('fvg')) {
            // Zonas de Liquidez (FVG Alcistas - Activos sin mitigar)
            smcData.fvgs.bullish.forEach(fvg => {
                const fvgSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: fvg.bottom },
                    topFillColor1: 'rgba(255, 204, 0, 0.15)', // Dorado más intenso
                    topFillColor2: 'rgba(255, 204, 0, 0.10)',
                    topLineColor: 'rgba(255, 204, 0, 0.6)',
                    bottomFillColor1: 'transparent',
                    bottomFillColor2: 'transparent',
                    bottomLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dotted,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                const data = times.filter(t => Number(t) >= fvg.time).map(time => ({ time, value: fvg.top }));
                fvgSeries.setData(data as any);
                fvgSeriesRef.current.push(fvgSeries);
            });

            // Zonas de Liquidez (FVG Bajistas - Activos sin mitigar)
            smcData.fvgs.bearish.forEach(fvg => {
                const fvgSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: fvg.top },
                    bottomFillColor1: 'rgba(255, 204, 0, 0.15)', // Dorado más intenso
                    bottomFillColor2: 'rgba(255, 204, 0, 0.10)',
                    bottomLineColor: 'rgba(255, 204, 0, 0.6)',
                    topFillColor1: 'transparent',
                    topFillColor2: 'transparent',
                    topLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dotted,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                const data = times.filter(t => Number(t) >= fvg.time).map(time => ({ time, value: fvg.bottom }));
                fvgSeries.setData(data as any);
                fvgSeriesRef.current.push(fvgSeries);
            });
        }

        // El truco de rendimiento: depender de 'candleCount' y 'smcData', NO de 'candles'.
        // Esto previene que react borre y recree las 8 zonas en CADA TICK inter-vela.
    }, [smcData, indicators, candleCount]);

    // ── Liquidity Heatmap visualization (Order Book Depth) ──
    const liquidityLinesRef = useRef<any[]>([]);

    useEffect(() => {
        if (!chartRef.current || !liquidityHeatmap || !candleSeriesRef.current || times.length === 0) return;

        // Limpiar líneas de liquidez anteriores
        liquidityLinesRef.current.forEach(line => {
            try { candleSeriesRef.current?.removePriceLine(line); } catch (e) { }
        });
        liquidityLinesRef.current = [];

        // Función auxiliar para normalizar el volumen y calcular opacidad
        const maxBidVol = Math.max(...liquidityHeatmap.bids.map(b => b.volume), 1);
        const maxAskVol = Math.max(...liquidityHeatmap.asks.map(a => a.volume), 1);

        // Bids (Soportes en verde)
        liquidityHeatmap.bids.forEach(bid => {
            const intensity = 0.1 + (0.3 * (bid.volume / maxBidVol)); // Opacidad muy sutil
            const line = candleSeriesRef.current?.createPriceLine({
                price: bid.price,
                color: `rgba(0, 255, 65, ${intensity})`,
                lineWidth: 1, // Línea fina
                lineStyle: LineStyle.Solid,
                axisLabelVisible: false, // Ocultar etiqueta en el eje Y para no molestar
                title: `BID: ${bid.volume.toFixed(2)} Vol`
            });
            if (line) liquidityLinesRef.current.push(line);
        });

        // Asks (Resistencias en rojo)
        liquidityHeatmap.asks.forEach(ask => {
            const intensity = 0.1 + (0.3 * (ask.volume / maxAskVol)); // Opacidad muy sutil
            const line = candleSeriesRef.current?.createPriceLine({
                price: ask.price,
                color: `rgba(255, 0, 60, ${intensity})`,
                lineWidth: 1, // Línea fina
                lineStyle: LineStyle.Solid,
                axisLabelVisible: false, // Ocultar etiqueta en el eje Y
                title: `ASK: ${ask.volume.toFixed(2)} Vol`
            });
            if (line) liquidityLinesRef.current.push(line);
        });

    }, [liquidityHeatmap, indicators]);

    // ── S/R High-Touch + Niveles de Sesión ───────────────────────────────────
    const srLinesRef = useRef<{ line: any; series: any }[]>([]);

    useEffect(() => {
        const series = candleSeriesRef.current;
        if (!chartRef.current || !series) return;

        // Limpiar con la referencia exacta de la serie que creó cada línea
        srLinesRef.current.forEach(({ line, series: s }) => {
            try { s?.removePriceLine(line); } catch (e) { }
        });
        srLinesRef.current = [];

        const addLine = (price: number | null | undefined, color: string, title: string, style: number, width: number = 1) => {
            if (!price || !series) return;
            const line = series.createPriceLine({
                price, color, lineWidth: width as any, lineStyle: style,
                axisLabelVisible: true, title
            });
            if (line) srLinesRef.current.push({ line, series });
        };

        if (isEnabled('sr')) {
            // ── Key Levels (High-Touch + MTF + Volume) ─────────────────────────
            const touchesToWidth = (lvl: any): number =>
                lvl.mtf_confluence ? 4 : (lvl.ob_confluence ? 3 : lvl.touches >= 4 ? 3 : lvl.touches >= 2 ? 2 : 1);

            const touchesToAlpha = (t: number, mtf: boolean): string =>
                mtf ? '1.0' : t >= 4 ? '0.9' : t >= 2 ? '0.7' : '0.4';

            const getLevelColor = (lvl: { type: string; origin: string }, alpha: string): string => {
                if (lvl.type === 'RESISTANCE') {
                    return lvl.origin === 'ROLE_REVERSAL'
                        ? `rgba(251,146,60,${alpha})`   // naranja
                        : `rgba(255,0,60,${alpha})`;    // rojo
                } else {
                    return lvl.origin === 'ROLE_REVERSAL'
                        ? `rgba(250,204,21,${alpha})`   // amarillo
                        : `rgba(0,255,65,${alpha})`;    // verde
                }
            };

            const { resistances, supports } = tacticalDecision.key_levels;

            // Renderizar Resistencias
            resistances.forEach((r, i) => {
                const rank = i + 1;
                const alpha = touchesToAlpha(r.touches, r.mtf_confluence ?? false);
                const w = touchesToWidth(r);
                const color = getLevelColor(r, alpha);

                // Iconos de poder
                const mtfTag = r.mtf_confluence ? '◈' : ''; // Rombo para MTF (Institucional)
                const obTag = r.ob_confluence ? '★' : '';
                const volTag = (r.volume_score ?? 1) > 1.5 ? '⚡' : '';
                const typeTag = r.origin === 'ROLE_REVERSAL' ? '↩' : '▲';

                const label = `R${rank}${mtfTag}${obTag}${volTag}${typeTag}(${r.touches}t)`;
                // Niveles MTF Mayor son SÓLIDOS. R1 intraday es DASHED. Otros son DOTTED.
                const style = r.mtf_confluence ? LineStyle.Solid : (rank === 1 ? LineStyle.Dashed : LineStyle.Dotted);

                addLine(r.price, color, label, style, w);
            });

            // Renderizar Soportes
            supports.forEach((s, i) => {
                const rank = i + 1;
                const alpha = touchesToAlpha(s.touches, s.mtf_confluence ?? false);
                const w = touchesToWidth(s);
                const color = getLevelColor(s, alpha);

                const mtfTag = s.mtf_confluence ? '◈' : '';
                const obTag = s.ob_confluence ? '★' : '';
                const volTag = (s.volume_score ?? 1) > 1.5 ? '⚡' : '';
                const typeTag = s.origin === 'ROLE_REVERSAL' ? '↩' : '▼';

                const label = `S${rank}${mtfTag}${obTag}${volTag}${typeTag}(${s.touches}t)`;
                const style = s.mtf_confluence ? LineStyle.Solid : (rank === 1 ? LineStyle.Dashed : LineStyle.Dotted);

                addLine(s.price, color, label, style, w);
            });
        }


        // ── Niveles de Sesión ───────────────────────────────────────────────
        if (sessionData) {
            const { sessions, pdh, pdl } = sessionData;
            addLine(pdh, 'rgba(255,255,255,0.55)', 'PDH', LineStyle.LargeDashed);
            addLine(pdl, 'rgba(255,255,255,0.55)', 'PDL', LineStyle.LargeDashed);
            addLine(sessions.asia.high, 'rgba(251,146,60,0.7)', 'Asia H', LineStyle.Dotted);
            addLine(sessions.asia.low, 'rgba(251,146,60,0.7)', 'Asia L', LineStyle.Dotted);
            addLine(sessions.london.high, 'rgba(96,165,250,0.7)', 'Lon H', LineStyle.Dotted);
            addLine(sessions.london.low, 'rgba(96,165,250,0.7)', 'Lon L', LineStyle.Dotted);
        }

        // ── Fibonacci (Autofib) ─────────────────────────────────────────────
        if (isEnabled('fibonacci') && tacticalDecision?.fibonacci) {
            const { levels } = tacticalDecision.fibonacci;
            Object.entries(levels).forEach(([label, price]) => {
                // Golden Pocket (0.618 - 0.66)
                if (label === '0.618' || label === '0.66') {
                    addLine(price, 'rgba(0, 229, 255, 0.9)', `Fib ${label} 🌟`, LineStyle.Solid, 2);
                }
                // Extremos (0 y 1)
                else if (label === '0.0' || label === '1.0') {
                    addLine(price, 'rgba(255,255,255,0.8)', `Fib ${label}`, LineStyle.Solid, 2);
                }
                // Niveles intermedios clásicos
                else {
                    addLine(price, 'rgba(255,255,255,0.4)', `Fib ${label}`, LineStyle.Dashed, 1);
                }
            });
        }
    }, [tacticalDecision, sessionData, indicators]);

    return (
        <div className="w-full h-full relative" ref={chartContainerRef}>
            {!isConnected && (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="w-12 h-12 border-2 border-t-neon-cyan border-r-neon-cyan/50 border-b-transparent border-l-transparent rounded-full animate-spin" />
                    <p className="text-neon-cyan/80 text-xs tracking-[0.2em] mt-4 font-bold">CONECTANDO TELEMETRÍA...</p>
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
                        <li className="flex items-start gap-1">
                            <span className="text-white font-mono mt-0.5 w-8">▲, ▼</span>
                            <span>Soporte/Resistencia convencional.</span>
                        </li>
                        <li className="flex items-start gap-1">
                            <span className="text-white font-mono mt-0.5 w-8">↩</span>
                            <span><span className="text-yellow-400 font-bold">Role Reversal:</span> S/R roto que se invierte (Soporte pasa a Resistencia o viceversa).</span>
                        </li>
                        <li className="flex items-start gap-1">
                            <span className="text-white font-mono mt-0.5 w-8">(Nt)</span>
                            <span>Toques (Ej: 3t = 3 Toques). Mide la validación estructural.</span>
                        </li>
                        <li className="flex items-start gap-1">
                            <span className="text-white font-mono mt-0.5 w-8">⚡</span>
                            <span><span className="text-neon-cyan font-bold">Volumen:</span> Nivel con inyección de capital anómala (&gt;1.5x score).</span>
                        </li>
                        <li className="flex items-start gap-1">
                            <span className="text-white font-mono mt-0.5 w-8">◈</span>
                            <span><span className="text-purple-400 font-bold">MTF:</span> Confluencia con temporalidad pesada (4H/1D). <span className="text-white/80 underline decoration-purple-400/50">Líneas Sólidas</span>.</span>
                        </li>
                        <li className="flex items-start gap-1">
                            <span className="text-white font-mono mt-0.5 w-8">★</span>
                            <span>OB Confluencia: Nivel solapado con un Order Block activo.</span>
                        </li>
                    </ul>
                </div>
            )}
        </div>
    );
}
