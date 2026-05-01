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
    CHOPPY: { color: 'text-purple-400', bg: 'bg-purple-400/10 border-purple-400/30', glow: 'rgba(192,132,252,0.3)', label: 'CHOPPY (TRANSICIÓN)' },
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
    // Calcular distancia % entre precio y S/R
    const distToResistance = latestPrice && d.nearest_resistance
        ? ((d.nearest_resistance - latestPrice) / latestPrice * 100).toFixed(2)
        : null;
    const distToSupport = latestPrice && d.nearest_support
        ? ((latestPrice - d.nearest_support) / latestPrice * 100).toFixed(2)
        : null;


    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col overflow-hidden relative">
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

            {/* Header */}
            <div className="p-4 border-b border-white/5 flex items-center gap-2.5 bg-white/[0.01]">
                <Cpu size={15} className={d.strategy !== 'STANDBY' ? 'text-neon-green' : 'text-white/30'} />
                <h2 className="text-xs font-bold text-white/90 tracking-widest">RETINA TÉCNICA</h2>
            </div>

            <div className="p-3 flex flex-col gap-3">

                {/* 1. Radar de Sesgo Institucional (SMC) */}
                <div className={`rounded-xl p-3 border ${d.htf_bias?.direction === 'BULLISH' ? 'bg-neon-green/10 border-neon-green/30 shadow-[0_0_15px_rgba(0,255,136,0.2)]' : d.htf_bias?.direction === 'BEARISH' ? 'bg-neon-red/10 border-neon-red/30 shadow-[0_0_15px_rgba(255,0,60,0.2)]' : 'bg-white/5 border-white/10'}`}>
                    <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-1.5">SMC BIAS RADAR</span>
                    <p className={`text-sm font-black tracking-wider ${d.htf_bias?.direction === 'BULLISH' ? 'text-neon-green' : d.htf_bias?.direction === 'BEARISH' ? 'text-neon-red' : 'text-white/40'}`}>
                        {d.htf_bias?.direction || 'CALIBRANDO'} {d.htf_bias?.direction === 'BULLISH' ? '↗' : d.htf_bias?.direction === 'BEARISH' ? '↘' : '◈'}
                    </p>
                    <div className="mt-2 text-[9px] text-white/40 leading-tight">
                        {d.htf_bias?.reason || "Escaneando estructura de mercado instititucional..."}
                    </div>
                </div>

                {/* 1.5 PULSO INSTITUCIONAL (RVOL + ABSORCIÓN) - 💎 v5.7.155 Master Gold */}
                <div className="grid grid-cols-2 gap-2">
                    <div className="bg-white/[0.03] border border-white/10 rounded-xl p-2.5 flex flex-col justify-between">
                        <span className="text-[7px] font-black text-white/20 tracking-[0.2em] block mb-1 uppercase text-center">RVOL ROBUSTO</span>
                        <div className="flex flex-col items-center">
                            <span className={`text-[12px] font-black font-mono tracking-widest ${d.diagnostic?.rvol && d.diagnostic.rvol >= 1.5 ? 'text-neon-cyan' : 'text-white/60'}`}>
                                {d.diagnostic?.rvol?.toFixed(2) || '0.00'}x
                            </span>
                            <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden mt-1.5 flex gap-0.5">
                                <div className={`h-full ${d.diagnostic?.rvol && d.diagnostic.rvol >= 1.0 ? 'bg-neon-cyan' : 'bg-white/10'}`} style={{ width: '33%' }} />
                                <div className={`h-full ${d.diagnostic?.rvol && d.diagnostic.rvol >= 1.5 ? 'bg-neon-cyan' : 'bg-white/5'}`} style={{ width: '33%' }} />
                                <div className={`h-full ${d.diagnostic?.rvol && d.diagnostic.rvol >= 2.5 ? 'bg-neon-cyan animate-pulse' : 'bg-white/5'}`} style={{ width: '34%' }} />
                            </div>
                        </div>
                    </div>

                    <div className={`border rounded-xl p-2.5 flex flex-col justify-between transition-colors ${d.diagnostic?.is_absorption_elite ? 'bg-yellow-400/10 border-yellow-400/40 shadow-[0_0_15px_rgba(250,204,21,0.1)]' : 'bg-white/[0.03] border-white/10'}`}>
                        <span className="text-[7px] font-black text-white/20 tracking-[0.2em] block mb-1 uppercase text-center">ABSORCIÓN (Z)</span>
                        <div className="flex flex-col items-center">
                             <span className={`text-[12px] font-black font-mono tracking-widest ${d.diagnostic?.is_absorption_elite ? 'text-yellow-400' : 'text-white/60'}`}>
                                {d.diagnostic?.absorption_score?.toFixed(2) || '0.00'}σ
                            </span>
                            <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden mt-1.5 flex gap-0.5">
                                <div className={`h-full ${d.diagnostic?.absorption_score && d.diagnostic.absorption_score >= 1.0 ? (d.diagnostic.is_absorption_elite ? 'bg-yellow-400' : 'bg-neon-cyan/60') : 'bg-white/10'}`} style={{ width: '50%' }} />
                                <div className={`h-full ${d.diagnostic?.is_absorption_elite ? 'bg-yellow-400 shadow-[0_0_8px_rgba(250,204,21,0.4)]' : 'bg-white/10'}`} style={{ width: '50%' }} />
                            </div>
                        </div>
                    </div>
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

                {/* 3. SMC Health & Liquidity Status */}
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-2">SMC HEALTH CHECK</span>
                    <div className="space-y-3">
                        {/* OB Count */}
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] text-white/50">Order Blocks (Bull/Bear)</span>
                            <div className="flex items-center gap-1.5">
                                <span className="text-[10px] font-bold text-neon-green">{(d.smc?.order_blocks?.bullish?.length ?? 0)}</span>
                                <span className="text-white/20">/</span>
                                <span className="text-[10px] font-bold text-neon-red">{(d.smc?.order_blocks?.bearish?.length ?? 0)}</span>
                            </div>
                        </div>

                        {/* FVG Count */}
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] text-white/50">Fair Value Gaps</span>
                            <span className="text-[10px] font-bold text-yellow-400">
                                {(d.smc?.fvgs?.bullish?.length ?? 0) + (d.smc?.fvgs?.bearish?.length ?? 0)} Activos
                            </span>
                        </div>

                        {/* MS Structure */}
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] text-white/50">Estructura MS (1H)</span>
                            <span className={`text-[10px] font-bold ${d.htf_bias?.direction === 'BULLISH' ? 'text-neon-green' : 'text-neon-red'}`}>
                                {d.htf_bias?.direction || 'CALIBRANDO'}
                            </span>
                        </div>
                    </div>
                </div>

                {/* 3.5 LIQUIDEZ & SESIONES (v8.8.0) */}
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] uppercase">LIQUIDITY & SESSIONS</span>
                        {useTelemetryStore.getState().sessionData?.is_killzone && (
                            <span className="flex h-1.5 w-1.5 rounded-full bg-yellow-400 animate-pulse shadow-[0_0_5px_yellow]" />
                        )}
                    </div>
                    <div className="space-y-2">
                        {/* Asia Sweep Status */}
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] text-white/50">Asia Liquidity Sweep</span>
                            {(() => {
                                const sessions = useTelemetryStore.getState().sessionData?.sessions;
                                const swept = sessions?.asia?.swept_high || sessions?.asia?.swept_low;
                                return (
                                    <span className={`text-[10px] font-bold ${swept ? 'text-neon-cyan animate-pulse' : 'text-white/20'}`}>
                                        {swept ? 'DETECTADO ⚡' : 'ESPERANDO'}
                                    </span>
                                );
                            })()}
                        </div>
                        {/* Power Overlap Status */}
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] text-white/50">Power Overlap (NY/LON)</span>
                            <span className={`text-[10px] font-bold ${useTelemetryStore.getState().sessionData?.is_overlap ? 'text-indigo-400' : 'text-white/20'}`}>
                                {useTelemetryStore.getState().sessionData?.is_overlap ? 'ACTIVO 🔥' : 'INACTIVO'}
                            </span>
                        </div>
                    </div>
                </div>


                {/* 4. Fibonacci (si disponible) */}
                {d.fibonacci && (
                    <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                        <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-2">FIBONACCI DINÁMICO</span>
                        <div className="space-y-0.5">
                            {(() => {
                                const entries = Object.entries(d.fibonacci.levels ?? {})
                                    .filter(([k]) => ['0.236', '0.382', '0.5', '0.618', '0.66', '0.786'].includes(k))
                                    .sort(([a], [b]) => parseFloat(b) - parseFloat(a)) // DESC: nivel más alto primero
                                    .map(([level, price]) => ({ level, price: price as number }));

                                // Invertir orden si la pierna es bajista (niveles suben con el ratio)
                                const swingHigh = d.fibonacci.swing_high ?? 0;
                                const swingLow = d.fibonacci.swing_low ?? 0;
                                const isUptrend = swingLow < swingHigh;

                                // Ordenar DESC por precio (el precio más alto arriba) independiente de uptrend/downtrend
                                const sorted = [...entries].sort((a, b) => b.price - a.price);

                                const rows: React.ReactNode[] = [];
                                let priceInserted = false;

                                sorted.forEach((entry, idx) => {
                                    const { level, price } = entry;
                                    const nextEntry = sorted[idx + 1];
                                    const isGP = level === '0.618' || level === '0.66';
                                    const labelColor = isGP
                                        ? 'text-yellow-400'
                                        : level === '0.786' ? 'text-neon-red/60'
                                        : level === '0.236' ? 'text-white/30'
                                        : 'text-white/40';

                                    rows.push(
                                        <div key={level} className={`flex items-center justify-between rounded px-1.5 py-0.5 ${isGP ? 'bg-yellow-400/5' : ''}`}>
                                            <span className={`text-[9px] font-bold ${labelColor}`}>
                                                {level} {isGP ? '★GP' : ''}
                                            </span>
                                            <span className={`text-[9px] font-mono ${isGP ? 'text-yellow-400/90' : 'text-white/60'}`}>{fmt(price, '$', 0)}</span>
                                        </div>
                                    );

                                    // Insertar línea del precio si cae entre este nivel y el siguiente
                                    if (!priceInserted && latestPrice && nextEntry) {
                                        const isBelow = latestPrice <= price && latestPrice > nextEntry.price;
                                        if (isBelow) {
                                            const distToAbove = ((price - latestPrice) / latestPrice * 100).toFixed(2);
                                            const distToBelow = ((latestPrice - nextEntry.price) / latestPrice * 100).toFixed(2);
                                            priceInserted = true;
                                            rows.push(
                                                <div key="current-price" className="flex items-center justify-between bg-neon-cyan/10 border border-neon-cyan/30 rounded px-1.5 py-1 my-0.5 shadow-[0_0_8px_rgba(0,229,255,0.2)]">
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-neon-cyan text-[10px]">▶</span>
                                                        <span className="text-[9px] font-bold text-neon-cyan">PRECIO</span>
                                                    </div>
                                                    <div className="text-right">
                                                        <span className="text-[10px] font-mono font-black text-neon-cyan">{fmt(latestPrice, '$', 0)}</span>
                                                        <p className="text-[7px] text-white/30">↑{distToAbove}% · ↓{distToBelow}%</p>
                                                    </div>
                                                </div>
                                            );
                                        }
                                    }

                                    // Edge case: precio por debajo de todos los niveles
                                    if (!priceInserted && latestPrice && idx === sorted.length - 1 && latestPrice <= price) {
                                        priceInserted = true;
                                        rows.push(
                                            <div key="current-price" className="flex items-center justify-between bg-neon-cyan/10 border border-neon-cyan/30 rounded px-1.5 py-1 my-0.5">
                                                <div className="flex items-center gap-1">
                                                    <span className="text-neon-cyan text-[10px]">▶</span>
                                                    <span className="text-[9px] font-bold text-neon-cyan">PRECIO</span>
                                                </div>
                                                <span className="text-[10px] font-mono font-black text-neon-cyan">{fmt(latestPrice, '$', 0)}</span>
                                            </div>
                                        );
                                    }
                                });

                                // Edge case: precio por encima de todos los niveles
                                if (!priceInserted && latestPrice) {
                                    rows.unshift(
                                        <div key="current-price" className="flex items-center justify-between bg-neon-cyan/10 border border-neon-cyan/30 rounded px-1.5 py-1 my-0.5">
                                            <div className="flex items-center gap-1">
                                                <span className="text-neon-cyan text-[10px]">▶</span>
                                                <span className="text-[9px] font-bold text-neon-cyan">PRECIO</span>
                                            </div>
                                            <span className="text-[10px] font-mono font-black text-neon-cyan">{fmt(latestPrice, '$', 0)}</span>
                                        </div>
                                    );
                                }

                                return rows;
                            })()}
                            <div className="text-[8px] text-white/20 pt-1 border-t border-white/5 mt-1">
                                Swing: {fmt(d.fibonacci.swing_low, '$', 0)} → {fmt(d.fibonacci.swing_high, '$', 0)}
                            </div>
                        </div>
                    </div>
                )}


                {/* 5. Estrategia activa */}
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[9px] font-bold text-white/40 tracking-[0.2em] block mb-2">ESTRATEGIA ENRUTADA</span>
                    <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full flex-shrink-0 ${d.strategy && !d.strategy.toUpperCase().includes('STANDBY') ? 'bg-neon-green shadow-[0_0_8px_rgba(0,255,65,0.8)]' : 'bg-yellow-400/70 shadow-[0_0_8px_rgba(250,204,21,0.5)]'}`} />
                        <span className={`text-[10px] font-bold leading-snug ${d.strategy && d.strategy.toUpperCase().includes('STANDBY') ? 'text-yellow-400/90' : 'text-white/80'}`}>{d.strategy}</span>
                    </div>

                    {/* Explicación institucional del Standby por Choppiness */}
                    {d.strategy?.includes('Choppiness') && (
                        <div className="mt-2 bg-purple-400/10 border border-purple-400/20 rounded p-2 flex items-start gap-1.5">
                            <AlertTriangle size={10} className="text-purple-400 mt-0.5 flex-shrink-0" />
                            <p className="text-[8.5px] text-purple-400/80 leading-tight">
                                Acción de precio sucia. Volatilidad sin tendencia clara (Medias grandes desalineadas). El motor pausa operativas para proteger capital institucional.
                            </p>
                        </div>
                    )}
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
