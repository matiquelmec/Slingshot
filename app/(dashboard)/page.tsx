'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Terminal, ChevronRight, Plus, X, Lock } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useTelemetryStore, Timeframe } from '../store/telemetryStore';

const QuantDiagnosticPanel = dynamic(() => import('../components/ui/QuantDiagnosticPanel'), { ssr: false });
const LatticeStatus = dynamic(() => import('../components/ui/LatticeStatus'), { ssr: false });
const SessionClock = dynamic(() => import('../components/ui/SessionClock'), { ssr: false });
const MacroRadar = dynamic(() => import('../components/ui/MacroRadar'), { ssr: false });
const NewsTerminal = dynamic(() => import('../components/ui/NewsTerminal'), { ssr: false });
const LiquidationScanner = dynamic(() => import('../components/ui/LiquidationScanner'), { ssr: false });
const LatticeScanner = dynamic(() => import('../components/ui/LatticeScanner'), { ssr: false });
const MacroCalendar = dynamic(() => import('../components/macro/MacroCalendar'), { ssr: false });
const EliteConsole = dynamic(() => import('../components/ui/EliteConsole'), { ssr: false });
const OmegaCentinelPanel = dynamic(() => import('../components/execution/OmegaCentinelPanel'), { ssr: false });

// ── Tipos ─────────────────────────────────────────────────────────────────────

