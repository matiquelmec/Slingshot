'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Bell, Target, TrendingUp, TrendingDown, Clock, Search, ExternalLink } from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';

interface RadarSignal {
    id: string;
    asset: string;
    signal_type: string;
    entry_price: number;
    regime: string;
    confluence?: any;
    confluence_score?: number;
    status: string;
    created_at: string;
}

export default function RadarFeed() {
    const [signals, setSignals] = useState<RadarSignal[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');
    const router = useRouter();

    useEffect(() => {
        const supabase = createClient();

        // 1. Fetch initial signals (Only relevant ones for the Radar)
        const fetchSignals = async () => {
            const { data, error } = await supabase
                .from('signal_events')
                .select('*')
                .in('status', ['ACTIVE', 'BLOCKED_BY_MACRO']) // Filtro de Clase Mundial
                .order('created_at', { ascending: false })
                .limit(20);

            if (!error && data) {
                setSignals(data as RadarSignal[]);
            }
            setLoading(false);
        };

        fetchSignals();

        // 2. Subscribe to REALTIME updates (INSERT, UPDATE, DELETE)
        const channel = supabase
            .channel('radar_signals_v2')
            .on('postgres_changes', {
                event: '*', // Escuchar TODO
                schema: 'public',
                table: 'signal_events'
            }, (payload) => {
                if (payload.eventType === 'INSERT') {
                    const newSig = payload.new as RadarSignal;
                    if (['ACTIVE', 'BLOCKED_BY_MACRO'].includes(newSig.status)) {
                        setSignals(prev => [newSig, ...prev].slice(0, 50));
                    }
                } else if (payload.eventType === 'UPDATE') {
                    const updatedSig = payload.new as RadarSignal;

                    // Si ya no es relevante (ej: murió), lo eliminamos de la vista
                    if (!['ACTIVE', 'BLOCKED_BY_MACRO'].includes(updatedSig.status)) {
                        setSignals(prev => prev.filter(s => s.id !== updatedSig.id));
                    } else {
                        // Si sigue siendo relevante pero cambió algo (ej: precio entrada en evolución)
                        setSignals(prev => prev.map(s => s.id === updatedSig.id ? updatedSig : s));
                    }
                } else if (payload.eventType === 'DELETE') {
                    setSignals(prev => prev.filter(s => s.id !== payload.old.id));
                }
            })
            .subscribe();

        return () => {
            supabase.removeChannel(channel);
        };
    }, []);

    const filteredSignals = signals.filter(s =>
        s.asset.toLowerCase().includes(filter.toLowerCase()) ||
        s.signal_type.toLowerCase().includes(filter.toLowerCase())
    );

    const handleDeepDive = (signal: RadarSignal) => {
        // Guardamos en localStorage para que el Dashboard lo redireccione al activo correcto
        localStorage.setItem('slingshot_symbol', signal.asset);
        router.push(`/signals?symbol=${signal.asset}`);
    };

    return (
        <div className="flex-1 flex flex-col bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl overflow-hidden relative group">
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

            {/* Toolbar */}
            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                <div className="flex items-center gap-3">
                    <Activity size={16} className="text-neon-cyan" />
                    <h3 className="text-xs font-bold text-white/90 tracking-[0.2em] uppercase">MALLA DE EVENTOS GLOBAL</h3>
                </div>

                <div className="flex items-center gap-4">
                    <div className="relative">
                        <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                        <input
                            type="text"
                            placeholder="FILTRAR RADAR..."
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                            className="bg-black/40 border border-white/10 rounded-lg py-1.5 pl-8 pr-3 text-[10px] text-white focus:outline-none focus:border-neon-cyan/50 transition-all w-48"
                        />
                    </div>
                </div>
            </div>

            {/* Feed List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
                {loading ? (
                    <div className="h-full flex flex-col items-center justify-center gap-4 animate-pulse">
                        <div className="p-4 bg-neon-cyan/10 rounded-full">
                            <Target size={32} className="text-neon-cyan/40" />
                        </div>
                        <p className="text-[10px] text-white/20 tracking-[0.5em] font-bold">ESCANER OPERATIVO...</p>
                    </div>
                ) : filteredSignals.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center gap-4 text-white/20">
                        <Bell size={32} className="opacity-20" />
                        <p className="text-xs font-bold tracking-widest">NO HAY SEÑALES ACTIVAS EN EL RADAR</p>
                    </div>
                ) : (
                    <div className="flex flex-col gap-2">
                        <AnimatePresence initial={false}>
                            {filteredSignals.map((signal) => {
                                const isLong = signal.signal_type.toUpperCase().includes('LONG');
                                const score = signal.confluence_score || signal.confluence?.score || signal.confluence?.total_score || 0;
                                const isBlocked = signal.status === 'BLOCKED_BY_MACRO';

                                return (
                                    <motion.div
                                        key={signal.id}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        layout
                                        className={`group/card relative flex items-center gap-4 p-4 rounded-xl border transition-all ${isBlocked
                                            ? 'bg-black/40 border-white/5 opacity-60'
                                            : isLong
                                                ? 'bg-neon-green/5 border-neon-green/10 hover:border-neon-green/30'
                                                : 'bg-neon-red/5 border-neon-red/10 hover:border-neon-red/30'
                                            }`}
                                    >
                                        {/* Status Indicator Bar */}
                                        <div className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-r-full ${isBlocked ? 'bg-gray-700' : isLong ? 'bg-neon-green' : 'bg-neon-red'
                                            }`} />

                                        {/* Symbol Meta */}
                                        <div className="flex flex-col min-w-[100px]">
                                            <span className="text-lg font-black text-white tracking-tighter">{signal.asset}</span>
                                            <div className="flex items-center gap-1.5 mt-0.5">
                                                <div className={`h-1.5 w-1.5 rounded-full ${isLong ? 'bg-neon-green' : 'bg-neon-red'} animate-pulse`} />
                                                <span className={`text-[10px] font-bold uppercase tracking-wider ${isLong ? 'text-neon-green/80' : 'text-neon-red/80'}`}>
                                                    {signal.signal_type}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Entry Info */}
                                        <div className="flex-1 grid grid-cols-2 gap-4 border-x border-white/5 px-4 h-10 items-center">
                                            <div className="flex flex-col">
                                                <span className="text-[9px] text-white/30 font-bold tracking-widest uppercase">PRECIO ENTRADA</span>
                                                <span className="text-sm font-bold text-white/90 font-mono">
                                                    ${signal.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                </span>
                                            </div>
                                            <div className="flex flex-col">
                                                <span className="text-[9px] text-white/30 font-bold tracking-widest uppercase">RÉGIMEN</span>
                                                <span className="text-[10px] font-bold text-neon-cyan tracking-wider">{signal.regime}</span>
                                            </div>
                                        </div>

                                        {/* Confluence / Score */}
                                        <div className="flex flex-col items-center gap-1 min-w-[80px]">
                                            <span className="text-[9px] text-white/30 font-bold tracking-widest uppercase">CONFLUENCIA</span>
                                            <div className="flex items-center gap-2">
                                                <div className="h-1.5 w-12 bg-black/40 rounded-full overflow-hidden border border-white/5">
                                                    <motion.div
                                                        initial={{ width: 0 }}
                                                        animate={{ width: `${score}%` }}
                                                        className={`h-full ${isLong ? 'bg-neon-green' : 'bg-neon-red'}`}
                                                    />
                                                </div>
                                                <span className="text-[11px] font-black text-white">{score}%</span>
                                            </div>
                                        </div>

                                        {/* Action Button */}
                                        <div className="flex flex-col gap-1 items-end ml-auto">
                                            <div className="flex items-center gap-1.5 text-[10px] text-white/30 font-mono mb-1">
                                                <Clock size={10} />
                                                {new Date(signal.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </div>
                                            <button
                                                onClick={() => handleDeepDive(signal)}
                                                className="flex items-center gap-2 bg-white/5 border border-white/10 hover:bg-neon-cyan/20 hover:border-neon-cyan/40 text-white/60 hover:text-white px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all"
                                            >
                                                DEEP DIVE <ExternalLink size={10} />
                                            </button>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    </div>
                )}
            </div>
        </div>
    );
}
