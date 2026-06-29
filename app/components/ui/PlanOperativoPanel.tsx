'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Target, Compass, AlertTriangle, ArrowUpRight, ArrowDownRight, Award, Cpu, ChevronDown, ChevronUp, ShieldAlert, Sparkles } from 'lucide-react';
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
    regime: 'MARKUP' | 'MARKDOWN' | 'ACCUMULATION' | 'DISTRIBUTION' | 'CHOPPY';
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
        refPrice: 1578,
        refEntry: 1515,
        refSL: 1435,
        refTP1: 1680,
        refTP2: 1830,
        regime: 'MARKDOWN',
        regimeLabel: 'Bajista (MARKDOWN)',
        strategy: 'Long por Barrido de Liquidez (Caza de Stops)',
        reasonEntry: 'Colocado estratégicamente justo debajo de la liquidez SSL de $1,506.50 para atrapar la mecha de liquidación.',
        reasonSL: 'Invalidación estructural del barrido macro.',
        reasonTP1: 'Relleno del FVG bajista abierto.',
        reasonTP2: 'Zona OTE de descuento de Fibonacci.',
        isLong: true
    },
    {
        symbol: 'SOLUSDT',
        displayName: 'Solana (SOL-USD)',
        icon: '💎',
        refPrice: 71.21,
        refEntry: 70.20,
        refSL: 67.20,
        refTP1: 81.50,
        refTP2: 87.00,
        regime: 'ACCUMULATION',
        regimeLabel: 'Acumulación (ACCUMULATION)',
        strategy: 'Long Limitado (Entrada Directa)',
        reasonEntry: 'Dentro del FVG alcista de soporte, barriendo a los longs de 100x y 50x.',
        reasonSL: 'Por debajo del nivel 78.6% de Fibonacci, invalidando la OTE.',
        reasonTP1: 'Justo antes del Bearish OB.',
        reasonTP2: 'Zona de liquidez expuesta BSL (Setup Estrella).',
        isLong: true
    },
    {
        symbol: 'XRPUSDT',
        displayName: 'Ripple (XRP-USD)',
        icon: '🌀',
        refPrice: 1.054,
        refEntry: 0.9920,
        refSL: 0.9450,
        refTP1: 1.1100,
        refTP2: 1.2100,
        regime: 'MARKDOWN',
        regimeLabel: 'Bajista (MARKDOWN)',
        strategy: 'Long por Barrido de Soporte Psicológico',
        reasonEntry: 'Barrido por debajo del soporte clave de $1.01 y la barrera psicológica de $1.00.',
        reasonSL: 'Por debajo de la estructura de mínimos anterior.',
        reasonTP1: 'Retorno al FVG bajista.',
        reasonTP2: 'Zona OTE de equilibrio.',
        isLong: true
    },
    {
        symbol: 'XAGUSDT',
        displayName: 'Plata (XAG/USD)',
        icon: '🛡️',
        refPrice: 59.05,
        refEntry: 58.10,
        refSL: 56.40,
        refTP1: 68.00,
        refTP2: 75.50,
        regime: 'ACCUMULATION',
        regimeLabel: 'Acumulación (ACCUMULATION)',
        strategy: 'Long Limitado (Acumulación Pasiva)',
        reasonEntry: 'Cerca del mínimo estructural de $57.25.',
        reasonSL: 'Por debajo del soporte de 60 días.',
        reasonTP1: 'Límite del Bearish OB de $68.76.',
        reasonTP2: 'Atracción por ineficiencia de mercado.',
        isLong: true
    },
    {
        symbol: 'PAXGUSDT',
        displayName: 'PAX Gold (PAGX / PAXG)',
        icon: '🥇',
        refPrice: 4078,
        refEntry: 4045,
        refSL: 3935,
        refTP1: 4300,
        refTP2: 4500,
        regime: 'MARKDOWN',
        regimeLabel: 'Bajista en Descuento',
        strategy: 'Long Limitado (Refugio en Descuento)',
        reasonEntry: 'Dentro del FVG alcista de soporte de $4,034 - $4,065.',
        reasonSL: 'Por debajo del soporte de $3,963.',
        reasonTP1: 'Resistencia del FVG bajista.',
        reasonTP2: 'Resistencia institucional.',
        isLong: true
    },
    {
        symbol: 'CLUSDT',
        displayName: 'Petróleo WTI (CL=F)',
        icon: '🛢️',
        refPrice: 72.0,
        refEntry: 68.70,
        refSL: 67.50,
        refTP1: 73.00,
        refTP2: 77.00,
        regime: 'ACCUMULATION',
        regimeLabel: 'Acumulación en Extremo Descuento',
        strategy: 'Long Limitado (Rebote en FVG de Largo Plazo)',
        reasonEntry: 'Justo por debajo del soporte de $68.56, barriendo a los longs apalancados a 100x en $68.57.',
        reasonSL: 'Por debajo del nivel de liquidación de 50x de $67.91 e invalidando el FVG histórico.',
        reasonTP1: 'Imbalance bajista inmediato en $73.18.',
        reasonTP2: 'Antes de la zona de equilibrio OTE.',
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
};

