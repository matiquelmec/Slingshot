'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, Zap, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useTelemetryStore, Timeframe } from '../../store/telemetryStore';

interface MarketState {
    asset: string;
    price: number;
    regime?: string;
    bias?: string;
    ob_count?: number;
    fvg_active?: boolean;
    is_killzone?: boolean;
    macro_risk?: boolean;
    liq_magnet?: boolean;
    ml_dir?: string;
    ml_prob?: number;
    sentiment?: string;
    session?: string;
    last_updated: string;
}

export default function ActiveAssetsMonitor() {
    const [globalStates, setGlobalStates] = useState<MarketState[]>([]);
    const [watchlist, setWatchlist] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const { activeSymbol, connect } = useTelemetryStore();
    
    // Obtenemos el flujo en tiempo real desde Websockets
    const marketSummary = useTelemetryStore(state => state.marketSummary);

    useEffect(() => {
        const loadInitialSync = async () => {
            try {
                // 1. Cargar Watchlist local del usuario
                const localWl = localStorage.getItem('slingshot_watchlist');
                const wlData = localWl ? JSON.parse(localWl) : [];
                const userAssets = wlData.map((w: any) => w.asset.toUpperCase()) || [];
                setWatchlist(userAssets);

                // 2. Hidratación Base
                const res = await fetch(`http://localhost:8000/api/v1/market-states`);
                if (res.ok) {
                    const masterStates = await res.json();
                    const formatted = masterStates.map((s: any) => ({
                        asset: s.asset,
                        price: s.price || s.current_price,
                        regime: s.regime,
                        bias: s.bias,
                        ob_count: s.ob_count,
                        fvg_active: s.fvg_active,
                        macro_risk: s.macro_risk,
                        liq_magnet: s.liq_magnet,
                        ml_dir: s.ml_dir,
                        ml_prob: s.ml_prob,
                        sentiment: s.sentiment,
                        session: s.session,
                        last_updated: s.last_updated || new Date().toISOString()
                    }));
                    setGlobalStates(formatted);
                }
            } catch (err) {
                console.error("Error in Radar Center sync:", err);
            } finally {
                setLoading(false);
            }
        };

        // Hidratación Inicial Estática (Zero-Polling)
        loadInitialSync();
    }, []);

    // 3. Fusión Híbrida Inteligente: Base de API Inicial fusionada con Eventos WebSocket
    const displayMap = new Map();
    globalStates.forEach(s => displayMap.set(s.asset.toUpperCase(), s));
    
    // Transmisión de estado vivo (Zustand radar_update)
    Object.values(marketSummary).forEach((s: any) => {
        if(s.asset) {
            const assetKey = s.asset.toUpperCase();
            displayMap.set(assetKey, {
               ...(displayMap.get(assetKey) || {}),
               ...s,
               price: s.price || s.current_price,
               last_updated: new Date().toISOString()
            });
        }
    });

    // 4. Aplicar el filtro de la watchlist del usuario
    const states = Array.from(displayMap.values()).filter((s: any) => 
        watchlist.includes(s.asset.toUpperCase())
    );

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
                                <div className="flex items-center gap-2">
                                    {state.is_killzone && (
                                        <div className="px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-[8px] font-black text-amber-500 tracking-tighter">
                                            KILLZONE
                                        </div>
                                    )}
                                    {state.macro_risk && (
                                        <div className="px-1.5 py-0.5 rounded bg-orange-500/10 border border-orange-500/20 text-[8px] font-black text-orange-500 tracking-tighter animate-pulse">
                                            MACRO RISK
                                        </div>
                                    )}
                                    {state.liq_magnet && (
                                        <div className="px-1.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 text-[8px] font-black text-cyan-400 tracking-tighter shadow-[0_0_10px_rgba(0,229,255,0.2)]">
                                            LIQ MAGNET
                                        </div>
                                    )}
                                    {getBiasIcon(state.bias)}
                                </div>
                            </div>

                            <div className="flex items-center gap-3 mt-1 pt-2 border-t border-white/5">
                                <div className="flex flex-col">
                                    <span className="text-[8px] text-white/20 font-bold uppercase">AI PROJ</span>
                                    <span className={`text-[10px] font-black ${state.ml_dir === 'ALCISTA' ? 'text-neon-cyan' : state.ml_dir === 'BAJISTA' ? 'text-neon-red' : 'text-white/40'}`}>
                                        {state.ml_dir} {state.ml_prob}%
                                    </span>
                                </div>
                                <div className="flex flex-col ml-auto text-right">
                                    <span className="text-[8px] text-white/20 font-bold uppercase">SENTIMENT</span>
                                    <span className={`text-[10px] font-black ${state.sentiment === 'BULLISH' ? 'text-neon-cyan' : state.sentiment === 'BEARISH' ? 'text-neon-red' : 'text-white/40'}`}>
                                        {state.sentiment}
                                    </span>
                                </div>
                            </div>

                            <div className="mt-auto pt-2">
                                <div className="text-xl font-mono font-bold text-white flex items-center justify-between">
                                    ${state.price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    <span className={`text-[8px] px-1 py-0.5 rounded ${state.ml_dir === 'ALCISTA' ? 'bg-neon-cyan/10 text-neon-cyan' : 'bg-neon-red/10 text-neon-red'}`}>
                                        {state.ml_dir === 'ALCISTA' ? '↗' : '↘'}
                                    </span>
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
