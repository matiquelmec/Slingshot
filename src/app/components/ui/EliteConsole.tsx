'use client';

import React from 'react';
import { useTelemetryStore, MASTER_WATCHLIST } from '../../store/telemetryStore';
import { motion } from 'framer-motion';
import { Zap, Activity } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';

export default function EliteConsole() {
    const marketSummary = useTelemetryStore((state) => state.marketSummary);
    const activeSymbol = useTelemetryStore((state) => state.activeSymbol);
    const activeTimeframe = useTelemetryStore((state) => state.activeTimeframe);
    const connect = useTelemetryStore((state) => state.connect);

    return (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
            {MASTER_WATCHLIST.map((symbol) => {
                const data = marketSummary[symbol] || { price: 0, regime: 'SYNCING', bias: 'NEUTRAL', trend: 0 };
                const isActive = activeSymbol === symbol;

                const biasColor = data.bias === 'BULLISH' ? 'text-neon-green' 
                    : data.bias === 'BEARISH' ? 'text-neon-red' : 'text-white/40';
                const biasGlow = data.bias === 'BULLISH' ? 'bg-neon-green' 
                    : data.bias === 'BEARISH' ? 'bg-neon-red' : 'bg-white/20';

                return (
                    <motion.div
                        key={symbol}
                        onClick={() => connect(symbol, activeTimeframe)}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className={`p-3 rounded-xl border cursor-pointer transition-all duration-200 ${
                            isActive 
                                ? 'border-neon-cyan/60 bg-neon-cyan/10 ring-1 ring-neon-cyan/40 shadow-[0_0_20px_rgba(0,229,255,0.15)]' 
                                : 'border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]'
                        } backdrop-blur-xl flex flex-col gap-1.5 relative overflow-hidden`}
                    >
                        {/* Top Row: Symbol + Bias Dot */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                                <Zap size={10} className={`${isActive ? 'text-neon-cyan' : 'text-white/15'}`} />
                                <span className="text-[10px] font-black tracking-widest text-white/50 uppercase">{symbol.replace('USDT', '')}</span>
                            </div>
                            <div className="flex items-center gap-1">
                                <span className={`w-1.5 h-1.5 rounded-full ${biasGlow}`} />
                                <span className={`text-[7px] font-black ${biasColor} tracking-wider`}>{data.bias?.slice(0, 4)}</span>
                            </div>
                        </div>

                        <span className="text-base font-mono font-black text-white leading-none">
                            {formatCurrency(data.price)}
                        </span>

                        {/* Regime Bar */}
                        <div className="flex items-center justify-between text-[7px] font-bold text-white/20 tracking-widest uppercase">
                            <span>{data.regime || 'SYNC'}</span>
                        </div>
                        <div className="h-0.5 bg-white/5 rounded-full overflow-hidden">
                            <motion.div 
                                className={`h-full ${data.regime === 'MARKUP' || data.regime === 'ACCUMULATION' ? 'bg-neon-green' : data.regime === 'CHOPPY' ? 'bg-purple-400' : 'bg-neon-red'}`}
                                animate={{ width: `${Math.abs(data.trend || 50)}%` }}
                            />
                        </div>

                        {/* Priority Badge */}
                        <div className="flex items-center gap-1 mt-0.5">
                            <Activity size={8} className="text-neon-cyan/50 animate-pulse" />
                            <span className="text-[6px] font-bold text-white/15 tracking-widest uppercase">500ms</span>
                        </div>
                    </motion.div>
                );
            })}
        </div>
    );
}
