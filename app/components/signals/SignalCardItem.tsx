'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Signal } from '../../types/signal';
import { getSignalLifecycle, getSignalStyle } from '../../utils/signalLogic';

interface SignalCardItemProps {
    signal: Signal;
    currentPrice: number | null;
}

const formatTime = (ts: string) => {
    try {
        const date = new Date(ts);
        return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
        return ts?.split(' ')[1] || ts;
    }
};

const SignalCardItem: React.FC<SignalCardItemProps> = ({ signal, currentPrice }) => {

    // Memoizamos fuertemente el ciclo de vida. Solo recalcula si el currentPrice hace que evalúe distinto,
    // o si pasa mucha diferencia de Date.now()
    const { lifecycle, style } = useMemo(() => {
        const now = Date.now();
        const lc = getSignalLifecycle(signal, currentPrice, now);
        const st = getSignalStyle(signal.type);
        return { lifecycle: lc, style: st };
    }, [signal, currentPrice]); // Recalcula si el target signal muta o el precio toca su umbral

    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            className={`flex flex-col rounded border px-4 py-3 ${lifecycle.bgColor} transition-all`}
        >
            {/* ── Fila 1: Tiempo + Tipo + Estado ── */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-white/40">{formatTime(signal.timestamp)}</span>
                    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${style.bg} ${style.border}`}>
                        <span className={`text-[9px] font-bold tracking-wider ${style.color} ${style.shadow}`}>
                            {signal.type.replace('🟢', '').replace('🔴', '').trim()}
                        </span>
                    </div>
                </div>
                <span className={`text-[9px] font-bold tracking-widest ${lifecycle.color}`}>
                    {lifecycle.label}
                </span>
            </div>

            {/* ── Fila 2: Estado Educativo ── */}
            <div className={`text-[9px] font-mono px-2 py-1.5 rounded border border-white/5 bg-black/30 mb-2 ${lifecycle.color} leading-relaxed`}>
                {lifecycle.reason}
                {lifecycle.countdown && (
                    <span className="block mt-0.5 text-white/30">{lifecycle.countdown}</span>
                )}
            </div>

            {/* ── Fila 3: Zonas y Target ── */}
            <div className="grid grid-cols-3 gap-2 text-[9px] font-mono mb-2">
                <div className="flex flex-col gap-0.5 bg-white/[0.02] rounded px-2 py-1 border border-white/5">
                    <span className="text-white/30 text-[8px] tracking-widest">ZONA ENTRADA</span>
                    {signal.entry_zone_top && signal.entry_zone_bottom ? (
                        <span className="text-white/80 font-bold">
                            ${signal.entry_zone_bottom.toLocaleString(undefined, { maximumFractionDigits: 0 })} – ${signal.entry_zone_top.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </span>
                    ) : (
                        <span className="text-white/60 font-bold">${signal.price?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    )}
                </div>
                <div className="flex flex-col gap-0.5 bg-neon-red/5 rounded px-2 py-1 border border-neon-red/10">
                    <span className="text-neon-red/50 text-[8px] tracking-widest">⛔ STOP LOSS</span>
                    <span className="text-neon-red/90 font-bold">${signal.stop_loss?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex flex-col gap-0.5 bg-neon-green/5 rounded px-2 py-1 border border-neon-green/10">
                    <span className="text-neon-green/50 text-[8px] tracking-widest">🎯 TARGET 3R</span>
                    <span className="text-neon-green/90 font-bold">${signal.take_profit_3r?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
            </div>

            {/* ── Fila 4: Matemáticas de Riesgo ── */}
            <div className="flex items-center flex-wrap gap-1 mb-2">
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-neon-cyan/80 bg-neon-cyan/10 border border-neon-cyan/20 rounded">
                    RISK: {signal.risk_pct ? `${signal.risk_pct}%` : 'N/A'} ({signal.risk_usd || 'N/A'})
                </span>
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-[#d4af37] bg-[#d4af37]/10 border border-[#d4af37]/20 rounded">
                    {signal.leverage ? `${signal.leverage}x` : '1x'} LEV
                </span>
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/70 bg-white/10 border border-white/20 rounded">
                    SIZE: ${signal.position_size || '---'}
                </span>
                {signal.expiry_candles && (
                    <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/30 bg-white/5 border border-white/10 rounded">
                        VÁLIDA {signal.expiry_candles} velas ({(signal.expiry_candles * (signal.interval_minutes || 15))}min)
                    </span>
                )}
                {signal.trigger?.split('+').map((badge: string, i: number) => (
                    <span key={i} className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/40 bg-white/5 border border-white/10 rounded">
                        {badge.trim()}
                    </span>
                ))}
            </div>

            {/* ── Fila 5: Puntos de Confluencia (Institutional Score) ── */}
            {signal.confluence && (
                <div className="border-t border-white/5 pt-2 flex flex-col gap-1.5">
                    <div className="flex items-center gap-3">
                        <div className="flex-1 h-1.5 bg-black/60 rounded-full overflow-hidden border border-white/10">
                            <div
                                className={`h-full rounded-full transition-all duration-700 ${signal.confluence.score >= 70 ? 'bg-neon-green shadow-[0_0_6px_rgba(0,255,65,0.6)]' :
                                        signal.confluence.score >= 50 ? 'bg-neon-cyan shadow-[0_0_6px_rgba(0,229,255,0.6)]' :
                                            signal.confluence.score >= 30 ? 'bg-yellow-400' : 'bg-neon-red'
                                    }`}
                                style={{ width: `${signal.confluence.score}%` }}
                            />
                        </div>
                        <span className={`text-[10px] font-black tracking-widest whitespace-nowrap ${signal.confluence.score >= 70 ? 'text-neon-green' :
                                signal.confluence.score >= 50 ? 'text-neon-cyan' :
                                    signal.confluence.score >= 30 ? 'text-yellow-400' : 'text-neon-red'
                            }`}
                        >
                            {signal.confluence.score}/100 {signal.confluence.conviction}
                        </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                        {signal.confluence.checklist?.map((item, i) => (
                            <span key={i} className={`px-1.5 py-0.5 text-[8px] font-bold tracking-wider rounded border ${item.status === 'CONFIRMADO' ? 'text-neon-green/90 bg-neon-green/10 border-neon-green/20' :
                                    item.status === 'PARCIAL' ? 'text-yellow-400/90 bg-yellow-400/10 border-yellow-400/20' :
                                        'text-white/30 bg-white/5 border-white/10'
                                }`} title={item.detail}>
                                {item.status === 'CONFIRMADO' ? '✓' : item.status === 'PARCIAL' ? '◑' : '✗'} {item.factor}
                            </span>
                        ))}
                    </div>
                    {signal.confluence.reasoning && (
                        <p className="text-[9px] text-white/40 italic font-mono leading-relaxed pl-1 border-l border-white/10">
                            {signal.confluence.reasoning}
                        </p>
                    )}
                </div>
            )}
        </motion.div>
    );
};

export default React.memo(SignalCardItem);
