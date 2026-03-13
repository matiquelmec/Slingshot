'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, Zap, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useTelemetryStore, Timeframe } from '../../store/telemetryStore';

interface MarketState {
    asset: string;
    price: number;
    regime?: string;
    macro_bias?: string;
    session?: string;
    last_updated: string;
}

export default function ActiveAssetsMonitor() {
    const [states, setStates] = useState<MarketState[]>([]);
    const [watchlist, setWatchlist] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const { activeSymbol, connect } = useTelemetryStore();

    useEffect(() => {
        const loadSyncData = async () => {
            try {
                // 1. Cargar Watchlist local del usuario
                const localWl = localStorage.getItem('slingshot_watchlist');
                const wlData = localWl ? JSON.parse(localWl) : [];
                const userAssets = wlData.map((w: any) => w.asset.toUpperCase()) || [];
                setWatchlist(userAssets);

                // 2. Cargar estados del Master
                const res = await fetch(`http://localhost:8000/api/v1/market-states`);
                if (res.ok) {
                    const masterStates = await res.json();
                    
                    // Filtrar: Solo mostrar lo que el usuario PREVIAMENTE seleccionó en su control
                    // o los activos que el Master está procesando y que coinciden con su lista.
                    const filtered = masterStates.filter((s: MarketState) => 
                        userAssets.includes(s.asset.toUpperCase())
                    );
                    setStates(filtered);
                }
            } catch (err) {
                console.error("Error in Radar Center sync:", err);
            } finally {
                setLoading(false);
            }
        };

        loadSyncData();
        const interval = setInterval(loadSyncData, 5000); 
        return () => clearInterval(interval);
    }, []);

    const getBiasIcon = (bias?: string) => {
        switch (bias) {
            case 'BULLISH': return <TrendingUp size={14} className="text-neon-green" />;
            case 'BEARISH': return <TrendingDown size={14} className="text-neon-red" />;
            default: return <Minus size={14} className="text-white/30" />;
        }
    };

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-2">
                    <Zap size={16} className="text-amber-400" />
                    <h2 className="text-[10px] font-bold text-white/50 tracking-[0.2em]">RADAR CENTER V3.2</h2>
                </div>
                <span className="text-[9px] text-white/20 font-mono">LIVE MASTER SYNC</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {loading && states.length === 0 ? (
                    Array(4).fill(0).map((_, i) => (
                        <div key={i} className="h-32 bg-white/[0.02] border border-white/5 rounded-2xl animate-pulse" />
                    ))
                ) : (
                    states.map((state) => (
                        <motion.div
                            key={state.asset}
                            whileHover={{ y: -5, borderColor: 'rgba(0,229,255,0.3)' }}
                            onClick={() => connect(state.asset, '15m')}
                            className={`p-4 rounded-2xl border cursor-pointer transition-all flex flex-col gap-3 relative overflow-hidden ${
                                activeSymbol === state.asset 
                                ? 'bg-neon-cyan/10 border-neon-cyan/40 shadow-[0_0_20px_rgba(0,229,255,0.1)]' 
                                : 'bg-[#050B14]/60 border-white/5 hover:border-white/20'
                            }`}
                        >
                            <div className="flex justify-between items-start">
                                <div>
                                    <h3 className={`text-sm font-black tracking-tight ${activeSymbol === state.asset ? 'text-neon-cyan' : 'text-white/90'}`}>
                                        {state.asset}
                                    </h3>
                                    <p className="text-[10px] text-white/30 font-mono uppercase">{state.session || 'N/A'}</p>
                                </div>
                                {getBiasIcon(state.macro_bias)}
                            </div>

                            <div className="mt-auto">
                                <div className="text-xl font-mono font-bold text-white">
                                    ${state.price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </div>
                                <div className="flex items-center justify-between mt-1">
                                    <span className="text-[9px] font-bold text-neon-cyan/80 bg-neon-cyan/10 px-1.5 py-0.5 rounded border border-neon-cyan/20">
                                        {state.regime || 'STABLE'}
                                    </span>
                                    <span className="text-[8px] text-white/20">
                                        {new Date(state.last_updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </span>
                                </div>
                            </div>

                            {activeSymbol === state.asset && (
                                <div className="absolute top-0 right-0 p-1">
                                    <div className="relative flex h-2 w-2">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-cyan opacity-40"></span>
                                        <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-cyan"></span>
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    ))
                )}
            </div>
        </div>
    );
}
