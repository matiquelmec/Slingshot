'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Signal, AccountProfileConfig } from '../../types/signal';
import { useTelemetryStore } from '../../store/telemetryStore';
import { getSignalLifecycle, getSignalStyle } from '../../utils/signalLogic';
import { formatCurrency } from '../../utils/formatters';
import { calculateMt5Lots } from '../../utils/ftmoSpecs';

interface SignalCardItemProps {
    signal: Signal;
    currentPrice: number | null;
    profileConfig?: AccountProfileConfig;
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

const getStatusType = (status: string): 'success' | 'warning' | 'danger' | 'info' => {
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
        s === 'INSTITUCIONAL' ||
        s === 'OPTIMAL'
    ) {
        return 'success';
    }
    if (
        s === 'DENEGADO' ||
        s === 'VETADO' ||
        s === 'OBSOLETO' ||
        s.includes('DIVERGENTE') ||
        s === 'QUARANTINED'
    ) {
        return 'danger';
    }
    if (
        s === 'PARCIAL' ||
        s === 'VOLÁTIL' ||
        s === 'DECAYENDO' ||
        s.includes('PRECAUCIÓN') ||
        s.includes('ALERTA') ||
        s === 'MODERATE_NOISE'
    ) {
        return 'warning';
    }
    return 'info';
};