export default function PlanOperativoPanel() {
    const { latestPrices, marketSummary, smcData, liquidations, activeSymbol } = useTelemetryStore();
    const [expandedAsset, setExpandedAsset] = useState<string | null>('BTCUSDT');

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

    const toggleAsset = (symbol: string) => {
        setExpandedAsset(expandedAsset === symbol ? null : symbol);
    };

    return (
        <div className="flex flex-col h-full overflow-hidden bg-black/20 font-mono">
            {/* Header */}
            <div className="p-4 border-b border-white/5 flex items-center bg-gradient-to-r from-neon-cyan/15 to-transparent">
                <div className="flex items-center gap-2.5 pr-44">
                    <Compass size={16} className="text-neon-cyan animate-spin-slow" />
                    <h2 className="text-xs font-bold text-white/90 tracking-widest drop-shadow-[0_0_8px_rgba(0,229,255,0.4)]">
                        PLAN OPERATIVO
                    </h2>
                </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3">
                
                {/* Accordion List */}
                <div className="space-y-2">
                    {SETUPS_TEMPLATE.map((setup) => {
                        // Buscar precio en vivo o fallback
                        const livePrice = latestPrices[setup.symbol] || latestPrices[setup.symbol.replace('USDT', '')] || setup.refPrice;
                        const isExpanded = expandedAsset === setup.symbol;

                        // Escalado inteligente de precios si hay discrepancia
                        const scale = livePrice / setup.refPrice;
                        let entry = setup.refEntry * scale;
                        let sl = setup.refSL * scale;
                        let tp1 = setup.refTP1 * scale;
                        let tp2 = setup.refTP2 * scale;

                        let reasonEntry = setup.reasonEntry;
                        let reasonSL = setup.reasonSL;
                        let reasonTP1 = setup.reasonTP1;
                        let reasonTP2 = setup.reasonTP2;
                        let isDynamic = false;

                        // [NIVEL INSTITUCIONAL v12.0] Vinculación dinámica con SMC y Liquidaciones
                        const isCurrentActive = activeSymbol === setup.symbol || activeSymbol.replace('USDT', '') === setup.symbol.replace('USDT', '');
                        if (isCurrentActive) {
                            if (setup.isLong) {
                                // ── LONG SMC SETUP ──
                                // 1. Entrada en Bullish OB o FVG alcista
                                const bullOBs = smcData?.order_blocks?.bullish || [];
                                const activeOB = bullOBs
                                    .filter((ob: any) => ob.top < livePrice)
                                    .sort((a: any, b: any) => b.top - a.top)[0]; // Más cercano por debajo

                                if (activeOB) {
                                    entry = activeOB.top;
                                    sl = activeOB.bottom * 0.999;
                                    reasonEntry = `[⚡ OB] Entrada en el límite superior del Bullish OB detectado en $${formatCurrency(activeOB.bottom)} - $${formatCurrency(activeOB.top)}.`;
                                    reasonSL = `[🛡️ Invalidez] Colocado debajo del soporte inferior del Bullish OB ($${formatCurrency(activeOB.bottom)}).`;
                                    isDynamic = true;
                                } else {
                                    const bullFVGs = smcData?.fvgs?.bullish || [];
                                    const activeFVG = bullFVGs
                                        .filter((fvg: any) => fvg.top < livePrice)
                                        .sort((a: any, b: any) => b.top - a.top)[0];
                                    if (activeFVG) {
                                        entry = activeFVG.top;
                                        sl = activeFVG.bottom * 0.998;
                                        reasonEntry = `[⚡ FVG] Entrada en el límite superior del Fair Value Gap alcista en $${formatCurrency(activeFVG.top)}.`;
                                        reasonSL = `[🛡️ Invalidez] Debajo del soporte inferior del FVG en $${formatCurrency(activeFVG.bottom)}.`;
                                        isDynamic = true;
                                    }
                                }

                                // 2. TP1 en la base del Bearish OB o FVG bajista
                                const bearOBs = smcData?.order_blocks?.bearish || [];
                                const targetOB = bearOBs
                                    .filter((ob: any) => ob.bottom > livePrice)
                                    .sort((a: any, b: any) => a.bottom - b.bottom)[0]; // Más cercano por arriba
                                
                                if (targetOB) {
                                    tp1 = targetOB.bottom;
                                    reasonTP1 = `[🎯 TP] Resistencia estructural en la base del Bearish OB en $${formatCurrency(targetOB.bottom)}.`;
                                    isDynamic = true;
                                }

                                // 3. TP2 en la zona de liquidación más densa de Shorts
                                if (liquidations && liquidations.length > 0) {
                                    const shortLiqs = liquidations
                                        .filter((liq: any) => liq.type === 'SHORT_LIQ' && liq.price > livePrice)
                                        .sort((a: any, b: any) => b.volume - a.volume)[0];
                                    if (shortLiqs) {
                                        tp2 = shortLiqs.price;
                                        reasonTP2 = `[🔥 LIQ] Target en zona de liquidación masiva de shorts de ${shortLiqs.leverage}x ($${formatCurrency(shortLiqs.price)}).`;
                                        isDynamic = true;
                                    }
                                }
                            } else {
                                // ── SHORT SMC SETUP ──
                                // 1. Entrada en Bearish OB o FVG bajista
                                const bearOBs = smcData?.order_blocks?.bearish || [];
                                const activeOB = bearOBs
                                    .filter((ob: any) => ob.bottom > livePrice)
                                    .sort((a: any, b: any) => a.bottom - b.bottom)[0]; // Más cercano por arriba

                                if (activeOB) {
                                    entry = activeOB.bottom;
                                    sl = activeOB.top * 1.001;
                                    reasonEntry = `[⚡ OB] Venta corta en el límite inferior del Bearish OB detectado en $${formatCurrency(activeOB.bottom)} - $${formatCurrency(activeOB.top)}.`;
                                    reasonSL = `[🛡️ Invalidez] Colocado arriba del límite superior del Bearish OB ($${formatCurrency(activeOB.top)}).`;
                                    isDynamic = true;
                                } else {
                                    const bearFVGs = smcData?.fvgs?.bearish || [];
                                    const activeFVG = bearFVGs
                                        .filter((fvg: any) => fvg.bottom > livePrice)
                                        .sort((a: any, b: any) => a.bottom - b.bottom)[0];
                                    if (activeFVG) {
                                        entry = activeFVG.bottom;
                                        sl = activeFVG.top * 1.002;
                                        reasonEntry = `[⚡ FVG] Entrada corta en la base del Fair Value Gap bajista en $${formatCurrency(activeFVG.bottom)}.`;
                                        reasonSL = `[🛡️ Invalidez] Arriba de la invalidez del FVG bajista en $${formatCurrency(activeFVG.top)}.`;
                                        isDynamic = true;
                                    }
                                }

                                // 2. TP1 en la cima del Bullish OB o FVG alcista
                                const bullOBs = smcData?.order_blocks?.bullish || [];
                                const targetOB = bullOBs
                                    .filter((ob: any) => ob.top < livePrice)
                                    .sort((a: any, b: any) => b.top - a.top)[0]; // Más cercano por debajo

                                if (targetOB) {
                                    tp1 = targetOB.top;
                                    reasonTP1 = `[🎯 TP] Soporte estructural en el límite superior del Bullish OB en $${formatCurrency(targetOB.top)}.`;
                                    isDynamic = true;
                                }

                                // 3. TP2 en la zona de liquidación más densa de Longs
                                if (liquidations && liquidations.length > 0) {
                                    const longLiqs = liquidations
                                        .filter((liq: any) => liq.type === 'LONG_LIQ' && liq.price < livePrice)
                                        .sort((a: any, b: any) => b.volume - a.volume)[0];
                                    if (longLiqs) {
                                        tp2 = longLiqs.price;
                                        reasonTP2 = `[🔥 LIQ] Target en zona de liquidación masiva de longs de ${longLiqs.leverage}x ($${formatCurrency(longLiqs.price)}).`;
                                        isDynamic = true;
                                    }
                                }
                            }
                        }

                        const risk = Math.abs(entry - sl);
                        const reward = Math.abs(tp2 - entry);
                        const rr = risk > 0 ? (reward / risk).toFixed(1) : '0';

                        // Obtener régimen dinámico del store
                        const liveRegime = marketSummary[setup.symbol]?.regime || setup.regime;
                        const meta = REGIME_META[liveRegime] || REGIME_META[setup.regime] || REGIME_META['RANGING'];

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
                                            <div className="flex items-center gap-1.5">
                                                <span className="block text-xs font-black text-white/90 truncate">{setup.displayName}</span>
                                                {isDynamic && (
                                                    <span className="text-[7px] text-[#00e5ff] bg-[#00e5ff]/10 border border-[#00e5ff]/35 font-bold px-1 rounded uppercase tracking-wider shrink-0">
                                                        ✨ SMC DYNAMIC
                                                    </span>
                                                )}
                                            </div>
                                            <span className="block text-[8px] text-white/40 tracking-wider truncate uppercase">{setup.strategy}</span>
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
                                                    <div className="bg-white/[0.02] border border-white/5 rounded-lg p-2">
                                                        <span className="block text-[7px] text-white/40 font-black uppercase">Precio Entrada (Entry)</span>
                                                        <span className="text-xs font-black text-neon-cyan">{formatCurrency(entry)}</span>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonEntry}</span>
                                                    </div>
                                                    <div className="bg-white/[0.02] border border-neon-red/10 rounded-lg p-2">
                                                        <span className="block text-[7px] text-white/40 font-black uppercase">Stop Loss (SL)</span>
                                                        <span className="text-xs font-black text-neon-red">{formatCurrency(sl)}</span>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonSL}</span>
                                                    </div>
                                                    <div className="bg-white/[0.02] border border-neon-green/10 rounded-lg p-2">
                                                        <span className="block text-[7px] text-white/40 font-black uppercase">Take Profit 1 (TP1)</span>
                                                        <span className="text-xs font-black text-neon-green">{formatCurrency(tp1)}</span>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonTP1}</span>
                                                    </div>
                                                    <div className="bg-white/[0.02] border border-neon-green/10 rounded-lg p-2">
                                                        <span className="block text-[7px] text-white/40 font-black uppercase">Take Profit 2 (TP2)</span>
                                                        <span className="text-xs font-black text-neon-green/80">{formatCurrency(tp2)}</span>
                                                        <span className="block text-[7px] text-white/20 mt-1 italic leading-tight">{reasonTP2}</span>
                                                    </div>
                                                </div>

                                                {/* Summary Stats */}
                                                <div className="flex justify-between items-center text-[9px] bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                                    <span className="text-white/40 font-black">Régimen: <span className={`${meta.color} font-black`}>{meta.label}</span></span>
                                                    <span className="text-white/40 font-black">
                                                        Filtro: <span className={timeInfo.dayStatus === 'LOW' ? 'text-neon-red font-black' : timeInfo.isKillzone ? 'text-neon-green font-black' : 'text-yellow-400 font-black'}>
                                                            {timeInfo.dayStatus === 'LOW' ? 'W-END (EVITAR)' : timeInfo.isKillzone ? 'K-ZONE' : 'STANDBY'}
                                                        </span>
                                                    </span>
                                                    <span className="text-neon-cyan font-black">Ratio R:R: <span className="text-white">1:{rr}</span></span>
                                                </div>

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
                        <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${timeInfo.dayStatus === 'HIGH' && timeInfo.isKillzone ? 'bg-neon-green/20 text-neon-green border-neon-green/30' : 'bg-yellow-500/10 text-yellow-400 border-yellow-400/20'}`}>
                            {timeInfo.dayStatus === 'HIGH' && timeInfo.isKillzone ? 'VENTANA: APROBADA' : 'VENTANA: PRECAUCIÓN'}
                        </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[8px]">
                        <div className="bg-white/[0.02] border border-white/5 p-2 rounded-lg">
                            <span className="block text-white/40 font-bold uppercase">DÍA DE OPERACIÓN</span>
                            <span className={`block text-[10px] font-black mt-0.5 ${timeInfo.dayStatus === 'HIGH' ? 'text-neon-green' : 'text-yellow-400'}`}>
                                {timeInfo.dayName} ({timeInfo.dayStatus === 'HIGH' ? 'ALTA PROB.' : 'PROB. MEDIA/BAJA'})
                            </span>
                        </div>
                        <div className="bg-white/[0.02] border border-white/5 p-2 rounded-lg">
                            <span className="block text-white/40 font-bold uppercase">SESIÓN / HORARIO (UTC)</span>
                            <span className={`block text-[10px] font-black mt-0.5 ${timeInfo.isKillzone ? 'text-neon-green' : 'text-white/60'}`}>
                                {timeInfo.sessionName}
                            </span>
                        </div>
                    </div>

                    <p className="text-[8.5px] text-white/40 leading-relaxed font-mono pl-2 border-l border-white/10">
                        {timeInfo.dayReason} {timeInfo.isKillzone ? 'Estructura en máxima volatilidad institucional.' : 'Rango de bajo volumen. Mayor probabilidad de falsos rompimientos.'}
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
