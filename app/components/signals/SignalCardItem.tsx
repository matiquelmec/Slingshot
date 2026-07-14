'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Signal } from '../../types/signal';
import { useTelemetryStore } from '../../store/telemetryStore';
import { getSignalLifecycle, getSignalStyle } from '../../utils/signalLogic';
import { formatCurrency } from '../../utils/formatters';

interface SignalCardItemProps {
    signal: Signal;
    currentPrice: number | null;
}

const formatTime = (ts: any) => {
    try {
        if (!ts) return '---';
        
        let date: Date;
        // Si es un número (Unix Timestamp)
        if (typeof ts === 'number') {
            const unitMultiplier = ts < 2e9 ? 1000 : 1;
            date = new Date(ts * unitMultiplier);
        } else if (!isNaN(Number(ts))) {
            // Si es un string que representa un número
            const n = Number(ts);
            const unitMultiplier = n < 2e9 ? 1000 : 1;
            date = new Date(n * unitMultiplier);
        } else {
            // Si es una fecha ISO o similar
            date = new Date(ts);
        }

        if (isNaN(date.getTime())) {
            // Fallback: intentar extraer hora de un string con espacio
            return ts.toString().includes(' ') ? ts.toString().split(' ')[1] : ts.toString();
        }

        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return ts?.toString() || '---';
    }
};

const getStatusType = (status: string): 'success' | 'warning' | 'info' => {
    if (!status) return 'info';
    const s = status.toUpperCase();
    if (
        s.includes('CONFIRMADO') ||
        s === 'ELITE' ||
        s === 'ACTIVO' ||
        s === 'APROBADO' ||
        s === 'FRESCO' ||
        s === 'FAVORABLE' ||
        s === 'ALINEADO' ||
        s === 'INSTITUCIONAL'
    ) {
        return 'success';
    }
    if (
        s === 'PARCIAL' ||
        s === 'VOLÁTIL' ||
        s === 'DECAYENDO' ||
        s.includes('PRECAUCIÓN') ||
        s.includes('ALERTA')
    ) {
        return 'warning';
    }
    return 'info';
};

