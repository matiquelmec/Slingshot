'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Target, Compass, AlertTriangle, ArrowUpRight, ArrowDownRight, Award, Cpu, ChevronDown, ChevronUp, ShieldAlert, Sparkles, Copy, Check } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';
import { formatCurrency } from '../../utils/formatters';

interface AssetSetup {
    symbol: string;
    displayName: string;
    icon: string;
    refPrice: number;
    refEntry: number;
    refSL: number;
    refTP1: number;
    refTP2: number;
    regime: 'MARKUP' | 'MARKDOWN' | 'ACCUMULATION' | 'DISTRIBUTION' | 'CHOPPY' | 'RANGING';
    regimeLabel: string;
    strategy: string;
    reasonEntry: string;
    reasonSL: string;
    reasonTP1: string;
    reasonTP2: string;
    isLong: boolean;
}

const SETUPS_TEMPLATE: AssetSetup[] = [
    {
        symbol: 'BTCUSDT',
        displayName: 'Bitcoin (BTC-USD)',
        icon: '🪙',
        refPrice: 60252,
        refEntry: 63100,
        refSL: 65850,
        refTP1: 58200,
        refTP2: 54500,
        regime: 'MARKDOWN',
        regimeLabel: 'Bajista (MARKDOWN)',
        strategy: 'Short en Retroceso (Seguimiento de Tendencia)',
        reasonEntry: 'Zona de confluencia del FVG bajista diario y el inicio del Bearish OB.',
        reasonSL: 'Por encima de la resistencia del bloque de órdenes en $65,544.',
        reasonTP1: 'Cerca del soporte de 60 días.',
        reasonTP2: 'Zona de liquidación masiva de longs de 10x.',
        isLong: false
    },
    {
        symbol: 'ETHUSDT',
        displayName: 'Ethereum (ETH-USD)',
        icon: '🔱',
        refPrice: 2650,
        refEntry: 2580,
        refSL: 2490,
        refTP1: 2780,
        refTP2: 2950,
        regime: 'ACCUMULATION',
        regimeLabel: 'Acumulación OTE',
        strategy: 'Long en Golden Pocket (Descuento Institucional)',
        reasonEntry: 'Bloque de órdenes alcista de 15m con confluencia Fibonacci 61.8%-78.6%.',
        reasonSL: 'Invalidación por debajo del mínimo de la sesión de Londres.',
        reasonTP1: 'Liquidez BSL previa en máximos del día anterior.',
        reasonTP2: 'Imbalance FVG de 4h.',
        isLong: true
    },
    {
        symbol: 'INJUSDT',
        displayName: 'Injective (INJ-USD)',
        icon: '🚀',
        refPrice: 22.50,
        refEntry: 21.80,
        refSL: 20.90,
        refTP1: 23.90,
        refTP2: 26.20,
        regime: 'MARKUP',
        regimeLabel: 'Expansión Impulsiva',
        strategy: 'Long Sniper en Ruptura BOS + Retesteo OB',
        reasonEntry: 'Retesteo al Bullish Order Block tras rotura de estructura BOS limpia.',
        reasonSL: 'Por debajo del origen del impulso institucional.',
        reasonTP1: 'Toma de liquidez de máximos asiáticos.',
        reasonTP2: 'Expansión 3.0R hacia resistencia macro.',
        isLong: true
    },
    {
        symbol: 'SUIUSDT',
        displayName: 'Sui Network (SUI-USD)',
        icon: '💧',
        refPrice: 1.85,
        refEntry: 1.78,
        refSL: 1.71,
        refTP1: 1.96,
        refTP2: 2.15,
        regime: 'MARKUP',
        regimeLabel: 'Tendencia Alcista Fuerte',
        strategy: 'Long en FVG de Continuación',
        reasonEntry: 'Llenado de ineficiencia FVG de 15m durante la Killzone de Nueva York.',
        reasonSL: 'Por debajo del mínimo de la vela de impulso.',
        reasonTP1: 'Primer objetivo de cobertura 1.5R.',
        reasonTP2: 'Objetivo de liquidez abierta.',
        isLong: true
    },
    {
        symbol: 'AVAXUSDT',
        displayName: 'Avalanche (AVAX-USD)',
        icon: '🔺',
        refPrice: 24.80,
        refEntry: 24.10,
        refSL: 23.30,
        refTP1: 26.10,
        refTP2: 28.00,
        regime: 'ACCUMULATION',
        regimeLabel: 'Acumulación en Soporte',
        strategy: 'Long en Barrido de Liquidez SSL',
        reasonEntry: 'Caza de stops por debajo de soporte local antes del rebote.',
        reasonSL: 'Invalidación estructural bajo el rango.',
        reasonTP1: 'Mitigación del bloque contrario.',
        reasonTP2: 'Zona OTE de expansión.',
        isLong: true
    },
    {
        symbol: 'RENDERUSDT',
        displayName: 'Render (RENDER-USD)',
        icon: '🎨',
        refPrice: 5.60,
        refEntry: 5.42,
        refSL: 5.18,
        refTP1: 6.05,
        refTP2: 6.70,
        regime: 'MARKUP',
        regimeLabel: 'Markup Institucional',
        strategy: 'Long en FVG + RVOL 2.0x',
        reasonEntry: 'Entrada en descuento OTE tras confirmación de volumen relativo alto.',
        reasonSL: 'Protección bajo el pivote de 1h.',
        reasonTP1: 'Resistencia estructural 1.',
        reasonTP2: 'Proyección 3.2R de Fibonacci.',
        isLong: true
    },
    {
        symbol: 'NEARUSDT',
        displayName: 'Near Protocol (NEAR-USD)',
        icon: '🌐',
        refPrice: 4.20,
        refEntry: 4.05,
        refSL: 3.88,
        refTP1: 4.52,
        refTP2: 4.95,
        regime: 'ACCUMULATION',
        regimeLabel: 'Rango de Acumulación',
        strategy: 'Long en Bloque de Demanda',
        reasonEntry: 'Order Block alcista de 4h retesteado en sesión de Londres.',
        reasonSL: 'Invalidación bajo el mínimo de demanda.',
        reasonTP1: 'Equilibrio de rango.',
        reasonTP2: 'Máximo del rango.',
        isLong: true
    },
    {
        symbol: 'FETUSDT',
        displayName: 'Artificial Superintelligence (FET-USD)',
        icon: '🤖',
        refPrice: 1.15,
        refEntry: 1.09,
        refSL: 1.03,
        refTP1: 1.24,
        refTP2: 1.38,
        regime: 'MARKUP',
        regimeLabel: 'Impulso de Inteligencia',
        strategy: 'Long en Continuación de Tendencia',
        reasonEntry: 'Confluencia de EMA 200 y FVG de 15m.',
        reasonSL: 'Bajo la media móvil institucional.',
        reasonTP1: 'Barrido de liquidez de compras.',
        reasonTP2: 'Extensión de Fibonacci 1.618.',
        isLong: true
    },
    {
        symbol: 'ATOMUSDT',
        displayName: 'Cosmos (ATOM-USD)',
        icon: '⚛️',
        refPrice: 4.85,
        refEntry: 4.68,
        refSL: 4.52,
        refTP1: 5.10,
        refTP2: 5.50,
        regime: 'RANGING',
        regimeLabel: 'Rango Limpio',
        strategy: 'Long en Soporte de Rango',
        reasonEntry: 'Rebote en el piso del canal con divergencia alcista en delta.',
        reasonSL: 'Bajo el piso del rango.',
        reasonTP1: 'Punto medio del canal (POC).',
        reasonTP2: 'Techo del canal.',
        isLong: true
    },
    {
        symbol: 'TIAUSDT',
        displayName: 'Celestia (TIA-USD)',
        icon: '✨',
        refPrice: 5.10,
        refEntry: 4.90,
        refSL: 4.68,
        refTP1: 5.45,
        refTP2: 6.00,
        regime: 'ACCUMULATION',
        regimeLabel: 'Acumulación de Fondo',
        strategy: 'Long en Retroceso OTE 70.5%',
        reasonEntry: 'Zona OTE perfecta en Celestia tras barrido asiático.',
        reasonSL: 'Bajo el swing low.',
        reasonTP1: 'Máximo del día.',
        reasonTP2: 'Resistencia mayor.',
        isLong: true
    }
];

