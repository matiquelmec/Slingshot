'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Cpu, TrendingUp, TrendingDown, Minus, AlertTriangle, Target } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const REGIME_META: Record<string, { color: string; bg: string; glow: string; label: string }> = {
    MARKUP: { color: 'text-neon-green', bg: 'bg-neon-green/10 border-neon-green/30', glow: 'rgba(0,255,65,0.3)', label: 'MARKUP ↗' },
    MARKDOWN: { color: 'text-neon-red', bg: 'bg-neon-red/10 border-neon-red/30', glow: 'rgba(255,0,60,0.3)', label: 'MARKDOWN ↘' },
    ACCUMULATION: { color: 'text-yellow-400', bg: 'bg-yellow-400/10 border-yellow-400/30', glow: 'rgba(250,204,21,0.3)', label: 'ACUMULACIÓN' },
    DISTRIBUTION: { color: 'text-orange-400', bg: 'bg-orange-400/10 border-orange-400/30', glow: 'rgba(251,146,60,0.3)', label: 'DISTRIBUCIÓN' },
    RANGING: { color: 'text-neon-cyan', bg: 'bg-neon-cyan/10 border-neon-cyan/30', glow: 'rgba(0,229,255,0.3)', label: 'RANGING' },
    UNKNOWN: { color: 'text-white/40', bg: 'bg-white/5 border-white/10', glow: 'transparent', label: 'CALIBRANDO' },
};

