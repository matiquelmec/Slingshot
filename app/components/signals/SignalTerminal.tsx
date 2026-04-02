'use client';

import React, { useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Network, ShieldAlert, Check } from 'lucide-react';
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
    
    const currentPrice_live = useTelemetryStore(state => state.latestPrice);
    const signalHistory = useTelemetryStore(state => state.signalHistory);
    const auditedSignals = useTelemetryStore(state => state.auditedSignals);

    const tacticalDecision = useTelemetryStore(state => state.tacticalDecision as TacticalDecision);
    const mlProjection = useTelemetryStore(state => state.mlProjection as MLProjection);
    const sessionData = useTelemetryStore(state => state.sessionData as SessionData);
    const activeTimeframe = useTelemetryStore(state => state.activeTimeframe);
    const advisorLogs = useTelemetryStore(state => state.advisorLogs);
    const advisorLog = advisorLogs[activeSymbol] || null;

    const [globalSignals, setGlobalSignals] = React.useState<any[]>([]);
    const [isLoadingSignals, setIsLoadingSignals] = React.useState(true);

    useEffect(() => {
        const symbol = searchParams.get('symbol');
        if (symbol && symbol !== activeSymbol) {
            connect(symbol);
        }

        const fetchInitialHydration = async () => {
            try {
                const res = await fetch(`http://localhost:8000/api/v1/signals?status=ALL`);
                if (res.ok) {
                    const data = await res.json();
                    setGlobalSignals(data);
                }
            } catch (e) {
                console.warn("SignalTerminal: Feed offline.");
            } finally {
                setIsLoadingSignals(false);
            }
        };

        // Hidratación Inicial Estática (Zero-Polling)
        fetchInitialHydration();
    }, [searchParams, activeSymbol, connect]);

    // Combinación Híbrida: Base de Datos Local + Transmisión de WS (Zustand)
    const displayMap = new Map();
    [...signalHistory, ...globalSignals].forEach(s => displayMap.set(s.id || `${s.timestamp}-${s.asset}`, s));
    // El WS de Zustand (Auditor) SIEMPRE tiene la prioridad absolutaa (sobrescribe pasados)
    auditedSignals.forEach(s => displayMap.set(s.id || `${s.timestamp}-${s.asset}`, s));
    
    // Sort descendente por tiempo
    const displaySignals = Array.from(displayMap.values())
        .sort((a, b) => new Date(b.created_at || b.timestamp).getTime() - new Date(a.created_at || a.timestamp).getTime())
        .slice(0, 50);

    const activeCount = displaySignals.filter(s => s.status === 'ACTIVE').length;
    const blockedCount = displaySignals.filter(s => s.status?.startsWith('BLOCKED')).length;

    return (
        <div className="flex flex-col h-full bg-[#03070E]/80 backdrop-blur-2xl border-t border-white/10 overflow-hidden relative">
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
                <div className="flex items-center gap-3 text-[10px] font-bold tracking-widest text-white/40">
                    <span className="flex items-center gap-1.5"><Network size={12} className="text-neon-cyan/60" /> AUDIT MODE</span>
                    {activeCount > 0 && (
                        <span className="flex items-center gap-1 text-neon-green/80">
                            <Check size={10} /> {activeCount} APPROVED
                        </span>
                    )}
                    {blockedCount > 0 && (
                        <span className="flex items-center gap-1 text-red-400/80">
                            <ShieldAlert size={10} /> {blockedCount} BLOCKED
                        </span>
                    )}
                </div>
            </div>

            <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
                <DiagnosticGridModule
                    tacticalDecision={tacticalDecision}
                    activeTimeframe={activeTimeframe}
                    mlProjection={mlProjection}
                    sessionData={sessionData}
                />

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

                <div className="flex-none max-h-[150px] overflow-y-auto custom-scrollbar">
                    <AutonomousAdvisor
                        advisorLog={advisorLog}
                        strategy={tacticalDecision?.strategy ?? null}
                    />
                </div>

                {/* 4. SIGNAL AUDIT FEED (Aprobadas + Bloqueadas en tiempo real) */}
                <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-2">
                    {isLoadingSignals && displaySignals.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-neon-cyan/20 animate-pulse text-[10px] font-mono tracking-widest">
                            CONECTANDO CON EL FEED GLOBAL...
                        </div>
                    ) : displaySignals.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-white/10 text-[10px] font-mono italic tracking-widest flex-col gap-2 relative">
                            <div className="absolute inset-0 bg-gradient-to-t from-transparent to-white/[0.01] pointer-events-none" />
                            <ShieldAlert size={24} className="text-white/5" />
                            AWAITING ALGORITHMIC CONFLUENCE
                            <span className="text-[9px] text-white/20 mt-1">El auditor activará cuando cierre la próxima vela</span>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-2 px-2">
                            <AnimatePresence>
                                {displaySignals.map((sig, idx) => (
                                    <SignalCardItem
                                        key={`audited-${sig.timestamp}-${sig.asset ?? 'any'}-${idx}`}
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
