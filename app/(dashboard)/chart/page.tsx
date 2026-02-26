'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart2 } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useTelemetryStore, Timeframe } from '../../store/telemetryStore';
import { useIndicatorsStore } from '../../store/indicatorsStore';

const TradingChart = dynamic(() => import('../../components/ui/TradingChart'), { ssr: false });

const TIMEFRAMES: Timeframe[] = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '8h', '1d', '1w', '1M'];

export default function ChartPage() {
    const [mounted, setMounted] = useState(false);
    const [showIndicators, setShowIndicators] = useState(false);

    const { indicators, toggleIndicator } = useIndicatorsStore();
    const indicatorsPanelRef = useRef<HTMLDivElement>(null);

    const {
        activeSymbol,
        activeTimeframe,
        setTimeframe
    } = useTelemetryStore();

    useEffect(() => {
        setMounted(true);
    }, []);

    useEffect(() => {
        if (!showIndicators) return;
        const handler = (e: MouseEvent) => {
            if (indicatorsPanelRef.current && !indicatorsPanelRef.current.contains(e.target as Node)) {
                setShowIndicators(false);
            }
        };
        document.addEventListener('click', handler);
        return () => document.removeEventListener('click', handler);
    }, [showIndicators]);

    if (!mounted) return null;

    const handleTimeframeClick = (tf: Timeframe) => {
        if (tf !== activeTimeframe) setTimeframe(tf);
    };

    const enabledCount = indicators.filter(i => i.enabled).length;

    return (
        <div className="h-full w-full bg-[#010204]/80 backdrop-blur-3xl rounded-2xl border border-white/10 relative flex flex-col overflow-hidden shadow-[inset_0_0_100px_rgba(0,0,0,1)]">
            {/* Watermark */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none overflow-hidden">
                <span className="text-[12rem] font-black text-white/[0.015] tracking-tighter transform rotate-12 scale-150">SLINGSHOT</span>
            </div>

            {/* Chart Toolbar */}
            <div className="h-12 border-b border-white/5 bg-gradient-to-r from-white/[0.03] to-transparent flex items-center px-5 gap-6 z-20 relative">
                {/* Timeframe Selector */}
                <div className="flex gap-1.5">
                    {TIMEFRAMES.map(tf => {
                        const isActiveTf = tf === activeTimeframe;
                        return (
                            <button
                                key={tf}
                                onClick={() => handleTimeframeClick(tf)}
                                className={`text-[11px] font-bold px-3 py-1.5 rounded-md transition-all ${isActiveTf
                                    ? 'bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/40 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
                                    : 'text-white/40 hover:text-white/90 hover:bg-white/5 border border-transparent'
                                    }`}
                            >
                                {tf}
                            </button>
                        );
                    })}
                </div>

                <div className="h-4 w-px bg-white/10" />

                {/* Active Symbol Display */}
                <span className="text-xs font-bold text-white/60 tracking-widest">{activeSymbol || 'Ninguno'}</span>

                <div className="h-4 w-px bg-white/10" />

                {/* Indicators Button */}
                <div className="relative" ref={indicatorsPanelRef}>
                    <button
                        onClick={() => setShowIndicators(v => !v)}
                        className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-all ${showIndicators
                            ? 'text-neon-cyan bg-neon-cyan/10 border-neon-cyan/30'
                            : 'text-white/40 border-transparent hover:text-white/90 hover:bg-white/5'
                            }`}
                    >
                        <BarChart2 size={14} />
                        <span>Indicadores</span>
                        {enabledCount > 0 && (
                            <span className="bg-neon-cyan/20 text-neon-cyan text-[10px] font-bold px-1.5 py-0.5 rounded-full border border-neon-cyan/30">
                                {enabledCount}
                            </span>
                        )}
                    </button>

                    {/* Indicators Dropdown */}
                    <AnimatePresence>
                        {showIndicators && (
                            <motion.div
                                initial={{ opacity: 0, y: -8, scale: 0.97 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: -8, scale: 0.97 }}
                                transition={{ duration: 0.15 }}
                                className="absolute top-full mt-2 left-0 w-64 bg-[#06101A]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-2xl z-[200] overflow-hidden"
                                onClick={e => e.stopPropagation()}
                            >
                                <div className="p-3 border-b border-white/5">
                                    <p className="text-[10px] text-white/40 font-bold tracking-widest">INDICADORES TÉCNICOS</p>
                                </div>
                                <div className="p-2 flex flex-col gap-1">
                                    {indicators.map(ind => (
                                        <button
                                            key={ind.id}
                                            onClick={() => toggleIndicator(ind.id)}
                                            className={`flex items-center justify-between w-full px-3 py-2.5 rounded-lg transition-all text-left ${ind.enabled ? 'bg-white/5' : 'hover:bg-white/[0.03]'}`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                                    style={{ backgroundColor: ind.color, boxShadow: ind.enabled ? `0 0 6px ${ind.color}` : 'none' }}
                                                />
                                                <div>
                                                    <p className={`text-xs font-bold ${ind.enabled ? 'text-white/90' : 'text-white/30'}`}>{ind.label}</p>
                                                    <p className="text-[10px] text-white/25">{ind.sublabel}</p>
                                                </div>
                                            </div>
                                            <div className={`w-8 h-4 rounded-full flex items-center px-0.5 transition-all duration-200 flex-shrink-0 ${ind.enabled ? 'bg-neon-green/20 border border-neon-green/30' : 'bg-black border border-white/10'}`}>
                                                <motion.div
                                                    layout
                                                    className={`w-3 h-3 rounded-full ${ind.enabled ? 'bg-neon-green' : 'bg-white/20'}`}
                                                    animate={{ x: ind.enabled ? 14 : 0 }}
                                                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                                                />
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Chart Area */}
            <div className="flex-1 w-full relative z-0 min-h-0">
                <TradingChart />
            </div>
        </div>
    );
}