const SignalCardItem: React.FC<SignalCardItemProps> = ({ signal, currentPrice, profileConfig }) => {
    // Consumimos el mapa de precios globales para hidratación específica por activo (v5.8.0)
    const latestPrices = useTelemetryStore(state => state.latestPrices);
    const effectivePrice = useMemo(() => {
        return latestPrices[signal.asset || ''] || currentPrice;
    }, [latestPrices, signal.asset, currentPrice]);

    const [isCopied, setIsCopied] = React.useState(false);

    // Memoizamos fuertemente el ciclo de vida. Solo recalcula si el effectivePrice hace que evalúe distinto
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
            layout
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
            className={`flex flex-col rounded-xl border px-4 py-3 ${lifecycle.bgColor} transition-all relative ${
                (signal.confluence_score || 0) >= 70
                    ? 'border-neon-green/40 shadow-[0_0_20px_rgba(16,185,129,0.15)] ring-1 ring-neon-green/20'
                    : (signal.confluence_score || 0) >= 50
                    ? 'border-neon-cyan/35 shadow-[0_0_12px_rgba(6,182,212,0.1)]'
                    : ''
            }`}
        >
            {/* Priority Banner if High Confluence */}
            {(signal.confluence_score || 0) >= 70 ? (
                <div className="flex items-center justify-between bg-neon-green/10 border border-neon-green/25 rounded-lg px-2.5 py-1 mb-2">
                    <span className="text-neon-green text-[9px] font-mono font-black uppercase tracking-wider flex items-center gap-1.5">
                        <span>👑 PRIORIDAD ELITE</span>
                        <span className="text-white/40">|</span>
                        <span>CONFLUENCIA {signal.confluence_score}%</span>
                    </span>
                    <span className="text-neon-green text-[8px] font-mono font-bold bg-neon-green/20 px-1.5 py-0.5 rounded">PASO 1 + 2 OK</span>
                </div>
            ) : (signal.confluence_score || 0) >= 50 ? (
                <div className="flex items-center justify-between bg-neon-cyan/10 border border-neon-cyan/20 rounded-lg px-2.5 py-1 mb-2">
                    <span className="text-neon-cyan text-[9px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                        <span>🎯 ALTA EXPECTATIVA</span>
                        <span className="text-white/40">|</span>
                        <span>CONFLUENCIA {signal.confluence_score}%</span>
                    </span>
                    <span className="text-neon-cyan text-[8px] font-mono font-bold bg-neon-cyan/20 px-1.5 py-0.5 rounded">ALINEADO EMA 200</span>
                </div>
            ) : null}

            {/* Insignia Dinámica y Veraz de Categoría de Trade */}
            {(() => {
                const sStatus = signal.status || 'PENDING';
                const isTradeActive = sStatus === 'ACTIVE' || sStatus === 'FILLED';
                const isPending = sStatus === 'PENDING';
                const isBe = sStatus === 'BREAKEVEN' || signal.trailing_phase === 'BREAKEVEN' || signal.profit_locked;
                const isTpMax = sStatus === 'CLOSED_TP_MAX' || sStatus === 'CLOSED';
                const isStopped = sStatus === 'STOPPED_OUT';
                const isExpired = sStatus === 'EXPIRED' || sStatus === 'EXPIRED_MISSED' || sStatus === 'INVALIDATED_BROKEN';

                if (isTradeActive) {
                    return (
                        <div className="flex items-center justify-between bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-3 py-1 mb-2.5 shadow-[0_0_12px_rgba(16,185,129,0.15)]">
                            <span className="text-emerald-400 text-[8.5px] font-mono font-black uppercase tracking-wider flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block" />
                                <span>🔥 TRADE EN EJECUCIÓN EN VIVO</span>
                                {isBe && (
                                    <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-1.5 py-0.2 rounded text-[7.5px] font-black">
                                        🛡️ FAST BE (+1.0R LOCK)
                                    </span>
                                )}
                            </span>
                            <span className="text-emerald-400/60 text-[8px] font-mono font-bold">POSICIÓN ABIERTA</span>
                        </div>
                    );
                }

                if (isPending) {
                    return (
                        <div className="flex items-center justify-between bg-cyan-500/10 border border-cyan-500/30 rounded-xl px-3 py-1 mb-2.5 shadow-[0_0_12px_rgba(6,182,212,0.1)]">
                            <span className="text-neon-cyan text-[8.5px] font-mono font-black uppercase tracking-wider flex items-center gap-1.5">
                                <span>⏳ ORDEN LÍMITE PENDIENTE</span>
                                <span className="text-white/40">|</span>
                                <span className="text-white/70">ESPERANDO RETROCESO A ENTRADA</span>
                            </span>
                            <span className="text-neon-cyan/60 text-[8px] font-mono font-bold">SETUP LÍMITE</span>
                        </div>
                    );
                }

                if (isTpMax) {
                    return (
                        <div className="flex items-center justify-between bg-emerald-500/10 border border-emerald-500/25 rounded-xl px-3 py-1 mb-2.5">
                            <span className="text-emerald-400 text-[8.5px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                                <span>✅ TAKE PROFIT COMPLETADO</span>
                            </span>
                            <span className="text-emerald-400/60 text-[8px] font-mono">TRADE CERRADO</span>
                        </div>
                    );
                }

                if (isStopped) {
                    return (
                        <div className="flex items-center justify-between bg-rose-500/10 border border-rose-500/25 rounded-xl px-3 py-1 mb-2.5">
                            <span className="text-rose-400 text-[8.5px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                                <span>🛑 STOP LOSS HIT</span>
                            </span>
                            <span className="text-rose-400/60 text-[8px] font-mono">RIESGO CONTROLADO</span>
                        </div>
                    );
                }

                if (isExpired) {
                    return (
                        <div className="flex items-center justify-between bg-white/5 border border-white/10 rounded-xl px-3 py-1 mb-2.5 opacity-60">
                            <span className="text-white/50 text-[8.5px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                                <span>⏱️ SETUP EXPIRADO (PRECIO SE ALEJÓ)</span>
                            </span>
                            <span className="text-white/30 text-[8px] font-mono">DESCARTADO</span>
                        </div>
                    );
                }

                return (
                    <div className="flex items-center justify-between bg-white/5 border border-white/10 rounded-xl px-3 py-1 mb-2.5">
                        <span className="text-white/50 text-[8.5px] font-mono font-bold uppercase tracking-wider flex items-center gap-1.5">
                            <span>🛡️ SEÑAL AUDITADA ({sStatus})</span>
                        </span>
                        <span className="text-white/30 text-[8px] font-mono">AUDIT FEED</span>
                    </div>
                );
            })()}

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

                    {/* Badge de Dirección LONG / SHORT Explícito */}
                    {(() => {
                        const isLong = ((signal.signal_type?.toUpperCase().includes('LONG')) || (signal.type?.toUpperCase().includes('LONG')) || ((signal as any).direction?.toUpperCase().includes('LONG')));
                        return (
                            <span className={`text-[9px] font-mono font-black px-2 py-0.5 rounded-md border uppercase ${
                                isLong ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' : 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                            }`}>
                                {isLong ? '🟢 LONG' : '🔴 SHORT'}
                            </span>
                        );
                    })()}

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
            {(() => {
                const isLong = signal.type?.toLowerCase().includes('long') || signal.signal_type?.toLowerCase().includes('long');
                const entryP = signal.price || 0;
                const slP = signal.stop_loss || 0;
                const riskDist = Math.abs(entryP - slP);
                const bePrice = signal.be_price || (isLong ? entryP + (riskDist * 1.0) : entryP - (riskDist * 1.0));

                return (
                    <div className="flex flex-col gap-2 mb-2 font-mono">
                        <div className="grid grid-cols-4 gap-2 text-[9px]">
                            <div className="flex flex-col gap-0.5 bg-white/[0.02] rounded-xl px-2.5 py-1.5 border border-white/10 hover:border-white/20 transition-all">
                                <span className="text-white/40 text-[8px] tracking-widest uppercase font-bold">Entry Price</span>
                                {signal.entry_zone_top && signal.entry_zone_bottom ? (
                                    <span className="text-white font-bold">
                                        {formatCurrency(signal.entry_zone_bottom)} – {formatCurrency(signal.entry_zone_top)}
                                    </span>
                                ) : (
                                    <span className="text-white font-bold">{formatCurrency(signal.price)}</span>
                                )}
                            </div>
                            <div className="flex flex-col gap-0.5 bg-rose-500/10 rounded-xl px-2.5 py-1.5 border border-rose-500/30 hover:border-rose-500/50 transition-all">
                                <span className="text-rose-400 text-[8px] tracking-widest uppercase font-black flex justify-between">
                                    <span>Stop Loss</span>
                                    <span className="text-[7px] text-rose-400/80 font-mono">
                                        (-{signal.sl_dist_pct ? signal.sl_dist_pct.toFixed(2) : signal.price && signal.stop_loss ? ((Math.abs(signal.price - signal.stop_loss) / signal.price) * 100).toFixed(2) : '1.80'}%)
                                    </span>
                                </span>
                                <span className="text-rose-400 font-black">{formatCurrency(signal.stop_loss)}</span>
                            </div>
                            <div className="flex flex-col gap-0.5 bg-emerald-500/10 rounded-xl px-2.5 py-1.5 border border-emerald-500/30 hover:border-emerald-500/50 transition-all col-span-2">
                                <div className="flex justify-between items-center mb-0.5">
                                    <span className="text-emerald-400 text-[8px] tracking-widest uppercase font-black">TP Targets (70% / 15% / 15%)</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-emerald-300 text-[8px] font-bold">TP1 (+1.5R):</span>
                                    <span className="text-emerald-400 font-black">{formatCurrency(signal.tp1) || '---'}</span>
                                    <span className="text-emerald-300 text-[8px] font-bold ml-1">TP2 (+3.0R):</span>
                                    <span className="text-emerald-400 font-black">{formatCurrency(signal.tp2) || '---'}</span>
                                    <span className="text-emerald-500 text-[10px]">⚡</span>
                                    <span className="text-emerald-300 text-[8px] font-bold">TP3 (+5.0R):</span>
                                    <span className="text-emerald-300 font-black">{formatCurrency(signal.tp3 || signal.take_profit_3r) || '---'}</span>
                                </div>
                            </div>
                        </div>

                        {/* Fast BE Banner (+1.0R Trigger) */}
                        <div className="flex items-center justify-between px-3 py-1.5 bg-neon-cyan/10 border border-neon-cyan/30 rounded-xl text-[9px] shadow-[0_0_15px_rgba(6,182,212,0.1)]">
                            <span className="text-neon-cyan font-bold flex items-center gap-1.5 font-mono">
                                🛡️ Fast BE (+1.0R):
                                <span className="text-white font-black text-[10px]">{formatCurrency(bePrice)}</span>
                            </span>
                            <span className="text-white/50 text-[8px] font-sans font-medium">
                                Al alcanzar este nivel 👉 Mover SL a Entrada + Comisiones ($0.00 Riesgo)
                            </span>
                        </div>
                    </div>
                );
            })()}

            {/* ── Fila 4: Matemáticas de Riesgo v11.0 ── */}
            <div className="flex items-center flex-wrap gap-1 mb-2">
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded flex items-center gap-1 font-mono">
                    LOTE SUGERIDO ($100 RISK): ${formatCurrency(signal.position_size_usdt || signal.suggested_position_usdt || (signal.price && signal.stop_loss ? Math.round(100 / (Math.abs(signal.price - signal.stop_loss) / signal.price)) : 1000))} USDT
                </span>
                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-neon-cyan/80 bg-neon-cyan/10 border border-neon-cyan/20 rounded flex items-center gap-1">
                    RISK: {signal.risk_pct ? `${signal.risk_pct}%` : '1.0%'} {signal.risk_amount_usdt || signal.risk_usd ? `($${signal.risk_amount_usdt || signal.risk_usd})` : ''}
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

            {/* ── Fila 5: Ejecución Institucional Dinámica (MT5 / Bitunix) ── */}
            <div className="flex flex-col gap-2 mb-2">
                {/* Panel FTMO Dinámico */}
                {(profileConfig?.isFtmo || signal.ftmo_order) && (
                    <div className="px-2.5 py-2 bg-gradient-to-r from-neon-green/10 via-neon-cyan/5 to-transparent rounded-lg border border-neon-green/30 text-[9px] font-mono shadow-[inset_0_0_12px_rgba(16,185,129,0.08)]">
                        <div className="flex items-center justify-between mb-1.5">
                            <span className="text-neon-green font-black tracking-widest uppercase flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse" />
                                🎯 EJECUCIÓN FTMO (MT5 / cTrader)
                            </span>
                            <button
                                onClick={() => {
                                    const action = signal.type.toLowerCase().includes('long') ? 'BUY LIMIT' : 'SELL LIMIT';
                                    const sym = (signal.asset || 'BTCUSDT').replace('USDT', 'USD');
                                    const riskAmt = profileConfig?.riskUsd || 750;
                                    const dist = Math.abs((signal.price || 0) - (signal.stop_loss || 0));
                                    const lots = calculateMt5Lots(signal.asset || 'BTCUSDT', riskAmt, dist);
                                    const isL = signal.type.toLowerCase().includes('long');
                                    const beP = signal.be_price || (isL ? (signal.price || 0) + (dist * 1.2) : (signal.price || 0) - (dist * 1.2));
                                    const text = `[FTMO MT5] ${action} ${sym} @ ${signal.price} | LOTES: ${lots.toFixed(2)} | SL: ${signal.stop_loss} | 🛡️ MOVER A BE: ${formatCurrency(beP)} (+1.2R) | 🎯 TP3: ${signal.tp3 || signal.take_profit_3r || '---'} (+3.5R)`;
                                    navigator.clipboard.writeText(text);
                                    setIsCopied(true);
                                    setTimeout(() => setIsCopied(false), 2000);
                                }}
                                className={`px-2 py-0.5 rounded text-[8px] font-mono font-black transition-all flex items-center gap-1 cursor-pointer ${
                                    isCopied 
                                        ? 'bg-neon-green text-black shadow-[0_0_10px_rgba(16,185,129,0.5)]' 
                                        : 'bg-neon-green/20 hover:bg-neon-green/30 text-neon-green border border-neon-green/40'
                                }`}
                            >
                                {isCopied ? '✅ ¡ORDEN COPIADA!' : '📋 COPIAR ORDEN MT5'}
                            </button>
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-black/40 p-1.5 rounded border border-white/5">
                            <div className="flex flex-col">
                                <span className="text-white/40 uppercase text-[7px]">Símbolo MT5:</span>
                                <span className="text-white font-bold">{(signal.asset || 'BTCUSDT').replace('USDT', 'USD')}</span>
                            </div>
                            <div className="flex flex-col">
                                <span className="text-white/40 uppercase text-[7px]">Lotes Sugeridos:</span>
                                <span className="text-neon-green font-black text-[12px]">
                                    {(() => {
                                        const riskAmt = profileConfig?.riskUsd || 750;
                                        const dist = Math.abs((signal.price || 0) - (signal.stop_loss || 0));
                                        return calculateMt5Lots(signal.asset || 'BTCUSDT', riskAmt, dist).toFixed(2);
                                    })()} Lots
                                </span>
                            </div>
                            <div className="flex flex-col">
                                <span className="text-white/40 uppercase text-[7px]">Riesgo en Cuenta:</span>
                                <span className="text-neon-cyan font-bold">
                                    ${profileConfig?.riskUsd || 750} USD ({profileConfig?.riskPct || 0.75}%)
                                </span>
                            </div>
                            <div className="flex flex-col">
                                <span className="text-white/40 uppercase text-[7px]">Tipo de Orden:</span>
                                <span className={
                                    ((signal.signal_type?.toUpperCase().includes('LONG')) || (signal.type?.toUpperCase().includes('LONG')) || ((signal as any).direction?.toUpperCase().includes('LONG')))
                                        ? 'text-emerald-400 font-black' 
                                        : 'text-rose-400 font-black'
                                }>
                                    {((signal.signal_type?.toUpperCase().includes('LONG')) || (signal.type?.toUpperCase().includes('LONG')) || ((signal as any).direction?.toUpperCase().includes('LONG'))) ? 'BUY LIMIT' : 'SELL LIMIT'}
                                </span>
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
                                <span key={i} className={`px-1.5 py-0.5 text-[8px] font-bold tracking-wider rounded border transition-all ${
                                    statusType === 'success' ? 'text-neon-green/90 bg-neon-green/10 border-neon-green/30 shadow-[0_0_8px_rgba(0,255,65,0.15)]' :
                                    statusType === 'danger'  ? 'text-rose-400 bg-rose-500/10 border-rose-500/30' :
                                    statusType === 'warning' ? 'text-yellow-400/90 bg-yellow-400/10 border-yellow-400/20' :
                                    'text-white/30 bg-white/5 border-white/10'
                                }`} title={item.detail}>
                                    {statusType === 'success' ? '✓' : statusType === 'danger' ? '✕' : statusType === 'warning' ? '◑' : '○'} {item.factor}
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
