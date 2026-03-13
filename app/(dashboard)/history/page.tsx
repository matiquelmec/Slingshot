'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, TrendingUp, TrendingDown, Target, Clock, AlertTriangle, CheckCircle2, XCircle, RefreshCw, Info } from 'lucide-react';


interface SignalEvent {
    id: string;
    asset: string;
    interval: string;
    signal_type: string;
    entry_price: number;
    stop_loss: number;
    take_profit: number;
    regime: string;
    strategy: string;
    status: string;
    created_at: string;
}

export default function HistoryPage() {
    const [signals, setSignals] = useState<SignalEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [filterAsset, setFilterAsset] = useState('ALL');

    useEffect(() => {
        fetchSignals();
        // Auto-refresh every 5 seconds since it's a local live memory stream
        const interval = setInterval(fetchSignals, 5000);
        return () => clearInterval(interval);
    }, []);

    const fetchSignals = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/api/v1/signals');
            if (res.ok) {
                const data = await res.json();
                setSignals(data as SignalEvent[]);
            }
        } catch(e) {
            console.error("Local Master not ready");
        } finally {
            setLoading(false);
        }
    };

    const StatusBadge = ({ status }: { status: string }) => {
        switch (status) {
            case 'ACTIVE':
                return <span className="px-2 py-0.5 rounded border border-neon-cyan/30 bg-neon-cyan/10 text-neon-cyan text-[9px] font-bold tracking-widest flex items-center gap-1"><Clock size={10} /> ACTIVE</span>;
            case 'HIT_TP':
                return <span className="px-2 py-0.5 rounded border border-neon-green/30 bg-neon-green/10 text-neon-green text-[9px] font-bold tracking-widest flex items-center gap-1"><CheckCircle2 size={10} /> HIT TP</span>;
            case 'HIT_SL':
                return <span className="px-2 py-0.5 rounded border border-neon-red/30 bg-neon-red/10 text-neon-red text-[9px] font-bold tracking-widest flex items-center gap-1"><XCircle size={10} /> HIT SL</span>;
            case 'EXPIRED':
                return <span className="px-2 py-0.5 rounded border border-white/20 bg-white/5 text-white/50 text-[9px] font-bold tracking-widest flex items-center gap-1"><AlertTriangle size={10} /> EXPIRED</span>;
            default:
                return <span className="text-white/30 text-[9px]">{status}</span>;
        }
    };

    const SignalTypeBadge = ({ type }: { type: string }) => {
        const isLong = type === 'LONG';
        return (
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded border ${isLong ? 'border-neon-green/30 bg-neon-green/10 text-neon-green' : 'border-neon-red/30 bg-neon-red/10 text-neon-red'}`}>
                {isLong ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                <span className="text-[10px] font-black tracking-widest">{type}</span>
            </div>
        );
    };

    const uniqueAssets = Array.from(new Set(signals.map(s => s.asset)));
    const filteredSignals = filterAsset === 'ALL' ? signals : signals.filter(s => s.asset === filterAsset);

    // Métricas rápidas
    const totalSignals = filteredSignals.length;
    const activeSignals = filteredSignals.filter(s => s.status === 'ACTIVE').length;

    return (
        <div className="h-full w-full flex flex-col p-6 overflow-hidden">
            {/* Header */}
            <div className="flex-none mb-6">
                <div className="flex items-center gap-3 mb-2">
                    <div className="p-2.5 bg-gradient-to-br from-blue-500/20 to-transparent rounded-xl border border-blue-500/30">
                        <Database size={20} className="text-blue-400" />
                    </div>
                    <div>
                        <h1 className="text-xl font-black text-white/90 tracking-[0.2em]">SESSION LOG</h1>
                        <p className="text-[10px] text-white/40 tracking-widest flex items-center gap-1.5 mt-1">
                            <Info size={10} className="text-neon-cyan" /> 
                            REGISTRO EFÍMERO DE EVENTOS EN LA SESIÓN DE MEMORIA ACTUAL (SE BORRA AL REINICIAR)
                        </p>
                    </div>
                </div>
            </div>

            {/* Stats & Filters */}
            <div className="flex-none flex items-center justify-between mb-4 p-4 border border-white/5 rounded-xl bg-black/40 backdrop-blur-xl">
                <div className="flex items-center gap-6">
                    <div className="flex flex-col">
                        <span className="text-[9px] text-white/40 font-bold tracking-widest mb-1">TOTAL SIGNALS</span>
                        <span className="text-lg font-black text-white/80">{totalSignals}</span>
                    </div>
                    <div className="w-px h-8 bg-white/10" />
                    <div className="flex flex-col">
                        <span className="text-[9px] text-white/40 font-bold tracking-widest mb-1">ACTIVE NOW</span>
                        <span className="text-lg font-black text-neon-cyan">{activeSignals}</span>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <span className="text-[10px] text-white/40 font-bold tracking-widest">FILTER ASSET:</span>
                    <select
                        value={filterAsset}
                        onChange={(e) => setFilterAsset(e.target.value)}
                        className="bg-black/50 border border-white/10 rounded px-2 py-1 text-xs text-white/70 outline-none focus:border-neon-cyan/50"
                    >
                        <option value="ALL">ALL ASSETS</option>
                        {uniqueAssets.map(a => (
                            <option key={a} value={a}>{a}</option>
                        ))}
                    </select>
                    
                    <button 
                        onClick={fetchSignals} 
                        className="ml-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded p-1.5 text-white/50 hover:text-white/90 transition-colors"
                        title="Actualizar registro"
                    >
                        <RefreshCw size={14} className={loading && signals.length > 0 ? "animate-spin" : ""} />
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-hidden border border-white/5 rounded-xl bg-black/40 backdrop-blur-xl flex flex-col">
                <div className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-white/10 bg-white/[0.02] text-[9px] font-bold text-white/40 tracking-widest">
                    <div className="col-span-2">TIMESTAMP</div>
                    <div className="col-span-2">ASSET / TF</div>
                    <div className="col-span-1">DIRECTION</div>
                    <div className="col-span-1">ENTRY</div>
                    <div className="col-span-1">TARGET</div>
                    <div className="col-span-1">STOP LOSS</div>
                    <div className="col-span-2">REGIME / STRATEGY</div>
                    <div className="col-span-2">STATUS</div>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    {loading ? (
                        <div className="flex items-center justify-center h-full">
                            <span className="text-neon-cyan/50 animate-pulse text-[10px] tracking-widest font-bold">QUERYING LOCAL MASTER...</span>
                        </div>
                    ) : filteredSignals.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-white/20 text-[10px] tracking-widest font-bold">
                            NO SIGNALS FOUND
                        </div>
                    ) : (
                        <div className="flex flex-col">
                            <AnimatePresence>
                                {filteredSignals.map((sig, i) => (
                                    <motion.div
                                        key={sig.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.02 }}
                                        className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-white/5 items-center hover:bg-white/[0.02] transition-colors"
                                    >
                                        <div className="col-span-2 text-[10px] text-white/60">
                                            {new Date(sig.created_at).toLocaleString()}
                                        </div>
                                        <div className="col-span-2 flex items-center gap-2">
                                            <span className="text-[11px] font-black text-white/90">{sig.asset}</span>
                                            <span className="text-[9px] px-1 rounded border border-white/10 bg-white/5 text-white/40">{sig.interval}</span>
                                        </div>
                                        <div className="col-span-1">
                                            <SignalTypeBadge type={sig.signal_type} />
                                        </div>
                                        <div className="col-span-1 text-[11px] font-mono text-white/80">
                                            ${sig.entry_price.toLocaleString()}
                                        </div>
                                        <div className="col-span-1 text-[11px] font-mono text-neon-green/80 flex items-center gap-1">
                                            <Target size={10} /> ${sig.take_profit.toLocaleString()}
                                        </div>
                                        <div className="col-span-1 text-[11px] font-mono text-neon-red/80">
                                            ${sig.stop_loss.toLocaleString()}
                                        </div>
                                        <div className="col-span-2 flex flex-col gap-0.5">
                                            <span className="text-[9px] font-bold text-white/60 truncate" title={sig.regime}>{sig.regime}</span>
                                            <span className="text-[8px] text-white/30 truncate" title={sig.strategy}>{sig.strategy}</span>
                                        </div>
                                        <div className="col-span-2">
                                            <StatusBadge status={sig.status} />
                                        </div>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
