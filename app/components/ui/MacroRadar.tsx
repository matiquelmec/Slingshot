'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, BarChart, Zap, TrendingUp, TrendingDown, Info, DollarSign, Activity } from 'lucide-react';
import { useTelemetryStore } from '../../store/telemetryStore';

export default function MacroRadar() {
    const ghostData = useTelemetryStore(s => s.ghostData);

    if (!ghostData) {
        return (
            <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl p-4 flex flex-col items-center justify-center min-h-[120px]">
                <p className="text-[10px] text-white/20 italic animate-pulse">Sincronizando Capas Macro v4.0...</p>
            </div>
        );
    }

    const { 
        macro_bias, dxy_trend, dxy_price, nasdaq_trend, nasdaq_change_pct, risk_appetite,
        fear_greed_value, fear_greed_label, btc_dominance, funding_rate 
    } = ghostData;

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

    const getTrendIcon = (trend?: string) => {
        if (trend === 'BULLISH') return <TrendingUp size={10} className="text-neon-green" />;
        if (trend === 'BEARISH') return <TrendingDown size={10} className="text-neon-red" />;
        return <Activity size={10} className="text-white/20" />;
    };

    return (
        <div className="bg-[#050B14]/60 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl flex flex-col overflow-hidden relative">
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-cyan/20 to-transparent" />

            {/* Header Con Contexto Global */}
            <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.01]">
                <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                        <Globe size={14} className="text-neon-cyan animate-pulse" />
                        <h2 className="text-[11px] font-black text-white/90 tracking-widest uppercase italic">Radar Macro SMC</h2>
                    </div>
                </div>
                <motion.div 
                    initial={{ scale: 0.9 }}
                    animate={{ scale: 1 }}
                    className={`px-3 py-1 rounded-full text-[10px] font-black border ${biasBg} ${biasColor} shadow-[0_0_15px_-5px_currentColor]`}
                >
                    {macro_bias}
                </motion.div>
            </div>

            {/* Fila 1: Global Context (DXY / NASDAQ) */}
            <div className="p-4 grid grid-cols-2 gap-3 border-b border-white/5 bg-white/[0.02]">
                <div className="flex flex-col gap-1 boder border-white/5 bg-black/20 p-2 rounded-xl">
                    <div className="flex items-center justify-between">
                        <span className="text-[9px] font-bold text-white/30 uppercase tracking-tighter flex items-center gap-1">
                            <DollarSign size={10} className="text-neon-cyan" /> DXY Index
                        </span>
                        {getTrendIcon(dxy_trend)}
                    </div>
                    <div className="flex items-baseline gap-2">
                        <span className={`text-[11px] font-black ${dxy_trend === 'BULLISH' ? 'text-neon-green' : dxy_trend === 'BEARISH' ? 'text-neon-red' : 'text-white/40'}`}>
                            {dxy_trend || 'NEUTRAL'}
                        </span>
                        {typeof dxy_price === 'number' && dxy_price > 0 && (
                            <span className="text-[10px] text-white/40 font-mono">
                                {dxy_price.toFixed(2)}
                            </span>
                        )}
                    </div>
                </div>
                <div className="flex flex-col gap-1 border border-white/5 bg-black/20 p-2 rounded-xl">
                    <div className="flex items-center justify-between">
                        <span className="text-[9px] font-bold text-white/30 uppercase tracking-tighter flex items-center gap-1">
                            <BarChart size={10} className="text-orange-400" /> NASDAQ
                        </span>
                        {getTrendIcon(nasdaq_trend)}
                    </div>
                    <div className="flex items-baseline gap-2">
                        <span className={`text-[11px] font-black ${nasdaq_trend === 'BULLISH' ? 'text-neon-green' : nasdaq_trend === 'BEARISH' ? 'text-neon-red' : 'text-white/40'}`}>
                            {nasdaq_trend || 'NEUTRAL'}
                        </span>
                        {typeof nasdaq_change_pct === 'number' && (
                            <span className="text-[10px] text-white/40 font-mono">
                                {nasdaq_change_pct > 0 ? '+' : ''}{nasdaq_change_pct.toFixed(2)}%
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Fila 2: Crypto Metrics */}
            <div className="p-4 grid grid-cols-3 gap-3">
                {/* Fear & Greed */}
                <div className="flex flex-col gap-1">
                    <span className="text-[9px] font-bold text-white/30 tracking-wider">FEAR & GREED</span>
                    <div className="flex items-baseline gap-1">
                        <span className="text-lg font-black text-white/90">{fear_greed_value}</span>
                    </div>
                    <span className={`text-[8px] font-bold uppercase ${fear_greed_value > 50 ? 'text-neon-green/60' : 'text-neon-red/60'}`}>
                        {fear_greed_label}
                    </span>
                </div>

                {/* BTC Dominance */}
                <div className="flex flex-col gap-1">
                    <span className="text-[9px] font-bold text-white/30 tracking-wider">DOMINANCIA</span>
                    <div className="flex items-baseline gap-1">
                        <span className="text-lg font-black text-white/90">{btc_dominance?.toFixed(1)}%</span>
                    </div>
                    <span className="text-[8px] font-bold text-blue-400/60 uppercase">Market Weight</span>
                </div>

                {/* Funding Rate */}
                <div className="flex flex-col gap-1 relative group">
                    <span className="text-[9px] font-bold text-white/30 tracking-wider flex items-center gap-1">
                        FUNDING
                    </span>
                    <div className="flex items-baseline gap-1">
                        <span className={`text-lg font-black tabular-nums ${funding_rate > 0 ? 'text-neon-red' : 'text-neon-green'}`}>
                            {funding_rate?.toFixed(4)}%
                        </span>
                    </div>
                    <span className="text-[8px] font-bold text-white/20 uppercase">8h Average</span>
                </div>
            </div>

            {/* Macro Reason / Alert */}
            <div className="px-4 pb-4">
                <div className="bg-white/5 border border-white/10 rounded-xl p-2.5 flex gap-2 items-start relative overflow-hidden group">
                    <div className="absolute inset-0 bg-neon-cyan/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                    <Info size={12} className="text-neon-cyan mt-0.5 flex-shrink-0 relative z-10" />
                    <p className="text-[10px] text-white/60 leading-tight relative z-10 italic">
                        {ghost_data_reason(ghostData)}
                    </p>
                </div>
            </div>
        </div>
    );
}

function ghost_data_reason(data: any) {
    if (data.block_longs) return `🚫 LONGS BLOQUEADOS: ${data.reason}`;
    if (data.block_shorts) return `🚫 SHORTS BLOQUEADOS: ${data.reason}`;
    return data.reason || "Contexto Macro Estable.";
}
