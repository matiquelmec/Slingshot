'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Terminal, ChevronRight, Plus, X, Lock } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useTelemetryStore, Timeframe } from '../store/telemetryStore';

const QuantDiagnosticPanel = dynamic(() => import('../components/ui/QuantDiagnosticPanel'), { ssr: false });
const SessionClock = dynamic(() => import('../components/ui/SessionClock'), { ssr: false });
const MacroRadar = dynamic(() => import('../components/ui/MacroRadar'), { ssr: false });
const NewsTerminal = dynamic(() => import('../components/ui/NewsTerminal'), { ssr: false });
const LiquidationScanner = dynamic(() => import('../components/ui/LiquidationScanner'), { ssr: false });
const MacroCalendar = dynamic(() => import('../components/macro/MacroCalendar'), { ssr: false });

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
    const [sidePanelMode, setSidePanelMode] = useState<'LOGS' | 'NEWS' | 'LIQS' | 'CAL'>('LIQS');

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
        <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="show"
            className="h-full w-full grid grid-cols-12 gap-5 p-5 overflow-auto custom-scrollbar"
        >
            {/* Left Column: Watchlist */}
            <motion.section variants={itemVariants} className="col-span-12 lg:col-span-4 flex flex-col gap-5 min-h-[600px]">
                <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col relative overflow-hidden h-[400px]">
                    <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />
                    <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                        <div className="flex items-center gap-2.5">
                            <Activity size={16} className="text-neon-cyan" />
                            <h2 className="text-xs font-bold text-white/90 tracking-widest">CONTROL DE RADARES</h2>
                        </div>
                        <div className="flex items-center gap-2">
                            {/* Contador de tier */}
                            <span className={`text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full border ${watchlistFull ? 'text-amber-400 border-amber-400/30 bg-amber-400/10' : 'text-white/30 border-white/10'}`}>
                                {watchlist.length}/{maxWatchlist}
                            </span>
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-cyan opacity-40" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-cyan/80" />
                            </span>
                            {watchlistFull && (
                                <span title={`Máximo ${maxWatchlist} activos permitidos`}>
                                    <Lock size={13} className="text-amber-400/70 ml-1" />
                                </span>
                            )}
                            {!watchlistFull && (
                                <button
                                    onClick={() => setAddingSymbol(v => !v)}
                                    className="ml-1 text-white/30 hover:text-neon-cyan transition-colors"
                                    title="Añadir símbolo"
                                >
                                    <Plus size={14} />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Panel de búsqueda */}
                    <AnimatePresence>
                        {addingSymbol && !watchlistFull && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="overflow-hidden px-4 pt-3"
                            >
                                <div className="flex flex-col gap-2 relative">
                                    <div className="flex gap-2">
                                        <input
                                            autoFocus
                                            type="text"
                                            placeholder="Buscar par (ej. PEPE)..."
                                            value={newSymbol}
                                            onChange={e => setNewSymbol(e.target.value)}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter') {
                                                    if (filteredSymbols.length > 0) handleAddSymbol(filteredSymbols[0]);
                                                    else handleAddSymbol(newSymbol);
                                                }
                                            }}
                                            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none focus:border-neon-cyan/50"
                                        />
                                        <button onClick={handleAddSymbol} className="bg-neon-cyan/15 border border-neon-cyan/30 text-neon-cyan text-xs px-3 py-1.5 rounded-lg hover:bg-neon-cyan/25 transition-all">+</button>
                                    </div>
                                    {filteredSymbols.length > 0 && (
                                        <div className="flex flex-col gap-1 mt-1">
                                            {filteredSymbols.map(sym => (
                                                <button
                                                    key={sym}
                                                    onClick={() => handleAddSymbol(sym)}
                                                    className="w-full text-left px-3 py-1.5 text-xs bg-[#050B14] hover:bg-neon-cyan/20 border border-white/5 hover:border-neon-cyan/50 rounded-lg transition-colors text-white/80 hover:text-white"
                                                >
                                                    {sym}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Lista de activos */}
                    <div className="p-4 flex flex-col gap-2.5 overflow-y-auto flex-1 custom-scrollbar">
                        {watchlistLoading ? (
                            <div className="text-white/20 text-xs text-center mt-4 animate-pulse">Cargando watchlist...</div>
                        ) : watchlist.length === 0 ? (
                            <div className="text-white/20 text-xs text-center mt-4">
                                Sin activos. Usa el botón + para agregar.
                            </div>
                        ) : (
                            watchlist.map((entry) => {
                                const isActive = entry.asset === activeSymbol;
                                const summary = marketSummary[entry.asset];
                                
                                const biasColor = summary?.bias === 'BULLISH' ? 'text-neon-green' : 
                                                 summary?.bias === 'BEARISH' ? 'text-neon-red' : 'text-white/40';
                                
                                const regimeColor = summary?.regime === 'MARKUP' ? 'text-neon-green' :
                                                   summary?.regime === 'MARKDOWN' ? 'text-neon-red' :
                                                   summary?.regime === 'ACCUMULATION' ? 'text-yellow-400' :
                                                   summary?.regime === 'DISTRIBUTION' ? 'text-orange-400' : 'text-white/30';

                                return (
                                    <div
                                        key={entry.id}
                                        onClick={() => handleSymbolClick(entry)}
                                        className={`group flex flex-col gap-2 p-3 rounded-xl border transition-all cursor-pointer hover:-translate-y-0.5 ${isActive
                                            ? 'bg-neon-cyan/10 border-neon-cyan/30 shadow-[0_0_25px_rgba(0,229,255,0.1)]'
                                            : 'bg-white/[0.02] border-white/5 hover:border-white/20 hover:bg-white/[0.05]'
                                            }`}
                                    >
                                        <div className="flex justify-between items-center">
                                            <div className="flex items-center gap-2">
                                                <span className={`font-black tracking-widest text-[11px] ${isActive ? 'text-neon-cyan' : 'text-white/70 group-hover:text-white'}`}>
                                                    {entry.asset}
                                                </span>
                                                {summary?.bias && (
                                                    <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border border-current ${biasColor} opacity-70`}>
                                                        {summary.bias}
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-[10px] font-black text-white/80 tabular-nums">
                                                    {summary?.price ? `$${summary.price.toLocaleString('en-US', { maximumFractionDigits: (summary.price < 1 ? 4 : 2) })}` : (isActive && latestPrice ? `$${latestPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—')}
                                                </span>
                                                {!isActive && (
                                                    <button
                                                        onClick={e => { e.stopPropagation(); handleRemoveSymbol(entry); }}
                                                        className="opacity-0 group-hover:opacity-100 transition-opacity text-white/20 hover:text-red-400"
                                                    >
                                                        <X size={10} />
                                                    </button>
                                                )}
                                                <span className={`h-2 w-2 rounded-full ${isActive ? 'bg-neon-cyan shadow-[0_0_10px_rgba(0,229,255,1)] animate-pulse' : (summary ? 'bg-neon-green/40' : 'bg-white/10')}`} />
                                            </div>
                                        </div>
                                        
                                        {summary && (
                                            <div className="flex items-center justify-between text-[9px] font-bold tracking-tight">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-white/20 uppercase tracking-[0.1em]">Regime:</span>
                                                    <span className={`${regimeColor}`}>{summary.regime.replace('_', ' ')}</span>
                                                </div>
                                                <div className={`flex items-center gap-1 ${summary.trend > 0 ? 'text-neon-green' : summary.trend < 0 ? 'text-neon-red' : 'text-white/20'}`}>
                                                    {summary.trend > 0 ? '↗' : summary.trend < 0 ? '↘' : '→'}
                                                    <span className="text-white/30 uppercase tracking-[0.05em]">{summary.strategy.split(' ')[0]}</span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })
                        )}
                    </div>
                </div>

                <div className="flex-1 flex flex-col min-h-0">
                    <SessionClock />
                </div>
            </motion.section>

            {/* Middle Column */}
            <motion.section variants={itemVariants} className="col-span-12 lg:col-span-4 flex flex-col gap-5 min-h-[600px]">
                <div className="flex-1">
                    {isCalibrating ? (
                        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl h-full min-h-[400px] flex flex-col items-center justify-center p-5 shadow-2xl">
                            <div className="w-10 h-10 border-2 border-t-neon-cyan border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin mb-4"></div>
                            <p className="text-[10px] text-neon-cyan/80 tracking-[0.2em] font-bold uppercase drop-shadow-[0_0_8px_rgba(0,229,255,0.5)]">Calibrando Topografía...</p>
                            <p className="text-[9px] text-white/30 mt-2 text-center">Sincronizando SMC, Volatilidad y Niveles Institucionales</p>
                        </div>
                    ) : (
                        <QuantDiagnosticPanel />
                    )}
                </div>
                <div className="flex flex-col h-[300px]"><MacroRadar /></div>
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
                                    <p className="text-[9.5px] text-white/80 leading-relaxed font-mono tracking-tight border-l-2 border-neon-cyan/50 pl-2">
                                        <span className="text-neon-cyan opacity-80 font-bold mr-1">&gt;_</span>
                                        {typeof advisor_log === 'string' ? advisor_log : (advisor_log as any)?.content ?? 'Analizando...'}
                                    </p>
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
                        ) : (
                            <MacroCalendar />
                        )}
                    </div>
                </div>
            </motion.section>
        </motion.div>
    );
}
