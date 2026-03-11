'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, ShieldCheck, ChevronRight, TrendingUp, TrendingDown, Clock, Layers } from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';

import { useTelemetryStore } from '../../store/telemetryStore';
import { formatPrice } from '@/lib/utils';

interface MarketState {
    asset: string;
    price: number;
    regime: string;
    macro_bias: string;
    change_24h: number;
    last_updated: string;
}

export default function ActiveAssetsMonitor() {
    const [states, setStates] = useState<MarketState[]>([]);
    const [loading, setLoading] = useState(true);
    const router = useRouter();
    const connect = useTelemetryStore(state => state.connect);

    useEffect(() => {
        const supabase = createClient();

        const fetchStates = async () => {
            // Buscamos los estados en la tabla 'market_states' (que crearemos en el backend)
            // Si falla (porque aún no existe), usaremos mock data para que el usuario vea el diseño
            const { data, error } = await supabase
                .from('market_states')
                .select('*')
                .order('asset', { ascending: true });

            if (!error && data) {
                setStates(data as MarketState[]);
            } else {
                // Mock data para previsualizar el diseño "Premium" mientras migramos el backend
                setStates([
                    { asset: 'BTCUSDT', price: 67241.50, regime: 'ACCUMULATION', macro_bias: 'BULLISH', change_24h: 2.5, last_updated: new Date().toISOString() },
                    { asset: 'ETHUSDT', price: 3452.12, regime: 'MARKUP', macro_bias: 'NEUTRAL', change_24h: -1.2, last_updated: new Date().toISOString() },
                    { asset: 'SOLUSDT', price: 142.88, regime: 'MARKDOWN', macro_bias: 'BEARISH', change_24h: 5.4, last_updated: new Date().toISOString() },
                    { asset: 'PAXGUSDT', price: 2341.00, regime: 'RANGING', macro_bias: 'NEUTRAL', change_24h: 0.1, last_updated: new Date().toISOString() }
                ]);
            }
            setLoading(false);
        };

        fetchStates();

        // Suscribirse a cambios en tiempo real
        const channel = supabase
            .channel('market_states_v1')
            .on('postgres_changes', { event: '*', schema: 'public', table: 'market_states' }, (payload) => {
                const newState = payload.new as MarketState;
                setStates(prev => {
                    const idx = prev.findIndex(s => s.asset === newState.asset);
                    if (idx >= 0) {
                        const next = [...prev];
                        next[idx] = newState;
                        return next;
                    }
                    return [...prev, newState];
                });
            })
            .subscribe();

        return () => { supabase.removeChannel(channel); };
    }, []);

    const handleSelectAsset = (asset: string) => {
        localStorage.setItem('slingshot_symbol', asset);
        connect(asset);
        router.push(`/signals?symbol=${asset}`);
    };

    return (
        <div className="flex-1 flex flex-col bg-[#050B14]/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-white/[0.01] to-transparent pointer-events-none" />

            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-3">
                    <Layers size={16} className="text-neon-cyan" />
                    <h3 className="text-xs font-bold text-white/90 tracking-[0.2em] uppercase">VIGILANCIA VIP</h3>
                </div>
                <div className="flex items-center gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-neon-green animate-pulse" />
                    <span className="text-[9px] font-bold text-white/40 tracking-wider">MODO INTELIGENTE ACTIVO</span>
                </div>
            </div>

            <div className="flex-1 p-4 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
                {states.map((state) => (
                    <motion.div
                        key={state.asset}
                        onClick={() => handleSelectAsset(state.asset)}
                        whileHover={{ scale: 1.01, x: 5 }}
                        className="p-4 bg-white/[0.02] border border-white/5 hover:border-neon-cyan/30 rounded-xl transition-all cursor-pointer group"
                    >
                        <div className="flex justify-between items-start mb-3">
                            <div className="flex items-center gap-3">
                                <div className="text-lg font-black text-white tracking-widest">{state.asset}</div>
                                <div className={`text-[10px] font-black px-2 py-0.5 rounded border ${state.change_24h >= 0 ? 'bg-neon-green/10 text-neon-green border-neon-green/20' : 'bg-neon-red/10 text-neon-red border-neon-red/20'
                                    }`}>
                                    {state.change_24h >= 0 ? '+' : ''}{state.change_24h}%
                                </div>
                            </div>
                            <div className="flex flex-col items-end">
                                <span className="text-sm font-black text-white font-mono tracking-tighter">
                                    {formatPrice(state.price)}
                                </span>
                                <span className="text-[9px] text-white/30 uppercase tracking-widest font-bold">BINANCE SPOT</span>
                            </div>
                        </div>

                        {/* Status Bars */}
                        <div className="grid grid-cols-2 gap-3 mb-3">
                            <div className="bg-black/40 p-2 rounded-lg border border-white/5 flex flex-col gap-1">
                                <span className="text-[8px] text-white/20 font-bold uppercase tracking-widest">ESTADO WYCKOFF</span>
                                <span className="text-[10px] font-black text-neon-cyan tracking-wider truncate">{state.regime}</span>
                            </div>
                            <div className="bg-black/40 p-2 rounded-lg border border-white/5 flex flex-col gap-1">
                                <span className="text-[8px] text-white/20 font-bold uppercase tracking-widest">SESGO MACRO (GHOST)</span>
                                <span className={`text-[10px] font-black tracking-wider truncate ${state.macro_bias === 'BULLISH' ? 'text-neon-green' : state.macro_bias === 'BEARISH' ? 'text-neon-red' : 'text-gray-400'
                                    }`}>
                                    {state.macro_bias}
                                </span>
                            </div>
                        </div>

                        <div className="mt-2 text-[10px] text-white/20 flex items-center justify-between">
                            <div className="flex items-center gap-1.5 group-hover:text-neon-cyan transition-colors">
                                VER DETALLES EN TERMINAL <ChevronRight size={10} />
                            </div>
                            <div className="flex items-center gap-1.5 italic">
                                Sync: {new Date(state.last_updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>

            {/* Bottom Insight */}
            <div className="p-4 bg-neon-cyan/5 border-t border-white/5">
                <div className="flex items-center gap-3">
                    <div className="p-1.5 bg-neon-cyan/20 rounded-lg">
                        <Activity size={14} className="text-neon-cyan" />
                    </div>
                    <p className="text-[10px] text-white/50 leading-tight">
                        <span className="text-white font-bold">ANALYSIS CORE:</span> Los indicadores se actualizan cada 15m. El "Fast Path" de precios es en tiempo real.
                    </p>
                </div>
            </div>
        </div>
    );
}
