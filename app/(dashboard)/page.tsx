'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Terminal, ChevronRight, Plus, X, Lock } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useTelemetryStore, Timeframe } from '../store/telemetryStore';
import { useUser } from '../hooks/useUser';
import { createClient } from '@/lib/supabase/client';

const QuantDiagnosticPanel = dynamic(() => import('../components/ui/QuantDiagnosticPanel'), { ssr: false });
const SessionClock = dynamic(() => import('../components/ui/SessionClock'), { ssr: false });
const MacroRadar = dynamic(() => import('../components/ui/MacroRadar'), { ssr: false });

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
    const [tierLimitReached, setTierLimitReached] = useState(false);

    const { user } = useUser();
    const { activeSymbol, activeTimeframe, latestPrice, mlProjection, neuralLogs, connect } = useTelemetryStore();

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    useEffect(() => { setMounted(true); }, []);

    // Cargar watchlist desde Supabase al tener usuario
    useEffect(() => {
        if (!user) return;
        loadWatchlist();
    }, [user]);

    useEffect(() => {
        if (user) setTierLimitReached(watchlist.length >= user.tier.max_watchlist);
    }, [watchlist, user]);

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

    // ── DB Operations ─────────────────────────────────────────────────────────

    const loadWatchlist = useCallback(async () => {
        setWatchlistLoading(true);
        const supabase = createClient();
        const { data, error } = await supabase
            .from('user_watchlists')
            .select('id, asset, interval, alerts_enabled')
            .order('created_at', { ascending: true });

        if (!error && data) {
            // Auto-Seed: Si es un usuario nuevo con lista vacía, agregar el activo actual por defecto
            if (data.length === 0 && user && activeSymbol) {
                const { data: newData, error: insertError } = await supabase
                    .from('user_watchlists')
                    .insert({ user_id: user.id, asset: activeSymbol, interval: activeTimeframe, alerts_enabled: true })
                    .select('id, asset, interval, alerts_enabled')
                    .single();

                if (!insertError && newData) {
                    setWatchlist([newData as WatchlistEntry]);
                    setWatchlistLoading(false);
                    return;
                }
            }

            setWatchlist(data as WatchlistEntry[]);
            // Auto-conectar al primer activo de la lista (si lo hay) si no tenemos ninguno activo
            if (data.length > 0 && !activeSymbol) {
                connect(data[0].asset, data[0].interval as Timeframe);
            }
        }
        setWatchlistLoading(false);
    }, [activeSymbol, activeTimeframe, connect, user]);

    // Actualizar interval en Base de Datos cuando se cambia en el UI
    useEffect(() => {
        if (!user || !activeSymbol || !activeTimeframe || watchlist.length === 0) return;

        const currentEntry = watchlist.find(w => w.asset === activeSymbol);
        if (currentEntry && currentEntry.interval !== activeTimeframe) {
            const syncTimeframe = async () => {
                const supabase = createClient();
                await supabase
                    .from('user_watchlists')
                    .update({ interval: activeTimeframe })
                    .eq('id', currentEntry.id);

                setWatchlist(prev => prev.map(w =>
                    w.id === currentEntry.id ? { ...w, interval: activeTimeframe } : w
                ));
            };
            syncTimeframe();
        }
    }, [activeSymbol, activeTimeframe, user, watchlist]);

    const handleAddSymbol = useCallback(async (symToAdd?: string | React.MouseEvent) => {
        const sym = (typeof symToAdd === 'string' ? symToAdd : newSymbol).trim().toUpperCase();
        if (!sym || !user) return;

        // Validar límite de tier
        if (watchlist.length >= user.tier.max_watchlist) {
            setTierLimitReached(true);
            return;
        }

        // Evitar duplicados localmente antes de ir a la DB
        if (watchlist.find(w => w.asset === sym)) {
            setNewSymbol('');
            setAddingSymbol(false);
            return;
        }

        const supabase = createClient();
        const { data, error } = await supabase
            .from('user_watchlists')
            .insert({ user_id: user.id, asset: sym, interval: activeTimeframe, alerts_enabled: true })
            .select('id, asset, interval, alerts_enabled')
            .single();

        if (!error && data) {
            setWatchlist(prev => [...prev, data as WatchlistEntry]);
            if (watchlist.length === 0) {
                connect(data.asset, data.interval as Timeframe);
            }
        } else if (error) {
            console.error("Error agregando a watchlist:", error);
        }

        setNewSymbol('');
        setAddingSymbol(false);
        setFilteredSymbols([]);
    }, [newSymbol, user, watchlist, activeTimeframe]);

    const handleRemoveSymbol = useCallback(async (entry: WatchlistEntry) => {
        if (entry.asset === activeSymbol) return; // no eliminar el activo activo

        const supabase = createClient();
        const { error } = await supabase
            .from('user_watchlists')
            .delete()
            .eq('id', entry.id);

        if (!error) {
            setWatchlist(prev => prev.filter(w => w.id !== entry.id));
        }
    }, [activeSymbol]);

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

    const maxWatchlist = user?.tier.max_watchlist ?? 3;
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
                            {watchlistFull ? (
                                <span title={`Plan ${user?.tier.tier ?? 'free'}: máximo ${maxWatchlist} activos`}>
                                    <Lock size={13} className="text-amber-400/70 ml-1" />
                                </span>
                            ) : (
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
                    <div className="p-4 flex flex-col gap-2 overflow-y-auto flex-1 custom-scrollbar">
                        {watchlistLoading ? (
                            <div className="text-white/20 text-xs text-center mt-4 animate-pulse">Cargando watchlist...</div>
                        ) : watchlist.length === 0 ? (
                            <div className="text-white/20 text-xs text-center mt-4">
                                Sin activos. Usa el botón + para agregar.
                            </div>
                        ) : (
                            watchlist.map((entry) => {
                                const isActive = entry.asset === activeSymbol;
                                return (
                                    <div
                                        key={entry.id}
                                        onClick={() => handleSymbolClick(entry)}
                                        className={`group flex justify-between items-center text-xs p-3 rounded-lg border transition-all cursor-pointer hover:-translate-y-0.5 ${isActive
                                            ? 'bg-neon-cyan/10 border-neon-cyan/30 shadow-[0_0_20px_rgba(0,229,255,0.1)]'
                                            : 'bg-white/[0.02] border-white/5 hover:border-white/20 hover:bg-white/[0.05]'
                                            }`}
                                    >
                                        <span className={`font-bold tracking-wider ${isActive ? 'text-neon-cyan' : 'text-white/70 group-hover:text-white'}`}>
                                            {entry.asset}
                                        </span>
                                        <div className="flex items-center gap-2">
                                            {isActive && latestPrice && (
                                                <span className="text-neon-green font-bold text-[10px] tracking-wider">
                                                    ${latestPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                                                </span>
                                            )}
                                            {!isActive && (
                                                <button
                                                    onClick={e => { e.stopPropagation(); handleRemoveSymbol(entry); }}
                                                    className="opacity-0 group-hover:opacity-100 transition-opacity text-white/20 hover:text-red-400"
                                                >
                                                    <X size={10} />
                                                </button>
                                            )}
                                            <span className={`h-2 w-2 rounded-full ${isActive ? 'bg-neon-cyan shadow-[0_0_8px_rgba(0,229,255,0.8)]' : 'bg-neon-green/40'}`} />
                                        </div>
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
                <div className="flex-1"><QuantDiagnosticPanel /></div>
                <div className="flex flex-col h-[300px]"><MacroRadar /></div>
            </motion.section>

            {/* Right Column */}
            <motion.section variants={itemVariants} className="col-span-12 lg:col-span-4 flex flex-col gap-5 min-h-[600px]">
                <div className="h-44 bg-gradient-to-br from-[#050B14] to-black backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl flex flex-col justify-between p-5 relative overflow-hidden flex-shrink-0">
                    <div className={`absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(${mlProjection.direction === 'ALCISTA' ? '0,255,65' : mlProjection.direction === 'BAJISTA' ? '255,0,60' : '100,100,100'},0.1),transparent_50%)] pointer-events-none transition-colors duration-1000`} />
                    <div className="flex justify-between items-start z-10">
                        <p className="text-[10px] text-white/50 tracking-[0.2em] font-bold">PROYECCIÓN IA (XGBOOST)</p>
                        <Activity size={14} className={`${mlProjection.direction === 'ALCISTA' ? 'text-neon-green' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red' : 'text-gray-400'} opacity-50`} />
                    </div>
                    <div className="z-10 mt-auto">
                        <div className="flex items-baseline gap-3">
                            <span className={`text-4xl font-black ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green drop-shadow-[0_0_15px_rgba(0,255,65,0.5)]' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red drop-shadow-[0_0_15px_rgba(255,0,60,0.5)]' : 'text-white/50'} tracking-tighter`}>
                                {mlProjection.probability}%
                            </span>
                            <div className="flex flex-col">
                                <span className={`text-xs ${mlProjection.direction === 'ALCISTA' ? 'text-neon-green/80' : mlProjection.direction === 'BAJISTA' ? 'text-neon-red/80' : 'text-white/40'} font-semibold tracking-wider`}>
                                    {mlProjection.direction} ({activeTimeframe})
                                </span>
                                {mlProjection.reason && (
                                    <span className="text-[9px] text-white/40 mt-1 max-w-[200px] leading-tight break-words">{mlProjection.reason}</span>
                                )}
                            </div>
                        </div>
                        <div className="h-2 w-full bg-black rounded-full mt-4 overflow-hidden border border-white/5">
                            <motion.div
                                animate={{ width: `${mlProjection.probability}%` }}
                                transition={{ duration: 1.5, ease: [0.16, 1, 0.3, 1] }}
                                className={`h-full bg-gradient-to-r ${mlProjection.direction === 'ALCISTA' ? 'from-green-600 to-neon-green shadow-[0_0_15px_rgba(0,255,65,0.8)]' : mlProjection.direction === 'BAJISTA' ? 'from-red-600 to-neon-red shadow-[0_0_15px_rgba(255,0,60,0.8)]' : 'from-gray-600 to-gray-400'} relative`}
                            >
                                <div className="absolute top-0 right-0 bottom-0 w-4 bg-white/30 rounded-full blur-[2px]" />
                            </motion.div>
                        </div>
                    </div>
                </div>

                <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] flex-1 flex flex-col overflow-hidden relative">
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
                </div>
            </motion.section>
        </motion.div>
    );
}
