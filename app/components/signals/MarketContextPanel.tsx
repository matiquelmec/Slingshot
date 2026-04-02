'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Target, Clock, ArrowUpCircle, ArrowDownCircle, Pause, Layers, Eye } from 'lucide-react';
import { buildConditions, Condition } from '../../utils/signalLogic';
import { QuantDiagnostic, SessionData } from '../../types/signal';

// ─── Tipos ─────────────────────────────────────────────────────────────────
interface MarketContextPanelProps {
    regime: string | null;
    activeStrategy: string | null;
    diagnostic: QuantDiagnostic | null;
    currentPrice?: number | null;
    nearestSupport?: number | null;
    nearestResistance?: number | null;
    sessionData?: SessionData | null;
}

// ─── Configuración de Régimen (Limpiando Ternary Hells) ─────────────────────
const REGIME_META: Record<string, { color: string; border: string; icon: React.ReactNode; label: string; explanation: string; accent: string }> = {
    ACCUMULATION: {
        color: 'text-neon-cyan', border: 'border-neon-cyan/30', accent: 'bg-neon-cyan',
        icon: <Layers size={14} className="text-neon-cyan" />,
        label: 'ACUMULACIÓN',
        explanation: 'Evidencia de absorción institucional a precios bajos. El precio oscila en un rango estrecho mientras se agota la oferta flotante. Hipótesis directriz: Próxima fase es MARKUP (Ruptura Alcista).',
    },
    MARKUP: {
        color: 'text-neon-green', border: 'border-neon-green/30', accent: 'bg-neon-green',
        icon: <ArrowUpCircle size={14} className="text-neon-green" />,
        label: 'TENDENCIA ALCISTA (MARKUP)',
        explanation: 'Estructura de precios ascendente confirmada (Higher Highs, Higher Lows). Dominio de la demanda institucional. Hipótesis directriz: Comprar (LONG) en retrocesos a las zonas de valor.',
    },
    DISTRIBUTION: {
        color: 'text-red-400', border: 'border-red-400/30', accent: 'bg-red-400',
        icon: <Layers size={14} className="text-red-400" />,
        label: 'DISTRIBUCIÓN',
        explanation: 'Evidencia de descarga institucional gradual a precios altos. Cierres débiles ocultos tras aparentes impulsos alcistas. Hipótesis directriz: Próxima fase es MARKDOWN (Ruptura Bajista).',
    },
    MARKDOWN: {
        color: 'text-neon-red', border: 'border-neon-red/30', accent: 'bg-neon-red',
        icon: <ArrowDownCircle size={14} className="text-neon-red" />,
        label: 'TENDENCIA BAJISTA (MARKDOWN)',
        explanation: 'Estructura de precios descendente confirmada (Lower Lows, Lower Highs). Dominio absoluto de la presión vendedora. Hipótesis directriz: Vender (SHORT) en rebotes falsos.',
    },
    RANGING: {
        color: 'text-yellow-400', border: 'border-yellow-400/30', accent: 'bg-yellow-400',
        icon: <Pause size={14} className="text-yellow-400" />,
        label: 'RANGO — STANDBY',
        explanation: 'Equilibrio temporal entre oferta y demanda. El precio oscila sin una ruptura direccional. Hipótesis directriz: Esperar expansión de volumen o cazar barridas de liquidez.',
    },
    CHOPPY: {
        color: 'text-purple-400', border: 'border-purple-400/30', accent: 'bg-purple-400',
        icon: <Pause size={14} className="text-purple-400" />,
        label: 'CHOPPY (TRANSICIÓN VOLÁTIL)',
        explanation: 'Acción de precio sucia y volátil. Las medias móviles están desalineadas. El mercado está decidiendo dirección. Hipótesis directriz: Standby táctico para proteger capital.',
    },
    UNKNOWN: {
        color: 'text-white/40', border: 'border-white/10', accent: 'bg-white/20',
        icon: <Eye size={14} className="text-white/40" />,
        label: 'CALIBRANDO RED NEURAL...',
        explanation: 'Procesando historial espacial para determinar Régimen de Wyckoff. Requiere 50-200 velas previas estabilizadas antes de emitir un dictamen algorítmico seguro.',
    },
};

const STATUS_STYLES = {
    MET: 'border-neon-green/60 bg-neon-green/20 text-neon-green shadow-[0_0_6px_rgba(0,255,65,0.4)]',
    PARTIAL: 'border-yellow-400/60 bg-yellow-400/20 text-yellow-400',
    WAITING: 'border-white/15 bg-white/5 text-white/30',
    WARNING: 'border-neon-red/60 bg-neon-red/20 text-neon-red shadow-[0_0_6px_rgba(255,0,60,0.4)]',
};

const STATUS_TEXT_STYLES = {
    MET: 'text-neon-green/90',
    PARTIAL: 'text-yellow-400/90',
    WAITING: 'text-white/60',
    WARNING: 'text-neon-red/90',
};

const STATUS_SYMBOLS = { MET: '✓', PARTIAL: '◑', WAITING: '○', WARNING: '⚠' };