function fmt(val: number | null, prefix = '$', dp = 0): string {
    if (val == null) return '—';
    return prefix + val.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

function pct(val: number | null): string {
    if (val == null) return '—';
    return (val * 100).toFixed(2) + '%';
}

function SlopeIcon({ slope }: { slope: number | null }) {
    if (slope == null) return <Minus size={12} className="text-white/30" />;
    if (slope > 0) return <TrendingUp size={12} className="text-neon-green" />;
    if (slope < 0) return <TrendingDown size={12} className="text-neon-red" />;
    return <Minus size={12} className="text-white/30" />;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function QuantDiagnosticPanel() {
    const { tacticalDecision, latestPrice } = useTelemetryStore();
    const d = tacticalDecision;

    const regimeKey = Object.keys(REGIME_META).find(k => d.regime.includes(k)) ?? 'UNKNOWN';
    const regimeMeta = REGIME_META[regimeKey];

    // Calcular distancia % entre precio y S/R
    const distToResistance = latestPrice && d.nearest_resistance
        ? ((d.nearest_resistance - latestPrice) / latestPrice * 100).toFixed(2)
        : null;
    const distToSupport = latestPrice && d.nearest_support
        ? ((latestPrice - d.nearest_support) / latestPrice * 100).toFixed(2)
        : null;

    // Squeeze detection
    const isSqueeze = d.bb_width != null && d.bb_width_mean != null && d.bb_width < (d.bb_width_mean * 0.8);
    const bbPct = d.bb_width && d.bb_width_mean
        ? Math.min((d.bb_width / (d.bb_width_mean * 1.5)) * 100, 100)
        : 0;

    // SMA alignment
    const smaAligned = d.sma_fast != null && d.sma_slow != null;
    const smaBullish = smaAligned && d.sma_fast! > d.sma_slow!;

    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col overflow-hidden relative">
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

            {/* Header */}
            <div className="p-4 border-b border-white/5 flex items-center gap-2.5 bg-white/[0.01]">
                <Cpu size={15} className={d.strategy !== 'STANDBY' ? 'text-neon-green' : 'text-white/30'} />
                <h2 className="text-xs font-bold text-white/90 tracking-widest">RETINA TÉCNICA</h2>
            </div>

            <div className="p-3 flex flex-col gap-3">

                {/* 1. Radar de Régimen Wyckoff */}
                <div className={`rounded-xl p-3 border ${regimeMeta.bg}`} style={{ boxShadow: `0 0 20px ${regimeMeta.glow}` }}>
                    <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-1.5">RÉGIMEN WYCKOFF</span>
                    <p className={`text-sm font-black tracking-wider ${regimeMeta.color}`}>{regimeMeta.label}</p>
                    {/* Barra de extensión del precio */}
                    {d.dist_to_sma200 != null && (
                        <div className="mt-2">
                            <div className="flex justify-between text-[9px] text-white/30 mb-1">
                                <span>Dist. SMA200</span>
                                <span className={d.dist_to_sma200 > 0 ? 'text-neon-green/70' : 'text-neon-red/70'}>
                                    {d.dist_to_sma200 > 0 ? '+' : ''}{pct(d.dist_to_sma200)}
                                </span>
                            </div>
                            <div className="h-1 bg-black/40 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-1000 ${d.dist_to_sma200 > 0 ? 'bg-neon-green/60' : 'bg-neon-red/60'}`}
                                    style={{ width: `${Math.min(Math.abs(d.dist_to_sma200) / 0.10 * 100, 100)}%` }}
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* 2. Topografía Algorítmica — todos los key_levels */}
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-2">TOPOGRAFÍA S/R</span>
                    <div className="space-y-1">

                        {/* Resistencias (encima del precio, más cercana primera) */}
                        {[...d.key_levels.resistances].reverse().map((r, idx, arr) => {
                            const rank = arr.length - idx;
                            const distPct = latestPrice ? ((r.price - latestPrice) / latestPrice * 100).toFixed(2) : null;
                            const isRR = r.origin === 'ROLE_REVERSAL';
                            const dotColor = isRR ? 'bg-orange-400' : 'bg-neon-red';
                            const textColor = isRR
                                ? (r.touches >= 4 ? 'text-orange-400' : r.touches >= 2 ? 'text-orange-400/70' : 'text-orange-400/40')
                                : (r.touches >= 4 ? 'text-neon-red' : r.touches >= 2 ? 'text-neon-red/70' : 'text-neon-red/40');
                            return (
                                <div key={`res-${rank}`} className="flex items-center justify-between">
                                    <div className="flex items-center gap-1.5">
                                        <div className={`w-1.5 h-1.5 rounded-full ${dotColor}`}
                                            style={{ opacity: r.touches >= 4 ? 1 : r.touches >= 2 ? 0.6 : 0.3 }} />
                                        <span className={`text-[9px] font-bold ${textColor}`}>
                                            R{rank} <span className="text-white/20 font-normal">({r.touches}t)</span>
                                            {isRR && <span className="text-orange-400/70 ml-1">↩</span>}
                                            {r.ob_confluence && <span className="text-yellow-400/80 ml-1">★</span>}
                                            {r.mtf_confluence && <span className="text-neon-cyan/80 ml-1">◈</span>}
                                            {(r.volume_score ?? 1) > 1.5 && <span className="text-neon-cyan/80 ml-1">⚡</span>}
                                        </span>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[10px] font-black text-white/70 font-mono">{fmt(r.price)}</p>
                                        {distPct && <p className="text-[8px] text-neon-red/50">+{distPct}%</p>}
                                    </div>
                                </div>
                            );
                        })}

                        {/* Precio actual — separador */}
                        {latestPrice && (
                            <div className="flex items-center justify-between border-y border-white/5 py-1 my-1">
                                <span className="text-[9px] text-white/30">PRECIO ACTUAL</span>
                                <span className="text-[10px] font-bold text-neon-cyan/70 font-mono">{fmt(latestPrice, '$', 2)}</span>
                            </div>
                        )}

                        {/* Soportes (debajo del precio, más cercano primero) */}
                        {d.key_levels.supports.map((s, idx) => {
                            const rank = idx + 1;
                            const distPct = latestPrice ? ((latestPrice - s.price) / latestPrice * 100).toFixed(2) : null;
                            const isRR = s.origin === 'ROLE_REVERSAL';
                            const dotColor = isRR ? 'bg-yellow-400' : 'bg-neon-green';
                            const textColor = isRR
                                ? (s.touches >= 4 ? 'text-yellow-400' : s.touches >= 2 ? 'text-yellow-400/70' : 'text-yellow-400/40')
                                : (s.touches >= 4 ? 'text-neon-green' : s.touches >= 2 ? 'text-neon-green/70' : 'text-neon-green/40');
                            return (
                                <div key={`sup-${rank}`} className="flex items-center justify-between">
                                    <div className="flex items-center gap-1.5">
                                        <div className={`w-1.5 h-1.5 rounded-full ${dotColor}`}
                                            style={{ opacity: s.touches >= 4 ? 1 : s.touches >= 2 ? 0.6 : 0.3 }} />
                                        <span className={`text-[9px] font-bold ${textColor}`}>
                                            S{rank} <span className="text-white/20 font-normal">({s.touches}t)</span>
                                            {isRR && <span className="text-yellow-400/70 ml-1">↩</span>}
                                            {s.ob_confluence && <span className="text-yellow-400/80 ml-1">★</span>}
                                            {s.mtf_confluence && <span className="text-neon-cyan/80 ml-1">◈</span>}
                                            {(s.volume_score ?? 1) > 1.5 && <span className="text-neon-cyan/80 ml-1">⚡</span>}
                                        </span>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[10px] font-black text-white/70 font-mono">{fmt(s.price)}</p>
                                        {distPct && <p className="text-[8px] text-neon-green/50">-{distPct}%</p>}
                                    </div>
                                </div>
                            );
                        })}

                        {/* Fallback si no hay datos */}
                        {d.key_levels.resistances.length === 0 && d.key_levels.supports.length === 0 && (
                            <p className="text-[9px] text-white/20 text-center py-2">Calibrando niveles...</p>
                        )}
                    </div>
                </div>

                {/* 3. Indicadores Internos */}
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-2">INDICADORES INTERNOS</span>
                    <div className="space-y-2.5">
                        {/* SMA Alignment */}
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] text-white/50">SMA 50/200</span>
                            <div className="flex items-center gap-1.5">
                                <SlopeIcon slope={d.sma_slow_slope} />
                                <span className={`text-[10px] font-bold ${smaAligned ? (smaBullish ? 'text-neon-green' : 'text-neon-red') : 'text-white/30'}`}>
                                    {smaAligned ? (smaBullish ? 'ALCISTA' : 'BAJISTA') : 'CALIBRANDO'}
                                </span>
                            </div>
                        </div>
                        {/* BB Squeeze */}
                        <div>
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-[10px] text-white/50">Volatilidad BB</span>
                                <span className={`text-[10px] font-bold ${isSqueeze ? 'text-yellow-400' : 'text-neon-cyan/70'}`}>
                                    {d.bb_width != null ? (isSqueeze ? '⚠ SQUEEZE' : 'EXPANSIÓN') : '—'}
                                </span>
                            </div>
                            <div className="h-1 bg-black/40 rounded-full overflow-hidden">
                                <motion.div
                                    animate={{ width: `${bbPct}%` }}
                                    transition={{ duration: 0.8 }}
                                    className={`h-full rounded-full ${isSqueeze ? 'bg-yellow-400/70' : 'bg-neon-cyan/50'}`}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* 4. Estrategia activa */}
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-2">ESTRATEGIA ENRUTADA</span>
                    <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full flex-shrink-0 ${d.strategy !== 'STANDBY' ? 'bg-neon-green shadow-[0_0_8px_rgba(0,255,65,0.8)]' : 'bg-white/20'}`} />
                        <span className="text-[10px] text-white/80 font-bold leading-snug">{d.strategy}</span>
                    </div>
                    {d.signals.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-white/5">
                            <div className="flex items-center gap-1 mb-1">
                                <Target size={10} className="text-yellow-400" />
                                <span className="text-[9px] font-bold text-yellow-400">SEÑAL RECIENTE</span>
                            </div>
                            <p className="text-[10px] text-white/60 font-mono">{d.signals[d.signals.length - 1]?.type ?? ''}</p>
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
}