const SignalCardItem: React.FC<SignalCardItemProps> = ({ signal, currentPrice }) => {
    // Consumimos el mapa de precios globales para hidratación específica por activo (v5.8.0)
    const latestPrices = useTelemetryStore(state => state.latestPrices);
    const effectivePrice = useMemo(() => {
        return latestPrices[signal.asset] || currentPrice;
    }, [latestPrices, signal.asset, currentPrice]);

    // Memoizamos fuertemente el ciclo de vida. Solo recalcula si el effectivePrice hace que evalúe distinto,
    const { lifecycle, style } = useMemo(() => {
        const now = Date.now();
        const lc = getSignalLifecycle(signal, effectivePrice, now);
        const st = getSignalStyle(signal.type);
        return { lifecycle: lc, style: st };
    }, [signal, effectivePrice]); 

    const isBlocked = useMemo(() => {
        const validStatuses = ['ACTIVE', 'APPROVED', 'PENDING', 'FILLED', 'CLOSED_TP_MAX', 'STOPPED_OUT'];
        return signal.status && !validStatuses.includes(signal.status);
    }, [signal.status]);

    const isChasing = useMemo(() => {
        // Detectar si la señal tiene alguna alerta del OTE Watchdog en el checklist
        return signal.confluence?.checklist?.some(item => item.factor === 'OTE Watchdog') || false;
    }, [signal.confluence]);

    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            className={`flex flex-col rounded border px-4 py-3 ${lifecycle.bgColor} transition-all`}
        >
            {/* ── Fila 1: Tiempo + Tipo + Estado + Sesión ── */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-white/40">{formatTime(signal.created_at || signal.timestamp)}</span>
                    {signal.asset && (
                        <span className="text-[10px] font-black text-neon-cyan tracking-tighter bg-neon-cyan/5 px-1.5 py-0.5 rounded border border-neon-cyan/20">
                            {signal.asset}
                        </span>
                    )}
                    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${style.bg} ${style.border}`}>
                        <span className={`text-[9px] font-bold tracking-wider ${style.color} ${style.shadow}`}>
                            {signal.type.replace('🟢', '').replace('🔴', '').trim()}
                        </span>
                    </div>

                    {/* Badge de Sesión de Origen si existe */}
                    {signal.session && signal.session !== 'UNKNOWN' && (
                        <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-white/10 bg-white/5 text-white/50">
                            🕒 {signal.session}
                        </span>
                    )}

                    {/* Badge OTE Watchdog Alert */}
                    {isChasing && (
                        <span className="text-[8px] font-mono px-1.5 py-0.5 rounded border border-amber-500/20 bg-amber-500/10 text-amber-400 font-bold">
                            ⚠️ OTE CHASING
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {/* Badge de Agrupación (Deduplicador) */}
                    {(signal as any).groupCount > 1 && (
                        <span className="text-[8px] font-mono bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded font-black tracking-wide animate-pulse">
                            📂 {(signal as any).groupCount} EVENTOS SIMILARES
                        </span>
                    )}
                    <span className={`text-[9px] font-bold tracking-widest ${lifecycle.color}`}>
                        {lifecycle.label}
                    </span>
                </div>
            </div>

            {/* ── Fila 2: Estado Educativo o Reporte de Auditoría ── */}
            <div className={`text-[9px] font-mono px-2 py-1.5 rounded border border-white/5 bg-black/30 mb-2 ${lifecycle.color} leading-relaxed relative overflow-hidden group`}>
                {isBlocked && (
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500/30 group-hover:bg-red-500/60 transition-all" />
                )}
                <div className="flex items-start gap-2">
                    <span className="opacity-80 font-bold uppercase tracking-widest">
                        {isChasing ? 'OTE VETO' : lifecycle.label}:
                    </span>
                    <div className="flex-1 whitespace-pre-wrap">
                        {isChasing 
                            ? "Setup rechazado por OTE Watchdog: el precio se encuentra fuera de la zona de descuento/premium ideal (Golden Pocket). Persiguiendo precio." 
                            : lifecycle.reason}
                    </div>
                </div>
                {lifecycle.countdown && (
                    <span className="block mt-1 text-white/30 border-t border-white/5 pt-1 italic">{lifecycle.countdown}</span>
                )}
            </div>

            {/* ── SECCIÓN DE EVIDENCIA AUDITORÍA (Solo para bloqueadas) ── */}
            {isBlocked && (
                <div className="mb-2 px-2 py-1.5 bg-red-500/5 rounded border border-red-500/10 text-[8px] font-mono">
                    <span className="text-red-400 font-bold tracking-widest uppercase mb-1 block">🛡️ AUDIT EVIDENCE</span>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-1 opacity-70">
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                            <span className="text-white/40">Status:</span>
                            <span className="text-red-300 font-bold">{signal.status ? signal.status.replace('BLOCKED_BY_', '') : ''}</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                            <span className="text-white/40">Direction:</span>
                            <span className="text-white/80">{signal.type?.includes('LONG') ? 'LONG' : 'SHORT'}</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                            <span className="text-white/40">Confluence:</span>
                            <span className={signal.confluence?.score && signal.confluence.score >= 70 ? 'text-neon-green' : 'text-white/80'}>
                                {signal.confluence?.score || signal.confluence_score || 0}%
                            </span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                            <span className="text-white/40">R:R Ratio:</span>
                            <span className={signal.rr_ratio && signal.rr_ratio >= 1.8 ? 'text-neon-cyan' : 'text-neon-red'}>
                                {signal.rr_ratio || 'N/A'}
                            </span>
                        </div>
                    </div>
                </div>
            )}

            {/* ── SECCIÓN SOVEREIGN AI AUDIT (v13.0) ── */}
            {signal.ai_audit && (
                <div className={`mb-2 px-2 py-1.5 rounded border ${signal.ai_audit.approved ? 'bg-neon-cyan/5 border-neon-cyan/20' : 'bg-red-500/5 border-red-500/20'} text-[8px] font-mono`}>
                    <div className="flex items-center justify-between mb-1">
                        <span className={`${signal.ai_audit.approved ? 'text-neon-cyan' : 'text-red-400'} font-bold tracking-widest uppercase`}>
                            🤖 SOVEREIGN AI NARRATIVE AUDIT
                        </span>
                        <span className={`px-1 rounded ${signal.ai_audit.approved ? 'bg-neon-cyan/20 text-neon-cyan' : 'bg-red-500/20 text-red-400'} font-black`}>
                            {signal.ai_audit.verdict}
                        </span>
                    </div>
                    <p className="text-white/60 italic leading-relaxed">
                        "{signal.ai_audit.ai_reasoning}"
                    </p>
                    <div className="mt-1 flex items-center gap-2 text-[7px] text-white/30">
                        <span>Confidence: {(signal.ai_audit.confidence * 100).toFixed(0)}%</span>
                        <span className="w-1 h-1 bg-white/20 rounded-full" />
                        <span>Model: Local gemma3</span>
                    </div>
                </div>
            )}

            {/* ── Fila 3: Zonas y Target ── */}
            <div className="grid grid-cols-4 gap-2 text-[9px] font-mono mb-2">
                <div className="flex flex-col gap-0.5 bg-white/[0.02] rounded px-2 py-1 border border-white/5">
                    <span className="text-white/30 text-[8px] tracking-widest uppercase">Entry</span>
                    {signal.entry_zone_top && signal.entry_zone_bottom ? (
                        <span className="text-white/80 font-bold">
                            {formatCurrency(signal.entry_zone_bottom)} – {formatCurrency(signal.entry_zone_top)}
                        </span>
                    ) : (
                        <span className="text-white/60 font-bold">{formatCurrency(signal.price)}</span>
                    )}
                </div>
                <div className="flex flex-col gap-0.5 bg-red-500/10 rounded px-2 py-1 border border-red-500/30">
                    <span className="text-red-400 text-[8px] tracking-widest uppercase font-black">Stop Loss</span>
                    <span className="text-red-500 font-black">{formatCurrency(signal.stop_loss)}</span>
                </div>
                <div className="flex flex-col gap-0.5 bg-green-500/10 rounded px-2 py-1 border border-green-500/30 col-span-2">
                    <div className="flex justify-between items-center mb-0.5">
                        <span className="text-green-400 text-[8px] tracking-widest uppercase font-black">Take Profit Targets (1,2,3)</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-green-300 text-[8px] font-bold">T1:</span>
                        <span className="text-green-400 font-black">{formatCurrency(signal.tp1) || '---'}</span>
                        <span className="text-green-300 text-[8px] font-bold ml-1">T2:</span>
                        <span className="text-green-400 font-black">{formatCurrency(signal.tp2) || '---'}</span>
                        <span className="text-green-500 text-[10px]">⚡</span>
                        <span className="text-green-300 font-black">{formatCurrency(signal.tp3 || signal.take_profit_3r) || '---'}</span>
                    </div>
                </div>
            </div>

            {/* ── Fila 4: Matemáticas de Riesgo ── */}
            <div className="flex items-center flex-wrap gap-1 mb-2">
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-neon-cyan/80 bg-neon-cyan/10 border border-neon-cyan/20 rounded flex items-center gap-1">
                    RISK: {signal.risk_pct ? `${signal.risk_pct}%` : 'N/A'} {signal.risk_amount_usdt || signal.risk_usd ? `($${signal.risk_amount_usdt || signal.risk_usd})` : ''}
                    {signal.risk_pct && signal.risk_pct !== 1.0 && (
                        <span className="text-[7px] opacity-60 ml-1 border-l border-neon-cyan/20 pl-1 uppercase">Dynamic Scale</span>
                    )}
                </span>
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-[#d4af37] bg-[#d4af37]/10 border border-[#d4af37]/20 rounded">
                    {signal.leverage ? `${signal.leverage}x` : '1x'} LEV
                </span>
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/70 bg-white/10 border border-white/20 rounded">
                    SIZE: {signal.position_size_usdt || signal.position_size ? `$${signal.position_size_usdt || signal.position_size}` : '---'}
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

            {/* ── Fila 5: Ejecución Institucional (MT5 / Bitunix) ── */}
            <div className="flex flex-col gap-2 mb-2">
                {/* Panel FTMO */}
                {signal.ftmo_order && (
                    <div className="px-2 py-2 bg-gradient-to-r from-neon-cyan/10 to-transparent rounded border border-neon-cyan/20 text-[9px] font-mono shadow-[inset_0_0_10px_rgba(0,229,255,0.05)]">
                        <div className="flex items-center justify-between mb-1.5">
                            <span className="text-neon-cyan font-black tracking-widest uppercase flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 bg-neon-cyan rounded-full animate-pulse" />
                            EJECUCIÓN FTMO (MT5)
                            </span>
                            <span className="text-white/40 text-[7px]">$100K FUNDING</span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                            <div className="flex justify-between items-center border-b border-white/5 pb-1">
                                <span className="text-white/30 uppercase text-[7.5px]">Symbol:</span>
                                <span className="text-white font-bold">{signal.ftmo_order.symbol}</span>
                            </div>
                            <div className="flex justify-between items-center border-b border-white/5 pb-1">
                                <span className="text-white/30 uppercase text-[7.5px]">Volume:</span>
                                <span className="text-neon-cyan font-black tracking-tighter text-[11px] bg-neon-cyan/10 px-1 rounded">
                                    {signal.ftmo_order.volume.toFixed(2)} Lots
                                </span>
                            </div>
                            <div className="flex justify-between items-center border-b border-white/5 pb-1">
                                <span className="text-white/30 uppercase text-[7.5px]">Mode:</span>
                                <span className={signal.ftmo_order.action === 'BUY' ? 'text-neon-green font-bold' : 'text-neon-red font-bold'}>
                                    {signal.ftmo_order.action} LIMIT
                                </span>
                            </div>
                            <div className="flex justify-between items-center border-b border-white/5 pb-1">
                                <span className="text-white/30 uppercase text-[7.5px]">Magic ID:</span>
                                <span className="text-white/60">{signal.ftmo_order.magic}</span>
                            </div>
                        </div>
                    </div>
                )}

                {/* Panel Bitunix */}
                {signal.bitunix_order && (
                    <div className="px-2 py-2 bg-gradient-to-r from-purple-500/10 to-transparent rounded border border-purple-500/20 text-[9px] font-mono shadow-[inset_0_0_10px_rgba(168,85,247,0.05)]">
                        <div className="flex items-center justify-between mb-1.5">
                            <span className="text-purple-400 font-black tracking-widest uppercase flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" />
                            BITUNIX PERPETUALS
                            </span>
                            <span className="text-white/40 text-[7px]">ISOLATED MARGIN</span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                            <div className="flex justify-between items-center border-b border-white/5 pb-1">
                                <span className="text-white/30 uppercase text-[7.5px]">Quantity:</span>
                                <span className="text-purple-300 font-bold">{signal.bitunix_order.quantity} {signal.bitunix_order.symbol.replace('USDT','')}</span>
                            </div>
                            <div className="flex justify-between items-center border-b border-white/5 pb-1">
                                <span className="text-white/30 uppercase text-[7.5px]">Leverage:</span>
                                <span className="text-purple-400 font-black tracking-tighter text-[11px] bg-purple-500/10 px-1 rounded">
                                    {signal.bitunix_order.leverage}x
                                </span>
                            </div>
                            <div className="flex justify-between items-center col-span-2 border-b border-white/5 pb-1">
                                <span className="text-white/30 uppercase text-[7.5px]">Margin Reserved:</span>
                                <span className="text-white/80">{signal.bitunix_order.metadata?.margin_reserved}</span>
                            </div>
                        </div>
                        <div className="mt-1.5 flex items-center justify-between">
                            <span className="text-[7.5px] text-white/20 italic">Notional Value: {signal.bitunix_order.metadata?.notional_value}</span>
                        </div>
                    </div>
                )}
            </div>

            {/* ── Fila 6: Puntos de Confluencia (Institutional Score) ── */}
            {signal.confluence && (
                <div className="border-t border-white/5 pt-2 flex flex-col gap-1.5">
                    <div className="flex items-center gap-3">
                        <div className="flex-1 h-1.5 bg-black/60 rounded-full overflow-hidden border border-white/10">
                            <div
                                className={`h-full rounded-full transition-all duration-700 ${signal.confluence.score >= 60 ? 'bg-neon-green shadow-[0_0_6px_rgba(0,255,65,0.6)]' :
                                        signal.confluence.score >= 40 ? 'bg-neon-cyan shadow-[0_0_6px_rgba(0,229,255,0.6)]' :
                                            signal.confluence.score >= 25 ? 'bg-yellow-400' : 'bg-neon-red'
                                    }`}
                                style={{ width: `${signal.confluence.score}%` }}
                            />
                        </div>
                        <span className={`text-[10px] font-black tracking-widest whitespace-nowrap ${signal.confluence.score >= 60 ? 'text-neon-green' :
                                signal.confluence.score >= 40 ? 'text-neon-cyan' :
                                    signal.confluence.score >= 25 ? 'text-yellow-400' : 'text-neon-red'
                            }`}
                        >
                            {signal.confluence.score}/100 {signal.confluence.conviction}
                        </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                        {signal.confluence.checklist?.map((item, i) => {
                            const statusType = getStatusType(item.status);
                            return (
                                <span key={i} className={`px-1.5 py-0.5 text-[8px] font-bold tracking-wider rounded border ${
                                    statusType === 'success' ? 'text-neon-green/90 bg-neon-green/10 border-neon-green/20' :
                                    statusType === 'warning' ? 'text-yellow-400/90 bg-yellow-400/10 border-yellow-400/20' :
                                    'text-white/30 bg-white/5 border-white/10'
                                }`} title={item.detail}>
                                    {statusType === 'success' ? '✓' : statusType === 'warning' ? '◑' : '✗'} {item.factor}
                                </span>
                            );
                        })}
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