// ─── Sub-Componente Estado ─────────────────────────────────────────────────
const StatusDot = React.memo(({ status }: { status: Condition['status'] }) => (
    <div className={`mt-0.5 flex-shrink-0 w-4 h-4 rounded-full border flex items-center justify-center text-[8px] font-black ${STATUS_STYLES[status]}`}>
        {STATUS_SYMBOLS[status]}
    </div>
));
StatusDot.displayName = 'StatusDot';

// ─── Componente Principal Optimizado ───────────────────────────────────────
const MarketContextPanel: React.FC<MarketContextPanelProps> = ({
    regime, activeStrategy, diagnostic, currentPrice, nearestSupport, nearestResistance, sessionData
}) => {

    // Memoizamos el render para evitar cálculos intensivos inútiles
    const { key, meta, conditions, d } = useMemo(() => {
        const k = (regime ?? 'UNKNOWN').toUpperCase();
        const m = REGIME_META[k] ?? REGIME_META['UNKNOWN'];
        const conds = buildConditions(
            k, diagnostic, currentPrice ?? null, nearestSupport ?? null, nearestResistance ?? null, sessionData ?? null
        );
        const diagData = diagnostic || {} as QuantDiagnostic;

        return { key: k, meta: m, conditions: conds, d: diagData };
    }, [regime, diagnostic, currentPrice, nearestSupport, nearestResistance, sessionData]);

    return (
        <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className={`flex flex-col gap-3 p-4 rounded-lg border ${meta.border} bg-black/40 backdrop-blur-sm`}
        >
            {/* Header del Panel */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BookOpen size={11} className="text-white/30" />
                    <span className="text-[9px] font-bold tracking-widest text-white/30 uppercase">Contexto Maestro en Vivo</span>
                </div>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded border ${meta.border} bg-black/50`}>
                    {meta.icon}
                    <span className={`text-[10px] font-black tracking-widest ${meta.color}`}>{meta.label}</span>
                </div>
            </div>

            <div className="border-l-2 border-white/10 pl-3">
                <p className="text-[10px] text-white/60 leading-relaxed">{meta.explanation}</p>
            </div>

            {/* Estrategia Activa */}
            {activeStrategy && (
                <div className="flex items-start gap-2">
                    <Target size={10} className={`mt-0.5 flex-shrink-0 ${meta.color}`} />
                    <p className={`text-[10px] font-bold leading-relaxed ${meta.color}`}>{activeStrategy}</p>
                </div>
            )}

            {/* Listado de Condiciones Calculadas */}
            <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-1.5 mb-1">
                    <Clock size={10} className="text-white/30" />
                    <span className="text-[9px] font-bold tracking-widest text-white/30 uppercase">Condiciones del Motor</span>
                </div>

                {conditions.map((c, i) => (
                    <details key={i} className="group">
                        <summary className="flex items-start gap-2 py-1.5 cursor-pointer hover:bg-white/[0.03] rounded px-1 list-none">
                            <StatusDot status={c.status} />
                            <div className="flex flex-col flex-1 min-w-0">
                                <span className={`text-[9px] font-bold leading-tight ${STATUS_TEXT_STYLES[c.status]}`}>
                                    {c.label}
                                </span>
                                <span className="text-[9px] font-mono text-white/40 mt-0.5">{c.currentValue}</span>
                            </div>
                            <span className="text-[8px] text-white/20 group-open:rotate-90 transition-transform mt-1 flex-shrink-0">▶</span>
                        </summary>
                        <div className="pl-6 pb-2 pr-1">
                            <p className="text-[9px] text-white/50 leading-relaxed italic border-l border-white/10 pl-2">
                                {c.meaning}
                            </p>
                        </div>
                    </details>
                ))}
            </div>

            {/* Grilla Institucional de Coordenadas SMC */}
            <div className="grid grid-cols-4 gap-1.5 pt-2 border-t border-white/5">
                {[
                    { name: 'ALIGNMENT', val: (d as any)?.htf_bias?.direction || 'ANALYZING', ok: (d as any)?.htf_bias?.direction !== 'NEUTRAL' },
                    { name: 'KILLZONE', val: sessionData?.is_killzone ? 'ACTIVE' : 'OFF', ok: sessionData?.is_killzone },
                    { name: 'RVOL', val: `${(d?.volume ?? 1).toFixed(2)}x`, ok: (d?.volume ?? 1) >= 1.5 },
                    { name: 'LIQUIDITY', val: (sessionData?.pdl_swept || sessionData?.pdh_swept) ? 'SWEPT' : 'PENDING', ok: (sessionData?.pdl_swept || sessionData?.pdh_swept) },
                ].map(({ name, val, ok }) => (
                    <div key={name} className="flex flex-col items-center gap-0.5 bg-white/[0.02] rounded py-1 px-2 border border-white/5">
                        <span className="text-[7px] text-white/25 tracking-widest uppercase font-bold">{name}</span>
                        <span className={`text-[8px] font-black tracking-tighter ${ok ? meta.color : 'text-white/40'}`}>{val}</span>
                    </div>
                ))}
            </div>
        </motion.div>
    );
};

export default React.memo(MarketContextPanel);
