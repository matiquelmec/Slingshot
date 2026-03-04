'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Network, Crosshair, TrendingUp, TrendingDown, Target, ShieldAlert, Zap, Activity, Search, BarChart3, Clock, BrainCircuit, Radar } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';
import MarketContextPanel from './MarketContextPanel';

function TypewriterText({ text, speed = 30 }: { text: string; speed?: number }) {
    const [displayedText, setDisplayedText] = useState('');

    useEffect(() => {
        if (!text) {
            setDisplayedText('');
            return;
        }

        // Reset if we receive completely fresh text
        setDisplayedText((current) => {
            if (!text.startsWith(current)) return '';
            return current;
        });

        let timeoutId: NodeJS.Timeout;

        const tick = () => {
            setDisplayedText((current) => {
                if (current.length < text.length) {
                    timeoutId = setTimeout(tick, speed);
                    return text.slice(0, current.length + 1);
                }
                return current;
            });
        };

        timeoutId = setTimeout(tick, speed);
        return () => clearTimeout(timeoutId);
    }, [text, speed]);

    return (
        <div className="flex flex-col relative">
            <span className="whitespace-pre-wrap">{displayedText}<span className="animate-pulse bg-white/50 w-1.5 h-2.5 inline-block ml-0.5 align-middle" /></span>
        </div>
    );
}

