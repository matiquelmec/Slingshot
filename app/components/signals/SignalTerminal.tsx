'use client';

import React, { useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Network, ShieldAlert, Check, Trash2 } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
// Store & Types
import { useTelemetryStore } from '../../store/telemetryStore';
import { buildConditions, Condition } from '../../utils/signalLogic';
import { QuantDiagnostic, SessionData, TacticalDecision, MLProjection } from '../../types/signal';

// Micro-Componentes (Memoizados)
import DiagnosticGridModule from './DiagnosticGridModule';
import MarketContextPanel from './MarketContextPanel';
import AutonomousAdvisor from './AutonomousAdvisor';
import SignalCardItem from './SignalCardItem';
import OnChainMetricsPanel from './OnChainMetricsPanel';

export default function SignalTerminal() {
    const searchParams = useSearchParams();
    const connect = useTelemetryStore(state => state.connect);
    const activeSymbol = useTelemetryStore(state => state.activeSymbol);
    
    const currentPrice_live = useTelemetryStore(state => state.latestPrice);
    const signalHistory = useTelemetryStore(state => state.signalHistory);
    const auditedSignals = useTelemetryStore(state => state.auditedSignals);
    const onchainMetrics = useTelemetryStore(state => state.onchainMetrics);

    const tacticalDecision = useTelemetryStore(state => state.tacticalDecision as TacticalDecision);
    const mlProjection = useTelemetryStore(state => state.mlProjection as MLProjection);
    const sessionData = useTelemetryStore(state => state.sessionData as SessionData);
    const activeTimeframe = useTelemetryStore(state => state.activeTimeframe);
    const advisorLogs = useTelemetryStore(state => state.advisorLogs);
    const advisorLog = advisorLogs[activeSymbol] || null;
    const clearSignalHistory = useTelemetryStore(state => state.clearSignalHistory);
    const viewMode = useTelemetryStore(state => state.viewMode);
    const setViewMode = useTelemetryStore(state => state.setViewMode);
    const hydrateSignals = useTelemetryStore(state => state.hydrateSignals);

    const [isLoadingSignals, setIsLoadingSignals] = React.useState(true);
    const [hideBlocked, setHideBlocked] = React.useState(true);

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
                    hydrateSignals(data);
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

    // Los audiosignals siguen siendo directos para el Feed de auditoría
    const displayMap = new Map();
    Object.values(signalHistory).forEach(s => displayMap.set(s.id || `${s.timestamp}-${s.asset}`, s));
    Object.values(auditedSignals).forEach(s => displayMap.set(s.id || `${s.timestamp}-${s.asset}`, s));
    
    // Sort descendente por tiempo + Filtrado por Activo y Estado (v5.8.0)
    const displaySignals = Array.from(displayMap.values())
        .filter(s => viewMode === 'GLOBAL' || s.asset === activeSymbol)
        .filter(s => {
            if (!hideBlocked) return true;
            const score = s.confluence?.score || s.confluence_score || 0;
            return !s.status?.startsWith('BLOCKED') && s.status !== 'VETADA' && score >= 25;
        })
        .sort((a, b) => {
            const timeA = new Date(a.created_at || a.timestamp).getTime();
            const timeB = new Date(b.created_at || b.timestamp).getTime();
            return timeB - timeA;
        })
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
                    <div className="flex items-center bg-white/5 rounded-lg p-0.5 border border-white/5 mr-2">
                        <button 
                            onClick={() => setViewMode('SYMBOL')}
                            className={`px-2 py-1 rounded transition-all ${viewMode === 'SYMBOL' ? 'bg-neon-cyan/20 text-neon-cyan' : 'hover:text-white/60'}`}
                        >
                            {activeSymbol.replace('USDT', '')}
                        </button>
                        <button 
                            onClick={() => setViewMode('GLOBAL')}
                            className={`px-2 py-1 rounded transition-all ${viewMode === 'GLOBAL' ? 'bg-neon-cyan/20 text-neon-cyan' : 'hover:text-white/60'}`}
                        >
                            GLOBAL
                        </button>
                    </div>
                    <div className="flex items-center bg-white/5 rounded-lg p-0.5 border border-white/5 mr-2">
                        <button 
                            onClick={() => setHideBlocked(true)}
                            className={`px-2 py-1 rounded transition-all text-[9px] ${hideBlocked ? 'bg-green-500/20 text-green-400 font-black' : 'text-white/40 hover:text-white/60'}`}
                        >
                            SOLO APROBADAS
                        </button>
                        <button 
                            onClick={() => setHideBlocked(false)}
                            className={`px-2 py-1 rounded transition-all text-[9px] ${!hideBlocked ? 'bg-red-500/20 text-red-400 font-black' : 'text-white/40 hover:text-white/60'}`}
                        >
                            VER VETADAS
                        </button>
                    </div>
                    <span className="flex items-center gap-1.5 border-l border-white/10 pl-3"><Network size={12} className="text-neon-cyan/60" /> AUDIT MODE</span>
                    
                    <button 
                        onClick={() => {
                            if (window.confirm("¿Limpiar todo el historial de señales detectadas?")) {
                                clearSignalHistory();
                            }
                        }}
                        className="ml-2 p-1.5 hover:bg-red-500/20 hover:text-red-400 rounded-md transition-all group relative"
                        title="Limpiar Sensores"
                    >
                        <Trash2 size={12} />
                    </button>

                    {activeCount > 0 && (
                        <span className="flex items-center gap-1 text-neon-green/80 ml-2">
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

                <div className="flex-none px-4 pb-3 border-b border-white/5 grid grid-cols-1 lg:grid-cols-4 gap-4">
                    <div className="lg:col-span-3">
                        <MarketContextPanel
                            regime={tacticalDecision?.market_regime ?? tacticalDecision?.regime ?? null}
                            activeStrategy={tacticalDecision?.active_strategy ?? null}
                            diagnostic={tacticalDecision?.diagnostic ?? null}
                            currentPrice={tacticalDecision?.current_price ?? currentPrice_live ?? null}
                            nearestSupport={tacticalDecision?.nearest_support ?? null}
                            nearestResistance={tacticalDecision?.nearest_resistance ?? null}
                            sessionData={sessionData}
                            fibonacci={tacticalDecision?.fibonacci}
                        />
                    </div>
                    <div className="lg:col-span-1 border-l border-white/5 pl-4">
                        <OnChainMetricsPanel metrics={onchainMetrics} />
                    </div>
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
