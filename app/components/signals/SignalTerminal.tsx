'use client';

import React, { useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Network } from 'lucide-react';
import { useSearchParams } from 'next/navigation';

// Store & Types
import { useTelemetryStore } from '../../store/telemetryStore';
import { TacticalDecision, MLProjection, SessionData } from '../../types/signal';

// Micro-Componentes (Memoizados)
import DiagnosticGridModule from './DiagnosticGridModule';
import MarketContextPanel from './MarketContextPanel';
import AutonomousAdvisor from './AutonomousAdvisor';
import SignalCardItem from './SignalCardItem';

export default function SignalTerminal() {
    const searchParams = useSearchParams();
    const connect = useTelemetryStore(state => state.connect);
    const activeSymbol = useTelemetryStore(state => state.activeSymbol);
    // ─── Suscripciones al Store (Granulares) ───

    // ⚠️ Se actualiza ~10 veces por segundo en volatilidad extrema
    const currentPrice_live = useTelemetryStore(state => state.latestPrice);
    const signalHistory = useTelemetryStore(state => state.signalHistory);

    // ✅ Se actualizan estáticamente / 1 vez cada cierre de vela (15 min)
    const tacticalDecision = useTelemetryStore(state => state.tacticalDecision as TacticalDecision);
    const mlProjection = useTelemetryStore(state => state.mlProjection as MLProjection);
    const sessionData = useTelemetryStore(state => state.sessionData as SessionData);
    const activeTimeframe = useTelemetryStore(state => state.activeTimeframe);
    const advisorLog = useTelemetryStore(state => state.advisor_log);

    // ─── Sync con URL ───
    useEffect(() => {
        const symbol = searchParams.get('symbol');
        if (symbol && symbol !== activeSymbol) {
            connect(symbol);
        }
    }, [searchParams, activeSymbol, connect]);

    return (
        <div className="flex flex-col h-full bg-[#03070E]/80 backdrop-blur-2xl border-t border-white/10 overflow-hidden relative">

            {/* ── Header ── */}
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
                    <span>{signalHistory?.length || 0} ACTIVE SIGNALS</span>
                </div>
            </div>

            <div className="flex-1 flex flex-col overflow-hidden">

                {/* 1. MASTER DIAGNOSTIC GRID */}
                <DiagnosticGridModule
                    tacticalDecision={tacticalDecision}
                    activeTimeframe={activeTimeframe}
                    mlProjection={mlProjection}
                    sessionData={sessionData}
                />

                {/* 2. MARKET CONTEXT PANEL */}
                <div className="flex-none px-4 pb-3 border-b border-white/5">
                    <MarketContextPanel
                        regime={tacticalDecision?.market_regime ?? tacticalDecision?.regime ?? null}
                        activeStrategy={tacticalDecision?.active_strategy ?? null}
                        diagnostic={tacticalDecision?.diagnostic ?? null}
                        currentPrice={tacticalDecision?.current_price ?? currentPrice_live ?? null}
                        nearestSupport={tacticalDecision?.nearest_support ?? null}
                        nearestResistance={tacticalDecision?.nearest_resistance ?? null}
                        sessionData={sessionData}
                    />
                </div>

                {/* 3. AUTONOMOUS ADVISOR (LLM Log) */}
                <AutonomousAdvisor
                    advisorLog={advisorLog}
                    strategy={tacticalDecision?.strategy ?? null}
                />

                {/* 4. HISTORICAL SIGNAL SCROLL (HFT Actions) */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
                    {!signalHistory || signalHistory.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-white/10 text-[10px] font-mono italic tracking-widest flex-col gap-2 relative">
                            <div className="absolute inset-0 bg-gradient-to-t from-transparent to-white/[0.01] pointer-events-none" />
                            AWAITING ALGORITHMIC CONFLUENCE
                        </div>
                    ) : (
                        <div className="flex flex-col gap-2 px-2">
                            <AnimatePresence>
                                {signalHistory.map((sig) => (
                                    <SignalCardItem
                                        key={`${sig.timestamp}-${sig.type}`}
                                        signal={sig}
                                        currentPrice={currentPrice_live}
                                    />
                                ))}
                            </AnimatePresence>
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
}