const REGIME_META: Record<string, { color: string; bg: string; glow: string; label: string }> = {
    MARKUP:       { color: 'text-neon-green', bg: 'bg-neon-green/10 border-neon-green/30', glow: 'rgba(0,255,65,0.25)', label: 'MARKUP ↗' },
    MARKDOWN:     { color: 'text-neon-red',   bg: 'bg-neon-red/10 border-neon-red/30',     glow: 'rgba(255,0,60,0.25)', label: 'MARKDOWN ↘' },
    ACCUMULATION: { color: 'text-yellow-400', bg: 'bg-yellow-400/10 border-yellow-400/30', glow: 'rgba(250,204,21,0.25)', label: 'ACUMULACIÓN' },
    DISTRIBUTION: { color: 'text-orange-400', bg: 'bg-orange-400/10 border-orange-400/30', glow: 'rgba(251,146,60,0.25)', label: 'DISTRIBUCIÓN' },
    RANGING:      { color: 'text-neon-cyan',  bg: 'bg-neon-cyan/10 border-neon-cyan/30',   glow: 'rgba(0,229,255,0.25)', label: 'RANGING' },
    CHOPPY:       { color: 'text-purple-400', bg: 'bg-purple-400/10 border-purple-400/30', glow: 'rgba(192,132,252,0.25)', label: 'CHOPPY' },
    TRANSITION:   { color: 'text-yellow-400', bg: 'bg-yellow-400/10 border-yellow-400/30', glow: 'rgba(250,204,21,0.25)', label: 'TRANSICIÓN ⇄' },
    UNKNOWN:      { color: 'text-white/60',   bg: 'bg-white/5 border-white/10',            glow: 'rgba(255,255,255,0.1)',  label: 'UNKNOWN' },
};