export default function SignalTerminal() {
    const tacticalDecision = useTelemetryStore(state => state.tacticalDecision);
    const currentPrice_live = useTelemetryStore(state => state.latestPrice);
    const mlProjection = useTelemetryStore(state => state.mlProjection);
    const sessionData = useTelemetryStore(state => state.sessionData);
    const activeTimeframe = useTelemetryStore(state => state.activeTimeframe);
    const advisorLog = useTelemetryStore(state => state.advisor_log);

    const signalHistory = useTelemetryStore(state => state.signalHistory);

    const formatTime = (ts: string) => {
        try {
            const date = new Date(ts);
            return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch (e) {
            return ts?.split(' ')[1] || ts;
        }
    };

    // Evalúa el estado de vida de una señal en tiempo real
    const getSignalLifecycle = (sig: any): {
        status: 'PENDING' | 'EN_ZONA' | 'EXPIRADA' | 'INVALIDADA';
        label: string;
        reason: string;
        color: string;
        bgColor: string;
        countdown?: string;
    } => {
        const now = Date.now();
        const signalType = sig.signal_type || (sig.type?.includes('LONG') ? 'LONG' : 'SHORT');
        const currentPrice = currentPrice_live;
        const expiryTs = sig.expiry_timestamp ? new Date(sig.expiry_timestamp).getTime() : null;

        // 1. INVALIDADA por precio: el precio cerró más allá del SL (antes de entrar)
        if (currentPrice) {
            if (signalType === 'SHORT' && currentPrice > sig.stop_loss) {
                return {
                    status: 'INVALIDADA',
                    label: '✗ INVALIDADA',
                    reason: `Precio actual $${currentPrice.toLocaleString()} superó el Stop Loss $${sig.stop_loss?.toLocaleString()} — la tesis bajista quedó rota.`,
                    color: 'text-neon-red',
                    bgColor: 'bg-neon-red/5 border-neon-red/20 opacity-50',
                };
            }
            if (signalType === 'LONG' && currentPrice < sig.stop_loss) {
                return {
                    status: 'INVALIDADA',
                    label: '✗ INVALIDADA',
                    reason: `Precio actual $${currentPrice.toLocaleString()} rompió por debajo del Stop Loss $${sig.stop_loss?.toLocaleString()} — la tesis alcista quedó rota.`,
                    color: 'text-neon-red',
                    bgColor: 'bg-neon-red/5 border-neon-red/20 opacity-50',
                };
            }
        }

        // 2. EXPIRADA por tiempo
        if (expiryTs && now > expiryTs) {
            const intervalMin = sig.interval_minutes || 15;
            const n = sig.expiry_candles || 3;
            return {
                status: 'EXPIRADA',
                label: '⏱ EXPIRADA',
                reason: `Pasaron ${n} velas de ${intervalMin}min (${n * intervalMin}min) sin que el precio llegara a la zona de entrada. Señal descartada.`,
                color: 'text-white/40',
                bgColor: 'bg-white/[0.02] border-white/5 opacity-60',
            };
        }

        // 3. EN ZONA: precio dentro del rango de entrada
        if (currentPrice && sig.entry_zone_top && sig.entry_zone_bottom) {
            if (currentPrice >= sig.entry_zone_bottom && currentPrice <= sig.entry_zone_top) {
                return {
                    status: 'EN_ZONA',
                    label: '⚡ EN ZONA — ENTRY WINDOW',
                    reason: `Precio actual $${currentPrice.toLocaleString()} está dentro de la zona de entrada ($${sig.entry_zone_bottom?.toLocaleString()} – $${sig.entry_zone_top?.toLocaleString()}). Confirma con volumen antes de ejecutar.`,
                    color: 'text-neon-cyan',
                    bgColor: 'bg-neon-cyan/5 border-neon-cyan/30',
                };
            }
        }

        // 4. PENDING: esperando que el precio llegue a la zona
        const timeLeft = expiryTs ? Math.max(0, Math.floor((expiryTs - now) / 60000)) : null;
        const intervalMin = sig.interval_minutes || 15;
        const distToZone = currentPrice && sig.entry_zone_top && sig.entry_zone_bottom
            ? signalType === 'LONG'
                ? sig.entry_zone_top - currentPrice
                : currentPrice - sig.entry_zone_bottom
            : null;
        const distText = distToZone != null
            ? `Precio a $${Math.abs(distToZone).toLocaleString(undefined, { maximumFractionDigits: 0 })} de la zona.`
            : '';

        return {
            status: 'PENDING',
            label: '⏳ PENDIENTE',
            reason: `Esperando que el precio llegue a la zona de entrada ($${sig.entry_zone_bottom?.toLocaleString()} – $${sig.entry_zone_top?.toLocaleString()}). ${distText}`,
            color: 'text-yellow-400',
            bgColor: 'bg-yellow-400/5 border-yellow-400/20',
            countdown: timeLeft != null ? `Expira en ~${timeLeft}min (${Math.ceil(timeLeft / intervalMin)} velas)` : undefined,
        };
    };

    const getSignalStyle = (type: string) => {
        if (type.includes('LONG')) {
            return {
                color: 'text-neon-green',
                bg: 'bg-neon-green/10',
                border: 'border-neon-green/30',
                shadow: 'drop-shadow-[0_0_8px_rgba(0,255,65,0.8)]',
                icon: <TrendingUp size={14} className="text-neon-green flex-shrink-0" />
            };
        } else if (type.includes('SHORT')) {
            return {
                color: 'text-neon-red',
                bg: 'bg-neon-red/10',
                border: 'border-neon-red/30',
                shadow: 'drop-shadow-[0_0_8px_rgba(255,0,60,0.8)]',
                icon: <TrendingDown size={14} className="text-neon-red flex-shrink-0" />
            };
        }
        return {
            color: 'text-white/60',
            bg: 'bg-white/5',
            border: 'border-white/10',
            shadow: '',
            icon: <Crosshair size={14} className="text-white/40 flex-shrink-0" />
        };
    };

    // Helperes for Diagnostic UI
    const rsi = tacticalDecision?.diagnostic?.rsi || 50;
    const isRsiOversold = tacticalDecision?.diagnostic?.rsi_oversold;
    const isRsiOverbought = tacticalDecision?.diagnostic?.rsi_overbought;
    const isSqueezed = tacticalDecision?.diagnostic?.squeeze_active;
    const bbwp = tacticalDecision?.diagnostic?.bbwp || 0;
    const macdCross = tacticalDecision?.diagnostic?.macd_bullish_cross;

    // ML Color
    const getMlColor = () => {
        if (mlProjection?.direction === 'ALCISTA') return 'text-neon-green';
        if (mlProjection?.direction === 'BAJISTA') return 'text-neon-red';
        return 'text-white/40';
    };

    return (
        <div className="flex flex-col h-full bg-[#03070E]/80 backdrop-blur-2xl border-t border-white/10 overflow-hidden relative">

            {/* Header */}
            <div className="flex-none h-10 border-b border-white/5 flex items-center justify-between px-5 bg-gradient-to-r from-neon-cyan/5 to-transparent">
                <div className="flex items-center gap-3">
                    <div className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-cyan opacity-50" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-cyan shadow-[0_0_8px_rgba(0,229,255,1)]" />
                    </div>
                    <h2 className="text-[11px] font-black text-white px-1 tracking-[0.2em] flex items-center gap-2">
                        CONFLUENCE MATRIX <span className="text-white/30 font-normal">|</span> <span className="text-neon-cyan/80">HFT DIAGNOSTICS</span>
                    </h2>
                </div>
                <div className="flex items-center gap-4 text-[10px] font-bold tracking-widest text-white/40">
                    <span className="flex items-center gap-1.5"><Network size={12} className="text-neon-cyan/60" /> REAL-TIME</span>
                    <span>{signalHistory.length} ACTIVE SIGNALS</span>
                </div>
            </div>

            <div className="flex-1 flex flex-col overflow-hidden">
                {/* 1. MASTER DIAGNOSTIC DASHBOARD (Always Visible Top Section) */}
                <div className="flex-none grid grid-cols-4 gap-4 p-4 border-b border-white/5 bg-gradient-to-b from-white/[0.02] to-transparent">

                    {/* Module A: Structure & Regime */}
                    <div className="col-span-1 flex flex-col justify-between border-r border-white/5 pr-4">
                        <div className="flex items-center gap-2 mb-2">
                            <Network size={12} className="text-white/40" />
                            <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">Estructura & Régimen</span>
                        </div>
                        <div className="flex items-center gap-2 mb-2">
                            <span className="px-2 py-1 rounded border border-white/10 bg-white/5 text-[10px] font-bold tracking-widest text-white/80">
                                {tacticalDecision?.regime || 'CALIBRATING'}
                            </span>
                            <span className="px-2 py-1 rounded border border-blue-500/20 bg-blue-500/10 text-[10px] font-bold tracking-widest text-blue-400">
                                {activeTimeframe}
                            </span>
                        </div>
                        <div className="flex flex-col gap-1 text-[10px] font-mono">
                            <div className="flex items-center justify-between">
                                <span className="text-white/40">RESIST:</span>
                                <span className="text-green-400/80">${tacticalDecision?.nearest_resistance?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '---'}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-white/40">SUPPORT:</span>
                                <span className="text-red-400/80">${tacticalDecision?.nearest_support?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '---'}</span>
                            </div>
                        </div>
                    </div>

                    {/* Module B: Momentum (Criptodamus Suite) */}
                    <div className="col-span-1 flex flex-col justify-between border-r border-white/5 pr-4 pl-2">
                        <div className="flex items-center gap-2 mb-2">
                            <BarChart3 size={12} className="text-white/40" />
                            <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">Momentum Cuantitativo</span>
                        </div>

                        <div className="flex flex-col gap-2">
                            {/* RSI Bar */}
                            <div className="flex flex-col gap-1">
                                <div className="flex justify-between text-[9px] font-bold tracking-widest font-mono">
                                    <span className="text-white/50">RSI: {rsi.toFixed(1)}</span>
                                    {isRsiOversold && <span className="text-neon-green">OVERSOLD</span>}
                                    {isRsiOverbought && <span className="text-neon-red">OVERBOUGHT</span>}
                                </div>
                                <div className="h-1.5 w-full bg-black rounded-full overflow-hidden border border-white/10 relative">
                                    <div className="absolute left-[30%] top-0 bottom-0 w-px bg-white/20 z-10" />
                                    <div className="absolute left-[70%] top-0 bottom-0 w-px bg-white/20 z-10" />
                                    <div
                                        className={`h-full rounded-full ${isRsiOversold ? 'bg-neon-green' : isRsiOverbought ? 'bg-neon-red' : 'bg-white/40'}`}
                                        style={{ width: `${Math.min(100, Math.max(0, rsi))}%` }}
                                    />
                                </div>
                            </div>

                            <div className="flex items-center justify-between text-[10px] font-mono">
                                <span className="text-white/50">MACD CROSS:</span>
                                <span className={macdCross ? 'text-neon-green' : 'text-white/30'}>{macdCross ? 'BULLISH' : 'PENDING'}</span>
                            </div>
                        </div>
                    </div>

                    {/* Module C: Volatility & Liquidity */}
                    <div className="col-span-1 flex flex-col justify-between border-r border-white/5 pr-4 pl-2">
                        <div className="flex items-center gap-2 mb-2">
                            <Radar size={12} className="text-white/40" />
                            <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">Volatilidad (BBWP)</span>
                        </div>
                        <div className="flex items-center gap-3">
                            {/* Radar Ping Animation if Squeezed */}
                            <div className="relative flex h-8 w-8 items-center justify-center">
                                {isSqueezed && (
                                    <>
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-cyan opacity-20" />
                                        <span className="absolute inline-flex h-6 w-6 rounded-full border-2 border-neon-cyan/50 animate-pulse" />
                                    </>
                                )}
                                <div className={`relative inline-flex rounded-full h-3 w-3 ${isSqueezed ? 'bg-neon-cyan shadow-[0_0_10px_rgba(0,229,255,1)]' : 'bg-white/10'}`} />
                            </div>
                            <div className="flex flex-col">
                                <span className="text-[10px] font-bold tracking-widest text-white/60">SQUEEZE RADAR</span>
                                <span className={`text-[11px] font-black ${isSqueezed ? 'text-neon-cyan' : 'text-white/30'}`}>
                                    {isSqueezed ? 'COMPRESSED' : 'EXPANDED'} ({bbwp.toFixed(1)}%)
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Module D: AI & Environment */}
                    <div className="col-span-1 flex flex-col justify-between pl-2">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <BrainCircuit size={12} className="text-white/40" />
                                <span className="text-[9px] font-bold tracking-widest text-white/40 uppercase">XGBOOST ML / INFO</span>
                            </div>
                        </div>
                        <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-between text-[10px] font-mono bg-white/[0.02] border border-white/5 rounded px-2 py-1">
                                <span className="text-white/50">PROJECTION:</span>
                                <span className={`font-bold ${getMlColor()}`}>{mlProjection?.direction} {(mlProjection?.probability || 0).toFixed(0)}%</span>
                            </div>
                            <div className="flex items-center justify-between text-[10px] font-mono bg-white/[0.02] border border-white/5 rounded px-2 py-1">
                                <span className="flex items-center gap-1 text-white/50"><Clock size={10} /> SESSION:</span>
                                <span className="text-white/80 font-bold">{sessionData?.current_session || '---'}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* MARKET CONTEXT PANEL — visible siempre, incluso sin señales */}
                <div className="flex-none px-4 pb-3 border-b border-white/5">
                    <MarketContextPanel
                        regime={(tacticalDecision as any)?.market_regime ?? (tacticalDecision as any)?.regime ?? null}
                        activeStrategy={(tacticalDecision as any)?.active_strategy ?? null}
                        diagnostic={tacticalDecision?.diagnostic ?? null}
                        currentPrice={(tacticalDecision as any)?.current_price ?? currentPrice_live ?? null}
                        nearestSupport={(tacticalDecision as any)?.nearest_support ?? null}
                        nearestResistance={(tacticalDecision as any)?.nearest_resistance ?? null}
                        sessionData={sessionData}
                    />


                </div>



                {/* Status Strip -> Autonomous Advisor (LLM) */}
                <div className="flex-none bg-black/60 border-t border-b border-white/5 px-4 py-2 flex flex-col justify-center text-[10px] font-mono tracking-widest min-h-[40px]">
                    <div className="flex items-center gap-2 mb-1">
                        <BrainCircuit size={10} className="text-neon-cyan/80 animate-pulse" />
                        <span className="text-neon-cyan font-bold">AUTONOMOUS ADVISOR (LLM):</span>
                        {tacticalDecision?.strategy && (
                            <span className="text-white/30 text-[8px] border border-white/10 px-1 rounded">
                                ALGO: {tacticalDecision.strategy}
                            </span>
                        )}
                    </div>
                    <div className="text-white/70 leading-relaxed italic ml-4 border-l border-white/10 pl-2">
                        {advisorLog ? (
                            <TypewriterText text={advisorLog} speed={30} />
                        ) : (
                            <span className="text-white/30 animate-pulse">Awaiting candle close for tactical AI briefing...</span>
                        )}
                    </div>
                </div>

                {/* 2. HISTORICAL SIGNAL SCROLL (HFT Actions) */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
                    {signalHistory.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-white/10 text-[10px] font-mono italic tracking-widest flex-col gap-2 relative">
                            <div className="absolute inset-0 bg-gradient-to-t from-transparent to-white/[0.01] pointer-events-none" />
                            AWAITING ALGORITHMIC CONFLUENCE
                        </div>
                    ) : (
                        <div className="flex flex-col gap-2 px-2">
                            <AnimatePresence>
                                {signalHistory.map((sig, idx) => {
                                    const style = getSignalStyle(sig.type);
                                    const lifecycle = getSignalLifecycle(sig);
                                    const isFresh = lifecycle.status === 'EN_ZONA';

                                    return (
                                        <motion.div
                                            key={`${sig.timestamp}-${sig.type}`}
                                            initial={{ opacity: 0, x: -20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ duration: 0.4 }}
                                            className={`flex flex-col rounded border px-4 py-3 ${lifecycle.bgColor} transition-all`}
                                        >
                                            {/* ── Fila 1: Tiempo + Tipo + Estado ── */}
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-mono text-[10px] text-white/40">{formatTime(sig.timestamp)}</span>
                                                    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${style.bg} ${style.border}`}>
                                                        {style.icon}
                                                        <span className={`text-[9px] font-bold tracking-wider ${style.color} ${style.shadow}`}>
                                                            {sig.type.replace('🟢', '').replace('🔴', '').trim()}
                                                        </span>
                                                    </div>
                                                </div>
                                                <span className={`text-[9px] font-bold tracking-widest ${lifecycle.color}`}>
                                                    {lifecycle.label}
                                                </span>
                                            </div>

                                            {/* ── Fila 2: Estado educativo ── */}
                                            <div className={`text-[9px] font-mono px-2 py-1.5 rounded border border-white/5 bg-black/30 mb-2 ${lifecycle.color} leading-relaxed`}>
                                                {lifecycle.reason}
                                                {lifecycle.countdown && (
                                                    <span className="block mt-0.5 text-white/30">{lifecycle.countdown}</span>
                                                )}
                                            </div>

                                            {/* ── Fila 3: Zona de Entrada + Precios clave ── */}
                                            <div className="grid grid-cols-3 gap-2 text-[9px] font-mono mb-2">
                                                <div className="flex flex-col gap-0.5 bg-white/[0.02] rounded px-2 py-1 border border-white/5">
                                                    <span className="text-white/30 text-[8px] tracking-widest">ZONA ENTRADA</span>
                                                    {sig.entry_zone_top && sig.entry_zone_bottom ? (
                                                        <span className="text-white/80 font-bold">${sig.entry_zone_bottom.toLocaleString(undefined, { maximumFractionDigits: 0 })} – ${sig.entry_zone_top.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                                                    ) : (
                                                        <span className="text-white/60 font-bold">${sig.price?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                                                    )}
                                                </div>
                                                <div className="flex flex-col gap-0.5 bg-neon-red/5 rounded px-2 py-1 border border-neon-red/10">
                                                    <span className="text-neon-red/50 text-[8px] tracking-widest">⛔ STOP LOSS</span>
                                                    <span className="text-neon-red/90 font-bold">${sig.stop_loss?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                                                </div>
                                                <div className="flex flex-col gap-0.5 bg-neon-green/5 rounded px-2 py-1 border border-neon-green/10">
                                                    <span className="text-neon-green/50 text-[8px] tracking-widest">🎯 TARGET 3R</span>
                                                    <span className="text-neon-green/90 font-bold">${sig.take_profit_3r?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                                                </div>
                                            </div>

                                            {/* ── Fila 4: Risk Management ── */}
                                            <div className="flex items-center flex-wrap gap-1 mb-2">
                                                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-neon-cyan/80 bg-neon-cyan/10 border border-neon-cyan/20 rounded">
                                                    RISK: {sig.risk_pct ? `${sig.risk_pct}%` : 'N/A'} (${sig.risk_usd || 'N/A'})
                                                </span>
                                                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-[#d4af37] bg-[#d4af37]/10 border border-[#d4af37]/20 rounded">
                                                    {sig.leverage ? `${sig.leverage}x` : '1x'} LEV
                                                </span>
                                                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/70 bg-white/10 border border-white/20 rounded">
                                                    SIZE: ${sig.position_size || '---'}
                                                </span>
                                                {sig.expiry_candles && (
                                                    <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/30 bg-white/5 border border-white/10 rounded">
                                                        VÁLIDA {sig.expiry_candles} velas ({(sig.expiry_candles * (sig.interval_minutes || 15))}min)
                                                    </span>
                                                )}
                                                {sig.trigger?.split('+').map((badge: string, i: number) => (
                                                    <span key={i} className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/40 bg-white/5 border border-white/10 rounded">
                                                        {badge.trim()}
                                                    </span>
                                                ))}
                                            </div>

                                            {/* ── Fila 5: Confluence Score ── */}
                                            {sig.confluence && (
                                                <div className="border-t border-white/5 pt-2 flex flex-col gap-1.5">
                                                    <div className="flex items-center gap-3">
                                                        <div className="flex-1 h-1.5 bg-black/60 rounded-full overflow-hidden border border-white/10">
                                                            <div
                                                                className={`h-full rounded-full transition-all duration-700 ${sig.confluence.score >= 70 ? 'bg-neon-green shadow-[0_0_6px_rgba(0,255,65,0.6)]' :
                                                                    sig.confluence.score >= 50 ? 'bg-neon-cyan shadow-[0_0_6px_rgba(0,229,255,0.6)]' :
                                                                        sig.confluence.score >= 30 ? 'bg-yellow-400' :
                                                                            'bg-neon-red'
                                                                    }`}
                                                                style={{ width: `${sig.confluence.score}%` }}
                                                            />
                                                        </div>
                                                        <span className={`text-[10px] font-black tracking-widest whitespace-nowrap ${sig.confluence.score >= 70 ? 'text-neon-green' :
                                                            sig.confluence.score >= 50 ? 'text-neon-cyan' :
                                                                sig.confluence.score >= 30 ? 'text-yellow-400' :
                                                                    'text-neon-red'
                                                            }`}>
                                                            {sig.confluence.score}/100 {sig.confluence.conviction}
                                                        </span>
                                                    </div>
                                                    <div className="flex flex-wrap gap-1">
                                                        {sig.confluence.checklist?.map((item: any, i: number) => (
                                                            <span key={i} className={`px-1.5 py-0.5 text-[8px] font-bold tracking-wider rounded border ${item.status === 'CONFIRMADO'
                                                                ? 'text-neon-green/90 bg-neon-green/10 border-neon-green/20'
                                                                : item.status === 'PARCIAL'
                                                                    ? 'text-yellow-400/90 bg-yellow-400/10 border-yellow-400/20'
                                                                    : 'text-white/30 bg-white/5 border-white/10'
                                                                }`} title={item.detail}>
                                                                {item.status === 'CONFIRMADO' ? '✓' : item.status === 'PARCIAL' ? '◑' : '✗'} {item.factor}
                                                            </span>
                                                        ))}
                                                    </div>
                                                    {sig.confluence.reasoning && (
                                                        <p className="text-[9px] text-white/40 italic font-mono leading-relaxed pl-1 border-l border-white/10">
                                                            {sig.confluence.reasoning}
                                                        </p>
                                                    )}
                                                </div>
                                            )}
                                        </motion.div>
                                    );
                                })}
                            </AnimatePresence>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