interface WatchlistEntry {
    id: string          // UUID en Supabase
    asset: string
    interval: string
    alerts_enabled: boolean
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function OverviewPage() {
    const [mounted, setMounted] = useState(false);
    const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
    const [watchlistLoading, setWatchlistLoading] = useState(true);
    const [addingSymbol, setAddingSymbol] = useState(false);
    const [newSymbol, setNewSymbol] = useState('');
    const [availableSymbols, setAvailableSymbols] = useState<string[]>([]);
    const [filteredSymbols, setFilteredSymbols] = useState<string[]>([]);
    const [sidePanelMode, setSidePanelMode] = useState<'LOGS' | 'NEWS' | 'LIQS' | 'CAL' | 'OMEGA'>('LIQS');

    const { 
        activeSymbol, 
        activeTimeframe, 
        latestPrice, 
        mlProjection, 
        neuralLogs, 
        connect, 
        isCalibrating, 
        advisorLogs,
        marketSummary 
    } = useTelemetryStore();

    const advisor_log = (advisorLogs as Record<string, any>)[activeSymbol] || null;

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    useEffect(() => { setMounted(true); }, []);

    // Load watchlist from localStorage
    useEffect(() => {
        const localWatchlist = localStorage.getItem('slingshot_watchlist');
        if (localWatchlist) {
            try {
                const parsed = JSON.parse(localWatchlist) as WatchlistEntry[];
                setWatchlist(parsed);
                if (parsed.length > 0 && !activeSymbol) {
                    connect(parsed[0].asset, parsed[0].interval as Timeframe);
                }
            } catch (e) {
                console.error("Error parsing local watchlist");
            }
        } else {
            // Default watchlist (VIP Assets)
            const defaultWatchlist: WatchlistEntry[] = [
                { id: '1', asset: 'BTCUSDT', interval: '15m', alerts_enabled: true },
                { id: '2', asset: 'ETHUSDT', interval: '15m', alerts_enabled: true },
                { id: '3', asset: 'SOLUSDT', interval: '15m', alerts_enabled: true },
                { id: '4', asset: 'PAXGUSDT', interval: '15m', alerts_enabled: true }
            ];
            setWatchlist(defaultWatchlist);
            localStorage.setItem('slingshot_watchlist', JSON.stringify(defaultWatchlist));
            if (!activeSymbol) {
                // We use setTimeout to ensure it connects properly initially
                setTimeout(() => connect(defaultWatchlist[0].asset, defaultWatchlist[0].interval as Timeframe), 100);
            }
        }
        setWatchlistLoading(false);
    }, [activeSymbol, connect]);

    // Update interval in localStorage when changed in UI
    useEffect(() => {
        if (!activeSymbol || !activeTimeframe || watchlist.length === 0) return;

        const currentEntry = watchlist.find(w => w.asset === activeSymbol);
        if (currentEntry && currentEntry.interval !== activeTimeframe) {
            const updated = watchlist.map(w =>
                w.id === currentEntry.id ? { ...w, interval: activeTimeframe } : w
            );
            setWatchlist(updated);
            localStorage.setItem('slingshot_watchlist', JSON.stringify(updated));
        }
    }, [activeSymbol, activeTimeframe, watchlist]);

    // Buscar símbolos disponibles en Binance cuando se abre el panel de búsqueda
    useEffect(() => {
        if (addingSymbol && availableSymbols.length === 0) {
            fetch('https://api.binance.com/api/v3/ticker/price')
                .then(r => r.json())
                .then(data => {
                    setAvailableSymbols(
                        data.map((t: any) => t.symbol).filter((s: string) => s.endsWith('USDT')).sort()
                    );
                })
                .catch(() => { });
        }
    }, [addingSymbol, availableSymbols.length]);

    // Filtrar sugerencias de autocompletado
    useEffect(() => {
        if (!newSymbol.trim()) {
            setFilteredSymbols([]);
            return;
        }
        const term = newSymbol.trim().toUpperCase();
        setFilteredSymbols(
            availableSymbols.filter(s => s.includes(term) && !watchlist.find(w => w.asset === s)).slice(0, 5)
        );
    }, [newSymbol, availableSymbols, watchlist]);

    // ── Local Operations ─────────────────────────────────────────────────────────

    const handleAddSymbol = useCallback((symToAdd?: string | React.MouseEvent) => {
        const sym = (typeof symToAdd === 'string' ? symToAdd : newSymbol).trim().toUpperCase();
        if (!sym) return;

        // Evitar duplicados
        if (watchlist.find(w => w.asset === sym)) {
            setNewSymbol('');
            setAddingSymbol(false);
            return;
        }

        const newEntry: WatchlistEntry = {
            id: Math.random().toString(36).substring(7),
            asset: sym,
            interval: activeTimeframe,
            alerts_enabled: true
        };

        const updated = [...watchlist, newEntry];
        setWatchlist(updated);
        localStorage.setItem('slingshot_watchlist', JSON.stringify(updated));

        if (watchlist.length === 0) {
            connect(newEntry.asset, newEntry.interval as Timeframe);
        }

        setNewSymbol('');
        setAddingSymbol(false);
        setFilteredSymbols([]);
    }, [newSymbol, watchlist, activeTimeframe, connect]);

    const handleRemoveSymbol = useCallback((entry: WatchlistEntry) => {
        if (entry.asset === activeSymbol) return; // no eliminar el activo activo

        const updated = watchlist.filter(w => w.id !== entry.id);
        setWatchlist(updated);
        localStorage.setItem('slingshot_watchlist', JSON.stringify(updated));
    }, [activeSymbol, watchlist]);

    const handleSymbolClick = useCallback((entry: WatchlistEntry) => {
        if (entry.asset !== activeSymbol) {
            connect(entry.asset, entry.interval as Timeframe);
        }
    }, [activeSymbol, connect]);

    // ── Render ────────────────────────────────────────────────────────────────

    if (!mounted) return null;

    const containerVariants = {
        hidden: { opacity: 0 },
        show: { opacity: 1, transition: { staggerChildren: 0.12 } }
    };
    const itemVariants = {
        hidden: { opacity: 0, scale: 0.97, y: 15 },
        show: { opacity: 1, scale: 1, y: 0, transition: { type: 'spring' as const, stiffness: 250, damping: 22 } }
    };

    const maxWatchlist = 20; // Límite virtual
    const watchlistFull = watchlist.length >= maxWatchlist;

    return (
        <div className="min-h-screen flex flex-col bg-black select-none">
            <LatticeStatus />
            
            {/* Modal de Búsqueda de Símbolos (v5.7) */}
            <AnimatePresence>
                {addingSymbol && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-md flex items-center justify-center p-6"
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            className="bg-[#0A1019] border border-white/10 p-6 rounded-3xl w-full max-w-md shadow-2xl"
                        >
                            <div className="flex justify-between items-center mb-6">
                                <h3 className="text-sm font-black text-white tracking-widest">INJECTAR SCANNER ACTIVO</h3>
                                <button onClick={() => setAddingSymbol(false)} className="text-white/40 hover:text-white"><X size={20} /></button>
                            </div>
                            
                            <div className="relative mb-6">
                                <Terminal size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-neon-cyan" />
                                <input
                                    autoFocus
                                    placeholder="BUSCAR PAR (EJ: SOLUSDT)..."
                                    className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-6 text-xs font-mono font-bold text-white focus:border-neon-cyan outline-none transition-all uppercase"
                                    value={newSymbol}
                                    onChange={(e) => setNewSymbol(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleAddSymbol()}
                                />
                            </div>

                            <div className="flex flex-col gap-2 mb-6">
                                {filteredSymbols.map(sym => (
                                    <button
                                        key={sym}
                                        onClick={() => handleAddSymbol(sym)}
                                        className="flex items-center justify-between p-4 rounded-2xl bg-white/5 border border-white/5 hover:border-neon-cyan/50 hover:bg-white/10 transition-all"
                                    >
                                        <span className="text-xs font-black font-mono text-white/80">{sym}</span>
                                        <ChevronRight size={14} className="text-neon-cyan" />
                                    </button>
                                ))}
                            </div>

                            <p className="text-[9px] text-white/20 text-center font-bold uppercase tracking-widest">Binance Futures API Connected</p>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
            
            <motion.div
                variants={containerVariants}
                initial="hidden"
                animate="show"
                className="grid grid-cols-12 gap-5 p-5"
            >
                {/* Left Column: GLOBAL SELECTOR & TIME (v5.7.6) */}
                <motion.section variants={itemVariants} className="col-span-12 lg:col-span-4 flex flex-col gap-4 min-h-[750px]">
                    <div className="h-[420px] flex flex-col min-h-0">
                        <LatticeScanner />
                    </div>
                    
                    {/* Sesiones del Mercado */}
                    <div className="flex-1 min-h-0">
                        <SessionClock />
                    </div>
                </motion.section>

                {/* Middle Column: MARCO GLOBAL -> RETINA TÉCNICA */}
                <motion.section variants={itemVariants} className="col-span-12 lg:col-span-4 flex flex-col gap-4 min-h-[750px]">
                    {/* ── MACRO RADAR (Contexto Anterior al Análisis) ── */}
                    <div className="h-[200px] flex-shrink-0">
                        <MacroRadar />
                    </div>

                    {/* Retina Técnica — Expansión Máxima */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0 bg-[#05111B]/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl">
                        <QuantDiagnosticPanel />
                    </div>
                </motion.section>

                {/* Right Column */}
                <motion.section variants={itemVariants} className="col-span-12 lg:col-span-4 flex flex-col gap-5 min-h-[600px]">
                    <div className="h-44 bg-gradient-to-br from-[#050B14] to-black backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl flex flex-col justify-between p-5 relative overflow-hidden flex-shrink-0">
                        <div className={`absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(${mlProjection.direction === 'ALCISTA' ? '0,255,65' : mlProjection.direction === 'BAJISTA' ? '255,0,60' : '100,100,100'},0.1),transparent_50%)] pointer-events-none transition-colors duration-1000`} />
                        <div className="flex justify-between items-start z-10">
                            <p className="text-[10px] text-white/50 tracking-[0.2em] font-bold">INTELIGENCIA TÁCTICA (QWEN + XGBOOST)</p>
                            <Activity size={14} className={`${mlProjection.direction === 'ALCISTA' ? 'text-neon-green' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red' : 'text-gray-400'} opacity-50`} />
                        </div>
                        <div className="z-10 mt-auto">
                            <div className="flex items-center gap-4">
                                <div className="flex flex-col items-center justify-center min-w-[70px]">
                                    <span className={`text-4xl font-black ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green drop-shadow-[0_0_15px_rgba(0,255,65,0.5)]' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red drop-shadow-[0_0_15px_rgba(255,0,60,0.5)]' : 'text-white/50'} tracking-tighter`}>
                                        {mlProjection.probability}%
                                    </span>
                                    <span className={`text-[10px] ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green/80' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red/80' : 'text-white/40'} font-black tracking-widest mt-0.5 uppercase`}>
                                        {mlProjection.direction}
                                    </span>
                                </div>
                                
                                <div className="h-12 w-px bg-white/10" />

                                <div className="flex-1 flex flex-col justify-center overflow-y-auto max-h-[65px] custom-scrollbar pr-1">
                                    {advisor_log ? (
                                        <div className="flex flex-col gap-1 border-l-2 border-neon-cyan/50 pl-2">
                                            {(() => {
                                                let text = typeof advisor_log === 'string' ? advisor_log : (advisor_log as any)?.content ?? 'Analizando...';
                                                let parsed: any = null;
                                                if (typeof text === 'string' && text.startsWith('{')) {
                                                    try {
                                                        parsed = JSON.parse(text);
                                                        text = parsed.logic || text;
                                                    } catch(e) {}
                                                } else if (typeof advisor_log === 'object' && advisor_log !== null && 'verdict' in advisor_log) {
                                                    parsed = advisor_log;
                                                    text = parsed.logic || 'Analizando...';
                                                }
                                                return (
                                                    <>
                                                        {parsed && (
                                                            <div className="flex items-center gap-2">
                                                                <span className={`text-[8.5px] font-black tracking-widest px-1.5 py-0.5 rounded ${parsed.verdict === 'GO' ? 'bg-green-500/20 text-green-400' : parsed.verdict === 'AVOID' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                                                                    ACTITUD: {parsed.verdict}
                                                                </span>
                                                                <span className={`text-[8.5px] font-black tracking-widest px-1.5 py-0.5 rounded ${parsed.threat === 'LOW' ? 'bg-green-500/10 text-green-400/80' : parsed.threat === 'HIGH' ? 'bg-red-500/10 text-red-400/80' : 'bg-yellow-500/10 text-yellow-500/80'}`}>
                                                                    THREAT: {parsed.threat}
                                                                </span>
                                                            </div>
                                                        )}
                                                        <p className="text-[9.5px] text-white/80 leading-relaxed font-mono tracking-tight mt-0.5">
                                                            <span className="text-neon-cyan opacity-80 font-bold mr-1">&gt;_</span>
                                                            {text}
                                                        </p>
                                                    </>
                                                );
                                            })()}
                                        </div>
                                    ) : (
                                        <p className="text-[9px] text-white/30 italic text-center animate-pulse">
                                            Qwen inferiendo sobre ticks. Aguardando dictamen...
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] flex-1 flex flex-col overflow-hidden relative">
                        {/* Header Controls (Global for Side Panel) */}
                        <div className="absolute top-4 right-4 flex items-center gap-1.5 z-50 bg-black/40 p-1 rounded-xl border border-white/10 backdrop-blur-md">
                            <button
                                onClick={() => setSidePanelMode('LOGS')}
                                className={`px-3 py-1.5 rounded-lg text-[9px] font-black tracking-widest transition-all ${sidePanelMode === 'LOGS' ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30 shadow-[0_0_10px_rgba(0,229,255,0.2)]' : 'text-white/30 hover:text-white/60'}`}
                            >
                                LOGS
                            </button>
                            <button
                                onClick={() => setSidePanelMode('NEWS')}
                                className={`px-3 py-1.5 rounded-lg text-[9px] font-black tracking-widest transition-all ${sidePanelMode === 'NEWS' ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/30 shadow-[0_0_10px_rgba(191,0,255,0.2)]' : 'text-white/30 hover:text-white/60'}`}
                            >
                                NEWS
                            </button>
                            <button
                                onClick={() => setSidePanelMode('LIQS')}
                                className={`px-3 py-1.5 rounded-lg text-[9px] font-black tracking-widest transition-all ${sidePanelMode === 'LIQS' ? 'bg-neon-red/20 text-neon-red border border-neon-red/30 shadow-[0_0_10px_rgba(255,0,60,0.2)]' : 'text-white/30 hover:text-white/60'}`}
                            >
                                LIQS
                            </button>
                            <button
                                onClick={() => setSidePanelMode('CAL')}
                                className={`px-3 py-1.5 rounded-lg text-[9px] font-black tracking-widest transition-all ${sidePanelMode === 'CAL' ? 'bg-amber-500/20 text-amber-500 border border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.2)]' : 'text-white/30 hover:text-white/60'}`}
                            >
                                CAL
                            </button>
                            <button
                                onClick={() => setSidePanelMode('OMEGA')}
                                className={`px-3 py-1.5 rounded-lg text-[9px] font-black tracking-widest transition-all ${sidePanelMode === 'OMEGA' ? 'bg-white/20 text-white border border-white/40 shadow-[0_0_10px_rgba(255,255,255,0.2)]' : 'text-white/30 hover:text-white/60'}`}
                            >
                                OMEGA
                            </button>
                        </div>

                        <div className="flex-1 flex flex-col overflow-hidden">
                            {sidePanelMode === 'LOGS' ? (
                                <>
                                    <div className="p-4 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-neon-cyan/10 to-transparent">
                                        <div className="flex items-center gap-2.5">
                                            <Terminal size={16} className="text-neon-cyan" />
                                            <h2 className="text-xs font-bold text-white/90 tracking-widest drop-shadow-[0_0_8px_rgba(0,229,255,0.5)]">FLUJO NEURAL</h2>
                                        </div>
                                    </div>
                                    <div className="p-5 flex flex-col gap-5 overflow-y-auto text-[11.5px] leading-relaxed font-mono custom-scrollbar">
                                        {neuralLogs.length === 0 ? (
                                            <div className="text-white/40 italic">Esperando inicialización del motor neural...</div>
                                        ) : (
                                            neuralLogs.map((log) => (
                                                <div key={log.id} className={`relative pl-4 ${log.type === 'ALERT' ? 'bg-neon-red/5 p-3 rounded-xl border border-neon-red/10' : ''}`}>
                                                    <div className={`absolute left-0 top-${log.type === 'ALERT' ? '0' : '1.5'} bottom-0 w-${log.type === 'ALERT' ? '1' : '0.5'} ${log.type === 'ALERT' ? 'bg-neon-red rounded-l-xl shadow-[0_0_10px_rgba(255,0,60,0.5)]' : log.type === 'SYSTEM' ? 'bg-gradient-to-b from-blue-500 to-transparent' : 'bg-gradient-to-b from-white/30 to-transparent'}`} />
                                                    <span className={`block mb-1 font-${log.type === 'ALERT' ? 'bold' : 'semibold'} flex items-center gap-2 ${log.type === 'ALERT' ? 'text-neon-red' : log.type === 'SYSTEM' ? 'text-blue-400' : 'text-white/40'}`}>
                                                        [{log.timestamp}] <ChevronRight size={12} /> {log.type}
                                                    </span>
                                                    <span className={`${log.type === 'ALERT' ? 'text-white/90 font-medium' : 'text-white/60'}`}>{log.message}</span>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </>
                            ) : sidePanelMode === 'NEWS' ? (
                                <NewsTerminal />
                            ) : sidePanelMode === 'LIQS' ? (
                                <LiquidationScanner />
                            ) : sidePanelMode === 'CAL' ? (
                                <MacroCalendar />
                            ) : (
                                <OmegaCentinelPanel />
                            )}
                        </div>
                    </div>
                </motion.section>
            </motion.div>
        </div>
    );
}