export default function PlanOperativoPanel() {
    const { latestPrices, marketSummary, smcData, liquidations, activeSymbol, sessionData, connectionStatus, connect } = useTelemetryStore();
    const [expandedAsset, setExpandedAsset] = useState<string | null>('BTCUSDT');
    const [copiedId, setCopiedId] = useState<string | null>(null);

    const handleCopy = (value: number | string, id: string) => {
        navigator.clipboard.writeText(value.toString());
        setCopiedId(id);
        setTimeout(() => {
            setCopiedId(null);
        }, 1500);
    };

    // [NIVEL INSTITUCIONAL v12.4] Dos vías de Sincronía: Asegura que el acordeón y el store estén siempre alineados
    useEffect(() => {
        if (activeSymbol) {
            setExpandedAsset(activeSymbol);
        }
    }, [activeSymbol]);

    // [NIVEL INSTITUCIONAL v12.1] Sincronización de Reloj de Sesiones y Killzones del Servidor
    const timeInfo = useMemo(() => {
        const d = new Date();
        const utcDay = d.getUTCDay();
        const utcHour = d.getUTCHours();
        
        const days = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
        const dayName = days[utcDay];
        
        let dayStatus: 'HIGH' | 'MED' | 'LOW' = 'MED';
        let dayReason = '';
        
        if (utcDay >= 2 && utcDay <= 4) { // Martes, Miércoles, Jueves
            dayStatus = 'HIGH';
            dayReason = 'Día de alta probabilidad. Mayor participación de mercado institucional y expansión limpia de tendencia.';
        } else if (utcDay === 1) { // Lunes
            dayStatus = 'MED';
            dayReason = 'Lunes de establecimiento. Evitar operar antes de que se defina el rango inicial semanal.';
        } else if (utcDay === 5) { // Viernes
            dayStatus = 'MED';
            dayReason = 'Cierre semanal. Asegurar ganancias temprano y evitar tomar trades al final de la sesión.';
        } else { // Sábado, Domingo
            dayStatus = 'LOW';
            dayReason = 'Fin de semana. Sin volumen real. Volatilidad artificial por bots minoristas. Riesgo de manipulación alto.';
        }

        // Determinar sesiones activas en UTC
        let sessionName = 'DEAD ZONE (INACTIVO)';
        let isKillzone = false;
        
        if (utcHour >= 7 && utcHour <= 10) {
            sessionName = 'LONDON OPEN KILLZONE';
            isKillzone = true;
        } else if (utcHour >= 12 && utcHour <= 15) {
            sessionName = 'NEW YORK OPEN KILLZONE';
            isKillzone = true;
        } else if (utcHour >= 0 && utcHour <= 4) {
            sessionName = 'ASIA SESSION (SWEEP WINDOW)';
            isKillzone = false;
        }

        return { dayName, dayStatus, dayReason, sessionName, isKillzone };
    }, []);

    const currentSessionName = useMemo(() => {
        if (!sessionData?.current_session) return timeInfo.sessionName;
        const name = sessionData.current_session.toUpperCase();
        if (name === 'NEW_YORK') return 'NEW YORK SESSION';
        if (name === 'LONDON') return 'LONDON SESSION';
        if (name === 'ASIA') return 'ASIA SESSION';
        if (name === 'OFF_HOURS') return 'DEAD ZONE (INACTIVO)';
        return `${name.replace('_', ' ')} SESSION`;
    }, [sessionData?.current_session, timeInfo.sessionName]);

    const isKillzoneActive = sessionData?.is_killzone !== undefined
        ? sessionData.is_killzone
        : timeInfo.isKillzone;
        
    const dayLabel = useMemo(() => {
        if (!sessionData?.trading_day) return timeInfo.dayName;
        const day = sessionData.trading_day.toLowerCase();
        const daysMap: Record<string, string> = {
            monday: 'Lunes',
            tuesday: 'Martes',
            wednesday: 'Miércoles',
            thursday: 'Jueves',
            friday: 'Viernes',
            saturday: 'Sábado',
            sunday: 'Domingo'
        };
        return daysMap[day] || sessionData.trading_day;
    }, [sessionData?.trading_day, timeInfo.dayName]);

    const toggleAsset = (symbol: string) => {
        const nextAsset = expandedAsset === symbol ? null : symbol;
        setExpandedAsset(nextAsset);
        if (nextAsset) {
            // [NIVEL INSTITUCIONAL v12.3] Conexión atómica: Sincronizar WebSocket con la moneda expandida
            connect(symbol);
        }
    };

    return (
        <div className="flex flex-col h-full overflow-hidden bg-black/20 font-mono">
            {/* Header */}
            <div className="p-4 border-b border-white/5 flex items-center bg-gradient-to-r from-neon-cyan/15 to-transparent">
                <div className="flex items-center gap-2.5 pr-44">
                    <Compass size={16} className="text-neon-cyan animate-spin-slow" />
                    <div className="flex items-center gap-2">
                        <h2 className="text-xs font-bold text-white/90 tracking-widest drop-shadow-[0_0_8px_rgba(0,229,255,0.4)]">
                            PLAN OPERATIVO
                        </h2>
                        <span className="text-[8.5px] font-mono text-neon-cyan bg-neon-cyan/10 border border-neon-cyan/25 px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                            📋 HOJA DE RUTA TÁCTICA 1-CLICK
                        </span>
                    </div>
                </div>
            </div>

            {connectionStatus !== 'CONNECTED' && (
                <div className="mx-3 mt-3 p-2 bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-[8.5px] rounded-lg flex items-center gap-2 font-mono">
                    <AlertTriangle size={12} className="shrink-0 animate-pulse text-yellow-400" />
                    <span>
                        <strong>MODO OFFLINE:</strong> El motor backend no está conectado (Status: {connectionStatus}). Mostrando plantillas de referencia estáticas.
                    </span>
                </div>
            )}

            {/* List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3">
                
                {/* Accordion List */}
                <div className="space-y-2">
                    {SETUPS_TEMPLATE.map((setup) => {
                        // Buscar precio en vivo o fallback
                        const livePrice = latestPrices[setup.symbol] || latestPrices[setup.symbol.replace('USDT', '')] || setup.refPrice;
                        const isExpanded = expandedAsset === setup.symbol;
                        
                        // [NIVEL INSTITUCIONAL v12.5] Dirección Dinámica basada en el Régimen del Radar
                        const liveRegime = marketSummary[setup.symbol]?.regime || setup.regime;
                        const isLong = (() => {
                            if (['MARKUP', 'BULLISH_TREND', 'TRENDING_BULL', 'ACCUMULATION'].includes(liveRegime)) {
                                return true;
                            }
                            if (['MARKDOWN', 'BEARISH_TREND', 'TRENDING_BEAR', 'DISTRIBUTION'].includes(liveRegime)) {
                                return false;
                            }
                            return setup.isLong;
                        })();

                        // [OPTIMIZACIÓN v12.2] Evitar deriva de precios (drifting) si está cerca del rango del template
                        const priceDev = Math.abs(livePrice - setup.refPrice) / setup.refPrice;
                        const scale = priceDev < 0.15 ? 1.0 : livePrice / setup.refPrice;
                        let entry = setup.refEntry * scale;
                        let sl = setup.refSL * scale;
                        let tp1 = setup.refTP1 * scale;
                        let tp2 = setup.refTP2 * scale;

                        // Si la dirección calculada difiere de la plantilla estática, hacemos un espejo (mirror) de los niveles
                        if (isLong !== setup.isLong) {
                            const riskAmt = Math.abs(setup.refEntry - setup.refSL) * scale;
                            sl = isLong ? entry - riskAmt : entry + riskAmt;
                            tp1 = isLong ? entry + riskAmt * 1.5 : entry - riskAmt * 1.5;
                            tp2 = isLong ? entry + riskAmt * 3.0 : entry - riskAmt * 3.0;
                        }

                        let reasonEntry = setup.reasonEntry;
                        let reasonSL = setup.reasonSL;
                        let reasonTP1 = setup.reasonTP1;
                        let reasonTP2 = setup.reasonTP2;

                        if (isLong !== setup.isLong) {
                            reasonEntry = isLong 
                                ? `[⚡ Radar] Entrada en zona de descuento macro (${formatCurrency(entry)}).` 
                                : `[⚡ Radar] Entrada en corto en zona de distribución macro (${formatCurrency(entry)}).`;
                            reasonSL = isLong
                                ? `[🛡️ Invalidez] Stop Loss colocado debajo del soporte de tendencia.`
                                : `[🛡️ Invalidez] Stop Loss colocado arriba de la resistencia de tendencia.`;
                            reasonTP1 = `[🎯 TP] Primer target de cobertura asimétrica a 1.5x.`;
                            reasonTP2 = `[🔥 LIQ] Target final en busca de barrido a 3.0x de beneficio.`;
                        }

                        let isDynamic = false;
                        let isEntryDynamic = false;

                        // [NIVEL INSTITUCIONAL v12.0] Vinculación dinámica con SMC y Liquidaciones
                        const isCurrentActive = activeSymbol === setup.symbol || activeSymbol.replace('USDT', '') === setup.symbol.replace('USDT', '');
                        if (isCurrentActive) {
                            if (isLong) {
                                // ── LONG SMC SETUP ──
                                // 1. Entrada en Bullish OB o FVG alcista
                                const bullOBs = smcData?.order_blocks?.bullish || [];
                                const activeOB = bullOBs
                                    .filter((ob: any) => ob.top < livePrice)
                                    .sort((a: any, b: any) => b.top - a.top)[0]; // Más cercano por debajo

                                if (activeOB) {
                                    entry = activeOB.top;
                                    sl = activeOB.bottom * 0.999;
                                    reasonEntry = `[⚡ OB] Entrada en el límite superior del Bullish OB detectado en ${formatCurrency(activeOB.bottom)} - ${formatCurrency(activeOB.top)}.`;
                                    reasonSL = `[🛡️ Invalidez] Colocado debajo del soporte inferior del Bullish OB (${formatCurrency(activeOB.bottom)}).`;
                                    isEntryDynamic = true;
                                } else {
                                    const bullFVGs = smcData?.fvgs?.bullish || [];
                                    const activeFVG = bullFVGs
                                        .filter((fvg: any) => fvg.top < livePrice)
                                        .sort((a: any, b: any) => b.top - a.top)[0];
                                    if (activeFVG) {
                                        entry = activeFVG.top;
                                        sl = activeFVG.bottom * 0.998;
                                        reasonEntry = `[⚡ FVG] Entrada en el límite superior del Fair Value Gap alcista en ${formatCurrency(activeFVG.top)}.`;
                                        reasonSL = `[🛡️ Invalidez] Debajo del soporte inferior del FVG en ${formatCurrency(activeFVG.bottom)}.`;
                                        isEntryDynamic = true;
                                    }
                                }

                                // Solo si la entrada es dinámica recalculamos TPs dinámicos
                                if (isEntryDynamic) {
                                    isDynamic = true;
                                    const riskAmt = Math.abs(entry - sl);

                                    // 2. TP1 en la base del Bearish OB o FVG bajista
                                    const bearOBs = smcData?.order_blocks?.bearish || [];
                                    const targetOB = bearOBs
                                        .filter((ob: any) => ob.bottom > livePrice)
                                        .sort((a: any, b: any) => a.bottom - b.bottom)[0]; // Más cercano por arriba
                                    
                                    if (targetOB) {
                                        tp1 = targetOB.bottom;
                                        reasonTP1 = `[🎯 TP] Resistencia estructural en la base del Bearish OB en ${formatCurrency(targetOB.bottom)}.`;
                                    } else {
                                        tp1 = entry + riskAmt * 1.5;
                                        reasonTP1 = `[🎯 TP] Target proyectado a 1.5x del riesgo del stop loss estructural (${formatCurrency(tp1)}).`;
                                    }

                                    // 3. TP2 en la zona de liquidación más densa de Shorts
                                    let foundTP2 = false;
                                    if (liquidations && liquidations.length > 0) {
                                        const shortLiqs = liquidations
                                            .filter((liq: any) => liq.type === 'SHORT_LIQ' && liq.price > livePrice)
                                            .sort((a: any, b: any) => b.volume - a.volume)[0];
                                        if (shortLiqs) {
                                            tp2 = shortLiqs.price;
                                            reasonTP2 = `[🔥 LIQ] Target en zona de liquidación masiva de shorts de ${shortLiqs.leverage}x (${formatCurrency(shortLiqs.price)}).`;
                                            foundTP2 = true;
                                        }
                                    }
                                    if (!foundTP2) {
                                        tp2 = entry + riskAmt * 3.0;
                                        reasonTP2 = `[🔥 LIQ] Proyección matemática a 3.0x de beneficio asimétrico (${formatCurrency(tp2)}).`;
                                    }
                                }
                            } else {
                                // ── SHORT SMC SETUP ──
                                // 1. Entrada en Bearish OB o FVG bajista
                                const bearOBs = smcData?.order_blocks?.bearish || [];
                                const activeOB = bearOBs
                                    .filter((ob: any) => ob.bottom > livePrice)
                                    .sort((a: any, b: any) => b.bottom - b.bottom)[0]; // Más cercano por arriba

                                if (activeOB) {
                                    entry = activeOB.bottom;
                                    sl = activeOB.top * 1.001;
                                    reasonEntry = `[⚡ OB] Venta corta en el límite inferior del Bearish OB detectado en ${formatCurrency(activeOB.bottom)} - ${formatCurrency(activeOB.top)}.`;
                                    reasonSL = `[🛡️ Invalidez] Colocado arriba del límite superior del Bearish OB (${formatCurrency(activeOB.top)}).`;
                                    isEntryDynamic = true;
                                } else {
                                    const bearFVGs = smcData?.fvgs?.bearish || [];
                                    const activeFVG = bearFVGs
                                        .filter((fvg: any) => fvg.bottom > livePrice)
                                        .sort((a: any, b: any) => b.bottom - b.bottom)[0];
                                    if (activeFVG) {
                                        entry = activeFVG.bottom;
                                        sl = activeFVG.top * 1.002;
                                        reasonEntry = `[⚡ FVG] Entrada corta en la base del Fair Value Gap bajista en ${formatCurrency(activeFVG.bottom)}.`;
                                        reasonSL = `[🛡️ Invalidez] Arriba de la invalidez del FVG bajista en ${formatCurrency(activeFVG.top)}.`;
                                        isEntryDynamic = true;
                                    }
                                }

                                // Solo si la entrada es dinámica recalculamos TPs dinámicos
                                if (isEntryDynamic) {
                                    isDynamic = true;
                                    const riskAmt = Math.abs(entry - sl);

                                    // 2. TP1 en la cima del Bullish OB o FVG alcista
                                    const bullOBs = smcData?.order_blocks?.bullish || [];
                                    const targetOB = bullOBs
                                        .filter((ob: any) => ob.top < livePrice)
                                        .sort((a: any, b: any) => b.top - a.top)[0]; // Más cercano por debajo

                                    if (targetOB) {
                                        tp1 = targetOB.top;
                                        reasonTP1 = `[🎯 TP] Soporte estructural en el límite superior del Bullish OB en ${formatCurrency(targetOB.top)}.`;
                                    } else {
                                        tp1 = entry - riskAmt * 1.5;
                                        reasonTP1 = `[🎯 TP] Target proyectado a 1.5x del riesgo del stop loss estructural (${formatCurrency(tp1)}).`;
                                    }

                                    // 3. TP2 en la zona de liquidación más densa de Longs
                                    let foundTP2 = false;
                                    if (liquidations && liquidations.length > 0) {
                                        const longLiqs = liquidations
                                            .filter((liq: any) => liq.type === 'LONG_LIQ' && liq.price < livePrice)
                                            .sort((a: any, b: any) => b.volume - a.volume)[0];
                                        if (longLiqs) {
                                            tp2 = longLiqs.price;
                                            reasonTP2 = `[🔥 LIQ] Target en zona de liquidación masiva de longs de ${longLiqs.leverage}x (${formatCurrency(longLiqs.price)}).`;
                                            foundTP2 = true;
                                        }
                                    }
                                    if (!foundTP2) {
                                        tp2 = entry - riskAmt * 3.0;
                                        reasonTP2 = `[🔥 LIQ] Proyección matemática a 3.0x de beneficio asimétrico (${formatCurrency(tp2)}).`;
                                    }
                                }
                            }
                        }

                        const risk = Math.abs(entry - sl);
                        const reward = Math.abs(tp2 - entry);
                        const rr = risk > 0 ? (reward / risk).toFixed(1) : '0';

                        // Obtener régimen dinámico del store
                        const meta = REGIME_META[liveRegime] || REGIME_META[setup.regime] || REGIME_META['RANGING'];
                        const liveStrategy = (marketSummary[setup.symbol]?.strategy || setup.strategy).replace(/_/g, ' ');
 
                        return (
                            <div 
                                key={setup.symbol} 
                                className={`border rounded-xl transition-all duration-300 ${isExpanded ? 'bg-[#050C15]/90 border-white/20' : 'bg-white/[0.01] border-white/5 hover:border-white/10'}`}
                            >
                                {/* Accordion Header */}
                                <button 
                                    onClick={() => toggleAsset(setup.symbol)}
                                    className="w-full flex items-center justify-between p-3 text-left focus:outline-none"
                                >
                                    <div className="flex items-center gap-2.5 min-w-0">
                                        <span className="text-sm shrink-0">{setup.icon}</span>
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-1.5 flex-wrap">
                                                <span className="block text-xs font-black text-white/90 truncate">{setup.displayName}</span>
                                                {Number(rr) >= 2.5 ? (
                                                    <span className="text-[7px] text-neon-green bg-neon-green/10 border border-neon-green/30 font-black px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0 flex items-center gap-1 shadow-[0_0_8px_rgba(16,185,129,0.15)]">
                                                        👑 PRIORIDAD ELITE
                                                    </span>
                                                ) : isDynamic ? (
                                                    <span className="text-[7px] text-neon-cyan bg-neon-cyan/10 border border-neon-cyan/30 font-bold px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0 shadow-[0_0_8px_rgba(6,182,212,0.1)]">
                                                        🎯 ALTA EXPECTATIVA
                                                    </span>
                                                ) : null}
                                            </div>
                                            <span className="block text-[8px] text-white/40 tracking-wider truncate uppercase">{liveStrategy}</span>
                                        </div>
                                    </div>
                                    
                                    <div className="flex items-center gap-3 shrink-0 pl-2">
                                        <div className="text-right">
                                            <span className="block text-xs font-black text-neon-cyan">{formatCurrency(livePrice)}</span>
                                            <span 
                                                className={`inline-block text-[7px] font-black px-1.5 py-0.5 rounded border mt-0.5 transition-all duration-300 ${meta.bg} ${meta.color}`}
                                                style={{ boxShadow: `0 0 8px ${meta.glow}` }}
                                            >
                                                {meta.label}
                                            </span>
                                        </div>
                                        {isExpanded ? <ChevronUp size={14} className="text-white/40" /> : <ChevronDown size={14} className="text-white/40" />}
                                    </div>
                                </button>

                                {/* Accordion Content */}
                                <AnimatePresence initial={false}>
                                    {isExpanded && (
                                        <motion.div
                                            initial={{ height: 0, opacity: 0 }}
                                            animate={{ height: 'auto', opacity: 1 }}
                                            exit={{ height: 0, opacity: 0 }}
                                            transition={{ duration: 0.2 }}
                                            className="overflow-hidden"
                                        >
                                            <div className="p-3 border-t border-white/5 space-y-3 bg-black/40 text-[10px] rounded-b-xl">
                                                
                                                {/* Setup Grid */}
                                                <div className="grid grid-cols-2 gap-2">
                                                    <div className="bg-white/[0.02] border border-white/5 rounded-lg p-2 relative group/cell">
                                                        <div className="flex justify-between items-start">
                                                            <div>
                                                                <span className="block text-[7px] text-white/40 font-black uppercase">Precio Entrada (Entry)</span>
                                                                <span className="text-xs font-black text-neon-cyan">{formatCurrency(entry)}</span>
                                                            </div>
                                                            <button 
                                                                onClick={(e) => { e.stopPropagation(); handleCopy(entry, `${setup.symbol}-entry`); }}
                                                                className="opacity-0 group-hover/cell:opacity-100 transition-opacity p-1 bg-white/5 hover:bg-white/10 rounded text-white/60 hover:text-white"
                                                                title="Copiar precio de entrada"
                                                            >
                                                                {copiedId === `${setup.symbol}-entry` ? <Check size={10} className="text-neon-green" /> : <Copy size={10} />}
                                                            </button>
                                                        </div>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonEntry}</span>
                                                    </div>
                                                    <div className="bg-white/[0.02] border border-neon-red/10 rounded-lg p-2 relative group/cell">
                                                        <div className="flex justify-between items-start">
                                                            <div>
                                                                <span className="block text-[7px] text-white/40 font-black uppercase">Stop Loss (SL)</span>
                                                                <span className="text-xs font-black text-neon-red">{formatCurrency(sl)}</span>
                                                            </div>
                                                            <button 
                                                                onClick={(e) => { e.stopPropagation(); handleCopy(sl, `${setup.symbol}-sl`); }}
                                                                className="opacity-0 group-hover/cell:opacity-100 transition-opacity p-1 bg-white/5 hover:bg-white/10 rounded text-white/60 hover:text-white"
                                                                title="Copiar Stop Loss"
                                                            >
                                                                {copiedId === `${setup.symbol}-sl` ? <Check size={10} className="text-neon-green" /> : <Copy size={10} />}
                                                            </button>
                                                        </div>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonSL}</span>
                                                    </div>
                                                    <div className="bg-white/[0.02] border border-neon-green/10 rounded-lg p-2 relative group/cell">
                                                        <div className="flex justify-between items-start">
                                                            <div>
                                                                <span className="block text-[7px] text-white/40 font-black uppercase">Take Profit 1 (TP1)</span>
                                                                <span className="text-xs font-black text-neon-green">{formatCurrency(tp1)}</span>
                                                            </div>
                                                            <button 
                                                                onClick={(e) => { e.stopPropagation(); handleCopy(tp1, `${setup.symbol}-tp1`); }}
                                                                className="opacity-0 group-hover/cell:opacity-100 transition-opacity p-1 bg-white/5 hover:bg-white/10 rounded text-white/60 hover:text-white"
                                                                title="Copiar Take Profit 1"
                                                            >
                                                                {copiedId === `${setup.symbol}-tp1` ? <Check size={10} className="text-neon-green" /> : <Copy size={10} />}
                                                            </button>
                                                        </div>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonTP1}</span>
                                                    </div>
                                                    <div className="bg-white/[0.02] border border-neon-green/10 rounded-lg p-2 relative group/cell">
                                                        <div className="flex justify-between items-start">
                                                            <div>
                                                                <span className="block text-[7px] text-white/40 font-black uppercase">Take Profit 2 (TP2)</span>
                                                                <span className="text-xs font-black text-neon-green/80">{formatCurrency(tp2)}</span>
                                                            </div>
                                                            <button 
                                                                onClick={(e) => { e.stopPropagation(); handleCopy(tp2, `${setup.symbol}-tp2`); }}
                                                                className="opacity-0 group-hover/cell:opacity-100 transition-opacity p-1 bg-white/5 hover:bg-white/10 rounded text-white/60 hover:text-white"
                                                                title="Copiar Take Profit 2"
                                                            >
                                                                {copiedId === `${setup.symbol}-tp2` ? <Check size={10} className="text-neon-green" /> : <Copy size={10} />}
                                                            </button>
                                                        </div>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonTP2}</span>
                                                    </div>
                                                </div>

                                                {/* Risk Management & Lot Size Suggestion v11.0 */}
                                                <div className="grid grid-cols-2 gap-2 text-[9px] bg-amber-500/5 p-2 rounded-lg border border-amber-500/20">
                                                    <div>
                                                        <span className="block text-[7px] text-amber-400/70 font-black uppercase">Distancia SL (%)</span>
                                                        <span className="text-xs font-black text-amber-400 font-mono">
                                                            {((Math.abs(entry - sl) / entry) * 100).toFixed(2)}%
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <span className="block text-[7px] text-amber-400/70 font-black uppercase">Lote Sugerido ($100 Risk)</span>
                                                        <span className="text-xs font-black text-amber-400 font-mono">
                                                            ${formatCurrency(Math.round(100 / ((Math.abs(entry - sl) / entry) || 0.01)))} USDT
                                                        </span>
                                                    </div>
                                                </div>

                                                {/* Summary Stats */}
                                                <div className="flex justify-between items-center text-[9px] bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                                    <span className="text-white/40 font-black">Régimen: <span className={`${meta.color} font-black`}>{meta.label}</span></span>
                                                    <span className="text-white/40 font-black">
                                                        Filtro: <span className={timeInfo.dayStatus === 'LOW' ? 'text-neon-red font-black' : isKillzoneActive ? 'text-neon-green font-black' : 'text-yellow-400 font-black'}>
                                                            {timeInfo.dayStatus === 'LOW' ? 'W-END (EVITAR)' : isKillzoneActive ? 'K-ZONE' : 'STANDBY'}
                                                        </span>
                                                    </span>
                                                    <span className="text-neon-cyan font-black">Ratio R:R: <span className="text-white">1:{rr}</span></span>
                                                </div>

                                                {/* Action Bar: Copiar Plan Completo */}
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        const isLong = entry > sl;
                                                        const textPlan = `📋 PLAN OPERATIVO ${setup.displayName}\n` +
                                                            `• Dirección: ${isLong ? '🟢 LONG (COMPRA)' : '🔴 SHORT (VENTA)'}\n` +
                                                            `• Entrada Límite: $${formatCurrency(entry)}\n` +
                                                            `• Stop Loss: $${formatCurrency(sl)} (-${((Math.abs(entry - sl) / entry) * 100).toFixed(2)}%)\n` +
                                                            `• TP1: $${formatCurrency(tp1)}\n` +
                                                            `• TP2: $${formatCurrency(tp2)}\n` +
                                                            `• Lote Sugerido ($100 Risk): $${formatCurrency(Math.round(100 / ((Math.abs(entry - sl) / entry) || 0.01)))} USDT\n` +
                                                            `• R:R Proyectado: 1:${rr}`;
                                                        handleCopy(textPlan, `${setup.symbol}-fullplan`);
                                                    }}
                                                    className="w-full py-1.5 bg-neon-cyan/10 hover:bg-neon-cyan/20 border border-neon-cyan/30 rounded-lg text-neon-cyan text-[9px] font-bold font-mono transition-all flex items-center justify-center gap-1.5 active:scale-98"
                                                >
                                                    {copiedId === `${setup.symbol}-fullplan` ? (
                                                        <>
                                                            <Check size={12} className="text-neon-green" />
                                                            <span>¡PLAN COMPLETO COPIADO AL PORTAPAPELES!</span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Copy size={12} />
                                                            <span>COPIAR PLAN OPERATIVO COMPLETO PARA WHATSAPP/EXCHANGE</span>
                                                        </>
                                                    )}
                                                </button>

                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        );
                    })}
                </div>

                {/* ── 5. TEMPORAL CONFLUENCE ───────────────────────── */}
                <div className="bg-[#050C15]/60 border border-white/5 rounded-xl p-3 space-y-2">
                    <div className="flex justify-between items-center">
                        <div className="flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-neon-cyan animate-pulse" />
                            <span className="text-[9px] font-black uppercase text-white/60">CONFLUENCIA TEMPORAL</span>
                        </div>
                        <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${timeInfo.dayStatus === 'HIGH' && isKillzoneActive ? 'bg-neon-green/20 text-neon-green border-neon-green/30' : 'bg-yellow-500/10 text-yellow-400 border-yellow-400/20'}`}>
                            {timeInfo.dayStatus === 'HIGH' && isKillzoneActive ? 'VENTANA: APROBADA' : 'VENTANA: PRECAUCIÓN'}
                        </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[8px]">
                        <div className="bg-white/[0.02] border border-white/5 p-2 rounded-lg">
                            <span className="block text-white/40 font-bold uppercase">DÍA DE OPERACIÓN</span>
                            <span className={`block text-[10px] font-black mt-0.5 ${timeInfo.dayStatus === 'HIGH' ? 'text-neon-green' : 'text-yellow-400'}`}>
                                {dayLabel} ({timeInfo.dayStatus === 'HIGH' ? 'ALTA PROB.' : 'PROB. MEDIA/BAJA'})
                            </span>
                        </div>
                        <div className="bg-white/[0.02] border border-white/5 p-2 rounded-lg">
                            <span className="block text-white/40 font-bold uppercase">SESIÓN / HORARIO (UTC)</span>
                            <span className={`block text-[10px] font-black mt-0.5 ${isKillzoneActive ? 'text-neon-green' : 'text-white/60'}`}>
                                {currentSessionName}
                            </span>
                        </div>
                    </div>

                    <p className="text-[8.5px] text-white/40 leading-relaxed font-mono pl-2 border-l border-l-white/10">
                        {timeInfo.dayReason} {isKillzoneActive ? 'Estructura en máxima volatilidad institucional.' : 'Rango de bajo volumen. Mayor probabilidad de falsos rompimientos.'}
                    </p>
                </div>

                {/* Risk Guidelines Section */}
                <div className="p-3 rounded-xl border border-yellow-500/10 bg-yellow-500/[0.02] space-y-2">
                    <div className="flex items-center gap-2 text-amber-500">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span className="text-[9px] font-black uppercase tracking-wider">REGLAS DE GESTIÓN DE RIESGO</span>
                    </div>
                    <div className="space-y-1.5 text-[8.5px] text-white/50 leading-relaxed font-mono">
                        <p><strong className="text-white">Ejecución:</strong> Utiliza órdenes limitadas (Limit Orders) para asegurar los precios de entrada exactos. Evita entrar a mercado (Market Orders) durante picos de volatilidad.</p>
                        <p><strong className="text-white">Toma de Ganancias Parciales:</strong> Al alcanzar el TP1, se recomienda cerrar el 50% de la posición y mover el Stop Loss al precio de entrada (Breakeven) para asegurar un trade libre de riesgo.</p>
                        <p><strong className="text-white">Apalancamiento Recomendado:</strong> Dados los niveles calculados, no utilices un apalancamiento superior a 5x en Crypto y 10x en Commodities para mantener tus propios niveles de liquidación completamente fuera de la zona de peligro.</p>
                    </div>
                </div>

            </div>

            {/* Footer */}
            <div className="p-2 border-t border-white/5 bg-black/40">
                <div className="flex justify-between items-center text-[7px] text-white/15 uppercase tracking-tighter">
                    <span>Slingshot Gen 3 Platinum</span>
                    <span>Consolidador Multi-Activo</span>
                </div>
            </div>
        </div>
    );
}
