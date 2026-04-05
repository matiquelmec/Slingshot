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
    BaselineSeries,
    createSeriesMarkers
} from 'lightweight-charts';
import { useTelemetryStore, CandleData } from '../../store/telemetryStore';
import { useIndicatorsStore } from '../../store/indicatorsStore';

// SMC V4.0 PURO: Se han eliminado los cálculos matemáticos retail (RSI, EMA, MACD, BB)
// El sistema ahora se centra exclusivamente en el flujo de órdenes y liquidez institucional.


// ─── Component ───────────────────────────────────────────────────────────────

export default function TradingChart() {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);

    // Series refs
    const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);

    const sessionSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const killzoneSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);

    const markersSeriesRef = useRef<any>(null);
    const priceLineRef = useRef<any>(null);

    const { candles, isConnected, smcData, liquidityHeatmap, tacticalDecision, sessionData, liquidations, latestPrice } = useTelemetryStore();
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


        // Volume  (uses separate price scale)
        volumeRef.current = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });
        chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, borderVisible: false });


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

        // ─ Sanitización defensiva: Ordenar por tiempo y eliminar duplicados (última línea de defensa) ─
        const sortedCandles = [...candles]
            .sort((a, b) => Number(a.time) - Number(b.time))
            .filter((c, i, arr) => i === 0 || c.time !== arr[i - 1].time);

        candleSeriesRef.current.setData(sortedCandles as any);

        // ─ Helper 🎯 ─
        const on = (id: string) => indicators.find(i => i.id === id)?.enabled ?? false;

        // ── Dynamic Subpanels Layout ──
        let mainBottom = 0.08;

        // Apply to main chart scale: ends strictly 20% before the volume area
        chartRef.current?.priceScale('right').applyOptions({
            scaleMargins: { top: 0.05, bottom: mainBottom + 0.20 }
        });

        // Volume gets its own exclusive sub-area at the bottom of the main frame
        chartRef.current?.priceScale('volume').applyOptions({
            scaleMargins: { top: 1 - mainBottom - 0.15, bottom: mainBottom }
        });

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


    }, [candles, indicators]);

    // ── 🔴 LIVE PRICE LINE v4.3.4: Línea horizontal dinámica del precio actual ──
    useEffect(() => {
        const series = candleSeriesRef.current;
        if (!series || !latestPrice || latestPrice <= 0) return;

        // Eliminar la línea anterior
        if (priceLineRef.current) {
            try { series.removePriceLine(priceLineRef.current); } catch (e) { }
            priceLineRef.current = null;
        }

        // Determinar color: verde si sube vs open de última vela, rojo si baja
        const lastCandle = candles.length > 0 ? candles[candles.length - 1] : null;
        const isUp = lastCandle ? latestPrice >= lastCandle.open : true;

        priceLineRef.current = series.createPriceLine({
            price: latestPrice,
            color: isUp ? 'rgba(0, 255, 65, 0.9)' : 'rgba(255, 0, 60, 0.9)',
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: '',
        });
    }, [latestPrice]);

    // Array de tiempos para alinear la serie a través de todo el gráfico horizontal
    // (useMemo evita recrear innecesariamente)
    const times = React.useMemo(() => candles.map(c => c.time), [candles.length]);
    const candleCount = candles.length;

    // ── SMC & FVG visualization (Creative Transparent Zones) ──
    const smcSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);
    const fvgSeriesRef = useRef<ISeriesApi<'Baseline'>[]>([]);

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
            // Zonas Verdes (Demand/Support OBs)
            smcData.order_blocks.bullish.forEach(ob => {
                const obSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: ob.bottom },
                    topFillColor1: 'rgba(0, 255, 136, 0.50)',
                    topFillColor2: 'rgba(0, 255, 136, 0.15)',
                    topLineColor: 'rgba(0, 255, 136, 1.0)',
                    bottomFillColor1: 'transparent',
                    bottomFillColor2: 'transparent',
                    bottomLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Solid,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                const data = times.filter(t => Number(t) >= ob.time).map(time => ({ time, value: ob.top }));
                obSeries.setData(data as any);
                smcSeriesRef.current.push(obSeries);
            });

            // Zonas Rojas (Supply/Resistance OBs)
            smcData.order_blocks.bearish.forEach(ob => {
                const obSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: ob.top },
                    bottomFillColor1: 'rgba(255, 0, 60, 0.50)',
                    bottomFillColor2: 'rgba(255, 0, 60, 0.15)',
                    bottomLineColor: 'rgba(255, 0, 60, 1.0)',
                    topFillColor1: 'transparent',
                    topFillColor2: 'transparent',
                    topLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Solid,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                const data = times.filter(t => Number(t) >= ob.time).map(time => ({ time, value: ob.bottom }));
                obSeries.setData(data as any);
                smcSeriesRef.current.push(obSeries);
            });
        }

        if (isEnabled('fvg')) {
            // Zonas de Liquidez (FVG Alcistas)
            smcData.fvgs.bullish.forEach(fvg => {
                const fvgSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: fvg.bottom },
                    topFillColor1: 'rgba(255, 204, 0, 0.40)',
                    topFillColor2: 'rgba(255, 204, 0, 0.10)',
                    topLineColor: 'rgba(255, 204, 0, 0.9)',
                    bottomFillColor1: 'transparent',
                    bottomFillColor2: 'transparent',
                    bottomLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                const data = times.filter(t => Number(t) >= fvg.time).map(time => ({ time, value: fvg.top }));
                fvgSeries.setData(data as any);
                fvgSeriesRef.current.push(fvgSeries);
            });

            // Zonas de Liquidez (FVG Bajistas)
            smcData.fvgs.bearish.forEach(fvg => {
                const fvgSeries = chart.addSeries(BaselineSeries, {
                    baseValue: { type: 'price', price: fvg.top },
                    bottomFillColor1: 'rgba(255, 204, 0, 0.40)',
                    bottomFillColor2: 'rgba(255, 204, 0, 0.10)',
                    bottomLineColor: 'rgba(255, 204, 0, 0.9)',
                    topFillColor1: 'transparent',
                    topFillColor2: 'transparent',
                    topLineColor: 'transparent',
                    lineWidth: 1,
                    lineStyle: LineStyle.Dashed,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });

                const data = times.filter(t => Number(t) >= fvg.time).map(time => ({ time, value: fvg.bottom }));
                fvgSeries.setData(data as any);
                fvgSeriesRef.current.push(fvgSeries);
            });
        }
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

    // ── Liquidation Clusters visualization (Rekt Radar) ──
    const liquidationLinesRef = useRef<any[]>([]);

    useEffect(() => {
        if (!chartRef.current || !liquidations || !candleSeriesRef.current) return;

        // Limpiar líneas anteriores
        liquidationLinesRef.current.forEach(line => {
            try { candleSeriesRef.current?.removePriceLine(line); } catch (e) { }
        });
        liquidationLinesRef.current = [];

        if (isEnabled('liquidations')) {
            liquidations.forEach(liq => {
                const isAbove = liq.type === 'SHORT_LIQ';
                const opacity = 0.1 + (liq.strength / 100) * 0.4;
                const color = isAbove ? `rgba(0, 229, 255, ${opacity})` : `rgba(192, 132, 252, ${opacity})`;
                
                const line = candleSeriesRef.current?.createPriceLine({
                    price: liq.price,
                    color: color,
                    lineWidth: Math.max(1, Math.floor(liq.strength / 20)) as any,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: `REKT ${liq.leverage}x ${isAbove ? '▲' : '▼'}`,
                });
                if (line) liquidationLinesRef.current.push(line);
            });
        }
    }, [liquidations, indicators]);

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


        // ── Niveles de Sesión (Session Brackets Históricos v3) ─────────────────
        const chart = chartRef.current;
        if (!chart) return;

        // Limpiar Brackets anteriores
        sessionSeriesRef.current.forEach(s => { try { chart.removeSeries(s); } catch(e){} });
        sessionSeriesRef.current = [];
        killzoneSeriesRef.current.forEach(s => { try { chart.removeSeries(s); } catch(e){} });
        killzoneSeriesRef.current = [];

        if (sessionData && sessionData.sessions && isEnabled('session')) {
            const { sessions } = sessionData;

            // Valores ajustados a petición del comandante: Cajas muy opacas y marcadas (bg 0.25, kz 0.40).
            const sessionColors: Record<string, { color: string; bg: string; kz: string }> = {
                asia:   { color: 'rgba(251,146,60,0.8)', bg: 'rgba(251,146,60,0.25)', kz: 'rgba(251,146,60,0.40)' },
                london: { color: 'rgba(96,165,250,0.8)', bg: 'rgba(96,165,250,0.25)', kz: 'rgba(96,165,250,0.40)' },
                ny:     { color: 'rgba(192,132,252,0.8)', bg: 'rgba(192,132,252,0.25)', kz: 'rgba(192,132,252,0.40)' },
            };

            // Sanitización de velas
            const sorted = [...candles]
                .sort((a, b) => Number(a.time) - Number(b.time))
                .filter((c, i, arr) => i === 0 || c.time !== arr[i - 1].time);

            // 1. PDH / PDL (Maestras del día actual)
            const { pdh, pdl } = sessionData;
            addLine(pdh, 'rgba(0, 255, 255, 0.3)', 'PDH', LineStyle.Dashed, 1);
            addLine(pdl, 'rgba(0, 255, 255, 0.3)', 'PDL', LineStyle.Dashed, 1);

            if (sorted.length === 0) return;

            // 2. Trazar Cajas Perfectas Históricas
            Object.entries(sessions).forEach(([id, info]: [string, any]) => {
                if (info.start_utc == null || info.end_utc == null) return;

                let currentBlock: any[] = [];
                const blocks: any[][] = [];

                // Agrupamos consecutivamente las velas que rebotan dentro del rango horario
                for (let i = 0; i < sorted.length; i++) {
                    const c = sorted[i];
                    const h = new Date(Number(c.time) * 1000).getUTCHours();
                    
                    let inside = false;
                    if (info.start_utc < info.end_utc) {
                        inside = h >= info.start_utc && h < info.end_utc;
                    } else { // medianoche (ej: 22 a 06)
                        inside = h >= info.start_utc || h < info.end_utc;
                    }

                    if (inside) {
                        currentBlock.push(c);
                    } else {
                        if (currentBlock.length > 0) {
                            blocks.push(currentBlock);
                            currentBlock = [];
                        }
                    }
                }
                if (currentBlock.length > 0) blocks.push(currentBlock);

                // Instanciar un Baseline de Lightweight-Charts por cada iteración del bloque (todos los días del historial 1000 limit)
                blocks.forEach((blockCandles) => {
                    if (blockCandles.length < 2) return; // evitar cajas de un solo tick
                    
                    const blockHigh = Math.max(...blockCandles.map(c => c.high));
                    const blockLow  = Math.min(...blockCandles.map(c => c.low));

                    // Bracket de Sesión Principal
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

                    bracket.setData(blockCandles.map(c => ({ time: c.time, value: blockHigh })) as any);
                    sessionSeriesRef.current.push(bracket);

                    // 3. Replicar iluminación dinámica para Killzone (Asia, London y NY)
                    // (Los algoritmos SMC definen el Killzone Asiático en sus primeras 4 horas, London/NY en sus primeras 3)
                    const kzHours = id === 'asia' ? 4 : 3;
                    const kzStart = info.start_utc;
                    const kzEnd   = (info.start_utc + kzHours) % 24;
                    const kzCandles = blockCandles.filter(c => {
                        const hh = new Date(Number(c.time) * 1000).getUTCHours();
                        if (kzStart < kzEnd) return hh >= kzStart && hh < kzEnd;
                        return hh >= kzStart || hh < kzEnd;
                    });

                    if (kzCandles.length > 0) {
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
                        kzGlow.setData(kzCandles.map(c => ({ time: c.time, value: blockHigh })) as any);
                        killzoneSeriesRef.current.push(kzGlow);
                    }
                });
            });
        }

        if (isEnabled('fibonacci') && tacticalDecision?.fibonacci) {
            const { levels, swing_high, swing_low } = tacticalDecision.fibonacci;
            const isUptrend = (swing_low ?? 0) < (swing_high ?? 0);

            Object.entries(levels).forEach(([label, price]) => {
                const p = price as number;
                // ── Golden Pocket (0.618 – 0.66): Cian institucional brillante ──
                if (label === '0.618') {
                    addLine(p, 'rgba(0, 229, 255, 1.0)', `0.618 ★GP`, LineStyle.Solid, 2);
                }
                else if (label === '0.66') {
                    addLine(p, 'rgba(0, 229, 255, 0.7)', `0.66  ★GP`, LineStyle.Dashed, 2);
                }
                // ── Extremos de la pierna ──────────────────────────────────────
                else if (label === '0.0') {
                    addLine(p, 'rgba(255,255,255,0.8)', isUptrend ? `Swing High` : `Swing Low`, LineStyle.Solid, 2);
                }
                else if (label === '1.0') {
                    addLine(p, 'rgba(255,255,255,0.8)', isUptrend ? `Swing Low` : `Swing High`, LineStyle.Solid, 2);
                }
                // ── 0.786: zona roja de invalidación ──────────────────────────
                else if (label === '0.786') {
                    addLine(p, 'rgba(255,80,80,0.6)', `Fib 0.786`, LineStyle.Dotted, 1);
                }
                // ── Niveles intermedios ────────────────────────────────────────
                else {
                    addLine(p, 'rgba(255,255,255,0.4)', `Fib ${label}`, LineStyle.Dashed, 1);
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

            {/* Session Legend Overlay */}
            {isEnabled('session') && sessionData && (
                <div className="absolute top-4 right-16 z-20 pointer-events-none bg-[#050B14]/80 backdrop-blur-md border border-white/10 rounded-lg p-3 max-w-[200px] shadow-2xl">
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
        </div>
    );
}
