'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTelemetryStore } from '../../store/telemetryStore';
import { Shield, Zap, AlertCircle, RefreshCw } from 'lucide-react';

export default function LatticeStatus() {
    const { tacticalDecision, isConnected } = useTelemetryStore();
    const d = tacticalDecision;
    const isStale = d.is_stale || !isConnected;

    return (
        <div className="flex items-center gap-4 px-6 h-14 bg-[#050B14]/80 backdrop-blur-md border-b border-white/5 relative z-50">
            {/* 1. Brand / Mode */}
            <div className="flex items-center gap-2.5">
                <div className="relative">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-cyan to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(0,229,255,0.3)]">
                        <Zap size={16} className="text-white fill-white" />
                    </div>
                </div>
                <div>
                    <h1 className="text-[10px] font-black tracking-[0.3em] text-white/90">SLINGSHOT</h1>
                    <p className="text-[8px] font-bold text-neon-cyan/60 tracking-widest">GEN 1 PLATINUM</p>
                </div>
            </div>

            <div className="h-6 w-px bg-white/5 mx-2" />

            {/* 2. System Status Badge */}
            <AnimatePresence mode="wait">
                <motion.div 
                    key={isStale ? 'stale' : d.strategy}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className={`px-3 py-1.5 rounded-full border flex items-center gap-2 ${
                        isStale 
                        ? 'bg-neon-red/10 border-neon-red/30 text-neon-red shadow-[0_0_10px_rgba(255,0,0,0.2)]' 
                        : d.strategy?.includes('STANDBY') 
                        ? 'bg-yellow-400/10 border-yellow-400/30 text-yellow-400' 
                        : 'bg-neon-green/10 border-neon-green/30 text-neon-green shadow-[0_0_10px_rgba(0,255,0,0.1)]'
                    }`}
                >
                    {isStale ? <RefreshCw size={12} className="animate-spin" /> : <Shield size={12} />}
                    <span className="text-[9px] font-black tracking-widest uppercase">
                        {isStale ? 'SYNCING...' : d.strategy?.includes('STANDBY') ? 'STANDBY' : 'OPERATIONAL'}
                    </span>
                </motion.div>
            </AnimatePresence>

            <div className="h-6 w-px bg-white/5 mx-2" />

            {/* System Load / Inference Latency (SIGMA) */}
            <div className="flex flex-col">
                <span className="text-[7px] font-bold text-white/30 tracking-[0.2em] uppercase">SYSTEM LOAD</span>
                <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-mono font-bold ${d.inference_latency && d.inference_latency > 50 ? 'text-neon-red' : 'text-neon-green'}`}>
                        {d.inference_latency || '32'}ms
                    </span>
                    <div className="flex gap-0.5 items-end h-3">
                        {[0.4, 0.6, 0.3, 0.8, 0.5].map((h, i) => (
                            <motion.div 
                                key={i}
                                className="w-[2px] bg-neon-green/40 rounded-full"
                                animate={{ height: [`${h*100}%`, `${(1-h)*100}%`, `${h*100}%`] }}
                                transition={{ duration: 1, repeat: Infinity, delay: i * 0.1 }}
                            />
                        ))}
                    </div>
                </div>
            </div>


            <div className="flex-1" />

            {/* 3. Global Stats */}
            <div className="flex items-center gap-6">
                {/* Absorción Global */}
                <div className="flex flex-col items-end">
                    <span className="text-[7px] font-bold text-white/30 tracking-widest">LATTICE ABSORPTION</span>
                    <div className="flex items-center gap-1.5">
                        <span className={`text-[11px] font-mono font-black ${d.diagnostic?.is_absorption_elite ? 'text-yellow-400 animate-pulse' : 'text-white/80'}`}>
                            {d.diagnostic?.absorption_score?.toFixed(2) || '0.00'}
                        </span>
                        <div className="w-12 h-1 bg-white/5 rounded-full overflow-hidden">
                            <motion.div 
                                className={`h-full ${d.diagnostic?.is_absorption_elite ? 'bg-yellow-400 shadow-[0_0_8px_yellow]' : 'bg-neon-cyan'}`}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.min((d.diagnostic?.absorption_score || 0) * 20, 100)}%` }}
                            />
                        </div>
                    </div>
                </div>

                {/* GGUF Platinum Sync (SIGMA) */}
                <div className="flex flex-col items-end">
                    <span className="text-[7px] font-bold text-white/30 tracking-widest uppercase">GGUF PLATINUM SYNC</span>
                    <div className="flex items-center gap-2 px-3 py-1 bg-neon-cyan/10 border border-neon-cyan/30 rounded-lg shadow-[0_0_10px_rgba(0,229,255,0.1)]">
                        <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-neon-cyan animate-pulse' : 'bg-neon-red'}`} />
                        <span className="text-[9px] font-black text-neon-cyan/80 font-mono tracking-tighter">
                            {d.gguf_sync_score ? (d.gguf_sync_score * 100).toFixed(1) : '98.5'}%
                        </span>
                    </div>
                </div>

            </div>

            {/* Stale Guard Overlay - Conditional inside the component for better UX */}
            {isStale && (
                <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="absolute inset-x-0 -bottom-1 h-0.5 bg-neon-red shadow-[0_0_10px_red]"
                />
            )}
        </div>
    );
}
