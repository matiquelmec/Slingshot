'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Network, Crosshair, TrendingUp, TrendingDown, Target, ShieldAlert, Zap, Activity, Search, BarChart3, Clock, BrainCircuit, Radar } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

function TypewriterText({ text, speed = 30 }: { text: string; speed?: number }) {
    const [displayedText, setDisplayedText] = useState('');

    useEffect(() => {
        setDisplayedText('');
        if (!text) return;

        let i = 0;
        const timer = setInterval(() => {
            if (i < text.length) {
                setDisplayedText(prev => prev + text.charAt(i));
                i++;
            } else {
                clearInterval(timer);
            }
        }, speed);

        return () => clearInterval(timer);
    }, [text, speed]);

    return (
        <div className="flex flex-col relative">
            <span className="whitespace-pre-wrap">{displayedText}<span className="animate-pulse bg-white/50 w-1.5 h-2.5 inline-block ml-0.5 align-middle" /></span>
        </div>
    );
}

export default function SignalTerminal() {
    const tacticalDecision = useTelemetryStore(state => state.tacticalDecision);
    const currentPrice = useTelemetryStore(state => state.latestPrice);
    const mlProjection = useTelemetryStore(state => state.mlProjection);
    const sessionData = useTelemetryStore(state => state.sessionData);
    const activeTimeframe = useTelemetryStore(state => state.activeTimeframe);
    const advisorLog = useTelemetryStore(state => state.advisor_log);

    const [signals, setSignals] = useState<any[]>([]);

    useEffect(() => {
        if (tacticalDecision?.signals) {
            setSignals([...tacticalDecision.signals].reverse().slice(0, 10));
        }
    }, [tacticalDecision?.signals]);

    const formatTime = (ts: string) => {
        try {
            const date = new Date(ts);
            return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch (e) {
            return ts?.split(' ')[1] || ts;
        }
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
                    <span>{signals.length} ACTIVE SIGNALS</span>
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
                    {signals.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-white/10 text-[10px] font-mono italic tracking-widest flex-col gap-2 relative">
                            <div className="absolute inset-0 bg-gradient-to-t from-transparent to-white/[0.01] pointer-events-none" />
                            AWAITING ALGORITHMIC CONFLUENCE
                        </div>
                    ) : (
                        <div className="flex flex-col gap-1.5 px-2">
                            <AnimatePresence>
                                {signals.map((sig, idx) => {
                                    const style = getSignalStyle(sig.type);
                                    const isFresh = idx === 0;

                                    return (
                                        <motion.div
                                            key={`${sig.timestamp}-${sig.type}`}
                                            initial={{ opacity: 0, x: -20, backgroundColor: 'rgba(0,229,255,0.2)' }}
                                            animate={{ opacity: 1, x: 0, backgroundColor: 'rgba(255,255,255,0.02)' }}
                                            transition={{
                                                duration: 0.5,
                                                backgroundColor: { duration: 2, ease: "easeOut" }
                                            }}
                                            className={`grid grid-cols-12 gap-4 px-4 py-2.5 rounded border border-white/5 items-center cursor-default hover:bg-white/[0.04] transition-colors relative overflow-hidden group`}
                                        >
                                            {isFresh && (
                                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-white/20" />
                                            )}

                                            <div className="col-span-1 font-mono text-[10px] text-white/50">
                                                {formatTime(sig.timestamp)}
                                            </div>

                                            <div className="col-span-3 flex items-center gap-2">
                                                <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${style.bg} ${style.border}`}>
                                                    {style.icon}
                                                    <span className={`text-[9px] font-bold tracking-wider ${style.color} ${style.shadow}`}>
                                                        {sig.type.replace('🟢', '').replace('🔴', '').trim()}
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="col-span-2 flex flex-col justify-center">
                                                <span className="font-mono text-[11px] font-bold text-white/90">
                                                    ${sig.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                </span>
                                            </div>

                                            <div className="col-span-3 flex flex-col justify-center gap-0.5">
                                                <div className="flex items-center gap-2 text-[9px] font-mono">
                                                    <ShieldAlert size={10} className="text-neon-red/70" />
                                                    <span className="text-white/80">${sig.stop_loss?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '---'}</span>
                                                </div>
                                                <div className="flex items-center gap-2 text-[9px] font-mono">
                                                    <Target size={10} className="text-neon-green/70" />
                                                    <span className="text-white/80">${sig.take_profit_3r?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '---'}</span>
                                                </div>
                                            </div>

                                            <div className="col-span-3 flex items-center flex-wrap gap-1">
                                                {sig.trigger?.split('+').map((badge: string, i: number) => (
                                                    <span key={i} className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-white/50 bg-white/5 border border-white/10 rounded">
                                                        {badge.trim()}
                                                    </span>
                                                ))}
                                                <span className="px-1.5 py-0.5 text-[8px] font-bold tracking-wider text-neon-cyan/80 bg-neon-cyan/10 border border-neon-cyan/20 rounded">
                                                    RISK: ${sig.risk_usd || 'N/A'}
                                                </span>
                                            </div>

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
