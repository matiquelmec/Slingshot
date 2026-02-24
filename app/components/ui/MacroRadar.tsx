'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Globe, BarChart, Zap, TrendingUp, TrendingDown, Info } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

export default function MacroRadar() {
    const ghostData = useTelemetryStore(s => s.ghostData);

    if (!ghostData) {
        return (
            <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl p-4 flex flex-col items-center justify-center min-h-[120px]">
                <p className="text-[10px] text-white/20 italic">Sincronizando Radar Macro...</p>
            </div>
        );
    }

    const { fear_greed_value, fear_greed_label, btc_dominance, funding_rate, macro_bias } = ghostData;

    const biasColor = {
        BULLISH: 'text-neon-green',
        BEARISH: 'text-neon-red',
        NEUTRAL: 'text-white/50',
        BLOCK_LONGS: 'text-orange-400',
        BLOCK_SHORTS: 'text-purple-400',
        CONFLICTED: 'text-yellow-400'
    }[macro_bias] || 'text-white/50';

    const biasBg = {
        BULLISH: 'bg-neon-green/10 border-neon-green/20',
        BEARISH: 'bg-neon-red/10 border-neon-red/20',
        NEUTRAL: 'bg-white/5 border-white/10',
        BLOCK_LONGS: 'bg-orange-400/10 border-orange-400/20',
        BLOCK_SHORTS: 'bg-purple-400/10 border-purple-400/20',
        CONFLICTED: 'bg-yellow-400/10 border-yellow-400/20'
    }[macro_bias] || 'bg-white/5 border-white/10';

    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col overflow-hidden relative">
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                <div className="flex items-center gap-2.5">
                    <Globe size={15} className="text-neon-cyan" />
                    <h2 className="text-xs font-bold text-white/90 tracking-widest uppercase">Radar Macro (Ghost)</h2>
                </div>
                <div className={`px-2 py-0.5 rounded-full text-[9px] font-black border ${biasBg} ${biasColor}`}>
                    {macro_bias}
                </div>
            </div>

            <div className="p-4 grid grid-cols-3 gap-3">
                {/* Fear & Greed */}
                <div className="flex flex-col gap-1">
                    <span className="text-[9px] font-bold text-white/30 tracking-wider">FEAR & GREED</span>
                    <div className="flex items-baseline gap-1">
                        <span className="text-lg font-black text-white/90">{fear_greed_value}</span>
                    </div>
                    <span className="text-[8px] font-bold text-neon-cyan/60 uppercase">{fear_greed_label}</span>
                </div>

                {/* BTC Dominance */}
                <div className="flex flex-col gap-1">
                    <span className="text-[9px] font-bold text-white/30 tracking-wider">DOMINANCIA</span>
                    <div className="flex items-baseline gap-1">
                        <span className="text-lg font-black text-white/90">{btc_dominance.toFixed(1)}%</span>
                    </div>
                    <span className="text-[8px] font-bold text-blue-400/60 uppercase">Market Weight</span>
                </div>

                {/* Funding Rate */}
                <div className="flex flex-col gap-1">
                    <span className="text-[9px] font-bold text-white/30 tracking-wider">FUNDING</span>
                    <div className="flex items-baseline gap-1">
                        <span className={`text-lg font-black ${funding_rate > 0 ? 'text-neon-red' : 'text-neon-green'}`}>
                            {(funding_rate * 100).toFixed(4)}%
                        </span>
                    </div>
                    <span className="text-[8px] font-bold text-white/20 uppercase">8h Avg</span>
                </div>
            </div>

            {/* Macro Reason / Alert */}
            <div className="px-4 pb-4">
                <div className="bg-white/5 border border-white/10 rounded-xl p-2.5 flex gap-2 items-start">
                    <Info size={12} className="text-neon-cyan mt-0.5 flex-shrink-0" />
                    <p className="text-[10px] text-white/60 leading-tight">
                        {ghostData.reason || "Condiciones de red estables. Filtros de bias operativos."}
                    </p>
                </div>
            </div>
        </div>
    );
}
